"""Tests for the schematic glyph primitives in graph_primitives.

Covers the port/txline shapes, the cubic-bezier wire routing, and the
GraphCircuit container's glyph bookkeeping (anchor resolution, port
auto-orientation, end marks, axis extents). Qt-free (Agg).
"""

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402

from graphulator import graph_primitives as gp  # noqa: E402

R = 2.0


def make_ax():
    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111)
    ax.set_xlim(-20, 20)
    ax.set_ylim(-20, 20)
    return fig, ax


# ---------------------------------------------------------------------------
# shapes
# ---------------------------------------------------------------------------

def test_port_apex_is_beyond_the_body():
    x, y, w, h, apex_x = gp.portgeometry((0, 0), R)
    assert apex_x > w / 2            # nose sticks out past the body
    assert apex_x == pytest.approx(w / 2 + gp.PORT_APEX_W * R)


def test_port_apex_rotates_with_the_glyph():
    tip0, tan0 = gp.portapex((0, 0), R, angle=0.0)
    tip90, tan90 = gp.portapex((0, 0), R, angle=90.0)
    # the apex swings a quarter turn about the glyph center...
    assert tip90[0] == pytest.approx(0.0, abs=1e-9)
    assert tip90[1] == pytest.approx(tip0[0])
    # ...and so does the outward tangent
    assert tan0 == pytest.approx((1.0, 0.0), abs=1e-9)
    assert tan90 == pytest.approx((0.0, 1.0), abs=1e-9)


def test_a_ports_wire_anchors_inside_its_body():
    """The anchor is buried in the filled polygon so the stroke's end cap is
    hidden and the visible wire starts at the point of the pentagon."""
    x, y, w, h, apex_x = gp.portgeometry((0, 0), R)
    anchor, tangent = gp.portwirestart((0, 0), R, angle=0.0)
    assert -w / 2 < anchor[0] < apex_x          # strictly inside the outline
    assert abs(anchor[1]) < h / 2
    # and it aims straight out through the apex
    assert tangent == pytest.approx((1.0, 0.0), abs=1e-9)
    assert anchor[0] < gp.portapex((0, 0), R, angle=0.0)[0][0]


def test_port_length_and_height_stretch_independently():
    _, _, w1, h1, _ = gp.portgeometry((0, 0), R, length=2.0, height=1.0)
    _, _, w2, h2, _ = gp.portgeometry((0, 0), R, length=1.0, height=2.0)
    assert w1 == pytest.approx(2 * w2)
    assert h2 == pytest.approx(2 * h1)


def test_txline_ends_point_outward_along_the_axis():
    ends = gp.txlineendpoints((0, 0), R, angle=0.0)
    (p0, t0), (pL, tL) = ends['x0'], ends['xL']
    assert p0[0] < 0 < pL[0]
    assert t0 == pytest.approx((-1.0, 0.0), abs=1e-9)
    assert tL == pytest.approx((1.0, 0.0), abs=1e-9)
    # the two stubs are symmetric about the glyph center
    assert p0[0] == pytest.approx(-pL[0])


def test_txline_length_stretch_moves_the_ends_not_the_stub():
    short = gp.txlineendpoints((0, 0), R, length=1.0)['xL'][0][0]
    long_ = gp.txlineendpoints((0, 0), R, length=2.0)['xL'][0][0]
    # the body doubles; the fixed-length stub does not
    assert long_ - short == pytest.approx(gp.TXLINE_BODY_W * R)


def test_port_draws_a_five_sided_body_and_nothing_else():
    """The port is the pentagon alone. It used to own a lead stub, whose
    width had to be kept in visual agreement with every wire that met it;
    now the line leaving a port IS the connection's own stroke."""
    fig, ax = make_ax()
    info = gp.port(ax=ax, xy=(0, 0), R=R, label='P1')
    polys = [p for p in ax.patches if isinstance(p, matplotlib.patches.Polygon)]
    assert len(polys) == 1
    assert len(polys[0].get_xy()) in (5, 6)   # matplotlib may repeat vertex 0
    assert len(ax.lines) == 0                 # no lead
    assert info['apex'][0] > 0
    plt.close(fig)


def test_txline_draws_a_closed_cap_and_an_open_mouth():
    fig, ax = make_ax()
    gp.txline(ax=ax, xy=(0, 0), R=R, label='TL1', drawendmarks=False)
    arcs = [p for p in ax.patches if isinstance(p, matplotlib.patches.Arc)]
    ellipses = [p for p in ax.patches
                if isinstance(p, matplotlib.patches.Ellipse)
                and not isinstance(p, matplotlib.patches.Arc)]
    assert len(arcs) == 1        # closed (left) cap, drawn as a half-ellipse
    # body fill ellipse + the open mouth
    assert len(ellipses) == 2
    mouth = max(ellipses, key=lambda e: e.center[0])
    assert mouth.get_facecolor()[:3] == (1.0, 1.0, 1.0)   # open == white
    plt.close(fig)


def test_txline_end_marks_are_filled_only_where_named():
    fig, ax = make_ax()
    gp.txline(ax=ax, xy=(0, 0), R=R, endmarks=('x0',))
    circles = [p for p in ax.patches
               if isinstance(p, matplotlib.patches.Circle)]
    assert len(circles) == 2
    left, right = sorted(circles, key=lambda c: c.center[0])
    assert left.get_facecolor()[:3] != (1.0, 1.0, 1.0)     # terminated
    assert right.get_facecolor()[:3] == (1.0, 1.0, 1.0)    # open
    plt.close(fig)


def test_readable_angle_folds_upside_down_text():
    assert gp.readableangle(0) == 0
    assert gp.readableangle(45) == 45
    assert gp.readableangle(180) == pytest.approx(0)
    assert gp.readableangle(200) == pytest.approx(20)
    assert gp.readableangle(300) == pytest.approx(300)


# ---------------------------------------------------------------------------
# wire routing
# ---------------------------------------------------------------------------

def test_wire_starts_and_ends_on_its_anchors():
    pts = gp.wirepoints((0, 0), (1, 0), (10, 5), (1, 0), R=R)
    assert pts[0] == pytest.approx((0, 0))
    assert pts[-1] == pytest.approx((10, 5))


def _unit(v):
    return np.asarray(v, dtype=float) / np.hypot(*v)


def test_wire_leaves_colinear_with_the_lead():
    """The defining property: the wire sets off along t0, not toward the
    target. That is what makes a fan out of one port collimate.

    A sampled curve is only tangent to t0 in the limit, so the first chord
    is checked at a high sample count.
    """
    t0 = (0.0, 1.0)
    pts = gp.wirepoints((0, 0), t0, (10, 0), (1, 0), R=R, samples=4001)
    assert _unit(pts[1] - pts[0]) == pytest.approx(np.array(t0), abs=1e-3)


def test_wire_arrives_along_the_target_tangent():
    t1 = np.array([1.0, 0.0])
    pts = gp.wirepoints((0, 10), (0, -1), (10, 0), t1, R=R, samples=4001)
    assert _unit(pts[-1] - pts[-2]) == pytest.approx(t1, abs=1e-3)


def test_wire_tangents_converge_with_sampling():
    """The sampled chord approaches the exact tangent as samples grow --
    i.e. the 33-sample default is a drawing resolution, not a different
    curve."""
    t0 = np.array([0.0, 1.0])
    errs = []
    for n in (33, 129, 513):
        pts = gp.wirepoints((0, 0), t0, (10, 0), (1, 0), R=R, samples=n)
        errs.append(np.hypot(*(_unit(pts[1] - pts[0]) - t0)))
    assert errs[0] > errs[1] > errs[2]
    assert errs[0] < 0.1          # even the default is visually colinear


def test_node_wire_end_lands_on_the_circle_facing_the_source():
    pt, tan = gp.nodewireend((0, 0), R, toward=(10, 0))
    assert pt == pytest.approx((R, 0.0))
    assert tan == pytest.approx((-1.0, 0.0))   # travelling INTO the node


# ---------------------------------------------------------------------------
# GraphCircuit integration
# ---------------------------------------------------------------------------

def make_circuit():
    g = gp.GraphCircuit(allow_duplicate_labels=True)
    g.addnode(label='A', xy=(0, 0), R=R, node_id=0, drawselfloop=False)
    g.addnode(label='B', xy=(12, 0), R=R, node_id=1, drawselfloop=False)
    return g


def test_wire_anchors_resolve_by_label_and_by_id():
    g = make_circuit()
    g.addport(label='P1', xy=(-10, 0), R=R)
    by_label = g._wireanchor(('port', 'P1'))
    by_id = g._wireanchor(('port', 0))
    assert by_label[0] == pytest.approx(by_id[0])

    node_by_label = g._wireanchor(('node', 'A'), toward=(10, 0))
    node_by_id = g._wireanchor(('node', 0), toward=(10, 0))
    assert node_by_label[0] == pytest.approx(node_by_id[0])


def test_unknown_anchor_raises():
    g = make_circuit()
    with pytest.raises(ValueError):
        g._wireanchor(('port', 'nope'))
    with pytest.raises(ValueError):
        g._wireanchor(('sprocket', 'A'))


def test_autoorient_aims_the_lead_at_a_single_target():
    g = make_circuit()
    g.addport(label='P1', xy=(-10, 0), R=R, autoorient=True)
    g.addwire(start=('port', 'P1'), end=('node', 'A'))
    # A sits due east of the port
    assert g._portangle(g.ports[0]) == pytest.approx(0.0, abs=1e-9)


def test_autoorient_aims_at_the_centroid_of_several_targets():
    g = make_circuit()
    g.addnode(label='C', xy=(0, 10), R=R, node_id=2, drawselfloop=False)
    g.addport(label='P1', xy=(-10, 5), R=R, autoorient=True)
    g.addwire(start=('port', 'P1'), end=('node', 'A'))     # (0, 0)
    g.addwire(start=('port', 'P1'), end=('node', 'C'))     # (0, 10)
    # centroid (0, 5) is due east of the port at (-10, 5)
    assert g._portangle(g.ports[0]) == pytest.approx(0.0, abs=1e-9)


def test_autoorient_is_off_when_not_requested():
    g = make_circuit()
    g.addport(label='P1', xy=(-10, 0), R=R, angle=123.0)
    g.addwire(start=('port', 'P1'), end=('node', 'A'))
    assert g._portangle(g.ports[0]) == pytest.approx(123.0)


def test_autoorient_falls_back_to_the_stored_angle_when_unwired():
    g = make_circuit()
    g.addport(label='P1', xy=(-10, 0), R=R, angle=45.0, autoorient=True)
    assert g._portangle(g.ports[0]) == pytest.approx(45.0)


def test_terminated_txline_ends_are_the_wired_ones():
    g = make_circuit()
    g.addtxline(label='TL1', xy=(0, -10), R=R)
    g.addwire(start=('txline', 'TL1', 'xL'), end=('node', 'B'))
    assert g._terminatedtxlineends(g.txlines[0]) == ('xL',)


def test_draw_emits_glyphs_and_wires():
    g = make_circuit()
    g.addport(label='P1', xy=(-10, 0), R=R, autoorient=True)
    g.addtxline(label='TL1', xy=(0, -10), R=R)
    g.addwire(start=('port', 'P1'), end=('node', 'A'))
    g.addwire(start=('txline', 'TL1', 'xL'), end=('node', 'B'))
    g.addwire(start=('txline', 'TL1', 'x0'), end=('port', 'P1'))
    g.draw(figsize=8, overfrac=0.2)
    # 2 nodes + port body + txline caps/mouth/marks are patches; the three
    # wires and the txline rails/stubs are Line2Ds
    assert len(g.ax.lines) >= 3
    assert len(g.ax.patches) >= 5
    plt.close(g.ax.figure)


def test_axes_grow_to_include_a_long_txline():
    g = make_circuit()
    g.draw(figsize=8, overfrac=0.0)
    without = g.ax.get_ylim()
    plt.close(g.ax.figure)

    g2 = make_circuit()
    g2.addtxline(label='TL1', xy=(0, -40), R=R)
    g2.draw(figsize=8, overfrac=0.0)
    with_txline = g2.ax.get_ylim()
    plt.close(g2.ax.figure)

    assert with_txline[0] < without[0] - 20


def test_a_glyph_only_circuit_draws_without_nodes():
    g = gp.GraphCircuit()
    g.addport(label='P1', xy=(-6, 0), R=R)
    g.addtxline(label='TL1', xy=(4, 0), R=R)
    g.addwire(start=('txline', 'TL1', 'x0'), end=('port', 'P1'))
    g.draw(figsize=6, overfrac=0.2)     # must not raise on an empty node list
    assert g.ax.get_xlim()[0] < -6
    plt.close(g.ax.figure)


def test_glyph_R_falls_back_to_the_node_radius():
    g = gp.GraphCircuit()
    g.nodeprefs['R'] = 3.0
    term = g.addport(label='P1', xy=(0, 0))
    assert term['R'] == 3.0


def test_mathboldlabel_wraps_scripts_separately():
    assert gp.mathboldlabel('A') == r'\mathbf{\mathsf{A}}'
    out = gp.mathboldlabel('A_{12}')
    assert out.count('_') == 1
    assert out.startswith(r'\mathbf{\mathsf{A}}_{')
    assert gp.mathboldlabel('A', use_latex=True) == r'\mathbf{A}'


# ---------------------------------------------------------------------------
# the open mouth is a bore, not a disc
# ---------------------------------------------------------------------------

def _mouth_stub(ax):
    """The txline's right-hand stub: the longest line right of center."""
    return max(ax.lines, key=lambda ln: max(ln.get_xdata()))


def test_mouth_stub_starts_at_the_bore_center(fig_ax=None):
    fig, ax = make_ax()
    gp.txline(ax=ax, xy=(0, 0), R=R, height=3.0, drawendmarks=False)
    x, y, w, h, rx = gp.txlinegeometry((0, 0), R, 1.0, 3.0)

    stub = _mouth_stub(ax)
    xs = stub.get_xdata()
    # it begins at the CENTER of the mouth ellipse, not at its rim
    assert min(xs) == pytest.approx(x + w)
    assert min(xs) < (x + w + rx)
    plt.close(fig)


def test_mouth_stub_is_drawn_in_front_of_the_mouth_with_a_round_cap():
    fig, ax = make_ax()
    gp.txline(ax=ax, xy=(0, 0), R=R, height=3.0, drawendmarks=False)
    mouth = max((p for p in ax.patches
                 if isinstance(p, matplotlib.patches.Ellipse)
                 and not isinstance(p, matplotlib.patches.Arc)),
                key=lambda e: e.center[0])
    stub = _mouth_stub(ax)
    assert stub.get_zorder() > mouth.get_zorder()
    assert stub.get_solid_capstyle() == 'round'
    plt.close(fig)


def test_the_closed_cap_stub_still_leaves_the_outer_surface():
    fig, ax = make_ax()
    gp.txline(ax=ax, xy=(0, 0), R=R, height=3.0, drawendmarks=False)
    x, y, w, h, rx = gp.txlinegeometry((0, 0), R, 1.0, 3.0)
    left = min(ax.lines, key=lambda ln: min(ln.get_xdata()))
    # the closed end IS a surface, so its stub starts on the cap, not inside
    assert max(left.get_xdata()) == pytest.approx(x - w - rx)
    plt.close(fig)


def test_the_stub_tips_are_unchanged_by_the_bore_fix():
    """The wire attach points must not move: the end-drag maths and every
    saved graph depend on them."""
    ends = gp.txlineendpoints((0, 0), R, height=3.0)
    x, y, w, h, rx = gp.txlinegeometry((0, 0), R, 1.0, 3.0)
    assert ends['xL'][0][0] == pytest.approx(x + w + rx + gp.TXLINE_LEAD_LEN * R)


# ---------------------------------------------------------------------------
# txline label sizing
# ---------------------------------------------------------------------------

def _label_fontsize(ax):
    """The primitive draws its label with ax.text, so the requested point
    size is readable straight off the artist."""
    assert ax.texts, "no label was drawn"
    return ax.texts[-1].get_fontsize()


def test_txline_label_grows_with_the_body_height():
    """It used to be clamped at 1.1 R, so stretching the body left the label
    stranded at a fixed size."""
    heights = []
    for height in (2.0, 4.0):
        fig, ax = make_ax()
        gp.txline(ax=ax, xy=(0, 0), R=R, height=height, label='X')
        heights.append(_label_fontsize(ax))
        plt.close(fig)
    assert heights[1] > 1.5 * heights[0]


def test_txline_labelscale_scales_the_label():
    sizes = []
    for scale in (0.5, 2.0):
        fig, ax = make_ax()
        gp.txline(ax=ax, xy=(0, 0), R=R, height=3.0, label='X',
                  labelscale=scale)
        sizes.append(_label_fontsize(ax))
        plt.close(fig)
    assert sizes[1] == pytest.approx(4 * sizes[0], rel=0.05)


def test_a_long_txline_label_is_capped_by_the_body_length():
    """Growing with height must not let a long label spill out the ends."""
    fig, ax = make_ax()
    gp.txline(ax=ax, xy=(0, 0), R=R, height=6.0, length=0.4,
              label='LONGLABEL')
    _, _, w, _, _ = gp.txlinegeometry((0, 0), R, 0.4, 6.0)
    ppdu = gp.pointsperdataunit(ax)
    # the drawn text is no wider than the body it sits in
    width_data = (gp.GLYPH_LABEL_ADVANCE * len('LONGLABEL')
                  * _label_fontsize(ax) / ppdu)
    assert width_data <= 2 * w
    plt.close(fig)


def test_a_short_label_in_a_tall_body_is_not_capped():
    """The width cap must not silently undo the height scaling."""
    fig, ax = make_ax()
    gp.txline(ax=ax, xy=(0, 0), R=R, height=6.0, label='X')
    _, _, _, h, _ = gp.txlinegeometry((0, 0), R, 1.0, 6.0)
    ppdu = gp.pointsperdataunit(ax)
    expected = 2 * h * ppdu * gp.GLYPH_LABEL_SCALE * 1.6
    assert _label_fontsize(ax) == pytest.approx(expected)
    plt.close(fig)
