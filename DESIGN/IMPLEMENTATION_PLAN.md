# Implementation Plan

## Purpose

This plan breaks the native rewrite into implementation phases.

Each phase is designed to be small enough to execute in a separate session while still carrying enough context to preserve quality.

Before starting any phase, read:

1. `newsource/PROJECT_SPEC.md`
2. `newsource/DESIGN/APP_UX_DECISIONS.md`
3. `newsource/DESIGN/ARCHITECTURE.md`
4. The current phase section in this file

Do not import old root modules directly in native runtime. Use them only as references.

## Global Rules

- Source lives under `newsource/`.
- Native runtime must not depend on Eel.
- Keep services testable without opening windows.
- Use region id in models from the start.
- MVP exposes one region, region `1`.
- Keep filter order: `blur -> dilate -> invert -> threshold`.
- Every app launch creates a new session log file.
- Old logs do not need startup loading.
- Translation queue limit is 5.
- Queue-full sends no API request.
- Log and preview windows must persist size and position.
- OpenAI key remains in `config.ini`.
- Create `requirements-native.txt` for the new app.

## Phase 0: Native Skeleton And Requirements

### Goal

Create the native source skeleton and dependency file without implementing behavior.

### Files To Create

```text
newsource/native_app.py
newsource/build_native.bat
newsource/requirements-native.txt
newsource/native/__init__.py
newsource/native/core/__init__.py
newsource/native/core/models.py
newsource/native/core/paths.py
newsource/native/core/dpi.py
newsource/native/core/startup.py
newsource/native/app/__init__.py
newsource/native/config/__init__.py
newsource/native/logs/__init__.py
newsource/native/filters/__init__.py
newsource/native/ocr/__init__.py
newsource/native/translation/__init__.py
newsource/native/capture/__init__.py
newsource/native/regions/__init__.py
newsource/native/hotkeys/__init__.py
newsource/native/ui/__init__.py
newsource/profiles/light-background.yaml
newsource/profiles/wuwa.yaml
```

### Required Content

`requirements-native.txt` starts with:

```text
PySide6
mss
keyboard>=0.13.5
openai>=1.0.0
pytesseract==0.3.10
Pillow==10.0.1
opencv-python==4.8.0.76
numpy==1.26.0
PyYAML==6.0.1
pyinstaller==5.13.2
pyinstaller-hooks-contrib==2023.8
requests==2.31.0
```

`core/models.py` defines:

- `ScreenRegion`
- `FilterConfig`
- `LogEntry`
- `WindowState`

`core/paths.py` defines:

- `app_root()`
- `bundle_root()`
- common path helpers for config/logs/profiles/Tesseract.

`core/dpi.py` defines a Windows DPI-awareness helper.

`build_native.bat` builds from inside `newsource` and writes output to:

```text
newsource/dist/
```

`native_app.py` can initially print/start a minimal app placeholder, but should not import old source modules.

### Acceptance

- Files exist.
- `python -m py_compile` succeeds for new Python files.
- No native file imports `eel`.
- Models include `region_id` or region id fields.

### Verify

```powershell
python -m compileall -q newsource\native_app.py newsource\native
rg -n "import eel|from eel" newsource\native newsource\native_app.py
```

## Phase 1: Config Service And Runtime Folders

### Goal

Implement native config handling and runtime folder creation.

### Files

```text
newsource/native/config/service.py
newsource/native/core/startup.py
newsource/native/core/paths.py
```

### Source References

- `config.py`
- `config.ini`
- `INVESTIGATION_5_PACKAGING_ADMIN_AND_RUNTIME.md`
- `INVESTIGATION_6_MIGRATION_AND_COMPATIBILITY.md`

### Required Behavior

- Use explicit config path.
- Read existing `config.ini`.
- Create config if missing.
- Preserve old sections.
- Add missing native sections/keys:
  - `[REGION_1]`
  - `[NATIVEAPP]`
  - `[FILTERCONFIG]`
- Map `[REGIONCONFIG]` to `[REGION_1]` if needed.
- Backup config before first native section migration if practical.
- Ensure runtime folders:
  - `logs/text/`
  - `profiles/`

### Acceptance

- Existing config is not destroyed.
- Native sections are added.
- Existing OpenAI key remains present.
- Existing OCR settings remain present.
- Runtime folders are created.
- Read/write uses the same explicit path, not cwd-dependent `"config.ini"`.

### Verify

```powershell
python -m py_compile newsource\native\config\service.py newsource\native\core\startup.py
```

Recommended manual check:

- Copy `config.ini` to a temp file.
- Run config migration against the copy.
- Confirm old sections and native sections both exist.

## Phase 2: Log Service

### Goal

Implement pure log persistence for the new session.

### Files

```text
newsource/native/logs/service.py
newsource/native/core/models.py
```

### Source References

- `logger.py`
- `INVESTIGATION_4_NATIVE_UI_AND_ASYNC_LOG_ARCHITECTURE.md`
- `INVESTIGATION_6_MIGRATION_AND_COMPATIBILITY.md`

### Required Behavior

- Create a new session id at app startup using microseconds.
- Append source text immediately.
- Update translation in the same line with:

```text
|||TRANSLATION|||
```

- Use UTF-8.
- Use file lock.
- Remove newlines from log text.
- Parse old second-level IDs and new microsecond IDs.
- Provide parser for future/manual log load, but startup does not need old log loading.
- Do not persist queue/API errors as translations.

### Acceptance

- New session file is created.
- Appending two rows in the same second creates unique IDs.
- Translation update modifies the correct row.
- Parser reads old and new sample lines.
- No Eel import.

### Verify

```powershell
python -m py_compile newsource\native\logs\service.py
```

Recommended small script:

- create temp logs dir
- append source
- update translation
- parse the file back

## Phase 3: Profile Service And Filter Service

### Goal

Implement filter profile import/export and image filtering without UI.

### Files

```text
newsource/native/filters/profiles.py
newsource/native/filters/service.py
```

### Source References

- `web/image.js`
- `web/index.js` filter section
- `imageprofile.py`
- `profiles/light-background.yaml`
- `profiles/wuwa.yaml`
- `INVESTIGATION_3_IMAGE_FILTER_PIPELINE_AND_PROFILES.md`

### Required Behavior

Profile service:

- Load YAML profiles from runtime `profiles/`.
- Add display `name` from file stem.
- Import YAML file.
- Export YAML file.
- Preserve keys:
  - `invertColor`
  - `dilate`
  - `blurImageRadius`
  - `binarizeThreshold`
- Omit `binarizeThreshold` when binarize disabled.

Filter service:

- Accept `PIL.Image`.
- Return filtered `PIL.Image`.
- Do not mutate input.
- Keep order:

```text
blur -> dilate -> invert -> threshold
```

- Implement threshold using existing luminance coefficients.
- Implement invert directly.
- Implement JS-compatible 4-neighbor luminance dilate.
- Start with OpenCV Gaussian blur approximation.

### Acceptance

- Existing profiles load.
- Exported profile has old-compatible keys.
- Applying filters returns an image of the same size.
- OCR path can receive returned image later.

### Verify

```powershell
python -m py_compile newsource\native\filters\profiles.py newsource\native\filters\service.py
```

Recommended manual check:

- Load `profiles/wuwa.yaml`.
- Apply to a sample image.
- Export and inspect YAML.

## Phase 4: Translation And OCR Services

### Goal

Implement native OCR and translation services without UI.

### Files

```text
newsource/native/ocr/service.py
newsource/native/translation/service.py
```

### Source References

- `ocr.py`
- `translate.py`
- `tools.py`
- `INVESTIGATION_1_BACKEND_REUSE_AUDIT.md`

### Required Behavior

OCR:

- Accept `PIL.Image` or image path.
- Set Tesseract executable path from native path service.
- Use OCR config from config service.
- Preserve useful cleanup/confidence filtering from current `ocr.py`.
- Keep logic that does not over-filter stuck-together English text.
- Return clean text string.
- No logging inside OCR service.

Translation:

- Read OpenAI key from `[TRANSLATIONCONFIG]`.
- Preserve compatibility where `translation_service = Google Translate` means current OpenAI path.
- Use existing prompt behavior initially.
- Return translation text or raise controlled error.
- No UI calls.

### Acceptance

- OCR service compiles and can process a simple image manually.
- Translation service compiles.
- Missing OpenAI key produces controlled error.
- No Eel import.

### Verify

```powershell
python -m py_compile newsource\native\ocr\service.py newsource\native\translation\service.py
rg -n "import eel|from eel" newsource\native
```

## Phase 5: Event Bus, Workers, And Controller

### Goal

Implement the async workflow without full UI.

### Files

```text
newsource/native/app/event_bus.py
newsource/native/app/workers.py
newsource/native/app/app_controller.py
```

### Source References

- `game2text.py` async queue functions
- `INVESTIGATION_4_NATIVE_UI_AND_ASYNC_LOG_ARCHITECTURE.md`
- `ARCHITECTURE.md`

### Required Behavior

- Event bus exposes signals:
  - `log_entry_created`
  - `log_entry_updated`
  - `status_changed`
  - `capture_failed`
  - `preview_image_updated`
  - `region_updated`
- Workers use:

```python
capture_executor = ThreadPoolExecutor(max_workers=1)
translation_executor = ThreadPoolExecutor(max_workers=5)
translation_slots = threading.BoundedSemaphore(5)
```

- Queue full emits row-level red error patch and sends no API request.
- Controller owns capture/OCR/translation orchestration.
- No worker touches UI widgets directly.

### Acceptance

- Simulated OCR text can create a log row and queue translation.
- Simulated queue full emits correct update.
- Translation done updates correct row by `log_id`.
- Executors shut down cleanly.

### Verify

```powershell
python -m py_compile newsource\native\app\event_bus.py newsource\native\app\workers.py newsource\native\app\app_controller.py
```

## Phase 6: Minimal PySide App And Window Persistence

### Goal

Create three native windows and persist their position/size/open state.

### Files

```text
newsource/native_app.py
newsource/native/ui/main_window.py
newsource/native/ui/log_window.py
newsource/native/ui/log_row_widget.py
newsource/native/ui/preview_window.py
newsource/native/ui/filter_panel.py
```

### Required Behavior

Main window:

- Buttons exist:
  - capture now
  - select region
  - show/hide border
  - open/close log
  - open/close preview
  - open config
  - reload config
- Status label exists.

Log window:

- Resizable.
- Always-on-top default.
- Row format only source/divider/translation state.
- Auto-scroll bottom on new row.
- No icons/actions.

Preview window:

- Resizable.
- Contains preview area and filter controls.
- Filter controls do not stretch awkwardly.
- Shows active profile.

Persistence:

- Save window open state and geometry.
- Restore on startup.

### Acceptance

- App starts with PySide.
- Three windows can be opened/closed.
- Closing/reopening app restores windows according to config.
- Log row can be added from a test button/event.

### Verify

```powershell
python -m compileall -q newsource\native_app.py newsource\native
python newsource\native_app.py
```

## Phase 7: Screen Capture, Region Overlay, Border

### Goal

Implement region selection and screen capture.

### Files

```text
newsource/native/capture/screen_capture.py
newsource/native/regions/overlay.py
newsource/native/regions/border.py
newsource/native/hotkeys/service.py
newsource/native/core/dpi.py
```

### Source References

- `INVESTIGATION_2_SCREEN_CAPTURE_AND_REGION_OVERLAY.md`
- `hotkeys.py`

### Required Behavior

- Select region by button and `Ctrl+Shift+Q`.
- Mouse release saves immediately.
- Escape cancels.
- Region saved as physical pixels.
- Border visible by default after region exists.
- Border can be hidden/shown.
- Capture hides border before screenshot and restores after.
- `Ctrl+Q` triggers capture for region 1.
- If no region exists, either open region selection or show clear status.

### Acceptance

- Region can be selected on screen.
- Region persists after restart.
- Border appears after restart when region exists.
- Capture image size equals selected region size.
- Hotkeys trigger expected actions.

### Verify

Manual:

- Test 100% DPI.
- If possible, test 125% and 150% DPI.
- Test borderless/windowed game or normal app window.

Compile:

```powershell
python -m py_compile newsource\native\capture\screen_capture.py newsource\native\regions\overlay.py newsource\native\regions\border.py newsource\native\hotkeys\service.py
```

## Phase 8: Connect Full Runtime Flow

### Goal

Make the MVP workflow work end to end.

### Flow

```text
Ctrl+Q
  -> capture region
  -> apply filters
  -> OCR
  -> log source
  -> show pending translation
  -> OpenAI translate
  -> update log row
  -> update log file
```

### Required Behavior

- OCR no text creates red row:

```text
Không nhận diện được text.
```

- Queue full creates red row-level message.
- Translation completion can arrive out of order.
- Preview uses same filter service as OCR.
- No double translation path exists.

### Acceptance

- Real Ctrl+Q creates source row.
- Translation appears under the correct row.
- Five rapid requests can run.
- Sixth active translation shows queue-full and sends no API request.
- Log file contains source and translated text for successful translations.

### Verify

```powershell
python -m compileall -q newsource\native_app.py newsource\native
python newsource\native_app.py
```

Manual:

- Use a game/screenshot region.
- Trigger repeated captures.
- Reload app and confirm a new session file starts.

## Phase 9: Packaging

### Goal

Create native build files and verify packaged runtime.

### Files

```text
newsource/build_native.bat
newsource/native-game2text.spec
newsource/run_native_admin.bat
```

### Source References

- `build.bat`
- `game2text.spec`
- `run_admin.bat`
- `INVESTIGATION_5_PACKAGING_ADMIN_AND_RUNTIME.md`

### Required Behavior

- One-folder PyInstaller build.
- Entry: `newsource/native_app.py`.
- Include:
  - `resources/bin/win/tesseract`
  - starter `config.ini`
  - `profiles/`
- Do not include:
  - Eel/web
  - Anki
  - Textractor
  - dictionaries
  - Sudachi
  - old logs
- Runtime files beside exe:
  - `config.ini`
  - `logs/`
  - `profiles/`

### Acceptance

- Packaged exe starts.
- Packaged exe finds Tesseract.
- Packaged exe creates/writes logs.
- Packaged exe loads profiles.
- Packaged exe does not overwrite existing runtime config/logs/profiles.
- Admin launcher starts app elevated.

### Verify

```powershell
newsource\build_native.bat
```

Manual:

- Run packaged app.
- Trigger OCR.
- Trigger translation.
- Restart and verify window/region/filter persistence.

## Phase 10: Stabilization And Cleanup

### Goal

Stabilize MVP and remove temporary debug code.

### Checklist

- No old runtime imports from root modules.
- No Eel imports.
- No hidden double API call.
- Config migration is safe.
- Hotkeys unregister on exit.
- Executors shut down on exit.
- Window state is saved reliably.
- Preview and OCR use same filter output.
- Queue full behavior is correct.
- Empty OCR behavior is correct.
- Packaged app still works.

### Verify

```powershell
rg -n "import eel|from eel|python -m eel|web\\" newsource
python -m py_compile newsource\native_app.py newsource\native\*.py
```

Manual smoke test:

1. Start app.
2. Select region.
3. Confirm border visible.
4. Open preview.
5. Change filters.
6. Capture with `Ctrl+Q`.
7. Confirm source row.
8. Confirm translation row.
9. Restart.
10. Confirm window state and region border restore.

## Suggested Execution Order

Do phases in order:

1. Phase 0
2. Phase 1
3. Phase 2
4. Phase 3
5. Phase 4
6. Phase 5
7. Phase 6
8. Phase 7
9. Phase 8
10. Phase 9
11. Phase 10

Reason:

- Service layer before UI reduces coupling.
- UI skeleton before screen overlay reduces debugging complexity.
- Packaging comes after runtime behavior is stable.

## How To Start A Future Implementation Session

Use this prompt shape:

```text
Thực hiện Phase N trong newsource/DESIGN/IMPLEMENTATION_PLAN.md.
Đọc PROJECT_SPEC.md, APP_UX_DECISIONS.md, ARCHITECTURE.md và section Phase N trước khi code.
Giữ source native độc lập, không import module cũ runtime.
Sau khi làm xong, chạy verify trong phase đó và tóm tắt file đã sửa.
```

This keeps each implementation step bounded and self-contained.
