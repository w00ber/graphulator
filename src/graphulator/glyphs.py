"""Schematic glyphs for Graphulator: ports, transmission lines, wiring.

Graphulator draws coupled-mode graphs -- nodes and edges. A diagram usually
needs two more things that are not modes: somewhere for a signal to enter or
leave (a **port**), and a length of line between two parts of the drawing (a
**transmission line**, ``txline`` in code). Paragraphulator grew these glyphs
first, as the *visible* face of its hub/transmission-line physics. Here they
are purely diagrammatic: Graphulator has no extractor, so a port is a port
and nothing is computed from it. That is deliberate -- it keeps the glyph
vocabulary, the curvy wiring and the auto-orientation identical across the
two apps while leaving the numerics where they belong.

Shapes and wire routing live in :mod:`graphulator.graph_primitives` (the
``port`` / ``txline`` / ``wire`` primitives), so what the canvas shows and
what an exported script draws come from the same code.

Data shapes (GUI-side; the drawing-side arguments are in graph_primitives):

    port = {
        'port_id': int,           # unique within the graph
        'label': str,
        'pos': (x, y),
        'angle': float,               # degrees CCW
        'angle_pinned': bool,         # True -> manual angle; False -> auto
        'w_mult': float, 'h_mult': float,
        'linewidth': float, 'color': str, 'fill': str,
        'label_color': str, 'label_size_mult': float,
        'labelnudge': (dx, dy),
        'connections': [              # wires out of this port's lead
            {'kind': 'node', 'node_id': int, ...style...},
            ...
        ],
    }

    txline = {
        'txline_id': int,
        'label': str,
        'pos': (x, y),
        'angle': float,
        'w_mult': float, 'h_mult': float,   # length / height
        'linewidth': float, 'color': str, 'fill': str,
        'label_color': str, 'label_size_mult': float,
        'labelnudge': (dx, dy),
        'ends': {'x0': [conn, ...], 'xL': [conn, ...]},
    }

    conn = {'kind': 'node'|'port', 'node_id'|'port_id': int,
            'color': None|str, 'linewidth_mult': float,
            'label': str, 'label_size_mult': float}

A wire always leaves a lead tip COLINEAR with the lead and lands on its
target along the target's own normal, so a fan out of one port collimates
through the lead before spreading. An **auto-orienting** port
(``angle_pinned`` False, the default) aims its lead at the centroid of
whatever it is wired to, which is what makes a dragged node pull its port
around to face it. Rotating a port by hand pins it; the Properties panel
and the right-click menu both toggle that back.
"""

import copy
import logging

import matplotlib.lines as mlines
import matplotlib.patches as mpatches
import matplotlib.transforms as mtransforms
import numpy as np
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from . import graph_primitives as gp
from .code_export import Call
from .graph_primitives import (
    GLYPH_LABEL_ADVANCE,
    GLYPH_LABEL_FILL,
    PORT_APEX_W,
    PORT_BODY_H,
    PORT_BODY_W,
    PORT_LW,
    TXLINE_BODY_H,
    TXLINE_BODY_W,
    TXLINE_LEAD_LEN,
    TXLINE_LW,
    WIRE_COLOR,
    WIRE_LW,
    rotatepoint,
)

logger = logging.getLogger(__name__)

#: Length/height multiplier limits for the arrow-key stretch.
GLYPH_SIZE_MIN, GLYPH_SIZE_MAX = 0.3, 4.0

#: Step per keystroke for the stretch (arrow keys) and the label size.
GLYPH_SIZE_STEP = 0.1
GLYPH_LABEL_SIZE_STEP = 0.1

#: Label-size multiplier limits.
GLYPH_LABEL_SIZE_MIN, GLYPH_LABEL_SIZE_MAX = 0.2, 3.0

#: Grab radius of a txline end handle, in node radii. The dot is drawn at
#: 0.12 R; a handle you have to hit that precisely is unusable, so the
#: catchment is roughly the whole stub.
TXLINE_END_GRAB = 0.7

#: Line styles offered for a wire, panel label -> matplotlib style.
WIRE_LINESTYLES = {'Solid': '-', 'Dashed': '--', 'Dotted': ':',
                   'Dash-dot': '-.'}

#: Node-label font scale, matching _draw_nodes (35 % of the node diameter).
GLYPH_LABEL_FONT_SCALE = 0.35


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------

def _color_button(initial, parent=None):
    """Small swatch button opening a QColorDialog; ``.color()`` reads it."""
    btn = QPushButton(parent)
    btn.setFixedSize(46, 22)

    def _apply(name):
        btn._color = name
        btn.setStyleSheet(f"background-color: {name}; border: 1px solid #888;")

    def _pick():
        col = QColorDialog.getColor(QColor(btn._color), btn.window())
        if col.isValid():
            _apply(col.name())

    btn.clicked.connect(_pick)
    btn.color = lambda: btn._color
    _apply(initial)
    return btn


def _mult_spin(value, tooltip='', lo=GLYPH_SIZE_MIN, hi=GLYPH_SIZE_MAX):
    box = QDoubleSpinBox()
    box.setRange(lo, hi)
    box.setDecimals(2)
    box.setSingleStep(0.1)
    box.setValue(float(value))
    if tooltip:
        box.setToolTip(tooltip)
    return box


def _add_appearance_rows(form, obj, default_lw, default_fill):
    """Length/height/stroke/color rows shared by both glyph dialogs.

    Returns the widget dict; read it back with :func:`_appearance_result`.
    """
    widgets = {}
    widgets['w_mult'] = _mult_spin(
        obj.get('w_mult', 1.0),
        "Stretch the glyph length (× default; ←/→ when selected)")
    form.addRow("Length ×:", widgets['w_mult'])
    widgets['h_mult'] = _mult_spin(
        obj.get('h_mult', 1.0),
        "Stretch the glyph height (× default; ↑/↓ when selected)")
    form.addRow("Height ×:", widgets['h_mult'])
    widgets['label_size_mult'] = _mult_spin(
        obj.get('label_size_mult', 1.0),
        "Label size (× default; Ctrl+↑/Ctrl+↓ when selected)",
        lo=GLYPH_LABEL_SIZE_MIN, hi=GLYPH_LABEL_SIZE_MAX)
    form.addRow("Label size ×:", widgets['label_size_mult'])
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
    widgets['label_color'] = _color_button(obj.get('label_color', 'black'))
    form.addRow("Label color:", widgets['label_color'])
    return widgets


def _appearance_result(widgets):
    return {'w_mult': widgets['w_mult'].value(),
            'h_mult': widgets['h_mult'].value(),
            'label_size_mult': widgets['label_size_mult'].value(),
            'linewidth': widgets['linewidth'].value(),
            'color': widgets['color'].color(),
            'fill': widgets['fill'].color(),
            'label_color': widgets['label_color'].color()}


class PortInputDialog(QDialog):
    """Label, orientation and appearance of a (new or edited) port."""

    def __init__(self, default_label='P1', parent=None, editing=False,
                 port=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Port" if editing else "Place Port")
        port = port or {}
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.label_edit = QLineEdit(default_label)
        form.addRow("Label:", self.label_edit)
        self.auto_orient_check = QCheckBox("Auto-orient toward wired group")
        self.auto_orient_check.setChecked(
            not port.get('angle_pinned', False))
        self.auto_orient_check.setToolTip(
            "Checked: the lead points at the center of whatever this "
            "port is wired to.\nUnchecked: the rotation is fixed — "
            "set it with Ctrl+← / Ctrl+→ (which also fixes it).")
        form.addRow(self.auto_orient_check)
        self.appearance = _add_appearance_rows(form, port, PORT_LW,
                                               'white')
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok
                                   | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.label_edit.setFocus()
        self.label_edit.selectAll()

    def get_result(self):
        result = {'label': self.label_edit.text().strip(),
                  'auto_orient': self.auto_orient_check.isChecked()}
        result.update(_appearance_result(self.appearance))
        return result


class TxLineInputDialog(QDialog):
    """Label and appearance of a (new or edited) txline."""

    def __init__(self, default_label='TL1', parent=None, editing=False,
                 txline=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Transmission Line" if editing else "Place Transmission Line")
        txline = txline or {}
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.label_edit = QLineEdit(default_label)
        form.addRow("Label:", self.label_edit)
        angle = QDoubleSpinBox()
        angle.setRange(-360.0, 360.0)
        angle.setDecimals(1)
        angle.setSingleStep(15.0)
        angle.setSuffix("°")
        angle.setValue(float(txline.get('angle', 0.0)))
        self.angle_spin = angle
        form.addRow("Angle:", angle)
        self.appearance = _add_appearance_rows(form, txline, TXLINE_LW, '#cccccc')
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok
                                   | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.label_edit.setFocus()
        self.label_edit.selectAll()

    def get_result(self):
        result = {'label': self.label_edit.text().strip(),
                  'angle': self.angle_spin.value()}
        result.update(_appearance_result(self.appearance))
        return result


# ---------------------------------------------------------------------------
# The mixin
# ---------------------------------------------------------------------------

class GlyphMixin:
    """Port/txline glyphs, their wiring, and the interactions on them.

    Mixed into the main window ahead of ``GraphWindowCommonMixin`` so the
    overrides here (``_select_all``, ``_rotate_selected_nodes``,
    ``_compute_best_selfloop_angle``'s avoid-list hook) win.
    """

    # ---- state ----

    def _init_glyph_state(self):
        self.ports = []
        self.txlines = []
        self.port_id_counter = 0
        self.txline_id_counter = 0
        self.port_counter = 0
        self.txline_counter = 0

        self.selected_ports = []
        self.selected_txlines = []
        self.selected_wires = []      # [(owner, conn)], owner = port|txline

        # drag-to-move
        self._glyph_drag_pending = None    # (kind, obj)
        self._glyph_dragging = None
        self._glyph_drag_start = None
        self._glyph_drag_preview = None

        # drag ONE end of a txline (stretch + aim it, other end held fixed)
        self._txline_end_drag_pending = None   # (txline, end)
        self._txline_end_dragging = None
        self._txline_end_drag_preview = []

        # wiring: the lead a pending wire starts from
        self._wire_pending = None          # ('port', t) | ('txline', c, end)

        # last-used appearance, so a run of glyphs comes out consistent
        self.last_port_props = None
        self.last_txline_props = None

    @property
    def _has_glyphs(self):
        return bool(self.ports or self.txlines)

    # ---- creation / removal ----

    def _next_glyph_label(self, prefix, counter_attr):
        n = getattr(self, counter_attr, 0) + 1
        return f"{prefix}{n}"

    def add_port(self, label=None, pos=(0.0, 0.0), angle=0.0, **props):
        """Add a port glyph and return it."""
        self.port_counter += 1
        term = {
            'port_id': self.port_id_counter,
            'label': (label if label is not None
                      else f"P{self.port_counter}"),
            'pos': tuple(pos),
            'angle': float(angle),
            'angle_pinned': False,
            'w_mult': 1.0,
            'h_mult': 1.0,
            'linewidth': PORT_LW,
            'color': 'black',
            'fill': 'white',
            'label_color': 'black',
            'label_size_mult': 1.0,
            'labelnudge': (0.0, 0.0),
            'connections': [],
        }
        term.update(props)
        self.port_id_counter += 1
        self.ports.append(term)
        return term

    def add_txline(self, label=None, pos=(0.0, 0.0), angle=0.0, **props):
        """Add a txline glyph and return it."""
        self.txline_counter += 1
        cx = {
            'txline_id': self.txline_id_counter,
            'label': (label if label is not None
                      else f"TL{self.txline_counter}"),
            'pos': tuple(pos),
            'angle': float(angle),
            'w_mult': 1.0,
            'h_mult': 1.0,
            'linewidth': TXLINE_LW,
            'color': 'black',
            'fill': '#cccccc',
            'label_color': 'black',
            'label_size_mult': 1.0,
            'labelnudge': (0.0, 0.0),
            'ends': {'x0': [], 'xL': []},
        }
        cx.update(props)
        self.txline_id_counter += 1
        self.txlines.append(cx)
        return cx

    @staticmethod
    def _default_wire_conn(**kw):
        conn = {'color': None, 'linewidth_mult': 1.25, 'linestyle': '-',
                'label': '', 'label_size_mult': 1.0}
        conn.update(kw)
        return conn

    def connect_port_to_node(self, port, node):
        """Wire a port's lead to a node. Returns the conn."""
        conn = self._default_wire_conn(kind='node', node_id=node['node_id'])
        port['connections'].append(conn)
        return conn

    def connect_port_to_txline(self, port, txline, end):
        """Wire a port's lead to one end of a txline.

        The conn is recorded on the TXLINE, so a wire always has exactly one
        owner however it was drawn (either lead traces the same curve).
        """
        conn = self._default_wire_conn(kind='port',
                                       port_id=port['port_id'])
        txline['ends'][end].append(conn)
        return conn

    def connect_txline_end(self, txline, end, target):
        """Wire one txline end to a node or a port. Returns the conn."""
        if 'node_id' in target:
            conn = self._default_wire_conn(kind='node',
                                           node_id=target['node_id'])
        else:
            conn = self._default_wire_conn(
                kind='port', port_id=target['port_id'])
        txline['ends'][end].append(conn)
        return conn

    def remove_port(self, port):
        """Remove a port and every wire that referenced it."""
        if port in self.ports:
            self.ports.remove(port)
        if port in self.selected_ports:
            self.selected_ports.remove(port)
        tid = port['port_id']
        for cx in self.txlines:
            for end in ('x0', 'xL'):
                cx['ends'][end] = [c for c in cx['ends'][end]
                                   if not (c['kind'] == 'port'
                                           and c.get('port_id') == tid)]
        self.selected_wires = [(o, c) for o, c in self.selected_wires
                               if o is not port]

    def remove_txline(self, txline):
        """Remove a txline and its wiring."""
        if txline in self.txlines:
            self.txlines.remove(txline)
        if txline in self.selected_txlines:
            self.selected_txlines.remove(txline)
        self.selected_wires = [(o, c) for o, c in self.selected_wires
                               if o is not txline]

    def _drop_glyph_wires_for_node(self, node_id):
        """Drop every wire that pointed at a node being deleted."""
        for term in self.ports:
            term['connections'] = [c for c in term['connections']
                                   if not (c['kind'] == 'node'
                                           and c.get('node_id') == node_id)]
        for cx in self.txlines:
            for end in ('x0', 'xL'):
                cx['ends'][end] = [c for c in cx['ends'][end]
                                   if not (c['kind'] == 'node'
                                           and c.get('node_id') == node_id)]

    # ---- geometry ----

    def _port_geometry(self, port):
        """(x, y, w, h, apex_x) in UNROTATED data units."""
        return gp.portgeometry(port['pos'], self.node_radius,
                                   port.get('w_mult', 1.0),
                                   port.get('h_mult', 1.0))

    def _port_effective_angle(self, port):
        """Drawing/hit-test angle of a port.

        An unpinned port aims its lead at the CENTROID of everything it
        is wired to (a cluster therefore pulls proportionally, which a mean
        of unit directions would not). Pinned or unwired, it uses the stored
        angle.
        """
        if port.get('angle_pinned'):
            return port.get('angle', 0.0)
        targets = self._port_wire_targets(port)
        if not targets:
            return port.get('angle', 0.0)
        px, py = port['pos']
        cx = sum(t[0] for t in targets) / len(targets)
        cy = sum(t[1] for t in targets) / len(targets)
        vx, vy = cx - px, cy - py
        if abs(vx) < 1e-12 and abs(vy) < 1e-12:
            return port.get('angle', 0.0)
        return float(np.degrees(np.arctan2(vy, vx)))

    def _port_wire_targets(self, port):
        """Positions this port is wired to (nodes, and txline ends)."""
        node_pos = {n['node_id']: n['pos'] for n in self.nodes}
        targets = [node_pos[c['node_id']] for c in port['connections']
                   if c['kind'] == 'node' and c['node_id'] in node_pos]
        tid = port['port_id']
        for cx in self.txlines:
            for end in ('x0', 'xL'):
                if any(c['kind'] == 'port'
                       and c.get('port_id') == tid
                       for c in cx['ends'][end]):
                    targets.append(self._txline_end_points(cx)[end])
        return targets

    def _port_apex(self, port):
        """The point of the pentagon: where a wire visibly leaves."""
        pt, _ = gp.portapex(port['pos'], self.node_radius,
                                   self._port_effective_angle(port),
                                   port.get('w_mult', 1.0),
                                   port.get('h_mult', 1.0))
        return pt

    def _port_wire_start(self, port):
        """(anchor point, outward unit tangent) of a port.

        The anchor is buried inside the filled body, so the wire's end cap
        is hidden by the polygon and the visible line starts at the apex.
        """
        pt, tan = gp.portwirestart(
            port['pos'], self.node_radius,
            self._port_effective_angle(port),
            port.get('w_mult', 1.0), port.get('h_mult', 1.0))
        return np.asarray(pt, dtype=float), np.asarray(tan, dtype=float)

    def _txline_geometry(self, txline):
        """(x, y, w, h, rx) in UNROTATED data units."""
        return gp.txlinegeometry(txline['pos'], self.node_radius,
                               txline.get('w_mult', 1.0),
                               txline.get('h_mult', 1.0))

    def _txline_end_points(self, txline):
        """{'x0': (x, y), 'xL': (x, y)}: rotated stub tips."""
        ends = gp.txlineendpoints(txline['pos'], self.node_radius,
                                txline.get('angle', 0.0),
                                txline.get('w_mult', 1.0),
                                txline.get('h_mult', 1.0))
        return {k: v[0] for k, v in ends.items()}

    def set_txline_end(self, txline, end, point):
        """Move one END of a txline to `point`, holding the other end fixed.

        The glyph is stored as center + angle + length, so dragging an end
        has to solve for all three: the axis becomes the line from the
        fixed end to `point`, the length becomes their separation minus the
        two stubs, and the center lands where it puts the FIXED end back
        exactly where it was. Solving for the center last is what keeps the
        anchored end still even when the length hits its clamp.
        """
        r = self.node_radius
        ends = self._txline_end_points(txline)
        fixed = np.asarray(ends['xL' if end == 'x0' else 'x0'], dtype=float)
        moving = np.asarray(point, dtype=float)
        span = moving - fixed
        total = float(np.hypot(*span))

        _, _, _, h, rx = self._txline_geometry(txline)
        stub = rx + TXLINE_LEAD_LEN * r          # fixed, independent of length
        half_body = total / 2.0 - stub
        txline['w_mult'] = float(np.clip(half_body / (TXLINE_BODY_W * r),
                                         GLYPH_SIZE_MIN, GLYPH_SIZE_MAX))

        if total > 1e-9:
            # the glyph's own axis runs x0 -> xL
            axis = span if end == 'xL' else -span
            txline['angle'] = float(
                np.degrees(np.arctan2(axis[1], axis[0]))) % 360.0

        theta = np.radians(txline['angle'])
        u = np.array([np.cos(theta), np.sin(theta)])
        half = TXLINE_BODY_W * r * txline['w_mult'] + stub
        center = fixed + half * u if end == 'xL' else fixed - half * u
        txline['pos'] = (float(center[0]), float(center[1]))
        return txline

    def _txline_end_wire_start(self, txline, end):
        """(stub-tip point, outward unit tangent) of one txline end."""
        ends = gp.txlineendpoints(txline['pos'], self.node_radius,
                                txline.get('angle', 0.0),
                                txline.get('w_mult', 1.0),
                                txline.get('h_mult', 1.0))
        pt, tan = ends[end]
        return np.asarray(pt, dtype=float), np.asarray(tan, dtype=float)

    def _node_wire_end(self, node, toward):
        """(entry point on the node circle, arrival unit tangent)."""
        radius = self.node_radius * node.get('node_size_mult', 1.0)
        pt, tan = gp.nodewireend(node['pos'], radius, toward)
        return np.asarray(pt, dtype=float), np.asarray(tan, dtype=float)

    # ---- wire routing ----

    def _glyph_wire_points(self, p0, t0, p1, t1, samples=33):
        return gp.wirepoints(p0, t0, p1, t1, R=self.node_radius,
                             samples=samples)

    def _wire_for(self, owner, conn, end=None, node_by_id=None):
        """Sampled points of one wire, or None when its target is gone.

        `owner` is the port or txline the wire leaves; `end` names the
        txline end when the owner is a txline.
        """
        nodes = (node_by_id if node_by_id is not None
                 else {n['node_id']: n for n in self.nodes})
        if end is None:
            p0, t0 = self._port_wire_start(owner)
        else:
            p0, t0 = self._txline_end_wire_start(owner, end)

        if conn['kind'] == 'node':
            node = nodes.get(conn.get('node_id'))
            if node is None:
                return None
            p1, t1 = self._node_wire_end(node, p0)
        else:
            term = self._port_by_id(conn.get('port_id'))
            if term is None:
                return None
            p1, t_out = self._port_wire_start(term)
            t1 = -t_out       # arrive travelling INTO the lead
        return self._glyph_wire_points(p0, t0, p1, t1)

    def _port_by_id(self, port_id):
        for term in self.ports:
            if term['port_id'] == port_id:
                return term
        return None

    def _iter_glyph_wires(self, node_by_id=None):
        """Yield (owner, end, conn, points) for every drawable wire."""
        nodes = (node_by_id if node_by_id is not None
                 else {n['node_id']: n for n in self.nodes})
        for term in self.ports:
            for conn in term['connections']:
                pts = self._wire_for(term, conn, node_by_id=nodes)
                if pts is not None:
                    yield term, None, conn, pts
        for cx in self.txlines:
            for end in ('x0', 'xL'):
                for conn in cx['ends'][end]:
                    pts = self._wire_for(cx, conn, end=end, node_by_id=nodes)
                    if pts is not None:
                        yield cx, end, conn, pts

    @staticmethod
    def wire_style(conn, default_color=WIRE_COLOR):
        """(color, linewidth, linestyle) of one wire, honoring the
        per-wire overrides."""
        color = conn.get('color') or default_color
        return (color,
                WIRE_LW * float(conn.get('linewidth_mult', 1.25)),
                conn.get('linestyle') or '-')

    # ---- hit testing ----

    def _find_port_at_position(self, x, y):
        if x is None or y is None:
            return None
        for term in reversed(self.ports):
            px, py, w, h, apex_x = self._port_geometry(term)
            ux, uy = rotatepoint(x, y, px, py,
                                 -self._port_effective_angle(term))
            if (px - w / 2 <= ux <= apex_x) and (py - h / 2 <= uy <= py + h / 2):
                return term
        return None

    def _find_txline_at_position(self, x, y):
        if x is None or y is None:
            return None
        r = self.node_radius
        for cx in reversed(self.txlines):
            lx, ly, w, h, rx = self._txline_geometry(cx)
            ux, uy = rotatepoint(x, y, lx, ly, -cx.get('angle', 0.0))
            # a slender txline is hard to grab, so the hit box has a floor
            hh = max(h, 0.35 * r)
            if (lx - w - rx <= ux <= lx + w + rx) and (ly - hh <= uy <= ly + hh):
                return cx
        return None

    def _find_txline_end_at_position(self, x, y, tol=None):
        """(txline, end) of the stub tip near (x, y), else None.

        This is the STRICT test -- "the pointer is on that end handle" --
        used to arm an end drag. The end dot is only 0.12 R across, so the
        grab radius is deliberately several times its drawn size.
        """
        if x is None or y is None:
            return None
        tol = tol if tol is not None else TXLINE_END_GRAB * self.node_radius
        best, best_d = None, tol
        for cx in reversed(self.txlines):
            for end, (ex, ey) in self._txline_end_points(cx).items():
                d = float(np.hypot(x - ex, y - ey))
                if d < best_d:
                    best, best_d = (cx, end), d
        return best

    def _txline_end_for_click(self, x, y):
        """(txline, end) for a click meant to WIRE a transmission line.

        A wire belongs to one END of a txline, but the end stub tips are
        tiny targets and the body between them is not -- so a click
        anywhere on the glyph resolves to whichever end it is nearer. That
        is also the only sensible reading: a txline is a two-terminal
        object, so "wire this line" always means one of its two terminals,
        never its center.
        """
        hit = self._find_txline_end_at_position(x, y)
        if hit is not None:
            return hit
        cx = self._find_txline_at_position(x, y)
        if cx is None:
            return None
        ends = self._txline_end_points(cx)
        end = min(ends, key=lambda e: np.hypot(x - ends[e][0],
                                               y - ends[e][1]))
        return cx, end

    def _find_glyph_wire_at_position(self, x, y, tol=None):
        """(owner, end, conn) of the wire near (x, y), else None."""
        if x is None or y is None:
            return None
        tol = tol if tol is not None else 0.35 * self.node_radius
        best, best_d = None, tol
        for owner, end, conn, pts in self._iter_glyph_wires():
            d = _dist_to_polyline(x, y, pts)
            if d < best_d:
                best, best_d = (owner, end, conn), d
        return best

    # ---- selection helpers ----

    def _clear_glyph_selection(self):
        self.selected_ports = []
        self.selected_txlines = []
        self.selected_wires = []

    def _selected_glyphs(self):
        return list(self.selected_ports) + list(self.selected_txlines)

    def _select_all(self):
        """Select everything, glyphs included.

        A "whole graph" selection that left the ports and txlines behind
        was most visible when rotating: the nodes turned and the glyphs
        stayed put.
        """
        super()._select_all()
        self.selected_ports = list(self.ports)
        self.selected_txlines = list(self.txlines)
        self._update_plot()

    def _shortcut_context(self):
        """Add a 'glyph' context for selected ports / txlines."""
        if (self._selected_glyphs() and not self.selected_nodes
                and not self.selected_edges):
            return 'glyph'
        return super()._shortcut_context()

    # ---- self-loop orientation ----

    def _selfloop_avoid_angles(self, node, exclude_edge=None):
        """Angles a self-loop on `node` should keep away from.

        Extends the base list (its edges) with the direction each glyph wire
        arrives from, so a self-loop does not auto-orient straight into a
        port's wire.
        """
        angles = super()._selfloop_avoid_angles(node, exclude_edge)
        node_id = node['node_id']
        cx, cy = node['pos']
        for owner, end, conn, pts in self._iter_glyph_wires():
            if conn['kind'] != 'node' or conn.get('node_id') != node_id:
                continue
            # the wire arrives at pts[-1]; approach direction from the
            # second-to-last sample keeps short wires honest
            ex, ey = pts[-1]
            angles.append(float(np.degrees(np.arctan2(ey - cy, ex - cx))) % 360)
        return angles

    # ---- keyboard: stretch, label size, nudge, rotate ----

    def _adjust_glyph_size(self, direction):
        """Arrow-key stretch for selected glyphs: Up/Down = height,
        Left/Right = length. Returns True when it consumed the key."""
        glyphs = self._selected_glyphs()
        if not glyphs:
            return False
        self._save_state()
        key = 'h_mult' if direction in ('up', 'down') else 'w_mult'
        sign = 1 if direction in ('up', 'right') else -1
        for g in glyphs:
            g[key] = float(np.clip(g.get(key, 1.0) + sign * GLYPH_SIZE_STEP,
                                   GLYPH_SIZE_MIN, GLYPH_SIZE_MAX))
        what = 'height' if key == 'h_mult' else 'length'
        logger.debug("Glyph %s: %s", what,
                     ", ".join(f"{g['label']}={g[key]:.2f}" for g in glyphs))
        self._update_plot()
        return True

    def _adjust_glyph_label_size(self, direction):
        """Ctrl+Up/Down: label size of the selected glyphs."""
        glyphs = self._selected_glyphs()
        if not glyphs:
            return False
        self._save_state()
        sign = 1 if direction == 'up' else -1
        for g in glyphs:
            g['label_size_mult'] = float(np.clip(
                g.get('label_size_mult', 1.0) + sign * GLYPH_LABEL_SIZE_STEP,
                GLYPH_LABEL_SIZE_MIN, GLYPH_LABEL_SIZE_MAX))
        self._update_plot()
        return True

    def _nudge_glyph_label(self, direction):
        """Shift+arrows: fine-tune the label position inside its glyph.

        The step follows the glyph's own size, so a stretched txline nudges in
        the same visual increments a small one does.
        """
        glyphs = self._selected_glyphs()
        if not glyphs:
            return False
        self._save_state()
        for g in glyphs:
            step = 0.04 * self.node_radius * max(g.get('h_mult', 1.0), 0.5)
            dx, dy = g.get('labelnudge', (0.0, 0.0))
            if direction == 'left':
                dx -= step
            elif direction == 'right':
                dx += step
            elif direction == 'up':
                dy += step
            elif direction == 'down':
                dy -= step
            g['labelnudge'] = (dx, dy)
        self._update_plot()
        return True

    def _rotate_glyph_in_place(self, direction):
        """Ctrl+Left/Right: spin the selected glyphs about their own centers.

        Rotating an auto-orienting port by hand PINS it (otherwise the
        next redraw would undo the rotation), starting from its current
        auto-orientation so the first step is a small visible nudge.
        """
        glyphs = self._selected_glyphs()
        if not glyphs:
            return False
        step = getattr(self.APP_CONFIG, 'GLYPH_ROTATION_INCREMENT', 15)
        delta = step if direction == 'left' else -step
        self._save_state()
        for g in glyphs:
            if 'port_id' in g:
                base = self._port_effective_angle(g)
                g['angle_pinned'] = True
                g['angle'] = (base + delta) % 360.0
            else:
                g['angle'] = (g.get('angle', 0.0) + delta) % 360.0
        self._update_plot()
        return True

    def _rotate_selected_nodes(self, angle_degrees):
        """Rotate the selection, glyphs included.

        With a SINGLE glyph selected, spin it in place (the useful primitive
        for aiming a lead). With two or more objects selected -- nodes,
        glyphs, or any mix -- the selection is a layout and rotates rigidly
        about its centroid, every glyph carrying its orientation along, so
        the drawing keeps its shape. An auto-orienting port is left
        UNpinned in a rigid rotation: whatever it is wired to moved too, so
        it re-aims itself correctly.
        """
        glyphs = self._selected_glyphs()
        if not glyphs:
            super()._rotate_selected_nodes(angle_degrees)
            return

        n_selected = len(glyphs) + len(self.selected_nodes)
        if n_selected > 1:
            if self.selected_nodes:
                # the node centroid, as the base class uses, so nodes and
                # glyphs share one pivot
                pivot = np.array([n['pos'] for n in self.selected_nodes]
                                 ).mean(axis=0)
                super()._rotate_selected_nodes(angle_degrees)
            else:
                pivot = np.array([g['pos'] for g in glyphs]).mean(axis=0)
                self._save_state()
            for g in glyphs:
                gx, gy = rotatepoint(g['pos'][0], g['pos'][1],
                                     pivot[0], pivot[1], -angle_degrees)
                g['pos'] = (gx, gy)
                if 'port_id' in g and not g.get('angle_pinned'):
                    continue      # auto-orient re-aims it for free
                g['angle'] = (g.get('angle', 0.0) - angle_degrees) % 360.0
            self._update_plot()
            return

        # a single glyph: spin it in place
        self._save_state()
        for g in glyphs:
            if 'port_id' in g:
                base = self._port_effective_angle(g)
                g['angle_pinned'] = True
                g['angle'] = (base - angle_degrees) % 360.0
            else:
                g['angle'] = (g.get('angle', 0.0) - angle_degrees) % 360.0
        self._update_plot()

    # ---- editing ----

    def _edit_port(self, port):
        dialog = PortInputDialog(default_label=port['label'],
                                     parent=self, editing=True,
                                     port=port)
        if dialog.exec() != QDialog.Accepted:
            return
        self._save_state()
        self._apply_port_style(port, dialog.get_result())
        self._update_plot()

    def _apply_port_style(self, port, result):
        for key in ('w_mult', 'h_mult', 'linewidth', 'color', 'fill',
                    'label_color', 'label_size_mult'):
            if key in result:
                port[key] = result[key]
        if 'label' in result:
            port['label'] = result['label']
        if 'auto_orient' in result:
            was_auto = not port.get('angle_pinned', False)
            pin = not result['auto_orient']
            if was_auto and pin:
                # Freeze at what is on SCREEN, not at the stale stored
                # angle. The effective angle has to be read BEFORE the pin
                # flag flips, or it reports the stored one right back.
                shown = self._port_effective_angle(port)
                port['angle'] = shown % 360.0
            port['angle_pinned'] = pin

    def _edit_txline(self, txline):
        dialog = TxLineInputDialog(default_label=txline['label'], parent=self,
                                 editing=True, txline=txline)
        if dialog.exec() != QDialog.Accepted:
            return
        self._save_state()
        result = dialog.get_result()
        for key in ('label', 'angle', 'w_mult', 'h_mult', 'linewidth',
                    'color', 'fill', 'label_color', 'label_size_mult'):
            if key in result:
                txline[key] = result[key]
        self._update_plot()

    # ---- placement modes ----

    def _toggle_port_mode(self):
        self.placement_mode = (None if self.placement_mode == 'port'
                               else 'port')
        self._exit_wire_pending()
        self._update_plot()

    def _toggle_port_continuous_mode(self):
        self.placement_mode = (
            None if self.placement_mode == 'port_continuous'
            else 'port_continuous')
        self._exit_wire_pending()
        self._update_plot()

    def _toggle_txline_mode(self):
        self.placement_mode = None if self.placement_mode == 'txline' else 'txline'
        self._exit_wire_pending()
        self._update_plot()

    def _exit_wire_pending(self):
        self._wire_pending = None

    def _on_click_port_placement(self, event):
        snap_x, snap_y = self._snap_to_grid(event.xdata, event.ydata)
        continuous = self.placement_mode == 'port_continuous'
        props = dict(self.last_port_props or {})
        if continuous and props:
            label = self._auto_increment_label(props.pop('label', 'P1'))
        else:
            dialog = PortInputDialog(
                default_label=f"P{self.port_counter + 1}", parent=self,
                port=self.last_port_props or {})
            if dialog.exec() != QDialog.Accepted:
                return
            result = dialog.get_result()
            label = result.pop('label', None) or f"P{self.port_counter + 1}"
            auto = result.pop('auto_orient', True)
            props = result
            props['angle_pinned'] = not auto
        self._save_state()
        term = self.add_port(label=label, pos=(snap_x, snap_y), **props)
        self.last_port_props = dict(props, label=label)
        logger.info("✓ Port '%s' placed at (%.3f, %.3f)",
                    term['label'], snap_x, snap_y)
        if self.placement_mode == 'port':
            self.placement_mode = None
        self._update_plot()

    def _on_click_txline_placement(self, event):
        snap_x, snap_y = self._snap_to_grid(event.xdata, event.ydata)
        dialog = TxLineInputDialog(default_label=f"TL{self.txline_counter + 1}",
                                 parent=self,
                                 txline=self.last_txline_props or {})
        if dialog.exec() != QDialog.Accepted:
            return
        result = dialog.get_result()
        label = result.pop('label', None) or f"TL{self.txline_counter + 1}"
        self._save_state()
        cx = self.add_txline(label=label, pos=(snap_x, snap_y), **result)
        self.last_txline_props = dict(result, label=label)
        logger.info("✓ Transmission line '%s' placed at (%.3f, %.3f)",
                    cx['label'], snap_x, snap_y)
        self.placement_mode = None
        self._update_plot()

    # ---- wiring with the edge tool ----

    def _maybe_handle_glyph_edge_click(self, event):
        """Edge-mode click that lands on a glyph: start or finish a wire.

        A wire always starts at a lead -- a port, or one end of a txline --
        and finishes on a node, a port, or a txline end, which is exactly
        the set of things a lead can physically reach.
        """
        if not self._has_glyphs:
            return False
        x, y = event.xdata, event.ydata

        if self._wire_pending is None:
            term = self._find_port_at_position(x, y)
            if term is not None:
                self._wire_pending = ('port', term)
                self._status_message(
                    f"Wire from port '{term['label']}' — click a "
                    "node, another port, or a txline end", 6000)
                self._update_plot()
                return True
            hit = self._txline_end_for_click(x, y)
            if hit is not None:
                cx, end = hit
                self._wire_pending = ('txline', cx, end)
                self._status_message(
                    f"Wire from txline '{cx['label']}' ({end}) — click a "
                    "node, a port, or another txline end", 6000)
                self._update_plot()
                return True
            return False

        # a wire is pending: try to land it
        target_node = self._find_node_at_position(x, y)
        target_term = (None if target_node is not None
                       else self._find_port_at_position(x, y))
        target_end = (None if (target_node is not None
                               or target_term is not None)
                      else self._txline_end_for_click(x, y))
        if target_node is None and target_term is None and target_end is None:
            return False

        pending = self._wire_pending
        self._wire_pending = None
        self._save_state()
        made = self._make_wire(pending, target_node, target_term, target_end)
        if made and self.placement_mode == 'edge':
            self.placement_mode = None
        self._update_plot()
        return True

    def _make_wire(self, pending, node=None, port=None, txline_end=None):
        """Create the pending wire onto whichever target was clicked."""
        if pending[0] == 'port':
            src = pending[1]
            if node is not None:
                if any(c['kind'] == 'node' and c['node_id'] == node['node_id']
                       for c in src['connections']):
                    logger.info("Port '%s' is already wired to '%s'",
                                src['label'], node['label'])
                    return False
                src['connections'].append(
                    self._default_wire_conn(kind='node',
                                            node_id=node['node_id']))
                logger.info("Wired port '%s' → node '%s'",
                            src['label'], node['label'])
                return True
            if port is not None and port is not src:
                # port-to-port: recorded on the TARGET so the wire
                # has one owner (either lead draws the same curve)
                port['connections'].append(
                    self._default_wire_conn(
                        kind='port', port_id=src['port_id']))
                logger.info("Wired port '%s' → port '%s'",
                            src['label'], port['label'])
                return True
            if txline_end is not None:
                cx, end = txline_end
                cx['ends'][end].append(
                    self._default_wire_conn(
                        kind='port', port_id=src['port_id']))
                logger.info("Wired port '%s' → txline '%s' (%s)",
                            src['label'], cx['label'], end)
                return True
            return False

        _, src_txline, src_end = pending
        if node is not None:
            src_txline['ends'][src_end].append(
                self._default_wire_conn(kind='node', node_id=node['node_id']))
            logger.info("Wired txline '%s' (%s) → node '%s'",
                        src_txline['label'], src_end, node['label'])
            return True
        if port is not None:
            src_txline['ends'][src_end].append(
                self._default_wire_conn(
                    kind='port', port_id=port['port_id']))
            logger.info("Wired txline '%s' (%s) → port '%s'",
                        src_txline['label'], src_end, port['label'])
            return True
        if txline_end is not None and txline_end[0] is not src_txline:
            # txline-to-txline needs a shared anchor; route it through the
            # target's end by giving it a node-free port-style conn is
            # not possible, so refuse rather than draw something misleading
            logger.info("Txline-to-txline wiring is not supported — place a "
                        "port between them")
            return False
        return False

    # ---- mouse: selection, drag, context menu ----

    def _maybe_handle_glyph_click(self, event, shift_pressed, is_double):
        """Normal-mode click on a glyph or wire. True when it consumed it."""
        if not self._has_glyphs:
            return False
        x, y = event.xdata, event.ydata

        term = self._find_port_at_position(x, y)
        if term is not None:
            if is_double:
                self._edit_port(term)
            elif shift_pressed:
                if term in self.selected_ports:
                    self.selected_ports.remove(term)
                else:
                    self.selected_ports.append(term)
            else:
                self._clear_glyph_selection()
                self.selected_ports = [term]
                self.selected_nodes.clear()
                self.selected_edges.clear()
                self._glyph_drag_pending = ('port', term)
                self._glyph_drag_start = (x, y)
            self._update_plot()
            return True

        # an END handle before the body: grabbing an end stretches and aims
        # the line, grabbing the body moves the whole glyph
        end_hit = self._find_txline_end_at_position(x, y)
        if end_hit is not None and not is_double and not shift_pressed:
            cx, end = end_hit
            self._clear_glyph_selection()
            self.selected_txlines = [cx]
            self.selected_nodes.clear()
            self.selected_edges.clear()
            self._txline_end_drag_pending = (cx, end)
            self._glyph_drag_start = (x, y)
            self._status_message(
                f"Dragging the {end} end of '{cx['label']}' \u2014 it snaps "
                "to the grid; the other end stays put", 4000)
            self._update_plot()
            return True

        cx = self._find_txline_at_position(x, y)
        if cx is not None:
            if is_double:
                self._edit_txline(cx)
            elif shift_pressed:
                if cx in self.selected_txlines:
                    self.selected_txlines.remove(cx)
                else:
                    self.selected_txlines.append(cx)
            else:
                self._clear_glyph_selection()
                self.selected_txlines = [cx]
                self.selected_nodes.clear()
                self.selected_edges.clear()
                self._glyph_drag_pending = ('txline', cx)
                self._glyph_drag_start = (x, y)
            self._update_plot()
            return True

        hit = self._find_glyph_wire_at_position(x, y)
        if hit is not None:
            owner, end, conn = hit
            if shift_pressed:
                pair = (owner, conn)
                if pair in self.selected_wires:
                    self.selected_wires.remove(pair)
                else:
                    self.selected_wires.append(pair)
            else:
                self._clear_glyph_selection()
                self.selected_wires = [(owner, conn)]
                self.selected_nodes.clear()
                self.selected_edges.clear()
            self._update_plot()
            return True

        if not shift_pressed and (self.selected_ports
                                  or self.selected_txlines
                                  or self.selected_wires):
            self._clear_glyph_selection()
        return False

    def _maybe_show_glyph_context_menu(self, event):
        """Right-click on a glyph or wire. True when it consumed it."""
        if not self._has_glyphs:
            return False
        from PySide6.QtGui import QCursor
        from PySide6.QtWidgets import QMenu

        step = getattr(self.APP_CONFIG, 'GLYPH_ROTATION_INCREMENT', 15)
        term = self._find_port_at_position(event.xdata, event.ydata)
        if term is not None:
            menu = QMenu(self)
            menu.addAction("Edit…", lambda: self._edit_port(term))
            menu.addAction(f"Rotate {step}° CCW",
                           lambda: self._rotate_one_glyph(term, step))
            menu.addAction(f"Rotate {step}° CW",
                           lambda: self._rotate_one_glyph(term, -step))
            menu.addSeparator()
            auto = menu.addAction("Auto-orient")
            auto.setCheckable(True)
            auto.setChecked(not term.get('angle_pinned', False))

            def toggle_auto():
                self._save_state()
                self._apply_port_style(
                    term, {'auto_orient': term.get('angle_pinned', False)})
                self._update_plot()
            auto.triggered.connect(lambda _=False: toggle_auto())
            menu.addSeparator()

            def delete_port():
                self._save_state()
                self.remove_port(term)
                self._update_plot()
            menu.addAction("Delete", delete_port)
            menu.exec(QCursor.pos())
            return True

        cx = self._find_txline_at_position(event.xdata, event.ydata)
        if cx is not None:
            menu = QMenu(self)
            menu.addAction("Edit…", lambda: self._edit_txline(cx))
            menu.addAction(f"Rotate {step}° CCW",
                           lambda: self._rotate_one_glyph(cx, step))
            menu.addAction(f"Rotate {step}° CW",
                           lambda: self._rotate_one_glyph(cx, -step))
            menu.addSeparator()

            def delete_txline():
                self._save_state()
                self.remove_txline(cx)
                self._update_plot()
            menu.addAction("Delete", delete_txline)
            menu.exec(QCursor.pos())
            return True

        hit = self._find_glyph_wire_at_position(event.xdata, event.ydata)
        if hit is not None:
            owner, end, conn = hit
            menu = QMenu(self)

            def delete_wire():
                self._save_state()
                self._remove_wire(owner, end, conn)
                self._update_plot()
            menu.addAction("Delete wire", delete_wire)
            menu.exec(QCursor.pos())
            return True
        return False

    def _rotate_one_glyph(self, glyph, angle_degrees):
        """Rotate one glyph from the context menu, selection-independent."""
        saved = (self.selected_ports, self.selected_txlines,
                 list(self.selected_nodes))
        is_port = 'port_id' in glyph
        self.selected_ports = [glyph] if is_port else []
        self.selected_txlines = [] if is_port else [glyph]
        self.selected_nodes.clear()
        try:
            self._rotate_selected_nodes(angle_degrees)
        finally:
            self.selected_ports, self.selected_txlines = saved[0], saved[1]
            self.selected_nodes[:] = saved[2]

    def _remove_wire(self, owner, end, conn):
        if end is None:
            if conn in owner['connections']:
                owner['connections'].remove(conn)
        elif conn in owner['ends'][end]:
            owner['ends'][end].remove(conn)
        self.selected_wires = [(o, c) for o, c in self.selected_wires
                               if c is not conn]

    def _maybe_handle_txline_end_motion(self, event):
        """True while a txline END drag is pending or active."""
        if (self._txline_end_drag_pending is None
                and self._txline_end_dragging is None):
            return False
        if event.xdata is None or event.ydata is None:
            return self._txline_end_dragging is not None

        if self._txline_end_dragging is None:
            if event.button != 1:
                return False
            dx = event.xdata - self._glyph_drag_start[0]
            dy = event.ydata - self._glyph_drag_start[1]
            if np.hypot(dx, dy) <= self.drag_threshold:
                return True         # consumed, but not yet a drag
            self._txline_end_dragging = self._txline_end_drag_pending
            self._txline_end_drag_pending = None

        cx, end = self._txline_end_dragging
        snap_x, snap_y = self._snap_to_grid(event.xdata, event.ydata)
        fixed = self._txline_end_points(cx)['xL' if end == 'x0' else 'x0']

        for artist in self._txline_end_drag_preview:
            try:
                artist.remove()
            except Exception:
                pass
        self._txline_end_drag_preview = []
        # preview the new axis, with the snapped end marked
        line = mlines.Line2D([fixed[0], snap_x], [fixed[1], snap_y],
                             color='darkorange', linestyle=':', linewidth=1.5,
                             zorder=20)
        self.canvas.ax.add_line(line)
        dot = mpatches.Circle((snap_x, snap_y), 0.18 * self.node_radius,
                              facecolor='none', edgecolor='darkorange',
                              linewidth=1.5, zorder=20)
        self.canvas.ax.add_patch(dot)
        self._txline_end_drag_preview = [line, dot]
        self.canvas.draw_idle()
        return True

    def _maybe_handle_txline_end_release(self, event):
        """True when the release belonged to a txline END drag."""
        for artist in self._txline_end_drag_preview:
            try:
                artist.remove()
            except Exception:
                pass
        self._txline_end_drag_preview = []

        if self._txline_end_dragging is not None:
            cx, end = self._txline_end_dragging
            self._txline_end_dragging = None
            if event.xdata is not None and event.ydata is not None:
                snap = self._snap_to_grid(event.xdata, event.ydata)
                if snap != tuple(self._txline_end_points(cx)[end]):
                    self._save_state()
                    self.set_txline_end(cx, end, snap)
                    self._recompute_unpinned_selfloop_angles(
                        self._wired_node_ids(cx))
            self._update_plot()
            return True
        if self._txline_end_drag_pending is not None:
            self._txline_end_drag_pending = None
            self._glyph_drag_start = None
            return True
        return False

    def _maybe_handle_glyph_motion(self, event):
        """True while a glyph drag is pending or active (dashed preview)."""
        if self._maybe_handle_txline_end_motion(event):
            return True
        if self._glyph_drag_pending is None and self._glyph_dragging is None:
            return False
        if event.xdata is None or event.ydata is None:
            return self._glyph_dragging is not None

        if self._glyph_dragging is None:
            if event.button != 1:
                return False
            dx = event.xdata - self._glyph_drag_start[0]
            dy = event.ydata - self._glyph_drag_start[1]
            if np.hypot(dx, dy) <= self.drag_threshold:
                return True     # consumed, but not yet a drag
            self._glyph_dragging = self._glyph_drag_pending
            self._glyph_drag_pending = None

        kind, obj = self._glyph_dragging
        snap_x, snap_y = self._snap_to_grid(event.xdata, event.ydata)

        if self._glyph_drag_preview is not None:
            try:
                self._glyph_drag_preview.remove()
            except Exception:
                pass
        r = self.node_radius
        if kind == 'port':
            half_w = (PORT_BODY_W / 2 + PORT_APEX_W) * r * obj.get('w_mult', 1.0)
            half_h = PORT_BODY_H / 2 * r * obj.get('h_mult', 1.0)
        else:
            half_w = (TXLINE_BODY_W * obj.get('w_mult', 1.0)
                      + TXLINE_LEAD_LEN) * r
            half_h = TXLINE_BODY_H * r * obj.get('h_mult', 1.0)
        extent = max(half_w, half_h)
        self._glyph_drag_preview = mpatches.Rectangle(
            (snap_x - extent, snap_y - extent), 2 * extent, 2 * extent,
            fill=False, edgecolor='darkorange', linestyle=':',
            linewidth=1.5, zorder=20)
        self.canvas.ax.add_patch(self._glyph_drag_preview)
        self.canvas.draw_idle()
        return True

    def _maybe_handle_glyph_release(self, event):
        """True when the left-button release belonged to a glyph drag."""
        if self._maybe_handle_txline_end_release(event):
            return True
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
                    logger.debug("Moved %s '%s' to (%.3f, %.3f)", kind,
                                 obj['label'], snap_x, snap_y)
                    # the glyph's wires now arrive at their nodes from a new
                    # direction, so unpinned self-loops there re-orient too
                    self._recompute_unpinned_selfloop_angles(
                        self._wired_node_ids(obj))
            self._update_plot()
            return True
        if self._glyph_drag_pending is not None:
            self._glyph_drag_pending = None
            self._glyph_drag_start = None
            return True
        return False

    def _clear_nodes(self):
        """Clear-all takes the glyphs with it, not just the nodes."""
        self.ports = []
        self.txlines = []
        self.port_counter = 0
        self.txline_counter = 0
        self._clear_glyph_selection()
        self._wire_pending = None
        super()._clear_nodes()

    def _wired_node_ids(self, glyph):
        """node_ids this glyph's wires reach (directly, or via a port
        wired to one of its txline ends)."""
        ids = set()
        conns = list(glyph.get('connections', []))
        for end in ('x0', 'xL'):
            conns.extend(glyph.get('ends', {}).get(end, []))
        for conn in conns:
            if conn['kind'] == 'node':
                ids.add(conn['node_id'])
            else:
                term = self._port_by_id(conn.get('port_id'))
                if term is not None:
                    ids.update(c['node_id'] for c in term['connections']
                               if c['kind'] == 'node')
        return ids

    def _delete_selected_glyphs(self):
        """Delete the selected glyphs and wires; returns how many went."""
        count = 0
        for owner, conn in list(self.selected_wires):
            for end in (None, 'x0', 'xL'):
                if end is None and 'connections' in owner:
                    if conn in owner['connections']:
                        owner['connections'].remove(conn)
                        count += 1
                        break
                elif end is not None and 'ends' in owner:
                    if conn in owner['ends'][end]:
                        owner['ends'][end].remove(conn)
                        count += 1
                        break
        self.selected_wires = []
        for term in list(self.selected_ports):
            self.remove_port(term)
            count += 1
        for cx in list(self.selected_txlines):
            self.remove_txline(cx)
            count += 1
        return count

    # ---- clipboard ----

    def _copy_glyphs_to_clipboard(self, clipboard):
        """Add the selected ports/txlines to `clipboard`.

        A wire is carried only when BOTH of its ends are in the copied set,
        exactly as an edge is: a pasted wire must have something of its own
        to land on, and silently re-pointing it at the original's target
        would make one copy quietly share the other's wiring.
        """
        node_ids = {n['node_id'] for n in self.selected_nodes}
        port_ids = {p['port_id'] for p in self.selected_ports}

        def keep(conn):
            if conn['kind'] == 'node':
                return conn.get('node_id') in node_ids
            return conn.get('port_id') in port_ids

        clipboard['ports'] = []
        for port in self.selected_ports:
            clip = copy.deepcopy(port)
            clip['connections'] = [c for c in clip['connections'] if keep(c)]
            clipboard['ports'].append(clip)

        clipboard['txlines'] = []
        for cx in self.selected_txlines:
            clip = copy.deepcopy(cx)
            clip['ends'] = {end: [c for c in clip['ends'][end] if keep(c)]
                            for end in ('x0', 'xL')}
            clipboard['txlines'].append(clip)

        return len(clipboard['ports']), len(clipboard['txlines'])

    def _clipboard_glyph_positions(self, clipboard):
        """Positions of the clipboard's glyphs, for the paste centroid.

        Without these a glyph-only copy has no centroid at all, and the
        paste lands exactly on top of the original.
        """
        return ([tuple(p['pos']) for p in clipboard.get('ports', [])]
                + [tuple(c['pos']) for c in clipboard.get('txlines', [])])

    def _paste_glyphs(self, clipboard, offset, old_id_to_new_node):
        """Paste the clipboard's glyphs, offset by `offset`, and select them.

        `old_id_to_new_node` maps the clipboard's node ids to the nodes just
        pasted, so a copied wire follows the copy rather than reattaching to
        the original. Ports are created before txlines because a txline end
        may be wired to one.
        """
        dx, dy = offset
        old_to_new_port = {}
        pasted = []

        for clip in clipboard.get('ports', []):
            port = copy.deepcopy(clip)
            old_id = port['port_id']
            port['port_id'] = self.port_id_counter
            self.port_id_counter += 1
            self.port_counter += 1
            port['pos'] = (clip['pos'][0] + dx, clip['pos'][1] + dy)
            self.ports.append(port)
            old_to_new_port[old_id] = port
            pasted.append(port)

        def remap(conn):
            """The copied wire's new target, or None when it did not travel."""
            conn = dict(conn)
            if conn['kind'] == 'node':
                node = old_id_to_new_node.get(conn.get('node_id'))
                if node is None:
                    return None
                conn['node_id'] = node['node_id']
                return conn
            port = old_to_new_port.get(conn.get('port_id'))
            if port is None:
                return None
            conn['port_id'] = port['port_id']
            return conn

        for port in pasted:
            port['connections'] = [c for c in map(remap, port['connections'])
                                   if c is not None]

        for clip in clipboard.get('txlines', []):
            cx = copy.deepcopy(clip)
            cx['txline_id'] = self.txline_id_counter
            self.txline_id_counter += 1
            self.txline_counter += 1
            cx['pos'] = (clip['pos'][0] + dx, clip['pos'][1] + dy)
            cx['ends'] = {end: [c for c in map(remap, cx['ends'][end])
                                if c is not None]
                          for end in ('x0', 'xL')}
            self.txlines.append(cx)
            pasted.append(cx)

        self.selected_ports = [g for g in pasted if 'port_id' in g]
        self.selected_txlines = [g for g in pasted if 'txline_id' in g]
        return len(self.selected_ports), len(self.selected_txlines)

    # ---- drawing ----

    def _glyph_points_per_data_unit(self, ax):
        """Same zoom-scaling factor _draw_nodes uses for label sizes."""
        fig = ax.figure
        xlim, ylim = ax.get_xlim(), ax.get_ylim()
        return min(fig.get_figwidth() * 72 / (xlim[1] - xlim[0]),
                   fig.get_figheight() * 72 / (ylim[1] - ylim[0]))

    def _draw_glyph_label(self, ax, text, x, y, font_size_points, ppdu,
                          color='black', rotation=0.0):
        """Draw a glyph label in the SAME style as node labels, through the
        cached vector renderer so it scales with zoom."""
        if not text or not str(text).strip():
            return
        body = gp.mathboldlabel(text, use_latex=self.use_latex)
        self._label_cache.draw(
            ax, rf"${body}$", x, y,
            fontsize_points=max(font_size_points, 1.0),
            points_per_data_unit=ppdu, color=color, ha='center', va='center',
            rotation=rotation, usetex=self.use_latex, zorder=12)

    def _draw_glyphs(self, ax=None):
        """Draw every port, txline and wire (called from the renderer)."""
        if not self._has_glyphs:
            return
        ax = ax or self.canvas.ax
        r = self.node_radius
        node_by_id = {n['node_id']: n for n in self.nodes}
        ppdu = self._glyph_points_per_data_unit(ax)

        # wires first, so the glyph bodies cover their stubs
        selected_conns = {id(c) for _, c in self.selected_wires}
        for owner, end, conn, pts in self._iter_glyph_wires(node_by_id):
            color, lw, style = self.wire_style(conn)
            selected = id(conn) in selected_conns
            if selected:
                # the halo stays solid whatever the wire's style, so a
                # dotted wire still reads as selected
                ax.add_line(mlines.Line2D(
                    pts[:, 0], pts[:, 1], color='salmon',
                    linewidth=max(4.0, lw + 2.6), zorder=3.5, alpha=0.9,
                    solid_capstyle='round'))
            ax.add_line(mlines.Line2D(
                pts[:, 0], pts[:, 1], color=color, linewidth=lw,
                linestyle=style, zorder=4, alpha=0.9,
                solid_capstyle='round'))
            if conn.get('label'):
                mx, my = pts[len(pts) // 2]
                font_pts = (0.55 * r * ppdu * GLYPH_LABEL_FONT_SCALE * 1.45
                            * float(conn.get('label_size_mult', 1.0)))
                ax.text(mx, my, conn['label'], ha='center', va='center',
                        zorder=5, fontsize=max(font_pts, 1.0), color=color,
                        bbox=dict(boxstyle='round,pad=0.18', fc='white',
                                  ec=color, lw=0.6))

        for cx in self.txlines:
            self._draw_one_txline(ax, cx, ppdu)
        for term in self.ports:
            self._draw_one_port(ax, term, ppdu)

        # the lead a pending wire will leave from
        if self._wire_pending is not None:
            if self._wire_pending[0] == 'port':
                pt = self._port_apex(self._wire_pending[1])
            else:
                _, cxp, end = self._wire_pending
                pt = self._txline_end_points(cxp)[end]
            ax.add_patch(mpatches.Circle(
                pt, 0.35 * r, fill=False, edgecolor='firebrick',
                linewidth=2, linestyle=':', zorder=15))

    def _draw_one_port(self, ax, term, ppdu):
        x, y, w, h, apex_x = self._port_geometry(term)
        angle = self._port_effective_angle(term)
        pending = (self._wire_pending is not None
                   and self._wire_pending[0] == 'port'
                   and self._wire_pending[1] is term)
        stroke = 'dodgerblue' if pending else term.get('color', 'black')
        lw = float(term.get('linewidth', PORT_LW))

        def rot(px, py):
            return rotatepoint(px, py, x, y, angle)

        verts = [rot(x - w / 2, y - h / 2),
                 rot(x + w / 2, y - h / 2),
                 rot(apex_x, y),
                 rot(x + w / 2, y + h / 2),
                 rot(x - w / 2, y + h / 2)]
        if term in self.selected_ports:
            ax.add_patch(mpatches.Polygon(
                verts, closed=True, fill=False, edgecolor='lightcoral',
                linewidth=6.0, zorder=10.5))
        ax.add_patch(mpatches.Polygon(
            verts, closed=True, facecolor=term.get('fill', 'white'),
            edgecolor=stroke, linewidth=lw, zorder=11, joinstyle='miter',
            linestyle='--' if pending else '-'))
        label = term.get('label', '')
        if label:
            font_pts = (h * GLYPH_LABEL_FONT_SCALE * 1.45 * ppdu
                        * float(term.get('label_size_mult', 1.0)))
            n_chars = max(len(str(label)), 1)
            font_pts = min(font_pts, GLYPH_LABEL_FILL * w * ppdu
                           / (GLYPH_LABEL_ADVANCE * n_chars))
            dx, dy = term.get('labelnudge', (0.0, 0.0))
            cx, cy = rot(x + dx, y + dy)
            self._draw_glyph_label(ax, label, cx, cy, font_pts, ppdu,
                                   color=term.get('label_color', 'black'),
                                   rotation=gp.readableangle(angle))

    def _draw_one_txline(self, ax, cx, ppdu):
        r = self.node_radius
        lx, ly, w, h, rx = self._txline_geometry(cx)
        angle = cx.get('angle', 0.0)
        stroke = cx.get('color', 'black')
        fill = cx.get('fill', '#cccccc')
        lw = float(cx.get('linewidth', TXLINE_LW))
        glyph_tf = (mtransforms.Affine2D().rotate_deg_around(lx, ly, angle)
                    + ax.transData)

        if cx in self.selected_txlines:
            hh = max(1.6 * h, 0.5 * r)
            ax.add_patch(mpatches.Rectangle(
                (lx - w - rx - TXLINE_LEAD_LEN * r, ly - hh),
                2 * (w + rx + TXLINE_LEAD_LEN * r), 2 * hh, fill=False,
                edgecolor='lightcoral', linewidth=5.0, zorder=9.5,
                transform=glyph_tf))

        ax.add_patch(mpatches.Rectangle(
            (lx - w, ly - h), 2 * w, 2 * h, facecolor=fill, edgecolor='none',
            zorder=10, transform=glyph_tf))
        ax.add_patch(mpatches.Ellipse(
            (lx - w, ly), 2 * rx, 2 * h, facecolor=fill, edgecolor='none',
            zorder=10, transform=glyph_tf))
        ax.add_patch(mpatches.Arc(
            (lx - w, ly), 2 * rx, 2 * h, theta1=90, theta2=270,
            edgecolor=stroke, linewidth=lw, zorder=11, transform=glyph_tf))
        ax.add_patch(mpatches.Ellipse(
            (lx + w, ly), 2 * rx, 2 * h, facecolor='white', edgecolor=stroke,
            linewidth=lw, zorder=11, transform=glyph_tf))
        for yy in (ly - h, ly + h):
            ax.add_line(mlines.Line2D([lx - w, lx + w], [yy, yy],
                                      color=stroke, linewidth=lw, zorder=11,
                                      transform=glyph_tf))
        # closed (left) cap: the stub leaves the outside of the rounded cap
        ax.add_line(mlines.Line2D(
            [lx - w - rx - TXLINE_LEAD_LEN * r, lx - w - rx], [ly, ly],
            color=stroke, linewidth=lw, zorder=11, transform=glyph_tf))
        # open (right) mouth: the conductor comes out of the BORE, so the
        # stub starts at the center of the mouth ellipse and is drawn in
        # FRONT of it, with a round cap so it reads as a wire end rather
        # than a cut edge. From the rim it looked stuck to the outside.
        ax.add_line(mlines.Line2D(
            [lx + w, lx + w + rx + TXLINE_LEAD_LEN * r], [ly, ly],
            color=stroke, linewidth=lw, solid_capstyle='round', zorder=11.4,
            transform=glyph_tf))

        pending = (self._wire_pending is not None
                   and self._wire_pending[0] == 'txline'
                   and self._wire_pending[1] is cx)
        for end, (ex, ey) in self._txline_end_points(cx).items():
            wired = bool(cx['ends'][end])
            is_pending = pending and self._wire_pending[2] == end
            mark = ('dodgerblue' if is_pending
                    else 'black' if wired else 'darkgray')
            ax.add_patch(mpatches.Circle(
                (ex, ey), 0.12 * r,
                facecolor=(mark if wired or is_pending else 'white'),
                edgecolor=mark, linewidth=1.6, zorder=11.5))

        label = cx.get('label', '')
        if label:
            scale = float(cx.get('label_size_mult', 1.0))
            n_chars = max(len(str(label)), 1)
            if 2 * h >= 0.85 * r:
                # Inside the body, sized to the body HEIGHT so stretching
                # the line grows its label with it. The old 1.1 r cap pinned
                # the label the moment the body was stretched at all, which
                # is what made the Label size spinbox look inert.
                tx, ty = lx, ly
                font_pts = (2 * h * ppdu * GLYPH_LABEL_FONT_SCALE * 1.6
                            * scale)
                # ...but never wider than the body it sits in
                font_pts = min(font_pts, GLYPH_LABEL_FILL * 2 * w * ppdu
                               / (GLYPH_LABEL_ADVANCE * n_chars))
            else:
                # too thin to hold text: float it just above, where nothing
                # clips it
                tx, ty = lx, ly + h + 0.45 * r
                font_pts = (0.9 * r * ppdu * GLYPH_LABEL_FONT_SCALE * 1.6
                            * scale)
            dx, dy = cx.get('labelnudge', (0.0, 0.0))
            tx, ty = rotatepoint(tx + dx, ty + dy, lx, ly, angle)
            self._draw_glyph_label(
                ax, label, tx, ty, font_pts, ppdu,
                color=cx.get('label_color', 'black'),
                rotation=gp.readableangle(angle))

    # ---- extents ----

    def _glyph_extent_points(self):
        """Extreme points of every glyph, for auto-fit and export framing."""
        pts = []
        r = self.node_radius
        for term in self.ports:
            x, y, w, h, apex_x = self._port_geometry(term)
            angle = self._port_effective_angle(term)
            for px, py in ((x - w / 2, y - h / 2), (x - w / 2, y + h / 2),
                           (apex_x, y - h / 2), (apex_x, y + h / 2)):
                pts.append(rotatepoint(px, py, x, y, angle))
        for cx in self.txlines:
            lx, ly, w, h, rx = self._txline_geometry(cx)
            half_w = w + rx + TXLINE_LEAD_LEN * r
            half_h = max(h, 1.35 * r)     # the label floats above a thin one
            for px, py in ((lx - half_w, ly - half_h),
                           (lx - half_w, ly + half_h),
                           (lx + half_w, ly - half_h),
                           (lx + half_w, ly + half_h)):
                pts.append(rotatepoint(px, py, lx, ly, cx.get('angle', 0.0)))
        return pts

    def _calculate_graph_extents(self):
        """Base extents, widened to include the glyphs."""
        pts = self._glyph_extent_points()
        if not pts:
            return super()._calculate_graph_extents()
        if not self.nodes:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            pad = self.node_radius
            return min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad
        x_min, x_max, y_min, y_max = super()._calculate_graph_extents()
        xs = [p[0] for p in pts] + [x_min, x_max]
        ys = [p[1] for p in pts] + [y_min, y_max]
        return min(xs), max(xs), min(ys), max(ys)

    # ---- serialization ----

    def _serialize_glyphs(self, data):
        """Add ports/txlines to the saved dict (omitted when there are
        none, so files of graphs without glyphs are unchanged)."""
        if self.ports:
            data['ports'] = [
                {'port_id': t['port_id'], 'label': t['label'],
                 'pos': list(t['pos']), 'angle': t.get('angle', 0.0),
                 'angle_pinned': t.get('angle_pinned', False),
                 'w_mult': t.get('w_mult', 1.0),
                 'h_mult': t.get('h_mult', 1.0),
                 'linewidth': t.get('linewidth', PORT_LW),
                 'color': t.get('color', 'black'),
                 'fill': t.get('fill', 'white'),
                 'label_color': t.get('label_color', 'black'),
                 'label_size_mult': t.get('label_size_mult', 1.0),
                 'labelnudge': list(t.get('labelnudge', (0.0, 0.0))),
                 'connections': [dict(c) for c in t['connections']]}
                for t in self.ports]
        if self.txlines:
            data['txlines'] = [
                {'txline_id': c['txline_id'], 'label': c['label'],
                 'pos': list(c['pos']), 'angle': c.get('angle', 0.0),
                 'w_mult': c.get('w_mult', 1.0),
                 'h_mult': c.get('h_mult', 1.0),
                 'linewidth': c.get('linewidth', TXLINE_LW),
                 'color': c.get('color', 'black'),
                 'fill': c.get('fill', '#cccccc'),
                 'label_color': c.get('label_color', 'black'),
                 'label_size_mult': c.get('label_size_mult', 1.0),
                 'labelnudge': list(c.get('labelnudge', (0.0, 0.0))),
                 'ends': {end: [dict(cn) for cn in c['ends'][end]]
                          for end in ('x0', 'xL')}}
                for c in self.txlines]

    def _deserialize_glyphs(self, data):
        """Rebuild ports/txlines from a saved dict.

        The glyphs were briefly called 'terminals' and 'coaxes' before
        release; a file written under those names still loads.
        """
        self.ports = []
        self.txlines = []
        self._clear_glyph_selection()
        self._wire_pending = None

        saved_ports = data.get('ports', data.get('terminals', []))
        saved_txlines = data.get('txlines', data.get('coaxes', []))

        for t in saved_ports:
            term = self.add_port(
                label=t.get('label', 'P'), pos=tuple(t.get('pos', (0, 0))),
                angle=t.get('angle', 0.0))
            term['port_id'] = t.get('port_id', t.get('terminal_id',
                                                     term['port_id']))
            term['angle_pinned'] = t.get('angle_pinned', False)
            for key, default in (('w_mult', 1.0), ('h_mult', 1.0),
                                 ('linewidth', PORT_LW),
                                 ('color', 'black'), ('fill', 'white'),
                                 ('label_color', 'black'),
                                 ('label_size_mult', 1.0)):
                term[key] = t.get(key, default)
            term['labelnudge'] = tuple(t.get('labelnudge', (0.0, 0.0)))
            term['connections'] = [_migrate_conn(c)
                                   for c in t.get('connections', [])]

        for c in saved_txlines:
            cx = self.add_txline(label=c.get('label', 'TL'),
                                 pos=tuple(c.get('pos', (0, 0))),
                                 angle=c.get('angle', 0.0))
            cx['txline_id'] = c.get('txline_id', c.get('coax_id',
                                                       cx['txline_id']))
            for key, default in (('w_mult', 1.0), ('h_mult', 1.0),
                                 ('linewidth', TXLINE_LW), ('color', 'black'),
                                 ('fill', '#cccccc'),
                                 ('label_color', 'black'),
                                 ('label_size_mult', 1.0)):
                cx[key] = c.get(key, default)
            cx['labelnudge'] = tuple(c.get('labelnudge', (0.0, 0.0)))
            ends = c.get('ends', {})
            cx['ends'] = {end: [_migrate_conn(cn) for cn in ends.get(end, [])]
                          for end in ('x0', 'xL')}

        # keep the id counters ahead of anything loaded
        self.port_id_counter = max(
            [t['port_id'] + 1 for t in self.ports], default=0)
        self.txline_id_counter = max(
            [c['txline_id'] + 1 for c in self.txlines], default=0)
        self.port_counter = len(self.ports)
        self.txline_counter = len(self.txlines)

    # ---- code export ----

    def _glyph_code_calls(self, x_center, y_center):
        """The glyphs as :class:`code_export.Call` records, or [].

        Mirrors the canvas exactly: the same graph_primitives call draws
        both, so the exported script reproduces what was on screen -- the
        auto-orientation included, since `addport(autoorient=True)`
        re-derives the lead angle from the wiring the script rebuilds.
        """
        if not self._has_glyphs:
            return []
        r = self.node_radius
        calls = []

        def label_of(obj):
            # repr, not manual quoting: a label may legitimately contain a
            # backslash (\Delta_A) or a quote, and only repr gets both right
            return repr(obj.get('label') or '')

        for term in self.ports:
            x, y = term['pos']
            ident = [('label', label_of(term)),
                     ('xy', f"({x - x_center:.3f}, {y - y_center:.3f})"),
                     ('port_id', str(term['port_id']))]
            extra = []
            if term.get('angle_pinned', False):
                extra.append(('angle', f"{term.get('angle', 0.0):.1f}"))
            else:
                extra.append(('autoorient', 'True'))
            style, per_glyph = self._glyph_style_args(term, PORT_LW, 'white')
            calls.append(Call('addport', ident=ident,
                              style=tuple([('R', f"{r:.3f}")] + style),
                              extra=extra + per_glyph, inline=True,
                              tag=term.get('label') or f"P{term['port_id']}"))

        for cx in self.txlines:
            x, y = cx['pos']
            ident = [('label', label_of(cx)),
                     ('xy', f"({x - x_center:.3f}, {y - y_center:.3f})"),
                     ('txline_id', str(cx['txline_id']))]
            style, per_glyph = self._glyph_style_args(cx, TXLINE_LW, '#cccccc')
            calls.append(Call(
                'addtxline', ident=ident,
                style=tuple([('R', f"{r:.3f}")] + style),
                extra=[('angle', f"{cx.get('angle', 0.0):.1f}")] + per_glyph,
                inline=True,
                tag=cx.get('label') or f"TL{cx['txline_id']}"))

        node_ids = {n['node_id'] for n in self.nodes}
        for term in self.ports:
            for conn in term['connections']:
                end_spec = self._export_conn_spec(conn, node_ids)
                if end_spec is None:
                    continue
                calls.append(self._wire_call(
                    f"('port', {term['port_id']})", end_spec, conn))
        for cx in self.txlines:
            for end in ('x0', 'xL'):
                for conn in cx['ends'][end]:
                    end_spec = self._export_conn_spec(conn, node_ids)
                    if end_spec is None:
                        continue
                    calls.append(self._wire_call(
                        f"('txline', {cx['txline_id']}, '{end}')",
                        end_spec, conn))
        return calls

    @classmethod
    def _wire_call(cls, start_spec, end_spec, conn):
        style, per_wire = cls._export_wire_style_args(conn)
        return Call('addwire', ident=[('start', start_spec),
                                      ('end', end_spec)],
                    style=tuple(style), extra=per_wire, inline=True)

    @staticmethod
    def _glyph_style_args(glyph, default_lw, default_fill):
        """(appearance, per-glyph) keywords -- the split the grouped export
        needs: everything that can be shared, then what cannot."""
        args = []
        for key, name, default in (('w_mult', 'length', 1.0),
                                   ('h_mult', 'height', 1.0),
                                   ('label_size_mult', 'labelscale', 1.0)):
            val = float(glyph.get(key, default))
            if abs(val - default) > 1e-6:
                args.append((name, f"{val:.3f}"))
        lw = float(glyph.get('linewidth', default_lw))
        if abs(lw - default_lw) > 1e-6:
            args.append(('lw', f"{lw:.2f}"))
        if glyph.get('color', 'black') != 'black':
            args.append(('color', repr(glyph['color'])))
        if glyph.get('fill', default_fill) != default_fill:
            args.append(('fill', repr(glyph['fill'])))
        if glyph.get('label_color', 'black') != 'black':
            args.append(('labelcolor', repr(glyph['label_color'])))
        per_glyph = []
        nudge = tuple(glyph.get('labelnudge', (0.0, 0.0)))
        if abs(nudge[0]) > 1e-6 or abs(nudge[1]) > 1e-6:
            per_glyph.append(('labelnudge',
                              f"({nudge[0]:.3f}, {nudge[1]:.3f})"))
        return args, per_glyph

    @staticmethod
    def _export_conn_spec(conn, node_ids):
        if conn['kind'] == 'node':
            if conn.get('node_id') not in node_ids:
                return None
            return f"('node', {conn['node_id']})"
        return f"('port', {conn['port_id']})"

    @staticmethod
    def _export_wire_style_args(conn):
        """(appearance, per-wire) keywords for one wire."""
        args = []
        if conn.get('color'):
            args.append(('color', repr(conn['color'])))
        mult = float(conn.get('linewidth_mult', 1.25))
        if abs(mult - 1.25) > 1e-6:
            args.append(('lw', f"{WIRE_LW * mult:.2f}"))
        style = conn.get('linestyle') or '-'
        if style != '-':
            args.append(('linestyle', repr(style)))
        scale = float(conn.get('label_size_mult', 1.0))
        if abs(scale - 1.0) > 1e-6:
            args.append(('labelscale', f"{scale:.3f}"))
        per_wire = []
        if conn.get('label'):
            per_wire.append(('label', repr(conn['label'])))
        return args, per_wire


def _migrate_conn(conn):
    """One saved wire, with the pre-release 'terminal' spelling accepted."""
    conn = dict(conn)
    if conn.get('kind') == 'terminal':
        conn['kind'] = 'port'
    if 'terminal_id' in conn:
        conn.setdefault('port_id', conn.pop('terminal_id'))
    return conn


def _dist_to_polyline(x, y, pts):
    """Minimum distance from (x, y) to a sampled wire."""
    p = np.array([x, y], dtype=float)
    a, b = pts[:-1], pts[1:]
    seg = b - a
    seg_len2 = np.einsum('ij,ij->i', seg, seg)
    seg_len2[seg_len2 == 0.0] = 1e-30
    t = np.clip(np.einsum('ij,ij->i', p - a, seg) / seg_len2, 0.0, 1.0)
    proj = a + t[:, None] * seg
    return float(np.min(np.hypot(*(p - proj).T)))
