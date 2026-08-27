"""Explicit ports & transmission-line macros for paragraphulator.

This module holds the GUI-side feature surface for hub-based dissipation:
port glyphs (monitored hubs), loss-hub glyphs (unmonitored), transmission-line
macro glyphs (LineResonator), their attachment links, placement modes,
canvas drawing, panel data, serialization fragments, and the extractor
payload builders.

The feature is gated by the ``EXPLICIT_PORTS_MODE`` setting (Settings ->
Interface). With the switch OFF the app looks and behaves exactly as before
(legacy per-node B_ext self-loops); the underlying numerics are hub-based
either way — the switch gates the GUI surface only. Opening a .pgraph that
contains ports or lines auto-enables the mode for the session and notifies
the user.

Data shapes (GUI-side; the extractor schema lives in autograph.py):

    port = {
        'port_id': int,               # unique within the graph
        'label': str,
        'pos': (x, y),
        'monitored': bool,            # True -> port, False -> loss hub
        'attachments': [
            {'node_id': int, 'rate': float, 'sign': +1|-1},
            ...                       # rate in arb. units (kappa = sqrt(rate))
        ],
    }

    line = {
        'line_id': int,
        'label': str,
        'pos': (x, y),
        'FSR': float, 'Ztx': float, 'f_max': float,
        'port_end': None|'x0'|'xL',
        'Z0_port': float, 'alpha_uniform': float,
    }

Phase-2 items deliberately NOT implemented here (blocked on derivations —
see autograph.py's blocked list): complex attachment weights (the per-link
phase widget is present but locked to 0/180), mixed-sector hubs, two-port
lines, band-limited combs.

TODO (tracked, glyph vocabulary): the loss hub currently renders as a
hatched variant of the port pentagon. The final dissipative-hub glyph is an
OPEN schema decision — "H" is reserved for the reactive hub — so do not
treat the hatched pentagon as permanent.
"""

import logging

import numpy as np
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
import matplotlib.transforms as mtransforms

from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QVBoxLayout,
                               QFormLayout, QLabel, QLineEdit, QCheckBox,
                               QComboBox, QMessageBox, QDoubleSpinBox)

from ..autograph import LineResonator

logger = logging.getLogger(__name__)

# Phase-2 tooltip shown on every locked phase widget
PHASE2_PHASE_TOOLTIP = (
    "Phase-1 hub weights are real signed (0\N{DEGREE SIGN} or "
    "180\N{DEGREE SIGN} only). Complex weights are Phase 2, blocked on the "
    "M_pumped two-sector derivation."
)

# Glyph geometry (data units, scaled by the node radius at draw time)
PORT_BODY_W = 1.6     # pentagon body width (x node_radius)
PORT_BODY_H = 1.2     # pentagon height
PORT_APEX_W = 0.7     # apex extension beyond the body
PORT_LEAD_LEN = 0.6   # thick lead at the apex
LINE_BODY_W = 2.6     # cylinder half-width
LINE_BODY_H = 0.8     # cylinder half-height
LINE_LEAD_LEN = 0.7


def _line_extractor_id(line):
    """Stable extractor line_id for a GUI line resonator."""
    return f"line:{line['line_id']}"


def _rotate_point(x, y, cx, cy, angle_deg):
    """Rotate (x, y) about (cx, cy) by angle_deg CCW."""
    if not angle_deg:
        return x, y
    a = np.radians(angle_deg)
    dx, dy = x - cx, y - cy
    return (cx + dx * np.cos(a) - dy * np.sin(a),
            cy + dx * np.sin(a) + dy * np.cos(a))


#: Tooltip for the line's alpha parameter (dialog + panel).
ALPHA_TOOLTIP = (
    "One-way amplitude attenuation \N{GREEK SMALL LETTER ALPHA}\N{MIDDLE DOT}"
    "\N{MATHEMATICAL ITALIC SMALL L} of the line, in nepers.\n"
    "1 Np = 8.686 dB, so \N{GREEK SMALL LETTER ALPHA} = (one-way insertion "
    "loss in dB) / 8.686;  0 = lossless.\n\n"
    "Spatially uniform loss damps EVERY comb mode identically (mode\n"
    "orthogonality in the open\N{EN DASH}open basis), as ordinary per-mode "
    "internal loss:\n"
    "    B_int = (2/\N{GREEK SMALL LETTER PI}) \N{MIDDLE DOT} "
    "\N{GREEK SMALL LETTER ALPHA} \N{MIDDLE DOT} FSR      (same linewidth "
    "for all modes,\n"
    "     so internal Q of mode n is Q = n\N{GREEK SMALL LETTER PI}/"
    "(2\N{GREEK SMALL LETTER ALPHA}))\n\n"
    "Mapping verified against a lossy-ABCD reference "
    "(tests/test_uniform_loss.py).\n"
    "Localized loss is a different species: use an (unmonitored) loss hub."
)


def port_hub_payload(port):
    """GUI port -> extractor hub dict (kappa = sign * sqrt(rate)).

    Same conversion as autograph.pgraph_port_to_hub — the GUI dict and the
    .pgraph 'ports' entry share one schema, so the programmatic
    extract_from_pgraph route and the live GUI route stay in lockstep.
    """
    from ..autograph import pgraph_port_to_hub
    return pgraph_port_to_hub(port)


def line_payload(line):
    """GUI line dict -> extractor LineResonator kwargs dict."""
    return {
        'line_id': _line_extractor_id(line),
        'label': line['label'],
        'FSR': float(line['FSR']),
        'Ztx': float(line['Ztx']),
        'f_max': float(line['f_max']),
        'port_end': line.get('port_end', 'xL'),
        'Z0_port': float(line.get('Z0_port', 50.0)),
        'alpha_uniform': float(line.get('alpha_uniform', 0.0)),
    }


class PortInputDialog(QDialog):
    """Label + monitored/loss choice for a new (or edited) port glyph."""

    def __init__(self, default_label='P1', monitored=True, parent=None,
                 editing=False):
        super().__init__(parent)
        self.setWindowTitle("Edit Port" if editing else "Place Port")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.label_edit = QLineEdit(default_label)
        form.addRow("Label:", self.label_edit)
        self.monitored_check = QCheckBox("Monitored (scattering port)")
        self.monitored_check.setChecked(monitored)
        self.monitored_check.setToolTip(
            "Checked: a port — its damping appears in M and it is a channel "
            "of S.\nUnchecked: a loss hub — same damping in M, no channel "
            "(energy exits unobserved).")
        form.addRow(self.monitored_check)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.label_edit.setFocus()
        self.label_edit.selectAll()

    def get_result(self):
        return {'label': self.label_edit.text().strip() or 'P',
                'monitored': self.monitored_check.isChecked()}


class LineInputDialog(QDialog):
    """Property panel for a transmission-line (LineResonator) glyph."""

    PORT_ENDS = [("x = L (alternating signs)", 'xL'),
                 ("x = 0 (all-plus signs)", 'x0'),
                 ("None (isolated comb)", None)]

    def __init__(self, line=None, default_label='TL1', parent=None):
        super().__init__(parent)
        editing = line is not None
        self.setWindowTitle("Edit Transmission Line" if editing
                            else "Place Transmission Line")
        line = line or {}
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.label_edit = QLineEdit(line.get('label', default_label))
        form.addRow("Label:", self.label_edit)

        def spin(value, lo, hi, decimals=4, step=1.0, tooltip=''):
            box = QDoubleSpinBox()
            box.setRange(lo, hi)
            box.setDecimals(decimals)
            box.setSingleStep(step)
            box.setValue(value)
            if tooltip:
                box.setToolTip(tooltip)
            return box

        self.fsr_spin = spin(line.get('FSR', 1.0), 1e-9, 1e9, 4, 0.1,
                             "Free spectral range [a.u.] (comb mode spacing)")
        form.addRow("FSR [au]:", self.fsr_spin)
        self.ztx_spin = spin(line.get('Ztx', 65.0), 1e-6, 1e6, 2, 1.0,
                             "Line characteristic impedance")
        form.addRow("Ztx [\N{GREEK CAPITAL LETTER OMEGA}]:", self.ztx_spin)
        self.fmax_spin = spin(line.get('f_max', 10.0), 1e-9, 1e12, 4, 1.0,
                              "Comb extent: N = ceil(f_max/FSR) mode pairs "
                              "from DC (full comb — band-limiting is Phase 2)")
        form.addRow("f_max [au]:", self.fmax_spin)

        self.port_end_combo = QComboBox()
        for text, value in self.PORT_ENDS:
            self.port_end_combo.addItem(text, value)
        current_end = line.get('port_end', 'xL')
        idx = next((i for i, (_, v) in enumerate(self.PORT_ENDS)
                    if v == current_end), 0)
        self.port_end_combo.setCurrentIndex(idx)
        self.port_end_combo.setToolTip(
            "Which end carries the port termination. One port per line "
            "(Phase 1); the other end is open.")
        form.addRow("Port end:", self.port_end_combo)

        self.z0_spin = spin(line.get('Z0_port', 50.0), 1e-6, 1e6, 2, 1.0,
                            "Port termination impedance")
        form.addRow("Z0 [\N{GREEK CAPITAL LETTER OMEGA}]:", self.z0_spin)

        self.alpha_spin = spin(line.get('alpha_uniform', 0.0), 0.0, 100.0, 6,
                               0.001, ALPHA_TOOLTIP)
        alpha_label = QLabel("\N{GREEK SMALL LETTER ALPHA} [Np]:")
        alpha_label.setToolTip(ALPHA_TOOLTIP)
        form.addRow(alpha_label, self.alpha_spin)

        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_result(self):
        return {
            'label': self.label_edit.text().strip() or 'TL',
            'FSR': self.fsr_spin.value(),
            'Ztx': self.ztx_spin.value(),
            'f_max': self.fmax_spin.value(),
            'port_end': self.port_end_combo.currentData(),
            'Z0_port': self.z0_spin.value(),
            'alpha_uniform': self.alpha_spin.value(),
        }


class AttachmentEditDialog(QDialog):
    """Per-link editor: coupling rate magnitude + sign; phase locked (Phase 2)."""

    def __init__(self, port_label, node_label, rate_mau, sign, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Attachment {port_label} \N{RIGHTWARDS ARROW} "
                            f"{node_label}")
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.rate_spin = QDoubleSpinBox()
        self.rate_spin.setRange(0.0, 1e6)
        self.rate_spin.setDecimals(2)
        self.rate_spin.setSingleStep(1.0)
        self.rate_spin.setValue(rate_mau)
        self.rate_spin.setToolTip(
            "Per-attachment external coupling rate [milliarb. units]; the "
            "coupling amplitude is kappa = sign * sqrt(rate).")
        form.addRow("B_ext [mau]:", self.rate_spin)

        self.sign_combo = QComboBox()
        self.sign_combo.addItem("+ (0\N{DEGREE SIGN})", 1)
        self.sign_combo.addItem("\N{MINUS SIGN} (180\N{DEGREE SIGN})", -1)
        self.sign_combo.setCurrentIndex(0 if sign >= 0 else 1)
        form.addRow("Sign:", self.sign_combo)

        # Phase widget: present in the schema, locked in Phase 1
        self.phase_spin = QDoubleSpinBox()
        self.phase_spin.setRange(0.0, 360.0)
        self.phase_spin.setValue(0.0 if sign >= 0 else 180.0)
        self.phase_spin.setEnabled(False)
        self.phase_spin.setToolTip(PHASE2_PHASE_TOOLTIP)
        form.addRow("Phase [\N{DEGREE SIGN}]:", self.phase_spin)

        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_result(self):
        return {'rate_mau': self.rate_spin.value(),
                'sign': self.sign_combo.currentData()}


class ExplicitPortsMixin:
    """Graphulator mixin: explicit port / loss-hub / line-resonator support.

    Host requirements: self.nodes, self.edges, self.canvas, self.node_radius,
    self.placement_mode, self._save_state(), self._update_plot(),
    self._snap_to_grid(), self._invalidate_scattering_data(),
    self.scattering_assignments, self.APP_CONFIG.
    """

    # ---- state ----

    def _init_explicit_ports_state(self):
        self.ports = []
        self.line_resonators = []
        self.port_id_counter = 0
        self.line_id_counter = 0
        self.selected_ports = []
        self.selected_lines = []
        self._attach_pending_port = None   # port awaiting a node click (edge mode)
        self._place_loss_hub_next = False  # next port placement is a loss hub
        self._explicit_ports_notice = None  # keeps the non-modal notice alive
        # glyph drag state (move ports/lines with the mouse in normal mode)
        self._glyph_drag_pending = None    # ('port'|'line', obj) armed on click
        self._glyph_drag_start = None      # (x, y) where the click landed
        self._glyph_dragging = None        # set once motion passes the threshold
        self._glyph_drag_preview = None    # dashed outline artist during drag

    @property
    def explicit_ports_enabled(self):
        return bool(getattr(self.APP_CONFIG, 'EXPLICIT_PORTS_MODE', False))

    def _has_explicit_port_objects(self):
        return bool(self.ports or self.line_resonators)

    # ---- programmatic scene API (used by placement modes and tests) ----

    def add_port(self, label=None, pos=(0.0, 0.0), monitored=True, angle=0.0):
        """Create a port (monitored) or loss hub (unmonitored) glyph."""
        if label is None:
            prefix = 'P' if monitored else 'LH'
            label = f"{prefix}{self.port_id_counter + 1}"
        port = {
            'port_id': self.port_id_counter,
            'label': label,
            'pos': (float(pos[0]), float(pos[1])),
            'angle': float(angle),
            'monitored': bool(monitored),
            'attachments': [],
        }
        self.ports.append(port)
        self.port_id_counter += 1
        self._invalidate_scattering_data()
        return port

    def add_line_resonator(self, label=None, pos=(0.0, 0.0), FSR=1.0,
                           Ztx=65.0, f_max=10.0, port_end='xL',
                           Z0_port=50.0, alpha_uniform=0.0, angle=0.0):
        """Create a transmission-line macro glyph."""
        if label is None:
            label = f"TL{self.line_id_counter + 1}"
        line = {
            'line_id': self.line_id_counter,
            'label': label,
            'pos': (float(pos[0]), float(pos[1])),
            'angle': float(angle),
            'FSR': float(FSR),
            'Ztx': float(Ztx),
            'f_max': float(f_max),
            'port_end': port_end,
            'Z0_port': float(Z0_port),
            'alpha_uniform': float(alpha_uniform),
        }
        # Validate parameters early through the numerics-side schema
        LineResonator(**line_payload(line))
        self.line_resonators.append(line)
        self.line_id_counter += 1
        self._invalidate_scattering_data()
        return line

    def add_port_attachment(self, port, node, rate=None, sign=1):
        """Attach a port/loss hub to a node.

        rate is in arb. units (kappa = sqrt(rate)); defaults to the legacy
        B_ext default. A second call for the same (port, node) updates the
        existing attachment.
        """
        node_id = node['node_id'] if isinstance(node, dict) else node
        if rate is None:
            rate = self.APP_CONFIG.DEFAULT_NODE_B_EXT / 1000.0
        for att in port['attachments']:
            if att['node_id'] == node_id:
                att['rate'] = float(rate)
                att['sign'] = 1 if sign >= 0 else -1
                self._invalidate_scattering_data()
                return att
        att = {'node_id': node_id, 'rate': float(rate),
               'sign': 1 if sign >= 0 else -1}
        port['attachments'].append(att)
        self._invalidate_scattering_data()
        return att

    def remove_port_attachment(self, port, node_id):
        port['attachments'] = [a for a in port['attachments']
                               if a['node_id'] != node_id]
        self._invalidate_scattering_data()

    def remove_port(self, port):
        if port in self.ports:
            self.ports.remove(port)
        if port in self.selected_ports:
            self.selected_ports.remove(port)
        self._invalidate_scattering_data()

    def remove_line_resonator(self, line):
        if line in self.line_resonators:
            self.line_resonators.remove(line)
        if line in self.selected_lines:
            self.selected_lines.remove(line)
        self._invalidate_scattering_data()

    def _drop_attachments_for_node(self, node_id):
        """Called when a node is deleted."""
        for port in self.ports:
            port['attachments'] = [a for a in port['attachments']
                                   if a['node_id'] != node_id]

    def explode_line_resonator(self, line):
        """One-way: materialize a line macro as real nodes + a port glyph.

        Creates one GUI node per comb mode (freq/B_int assigned) and, when
        the line has a port end, one port glyph attached to every mode with
        the signed comb weights. The macro glyph is removed.
        """
        resonator = LineResonator(**line_payload(line))
        macro_nodes, macro_hubs = resonator.expand()

        x0, y0 = line['pos']
        spacing = self.APP_CONFIG.DEFAULT_GRID_SPACING
        id_map = {}
        for i, mnode in enumerate(macro_nodes):
            node = {
                'node_id': self.node_id_counter,
                'label': mnode['label'],
                'pos': (x0 + (i - len(macro_nodes) / 2) * spacing,
                        y0 - 2 * spacing),
                'color': self.APP_CONFIG.MYCOLORS.get('GRAY', 'gray'),
                'color_key': 'GRAY',
                'node_size_mult': 0.8,
                'label_size_mult': 0.8,
                'conj': False,
            }
            self.nodes.append(node)
            id_map[mnode['node_id']] = node['node_id']
            self.scattering_assignments[node['node_id']] = {
                'freq': mnode['freq'],
                'B_int': mnode['B_int'],
            }
            self.node_id_counter += 1
            self.node_counter += 1

        new_port = None
        if macro_hubs:
            hub = macro_hubs[0]
            new_port = self.add_port(label=line['label'],
                                     pos=(x0, y0), monitored=True)
            for node_id, mag, phase in hub['attachments']:
                self.add_port_attachment(
                    new_port, id_map[node_id], rate=mag ** 2,
                    sign=1 if phase == 0.0 else -1)

        self.remove_line_resonator(line)
        self._invalidate_scattering_data()
        # adding nodes stales any committed Kron reduction, same as placement
        if hasattr(self, '_invalidate_kron_reduction'):
            self._invalidate_kron_reduction()
        logger.info("Exploded line '%s' into %d nodes%s", line['label'],
                    len(macro_nodes), " + port" if new_port else "")
        return new_port

    # ---- extractor payloads ----

    def _gui_hubs_payload(self, node_ids=None):
        """Hub dicts for extract_graph_data(hubs=...).

        Ports with no attachments are inert and omitted. When node_ids is
        given (component filtering), only hubs entirely inside the component
        are included (attachments always live in one component because
        shared ports merge components).
        """
        payload = []
        for port in self.ports:
            if not port['attachments']:
                continue
            if node_ids is not None and not all(
                    a['node_id'] in node_ids for a in port['attachments']):
                continue
            payload.append(port_hub_payload(port))
        return payload

    def _gui_lines_payload(self, line_ids=None):
        payload = []
        for line in self.line_resonators:
            if line_ids is not None and line['line_id'] not in line_ids:
                continue
            payload.append(line_payload(line))
        return payload

    def _port_adjacency_pairs(self):
        """Node-id pairs merged by shared ports (cross-damping couples them)."""
        pairs = []
        for port in self.ports:
            ids = [a['node_id'] for a in port['attachments']]
            pairs.extend((ids[0], other) for other in ids[1:])
        return pairs

    # ---- settings toggle ----

    def _apply_explicit_ports_mode(self):
        """Reconfigure the GUI surface after the settings toggle changes."""
        enabled = self.explicit_ports_enabled
        if hasattr(self, '_ports_menu'):
            self._ports_menu.menuAction().setVisible(enabled)
        if hasattr(self, 'properties_panel'):
            panel = self.properties_panel
            if hasattr(panel, 'ports_frame'):
                panel.ports_frame.setVisible(enabled and self.scattering_mode)
            if self.scattering_mode:
                panel._update_scattering_node_table()
                panel._update_scattering_ports_table()
        if not enabled and self._has_explicit_port_objects():
            self._status_message(
                "Explicit Ports disabled, but this graph contains ports/"
                "lines — they remain in the model.", 8000)
        self._update_plot()

    def _auto_enable_explicit_ports(self, why):
        """Turn the mode on (session-scoped) and notify non-modally."""
        if self.explicit_ports_enabled:
            return
        setattr(self.APP_CONFIG, 'EXPLICIT_PORTS_MODE', True)
        self._apply_explicit_ports_mode()
        msg = (f"{why} contains explicit ports or transmission lines, so "
               "Explicit Ports mode has been switched ON for this session. "
               "You can toggle it in Settings \N{RIGHTWARDS ARROW} Interface.")
        self._status_message("Explicit Ports mode auto-enabled", 8000)
        try:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Information)
            box.setWindowTitle("Explicit Ports enabled")
            box.setText(msg)
            box.setModal(False)
            box.show()
            self._explicit_ports_notice = box
        except Exception:  # headless/exotic platforms: statusbar is enough
            logger.info(msg)

    # ---- placement modes ----

    def _require_explicit_mode(self):
        if not self.explicit_ports_enabled:
            self._status_message(
                "Enable 'Explicit Ports & Lines' in Settings "
                "\N{RIGHTWARDS ARROW} Interface to place ports and lines.",
                6000)
            return False
        return True

    def _toggle_port_mode(self):
        if not self._require_explicit_mode():
            return
        if self.placement_mode == 'port':
            self.placement_mode = None
            print("Port placement mode OFF")
        else:
            self._exit_placement_mode()
            self.placement_mode = 'port'
            print("Port placement mode ON - click to place a port (Esc to exit)")
        self._update_plot()

    def _toggle_port_continuous_mode(self):
        if not self._require_explicit_mode():
            return
        if self.placement_mode == 'port_continuous':
            self.placement_mode = None
            print("Continuous port placement OFF")
        else:
            self._exit_placement_mode()
            self.placement_mode = 'port_continuous'
            print("Continuous port placement ON (Esc to exit)")
        self._update_plot()

    def _toggle_line_mode(self):
        if not self._require_explicit_mode():
            return
        if self.placement_mode == 'line':
            self.placement_mode = None
            print("Line placement mode OFF")
        else:
            self._exit_placement_mode()
            self.placement_mode = 'line'
            print("Line placement mode ON - click to place a transmission line")
        self._update_plot()

    def _start_loss_hub_placement(self):
        if not self._require_explicit_mode():
            return
        self._exit_placement_mode()
        self._place_loss_hub_next = True
        self.placement_mode = 'port'
        print("Loss-hub placement - click to place (Esc to exit)")
        self._update_plot()

    def _on_click_port_placement(self, event):
        snap_x, snap_y = self._snap_to_grid(event.xdata, event.ydata)
        monitored = not self._place_loss_hub_next
        prefix = 'P' if monitored else 'LH'
        default_label = f"{prefix}{self.port_id_counter + 1}"
        dialog = PortInputDialog(default_label=default_label,
                                 monitored=monitored, parent=self)
        if dialog.exec() == QDialog.Accepted:
            result = dialog.get_result()
            self._save_state()
            port = self.add_port(label=result['label'], pos=(snap_x, snap_y),
                                 monitored=result['monitored'])
            kind = "Port" if port['monitored'] else "Loss hub"
            print(f"✓ {kind} '{port['label']}' placed at "
                  f"({snap_x:.3f}, {snap_y:.3f}). Use edge mode (E) to "
                  "attach it to nodes.")
            if self.placement_mode == 'port':
                self.placement_mode = None
        self._place_loss_hub_next = False
        self._update_plot()

    def _on_click_line_placement(self, event):
        snap_x, snap_y = self._snap_to_grid(event.xdata, event.ydata)
        dialog = LineInputDialog(
            default_label=f"TL{self.line_id_counter + 1}", parent=self)
        if dialog.exec() == QDialog.Accepted:
            result = dialog.get_result()
            self._save_state()
            try:
                line = self.add_line_resonator(pos=(snap_x, snap_y), **result)
            except ValueError as exc:
                # invalid parameter combination (e.g. f_max < FSR): nothing
                # was added — drop the no-op undo snapshot and tell the user
                if self.undo_stack:
                    self.undo_stack.pop()
                QMessageBox.warning(self, "Invalid line parameters", str(exc))
            else:
                n_modes = 2 * LineResonator(**line_payload(line)).N + 1
                print(f"✓ Line '{line['label']}' placed "
                      f"({n_modes} comb modes at extraction)")
        self.placement_mode = None
        self._update_plot()

    # ---- attachment creation through edge mode ----

    def _create_attachment_interactively(self, port, node):
        self._save_state()
        self.add_port_attachment(port, node)
        msg = (f"Attached '{port['label']}' \N{RIGHTWARDS ARROW} "
               f"'{node['label']}' — edit its rate in the Ports panel "
               "(or double-click the dashed link)")
        print(f"✓ {msg}")
        self._status_message(msg, 6000)
        if hasattr(self, 'properties_panel'):
            self.properties_panel._update_scattering_ports_table()
        self._update_plot()

    def _maybe_handle_attachment_click(self, event):
        """Called first from the edge-mode click handler.

        Both click orders work in a single gesture: port then node, or node
        then port. Returns True when the click was consumed.
        """
        if not (self.explicit_ports_enabled or self.ports):
            return False

        port = self._find_port_at_position(event.xdata, event.ydata)
        if port is not None:
            if self.edge_mode_first_node is not None:
                # node-first order: complete the attachment right here
                node = self.edge_mode_first_node
                self.edge_mode_first_node = None
                self._create_attachment_interactively(port, node)
                return True
            if self._attach_pending_port is port:
                self._attach_pending_port = None
                self._status_message(
                    f"Attachment cancelled for '{port['label']}'", 4000)
            else:
                self._attach_pending_port = port
                self._status_message(
                    f"Port '{port['label']}' selected — now click the mode "
                    "to attach it to.", 6000)
                print(f"Port '{port['label']}' selected. Click a node to "
                      "attach it.")
            self._update_plot()
            return True

        line = self._find_line_at_position(event.xdata, event.ydata)
        if line is not None:
            # Phase-1: the line's comb modes are internal to the macro
            self._attach_pending_port = None
            self._status_message(
                f"'{line['label']}' is a macro: its comb modes take edges "
                "only after Insert \N{RIGHTWARDS ARROW} Explode Line to "
                "Nodes (its port is set by 'port end').", 8000)
            return True

        if self._attach_pending_port is not None:
            node = self._find_node_at_position(event.xdata, event.ydata)
            if node is not None:
                port = self._attach_pending_port
                self._attach_pending_port = None
                self._create_attachment_interactively(port, node)
                return True
        return False

    # ---- normal-mode interaction (select / edit / delete) ----

    def _maybe_handle_ports_normal_click(self, event, shift_pressed,
                                         is_double):
        """Called from the normal-mode click handler before node handling.

        Returns True when the click landed on a port/line/attachment link.
        """
        if not (self.ports or self.line_resonators):
            return False

        port = self._find_port_at_position(event.xdata, event.ydata)
        if port is not None:
            if is_double:
                self._edit_port(port)
            elif shift_pressed:
                if port in self.selected_ports:
                    self.selected_ports.remove(port)
                else:
                    self.selected_ports.append(port)
            else:
                self.selected_ports = [port]
                self.selected_lines = []
                self.selected_nodes.clear()
                self.selected_edges.clear()
                # arm drag-to-move (activates once motion passes threshold)
                self._glyph_drag_pending = ('port', port)
                self._glyph_drag_start = (event.xdata, event.ydata)
                self._status_message(
                    f"Selected {'port' if port['monitored'] else 'loss hub'} "
                    f"'{port['label']}' — drag to move, Ctrl+U/Ctrl+I to "
                    "rotate, double-click to edit, D to delete", 6000)
                print(f"Selected {'port' if port['monitored'] else 'loss hub'}"
                      f" '{port['label']}'")
            self._update_plot()
            return True

        line = self._find_line_at_position(event.xdata, event.ydata)
        if line is not None:
            if is_double:
                self._edit_line(line)
            elif shift_pressed:
                if line in self.selected_lines:
                    self.selected_lines.remove(line)
                else:
                    self.selected_lines.append(line)
            else:
                self.selected_lines = [line]
                self.selected_ports = []
                self.selected_nodes.clear()
                self.selected_edges.clear()
                self._glyph_drag_pending = ('line', line)
                self._glyph_drag_start = (event.xdata, event.ydata)
                self._status_message(
                    f"Selected line '{line['label']}' — drag to move, "
                    "Ctrl+U/Ctrl+I to rotate, double-click to edit, D to "
                    "delete", 6000)
                print(f"Selected line '{line['label']}'")
            self._update_plot()
            return True

        if is_double:
            hit = self._find_attachment_at_position(event.xdata, event.ydata)
            if hit is not None:
                self._edit_attachment(*hit)
                return True

        if not shift_pressed and (self.selected_ports or self.selected_lines):
            # clicking empty space clears port/line selection alongside nodes
            self.selected_ports = []
            self.selected_lines = []
        return False

    def _edit_port(self, port):
        dialog = PortInputDialog(default_label=port['label'],
                                 monitored=port['monitored'], parent=self,
                                 editing=True)
        if dialog.exec() == QDialog.Accepted:
            result = dialog.get_result()
            self._save_state()
            port['label'] = result['label']
            port['monitored'] = result['monitored']
            self._invalidate_scattering_data()
            if hasattr(self, 'properties_panel'):
                self.properties_panel._update_scattering_ports_table()
            self._update_plot()

    def _edit_line(self, line):
        dialog = LineInputDialog(line=line, parent=self)
        if dialog.exec() == QDialog.Accepted:
            result = dialog.get_result()
            # validate the candidate BEFORE mutating the stored line, so an
            # invalid edit cannot poison the glyph (which every redraw uses)
            candidate = dict(line)
            candidate.update(result)
            try:
                LineResonator(**line_payload(candidate))
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid line parameters", str(exc))
                return
            self._save_state()
            line.update(result)
            self._invalidate_scattering_data()
            if hasattr(self, 'properties_panel'):
                self.properties_panel._update_scattering_ports_table()
            self._update_plot()

    def _edit_attachment(self, port, att):
        node = next((n for n in self.nodes
                     if n['node_id'] == att['node_id']), None)
        node_label = node['label'] if node else str(att['node_id'])
        dialog = AttachmentEditDialog(port['label'], node_label,
                                      rate_mau=att['rate'] * 1000.0,
                                      sign=att['sign'], parent=self)
        if dialog.exec() == QDialog.Accepted:
            result = dialog.get_result()
            self._save_state()
            att['rate'] = result['rate_mau'] / 1000.0
            att['sign'] = result['sign']
            self._invalidate_scattering_data()
            if hasattr(self, 'properties_panel'):
                self.properties_panel._update_scattering_ports_table()
            self._update_plot()

    def _explode_selected_line(self):
        """Menu action: explode the selected line macro (one-way)."""
        if len(self.selected_lines) != 1:
            self._status_message("Select exactly one transmission line to "
                                 "explode.", 5000)
            return
        line = self.selected_lines[0]
        self._save_state()
        self.explode_line_resonator(line)
        if hasattr(self, 'properties_panel'):
            self.properties_panel._update_scattering_ports_table()
            if self.scattering_mode:
                self.properties_panel._update_scattering_node_table()
        self._update_plot()

    # ---- drag-to-move & rotation ----

    def _maybe_handle_glyph_motion(self, event):
        """Called from the host _on_motion. Returns True while a port/line
        glyph drag is pending or active (draws a dashed outline preview)."""
        if self._glyph_drag_pending is None and self._glyph_dragging is None:
            return False
        if event.xdata is None or event.ydata is None:
            return self._glyph_dragging is not None

        # activate once the left button is held and motion passes threshold
        if self._glyph_dragging is None:
            if event.button != 1:
                return False
            dx = event.xdata - self._glyph_drag_start[0]
            dy = event.ydata - self._glyph_drag_start[1]
            if np.hypot(dx, dy) <= self.drag_threshold:
                return True  # consumed, but not yet a drag
            self._glyph_dragging = self._glyph_drag_pending
            self._glyph_drag_pending = None
            kind, obj = self._glyph_dragging
            print(f"Dragging {kind} '{obj['label']}'...")

        kind, obj = self._glyph_dragging
        snap_x, snap_y = self._snap_to_grid(event.xdata, event.ydata)

        # dashed outline preview at the snapped position (cheap artists —
        # the full scene redraw happens once, on release)
        if self._glyph_drag_preview is not None:
            try:
                self._glyph_drag_preview.remove()
            except Exception:
                pass
        r = self.node_radius
        if kind == 'port':
            half_w = (PORT_BODY_W / 2 + PORT_APEX_W + PORT_LEAD_LEN) * r
            half_h = PORT_BODY_H / 2 * r
        else:
            half_w = (LINE_BODY_W + LINE_LEAD_LEN) * r
            half_h = LINE_BODY_H * r
        extent = max(half_w, half_h)
        self._glyph_drag_preview = mpatches.Rectangle(
            (snap_x - extent, snap_y - extent), 2 * extent, 2 * extent,
            fill=False, edgecolor='darkorange', linestyle=':',
            linewidth=1.5, zorder=20)
        self.canvas.ax.add_patch(self._glyph_drag_preview)
        self.canvas.draw_idle()
        return True

    def _maybe_handle_glyph_release(self, event):
        """Called from the host _on_release (left button). Returns True when
        it consumed the release (commits a move, or clears a pending drag)."""
        if self._glyph_dragging is not None:
            kind, obj = self._glyph_dragging
            self._glyph_dragging = None
            if self._glyph_drag_preview is not None:
                try:
                    self._glyph_drag_preview.remove()
                except Exception:
                    pass
                self._glyph_drag_preview = None
            if event.xdata is not None and event.ydata is not None:
                snap_x, snap_y = self._snap_to_grid(event.xdata, event.ydata)
                if (snap_x, snap_y) != tuple(obj['pos']):
                    self._save_state()
                    obj['pos'] = (snap_x, snap_y)
                    print(f"Moved {kind} '{obj['label']}' to "
                          f"({snap_x:.3f}, {snap_y:.3f})")
            self._update_plot()
            return True
        if self._glyph_drag_pending is not None:
            self._glyph_drag_pending = None
            self._glyph_drag_start = None
            return True
        return False

    def _rotate_selected_nodes(self, angle_degrees):
        """Rotate selection. With only port/line glyphs selected, rotate the
        glyphs' own orientation in place; otherwise defer to the node
        behavior (rotation of node positions about the selection centroid)."""
        if (self.selected_ports or self.selected_lines) \
                and not self.selected_nodes:
            self._save_state()
            for obj in self.selected_ports + self.selected_lines:
                obj['angle'] = (obj.get('angle', 0.0) - angle_degrees) % 360.0
            names = ', '.join(o['label'] for o in
                              self.selected_ports + self.selected_lines)
            print(f"Rotated {names} by {-angle_degrees:+g}\N{DEGREE SIGN}")
            self._update_plot()
            return
        super()._rotate_selected_nodes(angle_degrees)

    def _delete_selected_ports_lines(self):
        """Remove selected port/line glyphs. Returns how many were removed."""
        count = 0
        for port in list(self.selected_ports):
            self.remove_port(port)
            count += 1
        for line in list(self.selected_lines):
            self.remove_line_resonator(line)
            count += 1
        return count

    # ---- hit testing ----

    def _port_geometry(self, port):
        """(x, y, w, h, apex_x, lead_tip_x) in UNROTATED data units.

        The glyph may carry an 'angle' (degrees, CCW about pos); consumers
        rotate with _rotate_point / unrotate click points before testing.
        """
        r = self.node_radius
        x, y = port['pos']
        w = PORT_BODY_W * r
        h = PORT_BODY_H * r
        apex_x = x + w / 2 + PORT_APEX_W * r
        lead_tip_x = apex_x + PORT_LEAD_LEN * r
        return x, y, w, h, apex_x, lead_tip_x

    def _port_lead_tip(self, port):
        """Rotated position of the lead tip (attachment links start here)."""
        x, y, _, _, _, lead_tip_x = self._port_geometry(port)
        return _rotate_point(lead_tip_x, y, x, y, port.get('angle', 0.0))

    def _find_port_at_position(self, x, y):
        if x is None or y is None:
            return None
        for port in reversed(self.ports):
            px, py, w, h, apex_x, _ = self._port_geometry(port)
            # undo the glyph rotation, then test the axis-aligned shape
            ux, uy = _rotate_point(x, y, px, py, -port.get('angle', 0.0))
            if (px - w / 2 <= ux <= apex_x) and (py - h / 2 <= uy <= py + h / 2):
                return port
        return None

    def _find_line_at_position(self, x, y):
        if x is None or y is None:
            return None
        r = self.node_radius
        for line in reversed(self.line_resonators):
            lx, ly = line['pos']
            ux, uy = _rotate_point(x, y, lx, ly, -line.get('angle', 0.0))
            w = LINE_BODY_W * r + LINE_LEAD_LEN * r
            h = LINE_BODY_H * r
            if (lx - w <= ux <= lx + w) and (ly - h <= uy <= ly + h):
                return line
        return None

    def _find_attachment_at_position(self, x, y, tol=None):
        """Return (port, attachment) whose dashed link passes near (x, y)."""
        if x is None or y is None:
            return None
        tol = tol if tol is not None else 0.35 * self.node_radius
        node_pos = {n['node_id']: n['pos'] for n in self.nodes}
        for port in self.ports:
            p0 = np.array(self._port_lead_tip(port))
            for att in port['attachments']:
                pos = node_pos.get(att['node_id'])
                if pos is None:
                    continue
                p1 = np.array(pos, dtype=float)
                seg = p1 - p0
                seg_len2 = float(seg @ seg)
                if seg_len2 == 0.0:
                    continue
                t = float(np.clip((np.array([x, y]) - p0) @ seg / seg_len2,
                                  0.0, 1.0))
                dist = float(np.hypot(*(np.array([x, y]) - (p0 + t * seg))))
                if dist <= tol:
                    return port, att
        return None

    # ---- drawing ----

    def _draw_ports_and_lines(self, ax=None):
        """Draw port/loss-hub/line glyphs and attachment links."""
        if not (self.ports or self.line_resonators):
            return
        ax = ax or self.canvas.ax
        r = self.node_radius
        node_pos = {n['node_id']: n['pos'] for n in self.nodes}

        for port in self.ports:
            x, y, w, h, apex_x, lead_tip_x = self._port_geometry(port)
            angle = port.get('angle', 0.0)
            selected = port in self.selected_ports
            pending = port is self._attach_pending_port
            edge_color = ('darkorange' if selected
                          else 'dodgerblue' if pending else 'black')

            def rot(px, py):
                return _rotate_point(px, py, x, y, angle)

            # home-plate pentagon pointing right (rotated about pos)
            verts = [
                rot(x - w / 2, y - h / 2),
                rot(x + w / 2, y - h / 2),
                rot(apex_x, y),
                rot(x + w / 2, y + h / 2),
                rot(x - w / 2, y + h / 2),
            ]
            body = mpatches.Polygon(
                verts, closed=True,
                facecolor='white' if port['monitored'] else '#e8e8e8',
                edgecolor=edge_color, linewidth=2.5, zorder=11,
                linestyle='--' if pending else '-',
                hatch=None if port['monitored'] else '///')
            ax.add_patch(body)

            # short thick lead at the apex
            (ax0, ay0), (ax1, ay1) = rot(apex_x, y), rot(lead_tip_x, y)
            ax.add_line(mlines.Line2D(
                [ax0, ax1], [ay0, ay1], color=edge_color,
                linewidth=4.0, solid_capstyle='butt', zorder=11))

            # attachment links: thin dashed, visually distinct from edges
            tip_x, tip_y = ax1, ay1
            for att in port['attachments']:
                pos = node_pos.get(att['node_id'])
                if pos is None:
                    continue
                link_color = 'gray' if att['sign'] >= 0 else 'firebrick'
                ax.add_line(mlines.Line2D(
                    [tip_x, pos[0]], [tip_y, pos[1]], color=link_color,
                    linewidth=1.2, linestyle=(0, (4, 3)), zorder=4,
                    alpha=0.9))
                if att['sign'] < 0:
                    # mark inverted-sign links near the midpoint
                    mx, my = (tip_x + pos[0]) / 2, (tip_y + pos[1]) / 2
                    ax.text(mx, my, '\N{MINUS SIGN}', color='firebrick',
                            fontsize=9, ha='center', va='center', zorder=5)

            lx0, ly0 = rot(x - w / 2 - 0.2 * r, y)
            ax.text(lx0, ly0, port['label'],
                    ha='right', va='center', fontsize=10,
                    fontweight='bold', color=edge_color, zorder=12)

        for line in self.line_resonators:
            lx, ly = line['pos']
            w = LINE_BODY_W * r
            h = LINE_BODY_H * r
            angle = line.get('angle', 0.0)
            selected = line in self.selected_lines
            edge_color = 'darkorange' if selected else 'black'

            # glyph rotation: draw axis-aligned, then rotate every artist
            # about the glyph center
            glyph_tf = (mtransforms.Affine2D().rotate_deg_around(lx, ly, angle)
                        + ax.transData)

            # cylinder: body rectangle + right elliptical end-cap + left arc
            body = mpatches.Rectangle(
                (lx - w, ly - h), 2 * w, 2 * h, facecolor='#dddddd',
                edgecolor='none', zorder=10, transform=glyph_tf)
            ax.add_patch(body)
            cap = mpatches.Ellipse(
                (lx + w, ly), 0.6 * h * 2, 2 * h, facecolor='#cccccc',
                edgecolor=edge_color, linewidth=1.5, zorder=11,
                transform=glyph_tf)
            ax.add_patch(cap)
            left_arc = mpatches.Arc(
                (lx - w, ly), 0.6 * h * 2, 2 * h, theta1=90, theta2=270,
                edgecolor=edge_color, linewidth=1.5, zorder=11,
                transform=glyph_tf)
            ax.add_patch(left_arc)
            for seg in ((lx - w, ly - h, lx + w, ly - h),
                        (lx - w, ly + h, lx + w, ly + h)):
                ax.add_line(mlines.Line2D([seg[0], seg[2]], [seg[1], seg[3]],
                                          color=edge_color, linewidth=1.5,
                                          zorder=11, transform=glyph_tf))
            # thin leads centered on both ends
            for x0, x1 in ((lx - w - LINE_LEAD_LEN * r, lx - w),
                           (lx + w + 0.6 * h, lx + w + 0.6 * h
                            + LINE_LEAD_LEN * r)):
                ax.add_line(mlines.Line2D([x0, x1], [ly, ly],
                                          color=edge_color, linewidth=1.5,
                                          zorder=11, transform=glyph_tf))

            n_pairs = LineResonator(**line_payload(line)).N
            sub = f"FSR={line['FSR']:g}, N={n_pairs}"
            if line.get('port_end'):
                sub += f", port@{line['port_end']}"
            tx, ty = _rotate_point(lx, ly + h + 0.35 * r, lx, ly, angle)
            ax.text(tx, ty, line['label'], ha='center',
                    va='bottom', fontsize=10, fontweight='bold',
                    color=edge_color, zorder=12)
            sx, sy = _rotate_point(lx, ly - h - 0.35 * r, lx, ly, angle)
            ax.text(sx, sy, sub, ha='center', va='top',
                    fontsize=7, color='dimgray', zorder=12)

    # ---- serialization fragments ----

    def _serialize_ports_and_lines(self, data):
        """Add ports/lines to the .pgraph dict; bump version when present."""
        if self.ports:
            data['ports'] = [
                {
                    'port_id': p['port_id'],
                    'label': p['label'],
                    'pos': list(p['pos']),
                    'angle': p.get('angle', 0.0),
                    'monitored': p['monitored'],
                    'attachments': [
                        {'node_id': a['node_id'], 'rate': a['rate'],
                         'sign': a['sign']}
                        for a in p['attachments']
                    ],
                }
                for p in self.ports
            ]
        if self.line_resonators:
            data['line_resonators'] = [
                {
                    'line_id': l['line_id'],
                    'label': l['label'],
                    'pos': list(l['pos']),
                    'angle': l.get('angle', 0.0),
                    'FSR': l['FSR'],
                    'Ztx': l['Ztx'],
                    'f_max': l['f_max'],
                    'port_end': l.get('port_end'),
                    'Z0_port': l.get('Z0_port', 50.0),
                    'alpha_uniform': l.get('alpha_uniform', 0.0),
                }
                for l in self.line_resonators
            ]
        if self.ports or self.line_resonators:
            # 3.0 = 2.0 + ports/lines sections. Legacy-only graphs keep
            # writing 2.0 so older app versions read them unchanged.
            data['version'] = '3.0'
        return data

    def _deserialize_ports_and_lines(self, data, source_name="This file"):
        """Restore ports/lines from a .pgraph dict; auto-enable the mode."""
        self.ports = []
        self.line_resonators = []
        self.selected_ports = []
        self.selected_lines = []
        self._attach_pending_port = None

        known_node_ids = {n['node_id'] for n in self.nodes}
        max_port_id = -1
        for pdata in data.get('ports', []):
            attachments = []
            for a in pdata.get('attachments', []):
                if a['node_id'] not in known_node_ids:
                    logger.warning(
                        "Dropping attachment of port %r to unknown node %r",
                        pdata.get('label'), a['node_id'])
                    continue
                attachments.append({'node_id': a['node_id'],
                                    'rate': float(a.get('rate', 0.1)),
                                    'sign': 1 if a.get('sign', 1) >= 0 else -1})
            port = {
                'port_id': int(pdata['port_id']),
                'label': pdata.get('label', f"P{pdata['port_id']}"),
                'pos': tuple(pdata.get('pos', (0.0, 0.0))),
                'angle': float(pdata.get('angle', 0.0)),
                'monitored': bool(pdata.get('monitored', True)),
                'attachments': attachments,
            }
            self.ports.append(port)
            max_port_id = max(max_port_id, port['port_id'])
        self.port_id_counter = max_port_id + 1

        max_line_id = -1
        for ldata in data.get('line_resonators', []):
            line = {
                'line_id': int(ldata['line_id']),
                'label': ldata.get('label', f"TL{ldata['line_id']}"),
                'pos': tuple(ldata.get('pos', (0.0, 0.0))),
                'angle': float(ldata.get('angle', 0.0)),
                'FSR': float(ldata['FSR']),
                'Ztx': float(ldata['Ztx']),
                'f_max': float(ldata['f_max']),
                'port_end': ldata.get('port_end'),
                'Z0_port': float(ldata.get('Z0_port', 50.0)),
                'alpha_uniform': float(ldata.get('alpha_uniform', 0.0)),
            }
            self.line_resonators.append(line)
            max_line_id = max(max_line_id, line['line_id'])
        self.line_id_counter = max_line_id + 1

        if self._has_explicit_port_objects():
            self._auto_enable_explicit_ports(source_name)
