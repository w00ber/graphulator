"""
Color utility functions for Graphulator UI.

Consolidates duplicated color combo box setup code from dialogs.
"""

from PySide6.QtWidgets import QComboBox
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt

from .. import graphulator_para_config as config


def populate_color_combo(combo: QComboBox, selected_key: str = None) -> None:
    """Populate a QComboBox with colors from the MYCOLORS palette.

    Each item displays the color name with a colored background swatch.

    Args:
        combo: The QComboBox to populate.
        selected_key: Optional color key to select (e.g. 'RED', 'BLUE').
    """
    combo.clear()
    for color_key, color_value in config.MYCOLORS.items():
        combo.addItem(f"  {color_key}", color_key)
        idx = combo.count() - 1
        combo.setItemData(idx, QColor(color_value), Qt.BackgroundRole)

    if selected_key:
        try:
            idx = list(config.MYCOLORS.keys()).index(selected_key)
            combo.setCurrentIndex(idx)
        except (ValueError, IndexError):
            combo.setCurrentIndex(0)
