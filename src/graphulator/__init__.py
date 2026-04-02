"""
Graphulator - Interactive Graph Drawing Tool

A PySide6-based GUI application for creating coupled mode theory graphs
and quantum circuit diagrams with matplotlib rendering.
"""

__version__ = "0.1.0"
__author__ = "J. Aumentado"
__email__ = "jose.aumentado@nist.gov"

from . import graph_primitives
from . import graphulator_config

__all__ = ["graph_primitives", "graphulator_config"]
