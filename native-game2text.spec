# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


ROOT = Path(SPECPATH)
ICON_PATH = ROOT / "public" / "icon.ico"
TESSERACT_DIR = ROOT / "resources" / "bin" / "win" / "tesseract"
PROFILES_DIR = ROOT / "profiles"
PUBLIC_DIR = ROOT / "public"
PACKAGING_DIR = ROOT / "build" / "packaging"
PACKAGED_CONFIG = PACKAGING_DIR / "config.ini"

def collect_dir_files(source_dir: Path, dest_prefix: str) -> list[tuple[str, str]]:
    collected: list[tuple[str, str]] = []
    if not source_dir.exists():
        return collected
    for file_path in source_dir.rglob("*"):
        if not file_path.is_file():
            continue
        relative_parent = file_path.relative_to(source_dir).parent
        if str(relative_parent) == ".":
            dest_dir = dest_prefix
        else:
            normalized_parent = str(relative_parent).replace("\\", "/")
            dest_dir = f"{dest_prefix}/{normalized_parent}"
        collected.append((str(file_path), dest_dir))
    return collected


datas = []
datas += collect_dir_files(TESSERACT_DIR, "resources/bin/win/tesseract")
datas += collect_dir_files(PROFILES_DIR, "profiles")
datas += collect_dir_files(PUBLIC_DIR, "public")
if PACKAGED_CONFIG.exists():
    datas.append((str(PACKAGED_CONFIG), "."))
datas += collect_data_files("certifi")

hiddenimports = collect_submodules("openai")
hiddenimports += collect_submodules("requests")
hiddenimports += collect_submodules("charset_normalizer")
hiddenimports += collect_submodules("urllib3")
hiddenimports += collect_submodules("idna")
hiddenimports += collect_submodules("certifi")
hiddenimports += [
    "cv2",
    "keyboard",
    "numpy",
    "PIL",
    "pytesseract",
    "yaml",
]

excludes = [
    "eel",
    "anki",
    "sudachidict_small",
    "sudachipy",
    "textractor",
]

a = Analysis(
    ["native_app.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="native-game2text",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(ICON_PATH) if ICON_PATH.exists() else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="native-game2text",
)
