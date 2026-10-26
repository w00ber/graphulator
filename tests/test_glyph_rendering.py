"""Rendering fixes for glyphs, wires and the selection highlight.

Covers: line widths that follow the zoom (they were drawn in raw points, so
a zoomed-in graph showed hairlines on huge nodes), the shared stub a fan of
wires leaves a port through, rounded dash caps, and the one selection look
shared by wires, edges and self-loops. Headless (offscreen Qt + Agg).
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    # QtWebEngine refuses to sandbox as root (CI containers)
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")


@pytest.fixture()
def win(tmp_path):
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    import graphulator.graphulator_qt as gq
    from graphulator import graphulator_config as config

    w = gq.Graphulator()
    w.last_graph_path = tmp_path / "last.graph"
    w.recent_files_path = tmp_path / "recent"
    saved = {k: getattr(config, k) for k in
             ('DEFAULT_WIRE_ROUND_CAPS', 'DEFAULT_PORT_APEX_DEPTH',
              'DEFAULT_PORT_LEAD_LENGTH')}
    yield w, config
    for key, value in saved.items():
        setattr(config, key, value)


@pytest.fixture()
def para(tmp_path):
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    import graphulator.graphulator_para as gp
    from graphulator import graphulator_para_config as config

    w = gp.Graphulator()
    w.last_graph_path = tmp_path / "last.pgraph"
    w.recent_files_path = tmp_path / "recent"
    saved = {k: getattr(config, k) for k in
             ('DEFAULT_WIRE_ROUND_CAPS', 'DEFAULT_PORT_APEX_DEPTH',
              'DEFAULT_PORT_LEAD_LENGTH')}
    yield w, config
    for key, value in saved.items():
        setattr(config, key, value)


def add_node(w, label, pos):
    node = {'node_id': w.node_id_counter, 'label': label, 'pos': pos,
            'color': '#6699ff', 'color_key': 'BLUE', 'node_size_mult': 1.0,
            'label_size_mult': 1.0, 'conj': False,
            'nodelabelnudge': (0.0, 0.0)}
    w.nodes.append(node)
    w.node_id_counter += 1
    return node


def add_edge(w, a, b, **props):
    edge = {'from_node': a, 'to_node': b, 'from_node_id': a['node_id'],
            'to_node_id': b['node_id'], 'label1': '', 'label2': '',
            'linewidth_mult': 1.25, 'label_size_mult': 1.4,
            'label_offset_mult': 1.0, 'style': 'loopy', 'direction': 'both',
            'is_self_loop': False, 'flip_labels': False, 'looptheta': 30}
    edge.update(props)
    w.edges.append(edge)
    return edge


def zoom_to(w, half_span):
    w.base_xlim = (-half_span, half_span)
    w.base_ylim = (-half_span, half_span)
    w.canvas.ax.set_xlim(*w.base_xlim)
    w.canvas.ax.set_ylim(*w.base_ylim)


def drawn_widths(ax, color):
    return [ln.get_linewidth() for ln in ax.lines
            if ln.get_color() == color]


# ---------------------------------------------------------------------------
# line widths follow the zoom
# ---------------------------------------------------------------------------

def test_the_zoom_scale_tracks_the_view(win):
    w, _config = win
    zoom_to(w, 20.0)
    wide = w._zoom_lw_scale()
    zoom_to(w, 5.0)
    assert w._zoom_lw_scale() > wide


def test_a_port_stroke_scales_with_zoom(win):
    """matplotlib line widths are POINTS, so a stored width kept a fixed
    on-screen thickness while the drawing grew around it."""
    w, _config = win
    w.add_port(label='P1', pos=(0.0, 0.0), linewidth=3.0)

    def port_stroke():
        w._update_plot()
        polys = [p for p in w.canvas.ax.patches
                 if type(p).__name__ == 'Polygon']
        return max(p.get_linewidth() for p in polys)

    zoom_to(w, 20.0)
    far = port_stroke()
    zoom_to(w, 5.0)
    assert port_stroke() > far


def test_a_wire_scales_with_zoom(win):
    w, _config = win
    node = add_node(w, 'A', (6.0, 0.0))
    conn = w.connect_port_to_node(w.add_port(pos=(-6.0, 0.0)), node)
    conn['color'] = 'teal'

    zoom_to(w, 20.0)
    w._update_plot()
    far = max(drawn_widths(w.canvas.ax, 'teal'))
    zoom_to(w, 5.0)
    w._update_plot()
    assert max(drawn_widths(w.canvas.ax, 'teal')) > far


def test_wire_style_itself_still_reports_the_stored_width(win):
    """The zoom factor is applied at DRAW time only: wire_style is the
    stored-value accessor the panel and the code export read."""
    w, _config = win
    one = w.wire_style({})[1]
    zoom_to(w, 2.0)
    assert w.wire_style({})[1] == pytest.approx(one)


def test_a_para_wire_scales_with_zoom(para):
    w, _config = para
    node = add_node(w, 'A', (6.0, 0.0))
    port = w.add_port(label='P1', pos=(-6.0, 0.0))
    att = w.add_port_attachment(port, node)
    att['color'] = 'teal'

    zoom_to(w, 20.0)
    w._update_plot()
    far = max(drawn_widths(w.canvas.ax, 'teal'))
    zoom_to(w, 5.0)
    w._update_plot()
    assert max(drawn_widths(w.canvas.ax, 'teal')) > far


# ---------------------------------------------------------------------------
# a fan out of one port shares its stub
# ---------------------------------------------------------------------------

def test_wires_out_of_one_port_share_a_straight_run(win):
    """Paragraphulator's look: the split happens at an offset, not at the
    point of the pentagon."""
    w, _config = win
    a = add_node(w, 'A', (8.0, 4.0))
    b = add_node(w, 'B', (8.0, -4.0))
    port = w.add_port(label='P1', pos=(-4.0, 0.0))
    w.connect_port_to_node(port, a)
    w.connect_port_to_node(port, b)

    pts = [p for *_x, p in w._iter_glyph_wires()]
    coincident = np.hypot(*(pts[0] - pts[1]).T) < 1e-9
    assert coincident[0] and coincident[1]
    split_x = pts[0][int(np.argmax(~coincident))][0]
    assert split_x > w._port_apex(port)[0]


def test_the_shared_run_does_not_move_when_the_port_stretches(win):
    """The nose and the lead are FIXED geometry. Stretching the body (or
    letting a long label autosize it) must leave the point of the pentagon
    -- and the straight run the wires leave through -- exactly where it
    was, measured from the body edge."""
    w, _config = win
    port = w.add_port(label='P1', pos=(0.0, 0.0))
    wide = w.add_port(label='P2', pos=(0.0, 0.0), w_mult=2.0)
    assert w._port_wire_lead(port) > 0.0
    assert w._port_wire_lead(wide) == pytest.approx(w._port_wire_lead(port))

    def nose_depth(p):
        _x, _y, body_w, _h, apex_x = w._port_geometry(p)
        return apex_x - (p['pos'][0] + body_w / 2)

    assert nose_depth(wide) == pytest.approx(nose_depth(port))
    # ...and the body itself still stretches
    assert w._port_geometry(wide)[2] > w._port_geometry(port)[2]


def test_a_txline_wire_keeps_no_lead(win):
    """A txline draws its own stub, so its wires start at the tip."""
    w, _config = win
    node = add_node(w, 'A', (8.0, 0.0))
    cx = w.add_txline(label='TL1', pos=(0.0, 0.0))
    w.connect_txline_end(cx, 'xL', node)
    pts = next(p for *_x, p in w._iter_glyph_wires())
    tip = np.asarray(w._txline_end_points(cx)['xL'])
    assert np.allclose(pts[0], tip)


# ---------------------------------------------------------------------------
# rounded dash caps
# ---------------------------------------------------------------------------

def test_a_dotted_wire_gets_round_dash_caps(win):
    w, config = win
    node = add_node(w, 'A', (6.0, 0.0))
    conn = w.connect_port_to_node(w.add_port(pos=(-6.0, 0.0)), node)
    conn.update(color='teal', linestyle=':')
    w._update_plot()
    line = next(ln for ln in w.canvas.ax.lines
                if ln.get_color() == 'teal')
    assert line.get_dash_capstyle() == 'round'


def test_the_dash_cap_setting_turns_it_off(win):
    w, config = win
    config.DEFAULT_WIRE_ROUND_CAPS = False
    node = add_node(w, 'A', (6.0, 0.0))
    conn = w.connect_port_to_node(w.add_port(pos=(-6.0, 0.0)), node)
    conn.update(color='teal', linestyle=':')
    w._update_plot()
    line = next(ln for ln in w.canvas.ax.lines
                if ln.get_color() == 'teal')
    assert line.get_dash_capstyle() == 'butt'


def test_a_non_default_cap_style_is_exported(win):
    w, config = win
    config.DEFAULT_WIRE_ROUND_CAPS = False
    node = add_node(w, 'A', (6.0, 0.0))
    conn = w.connect_port_to_node(w.add_port(pos=(-6.0, 0.0)), node)
    args, _per_wire = w._export_wire_style_args(conn)
    assert ('capstyle', repr('butt')) in args


def test_a_para_dotted_wire_gets_round_dash_caps(para):
    w, config = para
    node = add_node(w, 'A', (6.0, 0.0))
    att = w.add_port_attachment(w.add_port(pos=(-6.0, 0.0)), node)
    att.update(color='teal', linestyle=':')
    w._update_plot()
    line = next(ln for ln in w.canvas.ax.lines
                if ln.get_color() == 'teal')
    assert line.get_dash_capstyle() == 'round'


# ---------------------------------------------------------------------------
# one selection look for wires, edges and self-loops
# ---------------------------------------------------------------------------

def halo_artists(ax, color='salmon'):
    """Every artist drawn in the shared selection-halo color."""
    from matplotlib.colors import to_rgb
    want = to_rgb(color)

    def is_halo(artist):
        getter = getattr(artist, 'get_edgecolor', None) or artist.get_color
        try:
            value = getter()
        except Exception:
            return False
        # a Line2D reports a NAME ('salmon'); a patch reports RGBA. Slicing
        # the name would hand to_rgb three letters, so only an RGBA tuple
        # gets trimmed.
        if not isinstance(value, str):
            value = tuple(value)[:3]
        try:
            return tuple(to_rgb(value)) == want
        except (TypeError, ValueError):
            return False

    return [a for a in list(ax.lines) + list(ax.patches) if is_halo(a)]


def test_a_selected_edge_gets_a_halo_not_a_dot(win):
    w, _config = win
    a = add_node(w, 'A', (-4.0, 0.0))
    b = add_node(w, 'B', (4.0, 0.0))
    edge = add_edge(w, a, b)

    w._update_plot()
    assert not halo_artists(w.canvas.ax)
    w.selected_edges.append(edge)
    w._update_plot()
    assert halo_artists(w.canvas.ax)
    # the old coral midpoint dot is gone
    from matplotlib.colors import to_rgb
    assert not [p for p in w.canvas.ax.patches
                if type(p).__name__ == 'Circle'
                and tuple(p.get_facecolor()[:3]) == to_rgb('lightcoral')]


def test_a_selected_self_loop_gets_a_halo(win):
    w, _config = win
    a = add_node(w, 'A', (0.0, 0.0))
    loop = add_edge(w, a, a, is_self_loop=True, selfloopangle=90,
                    selfloopscale=1.0, arrowlengthsc=1.0, flip=False,
                    angle_pinned=True, selflooplabelnudge=(0.0, 0.0))

    w._update_plot()
    assert not halo_artists(w.canvas.ax)
    w.selected_edges.append(loop)
    w._update_plot()
    assert halo_artists(w.canvas.ax)


def test_the_halo_is_wider_than_the_line_it_sits_under(win):
    w, _config = win
    assert w._selection_halo_lw(1.0) > 1.0
    assert w._selection_halo_lw(20.0) > 20.0
    # and it widens with the zoom, like the edge over it
    assert w._selection_halo_lw(20.0, 2.0) > w._selection_halo_lw(20.0, 1.0)


def test_a_selected_para_edge_gets_a_halo(para):
    w, _config = para
    a = add_node(w, 'A', (-4.0, 0.0))
    b = add_node(w, 'B', (4.0, 0.0))
    edge = add_edge(w, a, b)

    w._update_plot()
    assert not halo_artists(w.canvas.ax)
    w.selected_edges.append(edge)
    w._update_plot()
    assert halo_artists(w.canvas.ax)


# ---------------------------------------------------------------------------
# the port's nose and lead are FIXED geometry, and settable
# ---------------------------------------------------------------------------

def test_the_nose_depth_is_settable(win):
    w, config = win
    port = w.add_port(label='P1', pos=(0.0, 0.0))

    def nose_depth():
        _x, _y, body_w, _h, apex_x = w._port_geometry(port)
        return apex_x - (port['pos'][0] + body_w / 2)

    config.DEFAULT_PORT_APEX_DEPTH = 0.55
    shallow = nose_depth()
    config.DEFAULT_PORT_APEX_DEPTH = 1.5
    assert nose_depth() > shallow


def test_a_port_may_override_the_nose_depth(win):
    w, config = win
    config.DEFAULT_PORT_APEX_DEPTH = 0.55
    plain = w.add_port(label='P1', pos=(0.0, 0.0))
    pointy = w.add_port(label='P2', pos=(0.0, 0.0), apex=1.5)
    assert w.port_apex_depth(pointy) > w.port_apex_depth(plain)


def test_the_lead_length_is_settable(win):
    w, config = win
    port = w.add_port(label='P1', pos=(0.0, 0.0))
    config.DEFAULT_PORT_LEAD_LENGTH = 1.2
    short = w._port_wire_lead(port)
    config.DEFAULT_PORT_LEAD_LENGTH = 3.0
    assert w._port_wire_lead(port) > short


def test_the_lead_moves_where_the_fan_splits(win):
    w, config = win
    a = add_node(w, 'A', (10.0, 5.0))
    b = add_node(w, 'B', (10.0, -5.0))
    port = w.add_port(label='P1', pos=(-6.0, 0.0))
    w.connect_port_to_node(port, a)
    w.connect_port_to_node(port, b)

    def split_x():
        pts = [p for *_x, p in w._iter_glyph_wires()]
        shared = np.hypot(*(pts[0] - pts[1]).T) < 1e-9
        return pts[0][int(np.argmax(~shared))][0]

    config.DEFAULT_PORT_LEAD_LENGTH = 1.2
    near = split_x()
    config.DEFAULT_PORT_LEAD_LENGTH = 3.0
    assert split_x() > near


def test_a_non_default_nose_and_lead_are_exported(win):
    """The generated script calls the primitives directly, so geometry
    that differs from the primitive default has to be written out."""
    w, config = win
    config.DEFAULT_PORT_APEX_DEPTH = 1.5
    config.DEFAULT_PORT_LEAD_LENGTH = 3.0
    args = w._port_geometry_args(w.add_port(label='P1', pos=(0.0, 0.0)))
    assert dict(args)['apex'].startswith('1.5')
    assert dict(args)['lead'].startswith('3.0')


def test_the_default_nose_and_lead_stay_out_of_the_export(win):
    w, _config = win
    assert w._port_geometry_args(w.add_port(label='P1')) == []


def test_a_para_port_nose_and_lead_are_fixed(para):
    """Same rule in Paragraphulator, where a long label autosizes the body
    -- which used to drag the nose and the lead tip out with it."""
    w, _config = para
    short = w.add_port(label='P', pos=(0.0, 0.0))
    long_label = w.add_port(label='P_very_long_label', pos=(0.0, -8.0))

    def nose_and_lead(p):
        x, _y, body_w, _h, apex_x, lead_tip_x = w._port_geometry(p)
        return apex_x - (x + body_w / 2), lead_tip_x - apex_x

    assert nose_and_lead(long_label) == pytest.approx(nose_and_lead(short))
    # ...and the body itself still grew to hold the label
    assert w._port_geometry(long_label)[2] > w._port_geometry(short)[2]


def test_the_para_nose_and_lead_are_settable(para):
    w, config = para
    port = w.add_port(label='P1', pos=(0.0, 0.0))

    def tip():
        return w._port_geometry(port)[5]

    config.DEFAULT_PORT_APEX_DEPTH = 0.55
    config.DEFAULT_PORT_LEAD_LENGTH = 1.2
    plain = tip()
    config.DEFAULT_PORT_LEAD_LENGTH = 3.0
    longer = tip()
    assert longer > plain
    config.DEFAULT_PORT_APEX_DEPTH = 1.5
    assert tip() > longer


def test_a_para_port_may_override_the_geometry(para):
    w, config = para
    config.DEFAULT_PORT_APEX_DEPTH = 0.55
    plain = w.add_port(label='P1', pos=(0.0, 0.0))
    pointy = w.add_port(label='P2', pos=(0.0, 0.0))
    pointy['apex'] = 1.5
    assert w.port_apex_depth(pointy) > w.port_apex_depth(plain)


# ---------------------------------------------------------------------------
# the lead takes the widest attached wire's width
# ---------------------------------------------------------------------------

def test_an_unwired_port_lead_keeps_the_body_stroke(para):
    """Nothing attached means no seam to match."""
    w, _config = para
    port = w.add_port(label='P1', pos=(0.0, 0.0), )
    port['linewidth'] = 2.5
    assert w.port_lead_width(port) == pytest.approx(2.5)


def test_the_lead_matches_the_attached_wire(para):
    w, _config = para
    node = add_node(w, 'A', (6.0, 0.0))
    port = w.add_port(label='P1', pos=(-6.0, 0.0))
    port['linewidth'] = 2.0
    att = w.add_port_attachment(port, node)
    att['linewidth_mult'] = 4.0

    assert w.port_lead_width(port) == pytest.approx(w.wire_style(att)[1])
    assert w.port_lead_width(port) > 2.0


def test_the_lead_takes_the_WIDEST_of_several_wires(para):
    w, _config = para
    a = add_node(w, 'A', (6.0, 4.0))
    b = add_node(w, 'B', (6.0, -4.0))
    port = w.add_port(label='P1', pos=(-6.0, 0.0))
    thin = w.add_port_attachment(port, a)
    fat = w.add_port_attachment(port, b)
    thin['linewidth_mult'] = 0.5
    fat['linewidth_mult'] = 3.0

    assert w.port_lead_width(port) == pytest.approx(w.wire_style(fat)[1])


def test_a_line_terminated_on_the_port_counts_too(para):
    """A line end wired to the port meets the same lead tip."""
    w, _config = para
    port = w.add_port(label='P1', pos=(-6.0, 0.0))
    port['linewidth'] = 2.0
    line = w.add_line_resonator(label='TL1', pos=(0.0, 0.0), port_end=None)
    conn = w.connect_line_end_to_port(line, 'xL', port)
    conn['linewidth_mult'] = 4.0

    assert w.port_lead_width(port) == pytest.approx(w.wire_style(conn)[1])


def test_the_drawn_lead_uses_that_width(para):
    w, _config = para
    node = add_node(w, 'A', (6.0, 0.0))
    port = w.add_port(label='P1', pos=(-6.0, 0.0))
    port['color'] = 'indianred'          # so the lead is findable
    port['linewidth'] = 1.0
    att = w.add_port_attachment(port, node)
    att['linewidth_mult'] = 4.0
    w._update_plot()

    leads = drawn_widths(w.canvas.ax, 'indianred')
    assert leads
    assert max(leads) == pytest.approx(w.wire_style(att)[1], rel=0.01)


# ---------------------------------------------------------------------------
# arrow keys on a selected wire
# ---------------------------------------------------------------------------

def test_up_down_adjusts_a_selected_wire_width(win):
    w, _config = win
    node = add_node(w, 'A', (6.0, 0.0))
    port = w.add_port(pos=(-6.0, 0.0))
    conn = w.connect_port_to_node(port, node)
    w.selected_wires = [(port, conn)]

    before = conn['linewidth_mult']
    w._pan_arrow('up')
    assert conn['linewidth_mult'] > before
    w._pan_arrow('down')
    w._pan_arrow('down')
    assert conn['linewidth_mult'] < before


def test_left_right_adjusts_a_selected_wire_label_size(win):
    w, _config = win
    node = add_node(w, 'A', (6.0, 0.0))
    port = w.add_port(pos=(-6.0, 0.0))
    conn = w.connect_port_to_node(port, node)
    w.selected_wires = [(port, conn)]

    before = conn.get('label_size_mult', 1.0)
    w._pan_arrow('right')
    assert conn['label_size_mult'] > before


def test_one_arrow_press_is_one_undo_step(win):
    w, _config = win
    node = add_node(w, 'A', (6.0, 0.0))
    port = w.add_port(pos=(-6.0, 0.0))
    conn = w.connect_port_to_node(port, node)
    w.selected_wires = [(port, conn)]
    before = len(w.undo_stack)
    w._pan_arrow('up')
    assert len(w.undo_stack) == before + 1


def test_the_arrow_keys_still_pan_with_nothing_selected(win):
    w, _config = win
    assert w._adjust_wire_properties('up') is False


def test_up_down_adjusts_a_selected_attachment_in_para(para):
    w, _config = para
    node = add_node(w, 'A', (6.0, 0.0))
    port = w.add_port(pos=(-6.0, 0.0))
    att = w.add_port_attachment(port, node)
    w.selected_attachments = [(port, att)]

    before = w.wire_style(att)[1]
    w._pan_arrow('up')
    assert w.wire_style(att)[1] > before


def test_up_down_adjusts_a_selected_tap_in_para(para):
    w, _config = para
    node = add_node(w, 'A', (6.0, 0.0))
    w.scattering_assignments[node['node_id']] = {'freq': 5.0, 'B_int': 0.0}
    line = w.add_line_resonator(label='TL1', pos=(0.0, -8.0),
                                port_end=None, FSR=1.0, f_max=8.0)
    conn = w.connect_line_end_to_node(line, 'xL', node)
    w.selected_taps = [(line, 'xL', conn)]

    before = w.wire_style(conn)[1]
    w._pan_arrow('up')
    assert w.wire_style(conn)[1] > before


def test_a_selected_attachment_draws_no_dot_in_para(para):
    """The halo along the wire already says which one is selected."""
    from matplotlib.colors import to_rgb
    w, _config = para
    node = add_node(w, 'A', (6.0, 0.0))
    port = w.add_port(pos=(-6.0, 0.0))
    att = w.add_port_attachment(port, node)
    w.selected_attachments = [(port, att)]
    w._update_plot()

    assert halo_artists(w.canvas.ax)
    assert not [p for p in w.canvas.ax.patches
                if type(p).__name__ == 'Circle'
                and tuple(p.get_facecolor()[:3]) == to_rgb('lightcoral')]
