# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all


ROOT = Path(SPECPATH)
ICON_PATH = ROOT / "public" / "icon.ico"
TESSERACT_DIR = ROOT / "resources" / "bin" / "win" / "tesseract"
PROFILES_DIR = ROOT / "profiles"
PUBLIC_DIR = ROOT / "public"
PACKAGING_DIR = ROOT / "build" / "packaging-gpu"
PACKAGED_CONFIG = PACKAGING_DIR / "config.ini"
PADDLE_RUNTIME_DIR = ROOT / "runtime" / "paddle"


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


def find_site_packages() -> Path:
    candidates = [
        ROOT / "venv" / "Lib" / "site-packages",
        ROOT / ".venv" / "Lib" / "site-packages",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Could not find venv site-packages for GPU build.")


SITE_PACKAGES = find_site_packages()
NVIDIA_CU13_BIN = SITE_PACKAGES / "nvidia" / "cu13" / "bin" / "x86_64"
NVIDIA_CUDNN_BIN = SITE_PACKAGES / "nvidia" / "cudnn" / "bin"
PYTHON_BIDI_DIST_INFO = SITE_PACKAGES / "python_bidi-0.6.10.dist-info"
OPENCV_CONTRIB_DIST_INFO = SITE_PACKAGES / "opencv_contrib_python-4.10.0.84.dist-info"
SAFETENSORS_DIST_INFO = SITE_PACKAGES / "safetensors-0.7.0.dist-info"


datas = []
datas += collect_dir_files(TESSERACT_DIR, "resources/bin/win/tesseract")
datas += collect_dir_files(PROFILES_DIR, "profiles")
datas += collect_dir_files(PUBLIC_DIR, "public")
datas += collect_dir_files(PADDLE_RUNTIME_DIR, "runtime/paddle")
datas += collect_dir_files(PYTHON_BIDI_DIST_INFO, "python_bidi-0.6.10.dist-info")
datas += collect_dir_files(OPENCV_CONTRIB_DIST_INFO, "opencv_contrib_python-4.10.0.84.dist-info")
datas += collect_dir_files(SAFETENSORS_DIST_INFO, "safetensors-0.7.0.dist-info")
if PACKAGED_CONFIG.exists():
    datas.append((str(PACKAGED_CONFIG), "."))


binaries = []
binaries += collect_dir_files(NVIDIA_CU13_BIN, "nvidia/cu13/bin/x86_64")
binaries += collect_dir_files(NVIDIA_CUDNN_BIN, "nvidia/cudnn/bin")


hiddenimports = [
    "cv2",
    "keyboard",
    "numpy",
    "PIL",
    "pytesseract",
    "yaml",
]

for package_name in (
    "paddle",
    "paddleocr",
    "paddlex",
    "chardet",
    "requests",
    "charset_normalizer",
    "imagesize",
    "pypdfium2",
    "pypdfium2_raw",
    "pyclipper",
    "bidi",
    "shapely",
    "safetensors",
):
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(package_name)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports


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
    binaries=binaries,
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
    name="native-game2text-gpu",
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
    name="native-game2text-gpu",
)
