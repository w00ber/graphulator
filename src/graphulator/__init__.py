"""
Graphulator - Interactive Graph Drawing Tool

A PySide6-based GUI application for creating coupled mode theory graphs
and quantum circuit diagrams with matplotlib rendering.
"""

__version__ = "0.9.0"
__author__ = "J. Aumentado"
__copyright__ = "© J Aumentado"
__url__ = "https://github.com/w00ber/graphulator"

from . import graph_primitives
from . import graphulator_config

__all__ = ["graph_primitives", "graphulator_config"]
