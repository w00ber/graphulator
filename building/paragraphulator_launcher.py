#!/usr/bin/env python
"""
Launcher script for paragraphulator.
This script properly imports and runs paragraphulator as a module,
avoiding relative import issues when bundled with PyInstaller.
"""

import sys
import os

# Ensure the bundled resources can be found
if getattr(sys, 'frozen', False):
    # Running in a PyInstaller bundle
    bundle_dir = sys._MEIPASS
    # Add the bundle directory to the path
    if bundle_dir not in sys.path:
        sys.path.insert(0, bundle_dir)

    # Set QTWEBENGINEPROCESS_PATH for macOS app bundles
    # The WebEngine process is inside the PySide6 Qt framework
    if sys.platform == 'darwin':
        webengine_process = os.path.join(
            bundle_dir, 'PySide6', 'Qt', 'lib', 'QtWebEngineCore.framework',
            'Helpers', 'QtWebEngineProcess.app', 'Contents', 'MacOS', 'QtWebEngineProcess'
        )
        if os.path.exists(webengine_process):
            os.environ['QTWEBENGINEPROCESS_PATH'] = webengine_process

# Import and run the main function
from graphulator.graphulator_para import main

if __name__ == '__main__':
    main()
