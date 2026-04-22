# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for graphulator.

Build with:
    pyinstaller building/graphulator.spec --noconfirm --clean

Produces a one-folder distribution in dist/graphulator/.
On macOS it also creates a .app bundle at dist/graphulator.app.
"""

import sys
import tomllib
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

# ── Paths ─────────────────────────────────────────────────────────────
HERE = Path(SPECPATH)
ROOT = HERE.parent
SRC = ROOT / "src"
PKG = SRC / "graphulator"

# ── Platform helpers ──────────────────────────────────────────────────
IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"

# ── Version (read from pyproject.toml — single source of truth) ───────
with open(ROOT / "pyproject.toml", "rb") as f:
    VERSION = tomllib.load(f)["project"]["version"]

# ── Icon paths ────────────────────────────────────────────────────────
MAC_ICON = str(ROOT / "misc" / "graphulator.icns") if IS_MAC else None
WIN_ICON_PATH = ROOT / "misc" / "graphulator.ico"
WIN_ICON = str(WIN_ICON_PATH) if IS_WIN and WIN_ICON_PATH.exists() else None

# ── Entry point ───────────────────────────────────────────────────────
LAUNCHER = HERE / "graphulator_launcher.py"

# ── Bundled data ──────────────────────────────────────────────────────
matplotlib_datas = collect_data_files("matplotlib")

datas = [
    (str(PKG / "examples" / "graphs"), "graphulator/examples/graphs"),
    (str(ROOT / "examples" / "graphs"), "examples/graphs"),
]
datas.extend(matplotlib_datas)

# ── Hidden imports (PyInstaller sometimes misses these) ───────────────
hiddenimports = [
    # PySide6 (no WebEngine needed for graphulator)
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    # Matplotlib
    "matplotlib",
    "matplotlib.pyplot",
    "matplotlib.figure",
    "matplotlib.backends",
    "matplotlib.backends.backend_qtagg",
    "matplotlib.backends.backend_qt5agg",
    "matplotlib.backends.backend_agg",
    "matplotlib.backends.backend_svg",
    "matplotlib.backends.backend_pdf",
    "matplotlib.patches",
    "matplotlib.path",
    "matplotlib.colors",
    "matplotlib.cm",
    "matplotlib.ticker",
    "matplotlib.lines",
    "matplotlib.text",
    "matplotlib.artist",
    "matplotlib.transforms",
    "matplotlib.collections",
    "matplotlib.font_manager",
    # NumPy
    "numpy",
    "numpy.core",
    "numpy.core._multiarray_umath",
    "numpy.linalg",
    "numpy.fft",
    "numpy.random",
    # Graphulator modules
    "graphulator",
    "graphulator.graphulator_qt",
    "graphulator.graphulator_config",
    "graphulator.graph_primitives",
    # Other
    "json",
    "copy",
    "math",
    "collections",
    "functools",
    "itertools",
    "warnings",
    "traceback",
    "io",
    "re",
]

# ── Excludes ──────────────────────────────────────────────────────────
excludes = [
    "tkinter",
    "IPython",
    "jupyter",
    "notebook",
    "ipykernel",
    "ipywidgets",
    "scipy",
    "sympy",  # graphulator doesn't use sympy
    "test",
    "tests",
    # NOTE: do NOT exclude `unittest`. Several third-party packages
    # (pyparsing.testing, matplotlib.testing, ...) import unittest at
    # module load time. Excluding it saves ~2 MB but breaks the frozen
    # app with `ModuleNotFoundError: No module named 'unittest'`.
    "pytest",
    # Avoid PyQt5 / PySide6 conflicts
    "PyQt5",
    "PyQt5.QtCore",
    "PyQt5.QtGui",
    "PyQt5.QtWidgets",
    "PyQt5.sip",
    "qtpy",
    # Unused PySide6/Qt modules (saves ~100MB+)
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtBluetooth",
    "PySide6.QtCharts",
    "PySide6.QtConcurrent",
    "PySide6.QtDataVisualization",
    "PySide6.QtDesigner",
    "PySide6.QtGraphs",
    "PySide6.QtHelp",
    "PySide6.QtLocation",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNetworkAuth",
    "PySide6.QtNfc",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtPositioning",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickControls2",
    "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtSerialBus",
    "PySide6.QtSerialPort",
    "PySide6.QtShaderTools",
    "PySide6.QtSpatialAudio",
    "PySide6.QtSql",
    "PySide6.QtStateMachine",
    "PySide6.QtTest",
    "PySide6.QtTextToSpeech",
    "PySide6.QtUiTools",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
    "PySide6.QtXml",
]

# ── Analysis ──────────────────────────────────────────────────────────
a = Analysis(
    [str(LAUNCHER)],
    pathex=[str(PKG), str(SRC)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# ── Executable ────────────────────────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="graphulator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX can corrupt Qt/PySide6 binaries
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=WIN_ICON if IS_WIN else MAC_ICON,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="graphulator",
)

# ── macOS .app bundle ─────────────────────────────────────────────────
if IS_MAC:
    app = BUNDLE(
        coll,
        name="graphulator.app",
        icon=MAC_ICON,
        bundle_identifier="com.graphulator.graphulator",
        info_plist={
            "CFBundleName": "graphulator",
            "CFBundleDisplayName": "graphulator",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
            "NSPrincipalClass": "NSApplication",
            "LSMinimumSystemVersion": "10.15",
        },
    )
