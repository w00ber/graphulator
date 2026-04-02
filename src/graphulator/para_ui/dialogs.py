"""
Dialog widgets for paragraphulator.

This module contains the node and edge input dialogs.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QSlider, QCheckBox, QDialogButtonBox, QSpinBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from .. import graphulator_para_config as config
from .widgets import FineControlSpinBox


class NodeInputDialog(QDialog):
    """Dialog for inputting node properties"""

    # Class variables to persist last choices
    last_color = config.DEFAULT_NODE_COLOR_KEY
    last_node_size = config.DEFAULT_NODE_SIZE_MULT
    last_label_size = config.DEFAULT_NODE_LABEL_SIZE_MULT
    last_conj = config.DEFAULT_NODE_CONJUGATED
    last_outline_enabled = config.DEFAULT_NODE_OUTLINE_ENABLED
    last_outline_color = 'BLACK'
    last_outline_width = config.DEFAULT_NODE_OUTLINE_WIDTH
    last_outline_alpha = config.DEFAULT_NODE_OUTLINE_ALPHA

    def __init__(self, default_label='A', default_color='BLUE', parent=None, node=None, graphulator=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Node" if node else "Add Node")
        self.setModal(True)

        # Store result
        self.result = None

        # Store reference to node being edited (if any) and graphulator for live updates
        self.editing_node = node
        self.graphulator = graphulator

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

        # Connect for live updates
        self.color_combo.currentIndexChanged.connect(self._update_color_live)

        color_layout.addWidget(self.color_combo)
        layout.addLayout(color_layout)

        # Node size selection
        node_size_layout = QHBoxLayout()
        node_size_layout.addWidget(QLabel("Node Size:"))
        self.node_size_slider = QSlider(Qt.Horizontal)
        self.node_size_slider.setMinimum(config.NODE_SIZE_SLIDER_MIN)
        self.node_size_slider.setMaximum(config.NODE_SIZE_SLIDER_MAX)
        self.node_size_slider.setValue(int(self.last_node_size * 100))
        self.node_size_slider.valueChanged.connect(self._update_node_size_label)
        self.node_size_label = QLabel(f"{self.last_node_size:.3f}x")
        self.node_size_label.setMinimumWidth(60)
        node_size_layout.addWidget(self.node_size_slider)
        node_size_layout.addWidget(self.node_size_label)
        layout.addLayout(node_size_layout)

        # Label size selection
        label_size_layout = QHBoxLayout()
        label_size_layout.addWidget(QLabel("Label Size:"))
        self.label_size_slider = QSlider(Qt.Horizontal)
        self.label_size_slider.setMinimum(config.NODE_LABEL_SIZE_SLIDER_MIN)
        self.label_size_slider.setMaximum(config.NODE_LABEL_SIZE_SLIDER_MAX)
        self.label_size_slider.setValue(int(self.last_label_size * 100))
        self.label_size_slider.valueChanged.connect(self._update_label_size_label)
        self.label_size_label = QLabel(f"{self.last_label_size:.3f}x")
        self.label_size_label.setMinimumWidth(60)
        label_size_layout.addWidget(self.label_size_slider)
        label_size_layout.addWidget(self.label_size_label)
        layout.addLayout(label_size_layout)

        # Conjugation checkbox
        conj_layout = QHBoxLayout()
        conj_layout.addWidget(QLabel("Conjugated:"))
        self.conj_checkbox = QCheckBox()
        self.conj_checkbox.setChecked(self.last_conj)
        # Connect for live updates
        self.conj_checkbox.stateChanged.connect(self._update_conj_live)
        conj_layout.addWidget(self.conj_checkbox)
        layout.addLayout(conj_layout)

        # Outline checkbox
        outline_layout = QHBoxLayout()
        outline_layout.addWidget(QLabel("Outline:"))
        self.outline_checkbox = QCheckBox()
        self.outline_checkbox.setChecked(self.last_outline_enabled)
        self.outline_checkbox.stateChanged.connect(self._update_outline_enabled_live)
        outline_layout.addWidget(self.outline_checkbox)
        layout.addLayout(outline_layout)

        # Outline color selection
        outline_color_layout = QHBoxLayout()
        outline_color_layout.addWidget(QLabel("Outline Color:"))
        self.outline_color_combo = QComboBox()

        # Add colors to combo box with visual colors
        for color_key, color_value in config.MYCOLORS.items():
            self.outline_color_combo.addItem(f"  {color_key}", color_key)
            idx = self.outline_color_combo.count() - 1
            self.outline_color_combo.setItemData(idx, QColor(color_value), Qt.BackgroundRole)

        # Set to last used outline color
        try:
            last_idx = list(config.MYCOLORS.keys()).index(self.last_outline_color)
            self.outline_color_combo.setCurrentIndex(last_idx)
        except:
            self.outline_color_combo.setCurrentIndex(list(config.MYCOLORS.keys()).index('BLACK'))

        self.outline_color_combo.currentIndexChanged.connect(self._update_outline_color_live)
        outline_color_layout.addWidget(self.outline_color_combo)
        layout.addLayout(outline_color_layout)

        # Outline width selection
        outline_width_layout = QHBoxLayout()
        outline_width_layout.addWidget(QLabel("Outline Width:"))
        self.outline_width_spin = FineControlSpinBox()
        self.outline_width_spin.setRange(0.5, 10.0)
        self.outline_width_spin.setDecimals(1)
        self.outline_width_spin.setSingleStep(0.5)
        self.outline_width_spin.setValue(self.last_outline_width)
        self.outline_width_spin.valueChanged.connect(self._update_outline_width_live)
        outline_width_layout.addWidget(self.outline_width_spin)
        layout.addLayout(outline_width_layout)

        # Outline alpha selection
        outline_alpha_layout = QHBoxLayout()
        outline_alpha_layout.addWidget(QLabel("Outline Alpha:"))
        self.outline_alpha_spin = FineControlSpinBox()
        self.outline_alpha_spin.setRange(0.0, 1.0)
        self.outline_alpha_spin.setDecimals(2)
        self.outline_alpha_spin.setSingleStep(0.05)
        self.outline_alpha_spin.setValue(self.last_outline_alpha)
        self.outline_alpha_spin.valueChanged.connect(self._update_outline_alpha_live)
        outline_alpha_layout.addWidget(self.outline_alpha_spin)
        layout.addLayout(outline_alpha_layout)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

        # Make compact (increased height for outline controls)
        self.setFixedSize(400, 410)

    def _update_node_size_label(self):
        """Update node size label when slider changes"""
        mult = self.node_size_slider.value() / 100.0
        self.node_size_label.setText(f"{mult:.3f}x")
        # Live update if editing an existing node
        if self.editing_node and self.graphulator:
            self.editing_node['node_size_mult'] = mult
            self.graphulator._update_plot()

    def _update_label_size_label(self):
        """Update label size label when slider changes"""
        mult = self.label_size_slider.value() / 100.0
        self.label_size_label.setText(f"{mult:.3f}x")
        # Live update if editing an existing node
        if self.editing_node and self.graphulator:
            self.editing_node['label_size_mult'] = mult
            self.graphulator._update_plot()

    def _update_color_live(self):
        """Update node color in real-time when color combo changes"""
        if self.editing_node and self.graphulator:
            color_key = self.color_combo.currentData()
            self.editing_node['color'] = config.MYCOLORS[color_key]
            self.editing_node['color_key'] = color_key
            self.graphulator._update_plot()

    def _update_conj_live(self):
        """Update node conjugation in real-time when checkbox changes"""
        if self.editing_node and self.graphulator:
            self.editing_node['conj'] = self.conj_checkbox.isChecked()
            # Update edge styles for edges connected to this node
            self.graphulator._update_edge_styles_for_node(self.editing_node)
            # Update conjugate pair constraints (may create or dissolve constraint groups)
            self.graphulator._update_conjugate_pair_constraints()
            self.graphulator._update_plot()

    def _update_outline_enabled_live(self):
        """Update node outline enabled state in real-time"""
        if self.editing_node and self.graphulator:
            self.editing_node['outline_enabled'] = self.outline_checkbox.isChecked()
            self.graphulator._update_plot()

    def _update_outline_color_live(self):
        """Update node outline color in real-time"""
        if self.editing_node and self.graphulator:
            outline_color_key = self.outline_color_combo.currentData()
            self.editing_node['outline_color'] = config.MYCOLORS[outline_color_key]
            self.editing_node['outline_color_key'] = outline_color_key
            self.graphulator._update_plot()

    def _update_outline_width_live(self):
        """Update node outline width in real-time"""
        if self.editing_node and self.graphulator:
            self.editing_node['outline_width'] = self.outline_width_spin.value()
            self.graphulator._update_plot()

    def _update_outline_alpha_live(self):
        """Update node outline alpha in real-time"""
        if self.editing_node and self.graphulator:
            self.editing_node['outline_alpha'] = self.outline_alpha_spin.value()
            self.graphulator._update_plot()

    def accept(self):
        """Handle OK button"""
        from PySide6.QtWidgets import QMessageBox

        label = self.label_edit.text().strip()

        # Check for asterisk in label (reserved for conjugation display)
        if '*' in label:
            QMessageBox.warning(
                self,
                "Invalid Character",
                "The asterisk (*) is reserved for conjugation display.\n"
                "It has been removed from your label.\n\n"
                "To mark a node as conjugated, use the 'Conjugated' checkbox or press C."
            )
            label = label.replace('*', '')
            self.label_edit.setText(label)

        if not label:
            label = self.label_edit.placeholderText()

        color_key = self.color_combo.currentData()
        node_size_mult = self.node_size_slider.value() / 100.0
        label_size_mult = self.label_size_slider.value() / 100.0
        conj = self.conj_checkbox.isChecked()
        outline_enabled = self.outline_checkbox.isChecked()
        outline_color_key = self.outline_color_combo.currentData()
        outline_width = self.outline_width_spin.value()
        outline_alpha = self.outline_alpha_spin.value()

        # Persist choices for next node
        NodeInputDialog.last_color = color_key
        NodeInputDialog.last_node_size = node_size_mult
        NodeInputDialog.last_label_size = label_size_mult
        NodeInputDialog.last_conj = conj
        NodeInputDialog.last_outline_enabled = outline_enabled
        NodeInputDialog.last_outline_color = outline_color_key
        NodeInputDialog.last_outline_width = outline_width
        NodeInputDialog.last_outline_alpha = outline_alpha

        self.result = {
            'label': label,
            'color_key': color_key,
            'color': config.MYCOLORS[color_key],
            'node_size_mult': node_size_mult,
            'label_size_mult': label_size_mult,
            'conj': conj,
            'outline_enabled': outline_enabled,
            'outline_color_key': outline_color_key,
            'outline_color': config.MYCOLORS[outline_color_key],
            'outline_width': outline_width,
            'outline_alpha': outline_alpha
        }
        super().accept()

    def get_result(self):
        """Return the dialog result"""
        return self.result


class EdgeInputDialog(QDialog):
    """Dialog for inputting edge properties - simplified for parametric graphs"""

    # Class variables to persist last choices
    last_linewidth = 'Medium'
    last_direction = 'both'

    def __init__(self, node1_label='A', node2_label='B', is_self_loop=False, node1_conj=False, node2_conj=False, parent=None, edge=None, graphulator=None):
        super().__init__(parent)
        self.setWindowTitle("Self-Loop" if is_self_loop else "Edge")
        self.setModal(True)

        # Store result
        self.result = None
        self.is_self_loop = is_self_loop
        self.node1_conj = node1_conj
        self.node2_conj = node2_conj

        # Store reference to edge being edited (if any) and graphulator for live updates
        self.editing_edge = edge
        self.graphulator = graphulator

        # Create layout
        layout = QVBoxLayout()

        # For non-self-loops, show info about auto-determined style
        if not is_self_loop:
            # Determine style based on conjugation states
            same_conj = (node1_conj == node2_conj)
            auto_style = 'single' if same_conj else 'double'

            info_label = QLabel(f"Edge style: <b>{auto_style}</b> (auto-determined from conjugation states)")
            info_label.setWordWrap(True)
            layout.addWidget(info_label)
            layout.addSpacing(10)

        # Linewidth dropdown
        lw_layout = QHBoxLayout()
        lw_layout.addWidget(QLabel("Line Width:"))
        self.lw_combo = QComboBox()
        lw_options = ['Thin', 'Medium', 'Thick', 'X-Thick']
        self.lw_combo.addItems(lw_options)
        self.lw_combo.setCurrentText(EdgeInputDialog.last_linewidth)
        self.lw_combo.currentTextChanged.connect(self._update_linewidth_live)
        lw_layout.addWidget(self.lw_combo)
        layout.addLayout(lw_layout)

        # Style is now None for both self-loops and regular edges (auto-determined)
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
            # Set default angle from config
            default_angle = config.DEFAULT_SELFLOOP_ANGLE
            angle_index = default_angle // 45  # 0->0, 45->1, 90->2, etc.
            self.angle_combo.setCurrentIndex(min(angle_index, len(angle_options) - 1))
            self.angle_combo.currentTextChanged.connect(self._update_angle_live)
            angle_layout.addWidget(self.angle_combo)
            layout.addLayout(angle_layout)

            # Scale dropdown
            scale_layout = QHBoxLayout()
            scale_layout.addWidget(QLabel("Loop Size:"))
            self.scale_combo = QComboBox()
            scale_options = list(config.SELFLOOP_SCALE_OPTIONS.keys())
            self.scale_combo.addItems(scale_options)
            # Set default scale from config
            default_scale = config.DEFAULT_SELFLOOP_SCALE
            scale_index = 1  # fallback to Medium
            for i, (name, val) in enumerate(config.SELFLOOP_SCALE_OPTIONS.items()):
                if abs(val - default_scale) < 0.01:
                    scale_index = i
                    break
            self.scale_combo.setCurrentIndex(scale_index)
            self.scale_combo.currentTextChanged.connect(self._update_scale_live)
            scale_layout.addWidget(self.scale_combo)
            layout.addLayout(scale_layout)

            # Flip checkbox
            flip_loop_layout = QHBoxLayout()
            flip_loop_layout.addWidget(QLabel("Flip Direction:"))
            self.flip_loop_checkbox = QCheckBox()
            self.flip_loop_checkbox.setChecked(False)
            self.flip_loop_checkbox.stateChanged.connect(self._update_flip_live)
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
        else:
            self.dir_combo = None
            self.looptheta_spinbox = None

        # OK/Cancel buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

    def _update_linewidth_live(self):
        """Update edge linewidth in real-time"""
        if self.editing_edge and self.graphulator:
            lw_text = self.lw_combo.currentText()
            self.editing_edge['linewidth_mult'] = config.EDGE_LINEWIDTH_OPTIONS[lw_text]
            self.graphulator._update_plot()

    def _update_angle_live(self):
        """Update self-loop angle in real-time"""
        if self.editing_edge and self.graphulator and self.is_self_loop:
            angle_text = self.angle_combo.currentText()
            selfloopangle = int(angle_text.split('°')[0])
            self.editing_edge['selfloopangle'] = selfloopangle
            self.graphulator._update_plot()

    def _update_scale_live(self):
        """Update self-loop scale in real-time"""
        if self.editing_edge and self.graphulator and self.is_self_loop:
            scale_text = self.scale_combo.currentText()
            selfloopscale = config.SELFLOOP_SCALE_OPTIONS[scale_text]
            self.editing_edge['selfloopscale'] = selfloopscale
            self.graphulator._update_plot()

    def _update_flip_live(self):
        """Update self-loop flip in real-time"""
        if self.editing_edge and self.graphulator and self.is_self_loop:
            self.editing_edge['flip'] = self.flip_loop_checkbox.isChecked()
            self.graphulator._update_plot()

    def accept(self):
        """Store the input values when OK is clicked"""
        # No edge labels in parametric version - always empty
        label1 = ''
        label2 = ''

        linewidth = self.lw_combo.currentText()

        # Determine style based on conjugation states (for non-self-loops)
        if not self.is_self_loop:
            same_conj = (self.node1_conj == self.node2_conj)
            style = 'single' if same_conj else 'double'
        else:
            style = 'loopy'  # Self-loops always use loopy style

        direction = self.dir_combo.currentText() if self.dir_combo else 'both'

        # Self-loop specific parameters
        if self.is_self_loop and self.angle_combo and self.scale_combo and self.flip_loop_checkbox:
            angle_text = self.angle_combo.currentText()
            selfloopangle = int(angle_text.split('°')[0])  # Extract angle from "0° (Right)"

            scale_text = self.scale_combo.currentText()
            selfloopscale = config.SELFLOOP_SCALE_OPTIONS[scale_text]

            flip_loop = self.flip_loop_checkbox.isChecked()
        else:
            selfloopangle = 0
            selfloopscale = 1.0
            flip_loop = False

        # Persist choices for next edge
        EdgeInputDialog.last_linewidth = linewidth
        if not self.is_self_loop:
            EdgeInputDialog.last_direction = direction

        # Linewidth multipliers (for figsize=12, medium=5.5)
        lw_map = config.EDGE_LINEWIDTH_OPTIONS

        # Get looptheta value from spinbox (if not self-loop)
        looptheta = 30  # Default
        if not self.is_self_loop and hasattr(self, 'looptheta_spinbox') and self.looptheta_spinbox:
            looptheta = self.looptheta_spinbox.value()

        # For self-loops, use config default for arrowlengthsc (linewidth scale)
        arrowlengthsc = config.DEFAULT_SELFLOOP_ARROWLENGTH if self.is_self_loop else 1.0

        self.result = {
            'label1': label1,
            'label2': label2,
            'linewidth_mult': lw_map[linewidth],
            'label_size_mult': 1.0,  # Default, no user control in parametric version
            'label_offset_mult': 1.0,  # Default, no user control in parametric version
            'style': style,
            'direction': direction,
            'flip_labels': False,  # No labels, so no flipping
            'looptheta': looptheta,
            'selfloopangle': selfloopangle,
            'selfloopscale': selfloopscale,
            'flip': flip_loop,
            'arrowlengthsc': arrowlengthsc
        }
        super().accept()

    def get_result(self):
        """Return the dialog result"""
        return self.result
