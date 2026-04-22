#!/bin/bash
# Build a graphulator app as a standalone macOS .app bundle.
#
# Usage:
#     conda activate <your-env>
#     ./building/build.sh graphulator
#     ./building/build.sh paragraphulator
#
# Output: dist/<app>.app

set -e

APP="${1:-}"
case "$APP" in
    graphulator|paragraphulator) ;;
    *)
        echo "Usage: $0 {graphulator|paragraphulator}" >&2
        exit 2
        ;;
esac

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "=========================================="
echo "Building $APP.app"
echo "=========================================="

if [ -z "$CONDA_PREFIX" ]; then
    echo "ERROR: activate a conda environment first (e.g. 'conda activate CMT')." >&2
    exit 1
fi

PYTHON="${CONDA_PREFIX}/bin/python"
PIP="${CONDA_PREFIX}/bin/pip"

echo "Using conda environment: $CONDA_PREFIX"

if ! "$PYTHON" -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    "$PIP" install pyinstaller
fi

echo "Ensuring graphulator package is installed (editable)..."
"$PIP" install -e . --quiet

echo "Running PyInstaller on building/${APP}.spec..."
"$PYTHON" -m PyInstaller "building/${APP}.spec" --clean --noconfirm

APP_BUNDLE="dist/${APP}.app"

if [ ! -d "$APP_BUNDLE" ]; then
    echo "ERROR: expected bundle not found at $APP_BUNDLE" >&2
    exit 1
fi

echo "Trimming bundle size..."

# Qt translations (~5 MB)
rm -rf "$APP_BUNDLE/Contents/Frameworks/PySide6/Qt/translations" 2>/dev/null || true
rm -rf "$APP_BUNDLE/Contents/Resources/PySide6/Qt/translations" 2>/dev/null || true

# QtWebEngine non-English locales (paragraphulator only, ~20 MB)
LOCALES="$APP_BUNDLE/Contents/Frameworks/PySide6/Qt/lib/QtWebEngineCore.framework/Versions/A/Resources/qtwebengine_locales"
if [ -d "$LOCALES" ]; then
    find "$LOCALES" -name "*.pak" ! -name "en-US.pak" ! -name "en-GB.pak" -delete 2>/dev/null || true
fi

# Unused Qt plugins
PLUGINS="$APP_BUNDLE/Contents/Frameworks/PySide6/Qt/plugins"
if [ -d "$PLUGINS" ]; then
    for p in sqldrivers virtualkeyboard position sensors texttospeech multimedia qmltooling; do
        rm -rf "$PLUGINS/$p" 2>/dev/null || true
    done
fi

# Re-sign after modifications (ad-hoc signature — no Developer ID required)
codesign --force --deep --sign - "$APP_BUNDLE" 2>/dev/null || true

SIZE=$(du -sh "$APP_BUNDLE" | cut -f1)

echo ""
echo "=========================================="
echo "SUCCESS: $APP_BUNDLE  ($SIZE)"
echo ""
echo "Install with:"
echo "  ditto $APP_BUNDLE /Applications/${APP}.app"
echo "=========================================="
