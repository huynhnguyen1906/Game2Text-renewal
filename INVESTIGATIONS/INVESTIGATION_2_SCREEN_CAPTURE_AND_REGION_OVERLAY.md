# Investigation 2: Screen Capture And Region Overlay

## Scope

This investigation defines how the native app should let the user select a screen region directly over the game, save that region, capture it on hotkey, and optionally show a red border around the selected area.

This replaces the old web/canvas selection model. The old source selected a rectangle inside the browser video stream, while the native app must select and capture real screen coordinates.

## Executive Decision

Use a native overlay and a physical-screen coordinate model.

Recommended stack:

- `PySide6` for the region selection overlay and visible region border.
- `mss` for fast region screenshots.
- Existing `keyboard` package for global hotkey trigger.
- Existing `Pillow`/`OpenCV` stack for image handoff to filter/OCR services.

The selected region should be stored as physical screen pixels, not browser/canvas coordinates.

The app should support:

- one-shot region selection overlay
- persisted selected region
- optional always-on-top red border
- hidden border before capture to avoid polluting screenshots
- multi-monitor coordinates
- DPI conversion checks at 100%, 125%, and 150%

## Source Findings

### Current Web Selection

The old selection flow lives mainly in `web/index.js`.

Important behavior to preserve:

- User drags a rectangle.
- Negative width/height are normalized after mouse release.
- Selection triggers OCR from the selected region.
- Selection can be previewed.
- Filter preview is applied to the selected region.

Important behavior not reusable directly:

- Coordinates are canvas coordinates.
- Capture source is `videoElement`, not the desktop.
- `createCanvasWithSelection()` converts canvas coordinates to video coordinates using:

```javascript
aspectRatioY = videoElement.videoHeight / cv1.height;
aspectRatioX = videoElement.videoWidth / cv1.width;
```

Native app should not reuse this coordinate logic because there is no browser video stream.

### Current Config

Existing config has only selection appearance settings:

```ini
[APPEARANCE]
selection_color = hotpink
selection_line_width = 1
```

Native app needs a new region section because current config does not persist screen-region geometry.

## Proposed Coordinate Model

Store selected region in physical screen pixels:

```ini
[REGIONCONFIG]
x = 100
y = 200
width = 900
height = 180
monitor = 1
show_region_border = true
border_color = red
border_width = 2
```

Recommended internal data shape:

```python
@dataclass
class ScreenRegion:
    x: int
    y: int
    width: int
    height: int
    monitor: int
```

Rules:

- `x` and `y` are absolute virtual-desktop physical pixels.
- `width` and `height` are physical pixels.
- `monitor` is the selected monitor id, used for validation and user display.
- Negative drags are normalized before saving.
- Minimum region size should be enforced, for example 10x10 pixels.

Why physical pixels:

- `mss` captures by physical pixels.
- OCR needs exact captured pixels.
- Browser/canvas logical coordinate mapping is no longer relevant.

## DPI Strategy

DPI scaling is the main technical risk.

The native app should make the process DPI-aware before creating the Qt application. Recommended Windows behavior:

- Prefer Per-Monitor DPI Awareness V2.
- Do DPI setup at process start before `QApplication`.
- Treat `mss` coordinates as physical pixels.
- Convert Qt overlay geometry to capture geometry explicitly if Qt reports logical coordinates.

Implementation note:

```python
def enable_dpi_awareness():
    # Windows only. Call before QApplication is created.
    ...
```

Things to verify in prototype:

- At 100%, selected overlay rect equals captured image size.
- At 125%, selected overlay rect equals captured image size after conversion.
- At 150%, selected overlay rect equals captured image size after conversion.
- Region selected on a secondary monitor captures the expected pixels.

Decision:

- Store physical capture coordinates in config.
- If Qt gives logical coordinates under DPI scaling, convert at the overlay boundary and do not leak logical coordinates into backend services.

## Region Selection Overlay

Recommended module:

```text
newsource/native/region_overlay.py
```

Responsibilities:

- Show transparent full-screen overlay over the virtual desktop or over each monitor.
- Let the user drag a rectangle.
- Normalize drag direction.
- Return `ScreenRegion`.
- Cancel selection with `Esc`.
- Confirm selection on mouse release.

Recommended behavior:

- Overlay is frameless.
- Overlay is topmost while selecting.
- Cursor changes to crosshair.
- Background is lightly dimmed or fully transparent.
- Current drag rectangle is drawn in red.
- Existing selected region may be shown as a faint outline while selecting a new one.

Possible implementation approaches:

### Option A: One Overlay Covering Virtual Desktop

Use one frameless `QWidget` whose geometry covers the union of all screens.

Pros:

- Simple drag behavior across monitors.
- One widget handles all mouse events.

Cons:

- Coordinate conversion can be trickier if monitors have different DPI scales.

### Option B: One Overlay Per Monitor

Create one overlay widget per `QScreen`.

Pros:

- Easier per-monitor DPI handling.
- Easier to map monitor id.

Cons:

- Dragging across monitors is harder.
- More window management.

Decision:

- Start with Option B for reliability.
- Selection normally stays inside one game monitor.
- Cross-monitor drag is not required for MVP.

## Selected Region Border

Recommended module:

```text
newsource/native/region_border.py
```

Responsibilities:

- Show/hide the saved selected region.
- Draw a red border around the saved region.
- Stay above normal windows.
- Avoid intercepting mouse/keyboard input.
- Avoid appearing in OCR screenshots.

Recommended implementation:

- A transparent, frameless, always-on-top PySide window.
- Draw only the border in `paintEvent`.
- Set Qt transparent/input flags where available:
  - `Qt.WindowStaysOnTopHint`
  - `Qt.FramelessWindowHint`
  - `Qt.Tool`
  - `Qt.WindowTransparentForInput`
  - `WA_TransparentForMouseEvents`
  - `WA_TranslucentBackground`

Important capture rule:

- Hide the border before taking a screenshot.
- Wait briefly for the compositor to repaint if needed.
- Restore the border after capture if `show_region_border = true`.

Reason:

- Some screenshot APIs may capture topmost overlay windows.
- Hiding the border is the safest way to prevent the red outline from entering OCR input.

Alternative:

- Four thin border windows around the region instead of one transparent window.

Pros:

- Can be more reliable for click-through and capture avoidance.

Cons:

- More complicated positioning.

Decision:

- Start with one transparent border window.
- If screenshots include the border or input transparency is unreliable, switch to four thin border windows.

## Screen Capture

Recommended module:

```text
newsource/native/screen_capture.py
```

Use `mss`:

```python
def capture_region(region: ScreenRegion) -> Image.Image:
    with mss.mss() as sct:
        shot = sct.grab({
            "left": region.x,
            "top": region.y,
            "width": region.width,
            "height": region.height,
        })
        return Image.frombytes("RGB", shot.size, shot.rgb)
```

Pipeline:

1. Hotkey fires.
2. If border is visible, hide border.
3. Capture saved region with `mss`.
4. Restore border if enabled.
5. Send image to `filter_service.apply_filters()`.
6. Send processed image to `ocr_service.image_to_text()`.
7. Log OCR text immediately.
8. Queue translation.

Why `mss`:

- It captures screen regions directly.
- It is lightweight and fast.
- It avoids browser stream overhead.
- It can capture absolute monitor coordinates.

Dependency status:

- Current `requirements.txt` does not include `mss` or `PySide6`.
- Current repo already has `keyboard`, `Pillow`, `opencv-python`, and `pyinstaller`.

Native requirements should add:

```text
PySide6
mss
```

Exact versions can be decided during packaging investigation.

## Global Hotkey Interaction

The current app already uses `keyboard>=0.13.5`.

Native behavior:

- Global hotkey defaults to `ctrl+q`.
- Hotkey callback should not run OCR directly on the keyboard thread.
- Callback should emit a Qt signal or enqueue work into a worker.
- App may need administrator privileges when the focused game runs as admin.

Important rule:

- If the app is not elevated and the game is elevated, global hotkey behavior may fail. Packaging/runtime investigation should decide the admin relaunch strategy.

## Exclusive Fullscreen Behavior

Expected behavior:

- Borderless/windowed games should work best.
- Exclusive fullscreen may block overlay display or make screenshots unreliable.

Decision:

- MVP targets borderless/windowed fullscreen.
- Exclusive fullscreen support is best-effort, not guaranteed.
- The app should document or surface this limitation if the overlay/capture fails.

## Config Persistence

Add:

```ini
[REGIONCONFIG]
x = 100
y = 200
width = 900
height = 180
monitor = 1
show_region_border = true
border_color = red
border_width = 2
```

Optional native window settings:

```ini
[NATIVEAPP]
remember_last_region = true
select_region_hotkey = ctrl+shift+q
capture_hotkey = ctrl+q
```

Notes:

- User asked specifically to save selected region position.
- Region should be saved immediately after selection.
- If config has no valid region, app should prompt selection before allowing hotkey capture.

## Proposed User Flow

### First Run

1. App starts.
2. No saved region exists.
3. User clicks Select Region or presses a select-region hotkey.
4. Fullscreen overlay appears on the chosen monitor.
5. User drags region over game text.
6. Region is saved to `config.ini`.
7. Red border appears if enabled.
8. Log window remains available.

### Normal Use

1. User plays game.
2. Red border may be visible or hidden depending on config.
3. User presses `Ctrl+Q`.
4. App captures saved region.
5. OCR text is logged immediately.
6. Translation appears asynchronously.

### Hide/Show Region Border

1. User toggles border visibility.
2. `show_region_border` is updated in config.
3. Border window is shown/hidden immediately.

## Files To Add Later

Recommended native modules:

```text
newsource/native/region_overlay.py
newsource/native/region_border.py
newsource/native/screen_capture.py
newsource/native/dpi.py
```

Expected responsibilities:

- `region_overlay.py`: interactive region selection.
- `region_border.py`: optional red outline.
- `screen_capture.py`: `mss` capture from saved physical region.
- `dpi.py`: Windows DPI-awareness and coordinate conversion helpers.

## Prototype Checklist

Before implementing full UI, create a small prototype that proves:

- Overlay can be shown over a game/window.
- Region drag returns a normalized rectangle.
- Config saves and restores the same rectangle.
- `mss` screenshot size equals saved region width/height.
- Border can be shown and hidden.
- Capture while border is visible does not include the border because capture hides it first.
- Hotkey can trigger capture while the game is focused.
- DPI behavior is correct at 100%, 125%, and 150%.
- Secondary monitor capture works.

## Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Qt logical coordinates differ from `mss` physical pixels | Captured region is offset or wrong size | Make app DPI-aware and explicitly convert coordinates. |
| Multi-monitor geometry differs between Qt and `mss` | Wrong monitor capture | Validate monitor geometry from both APIs during prototype. |
| Border appears in screenshot | OCR gets red pixels/noise | Hide border before capture, restore after capture. |
| Border steals focus/input | Game controls break | Use transparent input flags; fallback to four thin windows or hide border while playing. |
| Exclusive fullscreen blocks overlay | User cannot select region over game | Target borderless/windowed mode for MVP. |
| App lacks admin rights | Hotkey may not work over elevated game | Runtime investigation should add admin launch/relaunch strategy. |

## Investigation 2 Result

The native app should replace browser canvas selection with a PySide screen overlay and `mss` region capture.

Final decisions:

- Store selected region as physical virtual-desktop pixels.
- Use `mss` for screenshot capture.
- Use PySide overlay for region selection.
- Use PySide transparent topmost border for visible selected region.
- Hide the border before capture.
- Add `[REGIONCONFIG]` to `config.ini`.
- Treat DPI and multi-monitor correctness as prototype gates before full implementation.

This gives the native rewrite a clean capture model that does not depend on the old web streaming architecture.
