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
        'Z0_port': float, 'alpha_uniform': float,
        'ends': {                     # explicit terminations, never implied
            'x0': None | {'kind': 'port', 'port_id': int},
            'xL': None | {'kind': 'port', 'port_id': int},
        },
        'port_end': ...,              # legacy; migrated to 'ends' on load
    }

A transmission line's comb NEVER leaves the macro. Terminating an end on a
port glyph merges the whole comb (kappa_n = u_n(end)*sqrt(gamma)) into that
port's single hub column at extraction time, so one drawn connection stands
for all 2N+1 couplings. The port is a real, visible, editable glyph — a line
is never implicitly terminated — and the same port may also attach to
ordinary nodes, because one physical resistor can see both a line and a
device. "Explode to Nodes" still exists as a manual escape hatch, but it is
NOT how you connect a line.

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
                               QComboBox, QMessageBox, QDoubleSpinBox,
                               QSpinBox, QHBoxLayout)

from ..autograph import LineResonator

logger = logging.getLogger(__name__)

# Phase-2 tooltip shown on every locked phase widget
PHASE2_PHASE_TOOLTIP = (
    "Phase-1 hub weights are real signed (0\N{DEGREE SIGN} or "
    "180\N{DEGREE SIGN} only). Complex weights are Phase 2, blocked on the "
    "M_pumped two-sector derivation."
)

# Glyph geometry (data units, scaled by the node radius at draw time).
# Default proportions follow the diagrammer reference art (port_coax):
# a boxy home-plate port with a long terminal lead, and a slender coax
# cylinder (~10:1) with a closed left cap and an open right mouth.
PORT_BODY_W = 1.5     # pentagon straight-body width (x node_radius)
PORT_BODY_H = 1.35    # pentagon height
PORT_APEX_W = 0.55    # tapered nose beyond the body
PORT_LEAD_LEN = 1.2   # terminal lead at the apex
LINE_BODY_W = 2.7     # cylinder half-length
LINE_BODY_H = 0.28    # cylinder half-height
LINE_LEAD_LEN = 0.55  # terminal stubs at both ends
PORT_LINEWIDTH = 2.0  # default stroke (uniform across body + lead)
LINE_LINEWIDTH = 1.6
GLYPH_SIZE_MIN, GLYPH_SIZE_MAX = 0.3, 4.0
PORT_LABEL_FILL = 0.90      # fraction of the body width a label may occupy
PORT_LABEL_ADVANCE = 0.60   # mean glyph advance / font size (bold sans)

# Wire (connection) appearance. Wires are SOLID: a wire reaching a port
# glyph already says "dissipative", so a dashed variant carried no extra
# information. Per-wire overrides ('color', 'linewidth_mult', 'label',
# 'label_size_mult') mirror the controls ordinary graph edges have.
WIRE_COLOR = 'dimgray'
WIRE_COLOR_INVERTED = 'firebrick'   # default for a sign = -1 attachment
WIRE_COLOR_TAP = 'teal'             # conservative node tap
WIRE_LINEWIDTH = 1.4                # data-unit base, scaled by linewidth_mult
PUMP_BUS_COLOR = 'black'            # the double-line pump bus (crosses sectors)


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
        # port_end is deprecated: termination comes from line['ends'], which
        # the GUI merges into the connected port's hub column. Emitting None
        # keeps LineResonator from generating an implicit hub of its own.
        'port_end': None,
        'Z0_port': float(line.get('Z0_port', 50.0)),
        'alpha_uniform': float(line.get('alpha_uniform', 0.0)),
        'conj': bool(line.get('conj', False)),
    }


# Physics fields a pumped line's conjugate twin mirrors from its primary.
# The twin is the SAME physical line seen in the idler sector, so it owns
# only its layout (pos, angle, style) and its own end connections.
TWIN_MIRRORED_KEYS = ('FSR', 'Ztx', 'f_max', 'Z0_port', 'alpha_uniform')
PUMP_COUPLINGS = ('inductive', 'capacitive')


def _color_button(initial, parent=None):
    """Small swatch button opening a QColorDialog; .color() reads it."""
    from PySide6.QtWidgets import QPushButton, QColorDialog
    from PySide6.QtGui import QColor
    btn = QPushButton(parent)
    btn.setFixedSize(46, 22)

    def _apply(name):
        btn._color = name
        btn.setStyleSheet(
            f"background-color: {name}; border: 1px solid #888;")

    def _pick():
        col = QColorDialog.getColor(QColor(btn._color), btn.window())
        if col.isValid():
            _apply(col.name())

    btn.clicked.connect(_pick)
    btn.color = lambda: btn._color
    _apply(initial)
    return btn


def _mult_spin(value, tooltip=''):
    box = QDoubleSpinBox()
    box.setRange(GLYPH_SIZE_MIN, GLYPH_SIZE_MAX)
    box.setDecimals(2)
    box.setSingleStep(0.1)
    box.setValue(value)
    if tooltip:
        box.setToolTip(tooltip)
    return box


def _add_appearance_rows(form, obj, default_lw, default_fill):
    """Length/height/stroke/color rows shared by the port & line dialogs.
    Returns the widget dict; read back with _appearance_result."""
    widgets = {}
    widgets['w_mult'] = _mult_spin(obj.get('w_mult', 1.0),
                                   "Stretch the glyph length "
                                   "(× default; "
                                   "arrow keys ←/"
                                   "→ when selected)")
    form.addRow("Length ×:", widgets['w_mult'])
    widgets['h_mult'] = _mult_spin(obj.get('h_mult', 1.0),
                                   "Stretch the glyph height "
                                   "(× default; "
                                   "arrow keys ↑/"
                                   "↓ when selected)")
    form.addRow("Height ×:", widgets['h_mult'])
    lw = QDoubleSpinBox()
    lw.setRange(0.25, 8.0)
    lw.setDecimals(2)
    lw.setSingleStep(0.25)
    lw.setValue(float(obj.get('linewidth', default_lw)))
    widgets['linewidth'] = lw
    form.addRow("Stroke width:", lw)
    widgets['color'] = _color_button(obj.get('color', 'black'))
    form.addRow("Stroke color:", widgets['color'])
    widgets['fill'] = _color_button(obj.get('fill', default_fill))
    form.addRow("Fill color:", widgets['fill'])
    return widgets


def _appearance_result(widgets):
    return {'w_mult': widgets['w_mult'].value(),
            'h_mult': widgets['h_mult'].value(),
            'linewidth': widgets['linewidth'].value(),
            'color': widgets['color'].color(),
            'fill': widgets['fill'].color()}


class PortInputDialog(QDialog):
    """Label, monitored/loss choice, orientation and appearance of a
    (new or edited) port glyph."""

    def __init__(self, default_label='P1', monitored=True, parent=None,
                 editing=False, port=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Port" if editing else "Place Port")
        port = port or {}
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
        self.auto_orient_check = QCheckBox(
            "Auto-orient toward attached group")
        self.auto_orient_check.setChecked(not port.get('angle_pinned', False))
        self.auto_orient_check.setToolTip(
            "Checked: the lead points at the center of the attached "
            "nodes/line ends.\nUnchecked: the rotation is fixed — set it "
            "with Ctrl+U / Ctrl+I (which also fixes it).")
        form.addRow(self.auto_orient_check)
        self.appearance = _add_appearance_rows(form, port, PORT_LINEWIDTH,
                                               'white')
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.label_edit.setFocus()
        self.label_edit.selectAll()

    def get_result(self):
        result = {'label': self.label_edit.text().strip() or 'P',
                  'monitored': self.monitored_check.isChecked(),
                  'auto_orient': self.auto_orient_check.isChecked()}
        result.update(_appearance_result(self.appearance))
        return result


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
            "Which end gets a port glyph created and wired to it when the "
            "line is placed. The port is a real, visible glyph afterwards: "
            "rewire it by clicking a line-end lead then a port with the "
            "edge tool (E). One terminated end per line in Phase 1.")
        if editing:
            # editing must not silently rewire: show the live topology
            terminated = [f"{e} ({len(ExplicitPortsMixin._end_conns(line, e))})"
                          for e in ('x0', 'xL')
                          if ExplicitPortsMixin._end_conns(line, e)]
            status = QLabel(", ".join(terminated) if terminated
                            else "both ends open")
            status.setToolTip("Rewire with the edge tool (E): click a line "
                              "end lead, then a port glyph or a mode.")
            form.addRow("Connected ends:", status)
            self.port_end_combo = None
        else:
            form.addRow("Terminate end with port:", self.port_end_combo)

        # How a NODE tap at each end couples to the line — a property of the
        # physical tap point, shared by everything attached there
        self.end_coupling_combos = {}
        end_coupling = line.get('end_coupling') or {}
        for end in ('x0', 'xL'):
            combo = QComboBox()
            combo.addItem("capacitive  (g_n \u221d \u221an)", 'capacitive')
            combo.addItem("inductive  (g_n \u221d 1/\u221an)", 'inductive')
            current = end_coupling.get(end, 'capacitive')
            combo.setCurrentIndex(0 if current == 'capacitive' else 1)
            combo.setToolTip(
                "Coupling type of a mode tapped at this end. Sets the "
                "verified per-mode profile relative to the reference "
                "harmonic: capacitive g_n \u221d \u221a(\u03c9_n), "
                "inductive g_n \u221d 1/\u221a(\u03c9_n).")
            self.end_coupling_combos[end] = combo
            form.addRow(f"Tap coupling @ {end}:", combo)

        self.z0_spin = spin(line.get('Z0_port', 50.0), 1e-6, 1e6, 2, 1.0,
                            "Port termination impedance")
        form.addRow("Z0 [\N{GREEK CAPITAL LETTER OMEGA}]:", self.z0_spin)

        self.alpha_spin = spin(line.get('alpha_uniform', 0.0), 0.0, 100.0, 6,
                               0.001, ALPHA_TOOLTIP)
        alpha_label = QLabel("\N{GREEK SMALL LETTER ALPHA} [Np]:")
        alpha_label.setToolTip(ALPHA_TOOLTIP)
        form.addRow(alpha_label, self.alpha_spin)

        self.appearance = _add_appearance_rows(form, line, LINE_LINEWIDTH,
                                               '#cccccc')

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
            'port_end': (self.port_end_combo.currentData()
                         if self.port_end_combo is not None else None),
            'end_coupling': {e: c.currentData()
                             for e, c in self.end_coupling_combos.items()},
            'Z0_port': self.z0_spin.value(),
            'alpha_uniform': self.alpha_spin.value(),
            **_appearance_result(self.appearance),
        }


class TapInputDialog(QDialog):
    """Node-tap parameters: reference harmonic (nearest highlighted),
    coupling rate at that harmonic, and sign."""

    def __init__(self, line_label, node_label, end, coupling, N, n_nearest,
                 rate_mau=100.0, sign=1, n_ref=None, parent=None,
                 editing=False):
        super().__init__(parent)
        self.setWindowTitle(
            ("Edit tap " if editing else "Tap ")
            + f"{node_label} \N{RIGHTWARDS ARROW} {line_label} ({end})")
        layout = QVBoxLayout(self)
        form = QFormLayout()

        note = QLabel(
            f"One connection couples '{node_label}' to ALL of "
            f"'{line_label}'s comb modes with the {coupling} profile\n"
            "g_n \u221d u_n(end)\u00b7(n/n_ref)^(\u00b1\u00bd). The rate "
            "below is the coupling AT the reference harmonic.")
        note.setWordWrap(True)
        layout.addWidget(note)

        self.n_ref_spin = QDoubleSpinBox()
        self.n_ref_spin.setDecimals(0)
        self.n_ref_spin.setRange(1, N)
        self.n_ref_spin.setValue(n_ref if n_ref is not None else n_nearest)
        self.n_ref_spin.setToolTip(
            f"Harmonic the coupling rate is referenced to (1..{N}).\n"
            f"Closest harmonic to the mode's frequency: n = {n_nearest}.")
        n_label = QLabel(f"Reference harmonic n_ref (nearest: "
                         f"<b>{n_nearest}</b>):")
        form.addRow(n_label, self.n_ref_spin)

        self.rate_spin = QDoubleSpinBox()
        self.rate_spin.setRange(0.0, 1e6)
        self.rate_spin.setDecimals(2)
        self.rate_spin.setSingleStep(1.0)
        self.rate_spin.setValue(rate_mau)
        self.rate_spin.setToolTip(
            "Coupling rate at the reference harmonic [milliarb. units]")
        form.addRow("rate @ n_ref [mau]:", self.rate_spin)

        self.sign_combo = QComboBox()
        self.sign_combo.addItem("+ (0\N{DEGREE SIGN})", 1)
        self.sign_combo.addItem("\N{MINUS SIGN} (180\N{DEGREE SIGN})", -1)
        self.sign_combo.setCurrentIndex(0 if sign >= 0 else 1)
        form.addRow("Sign:", self.sign_combo)

        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_result(self):
        return {'n_ref': int(self.n_ref_spin.value()),
                'rate': self.rate_spin.value() / 1000.0,
                'sign': self.sign_combo.currentData()}


class PumpInputDialog(QDialog):
    """Pumped termination of a line: which end, pump frequency, coupling
    rate at the reference pair, pump phase, and the element type."""

    def __init__(self, line_label, N, FSR, end='x0', f_p=None, rate_mau=50.0,
                 phase=0.0, n_ref=None, coupling='inductive', parent=None,
                 editing=False):
        super().__init__(parent)
        self.setWindowTitle(("Edit" if editing else "Add")
                            + f" pumped termination of {line_label}")
        self.N, self.FSR = int(N), float(FSR)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.end_combo = QComboBox()
        self.end_combo.addItem("x = 0 (all-plus signs)", 'x0')
        self.end_combo.addItem("x = L (alternating signs)", 'xL')
        self.end_combo.setCurrentIndex(0 if end == 'x0' else 1)
        self.end_combo.setToolTip(
            "The end carrying the modulated element. Its mode profile "
            "u_n(end) sets the sign pattern of the rank-one pump block.")
        form.addRow("Pumped end:", self.end_combo)

        self.fp_spin = QDoubleSpinBox()
        self.fp_spin.setRange(1e-9, 1e9)
        self.fp_spin.setDecimals(4)
        self.fp_spin.setSingleStep(0.1)
        self.fp_spin.setValue(float(f_p) if f_p is not None
                              else 2.0 * self.FSR * max(1, self.N // 2))
        self.fp_spin.setToolTip(
            "Pump frequency [a.u.]. Every harmonic pair with "
            "f_n + f_m = f_p is amplified and every pair with "
            "|f_n - f_m| = f_p is converted, all through one rank-one block.")
        form.addRow("Pump frequency f_p:", self.fp_spin)

        self.nref_spin = QSpinBox()
        self.nref_spin.setRange(1, max(1, self.N))
        self.nref_spin.setPrefix("n = ")
        self.partner_label = QLabel()
        self.partner_label.setStyleSheet("color: #666; font-style: italic;")
        if n_ref is None:
            n_ref = int(round(0.5 * self.fp_spin.value() / self.FSR))
        self.nref_spin.setValue(int(min(max(int(n_ref), 1), max(1, self.N))))
        self.nref_spin.setToolTip(
            "Signal harmonic the rate is defined at. Its idler partner is "
            "the harmonic nearest f_p - n*FSR (shown beside).")
        nref_row = QHBoxLayout()
        nref_row.addWidget(self.nref_spin)
        nref_row.addWidget(self.partner_label)
        form.addRow("Reference harmonic:", nref_row)

        self.rate_spin = QDoubleSpinBox()
        self.rate_spin.setRange(0.0, 1e6)
        self.rate_spin.setDecimals(3)
        self.rate_spin.setSingleStep(1.0)
        self.rate_spin.setValue(float(rate_mau))
        self.rate_spin.setToolTip(
            "Parametric coupling rate between harmonic n of the line and "
            "its idler partner m in the twin [milli-arb. units]; every other "
            "pair follows the verified profile (n m / n_ref m_ref)^(-1/2) "
            "for an inductive element.")
        form.addRow("Rate @ (n, m) [mau]:", self.rate_spin)

        self.phase_spin = QDoubleSpinBox()
        self.phase_spin.setRange(-360.0, 360.0)
        self.phase_spin.setDecimals(1)
        self.phase_spin.setSingleStep(15.0)
        self.phase_spin.setValue(float(phase))
        self.phase_spin.setSuffix("\N{DEGREE SIGN}")
        form.addRow("Pump phase:", self.phase_spin)

        self.coupling_combo = QComboBox()
        self.coupling_combo.addItem(
            "modulated inductor  (g_n \N{PROPORTIONAL TO} 1/\N{SQUARE ROOT}n)",
            'inductive')
        self.coupling_combo.addItem(
            "modulated capacitor  (g_n \N{PROPORTIONAL TO} \N{SQUARE ROOT}n)",
            'capacitive')
        self.coupling_combo.setCurrentIndex(0 if coupling == 'inductive' else 1)
        form.addRow("Element:", self.coupling_combo)

        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.fp_spin.valueChanged.connect(lambda _v: self._refresh_partner())
        self.nref_spin.valueChanged.connect(lambda _v: self._refresh_partner())
        self._refresh_partner()

    def _refresh_partner(self):
        n = self.nref_spin.value()
        f_partner = self.fp_spin.value() - n * self.FSR
        m = int(min(max(int(round(f_partner / self.FSR)), 1), max(1, self.N)))
        mismatch = f_partner - m * self.FSR
        tag = "degenerate" if m == n else f"idler partner m = {m}"
        self.partner_label.setText(
            f"{tag}  (f_p \N{MINUS SIGN} f_n = {f_partner:g}; "
            f"off harmonic by {mismatch:+g})")

    def get_result(self):
        return {'end': self.end_combo.currentData(),
                'f_p': self.fp_spin.value(),
                'rate': self.rate_spin.value() / 1000.0,
                'phase': self.phase_spin.value(),
                'n_ref': self.nref_spin.value(),
                'coupling': self.coupling_combo.currentData()}


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
        self.selected_attachments = []     # [(port, attachment), ...]
        self.selected_taps = []            # [(line, end, conn), ...]
        self.selected_pump_buses = []   # lines whose pump bus is selected
        self._attach_pending_port = None   # port awaiting a node click (edge mode)
        self._attach_pending_line_end = None  # (line, end) awaiting a port
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
            'w_mult': 1.0,
            'h_mult': 1.0,
            'linewidth': PORT_LINEWIDTH,
            'color': 'black',
            'fill': 'white',
            'attachments': [],
        }
        self.ports.append(port)
        self.port_id_counter += 1
        self._invalidate_scattering_data()
        return port

    def add_line_resonator(self, label=None, pos=(0.0, 0.0), FSR=1.0,
                           Ztx=65.0, f_max=10.0, port_end='xL',
                           Z0_port=50.0, alpha_uniform=0.0, angle=0.0,
                           end_coupling=None, w_mult=1.0, h_mult=1.0,
                           linewidth=None, color='black', fill='#cccccc',
                           conj=False, twin_of=None):
        """Create a transmission-line macro glyph."""
        if label is None:
            label = f"TL{self.line_id_counter + 1}"
        line = {
            'line_id': self.line_id_counter,
            'label': label,
            # pumped termination: {'end', 'f_p', 'rate', 'phase', 'n_ref',
            # 'coupling', 'twin_id'} or None (see set_line_pump)
            'pump': None,
            # the idler-sector twin of a pumped line: conj=True and
            # twin_of=<primary line_id>; physics mirrored from the primary
            'conj': bool(conj),
            'twin_of': twin_of,
            'pos': (float(pos[0]), float(pos[1])),
            'angle': float(angle),
            'w_mult': float(w_mult),
            'h_mult': float(h_mult),
            'linewidth': float(linewidth if linewidth is not None
                               else LINE_LINEWIDTH),
            'color': color,
            'fill': fill,
            # Explicit end connections: each end holds a LIST, so several
            # loads can tap the same physical point (e.g. a stub resonator
            # read out by two ports). A line is NEVER implicitly terminated:
            # its port is a real, visible, editable glyph.
            'ends': {'x0': [], 'xL': []},
            # How a node tap at each end couples to the line. This is a
            # property of the physical tap, shared by everything attached
            # there, not of the individual graph mode.
            'end_coupling': dict(end_coupling
                                 or {'x0': 'capacitive', 'xL': 'capacitive'}),
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

        # A terminated line gets a REAL port glyph, placed just beyond the
        # chosen end and wired to it. Nothing is implied: the port is
        # visible, labelled, movable and deletable like any other.
        if port_end in ('x0', 'xL'):
            offset = self._default_port_offset_for_line(line)
            px = line['pos'][0] + (offset if port_end == 'xL' else -offset)
            port = self.add_port(label=line['label'], pos=(px, line['pos'][1]),
                                 monitored=True)
            if port_end == 'xL':
                port['angle'] = 180.0      # apex faces the line
                port['angle_pinned'] = True
            self.connect_line_end_to_port(line, port_end, port)

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
        # a pumped line takes its twin along; deleting a twin un-pumps its
        # primary (the twin only exists because of the pump)
        primary = self.line_primary(line)
        if primary is not None:
            primary['pump'] = None
            self._remove_twin_glyph(line)      # its ports go with it
        else:
            twin = self.line_twin(line)
            if twin is not None:
                self._remove_twin_glyph(twin)
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

    def _gui_hubs_payload(self, node_ids=None, line_ids=None):
        """Hub dicts for extract_graph_data(hubs=...).

        A port's hub column is the union of its node attachments and the
        comb couplings of any transmission-line end terminated on it — one
        physical resistor can see both a line and a device, and the hub
        model represents that as one channel. Ports with neither are inert
        and omitted.
        """
        # port_id -> [(line, end), ...] terminating on that port
        line_terms = {}
        for line in self.line_resonators:
            if line_ids is not None and line['line_id'] not in line_ids:
                continue
            for end in ('x0', 'xL'):
                for conn in self._end_conns(line, end):
                    if conn.get('kind') == 'port':
                        line_terms.setdefault(conn['port_id'], []).append(
                            (line, end))

        payload = []
        for port in self.ports:
            atts = port['attachments']
            terms = line_terms.get(port['port_id'], [])
            if node_ids is not None and atts and not all(
                    a['node_id'] in node_ids for a in atts):
                continue
            if not atts and not terms:
                continue
            hub = port_hub_payload(port)
            for line, end in terms:
                resonator = LineResonator(**line_payload(line))
                hub['attachments'].extend(resonator.end_couplings(end))
            payload.append(hub)
        return payload

    def _gui_lines_payload(self, line_ids=None):
        self._sync_all_twins()
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
            from PySide6.QtCore import Qt as _Qt
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Information)
            box.setWindowTitle("Explicit Ports enabled")
            box.setText(msg)
            box.setModal(False)
            # The notice must never take the keyboard: it is informational,
            # and the app's single-key shortcuts ('+', '-', '?', 'a', ...)
            # are WindowShortcut-scoped to the main window, so an activated
            # popup silently swallows every one of them until it is
            # dismissed. Show it without activating and hand focus straight
            # back to the canvas.
            box.setAttribute(_Qt.WA_ShowWithoutActivating, True)
            box.setWindowFlag(_Qt.Tool, True)
            box.show()
            self._explicit_ports_notice = box
            self.activateWindow()
            self.raise_()
            if getattr(self, 'canvas', None) is not None:
                self.canvas.setFocus()
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
            self._apply_port_style(port, result)
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

    def _prompt_tap_params(self, line, end, node, editing=False, conn=None):
        """Dialog for tap parameters; None on cancel (test seam)."""
        resonator = self.line_resonator_for(line)
        params = self.scattering_assignments.get(node['node_id'], {})
        freq = params.get('freq')
        n_nearest = (resonator.nearest_harmonic(freq)
                     if freq is not None else 1)
        coupling = (line.get('end_coupling') or {}).get(end, 'capacitive')
        conn = conn or {}
        dialog = TapInputDialog(
            line['label'], node['label'], end, coupling, resonator.N,
            n_nearest, rate_mau=conn.get('rate', 0.1) * 1000.0,
            sign=conn.get('sign', 1), n_ref=conn.get('n_ref'),
            parent=self, editing=editing)
        if dialog.exec() != QDialog.Accepted:
            return None
        return dialog.get_result()

    def _create_tap_interactively(self, line, end, node):
        result = self._prompt_tap_params(line, end, node)
        if result is None:
            self._status_message("Tap cancelled", 3000)
            return
        self._save_state()
        try:
            conn = self.connect_line_end_to_node(
                line, end, node, rate=result['rate'], sign=result['sign'],
                n_ref=result['n_ref'])
        except ValueError as exc:
            if self.undo_stack:
                self.undo_stack.pop()
            QMessageBox.warning(self, "Cannot tap line", str(exc))
            return
        coupling = (line.get('end_coupling') or {}).get(end, 'capacitive')
        msg = (f"Tapped '{node['label']}' onto '{line['label']}' ({end}, "
               f"{coupling}) \u2014 rate referenced to harmonic "
               f"n = {conn['n_ref']}; change it in the Ports & Lines panel")
        print(f"\u2713 {msg}")
        self._status_message(msg, 8000)
        if hasattr(self, 'properties_panel'):
            self.properties_panel._update_scattering_ports_table()
        self._update_plot()

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
        """Edge-tool click routing for ports, line ends and nodes.

        Two gestures, either click order:
          port  +  node      -> attachment link (a shared port simply gets
                                more than one attachment)
          line end + port    -> terminate that end of the line on the port

        A transmission line is NEVER exploded to make a connection: its comb
        stays inside the macro and the coupling is assembled under the hood.
        Returns True when the click was consumed.
        """
        if not (self.explicit_ports_enabled or self.ports
                or self.line_resonators):
            return False

        # --- a line END lead ---
        hit_end = self._find_line_end_at_position(event.xdata, event.ydata)
        if hit_end is not None:
            line, end = hit_end
            if self._attach_pending_port is not None:
                port = self._attach_pending_port
                self._attach_pending_port = None
                self._connect_line_end_interactively(line, end, port)
                return True
            if self.edge_mode_first_node is not None:
                node = self.edge_mode_first_node
                self.edge_mode_first_node = None
                self._create_tap_interactively(line, end, node)
                return True
            if self._attach_pending_line_end == hit_end:
                self._attach_pending_line_end = None
                self._status_message("Line-end connection cancelled", 4000)
            else:
                self._attach_pending_line_end = hit_end
                self._attach_pending_port = None
                self._status_message(
                    f"'{line['label']}' {end} end selected \u2014 now click a "
                    "port glyph to terminate it.", 6000)
            self._update_plot()
            return True

        # --- a port glyph ---
        port = self._find_port_at_position(event.xdata, event.ydata)
        if port is not None:
            if self._attach_pending_line_end is not None:
                line, end = self._attach_pending_line_end
                self._attach_pending_line_end = None
                self._connect_line_end_interactively(line, end, port)
                return True
            if self.edge_mode_first_node is not None:
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
                self._attach_pending_line_end = None
                self._status_message(
                    f"Port '{port['label']}' selected \u2014 now click the mode "
                    "to attach it to, or a line end to terminate.", 6000)
            self._update_plot()
            return True

        # --- the line BODY: point at the end leads ---
        line = self._find_line_at_position(event.xdata, event.ydata)
        if line is not None:
            self._attach_pending_port = None
            self._status_message(
                f"Connect '{line['label']}' by its END leads \u2014 click the "
                "lead at either end, then a port glyph.", 8000)
            return True

        # --- a node completing a pending port or line end ---
        node = self._find_node_at_position(event.xdata, event.ydata)
        if node is not None:
            if self._attach_pending_port is not None:
                port = self._attach_pending_port
                self._attach_pending_port = None
                self._create_attachment_interactively(port, node)
                return True
            if self._attach_pending_line_end is not None:
                line, end = self._attach_pending_line_end
                self._attach_pending_line_end = None
                self._create_tap_interactively(line, end, node)
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

        bus_line = self._find_pump_bus_at_position(event.xdata, event.ydata)
        if bus_line is not None:
            if is_double:
                self._edit_pump(bus_line)
            elif shift_pressed:
                if bus_line in self.selected_pump_buses:
                    self.selected_pump_buses.remove(bus_line)
                else:
                    self.selected_pump_buses.append(bus_line)
            else:
                self.selected_pump_buses = [bus_line]
                self.selected_ports = []
                self.selected_lines = []
                self.selected_attachments = []
                self.selected_taps = []
                self.selected_nodes.clear()
                self.selected_edges.clear()
                self._status_message(
                    f"Selected pump bus of '{bus_line['label']}' "
                    "\N{EM DASH} double-click to edit, D to remove", 6000)
            self._update_plot()
            return True

        tap_hit = self._find_tap_at_position(event.xdata, event.ydata)
        if tap_hit is not None:
            line, end, conn = tap_hit
            if is_double:
                node = next((n for n in self.nodes
                             if n['node_id'] == conn['node_id']), None)
                if node is not None:
                    result = self._prompt_tap_params(line, end, node,
                                                     editing=True, conn=conn)
                    if result is not None:
                        self._save_state()
                        conn.update(result)
                        self._invalidate_scattering_data()
                        if hasattr(self, 'properties_panel'):
                            self.properties_panel._update_scattering_ports_table()
                        self._update_plot()
            elif shift_pressed:
                if tap_hit in self.selected_taps:
                    self.selected_taps.remove(tap_hit)
                else:
                    self.selected_taps.append(tap_hit)
                self._update_plot()
            else:
                self.selected_taps = [tap_hit]
                self.selected_attachments = []
                self.selected_ports = []
                self.selected_lines = []
                self.selected_nodes.clear()
                self.selected_edges.clear()
                self._status_message(
                    f"Selected tap onto '{line['label']}' ({end}, "
                    f"n_ref={conn.get('n_ref', 1)}) \u2014 double-click to "
                    "edit, D to delete", 6000)
                self._update_plot()
            return True

        hit = self._find_attachment_at_position(event.xdata, event.ydata)
        if hit is not None:
            if is_double:
                self._edit_attachment(*hit)
            elif shift_pressed:
                if hit in self.selected_attachments:
                    self.selected_attachments.remove(hit)
                else:
                    self.selected_attachments.append(hit)
                self._update_plot()
            else:
                port, att = hit
                self.selected_attachments = [hit]
                self.selected_ports = []
                self.selected_lines = []
                self.selected_nodes.clear()
                self.selected_edges.clear()
                node = next((n for n in self.nodes
                             if n['node_id'] == att['node_id']), None)
                node_label = node['label'] if node else str(att['node_id'])
                self._status_message(
                    f"Selected attachment '{port['label']}' "
                    f"\N{RIGHTWARDS ARROW} '{node_label}' — double-click to "
                    "edit rate/sign, D to delete", 6000)
                self._update_plot()
            return True

        if not shift_pressed and (self.selected_ports or self.selected_lines
                                  or self.selected_attachments
                                  or self.selected_taps):
            # clicking empty space clears glyph selection alongside nodes
            self.selected_ports = []
            self.selected_lines = []
            self.selected_attachments = []
            self.selected_taps = []
        self.selected_pump_buses = []
        return False

    def _maybe_show_glyph_context_menu(self, event):
        """Right-click on a port/line/attachment: context menu (Edit /
        Delete / line: Explode). Returns True when consumed."""
        if not (self.ports or self.line_resonators):
            return False
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QCursor

        port = self._find_port_at_position(event.xdata, event.ydata)
        if port is not None:
            menu = QMenu(self)
            menu.addAction("Edit\N{HORIZONTAL ELLIPSIS}",
                           lambda: self._edit_port(port))
            menu.addAction("Rotate 15\N{DEGREE SIGN} CCW  (Ctrl+U)",
                           lambda: self._rotate_selected_glyph(port, 15))
            menu.addAction("Rotate 15\N{DEGREE SIGN} CW  (Ctrl+I)",
                           lambda: self._rotate_selected_glyph(port, -15))
            menu.addSeparator()
            auto = menu.addAction("Auto-orient")
            auto.setCheckable(True)
            auto.setChecked(not port.get('angle_pinned', False))

            def toggle_auto():
                # desired auto state = opposite of current (= pinned flag)
                self._save_state()
                self._apply_port_style(
                    port, {'auto_orient': port.get('angle_pinned', False)})
                self._update_plot()
            auto.triggered.connect(lambda _=False: toggle_auto())
            def delete_port():
                self._save_state()
                self.remove_port(port)
                self._update_plot()
            menu.addAction("Delete", delete_port)
            menu.exec(QCursor.pos())
            return True

        line = self._find_line_at_position(event.xdata, event.ydata)
        if line is not None:
            menu = QMenu(self)
            menu.addAction("Edit\N{HORIZONTAL ELLIPSIS}",
                           lambda: self._edit_line(line))
            menu.addAction("Rotate 15\N{DEGREE SIGN} CCW  (Ctrl+U)",
                           lambda: self._rotate_selected_glyph(line, 15))
            menu.addAction("Rotate 15\N{DEGREE SIGN} CW  (Ctrl+I)",
                           lambda: self._rotate_selected_glyph(line, -15))
            menu.addSeparator()
            if line.get('twin_of') is None:
                menu.addAction(
                    ("Edit" if line.get('pump') else "Add")
                    + " pumped termination\N{HORIZONTAL ELLIPSIS}",
                    lambda: self._edit_pump(line))
                if line.get('pump'):
                    menu.addAction("Remove pumped termination",
                                   lambda: self._remove_pump(line))
            else:
                menu.addAction("Edit pump bus\N{HORIZONTAL ELLIPSIS}",
                               lambda: self._edit_pump(line))
            menu.addSeparator()
            def explode():
                self._save_state()
                self.explode_line_resonator(line)
                self._update_plot()
            menu.addAction("Explode to Nodes (one-way)", explode)
            def delete_line():
                self._save_state()
                self.remove_line_resonator(line)
                self._update_plot()
            menu.addAction("Delete", delete_line)
            menu.exec(QCursor.pos())
            return True

        bus_line = self._find_pump_bus_at_position(event.xdata, event.ydata)
        if bus_line is not None:
            menu = QMenu(self)
            menu.addAction("Edit pump bus\N{HORIZONTAL ELLIPSIS}",
                           lambda: self._edit_pump(bus_line))
            menu.addAction("Remove pumped termination",
                           lambda: self._remove_pump(bus_line))
            menu.exec(QCursor.pos())
            return True

        hit = self._find_attachment_at_position(event.xdata, event.ydata)
        if hit is not None:
            hit_port, att = hit
            menu = QMenu(self)
            menu.addAction("Edit rate/sign\N{HORIZONTAL ELLIPSIS}",
                           lambda: self._edit_attachment(hit_port, att))
            def delete_att():
                self._save_state()
                self.remove_port_attachment(hit_port, att['node_id'])
                if hasattr(self, 'properties_panel'):
                    self.properties_panel._update_scattering_ports_table()
                self._update_plot()
            menu.addAction("Delete attachment", delete_att)
            menu.exec(QCursor.pos())
            return True
        return False

    def _shortcut_context(self):
        """Add a 'glyph' context for selected ports / lines."""
        if (self.selected_ports or self.selected_lines) \
                and not self.selected_nodes and not self.selected_edges:
            return 'glyph'
        return super()._shortcut_context()

    def _rotate_selected_glyph(self, glyph, angle_degrees):
        """Rotate one glyph from the context menu (selection-independent,
        so it works even when the keyboard shortcut is unavailable)."""
        saved = (self.selected_ports, self.selected_lines,
                 self.selected_nodes)
        is_port = 'port_id' in glyph
        self.selected_ports = [glyph] if is_port else []
        self.selected_lines = [] if is_port else [glyph]
        self.selected_nodes = []
        try:
            self._rotate_selected_nodes(angle_degrees)
        finally:
            (self.selected_ports, self.selected_lines,
             self.selected_nodes) = saved

    def _apply_port_style(self, port, result):
        """Apply a PortInputDialog result's appearance + orientation."""
        for key in ('w_mult', 'h_mult', 'linewidth', 'color', 'fill'):
            if key in result:
                port[key] = result[key]
        if 'auto_orient' in result:
            if result['auto_orient']:
                port['angle_pinned'] = False
            elif not port.get('angle_pinned'):
                # freeze at the current effective angle so unchecking the
                # box never visibly snaps the glyph
                port['angle'] = self._port_effective_angle(port)
                port['angle_pinned'] = True

    def _edit_port(self, port):
        dialog = PortInputDialog(default_label=port['label'],
                                 monitored=port['monitored'], parent=self,
                                 editing=True, port=port)
        if dialog.exec() == QDialog.Accepted:
            result = dialog.get_result()
            self._save_state()
            port['label'] = result['label']
            port['monitored'] = result['monitored']
            self._apply_port_style(port, result)
            self._invalidate_scattering_data()
            if hasattr(self, 'properties_panel'):
                self.properties_panel._update_scattering_ports_table()
            self._update_plot()

    def _prompt_pump_params(self, line, editing=False):
        """Seam for tests: returns a PumpInputDialog result dict or None."""
        pump = line.get('pump') or {}
        resonator = self.line_resonator_for(line)
        dialog = PumpInputDialog(
            line['label'], resonator.N, resonator.FSR,
            end=pump.get('end', 'x0'), f_p=pump.get('f_p'),
            rate_mau=pump.get('rate', 0.05) * 1000.0,
            phase=pump.get('phase', 0.0), n_ref=pump.get('n_ref'),
            coupling=pump.get('coupling', 'inductive'), parent=self,
            editing=editing)
        if dialog.exec() == QDialog.Accepted:
            return dialog.get_result()
        return None

    def _edit_pump(self, line):
        """Add or edit the pumped termination of `line` interactively."""
        if line.get('twin_of') is not None:
            line = self.line_primary(line) or line
        editing = bool(line.get('pump'))
        result = self._prompt_pump_params(line, editing=editing)
        if result is None:
            return
        self._save_state()
        try:
            self.set_line_pump(line, **result)
        except ValueError as exc:
            if self.undo_stack:
                self.undo_stack.pop()
            QMessageBox.warning(self, "Cannot pump this line", str(exc))
            return
        if hasattr(self, 'properties_panel'):
            self.properties_panel._update_scattering_ports_table()
        self._update_plot()

    def _remove_pump(self, line):
        if line.get('twin_of') is not None:
            line = self.line_primary(line) or line
        if not line.get('pump'):
            return
        self._save_state()
        self.clear_line_pump(line)
        self.selected_pump_buses = [l for l in self.selected_pump_buses
                                    if l is not line]
        if hasattr(self, 'properties_panel'):
            self.properties_panel._update_scattering_ports_table()
        self._update_plot()

    def _end_is_pumped(self, line, end):
        pump = line.get('pump')
        if pump and pump.get('end') == end:
            return True
        primary = self.line_primary(line)
        return bool(primary and primary.get('pump')
                    and primary['pump'].get('end') == end)

    def _pump_bus_wire(self, line):
        """Sampled wire of the pump bus from `line`'s pumped end into its
        twin's, or None."""
        pump = line.get('pump')
        twin = self.line_twin(line) if pump else None
        if twin is None:
            return None
        end = pump['end']
        p0, t0 = self._line_end_wire_start(line, end)
        p1, t1 = self._line_end_wire_start(twin, end)
        return self._wire_points(p0, t0, p1, -t1)

    def _find_pump_bus_at_position(self, x, y, tol=None):
        if x is None or y is None:
            return None
        tol = tol if tol is not None else 0.45 * self.node_radius
        for line in self.line_resonators:
            pts = self._pump_bus_wire(line)
            if pts is not None and self._dist_to_polyline(x, y, pts) <= tol:
                return line
        return None

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
            result.pop('port_end', None)   # topology is rewired on canvas
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

    def _select_all(self):
        """Select everything, glyphs included.

        Ctrl+A previously took only nodes and edges, so a "whole graph"
        selection silently left ports and lines behind — most visibly when
        rotating, where the modes turned and the glyphs stayed put.
        """
        super()._select_all()
        self.selected_ports = list(self.ports)
        self.selected_lines = list(self.line_resonators)
        self.selected_attachments = [
            (port, att) for port in self.ports
            for att in port['attachments']]
        self.selected_taps = [
            (line, end, conn)
            for line in self.line_resonators
            for end in ('x0', 'xL')
            for conn in self._end_conns(line, end)
            if conn.get('kind') == 'node']
        self.selected_pump_buses = [l for l in self.line_resonators
                                    if l.get('pump')]
        self._update_plot()

    def _rotate_selected_nodes(self, angle_degrees):
        """Rotate selection.

        With ONLY port/line glyphs selected, spin each glyph's own
        orientation in place (the useful primitive for aiming a lead).
        When nodes are selected too, the selection is a layout: everything
        rotates rigidly about the node centroid — glyph positions travel
        with the modes and each glyph's orientation turns by the same
        angle, so the drawing keeps its shape.

        Manually rotating an attached port pins its angle (turns off the
        auto-orient toward its attachments), starting from the current
        auto-orientation so the first step is a small visible nudge. In a
        rigid-body rotation an auto-orienting port is left UNpinned: its
        attachments moved too, so it re-aims itself correctly.
        """
        glyphs = list(self.selected_ports) + list(self.selected_lines)
        if glyphs and self.selected_nodes:
            # rigid-body: nodes exactly as before, glyphs carried along
            positions = np.array([n['pos'] for n in self.selected_nodes])
            centroid = positions.mean(axis=0)
            super()._rotate_selected_nodes(angle_degrees)
            for glyph in glyphs:
                gx, gy = _rotate_point(glyph['pos'][0], glyph['pos'][1],
                                       centroid[0], centroid[1],
                                       -angle_degrees)
                glyph['pos'] = (gx, gy)
                if 'port_id' in glyph and not glyph.get('angle_pinned'):
                    continue          # auto-orient re-aims it for free
                glyph['angle'] = (glyph.get('angle', 0.0)
                                  - angle_degrees) % 360.0
            self._update_plot()
            return

        if (self.selected_ports or self.selected_lines) \
                and not self.selected_nodes:
            self._save_state()
            for port in self.selected_ports:
                base = self._port_effective_angle(port)
                if port['attachments'] and not port.get('angle_pinned'):
                    self._status_message(
                        f"'{port['label']}' rotation pinned (auto-orient "
                        "toward attachments is off for it)", 5000)
                port['angle_pinned'] = True
                port['angle'] = (base - angle_degrees) % 360.0
            for line in self.selected_lines:
                line['angle'] = (line.get('angle', 0.0) - angle_degrees) % 360.0
            names = ', '.join(o['label'] for o in
                              self.selected_ports + self.selected_lines)
            print(f"Rotated {names} by {-angle_degrees:+g}\N{DEGREE SIGN}")
            self._update_plot()
            return
        super()._rotate_selected_nodes(angle_degrees)

    def _delete_selected_ports_lines(self):
        """Remove selected port/line glyphs and attachment links.

        Returns how many objects were removed."""
        count = 0
        for line, end, conn in list(self.selected_taps):
            conns = self._end_conns(line, end)
            if conn in conns:
                conns.remove(conn)
                line['ends'][end] = conns
                self._invalidate_scattering_data()
                count += 1
        self.selected_taps = []
        for line in list(self.selected_pump_buses):
            if line.get('pump'):
                self.clear_line_pump(line)
                count += 1
        self.selected_pump_buses = []
        for port, att in list(self.selected_attachments):
            if att in port['attachments']:
                self.remove_port_attachment(port, att['node_id'])
                count += 1
        self.selected_attachments = []
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
        w_mult = port.get('w_mult', 1.0)
        if port.get('autosize', True):
            # grow (never shrink) the body so the label fits inside it
            w_mult = max(w_mult, self._port_label_w_mult(port))
        w = PORT_BODY_W * r * w_mult
        h = PORT_BODY_H * r * port.get('h_mult', 1.0)
        apex_x = x + w / 2 + PORT_APEX_W * r * w_mult
        lead_tip_x = apex_x + PORT_LEAD_LEN * r
        return x, y, w, h, apex_x, lead_tip_x

    def _port_label_font_data(self, port):
        """Label font height in DATA units (shared by draw + autosize, so
        the two can never drift apart)."""
        scale = getattr(self.APP_CONFIG, 'PLOT_NODE_LABEL_FONT_SCALE', 0.35)
        h = PORT_BODY_H * self.node_radius * port.get('h_mult', 1.0)
        return h * scale * 1.45

    def _port_label_w_mult(self, port):
        """Smallest length multiplier whose body holds the port's label."""
        n_chars = max(len(str(port.get('label', ''))), 1)
        label_w = PORT_LABEL_ADVANCE * n_chars * self._port_label_font_data(port)
        needed = label_w / PORT_LABEL_FILL
        return needed / (PORT_BODY_W * self.node_radius)

    def _port_effective_angle(self, port):
        """Drawing/hit-test angle of a port glyph.

        A port with attachments auto-orients its apex toward the mean
        direction of its attached nodes, so the lead always points at what
        it terminates. Manual rotation (Ctrl+U/Ctrl+I) pins the angle
        ('angle_pinned'); unattached or pinned ports use the stored angle.
        """
        if port.get('angle_pinned'):
            return port.get('angle', 0.0)
        px, py = port['pos']
        node_pos = {n['node_id']: n['pos'] for n in self.nodes}
        targets = [node_pos[a['node_id']] for a in port['attachments']
                   if a['node_id'] in node_pos]
        # a terminated line end pulls the apex toward that lead too
        for line in self.line_resonators:
            for end in ('x0', 'xL'):
                if any(c.get('kind') == 'port'
                       and c.get('port_id') == port['port_id']
                       for c in self._end_conns(line, end)):
                    targets.append(self._line_end_points(line)[end])
        if not targets:
            return port.get('angle', 0.0)
        # aim the lead at the CENTER of the attached group (its centroid),
        # not the mean unit direction, so a cluster pulls proportionally
        cx = sum(pos[0] for pos in targets) / len(targets)
        cy = sum(pos[1] for pos in targets) / len(targets)
        vx, vy = cx - px, cy - py
        if abs(vx) < 1e-12 and abs(vy) < 1e-12:
            return port.get('angle', 0.0)
        return float(np.degrees(np.arctan2(vy, vx)))

    def _line_geometry(self, line):
        """(lx, ly, w, h, rx) in UNROTATED data units.

        w/h are the cylinder half-length/half-height (stretchable per line
        via 'w_mult'/'h_mult'); rx is the end-cap ellipse half-depth, tied
        to h so the coax perspective survives stretching.
        """
        r = self.node_radius
        lx, ly = line['pos']
        w = LINE_BODY_W * r * line.get('w_mult', 1.0)
        h = LINE_BODY_H * r * line.get('h_mult', 1.0)
        return lx, ly, w, h, 0.5 * h

    def _line_end_points(self, line):
        """Rotated lead-tip coordinates of the line's two ends."""
        r = self.node_radius
        lx, ly, w, h, rx = self._line_geometry(line)
        angle = line.get('angle', 0.0)
        x0 = lx - w - rx - LINE_LEAD_LEN * r
        xL = lx + w + rx + LINE_LEAD_LEN * r
        return {'x0': _rotate_point(x0, ly, lx, ly, angle),
                'xL': _rotate_point(xL, ly, lx, ly, angle)}

    def _find_line_end_at_position(self, x, y, tol=None):
        """Return (line, end) whose lead tip is near (x, y), else None."""
        if x is None or y is None:
            return None
        tol = tol if tol is not None else 0.9 * self.node_radius
        best = None
        best_d = tol
        for line in reversed(self.line_resonators):
            for end, (ex, ey) in self._line_end_points(line).items():
                d = float(np.hypot(x - ex, y - ey))
                if d <= best_d:
                    best, best_d = (line, end), d
        return best

    @staticmethod
    def _end_conns(line, end):
        """Connection list at one end (normalizes legacy None/dict forms)."""
        raw = (line.get('ends') or {}).get(end)
        if not raw:
            return []
        return [raw] if isinstance(raw, dict) else list(raw)

    def _line_end_ports(self, line, end):
        """Port glyphs terminating `end`, in connection order."""
        out = []
        for conn in self._end_conns(line, end):
            if conn.get('kind') != 'port':
                continue
            port = next((p for p in self.ports
                         if p['port_id'] == conn['port_id']), None)
            if port is not None:
                out.append(port)
        return out

    def _line_end_port(self, line, end):
        """First port glyph terminating `end`, or None (drawing helper)."""
        ports = self._line_end_ports(line, end)
        return ports[0] if ports else None

    def connect_line_end_to_port(self, line, end, port):
        """Terminate one end of a line on an explicit port glyph.

        The port's hub column gains the line's comb couplings
        kappa_n = u_n(end)*sqrt(gamma) at extraction time; the port stays a
        first-class, movable, deletable glyph carrying its own label (and it
        may also attach to ordinary nodes — one physical resistor can see
        both a line and a device).
        """
        line.setdefault('ends', {'x0': [], 'xL': []})
        for e in ('x0', 'xL'):
            line['ends'][e] = self._end_conns(line, e)   # normalize
        other = 'xL' if end == 'x0' else 'x0'
        if line['ends'][other]:
            # Several loads at the SAME end are fine: they tap one physical
            # point, each contributing its own rank-one u_n(end) damper, and
            # that reproduces ABCD within the comb-truncation floor
            # (test_line_same_end_multiport). Loading BOTH ends is the
            # through-line two-port, which has no written-and-verified ABCD
            # two-port reference yet — refuse rather than ship an
            # unvalidated S21.
            raise ValueError(
                f"'{line['label']}' is already terminated at its {other} "
                "end. A two-port line (both ends loaded, i.e. transmission "
                "through the line) is a Phase-2 feature blocked on a "
                "written-and-verified ABCD two-port reference. Several "
                "loads on the SAME end are supported.")
        if any(c.get('port_id') == port['port_id']
               for c in line['ends'][end]):
            return None                                   # already attached
        conn = {'kind': 'port', 'port_id': port['port_id']}
        line['ends'][end].append(conn)
        self._invalidate_scattering_data()
        return conn

    def line_resonator_for(self, line):
        """The numerics-side LineResonator for a GUI line dict."""
        return LineResonator(**line_payload(line))

    def connect_line_end_to_node(self, line, end, node, rate=None,
                                 sign=1, n_ref=None):
        """Tap a graph mode onto one end of a line.

        ONE connection stands for the conservative couplings to every comb
        mode: g_n = rate * u_n(end) * (n/n_ref)^(+-1/2), the exponent set by
        the END's coupling type (capacitive/inductive — a property of the
        physical tap, shared by everything attached there). `rate` is the
        coupling AT harmonic `n_ref`, which removes the ambiguity when the
        attached mode's frequency is not on a harmonic; it defaults to the
        harmonic nearest that mode's assigned frequency.
        """
        node_id = node['node_id'] if isinstance(node, dict) else node
        if line.get('pump') or line.get('twin_of') is not None:
            raise ValueError(
                "Node taps on a pumped line (or its conjugate twin) are not "
                "supported yet: the tapped mode would need its own conjugate "
                "copy in the idler sector.")
        line.setdefault('ends', {'x0': [], 'xL': []})
        for e in ('x0', 'xL'):
            line['ends'][e] = self._end_conns(line, e)
        resonator = self.line_resonator_for(line)
        if n_ref is None:
            params = self.scattering_assignments.get(node_id, {})
            freq = params.get('freq')
            n_ref = (resonator.nearest_harmonic(freq) if freq is not None
                     else 1)
        if rate is None:
            rate = self.APP_CONFIG.DEFAULT_EDGE_RATE / 1000.0 \
                if hasattr(self.APP_CONFIG, 'DEFAULT_EDGE_RATE') else 0.1
        for conn in line['ends'][end]:
            if conn.get('kind') == 'node' and conn['node_id'] == node_id:
                conn.update({'rate': float(rate), 'sign': 1 if sign >= 0 else -1,
                             'n_ref': int(n_ref)})
                self._invalidate_scattering_data()
                return conn
        conn = {'kind': 'node', 'node_id': node_id, 'rate': float(rate),
                'sign': 1 if sign >= 0 else -1, 'n_ref': int(n_ref)}
        line['ends'][end].append(conn)
        self._invalidate_scattering_data()
        return conn

    # ---- pumped termination: linked conjugate twin + rank-one pump bus ----

    def line_twin(self, line):
        """The conjugate twin of a pumped line (None if unpumped)."""
        pump = line.get('pump')
        if not pump:
            return None
        return next((l for l in self.line_resonators
                     if l['line_id'] == pump.get('twin_id')), None)

    def line_primary(self, line):
        """The primary of a twin line (None if `line` is not a twin)."""
        if line.get('twin_of') is None:
            return None
        return next((l for l in self.line_resonators
                     if l['line_id'] == line['twin_of']), None)

    def _pump_reference_pair(self, line):
        """(n_ref, m_ref): the signal harmonic the rate is defined at and
        its idler partner, the harmonic nearest f_p - n_ref*FSR."""
        pump = line['pump']
        resonator = self.line_resonator_for(line)
        n_ref = int(pump.get('n_ref', 1))
        f_partner = float(pump['f_p']) - n_ref * resonator.FSR
        return n_ref, resonator.nearest_harmonic(f_partner)

    def set_line_pump(self, line, end, f_p, rate, phase=0.0, n_ref=None,
                      coupling='inductive', twin_pos=None):
        """Terminate `end` of `line` in a modulated element pumped at f_p.

        Physics (docs/pumped_line_termination.md): one element at one
        point couples through the single scalar Phi(end), so the parametric
        block between the comb and its conjugate twin is the RANK-ONE outer
        product g g^T of the end profile, with the inductive envelope
        g_n ~ u_n(end)/sqrt(n) for a modulated inductor (capacitive for a
        modulated capacitor). `rate` is the coupling between harmonic n_ref
        of the line and harmonic m_ref of its twin, m_ref being the harmonic
        nearest f_p - n_ref*FSR (the idler partner); every other pair
        follows the verified profile. The DC mode is excluded, as for taps.

        The twin is a real, linked glyph (own position/angle/style, mirrored
        physics) with its own port glyphs mirroring the primary's
        terminations: one hub column per sector, since a resistor does not
        convert frequency.
        """
        if line.get('twin_of') is not None:
            raise ValueError("Pump the primary line, not its conjugate twin.")
        if end not in ('x0', 'xL'):
            raise ValueError("end must be 'x0' or 'xL'")
        if coupling not in PUMP_COUPLINGS:
            raise ValueError(f"coupling must be one of {PUMP_COUPLINGS!r}")
        if self._line_tap_node_ids(line):
            raise ValueError(
                "A pumped line cannot carry node taps yet: a tapped mode "
                "would need its own conjugate copy in the idler sector "
                "(open item: how a shared port drives signal AND conjugate).")
        resonator = self.line_resonator_for(line)
        if n_ref is None:
            n_ref = resonator.nearest_harmonic(0.5 * float(f_p))
        n_ref = int(min(max(int(n_ref), 1), resonator.N))

        twin = self.line_twin(line)
        if twin is None:
            r = self.node_radius
            if twin_pos is None:
                lx, ly = line['pos']
                twin_pos = (lx, ly - 5.0 * r)
            twin = self.add_line_resonator(
                label=f"{line['label']}*", pos=twin_pos,
                angle=line.get('angle', 0.0),
                FSR=line['FSR'], Ztx=line['Ztx'], f_max=line['f_max'],
                port_end=None, Z0_port=line.get('Z0_port', 50.0),
                alpha_uniform=line.get('alpha_uniform', 0.0),
                end_coupling=dict(line.get('end_coupling') or {}),
                w_mult=line.get('w_mult', 1.0), h_mult=line.get('h_mult', 1.0),
                linewidth=line.get('linewidth'), color=line.get('color', 'black'),
                fill='white', conj=True, twin_of=line['line_id'])
            # mirror the primary's port terminations: same resistor, one
            # hub column per sector
            for e in ('x0', 'xL'):
                for port in self._line_end_ports(line, e):
                    offset = self._default_port_offset_for_line(twin)
                    tx, ty = twin['pos']
                    theta = np.radians(twin.get('angle', 0.0))
                    sgn = 1.0 if e == 'xL' else -1.0
                    ppos = (tx + sgn * offset * np.cos(theta),
                            ty + sgn * offset * np.sin(theta))
                    tport = self.add_port(label=f"{port['label']}*",
                                          pos=ppos,
                                          monitored=port.get('monitored', True))
                    self.connect_line_end_to_port(twin, e, tport)
        line['pump'] = {
            'end': end, 'f_p': float(f_p), 'rate': float(rate),
            'phase': float(phase), 'n_ref': n_ref, 'coupling': coupling,
            'twin_id': twin['line_id'],
        }
        self._sync_twin(line)
        self._invalidate_scattering_data()
        return twin

    def clear_line_pump(self, line):
        """Remove the pumped termination and its twin glyph."""
        twin = self.line_twin(line)
        line['pump'] = None
        if twin is not None:
            self._remove_twin_glyph(twin)
        self._invalidate_scattering_data()

    def _remove_twin_glyph(self, twin):
        # the twin's own ports go with it when nothing else uses them
        for e in ('x0', 'xL'):
            for port in list(self._line_end_ports(twin, e)):
                other_users = any(
                    conn.get('kind') == 'port'
                    and conn.get('port_id') == port['port_id']
                    for l in self.line_resonators if l is not twin
                    for ee in ('x0', 'xL')
                    for conn in self._end_conns(l, ee))
                if not port['attachments'] and not other_users:
                    self.remove_port(port)
        if twin in self.line_resonators:
            self.line_resonators.remove(twin)
        if twin in self.selected_lines:
            self.selected_lines.remove(twin)

    def _sync_twin(self, line):
        """Mirror the primary's physics onto its twin (same physical line)."""
        twin = self.line_twin(line)
        if twin is None:
            return
        for key in TWIN_MIRRORED_KEYS:
            twin[key] = line[key]
        twin['end_coupling'] = dict(line.get('end_coupling')
                                    or {'x0': 'capacitive', 'xL': 'capacitive'})
        twin['label'] = f"{line['label']}*"
        twin['conj'] = True
        twin['twin_of'] = line['line_id']

    def _sync_all_twins(self):
        for line in self.line_resonators:
            if line.get('pump'):
                self._sync_twin(line)

    def _gui_pump_edges(self, line_ids=None):
        """Synthesized (edge_dict, params) pairs for every pump bus.

        One drawn bus stands for the rank-one block: rate_nm = rate * w_n *
        w_m with w the end profile relative to the reference pair, phase =
        pump phase + the sign pattern u_n(end) u_m(end). The extractor sees
        ordinary pumped edges from the signal comb into the conjugate comb.
        """
        out = []
        for line in self.line_resonators:
            pump = line.get('pump')
            if not pump:
                continue
            if line_ids is not None and line['line_id'] not in line_ids:
                continue
            twin = self.line_twin(line)
            if twin is None:
                continue
            self._sync_twin(line)
            end = pump['end']
            n_ref, m_ref = self._pump_reference_pair(line)
            coupling = pump.get('coupling', 'inductive')
            res = self.line_resonator_for(line)
            tres = self.line_resonator_for(twin)
            sig = res.tap_couplings(end, n_ref, coupling)
            idl = tres.tap_couplings(end, m_ref, coupling)
            rate = float(pump['rate'])
            phase0 = float(pump.get('phase', 0.0))
            f_p = float(pump['f_p'])
            for sid, wn, phn in sig:
                for tid, wm, phm in idl:
                    edge = {'from_node_id': sid, 'to_node_id': tid,
                            'is_self_loop': False}
                    out.append((edge, {'f_p': f_p,
                                       'rate': rate * wn * wm,
                                       'phase': (phase0 + phn + phm) % 360.0,
                                       'frame_rule': 'sector'}))
        return out

    def _gui_synth_edges(self, line_ids=None, node_ids=None):
        """All macro-synthesized edges: node taps + pump buses."""
        return (self._gui_tap_edges(line_ids=line_ids, node_ids=node_ids)
                + self._gui_pump_edges(line_ids=line_ids))

    def _gui_tap_edges(self, line_ids=None, node_ids=None):
        """Synthesized (edge_dict, params) pairs for every node tap.

        The user draws one connection; this fans it out into the individual
        conservative couplings to each comb mode, which the extractor then
        sees as ordinary static (f_p = 0) edges. The comb never surfaces in
        the GUI.
        """
        out = []
        for line in self.line_resonators:
            if line_ids is not None and line['line_id'] not in line_ids:
                continue
            resonator = self.line_resonator_for(line)
            couplings = (line.get('end_coupling')
                         or {'x0': 'capacitive', 'xL': 'capacitive'})
            for end in ('x0', 'xL'):
                coupling = couplings.get(end, 'capacitive')
                for conn in self._end_conns(line, end):
                    if conn.get('kind') != 'node':
                        continue
                    node_id = conn['node_id']
                    if node_ids is not None and node_id not in node_ids:
                        continue
                    rate = float(conn.get('rate', 0.0))
                    flip = conn.get('sign', 1) < 0
                    n_ref = int(conn.get('n_ref', 1))
                    for comb_id, weight, phase in resonator.tap_couplings(
                            end, n_ref, coupling):
                        if flip:
                            phase = (phase + 180.0) % 360.0
                        edge = {'from_node_id': node_id,
                                'to_node_id': comb_id,
                                'is_self_loop': False}
                        out.append((edge, {'f_p': 0.0,
                                           'rate': rate * weight,
                                           'phase': phase}))
        return out

    def _line_tap_node_ids(self, line):
        """Node ids tapped onto either end of `line`."""
        ids = set()
        for end in ('x0', 'xL'):
            ids.update(c['node_id'] for c in self._end_conns(line, end)
                       if c.get('kind') == 'node')
        return ids

    def _find_tap_at_position(self, x, y, tol=None):
        """Return (line, end, conn) whose tap link passes near (x, y)."""
        if x is None or y is None:
            return None
        tol = tol if tol is not None else 0.35 * self.node_radius
        node_by_id = {n['node_id']: n for n in self.nodes}
        for line in self.line_resonators:
            for end in ('x0', 'xL'):
                for conn in self._end_conns(line, end):
                    if conn.get('kind') != 'node':
                        continue
                    wire = self._tap_wire(line, end, conn, node_by_id)
                    if wire is None:
                        continue
                    if self._dist_to_polyline(x, y, wire) <= tol:
                        return line, end, conn
        return None

    def disconnect_line_end(self, line, end, port=None):
        """Drop one connection at `end` (or all of them when port is None)."""
        line.setdefault('ends', {'x0': [], 'xL': []})
        conns = self._end_conns(line, end)
        if port is None:
            line['ends'][end] = []
        else:
            line['ends'][end] = [c for c in conns
                                 if c.get('port_id') != port['port_id']]
        self._invalidate_scattering_data()

    def _connect_line_end_interactively(self, line, end, port):
        self._save_state()
        try:
            self.connect_line_end_to_port(line, end, port)
        except ValueError as exc:
            if self.undo_stack:
                self.undo_stack.pop()       # nothing changed
            QMessageBox.warning(self, "Two-port line not available", str(exc))
            self._status_message(str(exc), 9000)
            return
        msg = (f"Terminated '{line['label']}' ({end}) on port "
               f"'{port['label']}' — its comb couples through that port")
        print(f"\u2713 {msg}")
        self._status_message(msg, 6000)
        if hasattr(self, 'properties_panel'):
            self.properties_panel._update_scattering_ports_table()
        self._update_plot()

    def _default_port_offset_for_line(self, line):
        """Center-to-center distance placing a port just beyond a lead."""
        r = self.node_radius
        _, _, w, _, rx = self._line_geometry(line)
        return (w + rx + LINE_LEAD_LEN * r
                + (PORT_LEAD_LEN + PORT_APEX_W + PORT_BODY_W / 2 + 0.4) * r)

    def _port_lead_tip(self, port):
        """Rotated position of the lead tip (attachment links start here)."""
        x, y, _, _, _, lead_tip_x = self._port_geometry(port)
        return _rotate_point(lead_tip_x, y, x, y,
                             self._port_effective_angle(port))

    def _find_port_at_position(self, x, y):
        if x is None or y is None:
            return None
        for port in reversed(self.ports):
            px, py, w, h, apex_x, _ = self._port_geometry(port)
            # undo the glyph rotation, then test the axis-aligned shape
            ux, uy = _rotate_point(x, y, px, py,
                                   -self._port_effective_angle(port))
            if (px - w / 2 <= ux <= apex_x) and (py - h / 2 <= uy <= py + h / 2):
                return port
        return None

    def _find_line_at_position(self, x, y):
        if x is None or y is None:
            return None
        r = self.node_radius
        for line in reversed(self.line_resonators):
            lx, ly, w, h, rx = self._line_geometry(line)
            ux, uy = _rotate_point(x, y, lx, ly, -line.get('angle', 0.0))
            w = w + rx + LINE_LEAD_LEN * r
            h = max(h, 0.35 * r)   # slender coax stays grabbable
            if (lx - w <= ux <= lx + w) and (ly - h <= uy <= ly + h):
                return line
        return None

    def _find_attachment_at_position(self, x, y, tol=None):
        """Return (port, attachment) whose dashed link passes near (x, y)."""
        if x is None or y is None:
            return None
        tol = tol if tol is not None else 0.35 * self.node_radius
        node_by_id = {n['node_id']: n for n in self.nodes}
        for port in self.ports:
            for att in port['attachments']:
                pts = self._attachment_wire(port, att, node_by_id)
                if pts is None:
                    continue
                if self._dist_to_polyline(x, y, pts) <= tol:
                    return port, att
        return None

    # ---- wire routing (rounded, tangent-constrained) ----

    def _wire_points(self, p0, t0, p1, t1, samples=33):
        """Sampled cubic-Bezier wire from p0 (leaving along unit tangent
        t0) to p1 (arriving traveling along unit tangent t1).

        This is the ComfyUI/Blender-node routing style: every wire leaves
        its terminal colinear with the terminal's lead and lands on its
        target along the target's own normal, with one smooth rounded
        curve in between (no rectilinear jogs). All wires out of one port
        share p0 and t0, so a fan collimates through the lead before
        spreading.
        """
        p0 = np.asarray(p0, dtype=float)
        p1 = np.asarray(p1, dtype=float)
        t0 = np.asarray(t0, dtype=float)
        t1 = np.asarray(t1, dtype=float)
        r = self.node_radius
        d = float(np.hypot(*(p1 - p0)))
        c = min(max(0.45 * d, 0.9 * r), 4.0 * r)
        c0 = p0 + c * t0
        c1 = p1 - c * t1
        ts = np.linspace(0.0, 1.0, samples)[:, None]
        pts = ((1 - ts) ** 3 * p0 + 3 * (1 - ts) ** 2 * ts * c0
               + 3 * (1 - ts) * ts ** 2 * c1 + ts ** 3 * p1)
        return pts

    def _port_wire_start(self, port):
        """(lead-tip point, outward unit tangent) of a port terminal."""
        theta = np.radians(self._port_effective_angle(port))
        return (np.array(self._port_lead_tip(port), dtype=float),
                np.array([np.cos(theta), np.sin(theta)]))

    def _line_end_wire_start(self, line, end):
        """(lead-tip point, outward unit tangent) of a line-end terminal."""
        theta = np.radians(line.get('angle', 0.0))
        axis = np.array([np.cos(theta), np.sin(theta)])
        pt = np.array(self._line_end_points(line)[end], dtype=float)
        return pt, (axis if end == 'xL' else -axis)

    def _node_wire_end(self, node, toward):
        """(entry point on the node circle, arrival unit tangent).

        The wire enters normal to the circle tangent — i.e. radially — on
        the side facing `toward` (the emitting terminal's lead tip).
        """
        cx, cy = node['pos']
        radius = self.node_radius * node.get('node_size_mult', 1.0)
        u = np.array([toward[0] - cx, toward[1] - cy], dtype=float)
        norm = float(np.hypot(*u))
        u = u / norm if norm > 1e-12 else np.array([1.0, 0.0])
        return np.array([cx, cy]) + radius * u, -u

    def _attachment_wire(self, port, att, node_by_id=None):
        """Sampled wire for one port->node attachment link, or None."""
        nodes = (node_by_id if node_by_id is not None
                 else {n['node_id']: n for n in self.nodes})
        node = nodes.get(att['node_id'])
        if node is None:
            return None
        p0, t0 = self._port_wire_start(port)
        p1, t1 = self._node_wire_end(node, p0)
        return self._wire_points(p0, t0, p1, t1)

    def _tap_wire(self, line, end, conn, node_by_id=None):
        """Sampled wire for one line-end->node tap link, or None."""
        nodes = (node_by_id if node_by_id is not None
                 else {n['node_id']: n for n in self.nodes})
        node = nodes.get(conn['node_id'])
        if node is None:
            return None
        p0, t0 = self._line_end_wire_start(line, end)
        p1, t1 = self._node_wire_end(node, p0)
        return self._wire_points(p0, t0, p1, t1)

    def _line_end_port_wire(self, line, end, port):
        """Sampled wire for a line-end->port termination link."""
        p0, t0 = self._line_end_wire_start(line, end)
        p1, tp = self._port_wire_start(port)
        # arrive at the port lead tip traveling INTO the lead
        return self._wire_points(p0, t0, p1, -tp)

    @staticmethod
    def _dist_to_polyline(x, y, pts):
        """Minimum distance from (x, y) to a sampled wire."""
        p = np.array([x, y], dtype=float)
        a = pts[:-1]
        b = pts[1:]
        seg = b - a
        seg_len2 = np.einsum('ij,ij->i', seg, seg)
        seg_len2[seg_len2 == 0.0] = 1e-30
        t = np.clip(np.einsum('ij,ij->i', p - a, seg) / seg_len2, 0.0, 1.0)
        proj = a + t[:, None] * seg
        return float(np.min(np.hypot(*(p - proj).T)))

    @staticmethod
    def wire_style(conn, default_color=WIRE_COLOR):
        """(color, linewidth) of one wire, honoring per-wire overrides."""
        color = conn.get('color') or default_color
        mult = float(conn.get('linewidth_mult', 1.25))
        return color, WIRE_LINEWIDTH * mult

    def _draw_wire(self, ax, pts, color, linewidth, linestyle='-',
                   selected=False, zorder=4, alpha=0.9):
        """Draw one routed wire (with the salmon selection underlay)."""
        if selected:
            ax.add_line(mlines.Line2D(
                pts[:, 0], pts[:, 1], color='salmon',
                linewidth=max(4.0, linewidth + 2.6),
                zorder=zorder - 0.5, alpha=0.9, solid_capstyle='round'))
        ax.add_line(mlines.Line2D(
            pts[:, 0], pts[:, 1], color=color, linewidth=linewidth,
            linestyle=linestyle, zorder=zorder, alpha=alpha,
            solid_capstyle='round'))

    def _draw_wire_label(self, ax, pts, conn, ppdu, color, fallback=None):
        """Label a wire at its midpoint, node-style (edge-label parity).

        A user-set 'label' wins; otherwise `fallback` (the tap's reference
        harmonic) is drawn, and a wire with neither stays bare.
        """
        text = conn.get('label') or fallback
        if not text:
            return
        mx, my = pts[len(pts) // 2]
        scale = float(conn.get('label_size_mult', 1.0))
        font_pts = 0.55 * self.node_radius * ppdu * scale * getattr(
            self.APP_CONFIG, 'PLOT_NODE_LABEL_FONT_SCALE', 0.35) * 1.45
        ax.text(mx, my, text, fontsize=max(font_pts, 1.0), color=color,
                ha='center', va='center', zorder=5,
                bbox=dict(boxstyle='round,pad=0.18', fc='white',
                          ec=color, lw=0.6))

    def _adjust_glyph_size(self, direction):
        """Arrow-key stretch for selected ports/lines (node-key parity):
        Up/Down = height, Left/Right = length."""
        glyphs = list(self.selected_ports) + list(self.selected_lines)
        if not glyphs:
            return False
        self._save_state()
        key, step = (('h_mult', 0.1) if direction in ('up', 'down')
                     else ('w_mult', 0.1))
        sign = 1 if direction in ('up', 'right') else -1
        for g in glyphs:
            if key == 'w_mult' and g.get('autosize', True) \
                    and 'port_id' in g:
                # take over from autosize starting at its current width, so
                # the first keystroke is a small visible nudge
                g['w_mult'] = max(g.get('w_mult', 1.0),
                                  self._port_label_w_mult(g))
                g['autosize'] = False
            g[key] = float(np.clip(g.get(key, 1.0) + sign * step,
                                   GLYPH_SIZE_MIN, GLYPH_SIZE_MAX))
        self._update_plot()
        return True

    # ---- drawing ----

    def _glyph_points_per_data_unit(self, ax):
        """Same zoom-scaling factor _draw_nodes uses for label sizes."""
        fig = ax.figure
        xlim, ylim = ax.get_xlim(), ax.get_ylim()
        ppdu_x = fig.get_figwidth() * 72 / (xlim[1] - xlim[0])
        ppdu_y = fig.get_figheight() * 72 / (ylim[1] - ylim[0])
        return min(ppdu_x, ppdu_y)

    @staticmethod
    def _readable_angle(angle_deg):
        """Glyph angle folded into the readable half-turn.

        A label rides its glyph so it always sits inside the body, but text
        that ends up upside down is worse than text that is merely
        mirrored about the glyph axis — so past a quarter turn it flips,
        the usual schematic convention (and the one this app's edge labels
        already follow).
        """
        angle = float(angle_deg) % 360.0
        if 90.0 < angle <= 270.0:
            angle -= 180.0
        return angle

    def _draw_glyph_label(self, ax, text, x, y, font_size_points,
                          points_per_data_unit, color='black', rotation=0.0):
        """Draw a glyph label in the SAME style as node labels: bold
        sans-serif mathtext (or sfmath in LaTeX mode) with _/^ handling,
        via the cached vector renderer so it scales with zoom."""
        if not text or not text.strip():
            return
        import re as _re
        if self.use_latex:
            def apply_font(t):
                return r'\mathbf{' + t + '}'
        else:
            def apply_font(t):
                return r'\mathbf{\mathsf{' + t + '}}'
        parts = _re.split(r'([_^])', text)
        formatted = []
        i = 0
        while i < len(parts):
            if parts[i] in ('_', '^'):
                formatted.append(parts[i])
                i += 1
                if i < len(parts):
                    content = parts[i]
                    if content.startswith('{') and content.endswith('}'):
                        formatted.append('{' + apply_font(content[1:-1]) + '}')
                    else:
                        formatted.append(apply_font(content))
                    i += 1
            elif parts[i]:
                formatted.append(apply_font(parts[i]))
                i += 1
            else:
                i += 1
        self._label_cache.draw(
            ax, rf"${''.join(formatted)}$", x, y,
            fontsize_points=font_size_points,
            points_per_data_unit=points_per_data_unit,
            color=color, ha='center', va='center', rotation=rotation,
            usetex=self.use_latex, zorder=12)

    def _draw_ports_and_lines(self, ax=None):
        """Draw port/loss-hub/line glyphs and their routed wiring."""
        if not (self.ports or self.line_resonators):
            return
        ax = ax or self.canvas.ax
        r = self.node_radius
        node_by_id = {n['node_id']: n for n in self.nodes}
        ppdu = self._glyph_points_per_data_unit(ax)
        config = self.APP_CONFIG
        label_font_scale = getattr(config, 'PLOT_NODE_LABEL_FONT_SCALE', 0.35)

        for port in self.ports:
            x, y, w, h, apex_x, lead_tip_x = self._port_geometry(port)
            angle = self._port_effective_angle(port)
            selected = port in self.selected_ports
            pending = port is self._attach_pending_port
            stroke = 'dodgerblue' if pending else port.get('color', 'black')
            lw = float(port.get('linewidth', PORT_LINEWIDTH))

            def rot(px, py):
                return _rotate_point(px, py, x, y, angle)

            # home-plate pentagon: square back, flat top/bottom, tapered
            # nose (diagrammer reference art), rotated about pos
            verts = [
                rot(x - w / 2, y - h / 2),
                rot(x + w / 2, y - h / 2),
                rot(apex_x, y),
                rot(x + w / 2, y + h / 2),
                rot(x - w / 2, y + h / 2),
            ]
            # selection indicator: salmon halo behind the glyph, matching
            # the node/edge selection language
            if selected:
                halo = mpatches.Polygon(
                    verts, closed=True, fill=False, edgecolor='salmon',
                    linewidth=6.0, zorder=10.5)
                ax.add_patch(halo)
            body = mpatches.Polygon(
                verts, closed=True,
                facecolor=(port.get('fill', 'white') if port['monitored']
                           else '#e8e8e8'),
                edgecolor=stroke, linewidth=lw, zorder=11,
                joinstyle='miter',
                linestyle='--' if pending else '-',
                hatch=None if port['monitored'] else '///')
            ax.add_patch(body)

            # terminal lead at the apex — same stroke as the body
            (ax0, ay0), (ax1, ay1) = rot(apex_x, y), rot(lead_tip_x, y)
            ax.add_line(mlines.Line2D(
                [ax0, ax1], [ay0, ay1], color=stroke,
                linewidth=lw, solid_capstyle='butt', zorder=11))

            # attachment wires: every wire leaves the lead tip colinear
            # with the lead (a multi-wire fan collimates through it) and
            # enters its node normal to the circle
            for att in port['attachments']:
                pts = self._attachment_wire(port, att, node_by_id)
                if pts is None:
                    continue
                att_selected = (port, att) in self.selected_attachments
                default = (WIRE_COLOR if att['sign'] >= 0
                           else WIRE_COLOR_INVERTED)
                link_color, lw = self.wire_style(att, default)
                self._draw_wire(ax, pts, link_color, lw,
                                selected=att_selected, zorder=4)
                mx, my = pts[len(pts) // 2]
                if att_selected:
                    ax.add_patch(mpatches.Circle(
                        (mx, my), 0.3, facecolor='lightcoral',
                        edgecolor='red', linewidth=2, zorder=20))
                # an inverted-sign wire is marked at the midpoint unless the
                # user gave the wire a label of its own
                self._draw_wire_label(
                    ax, pts, att, ppdu, link_color,
                    fallback=('\N{MINUS SIGN}' if att['sign'] < 0 else None))

            # label centered in the STRAIGHT part of the body (the nose
            # tapers, so text there would clip); this is the same width
            # budget the autosize above grows the body to satisfy
            cx, cy = rot(x, y)
            font_pts = self._port_label_font_data(port) * ppdu
            # with autosize OFF the body no longer grows for the label, so
            # a long one shrinks instead of spilling over the outline
            n_chars = max(len(port['label']), 1)
            font_pts = min(font_pts, PORT_LABEL_FILL * w * ppdu
                           / (PORT_LABEL_ADVANCE * n_chars))
            self._draw_glyph_label(ax, port['label'], cx, cy, font_pts, ppdu,
                                   rotation=self._readable_angle(angle))

        for line in self.line_resonators:
            lx, ly, w, h, rx = self._line_geometry(line)
            angle = line.get('angle', 0.0)
            selected = line in self.selected_lines
            stroke = line.get('color', 'black')
            fill = line.get('fill', '#cccccc')
            lw = float(line.get('linewidth', LINE_LINEWIDTH))

            # glyph rotation: draw axis-aligned, then rotate every artist
            # about the glyph center
            glyph_tf = (mtransforms.Affine2D().rotate_deg_around(lx, ly, angle)
                        + ax.transData)

            # selection indicator: salmon halo around the cylinder, matching
            # the node/edge selection language
            if selected:
                hh = max(1.6 * h, 0.5 * r)
                halo = mpatches.Rectangle(
                    (lx - w - rx - LINE_LEAD_LEN * r, ly - hh),
                    2 * (w + rx + LINE_LEAD_LEN * r), 2 * hh, fill=False,
                    edgecolor='salmon', linewidth=5.0, zorder=9.5,
                    transform=glyph_tf)
                ax.add_patch(halo)

            # slender coax cylinder (diagrammer reference art): gray body,
            # closed rounded cap on the left, open elliptical mouth on the
            # right, terminal stubs on both ends
            body = mpatches.Rectangle(
                (lx - w, ly - h), 2 * w, 2 * h, facecolor=fill,
                edgecolor='none', zorder=10, transform=glyph_tf)
            ax.add_patch(body)
            left_fill = mpatches.Ellipse(
                (lx - w, ly), 2 * rx, 2 * h, facecolor=fill,
                edgecolor='none', zorder=10, transform=glyph_tf)
            ax.add_patch(left_fill)
            left_arc = mpatches.Arc(
                (lx - w, ly), 2 * rx, 2 * h, theta1=90, theta2=270,
                edgecolor=stroke, linewidth=lw, zorder=11,
                transform=glyph_tf)
            ax.add_patch(left_arc)
            mouth = mpatches.Ellipse(
                (lx + w, ly), 2 * rx, 2 * h, facecolor='white',
                edgecolor=stroke, linewidth=lw, zorder=11,
                transform=glyph_tf)
            ax.add_patch(mouth)
            for seg in ((lx - w, ly - h, lx + w, ly - h),
                        (lx - w, ly + h, lx + w, ly + h)):
                ax.add_line(mlines.Line2D([seg[0], seg[2]], [seg[1], seg[3]],
                                          color=stroke, linewidth=lw,
                                          zorder=11, transform=glyph_tf))
            # terminal stubs centered on both ends
            for x0, x1 in ((lx - w - rx - LINE_LEAD_LEN * r, lx - w - rx),
                           (lx + w + rx, lx + w + rx + LINE_LEAD_LEN * r)):
                ax.add_line(mlines.Line2D([x0, x1], [ly, ly],
                                          color=stroke, linewidth=lw,
                                          zorder=11, transform=glyph_tf))

            # end leads: open (hollow), terminated (filled + wire to the
            # port glyph), or pending a connection (blue)
            pend = self._attach_pending_line_end
            for end_name, (ex, ey) in self._line_end_points(line).items():
                conn_ports = self._line_end_ports(line, end_name)
                is_pending = bool(pend and pend[0] is line
                                  and pend[1] == end_name)
                for conn_port in conn_ports:
                    pts = self._line_end_port_wire(line, end_name, conn_port)
                    conn = next(
                        (c for c in self._end_conns(line, end_name)
                         if c.get('kind') == 'port'
                         and c.get('port_id') == conn_port['port_id']), {})
                    wire_color, lw = self.wire_style(conn)
                    self._draw_wire(ax, pts, wire_color, lw, zorder=4)
                    self._draw_wire_label(ax, pts, conn, ppdu, wire_color)
                # node taps at this end: thin solid wires with an n_ref tag
                tap_conns = [cn for cn in self._end_conns(line, end_name)
                             if cn.get('kind') == 'node']
                for conn in tap_conns:
                    pts = self._tap_wire(line, end_name, conn, node_by_id)
                    if pts is None:
                        continue
                    tap_selected = ((line, end_name, conn)
                                    in self.selected_taps)
                    tap_color, lw = self.wire_style(conn, WIRE_COLOR_TAP)
                    self._draw_wire(ax, pts, tap_color, lw,
                                    selected=tap_selected, zorder=4)
                    self._draw_wire_label(
                        ax, pts, conn, ppdu, tap_color,
                        fallback=f"n={conn.get('n_ref', 1)}")

                connected = bool(conn_ports or tap_conns
                                 or self._end_is_pumped(line, end_name))
                mark = ('dodgerblue' if is_pending
                        else 'black' if connected else 'darkgray')
                ax.add_patch(mpatches.Circle(
                    (ex, ey), 0.12 * r,
                    facecolor=(mark if connected or is_pending else 'white'),
                    edgecolor=mark, linewidth=1.6, zorder=11.5))

            # label: inside the body when it is tall enough, else floated
            # above; node-style bold sans-serif either way
            if 2 * h >= 0.85 * r:
                tx, ty = lx, ly
                font_pts = min(2 * h, 1.1 * r) * ppdu * label_font_scale * 1.6
            else:
                tx, ty = _rotate_point(lx, ly + h + 0.45 * r, lx, ly, angle)
                font_pts = 0.9 * r * ppdu * label_font_scale * 1.6
            self._draw_glyph_label(ax, line['label'], tx, ty, font_pts, ppdu,
                                   rotation=self._readable_angle(angle))

            n_pairs = LineResonator(**line_payload(line)).N
            sub = f"FSR={line['FSR']:g}, N={n_pairs}"
            terminated = [e for e in ('x0', 'xL')
                          if self._line_end_ports(line, e)]
            if terminated:
                sub += ", port@" + "+".join(terminated)
            if line.get('pump'):
                sub += f", pump@{line['pump']['end']}"
            primary = self.line_primary(line)
            if primary is not None:
                sub = f"conjugate twin of {primary['label']}  (" + sub + ")"
            sy_off = max(h, 0.3 * r) + 0.35 * r
            sx, sy = _rotate_point(lx, ly - sy_off, lx, ly, angle)
            ax.text(sx, sy, sub, ha='center', va='top',
                    rotation=self._readable_angle(angle),
                    rotation_mode='anchor',
                    fontsize=7, color='dimgray', zorder=12)

        # pump buses: ONE double-line wire per rank-one parametric block,
        # from the pumped end of a line into the same end of its conjugate
        # twin (the edge crosses sectors, which is what the double line has
        # always meant for ordinary edges)
        for line in self.line_resonators:
            pts = self._pump_bus_wire(line)
            if pts is None:
                continue
            pump = line['pump']
            selected = line in getattr(self, 'selected_pump_buses', [])
            color, lw = self.wire_style(pump, PUMP_BUS_COLOR)
            outer = max(3.0 * lw, lw + 2.4)
            self._draw_wire(ax, pts, color, outer, selected=selected,
                            zorder=4)
            ax.add_line(mlines.Line2D(
                pts[:, 0], pts[:, 1], color='white', linewidth=outer - 2.0 * lw,
                zorder=4.1, solid_capstyle='butt'))
            n_ref, m_ref = self._pump_reference_pair(line)
            self._draw_wire_label(
                ax, pts, pump, ppdu, color,
                fallback=f"f_p={pump['f_p']:g}  ({n_ref},{m_ref})")

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
                    'angle_pinned': bool(p.get('angle_pinned', False)),
                    'monitored': p['monitored'],
                    'w_mult': p.get('w_mult', 1.0),
                    'h_mult': p.get('h_mult', 1.0),
                    'linewidth': p.get('linewidth', PORT_LINEWIDTH),
                    'color': p.get('color', 'black'),
                    'fill': p.get('fill', 'white'),
                    'attachments': [
                        {k: v for k, v in a.items()
                         if k in ('node_id', 'rate', 'sign', 'color',
                                  'linewidth_mult', 'label',
                                  'label_size_mult')}
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
                    'w_mult': l.get('w_mult', 1.0),
                    'h_mult': l.get('h_mult', 1.0),
                    'linewidth': l.get('linewidth', LINE_LINEWIDTH),
                    'color': l.get('color', 'black'),
                    'fill': l.get('fill', '#cccccc'),
                    'FSR': l['FSR'],
                    'Ztx': l['Ztx'],
                    'f_max': l['f_max'],
                    'ends': {e: [dict(c) for c
                                 in ExplicitPortsMixin._end_conns(l, e)]
                             for e in ('x0', 'xL')},
                    'end_coupling': dict(l.get('end_coupling')
                                         or {'x0': 'capacitive',
                                             'xL': 'capacitive'}),
                    'port_end': l.get('port_end'),   # legacy, read on load
                    'Z0_port': l.get('Z0_port', 50.0),
                    'alpha_uniform': l.get('alpha_uniform', 0.0),
                    'pump': (dict(l['pump']) if l.get('pump') else None),
                    'conj': bool(l.get('conj', False)),
                    'twin_of': l.get('twin_of'),
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
        self.selected_attachments = []
        self.selected_taps = []
        self.selected_pump_buses = []
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
                att = {'node_id': a['node_id'],
                       'rate': float(a.get('rate', 0.1)),
                       'sign': 1 if a.get('sign', 1) >= 0 else -1}
                for key in ('color', 'label'):
                    if a.get(key):
                        att[key] = a[key]
                for key in ('linewidth_mult', 'label_size_mult'):
                    if a.get(key) is not None:
                        att[key] = float(a[key])
                attachments.append(att)
            port = {
                'port_id': int(pdata['port_id']),
                'label': pdata.get('label', f"P{pdata['port_id']}"),
                'pos': tuple(pdata.get('pos', (0.0, 0.0))),
                'angle': float(pdata.get('angle', 0.0)),
                'angle_pinned': bool(pdata.get('angle_pinned', False)),
                'monitored': bool(pdata.get('monitored', True)),
                'w_mult': float(pdata.get('w_mult', 1.0)),
                'h_mult': float(pdata.get('h_mult', 1.0)),
                'linewidth': float(pdata.get('linewidth', PORT_LINEWIDTH)),
                'color': pdata.get('color', 'black'),
                'fill': pdata.get('fill', 'white'),
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
                'w_mult': float(ldata.get('w_mult', 1.0)),
                'h_mult': float(ldata.get('h_mult', 1.0)),
                'linewidth': float(ldata.get('linewidth', LINE_LINEWIDTH)),
                'color': ldata.get('color', 'black'),
                'fill': ldata.get('fill', '#cccccc'),
                'FSR': float(ldata['FSR']),
                'Ztx': float(ldata['Ztx']),
                'f_max': float(ldata['f_max']),
                'ends': {e: [dict(c) for c in
                             ExplicitPortsMixin._end_conns(ldata, e)]
                         for e in ('x0', 'xL')},
                'end_coupling': dict(ldata.get('end_coupling')
                                     or {'x0': 'capacitive',
                                         'xL': 'capacitive'}),
                'port_end': ldata.get('port_end'),
                'Z0_port': float(ldata.get('Z0_port', 50.0)),
                'alpha_uniform': float(ldata.get('alpha_uniform', 0.0)),
                'pump': (dict(ldata['pump']) if ldata.get('pump') else None),
                'conj': bool(ldata.get('conj', False)),
                'twin_of': ldata.get('twin_of'),
            }
            self.line_resonators.append(line)
            max_line_id = max(max_line_id, line['line_id'])
        self.line_id_counter = max_line_id + 1

        # pump/twin invariants: a pump needs its twin and a twin its
        # primary; anything dangling is dropped rather than half-restored
        known_line_ids = {l['line_id'] for l in self.line_resonators}
        for line in list(self.line_resonators):
            pump = line.get('pump')
            if pump and pump.get('twin_id') not in known_line_ids:
                logger.warning("Dropping pump of line %r: twin missing",
                               line['label'])
                line['pump'] = None
            if line.get('twin_of') is not None \
                    and line['twin_of'] not in known_line_ids:
                logger.warning("Dropping orphan twin %r", line['label'])
                self.line_resonators.remove(line)
        self._sync_all_twins()

        # Migration: files written before explicit line-end connections
        # carry only 'port_end'. Materialize the implied port as a real,
        # visible glyph wired to that end, so old graphs open with the same
        # physics and the new, editable topology.
        known_port_ids = {p['port_id'] for p in self.ports}
        for line in self.line_resonators:
            ends = line['ends']
            for end in ('x0', 'xL'):
                ends[end] = [
                    c for c in ends.get(end, [])
                    if (c.get('kind') == 'node'
                        and c.get('node_id') in known_node_ids)
                    or (c.get('kind') != 'node'
                        and c.get('port_id') in known_port_ids)]
            legacy_end = line.get('port_end')
            if legacy_end in ('x0', 'xL') and not any(ends.values()):
                offset = self._default_port_offset_for_line(line)
                px = line['pos'][0] + (offset if legacy_end == 'xL' else -offset)
                port = self.add_port(label=line['label'],
                                     pos=(px, line['pos'][1]), monitored=True)
                if legacy_end == 'xL':
                    port['angle'] = 180.0
                    port['angle_pinned'] = True
                self.connect_line_end_to_port(line, legacy_end, port)
                logger.info("Migrated implied port of line %r to an explicit "
                            "port glyph", line['label'])

        if self._has_explicit_port_objects():
            self._auto_enable_explicit_ports(source_name)
