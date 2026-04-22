# Building Standalone Executables

This directory contains everything needed to build standalone desktop apps
(macOS `.app` bundles and Windows `.exe` folders) using PyInstaller.

**Important:** PyInstaller does not support cross-compilation. You must build
on the target platform — a macOS bundle has to be built on macOS, a Windows
`.exe` on Windows.

## Directory contents

| File | Purpose |
|------|---------|
| `graphulator.spec` | Unified PyInstaller spec for graphulator (mac + win) |
| `paragraphulator.spec` | Unified PyInstaller spec for paragraphulator (mac + win) |
| `build.sh` | macOS build wrapper — takes app name as an argument |
| `build.bat` | Windows build wrapper — takes app name as an argument |
| `graphulator_launcher.py` | PyInstaller entry point for graphulator |
| `paragraphulator_launcher.py` | PyInstaller entry point for paragraphulator |

The **launcher scripts** are thin wrappers that handle `sys.path` setup when
running inside a frozen PyInstaller bundle. They are referenced by the `.spec`
files and are not meant to be run directly.

Each spec uses `sys.platform` to branch between the macOS and Windows builds,
so a single spec covers both platforms. The app version in the macOS
`Info.plist` is read live from `pyproject.toml`, so `CFBundleShortVersionString`
stays in sync automatically.

## Prerequisites

1. A conda (or other) Python environment with the runtime dependencies
   installed (`PySide6`, `matplotlib`, `numpy`, `sympy`, `seaborn`, etc.).
2. `PyInstaller` in that same environment — the build scripts will install it
   if missing.
3. The `graphulator` package installed in editable mode (`pip install -e .`).
   The build scripts do this automatically.

## Quick start

Run all commands from the **project root** (one level up from `building/`).

### macOS

```bash
conda activate CMT
./building/build.sh graphulator
./building/build.sh paragraphulator
```

Output: `dist/graphulator.app` / `dist/paragraphulator.app`.

Install system-wide with `ditto` (preserves symlinks — `cp -r` inflates app size):

```bash
ditto dist/paragraphulator.app /Applications/paragraphulator.app
```

### Windows

```cmd
conda activate CMT
building\build.bat graphulator
building\build.bat paragraphulator
```

Output: `dist\graphulator\graphulator.exe` / `dist\paragraphulator\paragraphulator.exe`.

## CI builds

The GitHub Actions workflow at `.github/workflows/build-apps.yml` builds all
four variants (graphulator + paragraphulator, macOS + Windows) on every
tagged release (`v*`) and whenever you manually trigger the workflow.

## Troubleshooting

### macOS: "App is damaged" warning

Unsigned apps trigger Gatekeeper. Either right-click → Open (bypasses Gatekeeper
once), or remove the quarantine attribute:

```bash
xattr -cr /Applications/paragraphulator.app
```

### macOS: library symbol conflicts (`_iconv`, etc.)

Usually caused by using Homebrew's PyInstaller instead of the conda-environment
one. `build.sh` avoids this by calling `${CONDA_PREFIX}/bin/python -m PyInstaller`
explicitly — make sure your conda env is activated.

### Windows: missing Visual C++ runtime

If the built `.exe` complains about missing `VCRUNTIME140.dll`, install the
[Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe).

### Windows: antivirus false positives

PyInstaller `.exe` files are sometimes flagged. Code-sign the binary or submit
it to the AV vendor for whitelisting.

### Missing hidden imports

Symptom: `ModuleNotFoundError` at runtime in the frozen app. Fix: add the
missing module to the `hiddenimports` list in the relevant `.spec` file.

### Debugging launch failures

Run the executable directly from a terminal to see the error output:

```bash
# macOS
./dist/paragraphulator.app/Contents/MacOS/paragraphulator

# Windows
dist\paragraphulator\paragraphulator.exe
```

## Bundle size

Bundles are large (~300–500 MB) because they carry a full Python interpreter,
Qt, and all runtime dependencies. `build.sh` strips unused Qt plugins,
translations, and (for paragraphulator) non-English QtWebEngine locales to
shave 100+ MB off the macOS bundle.
