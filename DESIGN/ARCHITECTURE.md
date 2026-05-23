# Architecture

## Purpose

This document is the implementation architecture for the native rewrite.

It is intentionally self-contained so later implementation steps can use this file without needing to reread all investigations.

## Product Contract

The app is a Windows-native screen translator for games.

MVP behavior:

- Three windows:
  - main window
  - log window
  - preview/filter window
- One active OCR region in MVP.
- Internal models must be multi-region-ready.
- Region border visible by default when a region exists.
- `Ctrl+Q` captures/translates region 1.
- `Ctrl+Shift+Q` selects/crops region 1.
- Each app launch starts a new log session file.
- Old logs do not need to load automatically on startup.
- Source text appears in the log immediately after OCR.
- Translation appears asynchronously under the matching source row.
- Translation queue limit is 5.
- Queue full shows a red row-level message and sends no API request.
- Preview/filter window owns filter controls and real-time preview.
- OpenAI key remains manually edited in `config.ini`.
- New source must be independent under `newsource/`.

Out of scope for MVP:

- Eel/web UI.
- Browser streaming.
- Anki.
- Textractor.
- dictionary lookup.
- game script matching.
- audio/media logging.
- transparent translated-text overlay mode.
- multiple active OCR regions. The design must leave room for this later.

## Runtime Stack

Use:

- `PySide6` for UI.
- `mss` for screen capture.
- `keyboard` for global hotkeys.
- `Pillow`, `OpenCV`, `numpy` for image handling/filtering.
- `pytesseract` for OCR.
- `openai` for translation.
- `PyYAML` for filter profiles.
- `PyInstaller` for packaging.

Do not import the old root modules directly at runtime. Copy/refactor logic from them into native modules.

## File Layout

Target layout:

```text
newsource/
  native_app.py
  requirements-native.txt
  build_native.bat
  run_native_admin.bat
  native-game2text.spec
  DESIGN/
    APP_UX_DECISIONS.md
    ARCHITECTURE.md
    IMPLEMENTATION_PLAN.md
  INVESTIGATIONS/
    ...
  native/
    __init__.py
    core/
      models.py
      paths.py
      startup.py
      dpi.py
    app/
      app_controller.py
      event_bus.py
      workers.py
    config/
      service.py
    logs/
      service.py
    filters/
      service.py
      profiles.py
    capture/
      screen_capture.py
    ocr/
      service.py
    translation/
      service.py
    hotkeys/
      service.py
    regions/
      overlay.py
      border.py
    ui/
      main_window.py
      log_window.py
      log_row_widget.py
      preview_window.py
      filter_panel.py
```

## Ownership Boundaries

### UI Layer

Files:

- `ui/main_window.py`
- `ui/log_window.py`
- `ui/log_row_widget.py`
- `ui/preview_window.py`
- `ui/filter_panel.py`
- `regions/overlay.py`
- `regions/border.py`

Rules:

- UI widgets do not perform OpenAI calls.
- UI widgets do not parse or write log files directly.
- UI widgets do not call Tesseract directly.
- UI widgets talk to `AppController` or emit UI signals.
- Worker threads never mutate widgets directly.

### Application Orchestration

Files:

- `app/app_controller.py`
- `app/event_bus.py`
- `app/workers.py`

Responsibilities:

- Connect windows, services, workers, and hotkeys.
- Own startup/shutdown flow.
- Own capture/OCR/translation workflow.
- Own window state persistence calls.
- Emit row updates through the event bus.

### Service Layer

Files:

- `config/service.py`
- `logs/service.py`
- `filters/profiles.py`
- `filters/service.py`
- `capture/screen_capture.py`
- `ocr/service.py`
- `translation/service.py`
- `hotkeys/service.py`
- `core/paths.py`
- `core/dpi.py`

Rules:

- Services are plain Python where possible.
- Services should be testable without launching PySide windows.
- Services should not import UI widgets.

## Core Data Models

Define these in `native/core/models.py`.

### ScreenRegion

Use region id from day one, even if MVP only exposes region `1`.

```python
@dataclass
class ScreenRegion:
    id: str
    label: str
    x: int
    y: int
    width: int
    height: int
    monitor: int
    border_color: str = "red"
    capture_hotkey: str = "ctrl+q"
    select_hotkey: str = "ctrl+shift+q"
    enabled: bool = True
```

Rules:

- Coordinates are physical virtual-desktop pixels.
- `width` and `height` must be positive.
- Drag direction is normalized before save.
- Minimum valid size should be enforced, for example 10x10 pixels.

### FilterConfig

```python
@dataclass
class FilterConfig:
    invertColor: bool = False
    dilate: bool = False
    blurImageRadius: int = 0
    binarizeThreshold: int | None = None
    activeProfile: str = ""

    @property
    def is_binarize_enabled(self) -> bool:
        return self.binarizeThreshold is not None
```

Compatibility rules:

- YAML profile missing `binarizeThreshold` means binarize disabled.
- UI config may store `binarizeEnabled` separately to keep slider value 50 while disabled.
- Export YAML omits `binarizeThreshold` when binarize is disabled.

### LogEntry

```python
@dataclass
class LogEntry:
    id: str
    row_key: str
    folder: str
    source_text: str
    translated_text: str | None = None
    translation_pending: bool = False
    translation_status: str = "idle"
    translation_error: str | None = None
    created_at: datetime | None = None
    region_id: str = "1"
```

Status values:

```text
idle
pending
done
error
queue_full
ocr_error
```

Rules:

- New current-session rows use `row_key = id`.
- Loaded historical duplicate-ID rows, if loaded later, should use `folder:line_number:id`.
- UI uses `row_key`.
- Translation update uses `id` for current-session native rows.

### WindowState

```python
@dataclass
class WindowState:
    open: bool
    x: int
    y: int
    width: int
    height: int
    always_on_top: bool = False
```

Use for main, log, and preview/filter windows.

## Config Schema

Use `config.ini` beside the executable or repo root in dev.

### REGION_1

Prefer `[REGION_1]` for multi-region readiness.

```ini
[REGION_1]
label = Region 1
x = 100
y = 200
width = 900
height = 180
monitor = 1
border_color = red
capture_hotkey = ctrl+q
select_hotkey = ctrl+shift+q
enabled = true
show_region_border = true
```

Compatibility:

- If old `[REGIONCONFIG]` exists, map it to `REGION_1`.
- New writes should prefer `[REGION_1]`.

### NATIVEAPP

```ini
[NATIVEAPP]
translation_queue_limit = 5
main_window_open = true
main_window_x = 100
main_window_y = 100
main_window_width = 420
main_window_height = 360
log_window_open = true
log_window_x = 1200
log_window_y = 120
log_window_width = 700
log_window_height = 900
log_always_on_top = true
preview_window_open = false
preview_window_x = 900
preview_window_y = 120
preview_window_width = 900
preview_window_height = 700
```

### FILTERCONFIG

```ini
[FILTERCONFIG]
invertColor = false
dilate = false
blurImageRadius = 0
binarizeEnabled = false
binarizeThreshold = 50
activeProfile =
```

### Existing Sections To Reuse

Read:

- `[OCRCONFIG]`
- `[TRANSLATIONCONFIG]`
- `[LOGCONFIG]`
- `[APPEARANCE]`

Preserve old sections. Do not delete or rewrite unrelated sections.

## Path Strategy

Use `native/core/paths.py`.

Definitions:

```python
def app_root() -> Path:
    """Editable runtime files: config.ini, logs, profiles."""

def bundle_root() -> Path:
    """Read-only bundled resources under PyInstaller _MEIPASS or repo root."""
```

Rules:

- `config.ini`, `logs/`, and `profiles/` use `app_root()`.
- bundled default resources use `bundle_root()`.
- Do not write into `_MEIPASS`.

## Startup Flow

Entry point: `newsource/native_app.py`.

Flow:

1. Enable DPI awareness before `QApplication`.
2. Create `QApplication`.
3. Resolve paths.
4. Ensure `config.ini` exists.
5. Backup config once before adding native sections, if practical.
6. Ensure native config sections/keys exist.
7. Ensure `logs/text/` exists.
8. Ensure `profiles/` exists.
9. Create a new session log id and log file path.
10. Set Tesseract executable path.
11. Create event bus.
12. Create services.
13. Create app controller.
14. Create windows.
15. Restore windows that were open last session.
16. Restore region 1 if configured.
17. Show region border if region exists and border is enabled.
18. Register hotkeys.
19. Start Qt event loop.

On shutdown:

1. Save window open states.
2. Save window geometries.
3. Unregister hotkeys.
4. Shut down executors.

## Window Architecture

### MainWindow

Purpose:

- Control surface.

Controls:

- Capture/translate now.
- Select region.
- Show/hide region border.
- Open/close log window.
- Open/close preview/filter window.
- Open config.
- Reload config.
- Status label for hotkey/admin/API/config issues.

Main window does not display logs.

### LogWindow

Purpose:

- Read translation logs.

Behavior:

- Always-on-top by default.
- Resizable.
- Auto-scroll to bottom on new row if already near bottom.
- No toolbar.
- No icons.
- Row format:

```text
source text
divider
translated/loading/error text
```

### PreviewWindow

Purpose:

- Show selected-region preview.
- Host filter/profile controls.

Behavior:

- Resizable.
- Captures selected region when opened.
- Has refresh preview button.
- Filter parameter controls stay stable while preview area grows.
- Filter changes apply in real time.
- Displays active profile name.

### RegionOverlay

Purpose:

- Select/crop a region.

Behavior:

- Triggered by main window button or select hotkey.
- Drag rectangle over screen.
- Mouse release saves immediately.
- No confirm button.
- Escape cancels selection.

### RegionBorder

Purpose:

- Show active region outline.

Behavior:

- Visible by default when region exists.
- Red for region 1.
- Hidden before capture and restored after capture.
- Should not capture mouse input.

## Event Bus

Use `PySide6.QtCore.Signal`.

Recommended signal owner in `native/app/event_bus.py`:

```python
class AppEventBus(QObject):
    log_entry_created = Signal(object)
    log_entry_updated = Signal(str, dict)
    status_changed = Signal(str)
    capture_failed = Signal(str)
    preview_image_updated = Signal(object)
    region_updated = Signal(object)
```

Rules:

- Workers emit events.
- UI consumes events.
- Backend services do not import widgets.
- Never mutate widgets from worker threads.

## Capture/OCR/Translation Flow

### Capture Hotkey Flow

```text
Ctrl+Q
  -> HotkeyService callback for region 1
  -> AppController.request_capture(region_id="1")
  -> Workers.submit_capture_ocr(region)
  -> RegionBorder.hide_temporarily()
  -> ScreenCapture.capture_region(region)
  -> RegionBorder.restore_if_enabled()
  -> FilterService.apply_filters(image, active_filter_config)
  -> OCRService.image_to_text(filtered_image)
  -> if no text:
       LogService.append_source_text("Không nhận diện được text.", status=ocr_error)
       EventBus.log_entry_created(error entry)
       stop
  -> LogService.append_source_text(text)
  -> EventBus.log_entry_created(entry)
  -> Workers.queue_translation(log_id, text)
```

### Translation Flow

```text
queue_translation(log_id, text)
  -> try acquire BoundedSemaphore(5)
  -> if unavailable:
       EventBus.log_entry_updated(log_id, queue_full patch)
       stop, no API request
  -> EventBus.log_entry_updated(log_id, pending patch)
  -> TranslationService.translate_text(text)
  -> LogService.update_translation(log_id, translated_text)
  -> EventBus.log_entry_updated(log_id, done patch)
  -> release semaphore
```

Queue-full message:

```text
Bạn đã chạm giới hạn queue dịch. Hãy đợi các câu trước dịch xong rồi dịch tiếp.
```

## Worker Strategy

Use `ThreadPoolExecutor`.

Recommended executors:

```python
capture_executor = ThreadPoolExecutor(max_workers=1)
translation_executor = ThreadPoolExecutor(max_workers=5)
translation_slots = threading.BoundedSemaphore(5)
```

Rationale:

- OCR/capture should not pile up aggressively when hotkey is spammed.
- Translation can complete out of order.
- Queue-full behavior prevents unbounded API backlog.

## Log Service

Write format:

```text
<log_id>, <source_text>
<log_id>, <source_text>|||TRANSLATION|||<translated_text>
```

Rules:

- New session file at every app launch.
- New IDs use `%Y%m%d-%H%M%S-%f`.
- File writes use a lock.
- Source text is appended immediately.
- Translation update rewrites matching current-session row.
- Do not persist queue/API errors as translations.
- Old logs do not need startup load in MVP.

Parser should still support old IDs for future manual log viewing/import.

## Filter Pipeline

Order:

```text
blur -> dilate -> invert -> threshold
```

Rules:

- OCR receives the filtered image.
- Preview displays the same filtered image.
- Changes update preview in real time.
- YAML profile import/export preserves existing keys:
  - `invertColor`
  - `dilate`
  - `blurImageRadius`
  - `binarizeThreshold`
- Export omits `binarizeThreshold` when binarize is disabled.

## Hotkeys

MVP:

```text
ctrl+q        capture region 1
ctrl+shift+q  select region 1
```

Future:

```text
ctrl+w        capture region 2
ctrl+shift+w  select region 2
```

Hotkey failures should not crash the app.

If hotkey registration fails, status should say:

```text
Không đăng ký được hotkey. Nếu game chạy admin, hãy chạy app bằng quyền admin.
```

## Packaging Architecture

Use one-folder PyInstaller initially.

Runtime folder:

```text
dist/native-game2text/
  native-game2text.exe
  config.ini
  profiles/
  logs/
  resources/bin/win/tesseract/
```

Do not package old logs.

Do not bundle old Eel/Anki/Textractor/dictionary/Sudachi features.

Admin:

- Do not force admin in manifest for MVP.
- Provide `run_native_admin.bat`.

## Native Requirements

Create `newsource/requirements-native.txt`.

Initial dependency set:

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

## Future-Proofing Rules

### Multi-Region

Do:

- Use `region_id` in models and events.
- Store region data per id.
- Route hotkeys through region id.

Do not:

- Hard-code global `current_region` deep inside services.
- Hard-code red border beyond region 1 defaults.

### Transparent Translation Overlay

Keep translated text events separate from log window rendering so a future overlay presenter can consume the same events.

MVP does not implement overlay text mode.

## Quality Gates

Before considering MVP done:

- Source runs without importing Eel.
- Main/log/preview windows open.
- Window positions/sizes persist.
- New app launch creates a new session log file.
- Region selection saves a physical-pixel region.
- Border shows by default after region selection and app restart.
- Capture hides border before screenshot.
- Filter preview updates in real time.
- Existing profiles load and export.
- OCR receives filtered image.
- OCR no-text creates red error row.
- Translation pending/done/error updates correct row.
- Queue 6th request shows red queue-full row and sends no API request.
- Packaged build finds config/profiles/Tesseract.
