# Investigation 3: Image Filter Pipeline And Profiles

## Scope

This investigation defines how the native rewrite should preserve the full image filter workflow from the current web app.

The user uses this feature fully, so native MVP must keep:

- image filter controls
- filtered preview
- filter order
- bundled profile loading
- YAML profile import
- YAML profile export
- reset filters

## Executive Decision

Port the current JavaScript filter behavior to Python and keep the current YAML profile format.

Recommended modules:

```text
newsource/native/filter_service.py
newsource/native/image_profile_service.py
newsource/native/filter_panel.py
```

Recommended libraries:

- `Pillow` for image object handling and preview conversion.
- `OpenCV`/`numpy` for fast filter operations.
- `PyYAML` for profile import/export.
- `PySide6` for filter UI and file dialogs.

The native app should not reuse `web/image.js` directly, but the behavior should be ported carefully.

## Current Source Findings

### Current Filter State

Current filter globals in `web/index.js`:

```javascript
let isInvertColor = false,
    isDilate = false,
    isBinarize = false;
let binarizeThreshold = 50;
let blurImageRadius = 0;
```

Native equivalent:

```python
@dataclass
class FilterConfig:
    invertColor: bool = False
    dilate: bool = False
    blurImageRadius: int = 0
    binarizeThreshold: int | None = None
```

Important compatibility detail:

- In the current app, binarization is enabled only when `binarizeThreshold` exists in the profile.
- Missing `binarizeThreshold` means binarize off.
- Default UI threshold is 50 when binarize is off.

Native should preserve this behavior.

### Current Filter Order

Current `preprocessImage(canvas)` order:

```javascript
if (blurImageRadius > 0) {
    blurARGB(..., blurImageRadius / 100);
}
if (isDilate) {
    dilate(...);
}
if (isInvertColor) {
    invertColors(...);
}
if (isBinarize) {
    thresholdFilter(..., binarizeThreshold / 100);
}
```

Native filter order must remain:

```text
blur -> dilate -> invert -> threshold
```

Do not reorder these operations unless there is a measured reason. OCR output can change significantly if the order changes.

### Current UI Controls

Current web UI controls in `web/index.html`:

- profile dropdown
- profile import button
- selected-region preview image
- Binarize checkbox
- Binarize threshold slider, 0-100, disabled when binarize off
- Gaussian Blur slider, 0-100
- Dilate checkbox
- Invert Color checkbox
- Export button
- Reset button

Native UI should preserve the same control set.

Recommended native placement:

- A filter/profile panel or dialog opened from the compact control window/log toolbar.
- The preview should show the current selected/captured region after filters.

## Filter Behavior To Preserve

### Threshold / Binarize

Current JS:

```javascript
const thresh = Math.floor(level * 255);
gray = 0.2126 * r + 0.7152 * g + 0.0722 * b;
val = gray >= thresh ? 255 : 0;
```

Native behavior:

- Convert RGB to luminance using the same coefficients:
  - R: `0.2126`
  - G: `0.7152`
  - B: `0.0722`
- Threshold level is `binarizeThreshold / 100`.
- Pixel becomes black or white.

Python shape:

```python
def apply_threshold(rgb: np.ndarray, threshold: int) -> np.ndarray:
    thresh = int((threshold / 100) * 255)
    gray = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    bw = np.where(gray >= thresh, 255, 0).astype(np.uint8)
    return np.stack([bw, bw, bw], axis=-1)
```

### Invert Color

Current JS:

```javascript
pixels[i] = pixels[i] ^ 255;
```

Native behavior:

```python
rgb = 255 - rgb
```

### Blur

Current JS uses Processing/p5-style blur with:

```javascript
blurARGB(..., blurImageRadius / 100)
buildBlurKernel(radius)
radius = (r * 3.5) | 0
```

UI range is `0-100`, but the value is divided by 100 before blur. That means the effective kernel radius becomes small in the current app.

Native decision:

- Keep the slider range `0-100`.
- Preserve current practical behavior as closely as possible.
- Use OpenCV Gaussian blur or a direct port if visual matching is poor.

Recommended initial mapping:

```python
def blur_kernel_from_slider(value: int) -> int:
    if value <= 0:
        return 0
    # Approximate current web behavior.
    radius = max(1, min(248, int((value / 100) * 3.5)))
    kernel = radius * 2 + 1
    return kernel
```

Then:

```python
cv2.GaussianBlur(rgb, (kernel, kernel), 0)
```

Risk:

- The current JS blur is not exactly OpenCV Gaussian blur.

Mitigation:

- In the prototype, compare before/after preview output for known game screenshots and existing profiles.
- If matching is visibly different, port the JS kernel algorithm directly to Python/numpy.

### Dilate

Current JS dilate is luminance-based and checks a 4-neighbor cross:

- current
- left
- right
- up
- down

It chooses the neighbor with the highest luminance.

This is not exactly the same as a standard OpenCV morphological dilation on grayscale/binary images.

Native decision:

- Implement a compatible 4-neighbor luminance dilation first.
- Do not blindly replace it with `cv2.dilate()` unless OCR and preview output are acceptable.

Python shape:

```python
def apply_luminance_dilate(rgb: np.ndarray) -> np.ndarray:
    lum = 77 * rgb[..., 0] + 151 * rgb[..., 1] + 28 * rgb[..., 2]
    # Compare current, left, right, up, down and choose RGB from highest luminance.
    ...
```

Reason:

- Existing profiles were tuned against the JS behavior.
- Matching current behavior matters more than using a textbook morphology operator.

## Filter Service API

Recommended module:

```text
newsource/native/filter_service.py
```

Recommended API:

```python
@dataclass
class FilterConfig:
    invertColor: bool = False
    dilate: bool = False
    blurImageRadius: int = 0
    binarizeThreshold: int | None = None

    @property
    def is_binarize_enabled(self) -> bool:
        return self.binarizeThreshold is not None

def apply_filters(image: Image.Image, config: FilterConfig) -> Image.Image:
    ...
```

Implementation rules:

- Input should accept a `PIL.Image`.
- Convert to RGB before processing.
- Return a `PIL.Image` suitable for:
  - preview
  - OCR
  - optional debug save
- Do not mutate the input image in place.
- Keep filter order: `blur -> dilate -> invert -> threshold`.

## Profile Format

Current bundled profile files:

```yaml
blurImageRadius: 50
binarizeThreshold: 40
dilate: true
invertColor: true
```

```yaml
invertColor: true
dilate: true
blurImageRadius: 0
binarizeThreshold: 19
```

Current exported profile shape in `web/index.js`:

```javascript
const imageProfile = {
    invertColor: isInvertColor,
    dilate: isDilate,
    blurImageRadius: blurImageRadius,
};
if (isBinarize) {
    imageProfile["binarizeThreshold"] = binarizeThreshold;
}
```

Native export must preserve the same keys and omission behavior:

- Always export:
  - `invertColor`
  - `dilate`
  - `blurImageRadius`
- Export `binarizeThreshold` only when binarize is enabled.

Reason:

- Current app treats missing `binarizeThreshold` as binarize disabled.
- Existing profiles stay compatible.

## Image Profile Service API

Recommended module:

```text
newsource/native/image_profile_service.py
```

Recommended API:

```python
def load_profiles(profile_dir: Path) -> list[dict]:
    ...

def import_profile(path: Path) -> FilterConfig:
    ...

def export_profile(path: Path, config: FilterConfig) -> None:
    ...

def profile_to_config(profile: dict) -> FilterConfig:
    ...

def config_to_profile(config: FilterConfig) -> dict:
    ...
```

Compatibility rules:

- `load_profiles()` loads `*.yaml` from runtime `profiles/`.
- Loaded profile gets a display `name` from `Path(file).stem`, matching current behavior.
- Unknown YAML keys should be ignored, not fatal.
- Missing known keys should use defaults.
- Invalid YAML should not crash the app; show a clear error.
- Import dialog defaults to runtime `profiles/`.
- Export dialog defaults to runtime `profiles/`.

## Active Filter Config Persistence

Profiles are not enough. The current active filter settings should also survive app restart.

Recommended config section:

```ini
[FILTERCONFIG]
invertColor = false
dilate = false
blurImageRadius = 0
binarizeEnabled = false
binarizeThreshold = 50
activeProfile =
```

Important:

- `binarizeEnabled` is for runtime UI state.
- YAML profile compatibility still uses missing `binarizeThreshold` to mean disabled.

On apply profile:

- Update active `FilterConfig`.
- Update UI controls.
- Save current filter config to `config.ini`.
- Refresh preview.

On manual control change:

- Update active `FilterConfig`.
- Clear or mark `activeProfile` as custom.
- Save current filter config to `config.ini`.
- Refresh preview.

## Native UI Recommendation

Recommended module:

```text
newsource/native/filter_panel.py
```

Recommended layout:

```text
FilterPanel
  Profile row
    [Profile dropdown] [Import] [Export] [Reset]
  Preview image
  Binarize row
    [checkbox] [threshold slider 0-100]
  Blur row
    [slider 0-100]
  Dilate checkbox
  Invert Color checkbox
```

Behavior:

- Preview updates immediately when a control changes.
- Threshold slider is disabled when binarize is off.
- Reset returns to:
  - invert off
  - dilate off
  - blur 0
  - binarize off
  - threshold UI value 50
- Export writes current settings to YAML.
- Import applies selected YAML.
- Profile dropdown applies bundled/runtime profile.

Preview source:

- Prefer the current selected/captured region.
- If no current capture exists, show empty/placeholder state.
- When region selection changes, refresh preview using new region screenshot.

## Integration With Capture/OCR Pipeline

Native OCR flow should be:

```text
capture selected region
  -> apply_filters(image, active_filter_config)
  -> preview/debug state may use the same filtered image
  -> ocr_service.image_to_text(filtered_image)
```

Important:

- OCR must receive the filtered image, not the original screenshot.
- Preview should represent the same filtered image that OCR receives.
- If user changes filters, next hotkey capture uses the new filters.

Optional debug setting:

```ini
[FILTERCONFIG]
save_debug_filtered_image = false
```

This can help compare native output with the old web output, but is not required for MVP.

## Prototype Checklist

Before full implementation, verify:

- Native loads `profiles/light-background.yaml`.
- Native loads `profiles/wuwa.yaml`.
- Profile dropdown displays names from YAML filenames.
- Import YAML applies settings.
- Export YAML matches current key format.
- Reset matches current web behavior.
- Threshold disabled state matches binarize checkbox.
- Filter order is `blur -> dilate -> invert -> threshold`.
- OCR receives filtered image.
- Preview updates immediately after each control change.
- Existing game screenshot with old profile produces comparable OCR output.
- Exported profile can be imported by the old app if needed.
- Old profile can be imported by the native app.

## Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| OpenCV blur differs from JS blur | OCR output changes | Compare sample screenshots; port JS blur exactly if needed. |
| OpenCV dilation differs from JS dilate | Text thickness/noise changes | Implement compatible 4-neighbor luminance dilate. |
| YAML export changes key names | Old profiles break | Preserve exact keys and omission behavior. |
| Active filter state is not saved | User must reconfigure every launch | Add `[FILTERCONFIG]`. |
| Preview differs from OCR input | User tunes wrong image | Use the same `apply_filters()` output for both preview and OCR. |
| Profile files inside bundle only | Export/import changes do not persist | Use runtime `profiles/` beside exe. |

## Investigation 3 Result

The native app must preserve the full image filter and profile workflow.

Final decisions:

- Port filters to Python; do not reuse JS directly.
- Keep exact filter order: `blur -> dilate -> invert -> threshold`.
- Implement threshold and invert directly.
- Implement JS-compatible 4-neighbor luminance dilate.
- Start with OpenCV Gaussian blur approximation, but verify against screenshots.
- Keep YAML profile keys:
  - `invertColor`
  - `dilate`
  - `blurImageRadius`
  - `binarizeThreshold`
- Preserve current export behavior: omit `binarizeThreshold` when binarize is disabled.
- Add `[FILTERCONFIG]` for active filter persistence.
- Use runtime `profiles/` for bundled, imported, and exported profiles.

This keeps the current filter workflow intact while making it native and testable.
