#!/usr/bin/env python
"""
Launcher script for graphulator.
This script properly imports and runs graphulator as a module,
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

# Import and run the main function
from graphulator.graphulator_qt import main

if __name__ == '__main__':
    main()
