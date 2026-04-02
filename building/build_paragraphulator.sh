#!/bin/bash
# Build paragraphulator as a standalone macOS app bundle
#
# Usage: conda activate CMT && ./building/build_paragraphulator.sh

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "=========================================="
echo "Building paragraphulator.app"
echo "=========================================="

# Use the conda environment's python explicitly
PYTHON="${CONDA_PREFIX}/bin/python"
PIP="${CONDA_PREFIX}/bin/pip"

if [ -z "$CONDA_PREFIX" ]; then
    echo "ERROR: Please activate your conda environment first:"
    echo "  conda activate CMT && ./build_paragraphulator.sh"
    exit 1
fi

echo "Using conda environment: $CONDA_PREFIX"
echo "Python: $PYTHON"

# Clean previous builds (macOS-specific directories)
echo "Cleaning previous builds..."
rm -rf build-mac dist-mac

# Ensure pyinstaller is installed in the conda environment
echo "Checking pyinstaller..."
if ! "$PYTHON" -c "import PyInstaller" 2>/dev/null; then
    echo "PyInstaller not found in conda env. Installing..."
    "$PIP" install pyinstaller
fi

echo "Using PyInstaller from conda env"

# Install the package in development mode (if not already)
echo "Ensuring graphulator is installed..."
"$PIP" install -e . --quiet

# Run PyInstaller using python -m to ensure correct environment
# Use --distpath and --workpath to avoid conflicts with Windows builds
echo "Running PyInstaller..."
"$PYTHON" -m PyInstaller building/paragraphulator-mac.spec --clean --noconfirm --distpath dist-mac --workpath build-mac

# Check if build succeeded
if [ -d "dist-mac/paragraphulator.app" ]; then
    echo ""
    echo "Cleaning up unnecessary Qt files..."

    # Remove Qt translation files (saves ~5MB)
    rm -rf dist-mac/paragraphulator.app/Contents/Frameworks/PySide6/Qt/translations 2>/dev/null
    rm -rf dist-mac/paragraphulator.app/Contents/Resources/PySide6/Qt/translations 2>/dev/null

    # Remove QtWebEngine locales except English (saves ~20MB)
    LOCALES_DIR="dist-mac/paragraphulator.app/Contents/Frameworks/PySide6/Qt/lib/QtWebEngineCore.framework/Versions/A/Resources/qtwebengine_locales"
    if [ -d "$LOCALES_DIR" ]; then
        find "$LOCALES_DIR" -name "*.pak" ! -name "en-US.pak" ! -name "en-GB.pak" -delete 2>/dev/null
        echo "  Removed non-English QtWebEngine locales"
    fi

    # Remove Qt plugins we don't need
    PLUGINS_DIR="dist-mac/paragraphulator.app/Contents/Frameworks/PySide6/Qt/plugins"
    if [ -d "$PLUGINS_DIR" ]; then
        rm -rf "$PLUGINS_DIR/sqldrivers" 2>/dev/null
        rm -rf "$PLUGINS_DIR/virtualkeyboard" 2>/dev/null
        rm -rf "$PLUGINS_DIR/position" 2>/dev/null
        rm -rf "$PLUGINS_DIR/sensors" 2>/dev/null
        rm -rf "$PLUGINS_DIR/texttospeech" 2>/dev/null
        rm -rf "$PLUGINS_DIR/multimedia" 2>/dev/null
        rm -rf "$PLUGINS_DIR/qmltooling" 2>/dev/null
        echo "  Removed unused Qt plugins"
    fi

    # Re-sign the app after modifications
    echo "Re-signing app bundle..."
    codesign --force --deep --sign - dist-mac/paragraphulator.app 2>/dev/null

    # Report final size
    FINAL_SIZE=$(du -sh dist-mac/paragraphulator.app | cut -f1)

    echo ""
    echo "=========================================="
    echo "SUCCESS! App bundle created at:"
    echo "  dist-mac/paragraphulator.app"
    echo ""
    echo "Final size: $FINAL_SIZE"
    echo ""
    echo "To install, run:"
    echo "  ditto dist-mac/paragraphulator.app /Applications/paragraphulator.app"
    echo ""
    echo "NOTE: Use 'ditto' instead of 'cp -r' to preserve symlinks"
    echo "      (cp -r expands symlinks and inflates app size)"
    echo "=========================================="
else
    echo ""
    echo "=========================================="
    echo "ERROR: Build failed. Check output above."
    echo "=========================================="
    exit 1
fi
