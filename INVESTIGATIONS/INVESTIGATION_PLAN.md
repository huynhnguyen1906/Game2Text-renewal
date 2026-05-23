# Native Rewrite Investigation Plan

## Purpose

This document lists the investigations needed before implementing the native Windows rewrite. The goal is to reuse as much of the current backend as possible while removing the Eel/web streaming UI.

Each investigation should end with concrete decisions, prototype notes if needed, and a short list of files/modules to keep, refactor, or replace.

## Investigation 1: Backend Reuse Audit

### Questions

- Which current Python modules can be reused as-is?
- Which modules need refactoring to remove Eel/UI coupling?
- Which modules should be dropped from the native rewrite?
- What should become standalone services in `newsource/native/`?

### Source Areas

- `ocr.py`
- `translate.py`
- `logger.py`
- `config.py`
- `tools.py`
- `util.py`
- `config.ini`

### Things To Verify

- `ocr.py` can expose a pure `image_to_text()` API that accepts an image and returns text.
- `translate.py` can be reused without depending on web UI state.
- `logger.py` needs separation between file persistence and UI events.
- `config.py` can safely read/write new native sections.
- Tesseract resource lookup works in dev and packaged builds.

### Expected Output

- Table: `keep as-is`, `reuse with refactor`, `replace`, `drop`.
- Proposed service boundaries:
  - `ocr_service.py`
  - `translation_service.py`
  - `log_service.py`
  - `config_service.py`

## Investigation 2: Screen Capture And Region Overlay

### Questions

- How should the app let the user select a screen region directly over the game?
- Which capture library should be used for fast region screenshots?
- How should the selected region be saved and restored?
- How should the region border be shown/hidden?
- What DPI and multi-monitor issues need handling?

### Candidate Tools

- `mss` for screen capture.
- `PySide6` transparent fullscreen overlay for region selection.
- `PySide6` always-on-top border window for visible selected-region outline.

### Things To Verify

- Absolute screen coordinates match screenshot coordinates.
- Windows DPI scaling at 100%, 125%, and 150%.
- Multi-monitor behavior.
- Borderless/windowed games.
- Exclusive fullscreen limitations.
- Global hotkey still works while game window is focused.

### Expected Output

- Prototype notes for selecting a region and taking a screenshot.
- Final coordinate model:
  - absolute screen coordinates
  - monitor id
  - width/height
- Proposed config section:

```ini
[REGIONCONFIG]
x = 100
y = 200
width = 900
height = 180
monitor = 1
show_region_border = true
```

## Investigation 3: Image Filter Pipeline And Profiles

### Questions

- How should the full current image filter workflow be preserved?
- Can the current JavaScript filters be ported cleanly to Python?
- How should filter settings be previewed and saved?
- How should profile load/import/export work in the native app?
- How should bundled profiles under `profiles/` remain compatible?

### Source Areas

- `web/index.js`
- `web/image.js`
- `imageprofile.py`
- `profiles/`

### Required Filters

- invert
- binarize threshold
- blur
- dilate
- reset filters
- load bundled profiles
- import YAML profile
- export current filter settings to YAML

### Things To Verify

- Filter output improves OCR on game screenshots.
- Filter order should match the current app where useful.
- Preview image renders quickly in the native UI.
- Filter settings can be stored in `config.ini` and exported/imported as profile YAML.
- Existing profile keys stay compatible:
  - `invertColor`
  - `dilate`
  - `blurImageRadius`
  - `binarizeThreshold`

### Expected Output

- Python function shape:

```python
def apply_filters(image, filter_config):
    ...
```

- Profile service shape:

```python
def load_profiles(profile_dir):
    ...

def import_profile(path):
    ...

def export_profile(path, filter_config):
    ...
```

- Decision on native profile UI and config persistence.

## Investigation 4: Native UI And Async Log Architecture

### Questions

- What should the native log window look like?
- Which Qt widgets should represent log rows?
- How should OCR jobs and translation jobs communicate with the UI?
- Should async use `QThreadPool`, `QThread`, or `ThreadPoolExecutor`?
- How should queue-full state be displayed?

### Required UI States

- source OCR text
- translation pending/loading
- translated text
- translation error
- queue full
- OCR failure

### Things To Verify

- Log rows update by unique `log_id`.
- Translation completion can arrive out of order.
- Queue limit prevents uncontrolled API calls.
- Log window position and size are saved/restored.
- Always-on-top option works.

### Expected Output

- UI skeleton decision:
  - main window vs log-only window
  - row widget layout
  - settings/filter panel placement
- Async architecture decision:
  - worker type
  - queue limit
  - signal/event shape

## Investigation 5: Packaging, Admin, And Runtime

### Questions

- How should the native app be packaged?
- How should it request administrator privileges?
- How should resource paths work in development and packaged builds?
- Which dependencies are needed in `requirements.txt`?
- How should the OpenAI key remain in `config.ini`?

### Candidate Tools

- `PyInstaller`
- existing `keyboard` library
- existing Tesseract resources under `resources/bin/win/tesseract`

### Things To Verify

- App can run as admin from a `.bat` or self-relaunch.
- `Ctrl+Q` works while another application/game is focused.
- Tesseract path resolves after packaging.
- `config.ini` remains editable next to the executable.
- Build does not overwrite user logs/config unexpectedly.

### Expected Output

- Build command.
- Admin launch strategy.
- Dependency list for native app.
- Runtime folder layout.

## Investigation 6: Migration And Compatibility

### Questions

- Should native app read old log files?
- Should it write the same `|||TRANSLATION|||` format?
- Should it share `config.ini` with the old Eel app?
- How should old timestamp log IDs be handled?

### Things To Verify

- Existing log parser handles both old IDs and new microsecond IDs.
- Native app avoids duplicate IDs.
- Old web app can still run if needed.

### Expected Output

- Log format decision.
- Backward compatibility decision.
- Migration notes for old users.

## Recommended Order

1. Backend Reuse Audit.
2. Screen Capture And Region Overlay.
3. Image Filter Pipeline.
4. Native UI And Async Log Architecture.
5. Packaging, Admin, And Runtime.
6. Migration And Compatibility.

The first implementation should start only after investigations 1 and 2 are resolved, because they define the core service boundaries and coordinate model.
