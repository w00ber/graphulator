# Building Standalone Executables

This directory contains everything needed to build standalone desktop apps
(macOS `.app` bundles and Windows `.exe` files) using PyInstaller.

**Important:** PyInstaller does not support cross-compilation. You must build on the target platform:
- macOS `.app` bundle -> build on macOS
- Windows `.exe` -> build on Windows

## Directory Contents

| File | Purpose |
|------|---------|
| `graphulator-mac.spec` | PyInstaller spec for graphulator on macOS |
| `graphulator-win.spec` | PyInstaller spec for graphulator on Windows |
| `paragraphulator-mac.spec` | PyInstaller spec for paragraphulator on macOS |
| `paragraphulator-win.spec` | PyInstaller spec for paragraphulator on Windows |
| `build_graphulator.sh` | macOS build script for graphulator |
| `build_graphulator.bat` | Windows build script for graphulator |
| `build_paragraphulator.sh` | macOS build script for paragraphulator |
| `build_paragraphulator.bat` | Windows build script for paragraphulator |
| `graphulator_launcher.py` | PyInstaller entry point for graphulator |
| `paragraphulator_launcher.py` | PyInstaller entry point for paragraphulator |

The **launcher scripts** are thin wrappers that handle import path setup when
running inside a PyInstaller bundle. They are referenced by the `.spec` files
and are not meant to be run directly.

## Prerequisites

1. **Conda environment** with all dependencies installed (PySide6, matplotlib, numpy, sympy, seaborn, etc.)
2. **PyInstaller** installed in the conda environment (the build scripts will install it if missing)
3. **graphulator** package installed in development mode (`pip install -e .`)

## Quick Start

All commands are run from the **project root directory** (one level up from `building/`).

### macOS

```bash
conda activate CMT
./building/build_graphulator.sh
# or
./building/build_paragraphulator.sh
```

Output: `dist-graphulator-mac/graphulator.app` or `dist-mac/paragraphulator.app`

To install system-wide (use `ditto`, not `cp -r`, to preserve symlinks):
```bash
ditto dist-mac/paragraphulator.app /Applications/paragraphulator.app
```

### Windows

```cmd
conda activate CMT
building\build_graphulator.bat
REM or
building\build_paragraphulator.bat
```

Output: `dist-graphulator-win\graphulator\graphulator.exe` or `dist-win\paragraphulator\paragraphulator.exe`

## Troubleshooting

### macOS: Library Symbol Conflicts (iconv)

**Symptom:** `dyld: Symbol not found: _iconv`

**Cause:** Using homebrew's PyInstaller instead of conda's. The build scripts
avoid this by explicitly using `${CONDA_PREFIX}/bin/python -m PyInstaller`.

### macOS: "App is damaged" Warning

Unsigned apps trigger Gatekeeper. Either:
1. Right-click the app and select "Open" (bypasses Gatekeeper once)
2. Remove the quarantine attribute: `xattr -cr /Applications/paragraphulator.app`

### Windows: Missing Visual C++ Runtime

**Symptom:** Missing DLL errors (e.g., `VCRUNTIME140.dll`)

**Solution:** Install the [Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe).

### Windows: Antivirus False Positives

PyInstaller executables are sometimes flagged. Sign the executable or submit for whitelisting.

### Relative Import Errors

**Symptom:** `ImportError: attempted relative import with no known parent package`

The launcher scripts handle this by setting up `sys.path` before importing.
If you see this error, make sure the spec file points to the correct launcher.

### Missing Hidden Imports

**Symptom:** `ModuleNotFoundError` at runtime.

Add the missing module to the `hiddenimports` list in the relevant `.spec` file.

### Debugging Launch Failures

Run the executable directly from a terminal to see error output:
```bash
# macOS
./dist-mac/paragraphulator.app/Contents/MacOS/paragraphulator

# Windows
dist-win\paragraphulator\paragraphulator.exe
```

## Bundle Size

Bundles are large (~500MB+) because they include the Python interpreter, Qt,
and all dependencies. The macOS build scripts automatically strip unused Qt
plugins and translations to reduce size.
