# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for graphulator Windows executable.

Run with: python -m PyInstaller graphulator-win.spec
From a conda environment with all dependencies installed.
"""

import sys
from pathlib import Path

# Get the project root (one level up from building/)
project_root = Path(SPECPATH).parent
src_dir = project_root / 'src' / 'graphulator'
icon_path = project_root / 'misc' / 'graphulator.ico'

# Use launcher script that properly handles imports
launcher_script = project_root / 'building' / 'graphulator_launcher.py'

# Collect matplotlib data files (fonts, etc.)
from PyInstaller.utils.hooks import collect_data_files
matplotlib_datas = collect_data_files('matplotlib')

# Collect data files
datas = [
    # Include example graphs
    (str(src_dir / 'examples' / 'graphs'), 'graphulator/examples/graphs'),
    # Include examples from top level
    (str(project_root / 'examples' / 'graphs'), 'examples/graphs'),
]

# Add matplotlib data files
datas.extend(matplotlib_datas)

# Hidden imports that PyInstaller may miss
hiddenimports = [
    # PySide6 (no WebEngine needed for graphulator)
    'PySide6',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
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
    # NumPy
    'numpy',
    'numpy.core',
    'numpy.core._multiarray_umath',
    'numpy.linalg',
    'numpy.fft',
    'numpy.random',
    # Graphulator modules
    'graphulator',
    'graphulator.graphulator_qt',
    'graphulator.graphulator_config',
    'graphulator.graph_primitives',
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
        'scipy',
        'sympy',  # graphulator doesn't use sympy
        'test',
        'tests',
        'unittest',
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
        'PySide6.QtWebChannel',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebSockets',
        'PySide6.QtXml',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='graphulator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX can cause issues with some DLLs
    console=False,  # No console window for GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path) if icon_path.exists() else None,
    version_info=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='graphulator',
)
