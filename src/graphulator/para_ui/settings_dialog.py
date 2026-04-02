"""
Settings dialog and color palette widgets for paragraphulator.

This module contains the SettingsDialog and ColorPaletteWidget classes.
"""

from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QScrollArea, QFormLayout, QSpinBox, QComboBox,
    QCheckBox, QLineEdit, QColorDialog, QListWidget, QListWidgetItem,
    QMessageBox
)
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QIcon, QPixmap

from .. import graphulator_para_config as config
from .widgets import FineControlSpinBox
from .shortcut_editor import ShortcutEditorWidget


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
            except:
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


class SettingsDialog(QDialog):
    """Comprehensive Settings dialog for configuring graphulator parameters.

    Features:
    - QTabWidget with organized parameter categories
    - Session state tracking for Cancel functionality
    - Persistent storage via JSON file for "Save as Defaults"
    - Flexible parameter registration for easy expansion
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.graphulator = parent
        self.setWindowTitle("Settings")
        self.setMinimumWidth(550)
        self.setMinimumHeight(650)

        # Import settings constants from main module (delayed to avoid circular imports)
        from ..graphulator_para import (
            SETTINGS_PARAMS, EXPORT_RESCALE_DEFAULTS,
            save_user_settings, delete_user_settings, USER_SETTINGS_FILE,
            _get_original_config_value, sync_dialog_defaults_from_config
        )
        self._SETTINGS_PARAMS = SETTINGS_PARAMS
        self._EXPORT_RESCALE_DEFAULTS = EXPORT_RESCALE_DEFAULTS
        self._save_user_settings = save_user_settings
        self._delete_user_settings = delete_user_settings
        self._USER_SETTINGS_FILE = USER_SETTINGS_FILE
        self._get_original_config_value = _get_original_config_value
        self._sync_dialog_defaults_from_config = sync_dialog_defaults_from_config

        # Store original values when dialog opens (for Cancel functionality)
        self._original_values = {}
        self._store_original_values()

        # Widget references for accessing values
        self._widgets = {}

        # Create main layout
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # Create tab widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Build tabs from SETTINGS_PARAMS
        self._build_tabs()

        # Create button layout
        button_layout = QHBoxLayout()

        # Reset to Defaults button
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setAutoDefault(False)  # Prevent Return key from activating
        reset_btn.setToolTip("Restore all parameters to their original code values")
        reset_btn.clicked.connect(self._on_reset_defaults)
        button_layout.addWidget(reset_btn)

        # Save as Defaults button
        save_defaults_btn = QPushButton("Save as Defaults")
        save_defaults_btn.setAutoDefault(False)  # Prevent Return key from activating
        save_defaults_btn.setToolTip("Save current settings to ~/.graphulator/settings.json")
        save_defaults_btn.clicked.connect(self._on_save_defaults)
        button_layout.addWidget(save_defaults_btn)

        button_layout.addStretch()

        main_layout.addLayout(button_layout)

        # Standard dialog buttons
        dialog_buttons = QHBoxLayout()

        apply_btn = QPushButton("Apply")
        apply_btn.setAutoDefault(False)  # Prevent Return key from activating
        apply_btn.setToolTip("Apply changes and keep dialog open")
        apply_btn.clicked.connect(self._on_apply)
        dialog_buttons.addWidget(apply_btn)

        ok_btn = QPushButton("OK")
        ok_btn.setAutoDefault(False)  # Prevent Return key from activating
        ok_btn.setToolTip("Apply changes and close dialog")
        ok_btn.clicked.connect(self._on_ok)
        dialog_buttons.addWidget(ok_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setAutoDefault(False)  # Prevent Return key from activating
        cancel_btn.setToolTip("Revert changes and close dialog")
        cancel_btn.clicked.connect(self._on_cancel)
        dialog_buttons.addWidget(cancel_btn)

        main_layout.addLayout(dialog_buttons)

    def _store_original_values(self):
        """Store current values when dialog opens for Cancel functionality."""
        self._original_values = {}
        for tab_name, params in self._SETTINGS_PARAMS.items():
            for param_name, display_name, param_type, min_val, max_val, step in params:
                self._original_values[param_name] = self._get_current_value(param_name)
        # Store palette values
        self._original_values['MYCOLORS'] = dict(config.MYCOLORS)
        self._original_values['SPARAMS_TRACE_COLORS'] = list(config.SPARAMS_TRACE_COLORS)

    def _get_current_value(self, param_name):
        """Get the current value of a parameter."""
        # Check if it's an export rescale param (stored in graphulator instance)
        if param_name in self._EXPORT_RESCALE_DEFAULTS:
            return self.graphulator.export_rescale.get(param_name,
                   self._EXPORT_RESCALE_DEFAULTS.get(param_name))
        # Otherwise get from config module
        return getattr(config, param_name, None)

    def _set_current_value(self, param_name, value):
        """Set the current value of a parameter."""
        # Check if it's an export rescale param (stored in graphulator instance)
        if param_name in self._EXPORT_RESCALE_DEFAULTS:
            self.graphulator.export_rescale[param_name] = value
        # Also always set in config module for consistency
        if hasattr(config, param_name):
            setattr(config, param_name, value)

    def _build_tabs(self):
        """Build UI tabs from SETTINGS_PARAMS definition."""
        for tab_name, params in self._SETTINGS_PARAMS.items():
            tab = QWidget()
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll_widget = QWidget()
            form_layout = QFormLayout()
            scroll_widget.setLayout(form_layout)
            scroll.setWidget(scroll_widget)

            tab_layout = QVBoxLayout()
            tab_layout.addWidget(scroll)
            tab.setLayout(tab_layout)

            # Determine if this tab should auto-refresh (S-Parameter Plot tab)
            auto_refresh = (tab_name == 'S-Parameter Plot')

            for param_name, display_name, param_type, min_val, max_val, step in params:
                current_value = self._get_current_value(param_name)
                widget = self._create_widget(param_name, param_type, current_value,
                                            min_val, max_val, step,
                                            auto_refresh=auto_refresh)
                form_layout.addRow(f"{display_name}:", widget)
                self._widgets[param_name] = (widget, param_type)

            self.tab_widget.addTab(tab, tab_name)

        # Add Color Palettes tab
        self._build_color_palettes_tab()

        # Add Keyboard Shortcuts tab
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
        # Shortcuts are already applied by the editor
        # Just mark that we have unsaved changes
        pass

    def _on_palette_changed(self):
        """Handle palette changes - apply and refresh."""
        # Apply palette changes to config
        config.MYCOLORS = self._node_palette.get_colors()
        config.SPARAMS_TRACE_COLORS = self._trace_palette.get_colors()
        self._refresh_ui()

    def _create_widget(self, param_name, param_type, current_value, min_val, max_val, step,
                       auto_refresh=False):
        """Create appropriate widget for parameter type.

        Args:
            auto_refresh: If True, changes will auto-apply and refresh the UI immediately.
        """
        if param_type == 'float':
            widget = FineControlSpinBox()
            widget.setMinimum(min_val)
            widget.setMaximum(max_val)
            widget.setSingleStep(step)
            # Determine decimal places from step
            if step < 0.01:
                widget.setDecimals(3)
            elif step < 0.1:
                widget.setDecimals(2)
            else:
                widget.setDecimals(2)
            if current_value is not None:
                widget.setValue(current_value)
            # Connect auto-refresh if enabled
            if auto_refresh:
                widget.valueChanged.connect(
                    lambda val, p=param_name: self._on_value_changed(p, val))
            return widget

        elif param_type == 'int':
            widget = QSpinBox()
            widget.setMinimum(int(min_val))
            widget.setMaximum(int(max_val))
            widget.setSingleStep(int(step))
            if current_value is not None:
                widget.setValue(int(current_value))
            # Connect auto-refresh if enabled
            if auto_refresh:
                widget.valueChanged.connect(
                    lambda val, p=param_name: self._on_value_changed(p, val))
            return widget

        elif param_type == 'color':
            # Create a button that shows color picker
            widget = QPushButton()
            widget.setAutoDefault(False)  # Prevent Return key from activating
            widget.setMinimumWidth(100)
            if current_value:
                widget.setStyleSheet(f"background-color: {current_value}; color: black;")
                widget.setText(current_value)
            else:
                widget.setText("Select Color")
            widget.clicked.connect(lambda checked, w=widget, p=param_name, ar=auto_refresh:
                                   self._on_color_button_clicked(w, p, ar))
            return widget

        elif param_type == 'bool':
            widget = QCheckBox()
            if current_value is not None:
                widget.setChecked(bool(current_value))
            # Connect auto-refresh if enabled
            if auto_refresh:
                widget.stateChanged.connect(
                    lambda state, p=param_name: self._on_value_changed(p, bool(state)))
            return widget

        elif param_type == 'dropdown':
            widget = QComboBox()
            # Handle different option formats
            options = min_val  # min_val holds the options for dropdown type
            if options == 'MYCOLORS_KEYS':
                # Special case: use MYCOLORS keys as options
                options = list(config.MYCOLORS.keys())

            # Build combo items
            if options and isinstance(options[0], tuple):
                # Options are (display_name, value) tuples
                for display_name, value in options:
                    widget.addItem(display_name, value)
                # Set current value by finding matching data
                if current_value is not None:
                    for i in range(widget.count()):
                        if widget.itemData(i) == current_value:
                            widget.setCurrentIndex(i)
                            break
            else:
                # Options are simple values (display = value)
                for value in options:
                    widget.addItem(str(value), value)
                if current_value is not None:
                    idx = widget.findData(current_value)
                    if idx >= 0:
                        widget.setCurrentIndex(idx)

            # Connect auto-refresh if enabled
            if auto_refresh:
                widget.currentIndexChanged.connect(
                    lambda idx, w=widget, p=param_name: self._on_value_changed(p, w.currentData()))
            return widget

        else:
            # Default to line edit
            widget = QLineEdit()
            if current_value is not None:
                widget.setText(str(current_value))
            return widget

    def _on_color_button_clicked(self, button, param_name, auto_refresh=False):
        """Handle color button click - open color picker."""
        current_color = self._get_current_value(param_name)
        color = QColorDialog.getColor(QColor(current_color) if current_color else QColor('white'),
                                      self, f"Select {param_name}")
        if color.isValid():
            color_name = color.name()
            button.setStyleSheet(f"background-color: {color_name}; color: black;")
            button.setText(color_name)
            # Auto-refresh if enabled
            if auto_refresh:
                self._on_value_changed(param_name, color_name)

    def _on_value_changed(self, param_name, value):
        """Handle value change - apply immediately and refresh UI."""
        self._set_current_value(param_name, value)
        self._refresh_ui()

    def _get_widget_value(self, param_name):
        """Get the current value from a widget."""
        if param_name not in self._widgets:
            return None

        widget, param_type = self._widgets[param_name]

        if param_type in ('float', 'int'):
            return widget.value()
        elif param_type == 'color':
            text = widget.text()
            return text if text != "Select Color" else None
        elif param_type == 'bool':
            return widget.isChecked()
        elif param_type == 'dropdown':
            return widget.currentData()
        else:
            return widget.text()

    def _set_widget_value(self, param_name, value):
        """Set a widget's displayed value."""
        if param_name not in self._widgets:
            return

        widget, param_type = self._widgets[param_name]

        if param_type == 'float':
            widget.setValue(float(value) if value is not None else 0.0)
        elif param_type == 'int':
            widget.setValue(int(value) if value is not None else 0)
        elif param_type == 'color':
            if value:
                widget.setStyleSheet(f"background-color: {value}; color: black;")
                widget.setText(value)
            else:
                widget.setStyleSheet("")
                widget.setText("Select Color")
        elif param_type == 'bool':
            widget.setChecked(bool(value) if value is not None else False)
        elif param_type == 'dropdown':
            if value is not None:
                idx = widget.findData(value)
                if idx >= 0:
                    widget.setCurrentIndex(idx)
        else:
            widget.setText(str(value) if value is not None else "")

    def _apply_all_values(self):
        """Apply all widget values to the config/graphulator."""
        for param_name in self._widgets:
            value = self._get_widget_value(param_name)
            if value is not None:
                self._set_current_value(param_name, value)

    def _refresh_ui(self):
        """Refresh the Graphulator UI after settings change."""
        # Update node_radius from config (in case DEFAULT_NODE_RADIUS changed)
        self.graphulator.node_radius = config.DEFAULT_NODE_RADIUS
        # Update main plot
        self.graphulator._update_plot()
        # Update S-parameter plot if in scattering mode
        # Note: sparams_data and sparams_canvas are on Graphulator, not PropertiesPanel
        if self.graphulator.scattering_mode:
            try:
                g = self.graphulator
                has_data = hasattr(g, 'sparams_data') and g.sparams_data is not None
                has_canvas = hasattr(g, 'sparams_canvas') and g.sparams_canvas is not None
                if has_data and has_canvas:
                    g._plot_sparams()
            except Exception as e:
                print(f"Settings: Error refreshing S-param plot: {e}")

    def _on_apply(self):
        """Apply button - apply changes, refresh UI, keep dialog open."""
        self._apply_all_values()
        # Sync dialog defaults so new nodes/edges use updated settings
        self._sync_dialog_defaults_from_config()
        # Reset last_node_props so continuous duplicate mode uses new defaults
        self.graphulator._reset_last_node_props_to_defaults()
        self._refresh_ui()

    def _on_ok(self):
        """OK button - apply changes, refresh UI, close dialog."""
        self._apply_all_values()
        # Sync dialog defaults so new nodes/edges use updated settings
        self._sync_dialog_defaults_from_config()
        # Reset last_node_props so continuous duplicate mode uses new defaults
        self.graphulator._reset_last_node_props_to_defaults()
        self._refresh_ui()
        self.accept()

    def _on_cancel(self):
        """Cancel button - revert to original values, close dialog."""
        # Restore original values
        for param_name, original_value in self._original_values.items():
            if param_name == 'MYCOLORS':
                config.MYCOLORS = original_value
                if hasattr(self, '_node_palette'):
                    self._node_palette.set_colors(original_value)
            elif param_name == 'SPARAMS_TRACE_COLORS':
                config.SPARAMS_TRACE_COLORS = original_value
                if hasattr(self, '_trace_palette'):
                    self._trace_palette.set_colors(original_value)
            elif original_value is not None:
                self._set_current_value(param_name, original_value)
        self._refresh_ui()
        self.reject()

    def _on_reset_defaults(self):
        """Reset to Defaults button - restore original config.py values."""
        # Delete user settings file
        self._delete_user_settings()

        # Restore original values from config module
        for tab_name, params in self._SETTINGS_PARAMS.items():
            for param_name, display_name, param_type, min_val, max_val, step in params:
                original_value = self._get_original_config_value(param_name)
                if original_value is not None:
                    self._set_current_value(param_name, original_value)
                    self._set_widget_value(param_name, original_value)

        # Reset palettes to defaults
        if hasattr(self, '_node_palette'):
            self._node_palette._reset_to_defaults()
        if hasattr(self, '_trace_palette'):
            self._trace_palette._reset_to_defaults()

        # Reset shortcuts to defaults
        if hasattr(self.graphulator, 'shortcut_manager'):
            self.graphulator.shortcut_manager.reset_to_defaults()

        self._refresh_ui()
        QMessageBox.information(self, "Reset Complete",
                               "All settings have been reset to their original defaults.")

    def _on_save_defaults(self):
        """Save as Defaults button - save current settings to JSON file."""
        # Apply current widget values first
        self._apply_all_values()

        # Collect all settings
        settings = {}
        for param_name in self._widgets:
            value = self._get_widget_value(param_name)
            if value is not None:
                settings[param_name] = value

        # Add palette settings
        if hasattr(self, '_node_palette'):
            settings['MYCOLORS'] = self._node_palette.get_colors()
        if hasattr(self, '_trace_palette'):
            settings['SPARAMS_TRACE_COLORS'] = self._trace_palette.get_colors()

        # Add shortcut bindings (only non-default ones)
        if hasattr(self.graphulator, 'shortcut_manager'):
            shortcut_bindings = self.graphulator.shortcut_manager.export_bindings()
            if shortcut_bindings:
                settings['shortcuts'] = shortcut_bindings

        # Save to file
        if self._save_user_settings(settings):
            QMessageBox.information(self, "Settings Saved",
                                   f"Settings saved to:\n{self._USER_SETTINGS_FILE}")
        else:
            QMessageBox.warning(self, "Save Failed",
                               "Could not save settings to file.")
