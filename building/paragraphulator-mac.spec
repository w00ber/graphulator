# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for paragraphulator macOS app bundle.

Run with: pyinstaller paragraphulator.spec
From the conda CMT environment.
"""

import sys
from pathlib import Path

# Get the project root (one level up from building/)
project_root = Path(SPECPATH).parent
src_dir = project_root / 'src' / 'graphulator'
icon_path = project_root / 'misc' / 'paragraphulator.icns'

# Use launcher script that properly handles imports
launcher_script = project_root / 'building' / 'paragraphulator_launcher.py'

# Collect matplotlib data files (fonts, etc.) - required for mathtext rendering
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
matplotlib_datas = collect_data_files('matplotlib')

# Collect certifi CA certificates for HTTPS (needed for MathJax CDN)
try:
    certifi_datas = collect_data_files('certifi')
except Exception:
    certifi_datas = []

# Collect data files
datas = [
    # Include help file
    (str(src_dir / 'help_para.md'), 'graphulator'),
    # Include tutorial file and images
    (str(src_dir / 'tutorial.md'), 'graphulator'),
    (str(src_dir / 'tutorial_images'), 'graphulator/tutorial_images'),
    # Include example pgraphs (parametric graph files)
    (str(src_dir / 'examples' / 'pgraphs'), 'graphulator/examples/pgraphs'),
    # Include examples from top level
    (str(project_root / 'examples' / 'pgraphs'), 'examples/pgraphs'),
    # Include KaTeX for local LaTeX rendering (no CDN dependency)
    (str(src_dir / 'katex'), 'graphulator/katex'),
]

# Add matplotlib data files
datas.extend(matplotlib_datas)

# Add certifi CA certificates
datas.extend(certifi_datas)

# Hidden imports that PyInstaller may miss
hiddenimports = [
    # PySide6
    'PySide6',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebChannel',
    'PySide6.QtNetwork',
    'PySide6.QtPrintSupport',
    'PySide6.QtSvg',
    'PySide6.QtSvgWidgets',
    # Matplotlib
    'matplotlib',
    'matplotlib.pyplot',
    'matplotlib.figure',
    'matplotlib.backends',
    'matplotlib.backends.backend_qtagg',
    'matplotlib.backends.backend_qt5agg',
    'matplotlib.backends.backend_agg',
    'matplotlib.backends.backend_svg',
    'matplotlib.backends.backend_pdf',
    'matplotlib.patches',
    'matplotlib.path',
    'matplotlib.colors',
    'matplotlib.cm',
    'matplotlib.ticker',
    'matplotlib.lines',
    'matplotlib.text',
    'matplotlib.artist',
    'matplotlib.transforms',
    'matplotlib.collections',
    'matplotlib.font_manager',
    'matplotlib.mathtext',
    'matplotlib._mathtext',
    # NumPy
    'numpy',
    'numpy.core',
    'numpy.core._multiarray_umath',
    'numpy.linalg',
    'numpy.fft',
    'numpy.random',
    # SymPy
    'sympy',
    'sympy.core',
    'sympy.core.sympify',
    'sympy.core.basic',
    'sympy.core.expr',
    'sympy.core.symbol',
    'sympy.core.numbers',
    'sympy.core.add',
    'sympy.core.mul',
    'sympy.core.power',
    'sympy.functions',
    'sympy.functions.elementary',
    'sympy.functions.elementary.exponential',
    'sympy.functions.elementary.trigonometric',
    'sympy.functions.elementary.complexes',
    'sympy.parsing',
    'sympy.parsing.sympy_parser',
    'sympy.simplify',
    'sympy.simplify.simplify',
    'sympy.polys',
    'sympy.matrices',
    'sympy.printing',
    'sympy.printing.latex',
    'mpmath',
    # Seaborn
    'seaborn',
    'seaborn.rcmod',
    'seaborn.palettes',
    # Graphulator modules
    'graphulator',
    'graphulator.graphulator_para',
    'graphulator.graphulator_para_config',
    'graphulator.graph_primitives',
    'graphulator.autograph',
    # Other
    'json',
    'copy',
    'math',
    'collections',
    'functools',
    'itertools',
    'warnings',
    'traceback',
    'io',
    're',
    'textwrap',
    'xml.etree.ElementTree',
    # Packaging (used by some dependencies)
    'packaging',
    'packaging.version',
    'packaging.specifiers',
    'packaging.requirements',
    # Markdown rendering
    'markdown',
    'markdown.extensions',
    'markdown.extensions.fenced_code',
    'markdown.extensions.tables',
    # SSL/Network for MathJax CDN loading
    'certifi',
    'ssl',
    'urllib3',
]

a = Analysis(
    [str(launcher_script)],
    pathex=[str(src_dir), str(project_root / 'src')],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Python packages we don't use
        'tkinter',
        'IPython',
        'jupyter',
        'notebook',
        'ipykernel',
        'ipywidgets',
        'scipy',  # Not used directly
        'test',
        'tests',
        'pytest',
        # Exclude PyQt5 to avoid conflict with PySide6
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.sip',
        'qtpy',
        # Unused PySide6/Qt modules (saves ~100MB+)
        'PySide6.Qt3DAnimation',
        'PySide6.Qt3DCore',
        'PySide6.Qt3DExtras',
        'PySide6.Qt3DInput',
        'PySide6.Qt3DLogic',
        'PySide6.Qt3DRender',
        'PySide6.QtBluetooth',
        'PySide6.QtCharts',
        'PySide6.QtConcurrent',
        'PySide6.QtDataVisualization',
        'PySide6.QtDesigner',
        'PySide6.QtGraphs',
        'PySide6.QtHelp',
        'PySide6.QtLocation',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'PySide6.QtNetworkAuth',
        'PySide6.QtNfc',
        'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets',
        'PySide6.QtPdf',
        'PySide6.QtPdfWidgets',
        'PySide6.QtPositioning',
        'PySide6.QtQml',
        'PySide6.QtQuick',
        'PySide6.QtQuick3D',
        'PySide6.QtQuickControls2',
        'PySide6.QtQuickWidgets',
        'PySide6.QtRemoteObjects',
        'PySide6.QtScxml',
        'PySide6.QtSensors',
        'PySide6.QtSerialBus',
        'PySide6.QtSerialPort',
        'PySide6.QtShaderTools',
        'PySide6.QtSpatialAudio',
        'PySide6.QtSql',
        'PySide6.QtStateMachine',
        'PySide6.QtTest',
        'PySide6.QtTextToSpeech',
        'PySide6.QtUiTools',
        'PySide6.QtWebSockets',
        'PySide6.QtXml',
        'PySide6.QtVirtualKeyboard',
        'PySide6.QtDBus',
    ],
    noarchive=False,
    optimize=0,  # Don't optimize - NumPy needs docstrings
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='paragraphulator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,  # Strip debug symbols to reduce size
    upx=False,  # UPX can cause issues on macOS
    console=False,  # No console window for GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,  # Strip debug symbols from collected binaries
    upx=False,
    upx_exclude=[],
    name='paragraphulator',
)

app = BUNDLE(
    coll,
    name='paragraphulator.app',
    icon=str(icon_path) if icon_path.exists() else None,
    bundle_identifier='com.graphulator.paragraphulator',
    info_plist={
        'CFBundleName': 'paragraphulator',
        'CFBundleDisplayName': 'paragraphulator',
        'CFBundleShortVersionString': '0.5.0',
        'CFBundleVersion': '0.5.0',
        'NSHighResolutionCapable': True,
        'NSPrincipalClass': 'NSApplication',
        'LSMinimumSystemVersion': '10.15',
    },
)
