# Native Game Screen Translator Spec

## Goal

Build a new Windows-native version of the current Game2Text workflow without the Eel/web streaming UI.

The new app focuses only on screen-region OCR, AI translation, filter preview/profile workflow, and a separate async log window. Existing web features such as Anki, Textractor, dictionaries, game script matching, audio, and browser streaming are out of scope.

## Core Workflow

1. User selects a region directly on top of the game screen.
2. App saves the selected region position and size.
3. User presses the global hotkey, default `Ctrl+Q`.
4. App captures a screenshot of the saved region.
5. App applies the configured image filters.
6. App runs OCR.
7. App immediately adds the OCR text to the log window.
8. App submits AI translation in the background.
9. Log window shows a loading state under the source text.
10. Each translation updates its matching log entry by `log_id` as soon as it finishes.

Each app launch starts a new session log file. Old logs do not need to be loaded automatically at startup.

## Window Model

The app has three main windows:

- Main window: buttons, controls, status, config/reload actions.
- Log window: source text, divider, translation/loading/error rows only.
- Preview/filter window: selected-region preview plus filter/profile controls.

The log window and preview/filter window must be resizable. Window open state, position, and size must be saved and restored.

## Required Features

- Windows-native UI.
- Three-window UI: main, log, preview/filter.
- Run with administrator privileges when needed for global hotkeys.
- Global hotkey trigger, default `Ctrl+Q`.
- Region selection hotkey, default `Ctrl+Shift+Q`.
- Direct screen-region selection overlay.
- Persist selected region in `config.ini`.
- Show or hide selected-region border from the main window.
- Red border around the active selected region when visible.
- Selected-region border is visible by default after startup when a region exists.
- Capture screenshot from the selected screen region without browser streaming.
- Preview selected/captured region.
- Full image filter workflow before OCR:
  - invert
  - binarize threshold
  - blur
  - dilate
  - reset filters
- Live preview of the filtered selected/captured region.
- Preview/filter window refreshes preview by capturing the current selected region again.
- Image filter profiles:
  - load bundled YAML profiles from `profiles/`
  - import profile from a YAML file
  - export current filter settings to YAML
  - preserve current profile keys:
    - `invertColor`
    - `dilate`
    - `blurImageRadius`
    - `binarizeThreshold`
- OCR using the existing Tesseract pipeline.
- AI translation using existing OpenAI config/key in `config.ini`.
- Separate log window similar to the current `logs.html`.
- Log rows show:
  - source OCR text
  - loading state while translation is pending
  - translated text when complete
  - red error text for queue-full/API/OCR errors
- Log rows do not need old icons/actions such as mic, audio, Anki, menu, or game script controls.
- If OCR detects no text, add a red log row saying no text was recognized.
- Async translation queue with bounded concurrency.
- Queue-full handling without sending extra API requests.
- Always auto-translate OCR text. No auto-translate toggle is needed for MVP.
- Save and restore window open state, position, and size.

## Config

Continue using `config.ini` for user-edited settings, including the OpenAI key.

Add a region section:

```ini
[REGIONCONFIG]
x = 100
y = 200
width = 900
height = 180
monitor = 1
show_region_border = true
border_color = red
```

Implementation should leave room for future multi-region support. Prefer internal region models with a region id even if MVP only exposes one region.

Add native app settings if needed:

```ini
[NATIVEAPP]
capture_hotkey = ctrl+q
select_region_hotkey = ctrl+shift+q
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

Add active filter settings:

```ini
[FILTERCONFIG]
invertColor = false
dilate = false
blurImageRadius = 0
binarizeEnabled = false
binarizeThreshold = 50
activeProfile =
```

## Suggested Stack

- `PySide6` for the native Windows UI.
- `mss` for fast screen capture.
- `keyboard` for global hotkeys.
- `OpenCV` and `Pillow` for image filtering/preview.
- Existing `ocr.py` logic for Tesseract OCR.
- Existing `translate.py` logic for OpenAI translation.
- `ThreadPoolExecutor` or Qt worker threads for async OCR/translation.

## Proposed File Layout

```text
newsource/
  PROJECT_SPEC.md
  native_app.py
  native/
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

## Out Of Scope

- Browser/Eel UI.
- Live browser screen streaming.
- Anki integration.
- Dictionary lookup.
- Textractor.
- Game script matching.
- Audio recording.
- Cloud OCR replacement.
- In-place game text replacement/inpainting.
- Transparent translated-text overlay mode.
- Multiple active OCR regions. The design should leave room for this, but MVP may implement one region first.

## Main Risks

- DPI scaling can make overlay coordinates differ from screenshot coordinates.
- Multi-monitor support needs careful coordinate handling.
- Exclusive fullscreen games may block overlays or screenshots. Borderless/windowed mode is expected to work better.
- Global hotkeys may require administrator privileges depending on the focused app/game.
- Too many translation requests can slow the app or hit API limits, so the queue must stay bounded.

## MVP Acceptance

- User can select a screen region.
- App remembers the region after restart.
- App shows the region border by default after restart when a region exists.
- `Ctrl+Q` captures that region and logs OCR text.
- `Ctrl+Shift+Q` starts region selection.
- Translation appears asynchronously under the correct log row.
- Multiple rapid hotkey presses do not corrupt log rows or duplicate DOM/log IDs.
- Queue limit prevents uncontrolled API spam.
- User can hide/show the red region border.
- Preview/filter window can be resized and updates filters in real time.
- Filter profiles can be imported and exported.
