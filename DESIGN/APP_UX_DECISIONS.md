# App UX Decisions

## Purpose

This document records the product and UX decisions after the six investigations.

It is the bridge from investigation to implementation design. The new source should use this as the current behavioral contract.

## Window Model

The native app has three main windows:

1. Main window
2. Log window
3. Preview/filter window

All three windows should have their open/closed state persisted.

The log window and preview/filter window must be resizable by dragging the window edges. Their size and position must be saved and restored.

## Main Window

The main window is the control surface.

It owns buttons and controls such as:

- translate selected region now
- select/crop region
- show/hide selected-region border
- open/close log window
- open/close preview/filter window
- open `config.ini`
- reload config
- show status for hotkey/admin/API/config problems

The log toolbar should not be placed in the log window. Log window stays focused on reading logs.

## Log Window

The log window should be visually close to the current `logs.html`, but simpler.

Each row contains only:

```text
source OCR text
----------------
translated text / loading / error
```

No mic icon, audio icon, Anki button, menu icon, or game script controls are needed.

Behavior:

- Log window is always-on-top by default.
- Log window should stay scrolled to the bottom as new rows arrive, matching the current web log behavior.
- Each app launch starts a new session log file.
- Old logs do not need to be loaded automatically at startup.
- Log rows update asynchronously by `log_id`.
- If OCR returns no text, add a red row message:

```text
Không nhận diện được text.
```

Queue full behavior:

- Keep the source OCR text row.
- Show the queue-full warning as red text under the divider.
- Do not add a separate queue widget or modal.

Translation behavior:

- Always auto-translate OCR text.
- No `Auto translate` toggle is needed for MVP.

## Preview And Filter Window

The preview/filter window contains both:

- captured region preview
- filter/profile controls

It is opened from the main window.

When the preview/filter window opens:

- capture the currently selected region immediately
- show the captured image
- apply current filters in real time

The window must include a refresh/reset-preview button so the user can capture the selected region again when the game screen changes.

The preview image should resize with the window. Filter parameter controls should not stretch awkwardly as the window grows. The recommended layout is:

```text
left/top: preview image, resizable
right/bottom: fixed-width filter controls
```

Exact orientation can be decided in implementation based on ergonomics, but the controls must remain stable and readable.

Filter UI must show which profile is currently active.

Required controls:

- profile dropdown
- import YAML profile
- export current filter settings
- reset filters
- binarize checkbox
- binarize threshold slider
- blur slider
- dilate checkbox
- invert checkbox
- refresh preview

Filter changes must update the preview in real time.

## Region Selection

Region selection flow:

1. User presses the select-region button or select-region hotkey.
2. Transparent overlay appears over the target screen.
3. User drags a rectangle over game text.
4. Releasing the mouse saves the region immediately.
5. No confirm/cancel step is required.

If the user wants to adjust the region, they simply select/crop again.

Region selection needs a hotkey.

Recommended initial hotkeys:

```ini
[NATIVEAPP]
capture_hotkey = ctrl+q
select_region_hotkey = ctrl+shift+q
```

## Selected Region Border

The selected-region border is visible by default.

Behavior:

- Red border around the selected region.
- Main window has a button to hide/show it.
- On app startup, if a region exists, show the border by default.
- If no region exists, no border appears. This tells the user there is no active selected region.
- Border is hidden temporarily before screenshot capture and restored afterward.

Default:

```ini
[REGIONCONFIG]
show_region_border = true
border_color = red
```

## No Region Selected

If capture is triggered without a selected region, use whichever implementation is simpler:

- open region selection automatically, or
- show a clear status/error message

Preferred behavior:

- automatically open region selection if possible

But this is not a hard blocker for MVP.

## Startup Behavior

On app launch:

1. Start a new session log file.
2. Restore windows that were open during the previous app session.
3. Restore window positions and sizes.
4. Register hotkeys.
5. Restore selected region from config if present.
6. Show selected-region border by default if region exists.
7. Do not force user to select a region on startup.
8. If no region exists, no border is shown.

The user will select a region when they want to start translating.

## Config And Settings

MVP does not need a large settings UI.

Required:

- Open `config.ini`
- Reload config

OpenAI key remains manually edited in `config.ini`.

The app should continue running if OpenAI key is missing, but translation rows should show an error when translation is attempted.

## Window Persistence

Persist:

- main window open state
- main window position and size
- log window open state
- log window position and size
- preview/filter window open state
- preview/filter window position and size
- log always-on-top state
- selected region
- selected-region border visibility
- active filter config
- active filter profile name

Recommended config keys:

```ini
[NATIVEAPP]
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

## Backend Reuse Strategy

The new source should be independent inside `newsource/`.

Do not import old modules directly at runtime because many of them pull in Eel or old features.

Use old source as reference and copy/refactor/customize into native services:

- `ocr.py` -> `native/ocr/service.py`
- `translate.py` -> `native/translation/service.py`
- `logger.py` -> `native/logs/service.py`
- `config.py` -> `native/config/service.py`
- `web/image.js` -> `native/filters/service.py`
- `imageprofile.py` -> `native/filters/profiles.py`
- `hotkeys.py` -> `native/hotkeys/service.py`

Create a separate native requirements file:

```text
newsource/requirements-native.txt
```

The goal is that the new source can later run in its own environment without the old Eel app dependencies.

## Future Multi-Region Scale-Up

MVP can start with one selected region, but the architecture must leave room for two or three regions.

Reason:

- Game text is not always located in one fixed area.

Future behavior idea:

- Region 1:
  - border color red
  - capture hotkey `ctrl+q`
  - select hotkey `ctrl+shift+q`
- Region 2:
  - border color blue
  - capture hotkey `ctrl+w`
  - select hotkey `ctrl+shift+w`
- Region 3:
  - optional later

Design implication:

- Do not hard-code a single global region everywhere.
- Use a region id in data structures even if MVP only creates region `1`.

Recommended model:

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
    border_color: str
    capture_hotkey: str
    select_hotkey: str
    enabled: bool = True
```

Recommended MVP config can still expose only region 1:

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
```

Compatibility note:

- Existing investigations used `[REGIONCONFIG]`.
- During implementation, prefer `[REGION_1]` if multi-region readiness is adopted from the start.
- A compatibility layer can map `[REGIONCONFIG]` to `[REGION_1]` if needed.

## Future Overlay Text Mode

Future scale-up may support a one-monitor user workflow:

- transparent overlay with only translated text
- no background
- user can select overlay text position
- once selected, disable selection and keep the overlay fixed

This is not MVP.

Design implication:

- Do not make the log rendering model depend entirely on a normal window background.
- Keep log row/text rendering logic separate enough that later an overlay text presenter can reuse translated text events.

## Current MVP Shape

MVP should implement:

- three windows
- one region
- selected-region border visible by default
- crop/select hotkey
- capture hotkey
- async log
- preview/filter window
- profile import/export
- config/log/profile runtime persistence
- independent native source and native requirements

MVP should leave hooks for:

- multiple regions
- overlay translated text mode
