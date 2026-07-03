"""Tests for graph_primitives compound-path edges and arrowhead styles.

The edge curve and its arrowhead are drawn as ONE compound Path in a single
PathPatch so vector exports (SVG) keep them together as one group. These
tests pin the geometry conventions and the SVG structure. Qt-free (Agg).
"""

import io
import math

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402
from matplotlib.path import Path  # noqa: E402

from graphulator import graph_primitives as gp  # noqa: E402

V = [[-1.0, 0.0], [2.0, 1.0]]
THETA = [90 + 34, 90 - 34]


def make_ax():
    fig = plt.figure()
    ax = fig.add_subplot(111)
    return fig, ax


@pytest.mark.parametrize("style", ["open", "filled", "stealth"])
def test_one_patch_per_edge(style):
    fig, ax = make_ax()
    patch = gp.looparrow(ax=ax, vstartend=V, theta=THETA, arrowstyle=style)
    assert len(ax.patches) == 1
    assert ax.patches[0] is patch
    assert len(ax.lines) == 0  # the old implementation used ax.plot for heads
    plt.close(fig)


@pytest.mark.parametrize("style", ["open", "filled", "stealth"])
def test_tip_is_curve_endpoint(style):
    fig, ax = make_ax()
    patch = gp.looparrow(ax=ax, vstartend=V, theta=THETA, arrowstyle=style)
    verts = patch.get_path().vertices
    # The curve's last vertex (index 3) is the endpoint; the head subpath
    # must include the same tip point.
    assert np.allclose(verts[3], V[1])
    assert any(np.allclose(v, V[1]) for v in verts[4:])
    plt.close(fig)


def test_filled_styles_are_filled_and_closed():
    for style in ("filled", "stealth"):
        fig, ax = make_ax()
        patch = gp.looparrow(ax=ax, vstartend=V, theta=THETA,
                             arrowstyle=style, color="black")
        codes = patch.get_path().codes
        assert Path.CLOSEPOLY in codes
        assert patch.get_facecolor()[3] > 0  # filled with the edge color
        plt.close(fig)


def test_open_style_is_unfilled():
    fig, ax = make_ax()
    patch = gp.looparrow(ax=ax, vstartend=V, theta=THETA, arrowstyle="open")
    assert patch.get_facecolor()[3] == 0
    assert Path.CLOSEPOLY not in patch.get_path().codes
    plt.close(fig)


def test_filled_retraces_curve_for_zero_winding():
    """Filled heads must retrace the Bezier so the open curve doesn't fill."""
    fig, ax = make_ax()
    open_patch = gp.looparrow(ax=ax, vstartend=V, theta=THETA, arrowstyle="open")
    filled_patch = gp.looparrow(ax=ax, vstartend=V, theta=THETA, arrowstyle="filled")
    n_open = len(open_patch.get_path().vertices)     # 4 curve + 3 head
    n_filled = len(filled_patch.get_path().vertices)  # 4 curve + 3 retrace + 4 head
    assert n_open == 7
    assert n_filled == 11
    # The retrace is the reversed curve control polygon
    verts = filled_patch.get_path().vertices
    assert np.allclose(verts[6], verts[0])  # retrace ends at the start point
    plt.close(fig)


def test_arrowscale_scales_barb_distance():
    fig, ax = make_ax()
    p1 = gp.looparrow(ax=ax, vstartend=V, theta=THETA, arrowstyle="open",
                      arrowlength=0.4, arrowscale=1.0)
    p2 = gp.looparrow(ax=ax, vstartend=V, theta=THETA, arrowstyle="open",
                      arrowlength=0.4, arrowscale=2.0)
    tip = np.asarray(V[1])
    barb1 = np.linalg.norm(p1.get_path().vertices[4] - tip)
    barb2 = np.linalg.norm(p2.get_path().vertices[4] - tip)
    assert barb2 == pytest.approx(2 * barb1)
    plt.close(fig)


def test_arrowopenang_changes_barb_spread():
    fig, ax = make_ax()
    narrow = gp.looparrow(ax=ax, vstartend=V, theta=THETA, arrowopenang=30.0)
    wide = gp.looparrow(ax=ax, vstartend=V, theta=THETA, arrowopenang=90.0)
    def spread(patch):
        verts = patch.get_path().vertices
        return np.linalg.norm(verts[4] - verts[6])  # barb-to-barb distance
    assert spread(wide) > spread(narrow)
    plt.close(fig)


def test_legacy_open_head_geometry_preserved():
    """The default 'open' style must reproduce the legacy arrowhead math."""
    fig, ax = make_ax()
    patch = gp.looparrow(ax=ax, vstartend=V, theta=THETA, arrowstyle="open",
                         arrowlength=0.4, arrowthetatweak=-8)
    # Legacy convention (old arrowhead()): tip at v[1], tangent 180-theta[1],
    # openang 60, L = length/cos(30 deg)
    th = (180 - THETA[1]) + (-8)
    L = 0.4 / math.cos(30 * math.pi / 180)
    th0 = th + 30
    expected_barb = (V[1][0] - L * math.cos(th0 * math.pi / 180),
                     V[1][1] + L * math.sin(th0 * math.pi / 180))
    assert np.allclose(patch.get_path().vertices[4], expected_barb)
    plt.close(fig)


def test_gid_propagates_and_svg_groups_edge_with_head():
    fig, ax = make_ax()
    patch = gp.selfloop(ax=ax, nodecent=[0, 0], R=1.0, loopR=6.0,
                        arrowlength=0.5, gid="edge_0")
    assert patch.get_gid() == "edge_0"
    ax.set_xlim(-10, 10)
    ax.set_ylim(-10, 10)
    buf = io.StringIO()
    fig.savefig(buf, format="svg")
    svg = buf.getvalue()
    assert svg.count('id="edge_0"') == 1
    plt.close(fig)


def test_edge_gid_suffixes():
    fig, ax = make_ax()
    gp.edge(ax=ax, nodexy=[(-4, 0), (4, 0)], nodeR=[2, 2], style="loopy",
            whichedges="both", label=[None, None], gid="edge_3",
            loopkwargs={"lw": 2.0, "arrowlength": 0.4})
    gids = {p.get_gid() for p in ax.patches}
    assert {"edge_3_fore", "edge_3_back"} <= gids
    plt.close(fig)


def test_legacy_api_still_callable():
    """Old signatures used by notebooks/exported code keep working."""
    fig, ax = make_ax()
    gp.drawloop(ax=ax, v=V, R=[2, 2], theta=THETA, lw=2)
    gp.arrowhead(ax=ax, v=[0, 0], theta=45, openang=60, lw=2, length=0.4)
    gp.looparrow(ax=ax, vstartend=V, R=[2, 2], theta=THETA, lw=3.0,
                 arrowlength=0.4, arrowthetatweak=0, color="black", alpha=1.0)
    gp.selfloop(ax=ax, baseangle=90, dtheta=-34, nodecent=[0, 0], R=1.2,
                loopR=6.0, arrowlength=0.3, color="black", lw=2, flip=False)
    plt.close(fig)


def test_double_style_uses_flush_butt_caps():
    """The double-line kludge (fat stroke + longer white overlay) only reads
    as two open-ended rails when both strokes end flush; round caps would
    bulge the fat stroke past the white stripe (regression seen in the field).
    """
    fig, ax = make_ax()
    gp.edge(ax=ax, nodexy=[(-4, 0), (4, 0)], nodeR=[2, 2], style="double",
            whichedges="both", label=[None, None],
            loopkwargs={"lw": 6.0, "arrowlength": 0.4})
    assert len(ax.patches) == 2  # fat colored pass + thin white overlay
    for p in ax.patches:
        assert p.get_capstyle() == "butt"
    whites = [p for p in ax.patches
              if p.get_edgecolor()[:3] == (1.0, 1.0, 1.0)]
    assert len(whites) == 1
    fat = next(p for p in ax.patches if p is not whites[0])
    assert fat.get_linewidth() > whites[0].get_linewidth()
    plt.close(fig)


def test_single_style_uses_flush_butt_caps():
    fig, ax = make_ax()
    gp.edge(ax=ax, nodexy=[(-4, 0), (4, 0)], nodeR=[2, 2], style="single",
            whichedges="both", label=[None, None],
            loopkwargs={"lw": 6.0, "arrowlength": 0.4})
    assert len(ax.patches) == 1
    assert ax.patches[0].get_capstyle() == "butt"
    plt.close(fig)


def test_loopy_style_keeps_round_caps():
    """Loopy edges carry the arrowhead in the same compound patch; round
    caps are the verified rendering for the stroked open-V head.
    """
    fig, ax = make_ax()
    gp.edge(ax=ax, nodexy=[(-4, 0), (4, 0)], nodeR=[2, 2], style="loopy",
            whichedges="both", label=[None, None],
            loopkwargs={"lw": 2.0, "arrowlength": 0.4})
    assert len(ax.patches) == 2
    for p in ax.patches:
        assert p.get_capstyle() == "round"
    plt.close(fig)
