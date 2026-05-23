# Investigation 1: Backend Reuse Audit

## Scope

This investigation reviews the current Python/web backend and decides what should be kept, refactored, replaced, or dropped for the native Windows rewrite.

The target app is not a full port of the old Eel app. It is a smaller native app focused on:

- screen-region capture
- image filtering
- Tesseract OCR
- OpenAI translation
- async translation logs
- saved region/config state

## Executive Decision

The current backend is useful, but most modules should not be copied into the native app as-is.

The best approach is to extract the working logic into pure services and remove web/UI coupling. The reusable value is mainly in OCR cleanup, Tesseract path handling, OpenAI translation, log file format, and the async queue behavior recently added to `game2text.py`.

Estimated reuse:

- Direct reuse as-is: low.
- Logic reuse after refactor: medium to high.
- Architecture reuse from current app: selective.

The native rewrite should start with service modules under `newsource/native/` instead of importing old modules directly. Importing the old modules directly would pull in Eel, browser-window code, Textractor, Anki, dictionary, game script, and clipboard behavior that is outside the MVP.

## Reuse Table

| Source | Decision | Reason |
| --- | --- | --- |
| `translate.py` | Reuse with light refactor | The OpenAI translation path is already usable, but the function name still says Google Translate and the model/prompt are hard-coded. |
| `ocr.py` | Reuse with medium refactor | Tesseract OCR, confidence filtering, and OCR cleanup are valuable. The module is currently tied to base64 images, temp files, logging, and optional OCR Space. |
| `logger.py` | Extract pure log service | The log parser/writer and `|||TRANSLATION|||` format are useful. Eel UI callbacks and game script matching should be removed from the native service. |
| `config.py` | Reuse with medium refactor | Existing config section helpers are useful, but config path handling should be explicit and native sections must be added. |
| `tools.py` | Reuse selected path helpers | `bundle_dir`, Tesseract executable lookup, and tessdata lookup are useful. Tk file pickers and Textractor path helpers are not needed. |
| `util.py` | Reuse only small helpers | Directory creation and some image helpers are useful. Browser, Eel, PID, and Textractor text cleanup helpers are out of scope. |
| `imageprofile.py` | Reuse profile workflow, replace UI | YAML filter profiles, bundled profile loading, import, and export are required. Tk dialogs should be replaced by native PySide dialogs. |
| `web/image.js` | Port filter algorithms only | Invert, threshold, blur, and dilate logic should be implemented in Python/OpenCV/Pillow. Do not reuse JS. |
| `hotkeys.py` | Reuse concept, rewrite binding | The `keyboard` package can stay. Eel callback and current web flow should be replaced with a native signal/callback. |
| `game2text.py` | Reuse async idea, not module | Queue limit, background translation, and update-by-log-id behavior are important. The module itself is too coupled to Eel and old features. |
| Anki/Textractor/dictionary/audio/clipboard/game scripts | Drop for MVP | These are outside the native rewrite scope and would add coupling without helping the desired workflow. |

## Proposed Native Service Boundaries

### `config_service.py`

Responsibilities:

- Read and write `config.ini` from an explicit path.
- Preserve existing sections such as OpenAI key and OCR settings.
- Add and maintain native sections:
  - `[REGIONCONFIG]`
  - `[NATIVEAPP]`
- Avoid cwd-sensitive writes.

Important source reference:

- Current `config.py` has useful read helpers.
- `w_config()` currently reads `"config.ini"` relative to the current working directory, while other reads use an absolute `config_file`. The native version should avoid this mismatch.

### `paths.py` or `resource_service.py`

Responsibilities:

- Resolve development paths and PyInstaller packaged paths.
- Locate bundled Tesseract executable.
- Locate tessdata.

Important source reference:

- `tools.py` already has `bundle_dir`, `path_to_tesseract()`, and `get_tessdata_dir()`.
- The old `get_tessdata_dir()` mutates tessdata folders for legacy OCR mode by renaming directories. The native rewrite should avoid hidden folder mutation unless legacy mode is truly required.

### `filter_service.py`

Responsibilities:

- Apply image filters before OCR.
- Accept a PIL/OpenCV image and return a processed image.
- Preserve the full current filter workflow:
  - invert
  - binarize threshold
  - blur
  - dilate
  - reset/no filters
- Preserve live preview behavior for the selected/captured region.

Important source reference:

- `web/image.js` contains working JS implementations.
- `profiles/*.yaml` already use settings like:
  - `blurImageRadius`
  - `binarizeThreshold`
  - `dilate`
  - `invertColor`

Decision:

- Port filter behavior to Python instead of preserving the JS pipeline.

### `image_profile_service.py`

Responsibilities:

- Load bundled profiles from `profiles/`.
- Import a YAML profile selected by the user.
- Export current filter settings to YAML.
- Preserve current profile key compatibility:
  - `invertColor`
  - `dilate`
  - `blurImageRadius`
  - `binarizeThreshold`
- Add profile `name` from the file stem when loading bundled profiles, matching the current behavior.

Important source reference:

- `imageprofile.py` already implements:
  - `load_image_profiles()`
  - `open_image_profile()`
  - `export_image_profile()`

Required cleanup:

- Replace Tk dialogs with PySide file dialogs.
- Keep YAML format compatible with existing files.
- Do not defer this feature; it is part of the core native workflow.

### `ocr_service.py`

Responsibilities:

- Accept an image object or image path.
- Run Tesseract OCR.
- Return clean OCR text.
- Avoid logging, UI updates, base64 conversion, and Eel imports.

Important source reference:

- Keep/refactor from `ocr.py`:
  - `tesseract_ocr()`
  - `clean_ocr_text()`
  - `tesseract_data_to_text()`
  - `should_keep_low_confidence_english_token()`
  - Tesseract config using `--psm`, language, and tessdata path

Native function shape:

```python
def image_to_text(image, orientation="horizontal") -> str:
    ...
```

or:

```python
def image_to_text(image, settings: OcrSettings) -> str:
    ...
```

Notes:

- The current source does OCR from base64 and writes temp image files. Native capture can pass a screenshot image directly, so the base64 path should not be carried over.
- OCR Space can be skipped for MVP because the current real workflow uses local Tesseract.

### `translation_service.py`

Responsibilities:

- Translate OCR text using OpenAI.
- Read API key/model/prompt settings through `config_service.py`.
- Return translated text or a structured error.

Important source reference:

- `translate.py` already has the OpenAI call inside `google_translate()`.

Required cleanup:

- Rename the active provider clearly. Current UI/config says Google Translate, but the code path actually calls OpenAI.
- Move hard-coded model and prompt to constants or config-backed settings.
- Remove unused translator imports if the old providers are not part of MVP.

Suggested function shape:

```python
def translate_text(text: str, settings: TranslationSettings) -> str:
    ...
```

### `log_service.py`

Responsibilities:

- Generate unique log IDs.
- Append OCR text immediately.
- Update existing log entry with translated text.
- Read latest logs.
- Preserve compatibility with old log files.
- Provide file locking.
- Do not call UI code.

Important source reference:

- Keep/refactor from `logger.py`:
  - `get_time_string()`
  - `parse_time_string()`
  - `split_log_line()`
  - `log_text()`
  - `update_log_text()`
  - `get_logs()`
- Keep the microsecond log ID fix because second-level IDs caused duplicate DOM/log IDs during repeated hotkey presses.
- Keep the current translation separator:

```text
|||TRANSLATION|||
```

Required cleanup:

- Remove Eel calls:
  - `eel.show_logs`
  - `eel.updateLogDataById`
  - `eel.addLogs`
  - `eel.isMatchingScript`
- Remove game script matching from the native log service.
- Keep old-ID parsing for compatibility.

Suggested data shape:

```python
@dataclass
class LogEntry:
    id: str
    source_text: str
    translated_text: str | None = None
    translation_pending: bool = False
    translation_error: str | None = None
```

### `hotkey_service.py`

Responsibilities:

- Register/unregister global hotkeys.
- Call a native callback when `Ctrl+Q` is pressed.
- Allow hotkey refresh after config changes.

Important source reference:

- `hotkeys.py` already uses the `keyboard` package.

Required cleanup:

- Remove Eel callback calls.
- Native UI should receive the hotkey event through a Qt signal or thread-safe callback.

### `workers.py`

Responsibilities:

- Run OCR jobs away from the UI thread.
- Run translation jobs in a bounded queue.
- Emit native UI updates by `log_id`.

Important source reference:

- Keep the design from the modified `game2text.py`:
  - translation queue limit
  - background translation
  - log row update by `log_id`
  - queue-full state without sending another API request

Decision:

- Rebuild this in native style with either `ThreadPoolExecutor` plus PySide signals or Qt worker classes.

## Module Findings

### `ocr.py`

Useful:

- Tesseract OCR integration.
- English cleanup logic.
- Confidence-based token filtering.
- Logic that keeps long stuck-together Latin tokens so OCR text is not over-filtered.

Problems for native:

- `detect_and_log()` writes logs directly.
- It imports `logger`, `util`, `tools`, and `ocr_space`.
- It expects base64 images from the web UI.
- It writes temp files.

Decision:

- Extract OCR core into `ocr_service.py`.
- Keep old `ocr.py` as reference only.

### `translate.py`

Useful:

- Existing OpenAI call.
- Existing config-based API key lookup.
- Simple provider wrapper.

Problems for native:

- `google_translate()` actually performs OpenAI translation.
- Prompt and model are hard-coded.
- `translators as ts` is imported but not used in the current active path.
- Error handling returns strings directly, which can make UI errors look like valid translations.

Decision:

- Extract to `translation_service.py`.
- Use explicit provider naming.
- Return structured errors or raise controlled exceptions for the worker layer.

### `logger.py`

Useful:

- Text log format.
- Translation update format.
- Log ID generation.
- File locking.
- Old/new timestamp parsing.

Problems for native:

- Strong Eel dependency.
- Mixes file persistence, web UI events, base64 images, game script matching, and log parsing.
- Some old parsing/error blocks are messy and should not be carried over blindly.

Decision:

- Build a pure `log_service.py`.
- Treat current `logger.py` as a reference implementation for format compatibility.

### `config.py`

Useful:

- `ConfigParser` based read/write.
- OS-specific section suffix support.
- Existing section constants.

Problems for native:

- Write path should be made explicit.
- Native sections do not exist yet.
- Service should be robust when keys/sections are missing.

Decision:

- Build `config_service.py` from current ideas.
- Add default creation/repair for native sections.

### `tools.py`

Useful:

- Bundled path resolution.
- Tesseract path lookup.
- tessdata path lookup.

Problems for native:

- Tk dialogs are not appropriate for PySide.
- Textractor helpers are out of scope.
- Legacy tessdata mutation should be reviewed before reuse.

Decision:

- Extract path/resource helpers only.

### `util.py`

Useful:

- Directory creation helper.
- Some image conversion helpers as reference.
- `RepeatedTimer` may be useful later but is not essential for MVP.

Problems for native:

- Imports Eel.
- Browser detection and PID helpers are for the old web/Textractor app.
- Base64 helpers are mainly web-streaming artifacts.

Decision:

- Do not import this module in native code.
- Copy only small pure helpers if needed.

### `imageprofile.py` and `profiles/`

Useful:

- Existing YAML profile file shape.
- Existing filter setting names.
- Existing bundled profile loading behavior.
- Existing profile import/export behavior.

Problems for native:

- Uses Tk dialogs.
- File dialog ownership should move to PySide.

Decision:

- Keep profile load/import/export as a required feature.
- Store the active filter config in `config.ini`, but also support full YAML profile import/export.

### `game2text.py`

Useful:

- Recent async log translation architecture.
- Queue limit behavior.
- Separation between index/manual translation and log async translation.

Problems for native:

- This is the Eel app entrypoint.
- It imports many out-of-scope systems.

Decision:

- Reuse the async idea, not the file.

## Keep, Refactor, Replace, Drop

### Keep Conceptually

- Tesseract OCR as the OCR engine.
- OpenAI as the AI translation engine.
- `config.ini` as editable user config.
- Full image filter workflow.
- YAML image filter profiles and export/import.
- Text log files.
- `|||TRANSLATION|||` separator.
- Microsecond log IDs.
- Async translation queue limit of 5.
- Queue-full error without sending an extra API request.

### Refactor Into Services

- OCR core from `ocr.py`.
- Translation core from `translate.py`.
- Log persistence from `logger.py`.
- Config read/write from `config.py`.
- Tesseract path resolution from `tools.py`.
- Hotkey registration from `hotkeys.py`.

### Replace

- Eel/web update calls with PySide signals.
- JavaScript image filters with Python image filters.
- Browser/canvas screenshot flow with native screen capture.
- Web log DOM updates with native log row updates.

### Drop From MVP

- Eel.
- Browser streaming.
- Anki.
- Textractor.
- Dictionary lookup.
- Game script matching.
- Audio/media logging.
- Clipboard monitor.
- OCR Space cloud OCR.

## Risks

- Old modules import Eel at module import time, so importing them directly in native code can fail or pull unwanted runtime behavior.
- Tesseract resource paths may differ between development and packaged builds.
- DPI scaling and multi-monitor behavior are not handled by backend services and need investigation 2.
- Old log files may contain old second-level IDs, so native parsing should keep backward compatibility.
- If translation errors are returned as plain strings, the UI may display them as successful translations. Native workers should separate success from error state.

## Recommended First Implementation Slice

1. Create `newsource/native/config_service.py`.
2. Create `newsource/native/log_service.py`.
3. Port only pure OCR functions into `newsource/native/ocr_service.py`.
4. Port OpenAI translation into `newsource/native/translation_service.py`.
5. Add a small worker prototype that:
   - creates a log entry immediately
   - marks translation pending
   - updates the same log entry by `log_id`
   - rejects new translation work when the queue is full

This slice can be tested without building the native UI first.

## Investigation 1 Result

Backend reuse is viable, but the rewrite should not import the old backend modules wholesale.

The safest direction is a service extraction:

- old source files are references
- new native service files own the runtime
- UI communication happens through PySide signals
- logs/config remain compatible where useful

This keeps the working backend behavior while removing the old web app's accidental complexity.
