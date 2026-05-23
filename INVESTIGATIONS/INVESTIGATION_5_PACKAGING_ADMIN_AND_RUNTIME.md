# Investigation 5: Packaging, Admin, And Runtime

## Scope

This investigation defines how the native Windows app should be packaged, launched with administrator rights when needed, resolve runtime resources, and keep user-editable files such as `config.ini`, `logs/`, and `profiles/` safe.

The native rewrite removes Eel/web streaming, so the existing `build.bat` and `game2text.spec` are references only, not the final build path.

## Executive Decision

Use PyInstaller for the native Windows app, but create a new native build script and a new native spec file.

Recommended direction:

- Entry point: `newsource/native_app.py`
- Build output: `dist/native-game2text/`
- Build tool: PyInstaller
- UI framework: PySide6
- Capture dependency: mss
- Hotkey dependency: keyboard
- OCR runtime: bundled Windows Tesseract from `resources/bin/win/tesseract`
- User-editable runtime files beside the executable:
  - `config.ini`
  - `logs/`
  - `profiles/`

Do not package old out-of-scope runtime systems:

- Eel/web
- Anki
- Textractor
- dictionaries
- Sudachi
- game scripts
- audio recording

This keeps the native package smaller and avoids carrying old feature coupling into the rewrite.

## Current Source Findings

### Existing Build Script

Current `build.bat` uses:

```bat
python -m eel game2text.py web ^
--windowed ^
--icon "public/icon.ico" ^
...
--add-data "logs;logs/" ^
--add-data "profiles;profiles/" ^
--add-data "gamescripts;gamescripts/" ^
--add-data "resources/sudachidict_small;sudachidict_small/" ^
--add-data "resources/sudachipy/resources;sudachipy/resources/" ^
--add-data "anki;anki/" ^
--add-data "resources/bin/win;resources/bin/win/" ^
--add-data "resources/dictionaries;resources/dictionaries/" ^
--add-data "config.ini;."
```

Useful:

- Existing PyInstaller-based distribution flow.
- Existing icon.
- Existing bundled `config.ini`.
- Existing `resources/bin/win/tesseract`.
- Existing `profiles/`.

Not suitable for native:

- Uses Eel build command.
- Packages web UI.
- Packages Anki/Textractor/dictionaries/Sudachi/game scripts.
- Packages `logs/` into the build, which risks mixing build-time logs with runtime logs.

### Existing PyInstaller Spec

Current `game2text.spec` is also Eel-oriented:

- entry: `game2text.py`
- data: `web`, Eel JS, logs, profiles, gamescripts, Anki, dictionaries, Sudachi, resources
- hidden imports: Eel/Bottle/Sudachi related
- name: `game2text`

Decision:

- Do not reuse this spec directly.
- Create a new native spec later:

```text
newsource/native-game2text.spec
```

### Existing Admin Script

Current admin launch:

```bat
run_admin.bat
run_as_admin.ps1
```

Current PowerShell script is hard-coded to this local workspace path:

```powershell
$pythonPath = "E:\GITHUB_SPACE\Game2Text\venv\Scripts\python.exe"
Start-Process powershell.exe ... -Verb RunAs
```

Useful:

- Confirms the current workflow already expects admin launch for global hotkeys.
- Uses Windows UAC `-Verb RunAs`.

Not suitable for packaged native app:

- Hard-coded developer path.
- Runs source Python, not packaged exe.
- Opens a PowerShell shell.

Decision:

- Replace with either:
  - packaged `.bat` that elevates the executable, or
  - in-app self-relaunch as admin.

For MVP, prefer a simple `run_native_admin.bat`.

## Runtime Folder Layout

Recommended packaged folder:

```text
dist/
  native-game2text/
    native-game2text.exe
    config.ini
    profiles/
      light-background.yaml
      wuwa.yaml
    logs/
      text/
      images/
    resources/
      bin/
        win/
          tesseract/
            tesseract.exe
            *.dll
            tessdata/
```

Notes:

- `config.ini` should be editable after build.
- `profiles/` should be editable because user uses full filter profile workflow.
- `logs/` should be created at runtime if missing.
- The app should not rely on writing inside PyInstaller `_MEIPASS`.

## Resource Path Strategy

Use two path concepts:

### Bundle Path

Where read-only bundled resources live.

In development:

```text
repo root
```

In PyInstaller:

```text
sys._MEIPASS
```

Used for:

- bundled Tesseract if placed inside PyInstaller bundle
- icons
- default templates

### Runtime Path

Where editable files live.

In development:

```text
repo root
```

In packaged build:

```text
folder containing native-game2text.exe
```

Used for:

- `config.ini`
- `logs/`
- `profiles/`

Recommended helper:

```python
def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]

def bundle_root() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return app_root()
```

Decision:

- Config/log/profile writes always use `app_root()`.
- Bundled read-only resources can use `bundle_root()`.

Reason:

- `sys._MEIPASS` is temporary/read-only in one-file mode.
- Even in one-folder mode, user data should not be mixed with temporary extraction folders.

## Config Strategy

Keep `config.ini` next to the executable.

Rules:

- On first run, if `config.ini` is missing, copy a default config from bundled templates or create one.
- Do not overwrite an existing user `config.ini` during app startup.
- Build process may copy a starter config into `dist/native-game2text/config.ini`.
- OpenAI key remains manually editable in `config.ini`.

Native sections to include:

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

[NATIVEAPP]
capture_hotkey = ctrl+q
select_region_hotkey = ctrl+shift+q
translation_queue_limit = 5
log_window_x = 1200
log_window_y = 120
log_window_width = 700
log_window_height = 900
always_on_top = true
dark_theme = true
```

Existing sections to preserve:

- `[OCRCONFIG]`
- `[TRANSLATIONCONFIG]`
- `[LOGCONFIG]`
- `[APPEARANCE]`

Decision:

- Native config service should repair missing native keys without removing old keys.

## Admin Strategy

Global hotkey may require admin if the focused game is elevated.

Recommended MVP strategy:

- Provide a `run_native_admin.bat`.
- Also show a status warning in the app if hotkey registration fails.

Example packaged admin launcher:

```bat
@echo off
powershell.exe -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~dp0native-game2text.exe' -Verb RunAs"
```

Alternative later:

- Self-relaunch as admin from inside Python using `ShellExecuteW(..., "runas", ...)`.

Pros of batch launcher:

- Simple.
- Easy to inspect.
- Avoids hidden elevation behavior.

Cons:

- User must launch through the admin batch file.

Decision:

- MVP: ship `run_native_admin.bat`.
- Later: optional in-app "Restart as admin" action.

## Manifest Strategy

Two options:

### Option A: Do Not Force Admin In Manifest

App can run normally.

Pros:

- No UAC prompt every launch.
- Better for config editing/testing.
- User can choose admin only when needed.

Cons:

- Hotkey may fail over elevated games.

### Option B: Require Administrator In Manifest

Every launch prompts UAC.

Pros:

- Hotkey likely works over elevated games.

Cons:

- More intrusive.
- Not always needed.
- Writing files beside exe under protected locations can still be awkward.

Decision:

- Do not force admin in manifest for MVP.
- Provide admin launcher.
- Add runtime warning if hotkey registration fails.

## Tesseract Packaging

Current bundled Windows Tesseract lives at:

```text
resources/bin/win/tesseract/tesseract.exe
resources/bin/win/tesseract/tessdata/
```

Native packaging should include only the needed OCR runtime:

```text
--add-data "resources/bin/win/tesseract;resources/bin/win/tesseract"
```

Do not include:

- `resources/bin/win/textractor`
- `resources/bin/win/wexpect`
- `resources/dictionaries`
- `resources/sudachidict_small`
- `resources/sudachipy`

Tesseract path in native:

```python
tesseract_cmd = runtime_or_bundle_path / "resources/bin/win/tesseract/tesseract.exe"
```

Tessdata path:

```python
tessdata_dir = runtime_or_bundle_path / "resources/bin/win/tesseract/tessdata"
```

Important:

- Avoid the old behavior that renames `tessdata` folders for legacy OCR mode.
- MVP should use LSTM/default tessdata directly.

## Profile Packaging

Profiles are user-facing and must remain editable.

Current profiles:

```text
profiles/light-background.yaml
profiles/wuwa.yaml
```

Packaging rule:

- Copy `profiles/` beside the executable.
- Native app loads profiles from runtime `profiles/`.
- Import/export writes YAML through user-selected path, defaulting to runtime `profiles/`.

Do not bundle profiles only inside `_MEIPASS`, because exported profiles must survive restart and rebuild.

## Logs Packaging

Do not package current `logs/` contents as build data.

Runtime rule:

- Create `logs/text/` and optional `logs/images/` on startup if missing.
- Preserve existing runtime logs across app restart.
- Build should not overwrite logs.

Reason:

- Logs are user data.
- Build-time logs should not become part of the release.
- Rebuilds should not erase or replace user logs.

## Requirements Strategy

Current requirements contain many old app dependencies.

Native MVP needs:

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

Maybe keep:

- `psutil` only if needed for process/admin checks.

Drop from native requirements:

- `Eel`
- `bottle`
- `bottle-websocket`
- `translators` if only OpenAI is used
- `pynput` if `keyboard` is enough
- `tk`
- `pydub`
- `fuzzywuzzy`
- `python-Levenshtein`
- `transformers`
- `wexpect`
- `pyperclip`
- Mac-only dependencies for Windows native MVP

Decision:

- Create separate native requirements later:

```text
newsource/requirements-native.txt
```

Do not mutate current `requirements.txt` yet because old source may still need it.

## Build Command

Recommended initial dev build command:

```bat
venv\Scripts\pyinstaller.exe ^
  --noconfirm ^
  --windowed ^
  --name native-game2text ^
  --icon public\icon.ico ^
  --add-data "resources\bin\win\tesseract;resources\bin\win\tesseract" ^
  --add-data "profiles;profiles" ^
  --add-data "config.ini;." ^
  newsource\native_app.py
```

Recommended final form:

```bat
venv\Scripts\pyinstaller.exe newsource\native-game2text.spec
```

Recommended build script:

```text
newsource/build_native.bat
```

Important:

- Build script should not delete user runtime `dist/native-game2text/logs`.
- If cleaning build output, back up or skip user-editable folders.

## One-File vs One-Folder

Recommended:

- Use one-folder mode for MVP.

Reason:

- Easier to keep editable `config.ini`, `profiles/`, and `logs/` next to exe.
- Easier to debug Tesseract resource paths.
- Faster startup than one-file extraction.
- Less chance of writing into a temporary `_MEIPASS` location.

One-file can be considered later after runtime paths are stable.

## Runtime Startup Checklist

At app start:

1. Enable DPI awareness before `QApplication`.
2. Resolve `app_root()` and `bundle_root()`.
3. Ensure `config.ini` exists.
4. Repair missing config sections/keys.
5. Ensure `logs/text/` exists.
6. Ensure `profiles/` exists.
7. Resolve Tesseract executable path.
8. Set `pytesseract.pytesseract.tesseract_cmd`.
9. Register hotkeys.
10. Open log window.
11. Restore log window geometry.
12. Restore region border if configured and region exists.

## Failure Handling

### Missing Config

Behavior:

- Create default config.
- Warn user in status area, not modal if possible.

### Missing Tesseract

Behavior:

- OCR disabled.
- Log/status shows clear error:

```text
Không tìm thấy Tesseract runtime.
```

### Hotkey Registration Fails

Behavior:

- App remains usable through UI buttons.
- Show warning:

```text
Không đăng ký được hotkey. Nếu game chạy admin, hãy chạy app bằng quyền admin.
```

### OpenAI Key Missing

Behavior:

- OCR still logs source text.
- Translation row shows red error or disabled translation state.
- Do not crash app.

### Profiles Missing

Behavior:

- Create empty `profiles/`.
- Filter UI still works with current config values.

## Files To Add Later

Recommended native packaging files:

```text
newsource/build_native.bat
newsource/requirements-native.txt
newsource/native-game2text.spec
newsource/run_native_admin.bat
newsource/native/paths.py
newsource/native/startup.py
```

## Prototype Checklist

Before final packaging:

- Dev run works from source.
- Packaged exe starts without console.
- Packaged exe finds `config.ini`.
- Packaged exe does not overwrite edited `config.ini`.
- Packaged exe loads profiles from runtime `profiles/`.
- Exported profile survives restart.
- Packaged exe creates `logs/text/`.
- Packaged exe writes logs.
- Packaged exe finds Tesseract.
- OCR works in packaged build.
- OpenAI translation works in packaged build.
- Hotkey works when app is normal and game is normal.
- Hotkey works when both app and game are admin.
- Non-admin app warns when hotkey registration fails.
- Rebuild does not erase runtime logs/profiles/config.

## Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Build copies old logs into release | Confusing stale logs | Do not package `logs/`; create at runtime. |
| Config inside `_MEIPASS` is edited instead of runtime config | User changes disappear | Use `app_root()` for editable config. |
| Tesseract path differs in packaged build | OCR fails | Centralize path resolution and verify in packaged prototype. |
| Admin required silently | Hotkey appears broken | Show hotkey registration warning and provide admin launcher. |
| PyInstaller misses PySide plugins | App fails to launch | Use PyInstaller hooks and validate clean packaged start. |
| Old dependencies bloat package | Large and fragile build | Use native requirements and exclude old features. |
| Rebuild overwrites user files | Data loss | Build to separate output or preserve runtime folders. |

## Investigation 5 Result

Native packaging should be a clean PyInstaller one-folder build with a separate native spec and native build script.

Final decisions:

- Do not reuse the Eel build command directly.
- Create a new native PyInstaller spec.
- Keep editable `config.ini`, `profiles/`, and `logs/` beside the exe.
- Bundle only Tesseract resources required for OCR.
- Do not bundle old Anki/Textractor/dictionary/Sudachi/web dependencies.
- Do not force admin in the manifest for MVP.
- Provide an admin launcher batch file.
- Warn clearly if hotkey registration fails.
- Use one-folder packaging until runtime paths are stable.

This keeps the packaged native app focused, easier to debug, and safer for user-owned config/log/profile files.
