"""
Graphulator - Interactive Graph Drawing Tool (Qt Version)
Advanced GUI for creating coupled mode theory graphs using PySide6
"""

import logging
import sys
import time
import json
import os
from datetime import datetime
from pathlib import Path
import numpy as np

logger = logging.getLogger(__name__)

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QDialog, QLabel, QLineEdit,
                               QComboBox, QPushButton, QDialogButtonBox, QCheckBox,
                               QSplitter, QGroupBox, QSlider, QSpinBox, QDoubleSpinBox,
                               QFormLayout, QColorDialog, QMenu, QTextEdit, QFileDialog,
                               QMessageBox, QMenuBar, QTabWidget, QScrollArea)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QKeySequence, QShortcut, QColor, QCursor, QAction, QIcon

import matplotlib
matplotlib.use('QtAgg')
# Use MathText instead of LaTeX for faster rendering
matplotlib.rcParams['text.usetex'] = False
matplotlib.rcParams['mathtext.fontset'] = 'stix'  # STIX fonts look similar to LaTeX
matplotlib.rcParams['font.family'] = 'STIXGeneral'

# Suppress matplotlib warnings about adjusting limits for aspect ratio
import warnings
warnings.filterwarnings('ignore', message='.*fixed.*limits.*aspect.*', category=UserWarning)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.patches as patches

# Import modules (relative imports for package)
from . import graph_primitives as gp
from . import graphulator_config as config
from .common_window import GraphWindowCommonMixin
from .para_core.graph_state import capture_graph_state
from .para_core.settings_manager import get_settings_manager
from .para_rendering.label_cache import LabelPathCache
from .settings_dialog import SettingsDialogBase, make_style_sample_scene


EXPORT_RESCALE_DEFAULTS = {
    'NODELABELSCALE': 1.000,
    'SLCC': 0.650,
    'SELFLOOP_LABELSCALE': 0.140,
    'SLLW': 6.000,
    'SLSC': 0.900,
    'SLLNOFFSET': (0.0, 0.0),
    'SELFLOOP_LABELNUDGE_SCALE': 1.100,
    'EDGEFONTSCALE': 0.850,
    'EDGELWSCALE': 2.700,
    'EDGELABELOFFSET': 1.000,
    'GUI_SELFLOOP_LABEL_SCALE': 1.300,
    'EXPORT_SELFLOOP_LABEL_DISTANCE': 1.000,
}

class NodeInputDialog(QDialog):
    """Dialog for inputting node properties"""

    # Class variables to persist last choices
    last_color = 'RED'
    last_node_size = 'Medium'
    last_label_size = 'Large'
    last_conj = False

    def __init__(self, default_label='A', default_color='BLUE', parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Node")
        self.setModal(True)

        # Store result
        self.result = None

        # Create layout
        layout = QVBoxLayout()

        # Label input
        label_layout = QHBoxLayout()
        label_layout.addWidget(QLabel("Label:"))
        self.label_edit = QLineEdit(default_label)
        self.label_edit.setFocus()
        self.label_edit.selectAll()
        label_layout.addWidget(self.label_edit)
        layout.addLayout(label_layout)

        # Color selection
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Color:"))
        self.color_combo = QComboBox()

        # Add colors to combo box with visual colors
        for color_key, color_value in config.MYCOLORS.items():
            self.color_combo.addItem(f"  {color_key}", color_key)
            idx = self.color_combo.count() - 1
            self.color_combo.setItemData(idx, QColor(color_value), Qt.BackgroundRole)

        # Set to last used color
        try:
            last_idx = list(config.MYCOLORS.keys()).index(self.last_color)
            self.color_combo.setCurrentIndex(last_idx)
        except:
            self.color_combo.setCurrentIndex(0)

        color_layout.addWidget(self.color_combo)
        layout.addLayout(color_layout)

        # Node size selection
        node_size_layout = QHBoxLayout()
        node_size_layout.addWidget(QLabel("Node Size:"))
        self.node_size_combo = QComboBox()
        self.node_size_combo.addItems(['Small', 'Medium', 'Large', 'X-Large'])
        self.node_size_combo.setCurrentText(self.last_node_size)
        node_size_layout.addWidget(self.node_size_combo)
        layout.addLayout(node_size_layout)

        # Label size selection
        label_size_layout = QHBoxLayout()
        label_size_layout.addWidget(QLabel("Label Size:"))
        self.label_size_combo = QComboBox()
        self.label_size_combo.addItems(['Small', 'Medium', 'Large', 'X-Large'])
        self.label_size_combo.setCurrentText(self.last_label_size)
        label_size_layout.addWidget(self.label_size_combo)
        layout.addLayout(label_size_layout)

        # Conjugation checkbox
        conj_layout = QHBoxLayout()
        conj_layout.addWidget(QLabel("Conjugated:"))
        self.conj_checkbox = QCheckBox()
        self.conj_checkbox.setChecked(self.last_conj)
        conj_layout.addWidget(self.conj_checkbox)
        layout.addLayout(conj_layout)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

        # Make compact
        self.setFixedSize(320, 230)

    def accept(self):
        """Handle OK button"""
        label = self.label_edit.text().strip()
        if not label:
            label = self.label_edit.placeholderText()

        color_key = self.color_combo.currentData()
        node_size = self.node_size_combo.currentText()
        label_size = self.label_size_combo.currentText()
        conj = self.conj_checkbox.isChecked()

        # Persist choices for next node
        NodeInputDialog.last_color = color_key
        NodeInputDialog.last_node_size = node_size
        NodeInputDialog.last_label_size = label_size
        NodeInputDialog.last_conj = conj

        # Size multipliers
        size_map = {'Small': 0.6, 'Medium': 1.0, 'Large': 1.4, 'X-Large': 1.8}

        self.result = {
            'label': label,
            'color_key': color_key,
            'color': config.MYCOLORS[color_key],
            'node_size_mult': size_map[node_size],
            'label_size_mult': size_map[label_size],
            'conj': conj
        }
        super().accept()

    def get_result(self):
        """Return the dialog result"""
        return self.result


class EdgeInputDialog(QDialog):
    """Dialog for inputting edge properties"""

    # Class variables to persist last choices
    last_linewidth = 'Medium'
    last_label_size = 'Medium'
    last_label_offset = 'Medium'
    last_style = 'loopy'
    last_direction = 'both'
    last_use_labels = False  # Default to no edge labels
    last_flip_labels = False  # Default to not flipped

    def __init__(self, node1_label='A', node2_label='B', is_self_loop=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Self-Loop" if is_self_loop else "Add Edge")
        self.setModal(True)

        # Store result
        self.result = None
        self.is_self_loop = is_self_loop

        # Create layout
        layout = QVBoxLayout()

        # Edge labels checkbox
        labels_checkbox_layout = QHBoxLayout()
        labels_checkbox_layout.addWidget(QLabel("Edge Labels:"))
        self.use_labels_checkbox = QCheckBox()
        self.use_labels_checkbox.setChecked(EdgeInputDialog.last_use_labels)
        self.use_labels_checkbox.stateChanged.connect(self._toggle_label_widgets)
        labels_checkbox_layout.addWidget(self.use_labels_checkbox)
        layout.addLayout(labels_checkbox_layout)

        # Label 1 input (forward direction, positive offset)
        label1_layout = QHBoxLayout()
        label1_layout.addWidget(QLabel("Label 1 (+):"))
        self.label1_input = QLineEdit()
        # Default label: \beta_{kj} for edges (from node2 to node1), empty for self-loops
        if not is_self_loop:
            default_label1 = rf'\beta_{{{node2_label}{node1_label}}}'
        else:
            default_label1 = ''
        self.label1_input.setText(default_label1)
        label1_layout.addWidget(self.label1_input)
        layout.addLayout(label1_layout)

        # Label 2 input (backward direction, negative offset) - only for non-self-loops
        if not is_self_loop:
            label2_layout = QHBoxLayout()
            label2_layout.addWidget(QLabel("Label 2 (-):"))
            self.label2_input = QLineEdit()
            default_label2 = rf'\beta_{{{node1_label}{node2_label}}}'
            self.label2_input.setText(default_label2)
            label2_layout.addWidget(self.label2_input)
            layout.addLayout(label2_layout)
        else:
            # For self-loops, create a dummy label2 input (not shown)
            self.label2_input = QLineEdit()
            self.label2_input.setText('')

        # Linewidth dropdown
        lw_layout = QHBoxLayout()
        lw_layout.addWidget(QLabel("Line Width:"))
        self.lw_combo = QComboBox()
        lw_options = ['Thin', 'Medium', 'Thick', 'X-Thick']
        self.lw_combo.addItems(lw_options)
        self.lw_combo.setCurrentText(EdgeInputDialog.last_linewidth)
        lw_layout.addWidget(self.lw_combo)
        layout.addLayout(lw_layout)

        # Label font size dropdown
        label_size_layout = QHBoxLayout()
        label_size_layout.addWidget(QLabel("Label Size:"))
        self.label_size_combo = QComboBox()
        label_size_options = ['Small', 'Medium', 'Large', 'X-Large', 'XX-Large']
        self.label_size_combo.addItems(label_size_options)
        self.label_size_combo.setCurrentText(EdgeInputDialog.last_label_size)
        label_size_layout.addWidget(self.label_size_combo)
        layout.addLayout(label_size_layout)

        # Label offset dropdown
        label_offset_layout = QHBoxLayout()
        label_offset_layout.addWidget(QLabel("Label Offset:"))
        self.label_offset_combo = QComboBox()
        label_offset_options = ['Close', 'Medium', 'Far']
        self.label_offset_combo.addItems(label_offset_options)
        self.label_offset_combo.setCurrentText(EdgeInputDialog.last_label_offset)
        label_offset_layout.addWidget(self.label_offset_combo)
        layout.addLayout(label_offset_layout)

        # Style dropdown (only for non-self-loops)
        if not is_self_loop:
            style_layout = QHBoxLayout()
            style_layout.addWidget(QLabel("Style:"))
            self.style_combo = QComboBox()
            style_options = ['loopy', 'single', 'double']
            self.style_combo.addItems(style_options)
            self.style_combo.setCurrentText(EdgeInputDialog.last_style)
            style_layout.addWidget(self.style_combo)
            layout.addLayout(style_layout)
        else:
            self.style_combo = None

        # Self-loop specific controls
        if is_self_loop:
            # Angle dropdown
            angle_layout = QHBoxLayout()
            angle_layout.addWidget(QLabel("Angle:"))
            self.angle_combo = QComboBox()
            angle_options = ['0° (Right)', '45° (Up-Right)', '90° (Up)', '135° (Up-Left)',
                           '180° (Left)', '225° (Down-Left)', '270° (Down)', '315° (Down-Right)']
            self.angle_combo.addItems(angle_options)
            self.angle_combo.setCurrentIndex(0)  # Default to 0° (Right)
            angle_layout.addWidget(self.angle_combo)
            layout.addLayout(angle_layout)

            # Scale dropdown
            scale_layout = QHBoxLayout()
            scale_layout.addWidget(QLabel("Loop Size:"))
            self.scale_combo = QComboBox()
            scale_options = ['Small (0.7x)', 'Medium (1.0x)', 'Large (1.3x)', 'X-Large (1.6x)']
            self.scale_combo.addItems(scale_options)
            self.scale_combo.setCurrentIndex(1)  # Default to Medium
            scale_layout.addWidget(self.scale_combo)
            layout.addLayout(scale_layout)

            # Flip checkbox
            flip_loop_layout = QHBoxLayout()
            flip_loop_layout.addWidget(QLabel("Flip Direction:"))
            self.flip_loop_checkbox = QCheckBox()
            self.flip_loop_checkbox.setChecked(False)
            flip_loop_layout.addWidget(self.flip_loop_checkbox)
            layout.addLayout(flip_loop_layout)
        else:
            self.angle_combo = None
            self.scale_combo = None
            self.flip_loop_checkbox = None

        # Direction dropdown (only for non-self-loops)
        if not is_self_loop:
            dir_layout = QHBoxLayout()
            dir_layout.addWidget(QLabel("Direction:"))
            self.dir_combo = QComboBox()
            dir_options = ['both', 'forward', 'backward']
            self.dir_combo.addItems(dir_options)
            self.dir_combo.setCurrentText(EdgeInputDialog.last_direction)
            dir_layout.addWidget(self.dir_combo)
            layout.addLayout(dir_layout)

            # Loop theta spinbox (for loopy edge curvature)
            looptheta_layout = QHBoxLayout()
            looptheta_layout.addWidget(QLabel("Loop Theta:"))
            self.looptheta_spinbox = QSpinBox()
            self.looptheta_spinbox.setMinimum(-180)
            self.looptheta_spinbox.setMaximum(180)
            self.looptheta_spinbox.setSuffix("°")
            self.looptheta_spinbox.setValue(30)  # Default value
            looptheta_layout.addWidget(self.looptheta_spinbox)
            layout.addLayout(looptheta_layout)
            logger.debug("EdgeInputDialog - looptheta spinbox created")
        else:
            self.dir_combo = None
            self.looptheta_spinbox = None

        # Flip labels checkbox
        flip_layout = QHBoxLayout()
        flip_layout.addWidget(QLabel("Flip Labels:"))
        self.flip_labels_checkbox = QCheckBox()
        self.flip_labels_checkbox.setChecked(EdgeInputDialog.last_flip_labels)
        flip_layout.addWidget(self.flip_labels_checkbox)
        layout.addLayout(flip_layout)

        # OK/Cancel buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

        # Initialize widget states based on checkbox
        self._toggle_label_widgets()

    def _toggle_label_widgets(self):
        """Enable/disable label-related widgets based on checkbox"""
        enabled = self.use_labels_checkbox.isChecked()

        # Toggle label input fields
        self.label1_input.setEnabled(enabled)
        self.label2_input.setEnabled(enabled)

        # Toggle label size and offset combos
        self.label_size_combo.setEnabled(enabled)
        self.label_offset_combo.setEnabled(enabled)

    def accept(self):
        """Store the input values when OK is clicked"""
        use_labels = self.use_labels_checkbox.isChecked()

        # If labels disabled, use empty strings
        if use_labels:
            label1 = self.label1_input.text()
            label2 = self.label2_input.text()
        else:
            label1 = ''
            label2 = ''

        linewidth = self.lw_combo.currentText()
        label_size = self.label_size_combo.currentText()
        label_offset = self.label_offset_combo.currentText()
        style = self.style_combo.currentText() if self.style_combo else 'loopy'
        direction = self.dir_combo.currentText() if self.dir_combo else 'both'
        flip_labels = self.flip_labels_checkbox.isChecked()

        # Self-loop specific parameters
        if self.is_self_loop and self.angle_combo and self.scale_combo and self.flip_loop_checkbox:
            angle_text = self.angle_combo.currentText()
            selfloopangle = int(angle_text.split('°')[0])  # Extract angle from "0° (Right)"

            scale_text = self.scale_combo.currentText()
            scale_map = {'Small (0.7x)': 0.7, 'Medium (1.0x)': 1.0, 'Large (1.3x)': 1.3, 'X-Large (1.6x)': 1.6}
            selfloopscale = scale_map[scale_text]

            flip_loop = self.flip_loop_checkbox.isChecked()
        else:
            selfloopangle = 0
            selfloopscale = 1.0
            flip_loop = False

        # Persist choices for next edge
        EdgeInputDialog.last_use_labels = use_labels
        EdgeInputDialog.last_linewidth = linewidth
        EdgeInputDialog.last_label_size = label_size
        EdgeInputDialog.last_label_offset = label_offset
        if self.style_combo:
            EdgeInputDialog.last_style = style
        EdgeInputDialog.last_flip_labels = flip_labels
        if not self.is_self_loop:
            EdgeInputDialog.last_direction = direction

        # Linewidth multipliers (for figsize=12, medium=5.5)
        lw_map = {'Thin': 1.0, 'Medium': 1.5, 'Thick': 2.0, 'X-Thick': 2.5}

        # Label font size multipliers (for figsize=12, medium=50)
        label_size_map = {'Small': 1.0, 'Medium': 1.4, 'Large': 1.8, 'X-Large': 2.5, 'XX-Large': 3.0}

        # Label offset multipliers (for figsize=12, medium=2.3)
        label_offset_map = {'Close': 0.5, 'Medium': 0.8, 'Far': 1.2}

        # Get looptheta value from spinbox (if not self-loop)
        looptheta = 30  # Default
        if not self.is_self_loop and hasattr(self, 'looptheta_spinbox') and self.looptheta_spinbox:
            looptheta = self.looptheta_spinbox.value()
            logger.debug(f"EdgeInputDialog - looptheta value from spinbox: {looptheta}")
        else:
            logger.debug(f"EdgeInputDialog - using default looptheta: {looptheta}, is_self_loop={self.is_self_loop}")

        self.result = {
            'label1': label1,
            'label2': label2,
            'linewidth_mult': lw_map[linewidth],
            'label_size_mult': label_size_map[label_size],
            'label_offset_mult': label_offset_map[label_offset],
            'style': style,
            'direction': direction,
            'flip_labels': flip_labels,
            'looptheta': looptheta,
            'selfloopangle': selfloopangle,
            'selfloopscale': selfloopscale,
            'flip': flip_loop,
            'arrowlengthsc': 1.0  # Default arrow length scale
        }
        super().accept()

    def get_result(self):
        """Return the dialog result"""
        return self.result


def sync_dialog_defaults_from_config(window=None):
    """Sync dialog memory and derived values from the config module.

    New-node appearance flows through NodeInputDialog's remembered class
    attributes and the window's last_node_props (continuous duplicate mode),
    not through config lookups at creation time. Call this after settings
    change (Apply / Reset / startup load) so the changed defaults actually
    reach newly placed nodes.
    """
    config.DEFAULT_NODE_COLOR = config.MYCOLORS.get(
        config.DEFAULT_NODE_COLOR_KEY, config.DEFAULT_NODE_COLOR)
    NodeInputDialog.last_color = config.DEFAULT_NODE_COLOR_KEY
    EdgeInputDialog.last_style = config.DEFAULT_EDGE_STYLE
    if window is not None:
        # Continuous modes rebuild their templates from the new defaults
        window.last_node_props = None
        window.last_edge_props = None


class PropertiesPanel(QWidget):
    """Properties panel for selected objects"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.graphulator = parent
        self.current_object = None  # Currently displayed object (node or edge)
        self.current_type = None  # 'node', 'edge', or None
        self.displayed_single = None  # Object whose property widgets are currently built (avoids rebuilding/focus-loss while editing)
        self.displayed_multi = None  # Selection signature whose multi-edit widgets are currently built (avoids rebuilding/focus-loss while editing)

        # Create main layout
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # Create tab widget
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs, stretch=1)

        # Tab 1: Object Properties
        properties_tab = QWidget()
        properties_tab_layout = QVBoxLayout()
        properties_tab.setLayout(properties_tab_layout)

        # Title label
        self.title_label = QLabel("No Selection")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        properties_tab_layout.addWidget(self.title_label)

        # Properties container (will be replaced based on selection)
        self.properties_widget = QWidget()
        self.properties_layout = QVBoxLayout()
        self.properties_widget.setLayout(self.properties_layout)
        properties_tab_layout.addWidget(self.properties_widget)

        properties_tab_layout.addStretch()

        self.tabs.addTab(properties_tab, "Properties")

        # Tab 2: Export Scaling
        self._create_scaling_tab()

        # Lower section: Help
        help_group = QGroupBox("Help")
        help_group_layout = QVBoxLayout()
        help_group.setLayout(help_group_layout)

        # Create scrollable text area for help
        self.help_text = QTextEdit()
        self.help_text.setReadOnly(True)
        self.help_text.setStyleSheet("font-family: monospace; font-size: 9px;")

        help_content = """<b>Controls:</b><br>
• g: Place single node<br>
• Shift+G: Continuous node mode<br>
• Ctrl+G: Auto-increment mode<br>
• e: Place single edge<br>
• Ctrl+E: Continuous edge mode<br>
• c: Conjugation mode<br>
• Esc: Exit mode / Clear selection<br>
• r: Rotate grid (45° / 30°)<br>
• t: Toggle grid (square/triangular)<br>
• a: Auto-fit view<br>
• +/-: Zoom in/out<br>
<br>
<b>Selection & Editing:</b><br>
• Left click: Select / drag node<br>
• Right click: Color/type menu<br>
• Shift+click: Multi-select<br>
• Click+drag: Selection window<br>
• Double-click: Edit properties<br>
• Up/Down: Node/edge size<br>
• Left/Right: Label size<br>
• Shift+arrows: Nudge labels<br>
• Ctrl+A: Select all<br>
• Ctrl+C/X/V: Copy/cut/paste<br>
• Ctrl+Z: Undo<br>
• Ctrl+Shift+Z / Ctrl+Y: Redo<br>
• Ctrl+,: Settings (defaults & conventions)<br>
• Ctrl+R: Rotate nodes 15° CCW<br>
• Ctrl+Shift+R: Rotate nodes 15° CW<br>
• d or Delete: Delete<br>
• f: Flip edge labels<br>
• Shift+F: Edge rotation mode<br>
<br>
<b>Other:</b><br>
• Ctrl+Shift+E: Export code<br>
• Ctrl+Shift+Delete: Clear all<br>
• Ctrl+L: Toggle LaTeX<br>
• Ctrl+Q: Quit"""

        self.help_text.setHtml(help_content)
        help_group_layout.addWidget(self.help_text)

        main_layout.addWidget(help_group, stretch=1)

        # Set minimum width
        self.setMinimumWidth(250)

    def _create_scaling_tab(self):
        """Create the export scaling parameters tab"""
        scaling_tab = QWidget()
        scaling_layout = QVBoxLayout()
        scaling_tab.setLayout(scaling_layout)

        # Add title
        title = QLabel("Export Scaling Parameters")
        title.setStyleSheet("font-weight: bold; font-size: 11px;")
        scaling_layout.addWidget(title)

        desc = QLabel("Tune these to match GUI and exported code rendering:")
        desc.setStyleSheet("font-size: 9px; color: gray;")
        desc.setWordWrap(True)
        scaling_layout.addWidget(desc)

        # Create scroll area for parameters
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QFormLayout()
        scroll_widget.setLayout(scroll_layout)
        scroll.setWidget(scroll_widget)

        # Store spinboxes for later access
        self.scaling_spinboxes = {}

        # Define parameters with descriptions
        param_info = {
            'GUI_SELFLOOP_LABEL_SCALE': ('GUI Self-loop Label Distance', 0.1, 5.0, 0.1),
            'EXPORT_SELFLOOP_LABEL_DISTANCE': ('Export Self-loop Label Distance', 0.1, 5.0, 0.1),
            'NODELABELSCALE': ('Node Label Scale', 0.1, 2.0, 0.05),
            'SELFLOOP_LABELSCALE': ('Self-loop Label Size', 0.1, 2.0, 0.05),
            'SLLW': ('Self-loop Linewidth', 0.1, 8.0, 0.1),
            'SLSC': ('Self-loop Scale', 0.1, 3.0, 0.1),
            'SELFLOOP_LABELNUDGE_SCALE': ('Self-loop Label Nudge Scale', 0.1, 3.0, 0.1),
            'EDGEFONTSCALE': ('Edge Label Font Scale', 0.1, 5.0, 0.1),
            'EDGELWSCALE': ('Edge Linewidth Scale', 0.1, 5.0, 0.1),
            'EDGELABELOFFSET': ('Edge Label Offset', 0.1, 3.0, 0.05),
        }

        # Create spinbox for each parameter
        for key, (label, min_val, max_val, step) in param_info.items():
            spinbox = QDoubleSpinBox()
            spinbox.setMinimum(min_val)
            spinbox.setMaximum(max_val)
            spinbox.setSingleStep(step)
            spinbox.setValue(self.graphulator.export_rescale.get(key, 1.0))
            spinbox.setDecimals(2)

            # Connect to update function
            spinbox.valueChanged.connect(lambda val, k=key: self._update_scaling_param(k, val))

            scroll_layout.addRow(f"{label}:", spinbox)
            self.scaling_spinboxes[key] = spinbox

        scaling_layout.addWidget(scroll)

        # Add preset management buttons
        preset_layout = QHBoxLayout()

        save_preset_btn = QPushButton("Save Preset...")
        save_preset_btn.clicked.connect(self._save_scaling_preset)
        preset_layout.addWidget(save_preset_btn)

        load_preset_btn = QPushButton("Load Preset...")
        load_preset_btn.clicked.connect(self._load_scaling_preset)
        preset_layout.addWidget(load_preset_btn)

        scaling_layout.addLayout(preset_layout)

        # Add set as defaults button
        set_defaults_btn = QPushButton("Set Current as Defaults")
        set_defaults_btn.clicked.connect(self._set_current_as_defaults)
        set_defaults_btn.setToolTip("Update the default values to match current settings")
        scaling_layout.addWidget(set_defaults_btn)

        # Add reset button
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_scaling_params)
        scaling_layout.addWidget(reset_btn)

        # Add apply and export buttons
        btn_layout = QHBoxLayout()
        apply_btn = QPushButton("Apply to GUI")
        apply_btn.clicked.connect(lambda: self.graphulator._update_plot())
        btn_layout.addWidget(apply_btn)

        export_btn = QPushButton("Export Code")
        export_btn.clicked.connect(lambda: self.graphulator._export_code())
        btn_layout.addWidget(export_btn)

        scaling_layout.addLayout(btn_layout)

        scaling_layout.addStretch()

        self.tabs.addTab(scaling_tab, "Export Scaling")

    def _update_scaling_param(self, key, value):
        """Update a scaling parameter"""
        self.graphulator.export_rescale[key] = value
        # If it's the GUI parameter, update the plot immediately
        if key == 'GUI_SELFLOOP_LABEL_SCALE':
            self.graphulator._update_plot()

    def _reset_scaling_params(self):
        """Reset all scaling parameters to defaults"""
        # defaults = {
        #     'NODELABELSCALE': 0.55,
        #     'SLCC': 0.65,
        #     'SELFLOOP_LABELSCALE': 0.65,
        #     'SLLW': 1.2,
        #     'SLSC': 1.0,
        #     'SLLNOFFSET': (0.0, 0.0),
        #     'SELFLOOP_LABELNUDGE_SCALE': 1.0,
        #     'EDGEFONTSCALE': 1.8,
        #     'EDGELWSCALE': 2.6,
        #     'EDGELABELOFFSET': 1.05,
        #     'GUI_SELFLOOP_LABEL_SCALE': 1.5,
        #     'EXPORT_SELFLOOP_LABEL_DISTANCE': 1.0,
        # }

        defaults = EXPORT_RESCALE_DEFAULTS

        for key, value in defaults.items():
            self.graphulator.export_rescale[key] = value
            if key in self.scaling_spinboxes:
                self.scaling_spinboxes[key].setValue(value)

        self.graphulator._update_plot()

    def _set_current_as_defaults(self):
        """Update the default values in the code to match current settings"""
        current_values = self.graphulator.export_rescale.copy()

        # Create a formatted string for the new defaults
        lines = []
        lines.append("New default values to update in your code:\n")
        lines.append("self.export_rescale = {")
        for key, value in current_values.items():
            if isinstance(value, tuple):
                lines.append(f"    '{key}': {value},")
            elif isinstance(value, float):
                lines.append(f"    '{key}': {value:.3f},")
            else:
                lines.append(f"    '{key}': {value},")
        lines.append("}")

        message = "\n".join(lines)

        # Show a dialog with the values
        dialog = QDialog(self)
        dialog.setWindowTitle("Default Values")
        dialog.setMinimumWidth(500)
        dialog.setMinimumHeight(400)

        layout = QVBoxLayout()

        info_label = QLabel("Copy these values to update the defaults in graphulator_qt.py\n"
                           "(around line 952 in the __init__ method):")
        layout.addWidget(info_label)

        text_edit = QTextEdit()
        text_edit.setPlainText(message)
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.setLayout(layout)
        dialog.exec()

    def _save_scaling_preset(self):
        """Save current scaling parameters to a JSON file"""
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Scaling Preset",
            "",
            "JSON Files (*.json);;All Files (*)"
        )

        if filename:
            try:
                preset_data = {
                    'version': '1.0',
                    'description': 'Graphulator export scaling preset',
                    'parameters': self.graphulator.export_rescale.copy()
                }

                with open(filename, 'w') as f:
                    json.dump(preset_data, f, indent=2)

                QMessageBox.information(
                    self,
                    "Preset Saved",
                    f"Scaling preset saved to:\n{filename}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error Saving Preset",
                    f"Failed to save preset:\n{str(e)}"
                )

    def _load_scaling_preset(self):
        """Load scaling parameters from a JSON file"""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Load Scaling Preset",
            "",
            "JSON Files (*.json);;All Files (*)"
        )

        if filename:
            try:
                with open(filename, 'r') as f:
                    preset_data = json.load(f)

                # Validate preset data
                if 'parameters' not in preset_data:
                    raise ValueError("Invalid preset file: missing 'parameters' key")

                parameters = preset_data['parameters']

                # Update the export_rescale dictionary and UI spinboxes
                for key, value in parameters.items():
                    if key in self.graphulator.export_rescale:
                        self.graphulator.export_rescale[key] = value
                        if key in self.scaling_spinboxes:
                            self.scaling_spinboxes[key].setValue(value)

                # Update the GUI
                self.graphulator._update_plot()

                QMessageBox.information(
                    self,
                    "Preset Loaded",
                    f"Scaling preset loaded from:\n{filename}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error Loading Preset",
                    f"Failed to load preset:\n{str(e)}"
                )

    def clear_properties(self):
        """Clear all property widgets and layouts"""
        # Remove all items (widgets and layouts) from properties layout
        while self.properties_layout.count():
            item = self.properties_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # Recursively clear and delete nested layouts
                self._clear_layout(item.layout())

    def _clear_layout(self, layout):
        """Recursively clear a layout"""
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    self._clear_layout(item.layout())

    def show_node_properties(self, node):
        """Show properties for a node"""
        self.clear_properties()
        self.current_object = node
        self.current_type = 'node'
        self.displayed_multi = None
        self.title_label.setText(f"Node: {node['label']}")

        # Create form layout for properties
        form = QFormLayout()

        # Label
        self.label_edit = QLineEdit(node['label'])
        self.label_edit.textChanged.connect(lambda: self._update_node_label())
        form.addRow("Label:", self.label_edit)

        # Color
        color_btn = QPushButton("Choose Color")
        color_btn.clicked.connect(lambda: self._choose_node_color())
        form.addRow("Color:", color_btn)

        # Node size
        self.node_size_slider = QSlider(Qt.Horizontal)
        self.node_size_slider.setMinimum(50)
        self.node_size_slider.setMaximum(200)
        self.node_size_slider.setValue(int(node.get('node_size_mult', 1.0) * 100))
        self.node_size_slider.valueChanged.connect(lambda: self._update_node_size())
        self.node_size_label = QLabel(f"{node.get('node_size_mult', 1.0):.3f}x")
        size_layout = QHBoxLayout()
        size_layout.addWidget(self.node_size_slider)
        size_layout.addWidget(self.node_size_label)
        form.addRow("Node Size:", size_layout)

        # Label size
        self.label_size_slider = QSlider(Qt.Horizontal)
        self.label_size_slider.setMinimum(50)
        self.label_size_slider.setMaximum(200)
        self.label_size_slider.setValue(int(node.get('label_size_mult', 1.0) * 100))
        self.label_size_slider.valueChanged.connect(lambda: self._update_label_size())
        self.label_size_label = QLabel(f"{node.get('label_size_mult', 1.0):.3f}x")
        label_size_layout = QHBoxLayout()
        label_size_layout.addWidget(self.label_size_slider)
        label_size_layout.addWidget(self.label_size_label)
        form.addRow("Label Size:", label_size_layout)

        # Conjugation
        self.conj_checkbox = QCheckBox()
        self.conj_checkbox.setChecked(node.get('conj', False))
        self.conj_checkbox.stateChanged.connect(lambda: self._update_conjugation())
        form.addRow("Conjugate:", self.conj_checkbox)

        # Outline
        self.outline_checkbox = QCheckBox()
        self.outline_checkbox.setChecked(node.get('outline_enabled', False))
        self.outline_checkbox.stateChanged.connect(lambda: self._update_outline_enabled())
        form.addRow("Outline:", self.outline_checkbox)

        outline_color_btn = QPushButton("Choose Outline Color")
        outline_color_btn.clicked.connect(lambda: self._choose_outline_color())
        form.addRow("Outline Color:", outline_color_btn)

        self.outline_width_spin = QDoubleSpinBox()
        self.outline_width_spin.setRange(0.5, 10.0)
        self.outline_width_spin.setDecimals(1)
        self.outline_width_spin.setSingleStep(0.5)
        self.outline_width_spin.setValue(node.get('outline_width', config.DEFAULT_NODE_OUTLINE_WIDTH))
        self.outline_width_spin.valueChanged.connect(lambda: self._update_outline_width())
        form.addRow("Outline Width:", self.outline_width_spin)

        self.outline_alpha_spin = QDoubleSpinBox()
        self.outline_alpha_spin.setRange(0.0, 1.0)
        self.outline_alpha_spin.setDecimals(2)
        self.outline_alpha_spin.setSingleStep(0.05)
        self.outline_alpha_spin.setValue(node.get('outline_alpha', config.DEFAULT_NODE_OUTLINE_ALPHA))
        self.outline_alpha_spin.valueChanged.connect(lambda: self._update_outline_alpha())
        form.addRow("Outline Alpha:", self.outline_alpha_spin)

        self.properties_layout.addLayout(form)
        self.displayed_single = node

    def show_edge_properties(self, edge):
        """Show properties for an edge or self-loop"""
        self.clear_properties()
        self.current_object = edge
        self.current_type = 'edge'
        self.displayed_multi = None
        from_label = edge['from_node']['label']
        to_label = edge['to_node']['label']
        is_self_loop = edge.get('is_self_loop', False)

        if is_self_loop:
            self.title_label.setText(f"Self-Loop: {from_label}")
        else:
            self.title_label.setText(f"Edge: {from_label} → {to_label}")

        # Create form layout for properties
        form = QFormLayout()

        if is_self_loop:
            # Self-loop specific properties
            # Label
            self.edge_label1_edit = QLineEdit(edge.get('label1', ''))
            self.edge_label1_edit.textChanged.connect(lambda: self._update_edge_labels())
            form.addRow("Label:", self.edge_label1_edit)

            # Angle spinbox with compass label
            angle_layout = QHBoxLayout()
            self.selfloop_angle_spinbox = QSpinBox()
            self.selfloop_angle_spinbox.setMinimum(0)
            self.selfloop_angle_spinbox.setMaximum(355)
            self.selfloop_angle_spinbox.setSingleStep(config.SELFLOOP_ANGLE_KEYBOARD_INCREMENT)
            self.selfloop_angle_spinbox.setWrapping(True)
            selfloopangle = edge.get('selfloopangle', 0)
            self.selfloop_angle_spinbox.setValue(selfloopangle)
            self.selfloop_angle_spinbox.setSuffix("°")
            self.selfloop_angle_spinbox.setToolTip("Ctrl+Left/Right (when self-loop selected)")
            self.selfloop_angle_spinbox.valueChanged.connect(lambda val: self._update_selfloop_angle_spinbox(val))
            angle_layout.addWidget(self.selfloop_angle_spinbox)
            self.selfloop_angle_compass_label = QLabel(self._compass_direction(selfloopangle))
            angle_layout.addWidget(self.selfloop_angle_compass_label)
            form.addRow("Angle:", angle_layout)

            # Angle pinned checkbox
            self.selfloop_angle_pinned_checkbox = QCheckBox()
            self.selfloop_angle_pinned_checkbox.setChecked(edge.get('angle_pinned', False))
            self.selfloop_angle_pinned_checkbox.setToolTip("When pinned, angle won't auto-adjust on node drag")
            self.selfloop_angle_pinned_checkbox.stateChanged.connect(lambda: self._update_selfloop_angle_pinned())
            form.addRow("Angle Pinned:", self.selfloop_angle_pinned_checkbox)

            # Loop Size
            self.selfloop_scale_combo = QComboBox()
            self.selfloop_scale_combo.addItems(['Small (0.7x)', 'Medium (1.0x)', 'Large (1.3x)', 'X-Large (1.6x)'])
            selfloopscale = edge.get('selfloopscale', 1.0)
            scale_map_reverse = {0.7: 0, 1.0: 1, 1.3: 2, 1.6: 3}
            closest_scale = min(scale_map_reverse.keys(), key=lambda x: abs(x - selfloopscale))
            self.selfloop_scale_combo.setCurrentIndex(scale_map_reverse[closest_scale])
            self.selfloop_scale_combo.currentTextChanged.connect(lambda: self._update_selfloop_scale())
            form.addRow("Loop Size:", self.selfloop_scale_combo)

            # Flip
            self.selfloop_flip_checkbox = QCheckBox()
            self.selfloop_flip_checkbox.setChecked(edge.get('flip', False))
            self.selfloop_flip_checkbox.stateChanged.connect(lambda: self._update_selfloop_flip())
            form.addRow("Flip Direction:", self.selfloop_flip_checkbox)

            # Linewidth
            self.linewidth_combo = QComboBox()
            self.linewidth_combo.addItems(['Thin', 'Medium', 'Thick', 'X-Thick'])
            lw_map = {1.0: 'Thin', 1.5: 'Medium', 2.0: 'Thick', 2.5: 'X-Thick'}
            current_lw = edge.get('linewidth_mult', 1.5)
            closest_lw = min(lw_map.keys(), key=lambda k: abs(k - current_lw))
            self.linewidth_combo.setCurrentText(lw_map[closest_lw])
            self.linewidth_combo.currentTextChanged.connect(lambda: self._update_edge_linewidth())
            form.addRow("Line Width:", self.linewidth_combo)

            # Arrowhead style (scale via the existing arrowlengthsc semantics)
            self.arrowstyle_combo = QComboBox()
            self.arrowstyle_combo.addItems(['open', 'filled', 'stealth'])
            self.arrowstyle_combo.setCurrentText(edge.get('arrowstyle', 'open'))
            self.arrowstyle_combo.currentTextChanged.connect(lambda: self._update_edge_arrowstyle())
            form.addRow("Arrowhead:", self.arrowstyle_combo)

            # Self-loop label background color
            label_bg_btn = QPushButton("Set Label BG" if edge.get('label_bgcolor') else "No Label BG")
            label_bg_btn.clicked.connect(lambda: self._choose_edge_label_bgcolor())
            form.addRow("Label BG:", label_bg_btn)
            if edge.get('label_bgcolor'):
                clear_label_bg_btn = QPushButton("Clear")
                clear_label_bg_btn.clicked.connect(lambda: self._clear_edge_label_bgcolor())
                form.addRow("", clear_label_bg_btn)
        else:
            # Regular edge properties
            # Labels
            self.edge_label1_edit = QLineEdit(edge.get('label1', ''))
            self.edge_label1_edit.textChanged.connect(lambda: self._update_edge_labels())
            form.addRow("Label 1 (+):", self.edge_label1_edit)

            self.edge_label2_edit = QLineEdit(edge.get('label2', ''))
            self.edge_label2_edit.textChanged.connect(lambda: self._update_edge_labels())
            form.addRow("Label 2 (-):", self.edge_label2_edit)

            # Linewidth
            self.linewidth_combo = QComboBox()
            self.linewidth_combo.addItems(['Thin', 'Medium', 'Thick', 'X-Thick'])
            # Find closest match
            lw_map = {1.0: 'Thin', 1.5: 'Medium', 2.0: 'Thick', 2.5: 'X-Thick'}
            current_lw = edge.get('linewidth_mult', 1.5)
            closest_lw = min(lw_map.keys(), key=lambda k: abs(k - current_lw))
            self.linewidth_combo.setCurrentText(lw_map[closest_lw])
            self.linewidth_combo.currentTextChanged.connect(lambda: self._update_edge_linewidth())
            form.addRow("Line Width:", self.linewidth_combo)

            # Style
            self.style_combo = QComboBox()
            self.style_combo.addItems(['loopy', 'single', 'double'])
            self.style_combo.setCurrentText(edge.get('style', 'loopy'))
            self.style_combo.currentTextChanged.connect(lambda: self._update_edge_style())
            form.addRow("Style:", self.style_combo)

            # Direction
            self.direction_combo = QComboBox()
            self.direction_combo.addItems(['both', 'forward', 'backward'])
            self.direction_combo.setCurrentText(edge.get('direction', 'both'))
            self.direction_combo.currentTextChanged.connect(lambda: self._update_edge_direction())
            form.addRow("Direction:", self.direction_combo)

            # Looptheta (curvature angle for loopy edges)
            self.looptheta_spinbox = QSpinBox()
            self.looptheta_spinbox.setMinimum(-180)
            self.looptheta_spinbox.setMaximum(180)
            self.looptheta_spinbox.setSuffix("°")
            self.looptheta_spinbox.setValue(edge.get('looptheta', 30))
            self.looptheta_spinbox.valueChanged.connect(lambda: self._update_edge_looptheta())
            form.addRow("Loop Theta (Ctrl+←/→):", self.looptheta_spinbox)

            # Arrowhead style + relative scale
            self.arrowstyle_combo = QComboBox()
            self.arrowstyle_combo.addItems(['open', 'filled', 'stealth'])
            self.arrowstyle_combo.setCurrentText(edge.get('arrowstyle', 'open'))
            self.arrowstyle_combo.currentTextChanged.connect(lambda: self._update_edge_arrowstyle())
            form.addRow("Arrowhead:", self.arrowstyle_combo)

            self.arrowscale_spinbox = QDoubleSpinBox()
            self.arrowscale_spinbox.setMinimum(0.2)
            self.arrowscale_spinbox.setMaximum(3.0)
            self.arrowscale_spinbox.setSingleStep(0.1)
            self.arrowscale_spinbox.setDecimals(2)
            self.arrowscale_spinbox.setSuffix("x")
            self.arrowscale_spinbox.setValue(edge.get('arrowscale', 1.0))
            self.arrowscale_spinbox.valueChanged.connect(lambda: self._update_edge_arrowscale())
            form.addRow("Arrowhead Scale:", self.arrowscale_spinbox)

            # Edge label background colors
            label1_bg_btn = QPushButton("Set Label1 BG" if edge.get('label1_bgcolor') else "No Label1 BG")
            label1_bg_btn.clicked.connect(lambda: self._choose_edge_label1_bgcolor())
            form.addRow("Label1 BG:", label1_bg_btn)
            if edge.get('label1_bgcolor'):
                clear_label1_bg_btn = QPushButton("Clear")
                clear_label1_bg_btn.clicked.connect(lambda: self._clear_edge_label1_bgcolor())
                form.addRow("", clear_label1_bg_btn)

            label2_bg_btn = QPushButton("Set Label2 BG" if edge.get('label2_bgcolor') else "No Label2 BG")
            label2_bg_btn.clicked.connect(lambda: self._choose_edge_label2_bgcolor())
            form.addRow("Label2 BG:", label2_bg_btn)
            if edge.get('label2_bgcolor'):
                clear_label2_bg_btn = QPushButton("Clear")
                clear_label2_bg_btn.clicked.connect(lambda: self._clear_edge_label2_bgcolor())
                form.addRow("", clear_label2_bg_btn)

        self.properties_layout.addLayout(form)
        self.displayed_single = edge

    def show_no_selection(self):
        """Show message when nothing is selected"""
        self.clear_properties()
        self.current_object = None
        self.current_type = None
        self.displayed_single = None
        self.displayed_multi = None
        self.title_label.setText("No Selection")

        info = QLabel("Select a node or edge to edit its properties.\n\nShift+click to select multiple objects.")
        info.setWordWrap(True)
        self.properties_layout.addWidget(info)

    # ---- Multi-selection editing -------------------------------------------------

    @staticmethod
    def selection_signature(nodes, edges):
        """A hashable signature identifying the current multi-selection by object identity."""
        return (frozenset(id(n) for n in nodes), frozenset(id(e) for e in edges))

    def _make_multi_int_spinbox(self, values, apply_fn, minimum, maximum, suffix=""):
        """Spinbox for a common integer property across a multi-selection.

        When the selected objects share one value it is shown normally; when they
        differ the smallest value is shown in gray (indeterminate) and is only
        written to all objects once the user changes it or presses Enter in it.
        """
        sb = QSpinBox()
        sb.setMinimum(minimum)
        sb.setMaximum(maximum)
        if suffix:
            sb.setSuffix(suffix)
        distinct = set(values)
        sb._indeterminate = len(distinct) > 1
        sb.blockSignals(True)
        sb.setValue(int(min(values)) if sb._indeterminate else int(next(iter(distinct))))
        sb.blockSignals(False)
        sb.setStyleSheet("color: gray;" if sb._indeterminate else "")

        def commit(val):
            sb._indeterminate = False
            sb.setStyleSheet("")
            apply_fn(int(val))
        sb.valueChanged.connect(commit)
        sb.lineEdit().returnPressed.connect(lambda: commit(sb.value()) if sb._indeterminate else None)
        return sb

    def _make_multi_double_spinbox(self, values, apply_fn, minimum, maximum, step, suffix="x", decimals=3):
        """Spinbox for a common float property across a multi-selection (see _make_multi_int_spinbox)."""
        sb = QDoubleSpinBox()
        sb.setMinimum(minimum)
        sb.setMaximum(maximum)
        sb.setSingleStep(step)
        sb.setDecimals(decimals)
        if suffix:
            sb.setSuffix(suffix)
        distinct = set(values)
        sb._indeterminate = len(distinct) > 1
        sb.blockSignals(True)
        sb.setValue(float(min(values)) if sb._indeterminate else float(next(iter(distinct))))
        sb.blockSignals(False)
        sb.setStyleSheet("color: gray;" if sb._indeterminate else "")

        def commit(val):
            sb._indeterminate = False
            sb.setStyleSheet("")
            apply_fn(float(val))
        sb.valueChanged.connect(commit)
        sb.lineEdit().returnPressed.connect(lambda: commit(sb.value()) if sb._indeterminate else None)
        return sb

    def _make_multi_combo(self, items, current_values, apply_fn):
        """Combo for a common discrete property; blank when the values differ.

        Uses the user-only `activated` signal so a programmatic build never commits.
        """
        cb = QComboBox()
        cb.addItems(items)
        distinct = set(current_values)
        if len(distinct) == 1 and next(iter(distinct)) in items:
            cb.setCurrentText(next(iter(distinct)))
        else:
            cb.setCurrentIndex(-1)  # blank == indeterminate
        cb.activated.connect(lambda: apply_fn(cb.currentText()))
        return cb

    def _make_multi_checkbox(self, values, apply_fn):
        """Tri-state checkbox for a common boolean property; partially-checked when values differ."""
        cb = QCheckBox()
        distinct = set(bool(v) for v in values)
        if len(distinct) == 1:
            cb.setChecked(next(iter(distinct)))
        else:
            cb.setTristate(True)
            cb.setCheckState(Qt.PartiallyChecked)

        def on_click():
            cb.setTristate(False)
            apply_fn(cb.isChecked())
        cb.clicked.connect(on_click)
        return cb

    def show_multi_properties(self, nodes, edges):
        """Show editable common properties for a multi-selection of nodes and/or edges."""
        self.clear_properties()
        self.current_object = None
        self.current_type = None
        self.displayed_single = None
        self.displayed_multi = self.selection_signature(nodes, edges)

        count_text = []
        if nodes:
            count_text.append(f"{len(nodes)} node(s)")
        if edges:
            count_text.append(f"{len(edges)} edge(s)")
        self.title_label.setText(f"Multiple Selection ({' + '.join(count_text)})")

        form = QFormLayout()

        # Node properties (only when nodes are selected)
        if nodes:
            size_sb = self._make_multi_double_spinbox(
                [n.get('node_size_mult', 1.0) for n in nodes],
                lambda val: self._apply_to_nodes('node_size_mult', val),
                0.5, 2.0, 0.1)
            form.addRow("Node Size:", size_sb)

            nlbl_sb = self._make_multi_double_spinbox(
                [n.get('label_size_mult', 1.0) for n in nodes],
                lambda val: self._apply_to_nodes('label_size_mult', val),
                0.5, 2.0, 0.1)
            form.addRow("Node Label Size:", nlbl_sb)

            conj_cb = self._make_multi_checkbox(
                [n.get('conj', False) for n in nodes],
                lambda val: self._apply_to_nodes('conj', val))
            form.addRow("Conjugate:", conj_cb)

            outline_cb = self._make_multi_checkbox(
                [n.get('outline_enabled', False) for n in nodes],
                lambda val: self._apply_to_nodes('outline_enabled', val))
            form.addRow("Outline:", outline_cb)

            color_btn = QPushButton("Choose Color (all nodes)")
            color_btn.clicked.connect(self._choose_multi_node_color)
            form.addRow("Color:", color_btn)

        # Edge properties (only when edges are selected)
        if edges:
            lw_map = {'Thin': 1.0, 'Medium': 1.5, 'Thick': 2.0, 'X-Thick': 2.5}
            lw_reverse = {v: k for k, v in lw_map.items()}
            lw_sb = self._make_multi_combo(
                ['Thin', 'Medium', 'Thick', 'X-Thick'],
                [lw_reverse.get(e.get('linewidth_mult', 1.5)) for e in edges
                 if e.get('linewidth_mult', 1.5) in lw_reverse],
                lambda text: self._apply_to_edges('linewidth_mult', lw_map[text]))
            form.addRow("Line Width:", lw_sb)

            regular_edges = [e for e in edges if not e.get('is_self_loop', False)]
            selfloops = [e for e in edges if e.get('is_self_loop', False)]

            # Arrowhead style applies to every edge type
            arrow_cb = self._make_multi_combo(
                ['open', 'filled', 'stealth'],
                [e.get('arrowstyle', 'open') for e in edges],
                lambda text: self._apply_to_edges('arrowstyle', text))
            form.addRow("Arrowhead:", arrow_cb)

            # Style/Direction/Loop Theta only when every selected edge is a regular edge
            if regular_edges and not selfloops:
                style_cb = self._make_multi_combo(
                    ['loopy', 'single', 'double'],
                    [e.get('style', 'loopy') for e in regular_edges],
                    lambda text: self._apply_to_edges('style', text))
                form.addRow("Style:", style_cb)

                dir_cb = self._make_multi_combo(
                    ['both', 'forward', 'backward'],
                    [e.get('direction', 'both') for e in regular_edges],
                    lambda text: self._apply_to_edges('direction', text))
                form.addRow("Direction:", dir_cb)

                looptheta_sb = self._make_multi_int_spinbox(
                    [e.get('looptheta', 30) for e in regular_edges],
                    lambda val: self._apply_to_edges('looptheta', val),
                    -180, 180, "°")
                form.addRow("Loop Theta:", looptheta_sb)

                arrowscale_sb = self._make_multi_double_spinbox(
                    [e.get('arrowscale', 1.0) for e in regular_edges],
                    lambda val: self._apply_to_edges('arrowscale', val),
                    0.2, 3.0, 0.1)
                form.addRow("Arrowhead Scale:", arrowscale_sb)

            # Loop Size/Flip only when every selected edge is a self-loop
            if selfloops and not regular_edges:
                scale_map = {'Small (0.7x)': 0.7, 'Medium (1.0x)': 1.0,
                             'Large (1.3x)': 1.3, 'X-Large (1.6x)': 1.6}
                scale_reverse = {v: k for k, v in scale_map.items()}
                scale_cb = self._make_multi_combo(
                    ['Small (0.7x)', 'Medium (1.0x)', 'Large (1.3x)', 'X-Large (1.6x)'],
                    [scale_reverse.get(e.get('selfloopscale', 1.0)) for e in selfloops
                     if e.get('selfloopscale', 1.0) in scale_reverse],
                    lambda text: self._apply_to_edges('selfloopscale', scale_map[text]))
                form.addRow("Loop Size:", scale_cb)

                flip_cb = self._make_multi_checkbox(
                    [e.get('flip', False) for e in selfloops],
                    lambda val: self._apply_to_edges('flip', val))
                form.addRow("Flip Direction:", flip_cb)

        self.properties_layout.addLayout(form)

        hint = QLabel("Gray values differ across the selection; edit a field to apply it to all.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 10px;")
        self.properties_layout.addWidget(hint)

    def _apply_to_nodes(self, key, value):
        """Write a property to every selected node (single undo step)."""
        g = self.graphulator
        if not g.selected_nodes:
            return
        g._save_state()
        for node in g.selected_nodes:
            node[key] = value
        g._update_plot()

    def _apply_to_edges(self, key, value):
        """Write a property to every selected edge (single undo step)."""
        g = self.graphulator
        if not g.selected_edges:
            return
        g._save_state()
        for edge in g.selected_edges:
            edge[key] = value
        g._update_plot()

    def _choose_multi_node_color(self):
        """Choose a color and apply it to all selected nodes."""
        g = self.graphulator
        if not g.selected_nodes:
            return
        start = QColor(g.selected_nodes[0].get('color', '#1f77b4'))
        color = QColorDialog.getColor(start, self.graphulator, "Choose Node Color (all selected)")
        if not color.isValid():
            return
        # Find a matching named color key, if any
        color_key = g.selected_nodes[0].get('color_key', 'BLUE')
        for key, val in config.MYCOLORS.items():
            if val.lower() == color.name().lower():
                color_key = key
                break
        g._save_state()
        for node in g.selected_nodes:
            node['color'] = color.name()
            node['color_key'] = color_key
        g._update_plot()

    # Update methods
    def _update_node_label(self):
        if self.current_object and self.current_type == 'node':
            new_label = self.label_edit.text().strip()
            # Prevent empty labels - use placeholder if empty
            if not new_label:
                new_label = '?'
                self.label_edit.setText(new_label)
            self.current_object['label'] = new_label
            self.graphulator._update_plot()

    def _choose_node_color(self):
        if self.current_object and self.current_type == 'node':
            current_color = QColor(self.current_object['color'])
            color = QColorDialog.getColor(current_color, self, "Choose Node Color")
            if color.isValid():
                self.current_object['color'] = color.name()
                # Find matching color key
                for key, val in config.MYCOLORS.items():
                    if val.lower() == color.name().lower():
                        self.current_object['color_key'] = key
                        break
                self.graphulator._update_plot()

    def _update_node_size(self):
        if self.current_object and self.current_type == 'node':
            mult = self.node_size_slider.value() / 100.0
            self.current_object['node_size_mult'] = mult
            self.node_size_label.setText(f"{mult:.3f}x")
            self.graphulator._update_plot()

    def _update_label_size(self):
        if self.current_object and self.current_type == 'node':
            mult = self.label_size_slider.value() / 100.0
            self.current_object['label_size_mult'] = mult
            self.label_size_label.setText(f"{mult:.3f}x")
            self.graphulator._update_plot()

    def _update_conjugation(self):
        if self.current_object and self.current_type == 'node':
            self.current_object['conj'] = self.conj_checkbox.isChecked()
            self.graphulator._update_plot()

    def _update_outline_enabled(self):
        if self.current_object and self.current_type == 'node':
            self.current_object['outline_enabled'] = self.outline_checkbox.isChecked()
            self.graphulator._update_plot()

    def _choose_outline_color(self):
        if self.current_object and self.current_type == 'node':
            current = self.current_object.get('outline_color', config.DEFAULT_NODE_OUTLINE_COLOR)
            color = QColorDialog.getColor(QColor(current), self.graphulator, "Choose Outline Color")
            if color.isValid():
                self.current_object['outline_color'] = color.name()
                self.graphulator._update_plot()

    def _update_outline_width(self):
        if self.current_object and self.current_type == 'node':
            self.current_object['outline_width'] = self.outline_width_spin.value()
            self.graphulator._update_plot()

    def _update_outline_alpha(self):
        if self.current_object and self.current_type == 'node':
            self.current_object['outline_alpha'] = self.outline_alpha_spin.value()
            self.graphulator._update_plot()

    def _choose_edge_label_bgcolor(self):
        """Choose background color for self-loop label"""
        if self.current_object and self.current_type == 'edge' and self.current_object.get('is_self_loop', False):
            current = self.current_object.get('label_bgcolor', 'white')
            color = QColorDialog.getColor(QColor(current), self.graphulator, "Choose Label Background Color")
            if color.isValid():
                self.current_object['label_bgcolor'] = color.name()
                self.graphulator._update_plot()
                self.show_edge_properties(self.current_object)

    def _clear_edge_label_bgcolor(self):
        """Clear background color for self-loop label"""
        if self.current_object and self.current_type == 'edge' and self.current_object.get('is_self_loop', False):
            if 'label_bgcolor' in self.current_object:
                del self.current_object['label_bgcolor']
            self.graphulator._update_plot()
            self.show_edge_properties(self.current_object)

    def _choose_edge_label1_bgcolor(self):
        """Choose background color for edge label1"""
        if self.current_object and self.current_type == 'edge' and not self.current_object.get('is_self_loop', False):
            current = self.current_object.get('label1_bgcolor', 'white')
            color = QColorDialog.getColor(QColor(current), self.graphulator, "Choose Label1 Background Color")
            if color.isValid():
                self.current_object['label1_bgcolor'] = color.name()
                self.graphulator._update_plot()
                self.show_edge_properties(self.current_object)

    def _clear_edge_label1_bgcolor(self):
        """Clear background color for edge label1"""
        if self.current_object and self.current_type == 'edge' and not self.current_object.get('is_self_loop', False):
            if 'label1_bgcolor' in self.current_object:
                del self.current_object['label1_bgcolor']
            self.graphulator._update_plot()
            self.show_edge_properties(self.current_object)

    def _choose_edge_label2_bgcolor(self):
        """Choose background color for edge label2"""
        if self.current_object and self.current_type == 'edge' and not self.current_object.get('is_self_loop', False):
            current = self.current_object.get('label2_bgcolor', 'white')
            color = QColorDialog.getColor(QColor(current), self.graphulator, "Choose Label2 Background Color")
            if color.isValid():
                self.current_object['label2_bgcolor'] = color.name()
                self.graphulator._update_plot()
                self.show_edge_properties(self.current_object)

    def _clear_edge_label2_bgcolor(self):
        """Clear background color for edge label2"""
        if self.current_object and self.current_type == 'edge' and not self.current_object.get('is_self_loop', False):
            if 'label2_bgcolor' in self.current_object:
                del self.current_object['label2_bgcolor']
            self.graphulator._update_plot()
            self.show_edge_properties(self.current_object)

    def _update_edge_labels(self):
        if self.current_object and self.current_type == 'edge':
            self.current_object['label1'] = self.edge_label1_edit.text()
            # Only update label2 if it exists (not present for self-loops)
            if hasattr(self, 'edge_label2_edit'):
                self.current_object['label2'] = self.edge_label2_edit.text()
            self.graphulator._update_plot()

    def _update_edge_linewidth(self):
        if self.current_object and self.current_type == 'edge':
            lw_map = {'Thin': 1.0, 'Medium': 1.5, 'Thick': 2.0, 'X-Thick': 2.5}
            self.current_object['linewidth_mult'] = lw_map[self.linewidth_combo.currentText()]
            self.graphulator._update_plot()

    def _update_edge_style(self):
        if self.current_object and self.current_type == 'edge':
            self.current_object['style'] = self.style_combo.currentText()
            self.graphulator._update_plot()

    def _update_edge_direction(self):
        if self.current_object and self.current_type == 'edge':
            self.current_object['direction'] = self.direction_combo.currentText()
            self.graphulator._update_plot()

    def _update_edge_arrowstyle(self):
        if self.current_object and self.current_type == 'edge':
            self.current_object['arrowstyle'] = self.arrowstyle_combo.currentText()
            self.graphulator._update_plot()

    def _update_edge_arrowscale(self):
        if self.current_object and self.current_type == 'edge':
            self.current_object['arrowscale'] = self.arrowscale_spinbox.value()
            self.graphulator._update_plot()

    def _update_edge_looptheta(self):
        if self.current_object and self.current_type == 'edge':
            self.current_object['looptheta'] = self.looptheta_spinbox.value()
            self.graphulator._update_plot()

    @staticmethod
    def _compass_direction(angle):
        """Return compass direction label for an angle."""
        compass = {
            0: 'Right', 45: 'Up-Right', 90: 'Up', 135: 'Up-Left',
            180: 'Left', 225: 'Down-Left', 270: 'Down', 315: 'Down-Right'
        }
        return compass.get(angle % 360, '')

    def _update_selfloop_angle(self):
        """Legacy angle update from combo (kept for compatibility)"""
        if self.current_object and self.current_type == 'edge':
            angle_text = self.selfloop_angle_combo.currentText()
            selfloopangle = int(angle_text.split('°')[0])
            self.current_object['selfloopangle'] = selfloopangle
            self.graphulator._update_plot()

    def _update_selfloop_angle_spinbox(self, value):
        """Update self-loop angle from spinbox"""
        if self.current_object and self.current_type == 'edge':
            self.current_object['selfloopangle'] = value
            self.current_object['angle_pinned'] = True
            # Update compass label and pinned checkbox
            if hasattr(self, 'selfloop_angle_compass_label'):
                self.selfloop_angle_compass_label.setText(self._compass_direction(value))
            if hasattr(self, 'selfloop_angle_pinned_checkbox'):
                self.selfloop_angle_pinned_checkbox.blockSignals(True)
                self.selfloop_angle_pinned_checkbox.setChecked(True)
                self.selfloop_angle_pinned_checkbox.blockSignals(False)
            self.graphulator._update_plot()

    def _update_selfloop_angle_pinned(self):
        """Update angle_pinned flag from checkbox"""
        if self.current_object and self.current_type == 'edge':
            self.current_object['angle_pinned'] = self.selfloop_angle_pinned_checkbox.isChecked()

    def _update_selfloop_scale(self):
        if self.current_object and self.current_type == 'edge':
            scale_text = self.selfloop_scale_combo.currentText()
            scale_map = {'Small (0.7x)': 0.7, 'Medium (1.0x)': 1.0, 'Large (1.3x)': 1.3, 'X-Large (1.6x)': 1.6}
            self.current_object['selfloopscale'] = scale_map[scale_text]
            self.graphulator._update_plot()

    def _update_selfloop_flip(self):
        if self.current_object and self.current_type == 'edge':
            self.current_object['flip'] = self.selfloop_flip_checkbox.isChecked()
            self.graphulator._update_plot()


class MplCanvas(FigureCanvas):
    """Matplotlib canvas for embedding in Qt"""

    # Custom signals
    click_signal = Signal(object)
    release_signal = Signal(object)
    motion_signal = Signal(object)
    scroll_signal = Signal(object)

    def __init__(self, parent=None, width=12, height=12, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)

        # Remove all margins - make axes fill entire figure
        self.fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

        self.ax = self.fig.add_subplot(111)

        # Remove any padding around the axes
        self.ax.set_position([0, 0, 1, 1])  # [left, bottom, width, height] in figure coordinates

        super().__init__(self.fig)

        # Connect matplotlib events to Qt signals
        self.mpl_connect('button_press_event', self._on_click)
        self.mpl_connect('button_release_event', self._on_release)
        self.mpl_connect('motion_notify_event', self._on_motion)
        self.mpl_connect('scroll_event', self._on_scroll)

    def _on_click(self, event):
        self.click_signal.emit(event)

    def _on_release(self, event):
        self.release_signal.emit(event)

    def _on_motion(self, event):
        self.motion_signal.emit(event)

    def _on_scroll(self, event):
        self.scroll_signal.emit(event)


class GraphulatorSettingsDialog(SettingsDialogBase):
    """Graphulator Settings dialog: styling defaults with a live preview.

    Convention parameters (conjugation styling, arrowhead opening angle,
    node base radius) live-apply to the open graph as they change; the
    remaining defaults affect newly placed objects, with an explicit
    "Apply to Existing" button for restyling the current graph.
    """

    def __init__(self, parent=None):
        super().__init__(
            parent,
            config_module=config,
            params_table=config.SETTINGS_PARAMS,
            settings_manager=get_settings_manager('graphulator',
                                                  config_module=config),
            live_params=config.LIVE_PARAMS,
            sample_scene=make_style_sample_scene(config),
        )

    def _refresh_ui(self):
        """Refresh the Graphulator canvas after settings change."""
        self.graphulator.node_radius = config.DEFAULT_NODE_RADIUS
        self.graphulator._update_plot()

    def _after_apply(self):
        """Sync dialog memory so new nodes pick up the changed defaults."""
        sync_dialog_defaults_from_config(self.graphulator)

    def _add_extra_buttons(self, button_layout):
        apply_existing_btn = QPushButton("Apply to Existing…")
        apply_existing_btn.setAutoDefault(False)
        apply_existing_btn.setToolTip(
            "Apply the edge arrowhead defaults to every edge and the node "
            "outline defaults to every node in the current graph (one undo "
            "step)")
        apply_existing_btn.clicked.connect(self._on_apply_to_existing)
        button_layout.addWidget(apply_existing_btn)

    def _on_apply_to_existing(self):
        """Restyle the current graph from the defaults (one undo step)."""
        self._apply_all_values()
        g = self.graphulator
        if not g.edges and not g.nodes:
            self._refresh_ui()
            return
        outline_desc = ("on" if config.DEFAULT_NODE_OUTLINE_ENABLED
                        else "off")
        reply = QMessageBox.question(
            self, "Apply to Existing",
            f"Apply the arrowhead defaults "
            f"({config.DEFAULT_EDGE_ARROWSTYLE}, "
            f"{config.DEFAULT_EDGE_ARROWSCALE:g}x) to all "
            f"{len(g.edges)} edge(s) and the outline defaults "
            f"({outline_desc}) to all {len(g.nodes)} node(s) in the "
            f"current graph?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        g._save_state()
        for edge in g.edges:
            edge['arrowstyle'] = config.DEFAULT_EDGE_ARROWSTYLE
            edge['arrowscale'] = config.DEFAULT_EDGE_ARROWSCALE
        for node in g.nodes:
            node['outline_enabled'] = config.DEFAULT_NODE_OUTLINE_ENABLED
            node['outline_color'] = config.DEFAULT_NODE_OUTLINE_COLOR
            node['outline_width'] = config.DEFAULT_NODE_OUTLINE_WIDTH
            node['outline_alpha'] = config.DEFAULT_NODE_OUTLINE_ALPHA
        self._refresh_ui()


class Graphulator(GraphWindowCommonMixin, QMainWindow):
    """Main application window"""

    # Shared-behavior parametrization (see GraphWindowCommonMixin); the
    # mixin's defaults are already the Graphulator values, so only the
    # config module needs setting.
    APP_CONFIG = config

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Graphulator - Interactive Graph Drawing Tool")

        # Apply saved user settings to the config module before any
        # config-derived state is initialized below, then sync the dialog
        # defaults so new nodes reflect the saved settings
        get_settings_manager('graphulator', config_module=config).load()
        sync_dialog_defaults_from_config()

        # Grid parameters
        self.grid_spacing = config.DEFAULT_GRID_SPACING
        self.grid_type = config.DEFAULT_GRID_TYPE
        self.grid_rotation = 0
        self.zoom_level = 1.0
        self.base_xlim = config.DEFAULT_XLIM
        self.base_ylim = config.DEFAULT_YLIM

        # Rendering mode
        self.use_latex = False  # Toggle between MathText and LaTeX rendering
        # Cached vector glyph-paths for labels: each unique label string is
        # compiled once (mathtext or LaTeX) and reused across pan/zoom/rescale via
        # cheap affine transforms, so the layout engine is never re-run per frame.
        self._label_cache = LabelPathCache()
        # Fast pan/zoom path state (scene built once; zoom only updates the view).
        self._build_ppu = None            # points-per-data-unit at last full build
        self._zoom_lw_snapshot = None     # [(artist, base_linewidth), ...] (grid excluded)
        self._grid_built_extent = None    # half-extent the grid currently covers
        self.latex_debounce_timer = QTimer()
        self.latex_debounce_timer.setSingleShot(True)
        self.latex_debounce_timer.timeout.connect(self._render_with_latex)
        self.latex_debounce_timeout = 400  # milliseconds
        self.is_fast_rendering = False  # True when using MathText for quick feedback

        # Resize debounce timer to prevent excessive redraws during window resize
        self.resize_debounce_timer = QTimer()
        self.resize_debounce_timer.setSingleShot(True)
        self.resize_debounce_timer.timeout.connect(self._handle_resize_complete)
        self.resize_debounce_timeout = 100  # milliseconds
        self.pending_resize_limits = None  # Store pending axis limits

        # Edge label rotation mode
        self.edge_rotation_mode = False  # True when adjusting edge label rotation

        # Export scaling parameters (tunable via UI)
        # self.export_rescale = {
        #     'NODELABELSCALE': 0.55,
        #     'SLCC': 0.65,  # Self-loop color correction (legacy)
        #     'SELFLOOP_LABELSCALE': 0.65,  # Self-loop label size scale
        #     'SLLW': 1.2,  # Self-loop linewidth
        #     'SLSC': 1.0,  # Self-loop scale
        #     'SLLNOFFSET': (0.0, 0.0),  # Self-loop label nudge offset
        #     'SELFLOOP_LABELNUDGE_SCALE': 1.0,  # Self-loop label nudge multiplier
        #     'EDGEFONTSCALE': 1.8,  # Edge label font scale
        #     'EDGELWSCALE': 2.6,  # Edge linewidth scale
        #     'EDGELABELOFFSET': 1.05,  # Edge label offset
        #     'GUI_SELFLOOP_LABEL_SCALE': 1.5,  # GUI self-loop label distance scale
        #     'EXPORT_SELFLOOP_LABEL_DISTANCE': 1.0,  # Export self-loop label distance scale
        # }
        
        # self.export_rescale = {
        #     'NODELABELSCALE': 1.000,
        #     'SLCC': 0.650,
        #     'SELFLOOP_LABELSCALE': 0.132,
        #     'SLLW': 6.700,
        #     'SLSC': 1.000,
        #     'SLLNOFFSET': (0.0, 0.0),
        #     'SELFLOOP_LABELNUDGE_SCALE': 1.100,
        #     'EDGEFONTSCALE': 1.100,
        #     'EDGELWSCALE': 2.700,
        #     'EDGELABELOFFSET': 1.000,
        #     'GUI_SELFLOOP_LABEL_SCALE': 1.300,
        #     'EXPORT_SELFLOOP_LABEL_DISTANCE': 1.200,
        # }

        self.export_rescale = EXPORT_RESCALE_DEFAULTS.copy()

        # Node parameters
        self.nodes = []
        self.node_counter = 0
        self.node_id_counter = 0  # Unique ID for each node, independent of labels
        self.node_radius = config.DEFAULT_NODE_RADIUS
        self.preview_patch = None
        self.preview_text = None

        # Edge parameters
        self.edges = []
        self.edge_mode_first_node = None  # First node selected in edge mode
        self.edge_mode_highlight_patch = None  # Visual highlight for first selected node

        # GraphCircuit for managing graph structure (allow duplicate labels)
        self.graph = gp.GraphCircuit(allow_duplicate_labels=True)

        # Placement mode
        self.placement_mode = None  # None, 'single', 'continuous', 'continuous_duplicate', 'conjugation', 'edge', or 'edge_continuous'

        # Last placed node properties for duplication
        self.last_node_props = None

        # Pan and zoom window state
        self.panning = False
        self.pan_start = None
        self.zoom_window = False
        self.zoom_window_start = None
        self.zoom_window_rect = None

        # Node dragging state
        self.dragging_node = None
        self.dragging_group = False  # True if dragging multiple selected nodes
        self.drag_pending_node = None  # Node clicked but not yet dragging (waiting for motion)
        self.drag_pending_group = False  # Group clicked but not yet dragging
        self.drag_start_pos = None  # Starting position for group drag
        self.drag_threshold = 0.1  # Minimum distance to move before starting drag (data units)
        self.drag_preview_patches = []  # List of preview patches for group drag
        self.drag_preview_texts = []  # List of preview texts for group drag

        # Double-click tracking
        self.last_click_time = 0
        self.last_click_pos = None
        self.double_click_threshold = 0.3  # seconds

        # Selection state
        self.selected_nodes = []  # List of selected node references
        self.selected_edges = []  # List of selected edge references
        self.selection_window = False
        self.selection_window_start = None
        self.selection_window_rect = None
        self.clipboard = {'nodes': [], 'edges': []}  # Copied nodes and edges

        # Undo system
        self.undo_stack = []  # Stack of previous states
        self.redo_stack = []  # Stack of undone states
        self.max_undo = 50  # Maximum undo levels

        # Graph circuit
        self.graph = gp.GraphCircuit()

        # File management
        self.current_filepath = None  # Path to currently open file
        self.is_modified = False  # Track unsaved changes
        self.recent_files = []  # List of recent file paths
        self.max_recent_files = 10
        self.recent_files_path = Path.home() / '.graphulator_recent'
        self.last_graph_path = Path.home() / '.graphulator_last.graph'

        # Load recent files list
        self._load_recent_files()

        # Create UI
        self._create_ui()
        self._create_menu_bar()
        self._create_shortcuts()
        self._update_plot()

        # Print instructions
        self._print_instructions()

    def _clear_all_previews(self):
        """Clear all preview patches and texts"""
        # Clear drag previews
        for patch in self.drag_preview_patches:
            try:
                patch.remove()
            except:
                pass
        for text in self.drag_preview_texts:
            try:
                text.remove()
            except:
                pass
        self.drag_preview_patches.clear()
        self.drag_preview_texts.clear()

        # Clear placement preview
        if self.preview_patch:
            try:
                self.preview_patch.remove()
            except:
                pass
            self.preview_patch = None

        if self.preview_text:
            try:
                self.preview_text.remove()
            except:
                pass
            self.preview_text = None

    def _create_ui(self):
        """Create the user interface"""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout (horizontal: canvas area | properties panel)
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)

        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # Left panel: Canvas area with status bar
        canvas_widget = QWidget()
        canvas_layout = QVBoxLayout()
        canvas_layout.setContentsMargins(0, 0, 0, 0)  # No margins
        canvas_layout.setSpacing(0)  # No spacing
        canvas_widget.setLayout(canvas_layout)

        # Status bar at top
        self.status_label = QLabel()
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                padding: 5px 10px;
                border-bottom: 1px solid #cccccc;
                font-family: monospace;
                font-size: 11px;
            }
        """)
        self.status_label.setWordWrap(False)
        canvas_layout.addWidget(self.status_label)

        # Canvas fills remaining space
        self.canvas = MplCanvas(self, width=12, height=12, dpi=100)
        canvas_layout.addWidget(self.canvas, stretch=1)  # Stretch to fill

        splitter.addWidget(canvas_widget)

        # Right panel: Properties (20%)
        self.properties_panel = PropertiesPanel(self)
        splitter.addWidget(self.properties_panel)

        # Set initial sizes (80:20 ratio = 4:1)
        # splitter.setSizes([960, 240])
        # Set initial sizes (70:30 ratio = 7:3)
        splitter.setSizes([840, 360])

        # Connect signals
        self.canvas.click_signal.connect(self._on_click)
        self.canvas.release_signal.connect(self._on_release)
        self.canvas.motion_signal.connect(self._on_motion)
        self.canvas.scroll_signal.connect(self._on_scroll)

        # Set window size (wider and taller)
        self.resize(1400, 900)

    def _create_shortcuts(self):
        """Create keyboard shortcuts"""
        # Placement modes
        QShortcut(QKeySequence("g"), self).activated.connect(lambda: self._set_placement_mode('single'))
        QShortcut(QKeySequence("Shift+G"), self).activated.connect(self._toggle_continuous_mode)
        QShortcut(QKeySequence("Ctrl+G"), self).activated.connect(self._toggle_continuous_duplicate_mode)
        QShortcut(QKeySequence("Esc"), self).activated.connect(self._exit_placement_mode)

        # Grid controls
        QShortcut(QKeySequence("r"), self).activated.connect(self._rotate_grid)
        QShortcut(QKeySequence("t"), self).activated.connect(self._toggle_grid_type)

        # Graph rotation controls (rotate selected nodes)
        QShortcut(QKeySequence("Ctrl+R"), self).activated.connect(lambda: self._rotate_selected_nodes(15))  # CCW
        QShortcut(QKeySequence("Ctrl+Shift+R"), self).activated.connect(lambda: self._rotate_selected_nodes(-15))  # CW

        # View controls
        QShortcut(QKeySequence("a"), self).activated.connect(self._auto_fit_view)
        QShortcut(QKeySequence("c"), self).activated.connect(self._toggle_conjugation_mode)
        # Clear-all moved off Ctrl+Shift+C: too close to Ctrl+C (copy) for a
        # destructive action. Mirror the Delete/Backspace pair used for deleting
        # the current selection.
        QShortcut(QKeySequence("Ctrl+Shift+Delete"), self).activated.connect(self._clear_nodes)
        QShortcut(QKeySequence("Ctrl+Shift+Backspace"), self).activated.connect(self._clear_nodes)

        # Flip edge labels shortcut
        QShortcut(QKeySequence("f"), self).activated.connect(self._toggle_flip_labels)
        QShortcut(QKeySequence("Shift+F"), self).activated.connect(self._toggle_edge_rotation_mode)

        # Edge mode shortcut
        QShortcut(QKeySequence("e"), self).activated.connect(self._toggle_edge_mode)
        QShortcut(QKeySequence("Ctrl+E"), self).activated.connect(self._toggle_edge_continuous_mode)

        # Zoom controls
        QShortcut(QKeySequence("+"), self).activated.connect(lambda: self._zoom(config.ZOOM_KEYBOARD_FACTOR))
        QShortcut(QKeySequence("="), self).activated.connect(lambda: self._zoom(config.ZOOM_KEYBOARD_FACTOR))
        QShortcut(QKeySequence("-"), self).activated.connect(lambda: self._zoom(1/config.ZOOM_KEYBOARD_FACTOR))

        # Pan controls (arrow keys)
        QShortcut(QKeySequence("Left"), self).activated.connect(lambda: self._pan_arrow('left'))
        QShortcut(QKeySequence("Right"), self).activated.connect(lambda: self._pan_arrow('right'))
        QShortcut(QKeySequence("Up"), self).activated.connect(lambda: self._arrow_key_action('up'))
        QShortcut(QKeySequence("Down"), self).activated.connect(lambda: self._arrow_key_action('down'))

        # Label nudge controls (Shift+arrow keys)
        QShortcut(QKeySequence("Shift+Left"), self).activated.connect(lambda: self._nudge_label('left'))
        QShortcut(QKeySequence("Shift+Right"), self).activated.connect(lambda: self._nudge_label('right'))
        QShortcut(QKeySequence("Shift+Up"), self).activated.connect(lambda: self._nudge_label('up'))
        QShortcut(QKeySequence("Shift+Down"), self).activated.connect(lambda: self._nudge_label('down'))

        # Self-loop parameter adjustments (Ctrl+arrow keys)
        QShortcut(QKeySequence("Ctrl+Up"), self).activated.connect(lambda: self._adjust_selfloop_scale('increase'))
        QShortcut(QKeySequence("Ctrl+Down"), self).activated.connect(lambda: self._adjust_selfloop_scale('decrease'))
        # Ctrl+Left/Right: adjust self-loop angle for self-loops, looptheta for regular edges
        ctrl_left = QShortcut(QKeySequence("Ctrl+Left"), self)
        ctrl_left.activated.connect(lambda: self._adjust_edge_looptheta_or_selfloop_angle('decrease'))
        ctrl_right = QShortcut(QKeySequence("Ctrl+Right"), self)
        ctrl_right.activated.connect(lambda: self._adjust_edge_looptheta_or_selfloop_angle('increase'))
        logger.debug(f"Ctrl+Left/Right shortcuts registered: {ctrl_left}, {ctrl_right}")

        # File operations
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self._new_graph)
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self._open_graph)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._save_graph)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self).activated.connect(self._save_graph_as)

        # Selection and clipboard
        QShortcut(QKeySequence("Ctrl+A"), self).activated.connect(self._select_all)
        QShortcut(QKeySequence("Ctrl+C"), self).activated.connect(self._copy_nodes)
        QShortcut(QKeySequence("Ctrl+X"), self).activated.connect(self._cut_nodes)
        QShortcut(QKeySequence("Ctrl+V"), self).activated.connect(self._paste_nodes)
        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(self._undo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self).activated.connect(self._redo)
        QShortcut(QKeySequence("Ctrl+Y"), self).activated.connect(self._redo)

        # Export
        QShortcut(QKeySequence("Ctrl+Shift+E"), self).activated.connect(self._export_code)

        # Toggle LaTeX rendering
        QShortcut(QKeySequence("Ctrl+L"), self).activated.connect(self._toggle_latex_mode)

        # Delete - try both Delete and Backspace keys
        QShortcut(QKeySequence(Qt.Key_Delete), self).activated.connect(self._delete_selected_nodes)
        QShortcut(QKeySequence(Qt.Key_Backspace), self).activated.connect(self._delete_selected_nodes)
        QShortcut(QKeySequence("d"), self).activated.connect(self._delete_selected_nodes)


        # Quit
        QShortcut(QKeySequence("Ctrl+Q"), self).activated.connect(self.close)

    def _print_instructions(self):
        """Print usage instructions to console"""
        logger.debug("=" * 70)
        logger.info("GRAPHULATOR - Interactive Graph Drawing Tool (Qt Version)")
        logger.debug("=" * 70)
        logger.info("Controls:")
        logger.debug("  'g'             : Place single node (dialog for label/color)")
        logger.debug("  'G' (Shift+g)   : Continuous node placement mode")
        logger.debug("  'Ctrl+G'        : Continuous duplicate mode (auto-increment labels)")
        logger.debug("  'e'             : Place single edge (exits after one edge)")
        logger.debug("  'Ctrl+E'        : Toggle continuous edge mode")
        logger.debug("  'c'             : Conjugation mode (click nodes to toggle)")
        logger.debug("  'Esc'           : Exit placement mode / Clear selection")
        logger.debug("  'r'             : Rotate grid (45° square, 30° triangular)")
        logger.debug("  't'             : Toggle grid type (square/triangular)")
        logger.debug("  'Ctrl+Shift+Delete' : Clear all nodes")
        logger.debug("  'a'             : Auto-fit view to nodes")
        logger.debug("  '+/-'           : Zoom in/out")
        logger.debug("  Mouse wheel     : Zoom in/out")
        logger.debug("  Arrow keys      : Pan view (or adjust size when selected)")
        logger.debug("")
        logger.debug("Node Selection & Editing:")
        logger.debug("  Left click      : Select node (drag to move)")
        logger.debug("  Right click     : Color menu (nodes) / Edge type menu (edges)")
        logger.debug("  Shift+click     : Add/remove node or edge from selection")
        logger.debug("  Click+drag      : Draw selection window")
        logger.debug("  Double-click    : Edit node or edge properties")
        logger.debug("  Up/Down arrows  : Increase/decrease node/edge size (when selected)")
        logger.debug("  Left/Right      : Adjust label size (nodes/edges when selected)")
        logger.debug("  Shift+Up/Down   : Nudge node label / Adjust edge label offset")
        logger.debug("  Shift+Left/Right: Nudge node label horizontally")
        logger.debug("  Ctrl+A          : Select all nodes and edges")
        logger.debug("  Ctrl+C          : Copy selected nodes and edges")
        logger.info("  Ctrl+X          : Cut selected nodes and edges")
        logger.debug("  Ctrl+V          : Paste nodes and edges at view center")
        logger.info("  Ctrl+Z          : Undo last action")
        logger.info("  Ctrl+Shift+Z/Y  : Redo last undone action")
        logger.debug("  Ctrl+R          : Rotate selected nodes 15° CCW")
        logger.debug("  Ctrl+Shift+R    : Rotate selected nodes 15° CW")
        logger.debug("  Ctrl+Shift+E    : Export graph as Python code")
        logger.debug("  Ctrl+L          : Toggle LaTeX rendering mode")
        logger.debug("  'f'             : Flip edge labels (when edge selected)")
        logger.debug("  Shift+F         : Toggle edge label rotation mode (when edge selected)")
        logger.debug("                    Then use Left/Right arrows to rotate ±5°")
        logger.debug("  'd' or Delete   : Delete selected nodes and edges")
        logger.debug("")
        logger.debug("Navigation:")
        logger.debug("  Middle button   : Pan (click and drag)")
        logger.debug("  Right button    : Zoom window (click and drag)")
        logger.debug("  'Ctrl+Q'        : Quit")
        logger.debug("=" * 70)
        logger.debug(f"Current: {self.grid_type} grid, rotation={self.grid_rotation}°")
        logger.debug("")

    def _create_menu_bar(self):
        """Create menu bar with File menu"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        # New
        new_action = QAction("&New", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self._new_graph)
        file_menu.addAction(new_action)

        # Open
        open_action = QAction("&Open...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_graph)
        file_menu.addAction(open_action)

        # Recent Files submenu
        self.recent_files_menu = file_menu.addMenu("Open &Recent")
        self._update_recent_files_menu()

        # Examples submenu
        self.examples_menu = file_menu.addMenu("&Examples")
        self._populate_examples_menu()

        # Reload Last Graph
        reload_action = QAction("Reload Last Graph", self)
        reload_action.triggered.connect(self._reload_last_graph)
        file_menu.addAction(reload_action)

        file_menu.addSeparator()

        # Settings
        settings_action = QAction("Se&ttings…", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._open_settings)
        file_menu.addAction(settings_action)

        file_menu.addSeparator()

        # Save
        save_action = QAction("&Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_graph)
        file_menu.addAction(save_action)

        # Save As
        save_as_action = QAction("Save &As...", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self._save_graph_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        # Export submenu
        export_menu = file_menu.addMenu("&Export")

        copy_clipboard_action = QAction("Copy Graph to Clipboard", self)
        copy_clipboard_action.setShortcut("Ctrl+Shift+I")
        copy_clipboard_action.setStatusTip(
            "Copy the whole graph to the clipboard (vector PDF/SVG + PNG) for "
            "pasting into Keynote, PowerPoint, Illustrator, etc."
        )
        copy_clipboard_action.triggered.connect(lambda: self._copy_graph_to_clipboard())
        export_menu.addAction(copy_clipboard_action)

        copy_vector_action = QAction("Copy Graph to Clipboard (Vector Only)", self)
        copy_vector_action.setShortcut("Ctrl+Shift+J")
        copy_vector_action.setStatusTip(
            "Copy the graph as vector PDF/SVG only (no raster fallback) so apps "
            "like Keynote/PowerPoint paste editable vector art instead of an image."
        )
        copy_vector_action.triggered.connect(self._copy_graph_to_clipboard_vector)
        export_menu.addAction(copy_vector_action)
        export_menu.addSeparator()

        export_code_action = QAction("Python Code...", self)
        export_code_action.setShortcut("Ctrl+Shift+E")
        export_code_action.triggered.connect(self._export_code)
        export_menu.addAction(export_code_action)

        export_png_action = QAction("PNG Image...", self)
        export_png_action.triggered.connect(self._export_png)
        export_menu.addAction(export_png_action)

        export_svg_action = QAction("SVG Image...", self)
        export_svg_action.triggered.connect(self._export_svg)
        export_menu.addAction(export_svg_action)

        export_pdf_action = QAction("PDF Document...", self)
        export_pdf_action.triggered.connect(self._export_pdf)
        export_menu.addAction(export_pdf_action)

        file_menu.addSeparator()

        # Exit
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        # On macOS Qt automatically relocates any action whose text matches
        # "About …" into the application menu, regardless of its menu role.
        about_action = QAction("&About Graphulator", self)
        about_action.setMenuRole(QAction.MenuRole.AboutRole)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)


    def _populate_examples_menu(self):
        """Populate the Examples submenu with example graphs from package resources"""
        self.examples_menu.clear()

        # Try to find examples in package resources
        try:
            from importlib import resources
            if hasattr(resources, 'files'):  # Python 3.9+
                examples_path = resources.files('graphulator').joinpath('examples/graphs')
            else:  # Fallback for older Python
                import pkg_resources
                examples_path = Path(pkg_resources.resource_filename('graphulator', 'examples/graphs'))

            # Find all .graph files
            example_files = []
            if hasattr(examples_path, 'iterdir'):
                example_files = sorted([f for f in examples_path.iterdir() if f.name.endswith('.graph')])
            else:
                example_files = sorted([Path(f) for f in examples_path.glob('*.graph')])

            if not example_files:
                no_examples = QAction("(No examples available)", self)
                no_examples.setEnabled(False)
                self.examples_menu.addAction(no_examples)
            else:
                for example_file in example_files:
                    action = QAction(example_file.stem, self)
                    action.setToolTip(f"Load example: {example_file.name}")
                    action.triggered.connect(lambda checked, f=example_file: self._load_example(f))
                    self.examples_menu.addAction(action)
        except Exception as e:
            logger.debug(f"Could not load examples: {e}")
            no_examples = QAction("(Examples not found)", self)
            no_examples.setEnabled(False)
            self.examples_menu.addAction(no_examples)

    def _load_example(self, example_path):
        """Load an example graph file"""
        try:
            # Read the example file content
            if hasattr(example_path, 'read_text'):
                # Using importlib.resources path
                content = example_path.read_text()
            else:
                # Using regular file path
                with open(example_path, 'r') as f:
                    content = f.read()

            # Parse and load the example
            import json
            data = json.loads(content)
            self._deserialize_graph(data)

            # Mark as not saved (it's from examples, not a file)
            self.current_filepath = None
            self._set_modified(False)
            self.setWindowTitle(f"Graphulator - {example_path.stem} (example)")
            logger.info(f"Loaded example: {example_path.stem}")
        except Exception as e:
            logger.error(f"Error loading example: {e}")
            QMessageBox.warning(self, "Load Error", f"Could not load example:\n{e}")

    def _serialize_graph(self):
        """Serialize graph to dictionary for saving"""
        data = {
            "version": "1.0",
            "metadata": {
                "created": datetime.now().isoformat(),
                "modified": datetime.now().isoformat()
            },
            "view": {
                "grid_type": self.grid_type,
                "grid_rotation": self.grid_rotation,
                "zoom_level": self.zoom_level,
                "xlim": list(self.canvas.ax.get_xlim()),
                "ylim": list(self.canvas.ax.get_ylim()),
                "use_latex": self.use_latex
            },
            "nodes": [],
            "edges": []
        }

        # Serialize nodes
        for node in self.nodes:
            node_data = {
                "node_id": node["node_id"],
                "label": node["label"],
                "pos": list(node["pos"]),
                "color": node["color"],
                "color_key": node["color_key"],
                "node_size_mult": node.get("node_size_mult", 1.0),
                "label_size_mult": node.get("label_size_mult", 1.0),
                "conj": node.get("conj", False),
                "nodelabelnudge": list(node.get("nodelabelnudge", (0.0, 0.0))),
                "outline_enabled": node.get("outline_enabled", False),
                "outline_color": node.get("outline_color", config.DEFAULT_NODE_OUTLINE_COLOR),
                "outline_width": node.get("outline_width", config.DEFAULT_NODE_OUTLINE_WIDTH),
                "outline_alpha": node.get("outline_alpha", config.DEFAULT_NODE_OUTLINE_ALPHA)
            }
            data["nodes"].append(node_data)

        # Serialize edges
        for edge in self.edges:
            edge_data = {
                "from_node_id": edge["from_node_id"],
                "to_node_id": edge["to_node_id"],
                "label1": edge.get("label1", ""),
                "label2": edge.get("label2", ""),
                "linewidth_mult": edge["linewidth_mult"],
                "label_size_mult": edge["label_size_mult"],
                "label_offset_mult": edge.get("label_offset_mult", 1.0),
                "style": edge["style"],
                "direction": edge["direction"],
                "is_self_loop": edge["is_self_loop"],
                "flip_labels": edge.get("flip_labels", False),
                "label_rotation_offset": edge.get("label_rotation_offset", 0),
                "looptheta": edge.get("looptheta", 30),
                "arrowstyle": edge.get("arrowstyle", "open"),
                "arrowscale": edge.get("arrowscale", 1.0)
            }
            # Add self-loop specific parameters
            if edge["is_self_loop"]:
                edge_data["selfloopangle"] = edge.get("selfloopangle", 0)
                edge_data["selfloopscale"] = edge.get("selfloopscale", 1.0)
                edge_data["arrowlengthsc"] = edge.get("arrowlengthsc", 1.0)
                edge_data["flip"] = edge.get("flip", False)
                edge_data["angle_pinned"] = edge.get("angle_pinned", False)
                edge_data["selflooplabelnudge"] = list(edge.get("selflooplabelnudge", (0.0, 0.0)))
                edge_data["label_bgcolor"] = edge.get("label_bgcolor", None)
            else:
                # Regular edge label background colors
                edge_data["label1_bgcolor"] = edge.get("label1_bgcolor", None)
                edge_data["label2_bgcolor"] = edge.get("label2_bgcolor", None)
            data["edges"].append(edge_data)

        return data

    def _deserialize_graph(self, data):
        """Deserialize graph from dictionary"""
        # Clear current graph
        self.nodes = []
        self.edges = []
        self.selected_nodes = []
        self.selected_edges = []
        self.undo_stack = []
        self.redo_stack = []

        # Restore view settings
        view = data.get("view", {})
        self.grid_type = view.get("grid_type", config.DEFAULT_GRID_TYPE)
        self.grid_rotation = view.get("grid_rotation", 0)
        self.zoom_level = view.get("zoom_level", 1.0)
        self.use_latex = view.get("use_latex", False)

        # Restore nodes
        node_id_map = {}  # Map from saved node_id to node object
        max_node_id = 0

        for node_data in data.get("nodes", []):
            node = {
                "node_id": node_data["node_id"],
                "label": node_data["label"],
                "pos": tuple(node_data["pos"]),
                "color": node_data["color"],
                "color_key": node_data["color_key"],
                "node_size_mult": node_data.get("node_size_mult", 1.0),
                "label_size_mult": node_data.get("label_size_mult", 1.0),
                "conj": node_data.get("conj", False),
                "nodelabelnudge": tuple(node_data.get("nodelabelnudge", (0.0, 0.0))),
                "outline_enabled": node_data.get("outline_enabled", False),
                "outline_color": node_data.get("outline_color", config.DEFAULT_NODE_OUTLINE_COLOR),
                "outline_width": node_data.get("outline_width", config.DEFAULT_NODE_OUTLINE_WIDTH),
                "outline_alpha": node_data.get("outline_alpha", config.DEFAULT_NODE_OUTLINE_ALPHA)
            }
            self.nodes.append(node)
            node_id_map[node_data["node_id"]] = node
            max_node_id = max(max_node_id, node_data["node_id"])

        # Update counters
        self.node_counter = len(self.nodes)
        self.node_id_counter = max_node_id + 1

        # Restore edges
        for edge_data in data.get("edges", []):
            from_node = node_id_map.get(edge_data["from_node_id"])
            to_node = node_id_map.get(edge_data["to_node_id"])

            if from_node and to_node:
                edge = {
                    "from_node": from_node,
                    "to_node": to_node,
                    "from_node_id": edge_data["from_node_id"],
                    "to_node_id": edge_data["to_node_id"],
                    "label1": edge_data.get("label1", ""),
                    "label2": edge_data.get("label2", ""),
                    "linewidth_mult": edge_data["linewidth_mult"],
                    "label_size_mult": edge_data["label_size_mult"],
                    "label_offset_mult": edge_data.get("label_offset_mult", 1.0),
                    "style": edge_data["style"],
                    "direction": edge_data["direction"],
                    "is_self_loop": edge_data["is_self_loop"],
                    "flip_labels": edge_data.get("flip_labels", False),
                    "label_rotation_offset": edge_data.get("label_rotation_offset", 0),
                    "looptheta": edge_data.get("looptheta", 30),
                    # Legacy literals, not config defaults: old files must
                    # render exactly as they did when saved
                    "arrowstyle": edge_data.get("arrowstyle", "open"),
                    "arrowscale": edge_data.get("arrowscale", 1.0)
                }
                # Restore self-loop specific parameters
                if edge_data["is_self_loop"]:
                    edge["selfloopangle"] = edge_data.get("selfloopangle", 0)
                    edge["selfloopscale"] = edge_data.get("selfloopscale", 1.0)
                    edge["arrowlengthsc"] = edge_data.get("arrowlengthsc", 1.0)
                    edge["flip"] = edge_data.get("flip", False)
                    edge["angle_pinned"] = edge_data.get("angle_pinned", False)
                    edge["selflooplabelnudge"] = tuple(edge_data.get("selflooplabelnudge", (0.0, 0.0)))
                    edge["label_bgcolor"] = edge_data.get("label_bgcolor", None)
                else:
                    # Restore regular edge label background colors
                    edge["label1_bgcolor"] = edge_data.get("label1_bgcolor", None)
                    edge["label2_bgcolor"] = edge_data.get("label2_bgcolor", None)
                self.edges.append(edge)

        # Auto-fit view to loaded graph (center and zoom to fit all objects)
        self._auto_fit_view()

    def _open_settings(self):
        """Open the Settings dialog (Ctrl+,)."""
        dialog = GraphulatorSettingsDialog(self)
        dialog.exec()

    def _new_graph(self):
        """Create a new graph"""
        if not self._check_unsaved_changes():
            return

        self.nodes = []
        self.edges = []
        self.selected_nodes = []
        self.selected_edges = []
        self.undo_stack = []
        self.redo_stack = []
        self.current_filepath = None
        self.node_counter = 0
        self.node_id_counter = 0

        # Reset view
        self.grid_type = config.DEFAULT_GRID_TYPE
        self.grid_rotation = 0
        self.zoom_level = 1.0
        self.canvas.ax.set_xlim(*config.DEFAULT_XLIM)
        self.canvas.ax.set_ylim(*config.DEFAULT_YLIM)

        self._set_modified(False)
        self._update_plot()
        logger.info("New graph created")

    def _open_graph(self):
        """Open a graph from file"""
        if not self._check_unsaved_changes():
            return

        filepath, _ = QFileDialog.getOpenFileName(
            self, "Open Graph", "", "Graph Files (*.graph);;All Files (*)"
        )

        if filepath:
            self._open_graph_file(filepath)


    def _export_png(self):
        """Export graph as PNG image"""
        if not self.nodes:
            logger.info("No nodes to export")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export PNG", "", "PNG Images (*.png);;All Files (*)"
        )

        if filepath:
            if not filepath.endswith('.png'):
                filepath += '.png'
            try:
                # Save current title
                current_title = self.canvas.ax.get_title()

                # Clear title for export
                self.canvas.ax.set_title('')

                # Redraw without grid
                self._update_plot_no_grid()

                # Crop tightly to the graph (labels included), not the full view.
                from . import clipboard_export
                bbox = clipboard_export.content_bbox_inches(self.canvas.fig)
                bbox_arg = bbox if bbox is not None else 'tight'

                # Export
                self.canvas.fig.savefig(filepath, dpi=300, bbox_inches=bbox_arg, transparent=True)

                # Restore title and redraw with grid
                self.canvas.ax.set_title(current_title)
                self._update_plot()

                logger.info(f"Exported PNG to {filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Could not export PNG:\n{e}")


    def _copy_graph_to_clipboard(self, include_png=True):
        """Copy the whole graph to the clipboard as vector PDF/SVG (+ PNG).

        Places several representations on the clipboard so it pastes with full
        vector fidelity into Keynote, PowerPoint, Illustrator, etc. When
        ``include_png`` is False the raster fallback is omitted (see
        :func:`clipboard_export.copy_figure_to_clipboard`).
        """
        from . import clipboard_export

        if not self.nodes:
            logger.info("No nodes to copy")
            self.statusBar().showMessage("No graph to copy", 3000)
            return

        try:
            # Match the look of the file exports: drop the title and grid.
            current_title = self.canvas.ax.get_title()
            self.canvas.ax.set_title('')
            self._update_plot_no_grid()

            backend, formats = clipboard_export.copy_figure_to_clipboard(
                self.canvas.fig, include_png=include_png
            )

            self.canvas.ax.set_title(current_title)
            self._update_plot()

            logger.info("Copied graph to clipboard via %s: %s", backend, formats)
            msg = "Graph copied to clipboard (vector only)" if not include_png \
                else "Graph copied to clipboard"
            self.statusBar().showMessage(msg, 3000)
        except Exception as e:
            logger.error("Could not copy graph to clipboard: %s", e)
            QMessageBox.critical(
                self, "Copy Error", f"Could not copy graph to clipboard:\n{e}"
            )

    def _export_svg(self):
        """Export graph as SVG image"""
        if not self.nodes:
            logger.info("No nodes to export")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export SVG", "", "SVG Images (*.svg);;All Files (*)"
        )

        if filepath:
            if not filepath.endswith('.svg'):
                filepath += '.svg'
            try:
                # Save current title
                current_title = self.canvas.ax.get_title()

                # Clear title for export
                self.canvas.ax.set_title('')

                # Redraw without grid
                self._update_plot_no_grid()

                # Crop tightly to the graph (labels included), not the full view.
                from . import clipboard_export
                bbox = clipboard_export.content_bbox_inches(self.canvas.fig)
                bbox_arg = bbox if bbox is not None else 'tight'

                # Render glyphs as outlined paths (svg.fonttype="path") so the
                # file is self-contained -- no CM/LaTeX fonts needed to view it.
                original_svg_fonttype = matplotlib.rcParams.get('svg.fonttype', 'path')
                matplotlib.rcParams['svg.fonttype'] = 'path'
                try:
                    self.canvas.fig.savefig(filepath, format='svg', bbox_inches=bbox_arg, transparent=True)
                finally:
                    matplotlib.rcParams['svg.fonttype'] = original_svg_fonttype

                # Restore title and redraw with grid
                self.canvas.ax.set_title(current_title)
                self._update_plot()

                logger.info(f"Exported SVG to {filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Could not export SVG:\n{e}")

    def _export_pdf(self):
        """Export graph as PDF document"""
        if not self.nodes:
            logger.info("No nodes to export")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export PDF", "", "PDF Documents (*.pdf);;All Files (*)"
        )

        if filepath:
            if not filepath.endswith('.pdf'):
                filepath += '.pdf'
            try:
                # Save current title
                current_title = self.canvas.ax.get_title()

                # Clear title for export
                self.canvas.ax.set_title('')

                # Redraw without grid
                self._update_plot_no_grid()

                # Crop tightly to the graph (labels included), not the full view.
                from . import clipboard_export
                bbox = clipboard_export.content_bbox_inches(self.canvas.fig)
                bbox_arg = bbox if bbox is not None else 'tight'

                # Build the PDF from the *outlined* SVG so its text is paths, not
                # font-referencing glyphs. This is what lets Illustrator (which
                # imports the PDF) show the labels without Computer Modern
                # installed. Falls back to matplotlib's font-embedded PDF if no
                # SVG->PDF converter is available.
                import io
                svg_buffer = io.BytesIO()
                original_svg_fonttype = matplotlib.rcParams.get('svg.fonttype', 'path')
                matplotlib.rcParams['svg.fonttype'] = 'path'
                try:
                    self.canvas.fig.savefig(svg_buffer, format='svg', bbox_inches=bbox_arg, transparent=True)
                finally:
                    matplotlib.rcParams['svg.fonttype'] = original_svg_fonttype

                pdf_bytes = clipboard_export.svg_bytes_to_pdf(svg_buffer.getvalue())
                if pdf_bytes is not None:
                    with open(filepath, 'wb') as f:
                        f.write(pdf_bytes)
                    logger.info(f"Exported PDF with outlined text to {filepath}")
                else:
                    # No SVG->PDF converter available: matplotlib PDF (fonts embedded)
                    original_fonttype = matplotlib.rcParams.get('pdf.fonttype', 42)
                    matplotlib.rcParams['pdf.fonttype'] = 42
                    try:
                        self.canvas.fig.savefig(filepath, format='pdf', bbox_inches=bbox_arg, dpi=300, transparent=True)
                    finally:
                        matplotlib.rcParams['pdf.fonttype'] = original_fonttype
                    logger.info(f"Exported PDF (fonts embedded) to {filepath}")

                # Restore title and redraw with grid
                self.canvas.ax.set_title(current_title)
                self._update_plot()

                logger.info(f"Exported PDF to {filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Could not export PDF:\n{e}")

    def closeEvent(self, event):
        """Handle window close event"""
        if self._check_unsaved_changes():
            # Save last graph automatically (for session restore)
            try:
                data = self._serialize_graph()
                with open(self.last_graph_path, 'w') as f:
                    json.dump(data, f, indent=2)
            except Exception:
                logger.exception("Failed to autosave last graph on close")
                reply = QMessageBox.warning(
                    self, "Autosave Failed",
                    "The session autosave failed, so this graph won't be "
                    "restored next launch.\n\nClose anyway?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply == QMessageBox.No:
                    event.ignore()
                    return

            event.accept()
        else:
            event.ignore()


    def _auto_increment_label(self, label):
        """Auto-increment a label based on its pattern

        Examples:
        - 'A' -> 'B', 'Z' -> 'AA'
        - 'A_1' -> 'A_2', 'A_9' -> 'A_{10}'
        - '1' -> '2', '99' -> '100'
        """
        import re

        # Pattern 1: Letter with underscore and number (e.g., 'A_1', 'B_12')
        match = re.match(r'^([A-Za-z]+)_(\d+)$', label)
        if match:
            prefix = match.group(1)
            num = int(match.group(2))
            next_num = num + 1
            # Use braces for multi-digit numbers
            if next_num >= 10:
                return f"{prefix}_{{{next_num}}}"
            else:
                return f"{prefix}_{next_num}"

        # Pattern 2: Pure number (e.g., '1', '42')
        match = re.match(r'^(\d+)$', label)
        if match:
            num = int(match.group(1))
            return str(num + 1)

        # Pattern 3: Pure letter(s) (e.g., 'A', 'Z', 'AA')
        match = re.match(r'^([A-Z]+)$', label)
        if match:
            letters = match.group(1)
            # Convert to number, increment, convert back
            # A=1, B=2, ..., Z=26, AA=27, etc.
            num = 0
            for char in letters:
                num = num * 26 + (ord(char) - ord('A') + 1)
            num += 1

            # Convert back to letters
            result = ''
            while num > 0:
                num -= 1
                result = chr(ord('A') + (num % 26)) + result
                num //= 26
            return result

        # Pattern 4: lowercase letters
        match = re.match(r'^([a-z]+)$', label)
        if match:
            letters = match.group(1)
            num = 0
            for char in letters:
                num = num * 26 + (ord(char) - ord('a') + 1)
            num += 1

            result = ''
            while num > 0:
                num -= 1
                result = chr(ord('a') + (num % 26)) + result
                num //= 26
            return result

        # If no pattern matches, just return the original label
        return label

    def _toggle_continuous_duplicate_mode(self):
        """Toggle continuous duplicate placement mode"""
        if self.placement_mode == 'continuous_duplicate':
            self.placement_mode = None
            logger.debug("Exited continuous duplicate mode")
        else:
            # If no previous node, use the configured defaults
            if self.last_node_props is None:
                self.last_node_props = {
                    'label': '',  # Empty string signals to use 'A' for first node
                    'color': config.MYCOLORS.get(config.DEFAULT_NODE_COLOR_KEY,
                                                 config.DEFAULT_NODE_COLOR),
                    'color_key': config.DEFAULT_NODE_COLOR_KEY,
                    'node_size_mult': 1.0,  # Medium
                    'label_size_mult': 1.4,  # Large
                    'conj': False
                }
                logger.debug("Continuous duplicate mode - starting with 'A'")
            else:
                logger.debug(f"Continuous duplicate mode - duplicating '{self.last_node_props['label']}' ({self.last_node_props['color_key']}) with auto-increment")

            self.placement_mode = 'continuous_duplicate'
            logger.debug("Click to place nodes, press Ctrl+G again to exit")
        self._update_plot()

    def _toggle_conjugation_mode(self):
        """Toggle conjugation mode or toggle selected nodes"""
        # If nodes are selected, toggle their conjugation directly
        if self.selected_nodes:
            self._save_state()
            for node in self.selected_nodes:
                node['conj'] = not node.get('conj', False)
            conj_count = sum(1 for node in self.selected_nodes if node.get('conj', False))
            logger.debug(f"Toggled conjugation for {len(self.selected_nodes)} node(s) ({conj_count} now conjugated)")
            self._update_plot()
        # Otherwise, enter/exit conjugation mode
        elif self.placement_mode == 'conjugation':
            self.placement_mode = None
            logger.debug("Exited conjugation mode")
            self._update_plot()
        else:
            self.placement_mode = 'conjugation'
            logger.debug("Conjugation mode - click nodes to toggle conjugation ('c' or Esc to exit)")
            self._update_plot()

    def _toggle_edge_mode(self):
        """Enter single edge placement mode (exits after one edge)"""
        self.placement_mode = 'edge'
        self.edge_mode_first_node = None
        logger.debug("Edge mode - click two nodes to connect them (single edge, exits after placement)")
        self._update_plot()

    def _toggle_edge_continuous_mode(self):
        """Toggle continuous edge mode (stays active, uses last edge settings)"""
        if self.placement_mode == 'edge_continuous':
            self.placement_mode = None
            self.edge_mode_first_node = None
            logger.debug("Exited continuous edge mode")
            self._update_plot()
        else:
            self.placement_mode = 'edge_continuous'
            self.edge_mode_first_node = None
            logger.debug("Continuous edge mode - click nodes to connect them (Ctrl+E to exit)")
            self._update_plot()

    def _exit_placement_mode(self):
        """Exit any placement mode and clear selections"""
        # Cancel any active dragging operations
        if self.dragging_node is not None:
            logger.debug("Cancelled node drag")
            self.dragging_node = None
            self.dragging_group = False
            self.drag_start_pos = None
            self._update_plot()
            return

        if self.placement_mode is not None:
            logger.debug(f"Exited {self.placement_mode} mode")
            self.placement_mode = None
            # Clear edge mode state if exiting edge mode
            if self.edge_mode_first_node is not None:
                self.edge_mode_first_node = None
            self._update_plot()
        elif self.selected_nodes or self.selected_edges:
            logger.debug(f"Cleared selection of {len(self.selected_nodes)} node(s) and {len(self.selected_edges)} edge(s)")
            self.selected_nodes.clear()
            self.selected_edges.clear()
            self._update_plot()


    def _show_edge_context_menu(self, _event, edge):
        """Show context menu for edge type selection"""
        # Select the edge if not already selected
        if edge not in self.selected_edges:
            self.selected_edges.clear()
            self.selected_edges.append(edge)
            self.selected_nodes.clear()  # Clear node selection when selecting edge
            self._update_plot()

        # Create context menu
        menu = QMenu(self)

        # Add edge type options
        for edge_type in ['loopy', 'single', 'double']:
            action = menu.addAction(edge_type.capitalize())
            action.triggered.connect(lambda _, t=edge_type, e=edge: self._change_edge_type(e, t))

        # Arrowhead style submenu (current style checked)
        arrow_menu = menu.addMenu("Arrowhead")
        current_style = edge.get('arrowstyle', 'open')
        for arrow_style in ['open', 'filled', 'stealth']:
            action = arrow_menu.addAction(arrow_style.capitalize())
            action.setCheckable(True)
            action.setChecked(arrow_style == current_style)
            action.triggered.connect(
                lambda _, s=arrow_style, e=edge: self._change_edge_arrowstyle(e, s))

        # Show menu at mouse position
        menu.exec(QCursor.pos())

    def _change_edge_arrowstyle(self, edge, arrow_style):
        """Change the arrowhead style of an edge (or all selected edges)"""
        self._save_state()

        if edge in self.selected_edges and len(self.selected_edges) > 1:
            for selected_edge in self.selected_edges:
                selected_edge['arrowstyle'] = arrow_style
            logger.debug(f"Changed arrowhead of {len(self.selected_edges)} edge(s) to {arrow_style}")
        else:
            edge['arrowstyle'] = arrow_style
            logger.debug(f"Changed edge arrowhead to {arrow_style}")

        self._update_plot()

    def _change_edge_type(self, edge, edge_type):
        """Change the type of an edge (or all selected edges if multiple selected)"""
        self._save_state()

        # If the clicked edge is in selection, change all selected edges
        if edge in self.selected_edges and len(self.selected_edges) > 1:
            for selected_edge in self.selected_edges:
                selected_edge['style'] = edge_type
            logger.debug(f"Changed type of {len(self.selected_edges)} edge(s) to {edge_type}")
        else:
            # Change just this edge
            edge['style'] = edge_type
            logger.debug(f"Changed edge type to {edge_type}")

        self._update_plot()

    def _toggle_flip_labels(self):
        """Toggle flip_labels for selected edges using 'f' key"""
        if not self.selected_edges:
            return

        self._save_state()

        for edge in self.selected_edges:
            current = edge.get('flip_labels', False)
            edge['flip_labels'] = not current

        # Print feedback
        if len(self.selected_edges) == 1:
            edge = self.selected_edges[0]
            state = "flipped" if edge['flip_labels'] else "normal"
            logger.debug(f"Edge labels: {state}")
        else:
            flipped_count = sum(1 for e in self.selected_edges if e.get('flip_labels', False))
            logger.debug(f"Toggled flip for {len(self.selected_edges)} edge(s) ({flipped_count} now flipped)")

        self._update_plot()


    def _zoom(self, factor):
        """Zoom by factor"""
        self.zoom_level *= factor
        logger.debug(f"Zoom level: {self.zoom_level:.3f}x")
        self._update_plot()

    def _pan_arrow(self, direction):
        """Pan view using arrow keys, or adjust node/edge properties if selected"""
        # If in edge rotation mode, adjust label rotation
        if self.edge_rotation_mode and self.selected_edges and direction in ['left', 'right']:
            self._adjust_edge_rotation(direction)
            return

        # If nodes are selected, adjust their size instead of panning
        if self.selected_nodes:
            self._adjust_node_size(direction)
            return

        # If edges are selected, adjust their properties instead of panning
        if self.selected_edges:
            self._adjust_edge_properties(direction)
            return

        # Otherwise, pan the view
        xlim = self._get_xlim()
        ylim = self._get_ylim()

        # Pan by 10% of current view width/height
        pan_amount_x = (xlim[1] - xlim[0]) * 0.1
        pan_amount_y = (ylim[1] - ylim[0]) * 0.1

        if direction == 'left':
            self.base_xlim = (self.base_xlim[0] - pan_amount_x, self.base_xlim[1] - pan_amount_x)
        elif direction == 'right':
            self.base_xlim = (self.base_xlim[0] + pan_amount_x, self.base_xlim[1] + pan_amount_x)
        elif direction == 'up':
            self.base_ylim = (self.base_ylim[0] + pan_amount_y, self.base_ylim[1] + pan_amount_y)
        elif direction == 'down':
            self.base_ylim = (self.base_ylim[0] - pan_amount_y, self.base_ylim[1] - pan_amount_y)

        # Fast view-only update (pan doesn't change zoom, so no scene rebuild)
        self._apply_view_fast()

    def _adjust_node_size(self, direction):
        """Adjust node size or label size for selected nodes"""
        if not self.selected_nodes:
            return

        self._save_state()

        # Use increment of 0.2 for smooth adjustment
        increment = 0.2

        for node in self.selected_nodes:
            if direction == 'up':
                # Increase node size
                current = node.get('node_size_mult', 1.0)
                node['node_size_mult'] = min(current + increment, 3.0)  # Cap at 3.0
            elif direction == 'down':
                # Decrease node size
                current = node.get('node_size_mult', 1.0)
                node['node_size_mult'] = max(current - increment, 0.2)  # Min at 0.2
            elif direction == 'left':
                # Decrease label size
                current = node.get('label_size_mult', 1.0)
                node['label_size_mult'] = max(current - increment, 0.2)  # Min at 0.2
            elif direction == 'right':
                # Increase label size
                current = node.get('label_size_mult', 1.0)
                node['label_size_mult'] = min(current + increment, 3.0)  # Cap at 3.0

        # Print feedback
        if len(self.selected_nodes) == 1:
            node = self.selected_nodes[0]
            if direction in ['up', 'down']:
                logger.debug(f"Node '{node['label']}' size: {node['node_size_mult']:.1f}")
            else:
                logger.debug(f"Node '{node['label']}' label size: {node['label_size_mult']:.1f}")
        else:
            if direction in ['up', 'down']:
                logger.debug(f"Adjusted node size for {len(self.selected_nodes)} nodes")
            else:
                logger.debug(f"Adjusted label size for {len(self.selected_nodes)} nodes")

        self._update_plot()


    def _nudge_label(self, direction):
        """Nudge node label position for selected nodes, or edge label offset for edges"""
        # If edges are selected, check if they are self-loops
        if self.selected_edges:
            # Check if any selected edges are self-loops
            has_selfloop = any(edge.get('is_self_loop', False) for edge in self.selected_edges)
            if has_selfloop:
                self._nudge_selfloop_label(direction)
            else:
                self._adjust_edge_label_offset(direction)
            return

        if not self.selected_nodes:
            return

        self._save_state()

        # Calculate nudge increment: 0.02 × diameter
        # diameter = 2 × radius × node_size_mult
        # Use reference node radius from config
        base_diameter = 2 * self.node_radius

        for node in self.selected_nodes:
            # Get current nudge (default to (0, 0))
            current_nudge = node.get('nodelabelnudge', (0.0, 0.0))
            node_size_mult = node.get('node_size_mult', 1.0)

            # Calculate increment based on this node's actual diameter
            diameter = base_diameter * node_size_mult
            increment = 0.01 * diameter

            # Update nudge based on direction
            nudge_x, nudge_y = current_nudge
            if direction == 'left':
                nudge_x -= increment
            elif direction == 'right':
                nudge_x += increment
            elif direction == 'up':
                nudge_y += increment
            elif direction == 'down':
                nudge_y -= increment

            node['nodelabelnudge'] = (nudge_x, nudge_y)

        # Print feedback
        if len(self.selected_nodes) == 1:
            node = self.selected_nodes[0]
            nudge = node['nodelabelnudge']
            logger.debug(f"Node '{node['label']}' label nudge: ({nudge[0]:.3f}, {nudge[1]:.3f})")
        else:
            logger.debug(f"Nudged labels for {len(self.selected_nodes)} nodes")

        self._update_plot()

    def _adjust_edge_properties(self, direction):
        """Adjust edge thickness or label size for selected edges"""
        if not self.selected_edges:
            return

        self._save_state()

        for edge in self.selected_edges:
            # Use larger increments for loopy style edges
            is_loopy = edge.get('style', 'loopy') == 'loopy'
            linewidth_increment = 0.2 if is_loopy else 0.1

            if direction == 'up':
                # Increase linewidth
                current = edge.get('linewidth_mult', 1.5)
                edge['linewidth_mult'] = min(current + linewidth_increment, 3.0)
            elif direction == 'down':
                # Decrease linewidth
                current = edge.get('linewidth_mult', 1.5)
                edge['linewidth_mult'] = max(current - linewidth_increment, 0.2)
            elif direction == 'left':
                # Decrease label size
                current = edge.get('label_size_mult', 1.4)
                edge['label_size_mult'] = max(current - 0.1, 0.5)
            elif direction == 'right':
                # Increase label size
                current = edge.get('label_size_mult', 1.4)
                edge['label_size_mult'] = min(current + 0.1, 3.0)

        # Print feedback
        if len(self.selected_edges) == 1:
            edge = self.selected_edges[0]
            if direction in ['up', 'down']:
                logger.debug(f"Edge linewidth: {edge['linewidth_mult']:.1f}")
            else:
                logger.debug(f"Edge label size: {edge['label_size_mult']:.1f}")
        else:
            logger.debug(f"Adjusted properties for {len(self.selected_edges)} edge(s)")

        self._update_plot()

    def _arrow_key_action(self, direction):
        """Handle Up/Down arrow keys - adjust self-loop linewidth if self-loop selected, otherwise pan"""
        # Check if a single self-loop is selected
        if len(self.selected_edges) == 1 and self.selected_edges[0].get('is_self_loop', False):
            self._adjust_selfloop_linewidth(direction)
        else:
            self._pan_arrow(direction)

    def _adjust_selfloop_linewidth(self, direction):
        """Adjust self-loop linewidth using Up/Down keys (20% increments)"""
        if not self.selected_edges or not self.selected_edges[0].get('is_self_loop', False):
            return

        self._save_state()
        edge = self.selected_edges[0]

        current = edge.get('linewidth_mult', 1.5)
        increment = current * 0.2  # 20% of current value

        if direction == 'up':
            edge['linewidth_mult'] = min(current + increment, 8.0)
        elif direction == 'down':
            edge['linewidth_mult'] = max(current - increment, 0.2)

        logger.debug(f"Self-loop linewidth: {edge['linewidth_mult']:.3f}")
        self._update_plot()

    def _adjust_selfloop_scale(self, action):
        """Adjust self-loop scale using Ctrl+Up/Down (20% increments)"""
        if not self.selected_edges:
            return

        # Filter to only self-loops
        selfloops = [e for e in self.selected_edges if e.get('is_self_loop', False)]
        if not selfloops:
            return

        self._save_state()

        for edge in selfloops:
            current = edge.get('selfloopscale', 1.0)
            increment = current * 0.2  # 20% of current value

            if action == 'increase':
                edge['selfloopscale'] = min(current + increment, 3.0)
            elif action == 'decrease':
                edge['selfloopscale'] = max(current - increment, 0.3)

        if len(selfloops) == 1:
            logger.debug(f"Self-loop scale: {selfloops[0]['selfloopscale']:.3f}")
        else:
            logger.debug(f"Adjusted scale for {len(selfloops)} self-loop(s)")

        self._update_plot()


    def _draw_grid(self):
        """Draw the grid overlay"""
        if self.grid_type == "square":
            self._draw_square_grid()
        else:
            self._draw_triangular_grid()


    def _edit_node(self, node):
        """Edit an existing node"""
        logger.debug(f"Editing node '{node['label']}'...")

        # Create dialog with current values
        dialog = NodeInputDialog(default_label=node['label'], parent=self)

        # Set current values
        try:
            color_idx = list(config.MYCOLORS.keys()).index(node['color_key'])
            dialog.color_combo.setCurrentIndex(color_idx)
        except:
            pass

        # Map multipliers back to size names
        size_map = {0.6: 'Small', 1.0: 'Medium', 1.4: 'Large', 1.8: 'X-Large'}
        node_size_mult = node.get('node_size_mult', 1.0)
        label_size_mult = node.get('label_size_mult', 1.0)

        node_size_name = size_map.get(node_size_mult, 'Medium')
        label_size_name = size_map.get(label_size_mult, 'Large')

        dialog.node_size_combo.setCurrentText(node_size_name)
        dialog.label_size_combo.setCurrentText(label_size_name)

        # Set current conjugation state
        conj = node.get('conj', False)
        dialog.conj_checkbox.setChecked(conj)

        if dialog.exec() == QDialog.Accepted:
            result = dialog.get_result()
            if result:
                self._save_state()

                # Update node properties
                node['label'] = result['label']
                node['color'] = result['color']
                node['color_key'] = result['color_key']
                node['node_size_mult'] = result['node_size_mult']
                node['label_size_mult'] = result['label_size_mult']
                node['conj'] = result['conj']

                # Update last_node_props so continuous mode inherits these properties
                self.last_node_props = {
                    'label': result['label'],
                    'color': result['color'],
                    'color_key': result['color_key'],
                    'node_size_mult': result['node_size_mult'],
                    'label_size_mult': result['label_size_mult'],
                    'conj': result['conj']
                }

                logger.info(f"✓ Updated node to '{result['label']}' ({result['color_key']})")
                self._update_plot()

    def _edit_edge(self, edge):
        """Edit an existing edge"""
        from_label = edge['from_node']['label']
        to_label = edge['to_node']['label']
        is_self_loop = edge['is_self_loop']

        logger.debug(f"Editing edge '{from_label}' → '{to_label}'...")

        # Create dialog with current values
        dialog = EdgeInputDialog(
            node1_label=from_label,
            node2_label=to_label,
            is_self_loop=is_self_loop,
            parent=self
        )

        # Set current labels
        dialog.label1_input.setText(edge.get('label1', ''))
        dialog.label2_input.setText(edge.get('label2', ''))

        # Map multipliers back to size names (use closest match for floating point safety)
        def find_closest_key(value, mapping):
            return min(mapping.keys(), key=lambda k: abs(k - value))

        linewidth_mult = edge.get('linewidth_mult', 1.0)
        label_size_mult = edge.get('label_size_mult', 1.0)
        label_offset_mult = edge.get('label_offset_mult', 1.0)

        # lw_map = {1.0: 'Thin', 1.5: 'Medium', 2.0: 'Thick', 2.5: 'X-Thick'}
        # label_size_map = {1.0: 'Small', 1.4: 'Medium', 1.8: 'Large', 2.5: 'X-Large', 3.0: 'XX-Large'}
        # label_offset_map = {0.5: 'Close', 0.8: 'Medium', 1.2: 'Far'}
        lw_map = {1.0: 'Thin', 1.5: 'Medium', 2.0: 'Thick', 2.5: 'X-Thick'}
        label_size_map = {1.0: 'Small', 1.4: 'Medium', 1.8: 'Large', 2.5: 'X-Large', 3.0: 'XX-Large'}
        label_offset_map = {0.5: 'Close', 0.8: 'Medium', 1.2: 'Far'}

        lw_name = lw_map[find_closest_key(linewidth_mult, lw_map)]
        label_size_name = label_size_map[find_closest_key(label_size_mult, label_size_map)]
        label_offset_name = label_offset_map[find_closest_key(label_offset_mult, label_offset_map)]

        dialog.lw_combo.setCurrentText(lw_name)
        dialog.label_size_combo.setCurrentText(label_size_name)
        dialog.label_offset_combo.setCurrentText(label_offset_name)
        if dialog.style_combo:
            dialog.style_combo.setCurrentText(edge['style'])
        if not is_self_loop and dialog.dir_combo:
            dialog.dir_combo.setCurrentText(edge['direction'])
        # Set looptheta for regular edges
        if not is_self_loop and hasattr(dialog, 'looptheta_spinbox') and dialog.looptheta_spinbox:
            dialog.looptheta_spinbox.setValue(edge.get('looptheta', 30))

        # Set self-loop specific values if applicable
        if is_self_loop and dialog.angle_combo and dialog.scale_combo and dialog.flip_loop_checkbox:
            selfloopangle = edge.get('selfloopangle', 0)
            # Find matching angle option
            angle_options = ['0° (Right)', '45° (Up-Right)', '90° (Up)', '135° (Up-Left)',
                           '180° (Left)', '225° (Down-Left)', '270° (Down)', '315° (Down-Right)']
            for i, option in enumerate(angle_options):
                if int(option.split('°')[0]) == selfloopangle:
                    dialog.angle_combo.setCurrentIndex(i)
                    break

            selfloopscale = edge.get('selfloopscale', 1.0)
            scale_map_reverse = {0.7: 0, 1.0: 1, 1.3: 2, 1.6: 3}
            closest_scale = min(scale_map_reverse.keys(), key=lambda x: abs(x - selfloopscale))
            dialog.scale_combo.setCurrentIndex(scale_map_reverse[closest_scale])

            dialog.flip_loop_checkbox.setChecked(edge.get('flip', False))

        # Set flip labels checkbox to current value
        dialog.flip_labels_checkbox.setChecked(edge.get('flip_labels', False))

        if dialog.exec() == QDialog.Accepted:
            result = dialog.get_result()
            if result:
                self._save_state()

                # Update edge properties
                edge['label1'] = result['label1']
                edge['label2'] = result['label2']
                edge['linewidth_mult'] = result['linewidth_mult']
                edge['label_size_mult'] = result['label_size_mult']
                edge['label_offset_mult'] = result['label_offset_mult']
                edge['style'] = result['style']
                edge['direction'] = result['direction']
                edge['flip_labels'] = result.get('flip_labels', False)

                # Update looptheta for regular edges
                if not is_self_loop:
                    edge['looptheta'] = result.get('looptheta', 30)

                # Update self-loop specific properties
                if is_self_loop:
                    edge['selfloopangle'] = result.get('selfloopangle', 0)
                    edge['selfloopscale'] = result.get('selfloopscale', 1.0)
                    edge['arrowlengthsc'] = result.get('arrowlengthsc', 1.0)
                    edge['flip'] = result.get('flip', False)

                if is_self_loop:
                    logger.info(f"✓ Updated self-loop on node '{from_label}'")
                else:
                    logger.info(f"✓ Updated edge '{from_label}' → '{to_label}'")
                logger.debug(f"  linewidth_mult={edge['linewidth_mult']}, label_size_mult={edge['label_size_mult']}, style={edge['style']}")
                self._update_plot()

    def _draw_nodes(self):
        """Draw all nodes"""
        # Calculate scaling factor once for all nodes
        fig = self.canvas.fig
        ax = self.canvas.ax
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()

        # Get figure size in inches and pixels
        fig_width_inches = fig.get_figwidth()
        fig_height_inches = fig.get_figheight()

        # Calculate points per data unit using average of x and y to handle aspect ratio
        fig_width_points = fig_width_inches * 72  # 72 points per inch
        fig_height_points = fig_height_inches * 72

        # For GUI: Use actual axis limits so fonts scale with zoom
        # This makes text size relative to nodes consistent when zooming
        data_width = xlim[1] - xlim[0]
        data_height = ylim[1] - ylim[0]
        points_per_data_unit_x = fig_width_points / data_width
        points_per_data_unit_y = fig_height_points / data_height
        # Use minimum to ensure font scales with the tighter dimension
        # This keeps text size consistent relative to nodes regardless of aspect ratio
        points_per_data_unit = min(points_per_data_unit_x, points_per_data_unit_y)

        for node in self.nodes:
            # Get size multipliers (default to 1.0 for old nodes without these fields)
            node_size_mult = node.get('node_size_mult', 1.0)
            label_size_mult = node.get('label_size_mult', 1.0)
            conj = node.get('conj', False)

            # Draw circle with size multiplier (no outline, like prettynodes)
            node_radius = self.node_radius * node_size_mult

            # Apply the conjugated-node convention (config-driven)
            if conj and config.CONJ_NODE_FILL_MODE == 'transparent':
                # Unfilled node with a colored ring
                ring_lw = 2.5 * node_size_mult * (points_per_data_unit / 43.0)
                circle = patches.Circle(
                    node['pos'], node_radius,
                    facecolor='none',
                    edgecolor=node['color'],
                    linewidth=ring_lw,
                    zorder=10
                )
            else:
                node_alpha = config.CONJ_NODE_FILL_ALPHA if conj else 1.0
                circle = patches.Circle(
                    node['pos'], node_radius,
                    facecolor=node['color'],
                    edgecolor='none',
                    alpha=node_alpha,
                    zorder=10
                )
            self.canvas.ax.add_patch(circle)

            # Draw custom outline if enabled (same convention as Paragraphulator)
            if node.get('outline_enabled', False):
                outline_circle = patches.Circle(
                    node['pos'], node_radius,
                    fill=False,
                    edgecolor=node.get('outline_color', config.DEFAULT_NODE_OUTLINE_COLOR),
                    linewidth=node.get('outline_width', config.DEFAULT_NODE_OUTLINE_WIDTH),
                    alpha=node.get('outline_alpha', config.DEFAULT_NODE_OUTLINE_ALPHA),
                    zorder=10.5  # on top of the fill, below labels
                )
                self.canvas.ax.add_patch(outline_circle)

            # Font size should be proportional to node radius
            # Aim for text to be about 35% of node diameter
            # Reduce size by 8% for conjugated nodes to accommodate asterisk
            conj_scale = config.CONJ_LABEL_SCALE if conj else 1.0
            font_size_points = node_radius * 2 * points_per_data_unit * 0.35 * label_size_mult * conj_scale

            # Draw label - use bold sans-serif text with proper subscript/superscript handling
            label_text = node['label']

            # Skip drawing label if it's empty or whitespace only
            if not label_text or not label_text.strip():
                continue

            # Format label with bold sans-serif, handling subscripts/superscripts
            # Split on _ and ^ while keeping the delimiters
            import re
            parts = re.split(r'([_^])', label_text)

            # Choose font command based on rendering mode
            if self.use_latex:
                # LaTeX with sfmath: just use \mathbf (sfmath provides sans-serif)
                def apply_font(text):
                    return r'\mathbf{' + text + '}'
            else:
                # MathText: use \mathbf{\mathsf{...}} explicitly
                def apply_font(text):
                    return r'\mathbf{\mathsf{' + text + '}}'

            formatted_parts = []
            i = 0
            while i < len(parts):
                if parts[i] in ['_', '^']:
                    # This is a sub/superscript operator
                    formatted_parts.append(parts[i])
                    i += 1
                    if i < len(parts):
                        # Next part is the sub/superscript content
                        content = parts[i]
                        if content.startswith('{') and content.endswith('}'):
                            # Already has braces, apply font to inner content
                            inner = content[1:-1]
                            formatted_parts.append('{' + apply_font(inner) + '}')
                        else:
                            # Single character, wrap it
                            formatted_parts.append(apply_font(content))
                        i += 1
                elif parts[i]:  # Non-empty part
                    # Regular text, apply font
                    formatted_parts.append(apply_font(parts[i]))
                    i += 1
                else:
                    i += 1

            formatted_label = ''.join(formatted_parts)

            # Add conjugation marker with proper formatting
            if conj:
                # Use asterisk (not superscripted) for conjugation
                formatted_text = rf"${formatted_label}\ast$"
            else:
                formatted_text = rf"${formatted_label}$"

            # For better centering of capital letters:
            # Empirically, for LaTeX math mode bold sans-serif, the visual center
            # is better approximated by using va='center' with a small downward adjustment
            # Math mode adds extra vertical space, so we compensate

            # Small adjustment factor - tune this to improve centering
            # Positive values move text down, negative values move text up
            adjustment_fraction = 0.05  # 5% of font size downward (base)

            vertical_adjustment_points = font_size_points * adjustment_fraction
            vertical_adjustment_data = vertical_adjustment_points / points_per_data_unit

            # Apply label nudge if present
            # Nudge should be relative to the base position, then apply vertical adjustment
            nudge = node.get('nodelabelnudge', (0.0, 0.0))
            label_x = node['pos'][0] + nudge[0]
            label_y = node['pos'][1] + nudge[1] - vertical_adjustment_data

            # Draw the label via the cached vector glyph-path renderer so it stays
            # crisp and fast across pan/zoom (no per-frame layout recompilation).
            # Transparent conjugated nodes have no fill, so the default white
            # label would vanish; use the node color instead
            if conj and config.CONJ_NODE_FILL_MODE == 'transparent':
                default_label_color = node['color']
            else:
                default_label_color = config.DEFAULT_NODE_LABEL_COLOR
            self._label_cache.draw(
                self.canvas.ax, formatted_text, label_x, label_y,
                fontsize_points=font_size_points,
                points_per_data_unit=points_per_data_unit,
                color=node.get('label_color', default_label_color),
                ha='center', va='center',
                usetex=self.use_latex, zorder=11,
            )

            # Draw selection indicator
            if node in self.selected_nodes:
                # Calculate linewidth for selection ring
                selection_linewidth = node_radius * 2 * points_per_data_unit * 0.04
                selection_ring = patches.Circle(
                    node['pos'], node_radius * 1.3,
                    fill=False, edgecolor='lightcoral', linewidth=selection_linewidth,
                    linestyle='-', zorder=12
                )
                self.canvas.ax.add_patch(selection_ring)

    def _draw_edges(self):
        """Draw all edges and self-loops"""

        # Debug: verify this is being called

        # Calculate scaling factor for edges (same as nodes)
        fig = self.canvas.fig
        ax = self.canvas.ax
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()

        # Get figure size in points
        fig_width_inches = fig.get_figwidth()
        fig_height_inches = fig.get_figheight()
        fig_width_points = fig_width_inches * 72
        fig_height_points = fig_height_inches * 72

        # Calculate points per data unit
        data_width = xlim[1] - xlim[0]
        data_height = ylim[1] - ylim[0]
        points_per_data_unit_x = fig_width_points / data_width
        points_per_data_unit_y = fig_height_points / data_height
        points_per_data_unit = min(points_per_data_unit_x, points_per_data_unit_y)

        # Base values calibrated for reference view (figsize=12, span~20 units)
        # This gives points_per_data_unit ≈ 43 for that reference
        reference_points_per_data_unit = 43.0

        for edge_index, edge in enumerate(self.edges):
            from_node = edge['from_node']
            to_node = edge['to_node']

            if edge['is_self_loop']:
                # Draw self-loop using graph_primitives selfloop function
                from_pos = from_node['pos']
                from_radius = self.node_radius * from_node.get('node_size_mult', 1.0)

                # Scale linewidth proportionally to zoom (base 2.5 at reference zoom)
                base_lw = 2.5
                scaled_lw = base_lw * edge['linewidth_mult'] * (points_per_data_unit / reference_points_per_data_unit)

                # Self-loop parameters following graph_primitives conventions
                selfloopscale = edge.get('selfloopscale', 1.0)
                LOOPYSCALE = 6 * selfloopscale
                selfloopangle = edge.get('selfloopangle', 0)  # Default 0 = right-pointing
                arrowlengthsc = edge.get('arrowlengthsc', 1.0)

                # Calculate loopR based on node radius (matches graph_primitives)
                loopR = from_radius * LOOPYSCALE

                # Calculate arrowlength (matches graph_primitives formula)
                arrowlength = from_radius / 2 * 2.25 / 4 * arrowlengthsc

                # Draw the self-loop arc
                gp.selfloop(
                    ax=self.canvas.ax,
                    nodecent=from_pos,
                    R=from_radius * 1.2,  # graph_primitives uses R*1.2
                    baseangle=selfloopangle,
                    dtheta=-34,  # Matches graph_primitives
                    loopR=loopR,
                    arrowlength=arrowlength,
                    lw=scaled_lw,
                    color=edge.get('color', 'black'),
                    flip=edge.get('flip', False),
                    arrowstyle=edge.get('arrowstyle', 'open'),
                    arrowscale=edge.get('arrowscale', 1.0),
                    arrowopenang=config.ARROWHEAD_OPEN_ANGLE,
                    gid=f'edge_{edge_index}'
                )

                # Draw self-loop label manually if present (use label1 for self-loops)
                selfloop_label = edge.get('label1', '')
                if selfloop_label and selfloop_label.strip():
                    # Calculate label position based on selfloopangle
                    # Match graph_primitives: Ranchor = 3.2 * R where R is the node radius
                    # Position is in data coordinates and should be zoom-independent
                    # GUI needs a scaling adjustment to match exported rendering (tunable in Export Scaling tab)
                    GUI_SELFLOOP_LABEL_SCALE = self.export_rescale.get('GUI_SELFLOOP_LABEL_SCALE', 1.5)
                    Ranchor = 3.2 * from_radius * GUI_SELFLOOP_LABEL_SCALE
                    label_x = from_pos[0] + 1.05 * Ranchor * np.cos(selfloopangle * np.pi / 180)
                    label_y = from_pos[1] + 1.05 * Ranchor * np.sin(selfloopangle * np.pi / 180)

                    # Apply nudge if present
                    nudge = edge.get('selflooplabelnudge', (0.0, 0.0))
                    label_x += nudge[0]
                    label_y += nudge[1]

                    # Auto-enclose label with $ signs for math mode
                    if not selfloop_label.startswith('$'):
                        formatted_label = f'${selfloop_label}$'
                    else:
                        formatted_label = selfloop_label

                    # Scale font size
                    base_font_size = 12
                    scaled_font_size = base_font_size * edge['label_size_mult'] * (points_per_data_unit / reference_points_per_data_unit)

                    # Draw self-loop label via the cached vector glyph-path renderer.
                    self._label_cache.draw(
                        self.canvas.ax, formatted_label, label_x, label_y,
                        fontsize_points=scaled_font_size,
                        points_per_data_unit=points_per_data_unit,
                        color=edge.get('label_color', 'black'),
                        ha='center', va='center',
                        usetex=self.use_latex, zorder=20,
                        bgcolor=edge.get('label_bgcolor') or None,
                    )

                # Calculate the Bezier curve control points (matching graph_primitives selfloop)
                dtheta = -34  # Matches graph_primitives
                R_node = from_radius * 1.2  # Node radius for selfloop attachment

                # Start and end points on the node circle
                theta_start = selfloopangle + dtheta
                theta_end = selfloopangle - dtheta
                v_start = [from_pos[0] + R_node * np.cos(theta_start * np.pi / 180),
                          from_pos[1] + R_node * np.sin(theta_start * np.pi / 180)]
                v_end = [from_pos[0] + R_node * np.cos(theta_end * np.pi / 180),
                        from_pos[1] + R_node * np.sin(theta_end * np.pi / 180)]

                # Bezier control points (perpendicular to node, extending by loopR/2)
                bz_start = [v_start[0] + loopR/2 * np.cos(theta_start * np.pi / 180),
                           v_start[1] + loopR/2 * np.sin(theta_start * np.pi / 180)]
                bz_end = [v_end[0] + loopR/2 * np.cos(theta_end * np.pi / 180),
                         v_end[1] + loopR/2 * np.sin(theta_end * np.pi / 180)]

                # Calculate apex of bezier curve at t=0.5 for selection indicator
                # For cubic Bezier: B(t) = (1-t)³P0 + 3(1-t)²t*P1 + 3(1-t)t²P2 + t³P3
                t = 0.5
                apex_x = ((1-t)**3 * v_start[0] +
                         3*(1-t)**2*t * bz_start[0] +
                         3*(1-t)*t**2 * bz_end[0] +
                         t**3 * v_end[0])
                apex_y = ((1-t)**3 * v_start[1] +
                         3*(1-t)**2*t * bz_start[1] +
                         3*(1-t)*t**2 * bz_end[1] +
                         t**3 * v_end[1])

                # Draw selection indicator for selected self-loops
                if edge in self.selected_edges:
                    # Place indicator at 75% along the bezier curve from node center
                    apex_dist_from_center = np.sqrt((apex_x - from_pos[0])**2 + (apex_y - from_pos[1])**2)
                    indicator_distance = apex_dist_from_center * 0.75
                    apex_angle = np.arctan2(apex_y - from_pos[1], apex_x - from_pos[0])
                    indicator_x = from_pos[0] + indicator_distance * np.cos(apex_angle)
                    indicator_y = from_pos[1] + indicator_distance * np.sin(apex_angle)

                    selection_circle = patches.Circle(
                        (indicator_x, indicator_y), from_radius * 0.3,
                        facecolor='lightcoral',
                        edgecolor='red',
                        linewidth=2,
                        zorder=25
                    )
                    self.canvas.ax.add_patch(selection_circle)
            else:
                # Draw edge using graph_primitives edge function
                from_pos = from_node['pos']
                to_pos = to_node['pos']
                from_radius = self.node_radius * from_node.get('node_size_mult', 1.0)
                to_radius = self.node_radius * to_node.get('node_size_mult', 1.0)

                # Calculate angle from from_node to to_node
                dx = to_pos[0] - from_pos[0]
                dy = to_pos[1] - from_pos[1]
                labeltheta = np.arctan2(dy, dx) * 180 / np.pi

                # Flip labels by 180 degrees if requested
                if edge.get('flip_labels', False):
                    labeltheta += 180

                # Add fine-tuning rotation offset
                labeltheta += edge.get('label_rotation_offset', 0)

                # Scale linewidth proportionally to zoom (base 5.5 at reference zoom)
                base_lw = 2.0
                linewidth_mult = edge.get('linewidth_mult', 1.0)
                scaled_lw = base_lw * linewidth_mult * (points_per_data_unit / reference_points_per_data_unit)

                # Edge label font size - graph_primitives will scale it based on points_per_data_unit
                # We just pass the multiplier (labelfontsize acts as a multiplier in graph_primitives)
                base_labelfontsize = 20
                label_size_mult = edge.get('label_size_mult', 1.0)
                scaled_labelfontsize = base_labelfontsize * label_size_mult
                # NOTE: DO NOT scale by points_per_data_unit here - graph_primitives does this internally!

                # Scale label offset (base 2.3 at reference zoom)
                base_labeloffset = 2.3
                scaled_labeloffset = base_labeloffset * edge.get('label_offset_mult', 1.0)

                # Format labels with math mode if they contain backslash
                label1_text = edge.get('label1', '')
                label2_text = edge.get('label2', '')

                # Add math mode if not already present
                if label1_text and not label1_text.startswith('$'):
                    label1_text = f'${label1_text}$'
                if label2_text and not label2_text.startswith('$'):
                    label2_text = f'${label2_text}$'

                # Convert empty strings to None for graph_primitives
                label1_formatted = label1_text if label1_text else None
                label2_formatted = label2_text if label2_text else None

                # Adjust linewidth for single/double styles (they multiply by 3.5x and 7x respectively)
                # Since graph_primitives only multiplies if 'lw' is NOT in loopkwargs,
                # we need to pre-multiply when passing 'lw' ourselves
                style = edge['style']
                single_double_lw_unit = 3.0
                if style == 'single':
                    final_lw = scaled_lw * single_double_lw_unit 
                elif style == 'double':
                    final_lw = scaled_lw * 2. * single_double_lw_unit
                else:  # loopy
                    final_lw = scaled_lw

                gp.edge(
                    ax=self.canvas.ax,
                    nodexy=[from_pos, to_pos],
                    nodeR=[from_radius, to_radius],
                    label=[label1_formatted, label2_formatted],
                    labeltheta=labeltheta,
                    labeloffset=scaled_labeloffset,
                    labelfontsize=scaled_labelfontsize,
                    labelbgcolor=[edge.get('label1_bgcolor', None), edge.get('label2_bgcolor', None)],
                    style=style,
                    whichedges=edge['direction'],
                    theta=edge.get('looptheta', 30),  # Looptheta parameter (adjustable via Ctrl+Left/Right)
                    loopkwargs={'lw': final_lw, 'arrowlength': 0.4,  # Add arrowheads
                                'arrowstyle': edge.get('arrowstyle', 'open'),
                                'arrowscale': edge.get('arrowscale', 1.0),
                                'arrowopenang': config.ARROWHEAD_OPEN_ANGLE},
                    gid=f'edge_{edge_index}',
                    label_cache=self._label_cache,
                    usetex=self.use_latex,
                )

                # Draw selection indicator for selected edges
                if edge in self.selected_edges:
                    mid_x = (from_pos[0] + to_pos[0]) / 2
                    mid_y = (from_pos[1] + to_pos[1]) / 2
                    # Draw a small circle at the edge midpoint
                    selection_circle = patches.Circle(
                        (mid_x, mid_y), 0.3,
                        facecolor='lightcoral',
                        edgecolor='red',
                        linewidth=2,
                        zorder=20
                    )
                    self.canvas.ax.add_patch(selection_circle)

    def _on_motion(self, event):
        """Handle mouse motion"""
        if event.inaxes != self.canvas.ax:
            return

        # Check for pending drag - activate only while the left button is actually
        # held (event.button is the button held during the motion, or None on a
        # bare hover). This prevents a stale pending-drag from turning post-release
        # cursor movement into an unwanted drag: only a real click-drag drags.
        if ((self.drag_pending_node or self.drag_pending_group)
                and self.drag_start_pos is not None
                and event.button == 1):
            dx = event.xdata - self.drag_start_pos[0]
            dy = event.ydata - self.drag_start_pos[1]
            distance = np.sqrt(dx**2 + dy**2)

            if distance > self.drag_threshold:
                # Activate dragging
                if self.drag_pending_group:
                    self.dragging_group = True
                    self.drag_pending_group = False
                    logger.debug(f"Dragging {len(self.selected_nodes)} node(s)...")
                elif self.drag_pending_node:
                    self.dragging_node = self.drag_pending_node
                    self.drag_pending_node = None
                    logger.debug(f"Dragging node '{self.dragging_node['label']}'...")
                # Fall through to dragging handling below

        # Handle panning - don't redraw during pan, just on release
        if self.panning and self.pan_start is not None:
            dx = event.xdata - self.pan_start[0]
            dy = event.ydata - self.pan_start[1]

            self.base_xlim = (self.base_xlim[0] - dx, self.base_xlim[1] - dx)
            self.base_ylim = (self.base_ylim[0] - dy, self.base_ylim[1] - dy)

            # Keep pan_start fixed in world coordinates for smoother panning
            # (don't update pan_start)

            # Update view limits directly without full redraw
            self.canvas.ax.set_xlim(*self._get_xlim())
            self.canvas.ax.set_ylim(*self._get_ylim())
            self.canvas.draw_idle()
            return

        # Handle selection window drawing
        if self.selection_window and self.selection_window_start is not None:
            # Remove old rectangle
            if self.selection_window_rect:
                try:
                    self.selection_window_rect.remove()
                except:
                    pass

            # Draw new rectangle
            x0, y0 = self.selection_window_start
            width = event.xdata - x0
            height = event.ydata - y0

            self.selection_window_rect = patches.Rectangle(
                (x0, y0), width, height,
                fill=False, edgecolor='darkgray', linestyle=':', linewidth=1.5, zorder=20,
            )
            self.canvas.ax.add_patch(self.selection_window_rect)
            self.canvas.draw_idle()
            return

        # Handle zoom window drawing
        if self.zoom_window and self.zoom_window_start is not None:
            # Remove old rectangle
            if self.zoom_window_rect:
                try:
                    self.zoom_window_rect.remove()
                except:
                    pass

            # Draw new rectangle
            x0, y0 = self.zoom_window_start
            width = event.xdata - x0
            height = event.ydata - y0

            self.zoom_window_rect = patches.Rectangle(
                (x0, y0), width, height,
                fill=False, edgecolor='slategray', linestyle='--', linewidth=1, zorder=19,
            )
            self.canvas.ax.add_patch(self.zoom_window_rect)
            self.canvas.draw_idle()
            return

        # Handle group dragging
        if self.dragging_group and self.drag_start_pos is not None:
            # Calculate offset from drag start
            dx = event.xdata - self.drag_start_pos[0]
            dy = event.ydata - self.drag_start_pos[1]

            # Remove old previews
            for patch in self.drag_preview_patches:
                try:
                    patch.remove()
                except:
                    pass
            for text in self.drag_preview_texts:
                try:
                    text.remove()
                except:
                    pass
            self.drag_preview_patches.clear()
            self.drag_preview_texts.clear()

            # Draw preview for each selected node
            any_occupied = False
            for node in self.selected_nodes:
                new_x = node['pos'][0] + dx
                new_y = node['pos'][1] + dy
                snap_x, snap_y = self._snap_to_grid(new_x, new_y)

                # Check if occupied by non-selected node
                occupied = any(
                    other_node not in self.selected_nodes and
                    np.isclose(other_node['pos'][0], snap_x, atol=0.01) and
                    np.isclose(other_node['pos'][1], snap_y, atol=0.01)
                    for other_node in self.nodes
                )
                any_occupied = any_occupied or occupied

                # Ghost appearance: use semi-transparent fill
                color = 'red' if occupied else 'lightblue'
                node_size_mult = node.get('node_size_mult', 1.0)

                preview_patch = patches.Circle(
                    (snap_x, snap_y), self.node_radius * node_size_mult,
                    fill=True, facecolor=color, edgecolor='gray',
                    linestyle=':', linewidth=1.5, alpha=0.5, zorder=15
                )
                self.canvas.ax.add_patch(preview_patch)
                self.drag_preview_patches.append(preview_patch)

                preview_text = self.canvas.ax.text(
                    snap_x, snap_y, node['label'],
                    ha='center', va='center', fontsize=14, color='gray', alpha=0.7, zorder=16
                )
                self.drag_preview_texts.append(preview_text)

            self.canvas.draw_idle()
            return

        # Handle single node dragging
        if self.dragging_node is not None:
            snap_x, snap_y = self._snap_to_grid(event.xdata, event.ydata)

            # Check if occupied by another node
            occupied = any(
                node != self.dragging_node and
                np.isclose(node['pos'][0], snap_x, atol=0.01) and
                np.isclose(node['pos'][1], snap_y, atol=0.01)
                for node in self.nodes
            )

            # Remove old preview
            for patch in self.drag_preview_patches:
                try:
                    patch.remove()
                except:
                    pass
            for text in self.drag_preview_texts:
                try:
                    text.remove()
                except:
                    pass
            self.drag_preview_patches.clear()
            self.drag_preview_texts.clear()

            # Draw preview (ghost appearance)
            color = 'red' if occupied else 'lightblue'
            node_size_mult = self.dragging_node.get('node_size_mult', 1.0)
            preview_patch = patches.Circle(
                (snap_x, snap_y), self.node_radius * node_size_mult,
                fill=True, facecolor=color, edgecolor='gray',
                linestyle=':', linewidth=1.5, alpha=0.5, zorder=15
            )
            self.canvas.ax.add_patch(preview_patch)
            self.drag_preview_patches.append(preview_patch)

            preview_text = self.canvas.ax.text(
                snap_x, snap_y, self.dragging_node['label'],
                ha='center', va='center', fontsize=14, color='gray', alpha=0.7, zorder=16
            )
            self.drag_preview_texts.append(preview_text)

            self.canvas.draw_idle()
            return

        # Handle node placement preview
        if self.placement_mode not in ['single', 'continuous', 'continuous_duplicate']:
            return

        snap_x, snap_y = self._snap_to_grid(event.xdata, event.ydata)

        # Check if occupied
        occupied = any(
            np.isclose(node['pos'][0], snap_x, atol=0.01) and
            np.isclose(node['pos'][1], snap_y, atol=0.01)
            for node in self.nodes
        )

        # Remove old preview
        if self.preview_patch:
            try:
                self.preview_patch.remove()
            except:
                pass

        if self.preview_text:
            try:
                self.preview_text.remove()
            except:
                pass

        # Draw preview
        color = 'red' if occupied else 'blue'
        self.preview_patch = patches.Circle(
            (snap_x, snap_y), self.node_radius,
            fill=True, edgecolor=color, linestyle=':', linewidth=1, zorder=15,
            alpha=0.5
        )
        self.canvas.ax.add_patch(self.preview_patch)

        if not occupied:
            self.preview_text = self.canvas.ax.text(
                snap_x, snap_y, '?',
                ha='center', va='center', fontsize=20, color='white', zorder=16
            )

        self.canvas.draw_idle()

    def _on_click(self, event):
        """Handle mouse click"""
        if event.inaxes != self.canvas.ax:
            return

        # Middle button - start panning
        if event.button == 2:
            self.panning = True
            self.pan_start = (event.xdata, event.ydata)
            return

        # Right button - show context menu if on node/edge, otherwise start zoom window
        if event.button == 3:
            clicked_node = self._find_node_at_position(event.xdata, event.ydata)
            if clicked_node:
                # Show context menu for color selection
                self._show_color_context_menu(event, clicked_node)
                return

            clicked_edge = self._find_edge_at_position(event.xdata, event.ydata)
            if clicked_edge:
                # Show context menu for edge type selection
                self._show_edge_context_menu(event, clicked_edge)
                return

            # Start zoom window if not on node or edge
            self.zoom_window = True
            self.zoom_window_start = (event.xdata, event.ydata)
            return

        # Left button - node placement, editing, dragging, or selection
        if event.button == 1:
            # Check for double-click on node (for editing)
            current_time = time.time()
            clicked_node = None

            # Use Qt's keyboard modifiers for reliable Shift/Ctrl detection
            modifiers = QApplication.keyboardModifiers()
            shift_pressed = modifiers & Qt.ShiftModifier
            ctrl_pressed = modifiers & Qt.ControlModifier

            # Conjugation mode - toggle conjugation on clicked nodes (handle before other modes)
            if self.placement_mode == 'conjugation':
                clicked_node = self._find_node_at_position(event.xdata, event.ydata)
                if clicked_node:
                    self._save_state()
                    # Toggle conjugation state
                    clicked_node['conj'] = not clicked_node.get('conj', False)
                    conj_state = "conjugated" if clicked_node['conj'] else "unconjugated"
                    logger.debug(f"Node '{clicked_node['label']}' is now {conj_state}")
                    self._update_plot()
                return

            # Edge mode - connect two nodes
            if self.placement_mode in ['edge', 'edge_continuous']:
                clicked_node = self._find_node_at_position(event.xdata, event.ydata)
                if clicked_node:
                    if self.edge_mode_first_node is None:
                        # First node selected
                        self.edge_mode_first_node = clicked_node
                        logger.debug(f"First node selected: '{clicked_node['label']}'. Click another node to connect.")
                        self._update_plot()
                    else:
                        # Second node selected - show dialog or use last settings
                        second_node = clicked_node
                        is_self_loop = (self.edge_mode_first_node == second_node)

                        # In continuous mode, use last edge settings if available
                        if self.placement_mode == 'edge_continuous' and hasattr(self, 'last_edge_props') and self.last_edge_props:
                            result = self.last_edge_props
                        else:
                            dialog = EdgeInputDialog(
                                node1_label=self.edge_mode_first_node['label'],
                                node2_label=second_node['label'],
                                is_self_loop=is_self_loop,
                                parent=self
                            )

                            if dialog.exec() == QDialog.Accepted:
                                result = dialog.get_result()
                                if result:
                                    # Store for continuous mode
                                    self.last_edge_props = result
                            else:
                                result = None

                        if result:
                            self._save_state()

                            # Check if edge already exists between these nodes (in either direction)
                            existing_edge = None
                            for edge in self.edges:
                                # Check both directions for regular edges
                                if not is_self_loop:
                                    if ((edge['from_node_id'] == self.edge_mode_first_node['node_id'] and
                                         edge['to_node_id'] == second_node['node_id']) or
                                        (edge['from_node_id'] == second_node['node_id'] and
                                         edge['to_node_id'] == self.edge_mode_first_node['node_id'])):
                                        existing_edge = edge
                                        break
                                # Check for existing self-loop
                                else:
                                    if (edge['is_self_loop'] and
                                        edge['from_node_id'] == self.edge_mode_first_node['node_id']):
                                        existing_edge = edge
                                        break

                            # Update existing edge or create new one
                            if existing_edge:
                                # Replace existing edge properties
                                existing_edge['from_node'] = self.edge_mode_first_node
                                existing_edge['to_node'] = second_node
                                existing_edge['from_node_id'] = self.edge_mode_first_node['node_id']
                                existing_edge['to_node_id'] = second_node['node_id']
                                existing_edge['label1'] = result['label1']
                                existing_edge['label2'] = result['label2']
                                existing_edge['linewidth_mult'] = result['linewidth_mult']
                                existing_edge['label_size_mult'] = result['label_size_mult']
                                existing_edge['label_offset_mult'] = result['label_offset_mult']
                                existing_edge['style'] = result['style']
                                existing_edge['direction'] = result['direction']
                                existing_edge['flip_labels'] = result.get('flip_labels', False)
                                existing_edge['is_self_loop'] = is_self_loop
                                # Self-loop specific parameters
                                if is_self_loop:
                                    existing_edge['selfloopangle'] = result.get('selfloopangle', 0)
                                    existing_edge['selfloopscale'] = result.get('selfloopscale', 1.0)
                                    existing_edge['arrowlengthsc'] = result.get('arrowlengthsc', 1.0)
                                    existing_edge['flip'] = result.get('flip', False)
                                if is_self_loop:
                                    logger.debug(f"Replaced self-loop on node '{self.edge_mode_first_node['label']}'")
                                else:
                                    logger.debug(f"Replaced edge: '{self.edge_mode_first_node['label']}' ↔ '{second_node['label']}'")
                            else:
                                # Create new edge
                                edge = {
                                    'from_node': self.edge_mode_first_node,
                                    'to_node': second_node,
                                    'from_node_id': self.edge_mode_first_node['node_id'],
                                    'to_node_id': second_node['node_id'],
                                    'label1': result['label1'],
                                    'label2': result['label2'],
                                    'linewidth_mult': result['linewidth_mult'],
                                    'label_size_mult': result['label_size_mult'],
                                    'label_offset_mult': result['label_offset_mult'],
                                    'style': result['style'],
                                    'direction': result['direction'],
                                    'flip_labels': result.get('flip_labels', False),
                                    'looptheta': result.get('looptheta', 30),
                                    'is_self_loop': is_self_loop,
                                    'arrowstyle': config.DEFAULT_EDGE_ARROWSTYLE,
                                    'arrowscale': config.DEFAULT_EDGE_ARROWSCALE
                                }
                                # Self-loop specific parameters
                                if is_self_loop:
                                    edge['selfloopangle'] = result.get('selfloopangle', 0)
                                    edge['selfloopscale'] = result.get('selfloopscale', 1.0)
                                    edge['arrowlengthsc'] = result.get('arrowlengthsc', 1.0)
                                    edge['flip'] = result.get('flip', False)
                                    edge['angle_pinned'] = False
                                    # Auto-adjust angle away from existing edges if enabled
                                    if config.AUTO_ADJUST_SELFLOOP_ANGLE:
                                        edge['selfloopangle'] = self._compute_best_selfloop_angle(second_node)
                                self.edges.append(edge)
                                if is_self_loop:
                                    logger.debug(f"Added self-loop to node '{self.edge_mode_first_node['label']}'")
                                else:
                                    logger.debug(f"Added edge: '{self.edge_mode_first_node['label']}' → '{second_node['label']}'")

                        # Recompute unpinned self-loop angles on affected nodes
                        if not is_self_loop and config.DYNAMIC_ADJUST_SELFLOOP_ANGLE:
                            affected_ids = {self.edge_mode_first_node['node_id'], second_node['node_id']}
                            self._recompute_unpinned_selfloop_angles(affected_ids)

                        # Exit single edge mode after placement, continue in continuous mode
                        if self.placement_mode == 'edge':
                            self.placement_mode = None
                            logger.debug("Edge placed - exited edge mode")

                        # Reset for next edge
                        self.edge_mode_first_node = None
                        self._update_plot()
                return

            if self.placement_mode is None:
                clicked_node = self._find_node_at_position(event.xdata, event.ydata)

                # Handle node selection with Shift key (do this before double-click check)
                if clicked_node and shift_pressed:
                    if clicked_node in self.selected_nodes:
                        self.selected_nodes.remove(clicked_node)
                        logger.debug(f"Deselected node '{clicked_node['label']}'")
                    else:
                        self.selected_nodes.append(clicked_node)
                        logger.debug(f"Selected node '{clicked_node['label']}'")
                    # Don't update click tracking for shift-clicks
                    self._update_plot()
                    return

                # Check if this is a double-click on node or edge
                if self.last_click_pos:
                    time_diff = current_time - self.last_click_time
                    pos_diff = np.sqrt((event.xdata - self.last_click_pos[0])**2 +
                                      (event.ydata - self.last_click_pos[1])**2)

                    if time_diff < self.double_click_threshold and pos_diff < 0.5:
                        # Double-click detected
                        if clicked_node:
                            # Edit node
                            self._edit_node(clicked_node)
                        else:
                            # Check for edge
                            clicked_edge = self._find_edge_at_position(event.xdata, event.ydata)
                            if clicked_edge:
                                self._edit_edge(clicked_edge)
                        self.last_click_time = 0
                        self.last_click_pos = None
                        return

                # Update click tracking
                self.last_click_time = current_time
                self.last_click_pos = (event.xdata, event.ydata)

                # Single click on node - select and prepare for potential dragging
                if clicked_node:
                    # If clicking on an already selected node, prepare to drag the whole group
                    if clicked_node in self.selected_nodes and len(self.selected_nodes) > 1:
                        self.drag_pending_group = True
                        self.drag_start_pos = (event.xdata, event.ydata)
                        # Don't print yet - wait until actual drag starts
                    else:
                        # Select only this node and prepare to drag it
                        if clicked_node not in self.selected_nodes:
                            self.selected_nodes.clear()
                            self.selected_edges.clear()  # Clear edge selection when selecting node
                            self.selected_nodes.append(clicked_node)
                            self._update_plot()
                        self.drag_pending_node = clicked_node
                        self.drag_start_pos = (event.xdata, event.ydata)
                        # Don't print yet - wait until actual drag starts
                    return

                # Single click on edge (if no node was clicked) - select edge
                if not clicked_node:
                    clicked_edge = self._find_edge_at_position(event.xdata, event.ydata)
                    if clicked_edge:
                        # Toggle edge selection with Shift, otherwise select only this edge
                        is_self_loop = clicked_edge.get('is_self_loop', False)
                        from_label = clicked_edge['from_node']['label']
                        to_label = clicked_edge['to_node']['label']

                        if shift_pressed:
                            if clicked_edge in self.selected_edges:
                                self.selected_edges.remove(clicked_edge)
                                if is_self_loop:
                                    logger.debug(f"Deselected self-loop on '{from_label}'")
                                else:
                                    logger.debug(f"Deselected edge '{from_label}' → '{to_label}'")
                            else:
                                self.selected_edges.append(clicked_edge)
                                if is_self_loop:
                                    logger.debug(f"Selected self-loop on '{from_label}'")
                                else:
                                    logger.debug(f"Selected edge '{from_label}' → '{to_label}'")
                        else:
                            self.selected_nodes.clear()  # Clear node selection when selecting edge
                            self.selected_edges.clear()
                            self.selected_edges.append(clicked_edge)
                            if is_self_loop:
                                logger.debug(f"Selected self-loop on '{from_label}'")
                            else:
                                logger.debug(f"Selected edge '{from_label}' → '{to_label}'")
                        self._update_plot()
                        return

                # Click on empty space - start selection window or clear selection
                if not clicked_node:
                    self.selected_nodes.clear()
                    self.selected_edges.clear()
                    self.selection_window = True
                    self.selection_window_start = (event.xdata, event.ydata)
                    self._update_plot()
                    return

            # Node placement mode
            if self.placement_mode in ['single', 'continuous', 'continuous_duplicate']:
                snap_x, snap_y = self._snap_to_grid(event.xdata, event.ydata)

                # Check if occupied
                occupied = any(
                    np.isclose(node['pos'][0], snap_x, atol=0.01) and
                    np.isclose(node['pos'][1], snap_y, atol=0.01)
                    for node in self.nodes
                )

                if occupied:
                    logger.debug(f"Position ({snap_x:.3f}, {snap_y:.3f}) already occupied!")
                    return

                # Continuous duplicate mode - use last node properties
                if self.placement_mode == 'continuous_duplicate':
                    if self.last_node_props:
                        self._save_state()

                        # Auto-increment the label (or use 'A' if empty string)
                        current_label = self.last_node_props['label']
                        if current_label == '':
                            # First node - start with 'A'
                            next_label = 'A'
                        else:
                            next_label = self._auto_increment_label(current_label)

                        # Add node with duplicated properties and incremented label
                        self.nodes.append({
                            'node_id': self.node_id_counter,
                            'label': next_label,
                            'pos': (snap_x, snap_y),
                            'color': self.last_node_props['color'],
                            'color_key': self.last_node_props['color_key'],
                            'node_size_mult': self.last_node_props['node_size_mult'],
                            'label_size_mult': self.last_node_props['label_size_mult'],
                            'conj': self.last_node_props['conj'],
                            'outline_enabled': config.DEFAULT_NODE_OUTLINE_ENABLED,
                            'outline_color': config.DEFAULT_NODE_OUTLINE_COLOR,
                            'outline_width': config.DEFAULT_NODE_OUTLINE_WIDTH,
                            'outline_alpha': config.DEFAULT_NODE_OUTLINE_ALPHA
                        })
                        self.node_counter += 1
                        self.node_id_counter += 1

                        # Update last_node_props with the new label for next placement
                        self.last_node_props['label'] = next_label

                        logger.info(f"✓ Node '{next_label}' ({self.last_node_props['color_key']}) placed at ({snap_x:.3f}, {snap_y:.3f})")
                        self._update_plot()
                    return

                # Show dialog for single and continuous modes
                # In continuous mode, inherit properties from last node
                default_label = self._get_next_label()
                if self.placement_mode == 'continuous' and self.last_node_props:
                    # Use properties from last modified node
                    dialog = NodeInputDialog(
                        default_label=default_label,
                        default_color=self.last_node_props['color_key'],
                        parent=self
                    )
                    # Set the dialog defaults to match last node
                    # Map multipliers back to size names
                    size_map = {0.6: 'Small', 1.0: 'Medium', 1.4: 'Large', 1.8: 'X-Large'}
                    def find_closest_size(value):
                        return min(size_map.keys(), key=lambda k: abs(k - value))

                    node_size_mult = self.last_node_props['node_size_mult']
                    label_size_mult = self.last_node_props['label_size_mult']

                    dialog.node_size_combo.setCurrentText(size_map[find_closest_size(node_size_mult)])
                    dialog.label_size_combo.setCurrentText(size_map[find_closest_size(label_size_mult)])
                    dialog.conj_checkbox.setChecked(self.last_node_props['conj'])
                else:
                    dialog = NodeInputDialog(default_label=default_label, default_color='BLUE', parent=self)

                if dialog.exec() == QDialog.Accepted:
                    result = dialog.get_result()
                    if result:
                        # Add node
                        new_node = {
                            'node_id': self.node_id_counter,
                            'label': result['label'],
                            'pos': (snap_x, snap_y),
                            'color': result['color'],
                            'color_key': result['color_key'],
                            'node_size_mult': result['node_size_mult'],
                            'label_size_mult': result['label_size_mult'],
                            'conj': result['conj'],
                            'outline_enabled': config.DEFAULT_NODE_OUTLINE_ENABLED,
                            'outline_color': config.DEFAULT_NODE_OUTLINE_COLOR,
                            'outline_width': config.DEFAULT_NODE_OUTLINE_WIDTH,
                            'outline_alpha': config.DEFAULT_NODE_OUTLINE_ALPHA
                        }
                        self.nodes.append(new_node)
                        self.node_counter += 1
                        self.node_id_counter += 1

                        # Save properties for duplication
                        self.last_node_props = {
                            'label': result['label'],
                            'color': result['color'],
                            'color_key': result['color_key'],
                            'node_size_mult': result['node_size_mult'],
                            'label_size_mult': result['label_size_mult'],
                            'conj': result['conj']
                        }

                        logger.info(f"✓ Node '{result['label']}' ({result['color_key']}) placed at ({snap_x:.3f}, {snap_y:.3f})")

                        # Exit single mode
                        if self.placement_mode == 'single':
                            self.placement_mode = None
                            logger.debug("Exited placement mode")

                        self._update_plot()

    def _on_release(self, event):
        """Handle mouse release"""
        # Middle button - stop panning
        if event.button == 2:
            self.panning = False
            self.pan_start = None
            return

        # Left button - complete selection window
        if event.button == 1:
            if self.selection_window and self.selection_window_start is not None:
                if event.inaxes == self.canvas.ax:
                    x0, y0 = self.selection_window_start
                    x1, y1 = event.xdata, event.ydata

                    # Ensure x0 < x1 and y0 < y1
                    if x1 < x0:
                        x0, x1 = x1, x0
                    if y1 < y0:
                        y0, y1 = y1, y0

                    # Select all nodes within the rectangle
                    for node in self.nodes:
                        nx, ny = node['pos']
                        if x0 <= nx <= x1 and y0 <= ny <= y1:
                            if node not in self.selected_nodes:
                                self.selected_nodes.append(node)

                    # Select all edges whose midpoints are within the rectangle
                    for edge in self.edges:
                        from_pos = edge['from_node']['pos']
                        to_pos = edge['to_node']['pos']
                        mid_x = (from_pos[0] + to_pos[0]) / 2
                        mid_y = (from_pos[1] + to_pos[1]) / 2
                        if x0 <= mid_x <= x1 and y0 <= mid_y <= y1:
                            if edge not in self.selected_edges:
                                self.selected_edges.append(edge)

                    msg = []
                    if self.selected_nodes:
                        msg.append(f"{len(self.selected_nodes)} node(s)")
                    if self.selected_edges:
                        msg.append(f"{len(self.selected_edges)} edge(s)")
                    if msg:
                        logger.debug(f"Selected {' and '.join(msg)}")

                # Clean up
                self.selection_window = False
                self.selection_window_start = None
                if self.selection_window_rect:
                    try:
                        self.selection_window_rect.remove()
                    except:
                        pass
                    self.selection_window_rect = None

                self._update_plot()
                return

        # Right button - complete zoom window
        if event.button == 3:
            if self.zoom_window and self.zoom_window_start is not None:
                if event.inaxes == self.canvas.ax:
                    x0, y0 = self.zoom_window_start
                    x1, y1 = event.xdata, event.ydata

                    # Ensure x0 < x1 and y0 < y1
                    if x1 < x0:
                        x0, x1 = x1, x0
                    if y1 < y0:
                        y0, y1 = y1, y0

                    # Check minimum size
                    if abs(x1 - x0) > 0.5 and abs(y1 - y0) > 0.5:
                        # Set new view limits
                        self.base_xlim = (x0, x1)
                        self.base_ylim = (y0, y1)
                        self.zoom_level = 1.0
                        logger.debug(f"Zoom window: ({x0:.3f}, {y0:.3f}) to ({x1:.3f}, {y1:.3f})")

                # Clean up
                self.zoom_window = False
                self.zoom_window_start = None
                if self.zoom_window_rect:
                    try:
                        self.zoom_window_rect.remove()
                    except:
                        pass
                    self.zoom_window_rect = None

                self._update_plot()
            return

        # Left button - complete group or single node dragging
        if event.button == 1:
            # Complete group dragging
            if self.dragging_group and self.drag_start_pos is not None:
                if event.inaxes == self.canvas.ax:
                    dx = event.xdata - self.drag_start_pos[0]
                    dy = event.ydata - self.drag_start_pos[1]

                    # Check if all new positions are valid
                    new_positions = []
                    all_valid = True
                    for node in self.selected_nodes:
                        new_x = node['pos'][0] + dx
                        new_y = node['pos'][1] + dy
                        snap_x, snap_y = self._snap_to_grid(new_x, new_y)

                        # Check if occupied by non-selected node
                        occupied = any(
                            other_node not in self.selected_nodes and
                            np.isclose(other_node['pos'][0], snap_x, atol=0.01) and
                            np.isclose(other_node['pos'][1], snap_y, atol=0.01)
                            for other_node in self.nodes
                        )

                        if occupied:
                            all_valid = False
                            break

                        new_positions.append((node, snap_x, snap_y))

                    # If all positions valid, move all nodes
                    if all_valid:
                        self._save_state()
                        for node, snap_x, snap_y in new_positions:
                            node['pos'] = (snap_x, snap_y)
                        logger.info(f"✓ Moved {len(self.selected_nodes)} node(s)")
                        self._recompute_unpinned_selfloop_angles(
                            {node['node_id'] for node in self.selected_nodes})
                    else:
                        logger.info(f"✗ Cannot move group - some positions occupied")

                # Clean up
                self.dragging_group = False
                self.drag_pending_group = False
                self.drag_start_pos = None
                for patch in self.drag_preview_patches:
                    try:
                        patch.remove()
                    except:
                        pass
                for text in self.drag_preview_texts:
                    try:
                        text.remove()
                    except:
                        pass
                self.drag_preview_patches.clear()
                self.drag_preview_texts.clear()

                self._update_plot()
                return

            # Complete single node dragging
            if self.dragging_node is not None:
                if event.inaxes == self.canvas.ax:
                    snap_x, snap_y = self._snap_to_grid(event.xdata, event.ydata)

                    # Check if occupied by another node
                    occupied = any(
                        node != self.dragging_node and
                        np.isclose(node['pos'][0], snap_x, atol=0.01) and
                        np.isclose(node['pos'][1], snap_y, atol=0.01)
                        for node in self.nodes
                    )

                    if not occupied:
                        self._save_state()
                        old_pos = self.dragging_node['pos']
                        self.dragging_node['pos'] = (snap_x, snap_y)
                        logger.info(f"✓ Moved node '{self.dragging_node['label']}' from ({old_pos[0]:.3f}, {old_pos[1]:.3f}) to ({snap_x:.3f}, {snap_y:.3f})")
                        self._recompute_unpinned_selfloop_angles({self.dragging_node['node_id']})
                    else:
                        logger.info(f"✗ Cannot move node '{self.dragging_node['label']}' - position occupied")

                # Clean up
                self.dragging_node = None
                self.drag_pending_node = None
                self.drag_start_pos = None
                for patch in self.drag_preview_patches:
                    try:
                        patch.remove()
                    except:
                        pass
                for text in self.drag_preview_texts:
                    try:
                        text.remove()
                    except:
                        pass
                self.drag_preview_patches.clear()
                self.drag_preview_texts.clear()

                self._update_plot()
                return

            # Clear pending drag states if mouse was released without dragging
            if self.drag_pending_node or self.drag_pending_group:
                self.drag_pending_node = None
                self.drag_pending_group = False
                self.drag_start_pos = None
                return

    def _on_scroll(self, event):
        """Handle mouse scroll"""
        if event.inaxes != self.canvas.ax:
            return

        if event.button == 'up':
            self.zoom_level *= config.ZOOM_SCROLL_FACTOR
        elif event.button == 'down':
            self.zoom_level /= config.ZOOM_SCROLL_FACTOR

        # Fast view-only update (no scene rebuild)
        self._apply_view_fast()


    def _capture_state(self):
        """Deep-copy the full graph state (every node/edge field)."""
        return capture_graph_state(self.nodes, self.edges)

    def _restore_state(self, state):
        """Install a captured state as the live graph."""
        self.nodes = state['nodes']
        self.edges = state['edges']

        # Clear selections (they reference the replaced dicts)
        self.selected_nodes.clear()
        self.selected_edges.clear()

        self._update_plot()


    def _copy_nodes(self):
        """Copy selected nodes and edges to clipboard"""
        if not self.selected_nodes and not self.selected_edges:
            logger.info("No nodes or edges selected to copy")
            self._status_message("Nothing selected to copy")
            return

        self.clipboard = {'nodes': [], 'edges': []}

        # Copy nodes
        for node in self.selected_nodes:
            self.clipboard['nodes'].append({
                'node_id': node['node_id'],
                'label': node['label'],
                'pos': node['pos'],
                'color': node['color'],
                'color_key': node['color_key'],
                'node_size_mult': node.get('node_size_mult', 1.0),
                'label_size_mult': node.get('label_size_mult', 1.0),
                'conj': node.get('conj', False),
                'nodelabelnudge': node.get('nodelabelnudge', (0.0, 0.0)),
                'outline_enabled': node.get('outline_enabled', False),
                'outline_color': node.get('outline_color', config.DEFAULT_NODE_OUTLINE_COLOR),
                'outline_width': node.get('outline_width', config.DEFAULT_NODE_OUTLINE_WIDTH),
                'outline_alpha': node.get('outline_alpha', config.DEFAULT_NODE_OUTLINE_ALPHA)
            })

        # Copy edges (only edges where both nodes are selected)
        for edge in self.selected_edges:
            if edge['from_node'] in self.selected_nodes and edge['to_node'] in self.selected_nodes:
                edge_copy = {
                    'from_node_id': edge['from_node_id'],
                    'to_node_id': edge['to_node_id'],
                    'label1': edge.get('label1', ''),
                    'label2': edge.get('label2', ''),
                    'linewidth_mult': edge['linewidth_mult'],
                    'label_size_mult': edge['label_size_mult'],
                    'label_offset_mult': edge.get('label_offset_mult', 1.0),
                    'style': edge['style'],
                    'direction': edge['direction'],
                    'looptheta': edge.get('looptheta', 30),
                    'flip_labels': edge.get('flip_labels', False),
                    'label_rotation_offset': edge.get('label_rotation_offset', 0),
                    'arrowstyle': edge.get('arrowstyle', 'open'),
                    'arrowscale': edge.get('arrowscale', 1.0),
                    'is_self_loop': edge['is_self_loop']
                }
                # Copy self-loop specific parameters
                if edge['is_self_loop']:
                    edge_copy['selfloopangle'] = edge.get('selfloopangle', 0)
                    edge_copy['selfloopscale'] = edge.get('selfloopscale', 1.0)
                    edge_copy['arrowlengthsc'] = edge.get('arrowlengthsc', 1.0)
                    edge_copy['flip'] = edge.get('flip', False)
                    edge_copy['angle_pinned'] = edge.get('angle_pinned', False)
                    edge_copy['selflooplabelnudge'] = edge.get('selflooplabelnudge', (0.0, 0.0))
                    edge_copy['label_bgcolor'] = edge.get('label_bgcolor', None)
                else:
                    edge_copy['label1_bgcolor'] = edge.get('label1_bgcolor', None)
                    edge_copy['label2_bgcolor'] = edge.get('label2_bgcolor', None)
                self.clipboard['edges'].append(edge_copy)

        msg = []
        if len(self.clipboard['nodes']) > 0:
            msg.append(f"{len(self.clipboard['nodes'])} node(s)")
        if len(self.clipboard['edges']) > 0:
            msg.append(f"{len(self.clipboard['edges'])} edge(s)")
        logger.info(f"Copied {' and '.join(msg)}")

    def _cut_nodes(self):
        """Cut selected nodes and edges to clipboard"""
        if not self.selected_nodes and not self.selected_edges:
            logger.info("No nodes or edges selected to cut")
            self._status_message("Nothing selected to cut")
            return

        self._save_state()

        self.clipboard = {'nodes': [], 'edges': []}
        nodes_to_remove = list(self.selected_nodes)
        edges_to_remove = []

        # Copy and remove nodes
        for node in nodes_to_remove:
            self.clipboard['nodes'].append({
                'node_id': node['node_id'],
                'label': node['label'],
                'pos': node['pos'],
                'color': node['color'],
                'color_key': node['color_key'],
                'node_size_mult': node.get('node_size_mult', 1.0),
                'label_size_mult': node.get('label_size_mult', 1.0),
                'conj': node.get('conj', False),
                'nodelabelnudge': node.get('nodelabelnudge', (0.0, 0.0)),
                'outline_enabled': node.get('outline_enabled', False),
                'outline_color': node.get('outline_color', config.DEFAULT_NODE_OUTLINE_COLOR),
                'outline_width': node.get('outline_width', config.DEFAULT_NODE_OUTLINE_WIDTH),
                'outline_alpha': node.get('outline_alpha', config.DEFAULT_NODE_OUTLINE_ALPHA)
            })
            self.nodes.remove(node)

            # Find all edges connected to this node
            for edge in self.edges:
                if edge['from_node'] == node or edge['to_node'] == node:
                    if edge not in edges_to_remove:
                        edges_to_remove.append(edge)

        # Copy and remove selected edges (only if both nodes are selected)
        for edge in self.selected_edges:
            if edge not in edges_to_remove and edge in self.edges:
                if edge['from_node'] in self.selected_nodes and edge['to_node'] in self.selected_nodes:
                    edge_copy = {
                        'from_node_id': edge['from_node_id'],
                        'to_node_id': edge['to_node_id'],
                        'label1': edge.get('label1', ''),
                        'label2': edge.get('label2', ''),
                        'linewidth_mult': edge['linewidth_mult'],
                        'label_size_mult': edge['label_size_mult'],
                        'label_offset_mult': edge.get('label_offset_mult', 1.0),
                        'style': edge['style'],
                        'direction': edge['direction'],
                        'looptheta': edge.get('looptheta', 30),
                        'flip_labels': edge.get('flip_labels', False),
                        'label_rotation_offset': edge.get('label_rotation_offset', 0),
                        'arrowstyle': edge.get('arrowstyle', 'open'),
                        'arrowscale': edge.get('arrowscale', 1.0),
                        'is_self_loop': edge['is_self_loop']
                    }
                    # Copy self-loop specific parameters
                    if edge['is_self_loop']:
                        edge_copy['selfloopangle'] = edge.get('selfloopangle', 0)
                        edge_copy['selfloopscale'] = edge.get('selfloopscale', 1.0)
                        edge_copy['arrowlengthsc'] = edge.get('arrowlengthsc', 1.0)
                        edge_copy['flip'] = edge.get('flip', False)
                        edge_copy['angle_pinned'] = edge.get('angle_pinned', False)
                        edge_copy['selflooplabelnudge'] = edge.get('selflooplabelnudge', (0.0, 0.0))
                    self.clipboard['edges'].append(edge_copy)
                edges_to_remove.append(edge)

        # Remove all edges
        for edge in edges_to_remove:
            if edge in self.edges:
                self.edges.remove(edge)

        msg = []
        if len(self.clipboard['nodes']) > 0:
            msg.append(f"{len(self.clipboard['nodes'])} node(s)")
        if len(self.clipboard['edges']) > 0:
            msg.append(f"{len(self.clipboard['edges'])} edge(s)")
        logger.info(f"Cut {' and '.join(msg)}")

        self.selected_nodes.clear()
        self.selected_edges.clear()
        self._update_plot()

    def _paste_nodes(self):
        """Paste nodes and edges from clipboard"""
        if not self.clipboard or (not self.clipboard.get('nodes') and not self.clipboard.get('edges')):
            logger.info("Clipboard is empty")
            return

        self._save_state()

        # Calculate offset to paste nodes relative to the center of the view
        xlim = self._get_xlim()
        ylim = self._get_ylim()
        view_center_x = (xlim[0] + xlim[1]) / 2
        view_center_y = (ylim[0] + ylim[1]) / 2

        # Calculate centroid of clipboard nodes
        if self.clipboard.get('nodes'):
            clip_x = sum(n['pos'][0] for n in self.clipboard['nodes']) / len(self.clipboard['nodes'])
            clip_y = sum(n['pos'][1] for n in self.clipboard['nodes']) / len(self.clipboard['nodes'])

            # Snap the centroid to grid to get the base offset
            snap_center_x, snap_center_y = self._snap_to_grid(view_center_x, view_center_y)

            # Calculate offset based on snapped centroid
            offset_x = snap_center_x - clip_x
            offset_y = snap_center_y - clip_y
        else:
            offset_x, offset_y = 0, 0

        # Clear selection and paste nodes
        self.selected_nodes.clear()
        self.selected_edges.clear()

        # Map old node IDs to new nodes
        old_id_to_new_node = {}

        for clip_node in self.clipboard.get('nodes', []):
            # Apply offset but DON'T snap individually - maintain relative positions
            new_x = clip_node['pos'][0] + offset_x
            new_y = clip_node['pos'][1] + offset_y

            # Check if position is occupied
            occupied = any(
                np.isclose(node['pos'][0], new_x, atol=0.01) and
                np.isclose(node['pos'][1], new_y, atol=0.01)
                for node in self.nodes
            )

            if not occupied:
                new_node = {
                    'node_id': self.node_id_counter,
                    'label': clip_node['label'],
                    'pos': (new_x, new_y),
                    'color': clip_node['color'],
                    'color_key': clip_node['color_key'],
                    'node_size_mult': clip_node.get('node_size_mult', 1.0),
                    'label_size_mult': clip_node.get('label_size_mult', 1.0),
                    'conj': clip_node.get('conj', False),
                    'nodelabelnudge': clip_node.get('nodelabelnudge', (0.0, 0.0)),
                    'outline_enabled': clip_node.get('outline_enabled', False),
                    'outline_color': clip_node.get('outline_color', config.DEFAULT_NODE_OUTLINE_COLOR),
                    'outline_width': clip_node.get('outline_width', config.DEFAULT_NODE_OUTLINE_WIDTH),
                    'outline_alpha': clip_node.get('outline_alpha', config.DEFAULT_NODE_OUTLINE_ALPHA)
                }
                self.nodes.append(new_node)
                self.node_id_counter += 1
                self.selected_nodes.append(new_node)
                old_id_to_new_node[clip_node['node_id']] = new_node

        # Paste edges (only if both endpoint nodes were pasted)
        for clip_edge in self.clipboard.get('edges', []):
            from_node_id = clip_edge['from_node_id']
            to_node_id = clip_edge['to_node_id']

            if from_node_id in old_id_to_new_node and to_node_id in old_id_to_new_node:
                from_new_node = old_id_to_new_node[from_node_id]
                to_new_node = old_id_to_new_node[to_node_id]
                new_edge = {
                    'from_node': from_new_node,
                    'to_node': to_new_node,
                    'from_node_id': from_new_node['node_id'],
                    'to_node_id': to_new_node['node_id'],
                    'label1': clip_edge.get('label1', ''),
                    'label2': clip_edge.get('label2', ''),
                    'linewidth_mult': clip_edge['linewidth_mult'],
                    'label_size_mult': clip_edge['label_size_mult'],
                    'label_offset_mult': clip_edge.get('label_offset_mult', 1.0),
                    'style': clip_edge['style'],
                    'direction': clip_edge['direction'],
                    'looptheta': clip_edge.get('looptheta', 30),
                    'flip_labels': clip_edge.get('flip_labels', False),
                    'label_rotation_offset': clip_edge.get('label_rotation_offset', 0),
                    'arrowstyle': clip_edge.get('arrowstyle', 'open'),
                    'arrowscale': clip_edge.get('arrowscale', 1.0),
                    'is_self_loop': clip_edge['is_self_loop']
                }
                # Restore self-loop specific parameters
                if clip_edge['is_self_loop']:
                    new_edge['selfloopangle'] = clip_edge.get('selfloopangle', 0)
                    new_edge['selfloopscale'] = clip_edge.get('selfloopscale', 1.0)
                    new_edge['arrowlengthsc'] = clip_edge.get('arrowlengthsc', 1.0)
                    new_edge['flip'] = clip_edge.get('flip', False)
                    new_edge['angle_pinned'] = clip_edge.get('angle_pinned', False)
                    new_edge['selflooplabelnudge'] = clip_edge.get('selflooplabelnudge', (0.0, 0.0))
                    new_edge['label_bgcolor'] = clip_edge.get('label_bgcolor', None)
                else:
                    new_edge['label1_bgcolor'] = clip_edge.get('label1_bgcolor', None)
                    new_edge['label2_bgcolor'] = clip_edge.get('label2_bgcolor', None)
                self.edges.append(new_edge)
                self.selected_edges.append(new_edge)

        msg = []
        if len(self.selected_nodes) > 0:
            msg.append(f"{len(self.selected_nodes)} node(s)")
        if len(self.selected_edges) > 0:
            msg.append(f"{len(self.selected_edges)} edge(s)")
        logger.info(f"Pasted {' and '.join(msg)}")
        self._update_plot()

    def _delete_selected_nodes(self):
        """Delete selected nodes and edges"""
        if not self.selected_nodes and not self.selected_edges:
            logger.info("No nodes or edges selected to delete")
            return

        self._save_state()

        # Delete selected nodes and any edges connected to them
        nodes_to_remove = list(self.selected_nodes)
        edges_to_remove = []

        for node in nodes_to_remove:
            if node in self.nodes:
                self.nodes.remove(node)
                # Find all edges connected to this node
                for edge in self.edges:
                    if edge['from_node'] == node or edge['to_node'] == node:
                        if edge not in edges_to_remove:
                            edges_to_remove.append(edge)

        # Delete selected edges
        for edge in self.selected_edges:
            if edge not in edges_to_remove and edge in self.edges:
                edges_to_remove.append(edge)

        # Remove all edges
        for edge in edges_to_remove:
            if edge in self.edges:
                self.edges.remove(edge)
            if edge in self.selected_edges:
                self.selected_edges.remove(edge)

        node_count = len(nodes_to_remove)
        edge_count = len(edges_to_remove)
        msg = []
        if node_count > 0:
            msg.append(f"{node_count} node(s)")
        if edge_count > 0:
            msg.append(f"{edge_count} edge(s)")
        logger.info(f"Deleted {' and '.join(msg)}")

        self.selected_nodes.clear()
        self.selected_edges.clear()
        self._update_plot()


    def _export_code(self):
        """Export graph as Python code using graph_primitives GraphCircuit"""
        if not self.nodes:
            logger.info("No nodes to export")
            return

        # Calculate full graph extents including all objects first
        # This will be used for both scaling calculations and final plot limits
        extent_x_min, extent_x_max, extent_y_min, extent_y_max = self._calculate_graph_extents()

        # Calculate graph center - we'll shift all coordinates to center at origin
        x_center = (extent_x_min + extent_x_max) / 2
        y_center = (extent_y_min + extent_y_max) / 2

        # Calculate the actual plot extent we'll use (with 10% padding)
        full_extent_span = max(extent_x_max - extent_x_min, extent_y_max - extent_y_min) * 1.1

        # Calculate points_per_data_unit for node label nudge calculations
        # This is still needed for vertical adjustment compensation
        figsize = 12
        fig_size_points = figsize * 72
        export_points_per_data_unit = fig_size_points / (full_extent_span * 2)  # *2 because extent is from -x_extent to +x_extent

        # NO fontscale_compensation needed anymore!
        # graph_primitives.py now auto-scales all labels (node, self-loop, edge) based on
        # points_per_data_unit, so they maintain correct proportions regardless of extent
        # All font size parameters (fontscale, selflooplabelscale, labelfontsize) now work
        # consistently as multipliers on auto-calculated base sizes

        # Debug: print the extent
        logger.debug(f"Graph extent span: {full_extent_span:.3f}")

        # Calculate linewidth scaling factor to keep linewidths proportional to node size
        # Linewidths are in points (absolute), but need to scale with graph extent
        # Use a reference extent (typical small graph is ~10-15 units after padding)
        reference_extent = 15.0
        lw_extent_scale = reference_extent / full_extent_span
        logger.debug(f"Linewidth extent scale factor: {lw_extent_scale:.3f}")

        # Use the export_rescale dictionary (tunable via UI in Export Scaling tab)
        # These parameters provide absolute control over scaling, independent of graph size
        RESCALE = self.export_rescale


        # Generate Python code
        code_lines = []
        code_lines.append("#!/usr/bin/env python")
        code_lines.append('"""')
        code_lines.append("Generated graph code using graph_primitives")
        code_lines.append('"""')
        code_lines.append("")
        code_lines.append("import matplotlib.pyplot as plt")
        code_lines.append("import graphulator.graph_primitives as gp")
        code_lines.append("import graphulator.graphulator_config as config")
        code_lines.append("")
        code_lines.append("# Create graph circuit (allow duplicate labels)")
        code_lines.append("# Set use_latex=True for LaTeX rendering, False for MathText (default)")
        use_latex_str = "True" if self.use_latex else "False"
        code_lines.append(f"graph = gp.GraphCircuit(allow_duplicate_labels=True, use_latex={use_latex_str})")
        code_lines.append("")

        # Check for duplicate labels
        label_counts = {}
        has_duplicates = False
        for node in self.nodes:
            label = node['label']
            label_counts[label] = label_counts.get(label, 0) + 1
            if label_counts[label] > 1:
                has_duplicates = True

        # Find self-loops for each node
        node_selfloops = {}  # Maps node_id to self-loop edge
        for edge in self.edges:
            if edge['is_self_loop']:
                node_selfloops[edge['from_node_id']] = edge

        code_lines.append("# Add nodes")

        for i, node in enumerate(self.nodes):
            label = node['label']
            # Handle empty labels - use space to avoid math parsing errors
            if not label or not label.strip():
                label = ' '
            node_id = node['node_id']
            x, y = node['pos']
            color_key = node['color_key']
            node_size_mult = node.get('node_size_mult', 1.0)
            label_size_mult = node.get('label_size_mult',1.0) * 0.75
            conj = node.get('conj', False)

            # HACK to fix the label_size_mult
            # label_size_mult *= 0.1

            # Use addnode for all nodes (consistent parameterization)
            radius = self.node_radius * node_size_mult

            # Check if this node has a self-loop
            has_selfloop = node_id in node_selfloops
            selfloop_edge = None
            selfloop_label = ''
            if has_selfloop:
                selfloop_edge = node_selfloops[node_id]
                selfloop_label = selfloop_edge.get('label1', '')

            # Shift coordinates to center graph at origin
            x_shifted = x - x_center
            y_shifted = y - y_center

            code_lines.append(f"# Node {i+1}: {label if label.strip() else '(blank)'}")
            if has_duplicates:
                # Include node_id to disambiguate
                code_lines.append(f"graph.addnode(label='{label}', xy=({x_shifted:.3f}, {y_shifted:.3f}), node_id={node_id},")
            else:
                code_lines.append(f"graph.addnode(label='{label}', xy=({x_shifted:.3f}, {y_shifted:.3f}),")
            code_lines.append(f"             nodecolor=config.MYCOLORS['{color_key}'],")
            code_lines.append(f"             R={radius:.3f},")
            # fontscale is now a simple multiplier - graph_primitives handles auto-scaling
            code_lines.append(f"             fontscale={label_size_mult * RESCALE['NODELABELSCALE']:.3f},")
            code_lines.append(f"             conj={conj},")

            # Add outline properties if enabled (qt stores free color strings)
            if node.get('outline_enabled', False):
                outline_color = node.get('outline_color', config.DEFAULT_NODE_OUTLINE_COLOR)
                outline_width = node.get('outline_width', config.DEFAULT_NODE_OUTLINE_WIDTH)
                outline_alpha = node.get('outline_alpha', config.DEFAULT_NODE_OUTLINE_ALPHA)
                code_lines.append(f"             nodeoutlinecolor='{outline_color}',")
                code_lines.append(f"             nodelw={outline_width:.1f},")
                code_lines.append(f"             nodeoutlinealpha={outline_alpha:.2f},")

            # Add nodelabelnudge if non-zero
            # Compensate for GUI's vertical adjustment (5% of font size downward)
            # so exported position matches GUI appearance
            nudge = node.get('nodelabelnudge', (0.0, 0.0))
            if nudge != (0.0, 0.0) and (abs(nudge[0]) > 0.001 or abs(nudge[1]) > 0.001):
                # Calculate vertical adjustment used in GUI rendering
                # Use export parameters to calculate points_per_data_unit
                conj_scale = config.CONJ_LABEL_SCALE if conj else 1.0
                font_size_points = radius * 2 * export_points_per_data_unit * 0.35 * label_size_mult * conj_scale
                adjustment_fraction = 0.05
                vertical_adjustment_points = font_size_points * adjustment_fraction
                vertical_adjustment_data = vertical_adjustment_points / export_points_per_data_unit

                # Subtract the adjustment from y-component of nudge for export
                # (GUI nudge is relative to adjusted position, export needs absolute position)
                export_nudge = (nudge[0], nudge[1] - vertical_adjustment_data)
                code_lines.append(f"             nodelabelnudge=({export_nudge[0]:.3f}, {export_nudge[1]:.3f}),")

            # Add self-loop parameters if this node has a self-loop
            if has_selfloop and selfloop_edge is not None:
                code_lines.append(f"             drawselfloop=True,")
                if selfloop_label:
                    # Auto-enclose label with $ signs for math mode if not already present
                    if not selfloop_label.startswith('$'):
                        export_label = f'${selfloop_label}$'
                    else:
                        export_label = selfloop_label
                    code_lines.append(f"             selflooplabel=r'{export_label}',")

                    # Add selflooplabelscale if non-default
                    label_size_mult = selfloop_edge.get('label_size_mult', 1.4)
                    if abs(label_size_mult - 1.4) > 0.01:
                        # selflooplabelscale works as multiplier relative to node label size
                        # It multiplies scaled_nodelabelsize, so it automatically scales proportionally
                        code_lines.append(f"             selflooplabelscale={label_size_mult * RESCALE['SELFLOOP_LABELSCALE']:.3f},")

                code_lines.append(f"             selflooplw={2.5 * selfloop_edge['linewidth_mult'] * RESCALE['SLLW'] * lw_extent_scale:.1f},")

                # Add selfloopangle
                selfloopangle = selfloop_edge.get('selfloopangle', 0)
                if selfloopangle != 0:
                    code_lines.append(f"             selfloopangle={selfloopangle},")

                # Add selfloopscale
                selfloopscale = selfloop_edge.get('selfloopscale', 1.0)
                if abs(selfloopscale - 1.0) > 0.01:
                    code_lines.append(f"             selfloopscale={selfloopscale * RESCALE['SLSC']:.3f},")

                # Add arrowlengthsc
                arrowlengthsc = selfloop_edge.get('arrowlengthsc', 1.0)
                if abs(arrowlengthsc - 1.0) > 0.01:
                    code_lines.append(f"             arrowlengthsc={arrowlengthsc:.3f},")

                # Add arrowstyle (self-loop arrowhead)
                sl_arrowstyle = selfloop_edge.get('arrowstyle', 'open')
                if sl_arrowstyle != 'open':
                    code_lines.append(f"             arrowstyle='{sl_arrowstyle}',")

                # Add flipselfloop
                flip = selfloop_edge.get('flip', False)
                if flip:
                    code_lines.append(f"             flipselfloop={flip},")

                # Add selflooplabelnudge if non-zero
                # Apply SELFLOOP_LABELNUDGE_SCALE and EXPORT_SELFLOOP_LABEL_DISTANCE
                nudge = selfloop_edge.get('selflooplabelnudge', (0.0, 0.0))
                nudge_scale = RESCALE.get('SELFLOOP_LABELNUDGE_SCALE', 1.0)
                export_distance_scale = RESCALE.get('EXPORT_SELFLOOP_LABEL_DISTANCE', 1.0)

                # Calculate scaled nudge accounting for both the fine-tuning nudge and distance scaling
                # The distance scale adjusts the overall radial position from the node center
                # We approximate this by scaling the nudge in the direction of the self-loop angle
                selfloopangle = selfloop_edge.get('selfloopangle', 0)
                angle_rad = selfloopangle * np.pi / 180

                # Base nudge from user adjustments
                scaled_nudge_x = nudge[0] * nudge_scale
                scaled_nudge_y = nudge[1] * nudge_scale

                # Add distance scaling component (moves label radially based on angle)
                if abs(export_distance_scale - 1.0) > 0.001:
                    # Calculate radial offset to adjust distance from node center
                    # This mimics changing the 3.2*R factor in the label positioning
                    radial_adjustment = (export_distance_scale - 1.0) * 0.5  # Scale factor for nudge
                    scaled_nudge_x += radial_adjustment * np.cos(angle_rad)
                    scaled_nudge_y += radial_adjustment * np.sin(angle_rad)

                if (abs(scaled_nudge_x) > 0.001 or abs(scaled_nudge_y) > 0.001):
                    code_lines.append(f"             selflooplabelnudge=({scaled_nudge_x:.3f}, {scaled_nudge_y:.3f}),")

                # Add selfloop label background color if set
                label_bgcolor = selfloop_edge.get('label_bgcolor', None)
                if label_bgcolor is not None:
                    code_lines.append(f"             selflooplabelbgcolor='{label_bgcolor}',")

                # Close the addnode call
                code_lines.append(f"             )")
            else:
                code_lines.append(f"             drawselfloop=False)")
            code_lines.append("")

        # Add edges if any exist (skip self-loops, they're handled in addnode)
        non_selfloop_edges = [e for e in self.edges if not e['is_self_loop']]
        if non_selfloop_edges:
            code_lines.append("# Add edges")
            for i, edge in enumerate(non_selfloop_edges):
                from_node = edge['from_node']
                to_node = edge['to_node']
                from_label = from_node['label']
                to_label = to_node['label']
                from_node_id = edge['from_node_id']
                to_node_id = edge['to_node_id']

                edge_label1 = edge.get('label1', '')
                edge_label2 = edge.get('label2', '')
                style = edge['style']
                direction = edge['direction']
                linewidth_mult = edge['linewidth_mult']
                label_size_mult = edge['label_size_mult']
                label_offset_mult = edge.get('label_offset_mult', 1.0)

                code_lines.append(f"# Edge {i+1}: {from_label} → {to_label}")

                # Calculate labeltheta from node positions
                from_pos = from_node['pos']
                to_pos = to_node['pos']
                dx = to_pos[0] - from_pos[0]
                dy = to_pos[1] - from_pos[1]
                labeltheta = np.arctan2(dy, dx) * 180 / np.pi

                # Flip labels by 180 degrees if requested
                if edge.get('flip_labels', False):
                    labeltheta += 180

                # Add fine-tuning rotation offset
                labeltheta += edge.get('label_rotation_offset', 0)

                # Base values for figsize=12
                base_lw = 4
                base_labelfontsize = 50 * 0.4
                base_labeloffset = 2.3

                # Apply multipliers and extent scaling
                # Scale linewidths inversely with extent to keep them proportional to circles
                scaled_lw = base_lw * linewidth_mult * lw_extent_scale
                scaled_labelfontsize = base_labelfontsize * label_size_mult
                scaled_labeloffset = base_labeloffset * label_offset_mult

                # Adjust linewidth for single/double styles (graph_primitives multiplies these)
                # Since we're passing 'lw' in loopkwargs, we need to pre-multiply
                single_double_lw_unit = 3.5
                if style == 'single':
                    scaled_lw *= single_double_lw_unit * 0.4
                elif style == 'double':
                    scaled_lw *= 0.9 * single_double_lw_unit
                elif style == 'loopy':
                    scaled_lw *= 0.4

                # Format labels - add $ if not already present
                def format_label(label_text):
                    if label_text:
                        if not label_text.startswith('$'):
                            return f'${label_text}$'
                        return label_text
                    return None

                formatted_label1 = format_label(edge_label1)
                formatted_label2 = format_label(edge_label2)

                # Build label list string
                label1_str = f"r'{formatted_label1}'" if formatted_label1 else "None"
                label2_str = f"r'{formatted_label2}'" if formatted_label2 else "None"
                label_str = f"[{label1_str}, {label2_str}]"

                # Use node_id if there are duplicates, otherwise use labels
                if has_duplicates:
                    code_lines.append(f"graph.addedge(fromnode_id={from_node_id}, tonode_id={to_node_id},")
                else:
                    code_lines.append(f"graph.addedge(fromnode='{from_label}', tonode='{to_label}',")
                code_lines.append(f"             label={label_str},")
                code_lines.append(f"             labeltheta={labeltheta:.1f},")
                code_lines.append(f"             labeloffset={scaled_labeloffset * RESCALE['EDGELABELOFFSET']:.1f},")
                code_lines.append(f"             labelfontsize={scaled_labelfontsize * RESCALE['EDGEFONTSCALE']:.0f},")

                # Add label background colors if set
                label1_bgcolor = edge.get('label1_bgcolor', None)
                label2_bgcolor = edge.get('label2_bgcolor', None)
                if label1_bgcolor or label2_bgcolor:
                    bgcolor1_str = f"'{label1_bgcolor}'" if label1_bgcolor else "None"
                    bgcolor2_str = f"'{label2_bgcolor}'" if label2_bgcolor else "None"
                    code_lines.append(f"             labelbgcolor=[{bgcolor1_str}, {bgcolor2_str}],")

                code_lines.append(f"             style='{style}',")
                code_lines.append(f"             whichedges='{direction}',")
                code_lines.append(f"             theta={edge.get('looptheta', 30)},")
                loopkwargs_parts = [f"'lw': {scaled_lw * RESCALE['EDGELWSCALE']:.1f}", "'arrowlength': 0.4"]
                arrowstyle = edge.get('arrowstyle', 'open')
                arrowscale = edge.get('arrowscale', 1.0)
                if arrowstyle != 'open':
                    loopkwargs_parts.append(f"'arrowstyle': '{arrowstyle}'")
                if abs(arrowscale - 1.0) > 0.01:
                    loopkwargs_parts.append(f"'arrowscale': {arrowscale:.3f}")
                code_lines.append(f"             loopkwargs={{{', '.join(loopkwargs_parts)}}})")
                code_lines.append("")

        code_lines.append("")
        code_lines.append("# Draw the graph")
        code_lines.append("# overfrac adds padding around the graph to ensure all elements are visible")
        code_lines.append("# Increase overfrac if labels or self-loops are cut off")
        code_lines.append("graph.draw(figsize=12, overfrac=0.2)")
        code_lines.append("")
        code_lines.append("plt.axis('off')")
        code_lines.append("plt.title('')  # Remove title")
        code_lines.append("plt.show()")

        # Join and copy to clipboard or print
        code = "\n".join(code_lines)

        # Try to copy to system clipboard
        try:
            clipboard = QApplication.clipboard()
            clipboard.setText(code)
            edge_str = f", {len(self.edges)} edge(s)" if self.edges else ""
            logger.info(f"✓ Exported code for {len(self.nodes)} node(s){edge_str} to clipboard")
        except Exception as e:
            logger.debug(f"Code export (clipboard failed: {e}, printing to console):")
            logger.debug("=" * 70)
            logger.debug(code)
            logger.debug("=" * 70)

    def _update_properties_panel(self):
        """Update the properties panel based on current selection"""
        # Single node selected
        if len(self.selected_nodes) == 1 and len(self.selected_edges) == 0:
            # Skip rebuilding if this object's widgets are already shown; rebuilding
            # destroys/recreates the input fields and kicks focus out while typing.
            if self.properties_panel.displayed_single is not self.selected_nodes[0]:
                self.properties_panel.show_node_properties(self.selected_nodes[0])
        # Single edge selected
        elif len(self.selected_edges) == 1 and len(self.selected_nodes) == 0:
            if self.properties_panel.displayed_single is not self.selected_edges[0]:
                self.properties_panel.show_edge_properties(self.selected_edges[0])
        # Multiple or mixed selection
        elif len(self.selected_nodes) > 1 or len(self.selected_edges) > 1:
            # Skip rebuilding if the same selection's widgets are already shown, so
            # fields keep focus while editing (same reasoning as the single-object case).
            signature = PropertiesPanel.selection_signature(self.selected_nodes, self.selected_edges)
            if self.properties_panel.displayed_multi != signature:
                self.properties_panel.show_multi_properties(self.selected_nodes, self.selected_edges)
        # No selection
        else:
            self.properties_panel.show_no_selection()

    def _auto_fit_view(self):
        """Auto-fit view to nodes"""
        if not self.nodes:
            logger.info("No nodes to fit view to")
            return

        positions = np.array([node['pos'] for node in self.nodes])
        centroid = positions.mean(axis=0)

        distances = np.sqrt(((positions - centroid) ** 2).sum(axis=1))
        max_distance = distances.max() + self.node_radius

        extent = max_distance * config.AUTOFIT_PADDING_FACTOR

        self.base_xlim = (centroid[0] - extent, centroid[0] + extent)
        self.base_ylim = (centroid[1] - extent, centroid[1] + extent)
        self.zoom_level = 1.0

        logger.debug(f"Auto-fit: centered on ({centroid[0]:.3f}, {centroid[1]:.3f}), extent={extent:.3f}")
        self._update_plot()

    def _update_plot_no_grid(self):
        """Redraw the plot without grid (for export)"""
        # Clear any stale preview patches first
        self._clear_all_previews()

        self.canvas.ax.clear()

        # Set limits and aspect FIRST before drawing
        self.canvas.ax.set_xlim(*self._get_xlim())
        self.canvas.ax.set_ylim(*self._get_ylim())
        self.canvas.ax.set_aspect('equal', adjustable='datalim', anchor='C')
        # Force axes to use full figure area (reapply after aspect is set)
        self.canvas.ax.set_position([0, 0, 1, 1])

        # Skip grid drawing for export

        # Draw edges BEFORE nodes so nodes appear on top
        self._draw_edges()

        # Draw nodes (now after aspect is set, so limits are correct)
        self._draw_nodes()

        # No edge mode highlight for export

        # No title for export
        self.canvas.ax.set_title('')
        self.canvas.ax.axis('off')

        # Disable per-artist clipping so the SVG/PDF carries no full-canvas clip
        # rectangle. matplotlib clips every artist to the axes box (the whole
        # 12x12 figure); Illustrator imports that clip as a second, canvas-sized
        # bounding box that dwarfs the graph when zoomed out. The export is
        # cropped to content via bbox_inches, so clipping is unnecessary here.
        for artist in self.canvas.ax.findobj():
            artist.set_clip_on(False)

        # Update properties panel
        if self.selected_nodes and len(self.selected_nodes) == 1:
            self.properties_panel.show_node_properties(self.selected_nodes[0])
        elif self.selected_edges and len(self.selected_edges) == 1:
            self.properties_panel.show_edge_properties(self.selected_edges[0])
        else:
            self.properties_panel.show_no_selection()

        self.canvas.draw()

    def _update_plot(self, force_latex=False, use_idle=True):
        """Redraw the plot.

        Labels are rendered from the cached vector glyph-path renderer
        (:class:`LabelPathCache`), so LaTeX-quality output stays crisp and fast
        across pan/zoom/rescale without re-invoking the layout engine.  The old
        fast/slow MathText<->LaTeX debounce hack is therefore no longer needed.

        Args:
            force_latex: Retained for backwards compatibility; no longer affects
                behaviour (rendering is always immediate and crisp).
            use_idle: Accepted for signature compatibility with the shared
                fast-view path; rendering always uses draw_idle here.
        """
        self._do_plot_render()


    def _do_plot_render(self):
        """Actually perform the plot rendering"""
        # Clear any stale preview patches first
        self._clear_all_previews()

        self.canvas.ax.clear()



        # Set limits and aspect FIRST before drawing
        self.canvas.ax.set_xlim(*self._get_xlim())
        self.canvas.ax.set_ylim(*self._get_ylim())
        self.canvas.ax.set_aspect('equal', adjustable='datalim', anchor='C')
        # Force axes to use full figure area (reapply after aspect is set)
        self.canvas.ax.set_position([0, 0, 1, 1])

        # Draw grid
        self._draw_grid()

        # Draw edges BEFORE nodes so nodes appear on top
        self._draw_edges()

        # Draw nodes (now after aspect is set, so limits are correct)
        self._draw_nodes()

        # Draw edge mode highlight (if first node is selected)
        if self.placement_mode in ['edge', 'edge_continuous'] and self.edge_mode_first_node is not None:
            node = self.edge_mode_first_node
            highlight_circle = patches.Circle(
                node['pos'], self.node_radius * node.get('node_size_mult', 1.0) * 1.3,
                facecolor='none',
                edgecolor='firebrick',
                linewidth=2,
                linestyle=':',
                zorder=15
            )
            self.canvas.ax.add_patch(highlight_circle)

        # Update status bar instead of title
        self._update_status_label()

        # No title on plot
        self.canvas.ax.set_title('')
        self.canvas.ax.axis('off')

        # draw_idle coalesces repaints and avoids the re-entrancy hazards of
        # pumping the event loop (processEvents) mid-render. The snapshot code
        # below reads only limits/artist attributes, not the renderer.
        self.canvas.draw_idle()

        # Update properties panel based on selection
        self._update_properties_panel()

        # Snapshot the scene for the fast pan/zoom path: current ppu + per-artist
        # base linewidths (grid excluded; it has fixed width and is rebuilt only
        # when the view grows past its extent).
        self._build_ppu = self._points_per_data_unit(
            self.canvas.ax.get_xlim(), self.canvas.ax.get_ylim())
        self._zoom_lw_snapshot = [
            (a, a.get_linewidth())
            for a in (list(self.canvas.ax.lines) + list(self.canvas.ax.patches))
            if a.get_gid() != 'grid' and a.get_linewidth()
        ]


    def _update_status_label(self):
        """Refresh the status bar text (cheap; used by both full and fast renders)."""
        mode_str = f" | Mode: {self.placement_mode}" if self.placement_mode else ""
        edge_str = f" | Edges: {len(self.edges)}" if self.edges else ""
        latex_str = " | LaTeX" if self.use_latex else ""
        fast_str = " (fast)" if self.is_fast_rendering else ""
        self.status_label.setText(
            f'{self.grid_type.capitalize()} Grid (rotation={self.grid_rotation}°, '
            f'zoom={self.zoom_level:.3f}x) | Nodes: {len(self.nodes)}'
            f'{edge_str}{mode_str}{latex_str}{fast_str}'
        )


def main():
    from graphulator._resources import resource_path

    app = QApplication(sys.argv)
    app.setApplicationName("Graphulator")
    icon_path = resource_path("assets", "graphulator_ICON.png")
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = Graphulator()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
