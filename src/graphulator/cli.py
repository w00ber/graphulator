#!/usr/bin/env python3
"""
Command-line interface for Graphulator.

This module provides the entry point for the 'graphulator' console command.
"""

import sys
from .graphulator_qt import main as gui_main


def main():
    """Main entry point for the graphulator command."""
    sys.exit(gui_main())


if __name__ == "__main__":
    main()
