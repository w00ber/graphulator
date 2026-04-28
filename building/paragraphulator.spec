# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for paragraphulator.

Build with:
    pyinstaller building/paragraphulator.spec --noconfirm --clean

Produces a one-folder distribution in dist/paragraphulator/.
On macOS it also creates a .app bundle at dist/paragraphulator.app.
"""

import sys
import tomllib
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

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
MAC_ICON = str(ROOT / "misc" / "paragraphulator.icns") if IS_MAC else None
WIN_ICON_PATH = ROOT / "misc" / "paragraphulator.ico"
WIN_ICON = str(WIN_ICON_PATH) if IS_WIN and WIN_ICON_PATH.exists() else None

# ── Entry point ───────────────────────────────────────────────────────
LAUNCHER = HERE / "paragraphulator_launcher.py"

# ── Bundled data ──────────────────────────────────────────────────────
matplotlib_datas = collect_data_files("matplotlib")

try:
    certifi_datas = collect_data_files("certifi")
except Exception:
    certifi_datas = []

# On Windows, bundle the full PySide6 install so QtWebEngineProcess and
# its resources ship with the .exe. On macOS the QtWebEngine framework
# is already inside the PySide6 wheel and the default collection picks
# it up.
if IS_WIN:
    try:
        pyside6_datas, pyside6_binaries, pyside6_hiddenimports = collect_all("PySide6")
    except Exception:
        pyside6_datas, pyside6_binaries, pyside6_hiddenimports = [], [], []
else:
    pyside6_datas, pyside6_binaries, pyside6_hiddenimports = [], [], []

datas = [
    (str(PKG / "help_para.md"), "graphulator"),
    (str(PKG / "tutorial.md"), "graphulator"),
    (str(PKG / "tutorial_images"), "graphulator/tutorial_images"),
    (str(PKG / "examples" / "pgraphs"), "graphulator/examples/pgraphs"),
    (str(ROOT / "examples" / "pgraphs"), "examples/pgraphs"),
    (str(PKG / "katex"), "graphulator/katex"),
    (str(PKG / "assets"), "graphulator/assets"),
]
datas.extend(matplotlib_datas)
datas.extend(certifi_datas)
datas.extend(pyside6_datas)

# ── Hidden imports ────────────────────────────────────────────────────
hiddenimports = [
    # PySide6
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebChannel",
    "PySide6.QtNetwork",
    "PySide6.QtPrintSupport",
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
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
    "matplotlib.mathtext",
    "matplotlib._mathtext",
    # NumPy
    "numpy",
    "numpy.core",
    "numpy.core._multiarray_umath",
    "numpy.linalg",
    "numpy.fft",
    "numpy.random",
    # SymPy
    "sympy",
    "sympy.core",
    "sympy.core.sympify",
    "sympy.core.basic",
    "sympy.core.expr",
    "sympy.core.symbol",
    "sympy.core.numbers",
    "sympy.core.add",
    "sympy.core.mul",
    "sympy.core.power",
    "sympy.functions",
    "sympy.functions.elementary",
    "sympy.functions.elementary.exponential",
    "sympy.functions.elementary.trigonometric",
    "sympy.functions.elementary.complexes",
    "sympy.parsing",
    "sympy.parsing.sympy_parser",
    "sympy.simplify",
    "sympy.simplify.simplify",
    "sympy.polys",
    "sympy.matrices",
    "sympy.printing",
    "sympy.printing.latex",
    "mpmath",
    # Seaborn
    "seaborn",
    "seaborn.rcmod",
    "seaborn.palettes",
    # Graphulator modules
    "graphulator",
    "graphulator.graphulator_para",
    "graphulator.graphulator_para_config",
    "graphulator.graph_primitives",
    "graphulator.autograph",
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
    "textwrap",
    "xml.etree.ElementTree",
    # Packaging (used by some dependencies)
    "packaging",
    "packaging.version",
    "packaging.specifiers",
    "packaging.requirements",
    # Markdown rendering
    "markdown",
    "markdown.extensions",
    "markdown.extensions.fenced_code",
    "markdown.extensions.tables",
    # SSL/Network for MathJax CDN loading
    "certifi",
    "ssl",
    "urllib3",
]
hiddenimports.extend(pyside6_hiddenimports)

# ── Excludes ──────────────────────────────────────────────────────────
excludes = [
    "tkinter",
    "IPython",
    "jupyter",
    "notebook",
    "ipykernel",
    "ipywidgets",
    "scipy",
    "test",
    "tests",
    "pytest",
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
    "PySide6.QtWebSockets",
    "PySide6.QtXml",
]

# NOTE: do NOT exclude `unittest`. pyparsing.testing (a transitive
# matplotlib dep) imports it at module load time, and a frozen app with
# it excluded raises `ModuleNotFoundError: No module named 'unittest'`.
if IS_MAC:
    excludes.extend([
        "PySide6.QtVirtualKeyboard",
        "PySide6.QtDBus",
    ])

# ── Analysis ──────────────────────────────────────────────────────────
a = Analysis(
    [str(LAUNCHER)],
    pathex=[str(PKG), str(SRC)],
    binaries=pyside6_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,  # Don't optimize — NumPy needs docstrings
)

pyz = PYZ(a.pure)

# ── Executable ────────────────────────────────────────────────────────
# macOS: strip debug symbols to reduce bundle size.
# Windows: leave symbols (stripping has caused DLL load issues in the past).
STRIP = IS_MAC

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="paragraphulator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=STRIP,
    upx=False,
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
    strip=STRIP,
    upx=False,
    upx_exclude=[],
    name="paragraphulator",
)

# ── macOS .app bundle ─────────────────────────────────────────────────
if IS_MAC:
    app = BUNDLE(
        coll,
        name="paragraphulator.app",
        icon=MAC_ICON,
        bundle_identifier="com.graphulator.paragraphulator",
        info_plist={
            "CFBundleName": "paragraphulator",
            "CFBundleDisplayName": "paragraphulator",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
            "NSPrincipalClass": "NSApplication",
            "LSMinimumSystemVersion": "10.15",
        },
    )
