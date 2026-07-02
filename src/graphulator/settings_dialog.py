"""App-agnostic Settings dialog base for Graphulator and Paragraphulator.

The dialog is generated from a declarative parameter table::

    {tab_name: [(param_name, display_name, type, min, max, step), ...]}

where ``type`` is one of ``'float' | 'int' | 'color' | 'bool' | 'dropdown'``
(for dropdowns, ``min`` holds the options: a list of values, a list of
``(display, value)`` tuples, or the sentinel ``'MYCOLORS_KEYS'``).

All app specifics are injected: the config module the parameters live on,
the parameter table, the (namespaced) SettingsManager for Save/Reset, an
``on_applied`` refresh callback, the set of ``live_params`` that apply to
the running app debounced as the user tweaks them (Cancel reverts), and an
optional ``sample_scene`` callable that draws a live preview of pending
values on an embedded canvas. Subclasses add app-only tabs and behavior via
the ``_extra_*`` hooks.
"""

import logging

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .para_ui.widgets import FineControlSpinBox

logger = logging.getLogger(__name__)

# Debounce for the preview pane and live-apply (ms)
PREVIEW_DEBOUNCE_MS = 150


class SampleSceneCanvas(FigureCanvasQTAgg):
    """Small embedded canvas that renders a canned preview scene.

    ``draw_fn(ax, values)`` receives the axes and the dialog's pending
    widget values (param name -> value) and draws the sample. It must not
    touch pyplot global state (use only the provided axes).
    """

    def __init__(self, draw_fn, width=4.2, height=2.2):
        self.fig = Figure(figsize=(width, height))
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self._draw_fn = draw_fn
        self.setMinimumHeight(int(height * 72))

    def refresh(self, values):
        self.ax.clear()
        try:
            self._draw_fn(self.ax, values)
        except Exception:
            logger.exception("Settings preview scene failed to draw")
        self.ax.set_aspect('equal')
        self.ax.set_axis_off()
        self.fig.tight_layout(pad=0.2)
        self.draw_idle()


def make_style_sample_scene(config_module):
    """Build a ``sample_scene`` callable previewing the styling defaults.

    Draws a canned scene — a normal node, a conjugated node (per the
    convention settings), a bidirectional edge with arrowheads, and a
    self-loop — from the dialog's pending widget values, falling back to the
    config module for anything the dialog doesn't expose. Uses only the
    provided axes (no pyplot state).
    """
    import matplotlib.patches as mpatches

    from . import graph_primitives as gp

    def draw(ax, values):
        def val(name, default=None):
            v = values.get(name)
            if v is None:
                v = getattr(config_module, name, default)
            return v

        node_color = val('DEFAULT_NODE_COLOR', 'indianred')
        label_color = val('DEFAULT_NODE_LABEL_COLOR', 'white')
        R = 0.6
        arrow_kwargs = dict(
            arrowstyle=val('DEFAULT_EDGE_ARROWSTYLE', 'open'),
            arrowscale=float(val('DEFAULT_EDGE_ARROWSCALE', 1.0)),
            arrowopenang=float(val('ARROWHEAD_OPEN_ANGLE', 60)),
        )

        # Edge between the two nodes. The sample pair is (A, A*) — opposite
        # conjugation — so apps with an edge-style convention (Paragraphulator)
        # preview it here; otherwise a loopy edge shows the arrowheads.
        edge_style = val('CONJ_DIFF_EDGE_STYLE', 'loopy')
        gp.edge(ax=ax, nodexy=[(-1.8, 0), (1.8, 0)], nodeR=[R, R],
                style=edge_style, whichedges='both', label=[None, None],
                loopkwargs=dict(lw=2.0, arrowlength=0.3, **arrow_kwargs))

        # Self-loop on the normal node
        gp.selfloop(ax=ax, nodecent=(-1.8, 0), R=R * 1.2, loopR=R * 6,
                    baseangle=180, dtheta=-34, arrowlength=R / 2 * 2.25 / 4,
                    lw=1.8, **arrow_kwargs)

        # Normal node
        ax.add_patch(mpatches.Circle((-1.8, 0), R, facecolor=node_color,
                                     edgecolor='none', zorder=10))
        ax.text(-1.8, 0, 'A', ha='center', va='center', fontsize=13,
                color=label_color, fontweight='bold', zorder=11)

        # Conjugated node per the convention settings
        conj_scale = float(val('CONJ_LABEL_SCALE', 0.92))
        if val('CONJ_NODE_FILL_MODE', 'dimmed') == 'transparent':
            ax.add_patch(mpatches.Circle((1.8, 0), R, facecolor='none',
                                         edgecolor=node_color, linewidth=2.0,
                                         zorder=10))
            conj_label_color = node_color
        else:
            ax.add_patch(mpatches.Circle(
                (1.8, 0), R, facecolor=node_color, edgecolor='none',
                alpha=float(val('CONJ_NODE_FILL_ALPHA', 0.5)), zorder=10))
            conj_label_color = label_color
        ax.text(1.8, 0, 'A*', ha='center', va='center',
                fontsize=13 * conj_scale, color=conj_label_color,
                fontweight='bold', zorder=11)

        ax.set_xlim(-4.6, 3.1)
        ax.set_ylim(-1.7, 1.7)

    return draw


class SettingsDialogBase(QDialog):
    """Table-driven Settings dialog with Apply/OK/Cancel semantics.

    Features:
    - QTabWidget with organized parameter categories
    - Session state tracking for Cancel functionality
    - Persistent storage via the injected SettingsManager ("Save as Defaults")
    - Optional live preview pane and debounced live-apply parameters
    """

    def __init__(self, parent=None, *, config_module, params_table,
                 settings_manager, on_applied=None, live_params=(),
                 sample_scene=None, auto_refresh_tabs=(),
                 window_title="Settings"):
        super().__init__(parent)
        self.graphulator = parent
        self._config = config_module
        self._params_table = params_table
        self._manager = settings_manager
        self._on_applied = on_applied
        self._live_params = set(live_params)
        self._sample_scene = sample_scene
        self._auto_refresh_tabs = set(auto_refresh_tabs)

        self.setWindowTitle(window_title)
        self.setMinimumWidth(550)
        self.setMinimumHeight(650)

        # Store original values when dialog opens (for Cancel functionality)
        self._original_values = {}
        self._store_original_values()

        # Widget references for accessing values
        self._widgets = {}

        # Debounced preview / live-apply plumbing
        self._pending_live = set()
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(PREVIEW_DEBOUNCE_MS)
        self._preview_timer.timeout.connect(self._refresh_sample)
        self._live_timer = QTimer(self)
        self._live_timer.setSingleShot(True)
        self._live_timer.setInterval(PREVIEW_DEBOUNCE_MS)
        self._live_timer.timeout.connect(self._flush_live)

        # Create main layout
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # Create tab widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Build tabs from the params table (+ subclass extras)
        self._build_tabs()

        # Optional live preview pane
        self._sample_canvas = None
        if self._sample_scene is not None:
            preview_box = QGroupBox("Preview")
            preview_layout = QVBoxLayout()
            preview_box.setLayout(preview_layout)
            self._sample_canvas = SampleSceneCanvas(self._sample_scene)
            preview_layout.addWidget(self._sample_canvas)
            main_layout.addWidget(preview_box)
            self._refresh_sample()

        # Create button layout
        button_layout = QHBoxLayout()

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setAutoDefault(False)  # Prevent Return key from activating
        reset_btn.setToolTip("Restore all parameters to their original code values")
        reset_btn.clicked.connect(self._on_reset_defaults)
        button_layout.addWidget(reset_btn)

        save_defaults_btn = QPushButton("Save as Defaults")
        save_defaults_btn.setAutoDefault(False)
        save_defaults_btn.setToolTip(
            f"Save current settings to {self._manager.settings_file}")
        save_defaults_btn.clicked.connect(self._on_save_defaults)
        button_layout.addWidget(save_defaults_btn)

        self._add_extra_buttons(button_layout)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        # Standard dialog buttons
        dialog_buttons = QHBoxLayout()

        apply_btn = QPushButton("Apply")
        apply_btn.setAutoDefault(False)
        apply_btn.setToolTip("Apply changes and keep dialog open")
        apply_btn.clicked.connect(self._on_apply)
        dialog_buttons.addWidget(apply_btn)

        ok_btn = QPushButton("OK")
        ok_btn.setAutoDefault(False)
        ok_btn.setToolTip("Apply changes and close dialog")
        ok_btn.clicked.connect(self._on_ok)
        dialog_buttons.addWidget(ok_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setAutoDefault(False)
        cancel_btn.setToolTip("Revert changes and close dialog")
        cancel_btn.clicked.connect(self._on_cancel)
        dialog_buttons.addWidget(cancel_btn)

        main_layout.addLayout(dialog_buttons)

    # ---- Subclass hooks ----

    def _extra_original_values(self):
        """Additional (name -> value) snapshots for Cancel (e.g. palettes)."""
        return {}

    def _extra_tabs(self):
        """Add app-specific tabs after the table-driven ones."""

    def _extra_settings(self):
        """Additional entries for Save as Defaults (e.g. palettes, shortcuts)."""
        return {}

    def _extra_cancel_restore(self, original_values):
        """Restore app-specific state on Cancel."""

    def _extra_reset(self):
        """Reset app-specific state on Reset to Defaults."""

    def _after_apply(self):
        """App-specific work after values are applied (Apply/OK)."""

    def _add_extra_buttons(self, button_layout):
        """Add app-specific buttons to the bottom-left button row."""

    # ---- Values ----

    def _store_original_values(self):
        """Store current values when dialog opens for Cancel functionality."""
        self._original_values = {}
        for _tab_name, params in self._params_table.items():
            for param_name, *_rest in params:
                self._original_values[param_name] = self._get_current_value(param_name)
        self._original_values.update(self._extra_original_values())

    def _get_current_value(self, param_name):
        """Get the current value of a parameter (config module attribute)."""
        return getattr(self._config, param_name, None)

    def _set_current_value(self, param_name, value):
        """Set the current value of a parameter on the config module."""
        if hasattr(self._config, param_name):
            setattr(self._config, param_name, value)

    # ---- UI construction ----

    def _build_tabs(self):
        """Build UI tabs from the params table, then subclass extras."""
        for tab_name, params in self._params_table.items():
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

            auto_refresh = tab_name in self._auto_refresh_tabs

            for param_name, display_name, param_type, min_val, max_val, step in params:
                current_value = self._get_current_value(param_name)
                widget = self._create_widget(param_name, param_type, current_value,
                                             min_val, max_val, step,
                                             auto_refresh=auto_refresh)
                form_layout.addRow(f"{display_name}:", widget)
                self._widgets[param_name] = (widget, param_type)

            self.tab_widget.addTab(tab, tab_name)

        self._extra_tabs()

    def _create_widget(self, param_name, param_type, current_value, min_val, max_val, step,
                       auto_refresh=False):
        """Create appropriate widget for parameter type.

        Args:
            auto_refresh: If True, changes auto-apply and refresh the UI
                immediately (legacy per-tab behavior).
        """
        if param_type == 'float':
            widget = FineControlSpinBox()
            widget.setMinimum(min_val)
            widget.setMaximum(max_val)
            widget.setSingleStep(step)
            widget.setDecimals(3 if step < 0.01 else 2)
            if current_value is not None:
                widget.setValue(current_value)
            if auto_refresh:
                widget.valueChanged.connect(
                    lambda val, p=param_name: self._on_value_changed(p, val))
            widget.valueChanged.connect(
                lambda _val, p=param_name: self._notify_changed(p))
            return widget

        elif param_type == 'int':
            widget = QSpinBox()
            widget.setMinimum(int(min_val))
            widget.setMaximum(int(max_val))
            widget.setSingleStep(int(step))
            if current_value is not None:
                widget.setValue(int(current_value))
            if auto_refresh:
                widget.valueChanged.connect(
                    lambda val, p=param_name: self._on_value_changed(p, val))
            widget.valueChanged.connect(
                lambda _val, p=param_name: self._notify_changed(p))
            return widget

        elif param_type == 'color':
            # Create a button that shows color picker
            widget = QPushButton()
            widget.setAutoDefault(False)
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
            if auto_refresh:
                widget.stateChanged.connect(
                    lambda state, p=param_name: self._on_value_changed(p, bool(state)))
            widget.stateChanged.connect(
                lambda _state, p=param_name: self._notify_changed(p))
            return widget

        elif param_type == 'dropdown':
            widget = QComboBox()
            options = min_val  # min_val holds the options for dropdown type
            if options == 'MYCOLORS_KEYS':
                options = list(self._config.MYCOLORS.keys())

            if options and isinstance(options[0], tuple):
                for display_name, value in options:
                    widget.addItem(display_name, value)
                if current_value is not None:
                    for i in range(widget.count()):
                        if widget.itemData(i) == current_value:
                            widget.setCurrentIndex(i)
                            break
            else:
                for value in options:
                    widget.addItem(str(value), value)
                if current_value is not None:
                    idx = widget.findData(current_value)
                    if idx >= 0:
                        widget.setCurrentIndex(idx)

            if auto_refresh:
                widget.currentIndexChanged.connect(
                    lambda idx, w=widget, p=param_name: self._on_value_changed(p, w.currentData()))
            widget.currentIndexChanged.connect(
                lambda _idx, p=param_name: self._notify_changed(p))
            return widget

        else:
            widget = QLineEdit()
            if current_value is not None:
                widget.setText(str(current_value))
            widget.textChanged.connect(
                lambda _text, p=param_name: self._notify_changed(p))
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
            if auto_refresh:
                self._on_value_changed(param_name, color_name)
            self._notify_changed(param_name)

    def _on_value_changed(self, param_name, value):
        """Handle auto-refresh value change - apply immediately and refresh UI."""
        self._set_current_value(param_name, value)
        self._refresh_ui()

    # ---- Live preview / live apply ----

    def _notify_changed(self, param_name):
        """A widget changed: schedule preview refresh and live-apply."""
        if self._sample_scene is not None:
            self._preview_timer.start()
        if param_name in self._live_params:
            self._pending_live.add(param_name)
            self._live_timer.start()

    def _flush_live(self):
        """Debounced live-apply of convention parameters to the running app."""
        for param_name in self._pending_live:
            self._set_current_value(param_name, self._get_widget_value(param_name))
        self._pending_live.clear()
        self._refresh_ui()

    def _refresh_sample(self):
        """Redraw the preview pane from pending widget values."""
        if self._sample_canvas is None:
            return
        values = {p: self._get_widget_value(p) for p in self._widgets}
        self._sample_canvas.refresh(values)

    # ---- Widget value plumbing ----

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
        """Apply all widget values to the config/app."""
        for param_name in self._widgets:
            value = self._get_widget_value(param_name)
            if value is not None:
                self._set_current_value(param_name, value)

    def _refresh_ui(self):
        """Refresh the owning application after settings change."""
        if self._on_applied is not None:
            self._on_applied()

    # ---- Button handlers ----

    def _on_apply(self):
        """Apply button - apply changes, refresh UI, keep dialog open."""
        self._apply_all_values()
        self._after_apply()
        self._refresh_ui()

    def _on_ok(self):
        """OK button - apply changes, refresh UI, close dialog."""
        self._apply_all_values()
        self._after_apply()
        self._refresh_ui()
        self.accept()

    def _on_cancel(self):
        """Cancel button - revert to original values, close dialog."""
        handled = set()
        self._extra_cancel_restore(self._original_values)
        for param_name, original_value in self._original_values.items():
            if param_name in handled:
                continue
            if param_name in self._widgets and original_value is not None:
                self._set_current_value(param_name, original_value)
        self._refresh_ui()
        self.reject()

    def _on_reset_defaults(self):
        """Reset to Defaults button - restore original config values."""
        # Clear this app's saved settings (namespace-scoped)
        self._manager.delete()

        # Restore original values from the config module
        for _tab_name, params in self._params_table.items():
            for param_name, *_rest in params:
                original_value = self._manager.get_original_config_value(param_name)
                if original_value is not None:
                    self._set_current_value(param_name, original_value)
                    self._set_widget_value(param_name, original_value)

        self._extra_reset()
        self._refresh_ui()
        QMessageBox.information(self, "Reset Complete",
                                "All settings have been reset to their original defaults.")

    def _on_save_defaults(self):
        """Save as Defaults button - save current settings via the manager."""
        # Apply current widget values first
        self._apply_all_values()

        settings = {}
        for param_name in self._widgets:
            value = self._get_widget_value(param_name)
            if value is not None:
                settings[param_name] = value
        settings.update(self._extra_settings())

        if self._manager.save(settings):
            QMessageBox.information(self, "Settings Saved",
                                    f"Settings saved to:\n{self._manager.settings_file}")
        else:
            QMessageBox.warning(self, "Save Failed",
                                "Could not save settings to file.")
