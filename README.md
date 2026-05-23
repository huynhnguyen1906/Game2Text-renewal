# Game2Text Renewal

Standalone native Windows rewrite of a modified Game2Text workflow.

## Status

This project currently includes:

- native main window
- native log window
- native filter/preview window
- region capture and border overlay
- OCR with Tesseract
- async translation flow
- game translation overlay
- PyInstaller packaging

## Development

Run from project root:

```powershell
.\venv\Scripts\Activate.ps1
python .\native_app.py
```

Build from project root:

```powershell
.\build_native.bat
```

## Upstream Attribution

This project is derived from and heavily modified from
[mathewthe2/Game2Text](https://github.com/mathewthe2/Game2Text).

The original upstream project is licensed under the Apache License 2.0.
This repository contains substantial modifications, a native standalone
runtime, and additional code that are not part of the official upstream
project.

This repository is not an official upstream release and is not maintained by
the original Game2Text author.

## License

This repository is distributed under the Apache License 2.0. See
[LICENSE](LICENSE).

