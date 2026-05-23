# Native Rewrite Handoff Context

This file is the practical handoff for continuing work on `newsource/` in a new chat.

It complements:

- `PROJECT_SPEC.md`
- `DESIGN/ARCHITECTURE.md`
- `DESIGN/APP_UX_DECISIONS.md`
- `DESIGN/IMPLEMENTATION_PLAN.md`

Those files describe the intended architecture. This file describes the **actual current state**, recent changes, known tradeoffs, and what to preserve.

## Project Status

`newsource/` is now a mostly standalone Windows-native rewrite of the old web/Eel workflow.

Implemented and usable:

- native main window
- native log window
- native preview/filter window
- region selection overlay
- visible/hideable region border
- OCR capture by hotkey
- async translation queue
- log rows with source text + translated text/loading/error
- filter preview and YAML profiles
- build packaging to `newsource/dist/native-game2text`
- optional game translation overlay window

The old web/Eel app still exists in repo root, but native runtime under `newsource/` is independent.

## Current Native Entry Points

- App entry: `newsource/native_app.py`
- Build script: `newsource/build_native.bat`
- Admin launcher for packaged app: `newsource/run_native_admin.bat`
- PyInstaller spec: `newsource/native-game2text.spec`

## Current Directory Shape

Important folders/files:

- `newsource/native/`
- `newsource/native_app.py`
- `newsource/config.ini`
- `newsource/config.template.ini`
- `newsource/profiles/`
- `newsource/resources/bin/win/tesseract/`
- `newsource/venv/`
- `newsource/dist/`

`newsource` is close to being movable as a standalone project. If moving it to a different path, recreating `venv` is safer than trusting the copied virtual environment.

## Run / Build Commands

### Dev Run

From repo root:

```powershell
cd .\newsource
.\venv\Scripts\Activate.ps1
python .\native_app.py
```

### Dev Run As Admin

From repo root:

```powershell
Start-Process powershell -Verb RunAs -ArgumentList '-NoExit','-Command','Set-Location "E:\GITHUB_SPACE\Game2Text\newsource"; .\venv\Scripts\Activate.ps1; python .\native_app.py'
```

### Build

From `newsource/`:

```powershell
.\build_native.bat
```

Build output:

```text
newsource/dist/native-game2text/
```

## Window Model

The app currently has these windows:

1. `MainWindow`
2. `LogWindow`
3. `PreviewWindow`
4. `GameOverlayWindow`
5. `GameOverlayEditorWindow`

The original MVP spec was 3 windows; overlay/editor were added later as the next feature layer.

## Current Working Features

### Main Window

Current blocks:

1. Capture / border block
2. Region select block
3. Log + preview toggle block
4. Game overlay block
5. Config block

Button hotkey labels are populated dynamically from config where applicable.

### Log Window

Current behavior:

- source text on top
- divider
- translated/loading/error text below
- font size controls (`+` / `-`)
- auto-scroll to bottom on:
  - row creation
  - row update
  - font size change

Important recent fix:

- scrolling now runs in two passes because translation update can change row height after layout commit

File:

- `native/ui/log_window.py`

### Preview / Filter

Current behavior:

- capture current OCR region for preview
- apply filters in real time
- refresh preview button works
- import/export YAML profiles works
- profile dropdown updates after export to internal profiles directory

Files:

- `native/ui/preview_window.py`
- `native/ui/filter_panel.py`
- `native/filters/service.py`
- `native/filters/profiles.py`

### Region Selection

Current behavior:

- region selection by button or hotkey
- drag-and-release saves region immediately
- red border can be shown/hidden
- border geometry updates even if border is hidden when region changes

Files:

- `native/regions/overlay.py`
- `native/regions/border.py`

### Async Translation

Current behavior:

- OCR text logs immediately
- translation is queued async
- queue limit is 5
- queue-full rows show red warning and do not send extra API requests
- translations update matching rows by `log_id`

Files:

- `native/app/app_controller.py`
- `native/app/workers.py`
- `native/logs/service.py`
- `native/translation/service.py`

### Game Overlay

Current behavior:

- top-level transparent overlay window
- shows latest translated text only
- no source text
- always-on-top
- edit mode allows drag/resize
- non-edit mode is click-through
- Windows shadow/border suppression was added at Qt + DWM level
- overlay style settings:
  - font size
  - overlay opacity
  - text opacity
  - outline opacity
  - background opacity
  - use text background
- overlay auto-hide after inactivity
- fade-out before hide is implemented
- overlay can be manually toggled independently from auto-hide state

Files:

- `native/ui/game_overlay_window.py`
- `native/ui/game_overlay_editor_window.py`
- `native/core/dpi.py`

## Overlay Auto-Hide Logic

Current design:

- config key: `GAMEOVERLAY.auto_hide_seconds`
- overlay keeps separate state for:
  - manual visible state
  - auto-hidden state
- when no new translated text arrives within configured seconds:
  - overlay fades out during the last `0.75s`
  - then hides
- on next translated text:
  - overlay shows immediately
  - opacity is restored to base value
  - no fade-in

This was chosen to avoid a confusing state where overlay remains technically visible but fully transparent.

## Current OCR State

### Current OCR Settings In Code

File:

- `native/ocr/service.py`

Important current state:

- `psm = 6`
- OCR image is upscaled before Tesseract
- current upscale factor is:

```python
OCR_UPSCALE_FACTOR = 2
```

At one point it was tested at `x3`, but the current code was returned to `x2`.

### Current OCR Findings

Important lesson from recent debugging:

- `clean_ocr_text()` is **not** the main source of major text loss
- the main instability was often from Tesseract not reading some glyphs correctly in the first place

Observed tradeoff:

- **white text on black background**
  - better punctuation in some cases
  - but can lose short final lines / short trailing text

- **black text on white background**
  - better at preserving short final lines / tiny line fragments
  - but punctuation and contractions can degrade
  - examples:
    - `This'U do.`
    - `I'l`

Another important finding:

- preview image looking clean does **not** mean OCR will be stable
- small pixel-level differences, anti-aliasing, and segmentation can still produce unstable OCR outputs

### Current OCR Config Recommendation

Current `config.ini` is intentionally less aggressive than before.

Previously removed options:

- `-c enable_new_segsearch=0`
- `-c language_model_ngram_on=0`

Reason:

- these were suspected to make OCR too rigid
- removing them gave Tesseract more default segmentation and language-model behavior

Current `extra_options` in config:

```ini
extra_options = "-c chop_enable=T -c use_new_state_cost=F -c segment_segcost_rating=F -c textord_force_make_prop_words=F -c edges_max_children_per_outline=40"
```

Current judgment:

- this is a reasonable intermediate configuration
- do not aggressively change it again unless more evidence appears

### OCR Debugging History

Debug code was added temporarily multiple times:

- raw OCR output
- cleaned OCR output
- multi-`psm` comparisons
- `image_to_data` vs `image_to_string`

Those debug paths were removed after testing and the code was returned to a simpler state.

If future OCR debugging is needed again, the correct place to instrument is:

- `native/ocr/service.py`

### OCR Next-Step Recommendation

If OCR issues return, do **not** immediately blame `clean_ocr_text()`.

Recommended order:

1. compare filtered preview polarity
2. compare raw OCR before clean
3. test whether issue is specific to:
   - white-on-black
   - black-on-white
   - short one-line subtitles
   - final short line
4. only then consider:
   - retry logic
   - `psm 7` fallback for suspicious single-line OCR
   - dual-pass OCR with both polarities

At the moment, none of those fallback mechanisms are implemented in runtime.

## Translation Service

File:

- `native/translation/service.py`

Current behavior:

- reads OpenAI API key from `config.ini`
- reads model from config:
  - `TRANSLATIONCONFIG.openai_model`
- currently uses OpenAI chat completions
- the config still says `translation_service = Google Translate`, but this is intentionally mapped to the OpenAI path for compatibility with the old modified source behavior

## Current Config Notes

Main config file:

- `newsource/config.ini`

Template used during build:

- `newsource/config.template.ini`

Important behavior:

- build uses `config.template.ini`
- build does **not** package the live API key from your runtime `config.ini`

That means:

- packaged builds are clean
- runtime API key stays local

## Current Hotkeys

Current main hotkeys:

- `Ctrl+Q` = capture OCR region
- `Ctrl+Shift+Q` = select OCR region
- `Ctrl+Shift+1` = toggle all visible region borders
- `Ctrl+Shift+2` = toggle game overlay

These labels are reflected dynamically in the main window UI.

## Current Build / Packaging State

Working:

- PyInstaller build script
- packaged app launch
- icon embedded in exe
- runtime window icon handling
- bundled Tesseract
- bundled profiles
- clean config template in packaged output

Build output target:

- `newsource/dist/native-game2text/`

## Known Tradeoffs / Cautions

### OCR Stability

The major remaining weak point is OCR stability across:

- subtitle polarity
- punctuation
- short one-line text
- short trailing lines

Current state is usable, but not fully solved.

### Preview vs OCR

Do not assume a good-looking preview means stable OCR.

### Overlay

Overlay feature is usable, but if future issues appear, rollback is easy because:

- fade logic is isolated in `game_overlay_window.py`
- manual visible vs auto-hidden state is explicit

## Recent Fixes That Should Not Be Lost

1. log window double-pass auto-scroll
2. source-independent `newsource` build structure
3. runtime icon + taskbar icon fix
4. overlay border/shadow suppression in non-edit mode
5. overlay fade-out and auto-hide state separation
6. overlay text style split:
   - text opacity
   - outline opacity
   - background opacity
   - overlay opacity
7. region border geometry update when hidden
8. OCR image upscale before Tesseract
9. removal of the two over-aggressive OCR extra options

## If Continuing In A New Chat

The safest instruction to give the next model is:

1. read:
   - `newsource/HANDOFF_CONTEXT.md`
   - `newsource/PROJECT_SPEC.md`
   - `newsource/DESIGN/ARCHITECTURE.md`
   - `newsource/DESIGN/APP_UX_DECISIONS.md`
2. treat `newsource/` as the active project
3. do not reintroduce runtime imports from the old Eel/web source
4. preserve current overlay behavior unless explicitly changing it
5. preserve current packaging behavior where build does not leak the live API key

## Suggested Next Work Items

If work continues later, the most likely next valuable tasks are:

1. OCR stabilization via optional dual-polarity OCR or heuristic fallback
2. multi-region support
3. game overlay polish
4. cleanup pass on docs/config defaults if the project is moved into a separate repo

