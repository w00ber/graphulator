"""
Settings dialog and color palette widgets for paragraphulator.

This module contains the SettingsDialog and ColorPaletteWidget classes.
"""

import logging

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QColorDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import graphulator_para_config as config
from ..settings_dialog import SettingsDialogBase
from .shortcut_editor import ShortcutEditorWidget

logger = logging.getLogger(__name__)


class ColorPaletteWidget(QWidget):
    """Widget for editing a color palette with reordering support.

    Features:
    - List of color swatches with labels
    - Click swatch to edit color
    - Up/Down buttons for reordering
    - Add/Remove buttons
    - Reset to defaults button
    """

    # Signal emitted when palette changes
    palette_changed = Signal()

    def __init__(self, palette_name, default_colors, parent=None):
        """
        Args:
            palette_name: Display name for the palette (e.g., "Node Colors")
            default_colors: Default color list for reset functionality
                           Can be list of colors or dict of {key: color}
            parent: Parent widget
        """
        super().__init__(parent)
        self.palette_name = palette_name
        self.default_colors = default_colors

        # Current colors as list of (key, color) tuples for dict-style palettes,
        # or list of colors for simple list palettes
        self.is_dict_palette = isinstance(default_colors, dict)
        if self.is_dict_palette:
            self._colors = list(default_colors.items())
        else:
            self._colors = list(default_colors)

        self._setup_ui()

    def _setup_ui(self):
        """Set up the widget UI."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        # Header with palette name
        header = QLabel(f"<b>{self.palette_name}</b>")
        layout.addWidget(header)

        # Main content: list + buttons
        content_layout = QHBoxLayout()
        layout.addLayout(content_layout)

        # Color list
        self.list_widget = QListWidget()
        self.list_widget.setMinimumHeight(150)
        self.list_widget.setMaximumHeight(200)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        content_layout.addWidget(self.list_widget, stretch=1)

        # Button column
        button_layout = QVBoxLayout()
        content_layout.addLayout(button_layout)

        # Move Up button
        self.up_btn = QPushButton("▲")
        self.up_btn.setMaximumWidth(30)
        self.up_btn.setAutoDefault(False)
        self.up_btn.setToolTip("Move selected color up")
        self.up_btn.clicked.connect(self._move_up)
        button_layout.addWidget(self.up_btn)

        # Move Down button
        self.down_btn = QPushButton("▼")
        self.down_btn.setMaximumWidth(30)
        self.down_btn.setAutoDefault(False)
        self.down_btn.setToolTip("Move selected color down")
        self.down_btn.clicked.connect(self._move_down)
        button_layout.addWidget(self.down_btn)

        button_layout.addStretch()

        # Add button
        self.add_btn = QPushButton("+")
        self.add_btn.setMaximumWidth(30)
        self.add_btn.setAutoDefault(False)
        self.add_btn.setToolTip("Add new color")
        self.add_btn.clicked.connect(self._add_color)
        button_layout.addWidget(self.add_btn)

        # Remove button
        self.remove_btn = QPushButton("−")
        self.remove_btn.setMaximumWidth(30)
        self.remove_btn.setAutoDefault(False)
        self.remove_btn.setToolTip("Remove selected color")
        self.remove_btn.clicked.connect(self._remove_color)
        button_layout.addWidget(self.remove_btn)

        # Reset button
        reset_btn = QPushButton("Reset")
        reset_btn.setAutoDefault(False)
        reset_btn.setToolTip(f"Reset {self.palette_name} to defaults")
        reset_btn.clicked.connect(self._reset_to_defaults)
        layout.addWidget(reset_btn)

        # Populate list
        self._refresh_list()

    def _refresh_list(self):
        """Refresh the list widget with current colors."""
        self.list_widget.clear()

        for item_data in self._colors:
            if self.is_dict_palette:
                key, color = item_data
                display_text = f"{key}: {color}"
            else:
                color = item_data
                display_text = color

            list_item = QListWidgetItem(display_text)

            # Create color swatch icon
            pixmap = QPixmap(20, 20)
            try:
                qcolor = QColor(color)
                if qcolor.isValid():
                    pixmap.fill(qcolor)
                else:
                    pixmap.fill(QColor('gray'))
            except Exception:
                pixmap.fill(QColor('gray'))
            list_item.setIcon(QIcon(pixmap))

            self.list_widget.addItem(list_item)

    def _move_up(self):
        """Move selected item up."""
        row = self.list_widget.currentRow()
        if row > 0:
            self._colors[row], self._colors[row - 1] = self._colors[row - 1], self._colors[row]
            self._refresh_list()
            self.list_widget.setCurrentRow(row - 1)
            self.palette_changed.emit()

    def _move_down(self):
        """Move selected item down."""
        row = self.list_widget.currentRow()
        if row >= 0 and row < len(self._colors) - 1:
            self._colors[row], self._colors[row + 1] = self._colors[row + 1], self._colors[row]
            self._refresh_list()
            self.list_widget.setCurrentRow(row + 1)
            self.palette_changed.emit()

    def _add_color(self):
        """Add a new color to the palette."""
        color = QColorDialog.getColor(QColor('white'), self, "Select New Color")
        if color.isValid():
            color_name = color.name()
            if self.is_dict_palette:
                # Generate a new key
                existing_keys = [k for k, v in self._colors]
                new_key = f"COLOR{len(self._colors) + 1}"
                while new_key in existing_keys:
                    new_key = f"COLOR{int(new_key[5:]) + 1}"
                self._colors.append((new_key, color_name))
            else:
                self._colors.append(color_name)
            self._refresh_list()
            self.list_widget.setCurrentRow(len(self._colors) - 1)
            self.palette_changed.emit()

    def _remove_color(self):
        """Remove the selected color."""
        row = self.list_widget.currentRow()
        if row >= 0 and len(self._colors) > 1:  # Keep at least one color
            del self._colors[row]
            self._refresh_list()
            new_row = min(row, len(self._colors) - 1)
            self.list_widget.setCurrentRow(new_row)
            self.palette_changed.emit()

    def _on_item_double_clicked(self, item):
        """Handle double-click to edit color."""
        row = self.list_widget.row(item)
        if row >= 0:
            if self.is_dict_palette:
                key, current_color = self._colors[row]
            else:
                current_color = self._colors[row]

            color = QColorDialog.getColor(QColor(current_color), self, "Edit Color")
            if color.isValid():
                if self.is_dict_palette:
                    self._colors[row] = (key, color.name())
                else:
                    self._colors[row] = color.name()
                self._refresh_list()
                self.list_widget.setCurrentRow(row)
                self.palette_changed.emit()

    def _reset_to_defaults(self):
        """Reset palette to default colors."""
        if self.is_dict_palette:
            self._colors = list(self.default_colors.items())
        else:
            self._colors = list(self.default_colors)
        self._refresh_list()
        self.palette_changed.emit()

    def get_colors(self):
        """Get the current colors.

        Returns:
            dict for dict-style palettes, list for simple list palettes
        """
        if self.is_dict_palette:
            return dict(self._colors)
        else:
            return list(self._colors)

    def set_colors(self, colors):
        """Set the current colors.

        Args:
            colors: dict or list of colors depending on palette type
        """
        if self.is_dict_palette:
            if isinstance(colors, dict):
                self._colors = list(colors.items())
            else:
                self._colors = list(colors)
        else:
            self._colors = list(colors)
        self._refresh_list()


class SettingsDialog(SettingsDialogBase):
    """Paragraphulator Settings dialog.

    Extends the shared table-driven dialog with the app's extras: the
    export-rescale parameters (stored on the window, not the config
    module), the Color Palettes tab, and the Keyboard Shortcuts tab.
    """

    def __init__(self, parent=None):
        # Import settings constants from the main module (delayed to avoid
        # circular imports)
        from ..graphulator_para import (
            EXPORT_RESCALE_DEFAULTS,
            LIVE_PARAMS,
            SETTINGS_PARAMS,
            sync_dialog_defaults_from_config,
        )
        from ..para_core.settings_manager import get_settings_manager
        from ..settings_dialog import make_style_sample_scene
        self._EXPORT_RESCALE_DEFAULTS = EXPORT_RESCALE_DEFAULTS
        self._sync_dialog_defaults_from_config = sync_dialog_defaults_from_config

        super().__init__(
            parent,
            config_module=config,
            params_table=SETTINGS_PARAMS,
            settings_manager=get_settings_manager(),
            auto_refresh_tabs=('S-Parameter Plot',),
            live_params=LIVE_PARAMS,
            sample_scene=make_style_sample_scene(config),
        )

    # ---- Export-rescale parameters live on the window, not the config ----

    def _get_current_value(self, param_name):
        if param_name in self._EXPORT_RESCALE_DEFAULTS:
            return self.graphulator.export_rescale.get(
                param_name, self._EXPORT_RESCALE_DEFAULTS.get(param_name))
        return super()._get_current_value(param_name)

    def _set_current_value(self, param_name, value):
        if param_name in self._EXPORT_RESCALE_DEFAULTS:
            self.graphulator.export_rescale[param_name] = value
        # Also always set in config module for consistency
        super()._set_current_value(param_name, value)

    # ---- App-specific tabs ----

    def _extra_tabs(self):
        self._build_color_palettes_tab()
        self._build_keyboard_shortcuts_tab()

    def _build_color_palettes_tab(self):
        """Build the Color Palettes tab with independent node and trace palettes."""
        tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        layout = QVBoxLayout()
        scroll_widget.setLayout(layout)
        scroll.setWidget(scroll_widget)

        tab_layout = QVBoxLayout()
        tab_layout.addWidget(scroll)
        tab.setLayout(tab_layout)

        # Get current colors from config (may have been loaded from user settings)
        current_node_colors = getattr(config, 'MYCOLORS', config.MYCOLORS)
        current_trace_colors = getattr(config, 'SPARAMS_TRACE_COLORS', config.SPARAMS_TRACE_COLORS)

        # Store default colors for reset (from config module originals)
        default_node_colors = {
            'RED': 'indianred', 'BLUE': 'cornflowerblue', 'GREEN': 'darkseagreen',
            'ORANGE': 'sandybrown', 'PURPLE': 'mediumpurple', 'TEAL': 'mediumaquamarine',
            'WHITE': 'white', 'BLACK': 'black', 'GRAY': 'gray',
            'LIGHTGRAY': 'lightgray', 'DARKGRAY': 'darkgray',
        }
        default_trace_colors = [
            'indianred', 'cornflowerblue', 'darkseagreen', 'sandybrown',
            'mediumpurple', 'mediumaquamarine', 'gray',
        ]

        # Node Colors palette widget
        self._node_palette = ColorPaletteWidget("Node Colors", default_node_colors)
        self._node_palette.set_colors(current_node_colors)
        self._node_palette.palette_changed.connect(self._on_palette_changed)
        layout.addWidget(self._node_palette)

        layout.addSpacing(20)

        # Trace Colors palette widget
        self._trace_palette = ColorPaletteWidget("S-Parameter Trace Colors", default_trace_colors)
        self._trace_palette.set_colors(current_trace_colors)
        self._trace_palette.palette_changed.connect(self._on_palette_changed)
        layout.addWidget(self._trace_palette)

        layout.addStretch()

        self.tab_widget.addTab(tab, "Color Palettes")

    def _build_keyboard_shortcuts_tab(self):
        """Build the Keyboard Shortcuts tab for customizing shortcuts."""
        if not hasattr(self.graphulator, 'shortcut_manager'):
            return  # Skip if shortcut manager not initialized

        self._shortcut_editor = ShortcutEditorWidget(
            self.graphulator.shortcut_manager, self
        )
        self._shortcut_editor.shortcuts_modified.connect(self._on_shortcuts_modified)
        self.tab_widget.addTab(self._shortcut_editor, "Keyboard Shortcuts")

    def _on_shortcuts_modified(self):
        """Handle shortcut modifications."""
        # Shortcuts are already applied by the editor; nothing else to do.
        pass

    def _on_palette_changed(self):
        """Handle palette changes - apply and refresh."""
        config.MYCOLORS = self._node_palette.get_colors()
        config.SPARAMS_TRACE_COLORS = self._trace_palette.get_colors()
        self._refresh_ui()

    # ---- App-specific dialog behavior ----

    def _extra_original_values(self):
        return {
            'MYCOLORS': dict(config.MYCOLORS),
            'SPARAMS_TRACE_COLORS': list(config.SPARAMS_TRACE_COLORS),
        }

    def _refresh_ui(self):
        """Refresh the Paragraphulator UI after settings change."""
        g = self.graphulator
        # Update node_radius from config (in case DEFAULT_NODE_RADIUS changed)
        g.node_radius = config.DEFAULT_NODE_RADIUS
        # Edge styles are derived from the conjugation convention; recompute
        # them so CONJ_SAME/DIFF_EDGE_STYLE changes take effect immediately
        for node in g.nodes:
            g._update_edge_styles_for_node(node)
        # Update main plot
        g._update_plot()
        # Update S-parameter plot if in scattering mode
        if self.graphulator.scattering_mode:
            try:
                g = self.graphulator
                has_data = hasattr(g, 'sparams_data') and g.sparams_data is not None
                has_canvas = hasattr(g, 'sparams_canvas') and g.sparams_canvas is not None
                if has_data and has_canvas:
                    g._plot_sparams()
            except Exception as e:
                logger.error("Settings: Error refreshing S-param plot: %s", e)

    def _after_apply(self):
        # Sync dialog defaults so new nodes/edges use updated settings
        self._sync_dialog_defaults_from_config()
        # Reset last_node_props so continuous duplicate mode uses new defaults
        self.graphulator._reset_last_node_props_to_defaults()

    def _extra_cancel_restore(self, original_values):
        if 'MYCOLORS' in original_values:
            config.MYCOLORS = original_values['MYCOLORS']
            if hasattr(self, '_node_palette'):
                self._node_palette.set_colors(original_values['MYCOLORS'])
        if 'SPARAMS_TRACE_COLORS' in original_values:
            config.SPARAMS_TRACE_COLORS = original_values['SPARAMS_TRACE_COLORS']
            if hasattr(self, '_trace_palette'):
                self._trace_palette.set_colors(original_values['SPARAMS_TRACE_COLORS'])

    def _extra_reset(self):
        if hasattr(self, '_node_palette'):
            self._node_palette._reset_to_defaults()
        if hasattr(self, '_trace_palette'):
            self._trace_palette._reset_to_defaults()
        if hasattr(self.graphulator, 'shortcut_manager'):
            self.graphulator.shortcut_manager.reset_to_defaults()

    def _extra_settings(self):
        settings = {}
        if hasattr(self, '_node_palette'):
            settings['MYCOLORS'] = self._node_palette.get_colors()
        if hasattr(self, '_trace_palette'):
            settings['SPARAMS_TRACE_COLORS'] = self._trace_palette.get_colors()
        # Add shortcut bindings (only non-default ones)
        if hasattr(self.graphulator, 'shortcut_manager'):
            shortcut_bindings = self.graphulator.shortcut_manager.export_bindings()
            if shortcut_bindings:
                settings['shortcuts'] = shortcut_bindings
        return settings
