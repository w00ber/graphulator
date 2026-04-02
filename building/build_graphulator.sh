#!/bin/bash
# Build graphulator as a standalone macOS app bundle
#
# Usage: conda activate CMT && ./building/build_graphulator.sh

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "=========================================="
echo "Building graphulator.app"
echo "=========================================="

# Use the conda environment's python explicitly
PYTHON="${CONDA_PREFIX}/bin/python"
PIP="${CONDA_PREFIX}/bin/pip"

if [ -z "$CONDA_PREFIX" ]; then
    echo "ERROR: Please activate your conda environment first:"
    echo "  conda activate CMT && ./build_graphulator.sh"
    exit 1
fi

echo "Using conda environment: $CONDA_PREFIX"
echo "Python: $PYTHON"

# Clean previous builds (use separate directories from paragraphulator)
echo "Cleaning previous builds..."
rm -rf build-graphulator-mac dist-graphulator-mac

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
echo "Running PyInstaller..."
"$PYTHON" -m PyInstaller building/graphulator-mac.spec --clean --noconfirm --distpath dist-graphulator-mac --workpath build-graphulator-mac

# Check if build succeeded
if [ -d "dist-graphulator-mac/graphulator.app" ]; then
    echo ""
    echo "=========================================="
    echo "SUCCESS! App bundle created at:"
    echo "  dist-graphulator-mac/graphulator.app"
    echo ""
    echo "To install, run:"
    echo "  ditto dist-graphulator-mac/graphulator.app /Applications/graphulator.app"
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
