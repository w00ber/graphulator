"""Image exports are rendered at an ABSOLUTE scale, not at the canvas zoom.

The canvas is a Qt widget, so its figure is whatever size the window is and
its view spans whatever the zoom says. Exports rendered that live figure,
so the same graph came out 1.65 in wide at 0.5x zoom and 6.6 in at 2x --
self-similar, but a size nobody chose. Every image export now pins the
figure to REFERENCE_POINTS_PER_DATA_UNIT x the Settings multiplier, which
is also the scale at which stored line widths arrive as literal points.
Headless (offscreen Qt + Agg).
"""

import io
import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    # QtWebEngine refuses to sandbox as root (CI containers)
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")


@pytest.fixture()
def win(tmp_path):
    """Graphulator."""
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    import graphulator.graphulator_qt as gq

    w = gq.Graphulator()
    w.last_graph_path = tmp_path / "last.graph"
    w.recent_files_path = tmp_path / "recent"
    return w


@pytest.fixture()
def para(tmp_path):
    """Paragraphulator."""
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    import graphulator.graphulator_para as gp

    w = gp.Graphulator()
    w.last_graph_path = tmp_path / "last.pgraph"
    w.recent_files_path = tmp_path / "recent"
    return w


@pytest.fixture()
def scale(monkeypatch):
    """Set the export multiplier without leaking it into other tests."""
    def _set(w, value):
        monkeypatch.setattr(w.APP_CONFIG, 'IMAGE_EXPORT_SCALE', value,
                            raising=False)
    return _set


def add_node(w, label, pos):
    node = {'node_id': w.node_id_counter, 'label': label, 'pos': pos,
            'color': '#6699ff', 'color_key': 'BLUE', 'node_size_mult': 1.0,
            'label_size_mult': 1.0, 'conj': False,
            'nodelabelnudge': (0.0, 0.0)}
    w.nodes.append(node)
    if hasattr(w, 'scattering_assignments'):
        w.scattering_assignments[node['node_id']] = {'freq': 5.0,
                                                     'B_int': 0.0}
    w.node_id_counter += 1
    return node


def scene(w):
    a = add_node(w, 'A', (0.0, 0.0))
    b = add_node(w, 'B', (4.0, 0.0))
    w.edges.append({'from_node': a, 'to_node': b, 'from_node_id': a['node_id'],
                    'to_node_id': b['node_id'], 'label1': 'g', 'label2': '',
                    'linewidth_mult': 1.0, 'label_size_mult': 1.0,
                    'label_offset_mult': 1.0, 'style': 'solid',
                    'direction': 'none', 'looptheta': 30,
                    'is_self_loop': False})
    return a, b


def svg_size(w):
    """(width, height) in points of what an export of `w` would produce."""
    with w._image_export_scope() as bbox:
        buf = io.BytesIO()
        w.canvas.fig.savefig(buf, format='svg', bbox_inches=bbox,
                             transparent=True)
    text = buf.getvalue().decode('utf8', 'replace')
    match = re.search(r'width="([\d.]+)pt" height="([\d.]+)pt"', text)
    assert match, "no size in the exported SVG"
    return float(match.group(1)), float(match.group(2))


# ---------------------------------------------------------------------------
# the pinned scale
# ---------------------------------------------------------------------------

def test_the_export_view_is_exactly_the_reference_scale(win):
    from graphulator.common_window import REFERENCE_POINTS_PER_DATA_UNIT

    scene(win)
    win.zoom_level = 2.7
    with win._absolute_scale_export_scope() as target:
        win._update_plot_no_grid()
        ppdu = win._points_per_data_unit(win.canvas.ax.get_xlim(),
                                         win.canvas.ax.get_ylim())
    assert target == pytest.approx(REFERENCE_POINTS_PER_DATA_UNIT)
    assert ppdu == pytest.approx(REFERENCE_POINTS_PER_DATA_UNIT)


def test_stored_line_widths_become_literal_points(win):
    """lw_scale == 1 at the reference scale is the whole reason for picking
    43: a stored width of 5.5 reaches Illustrator as 5.5 pt."""
    scene(win)
    win.zoom_level = 0.31
    with win._absolute_scale_export_scope():
        win._update_plot_no_grid()
        assert win._zoom_lw_scale() == pytest.approx(1.0)


def test_the_export_size_ignores_the_zoom(win):
    scene(win)
    sizes = set()
    for zoom in (0.5, 1.0, 2.0, 3.7):
        win.zoom_level = zoom
        sizes.add(svg_size(win))
    assert len(sizes) == 1, sizes


def test_the_export_size_ignores_the_window_size(win):
    """The Qt canvas resizes its figure, so the figure is whatever shape the
    window is; the export must not inherit that."""
    scene(win)
    win.canvas.fig.set_size_inches(9.0, 6.0, forward=False)
    narrow = svg_size(win)
    win.canvas.fig.set_size_inches(14.0, 14.0, forward=False)
    wide = svg_size(win)
    assert narrow == pytest.approx(wide)


def test_the_export_size_ignores_the_pan(win):
    scene(win)
    before = svg_size(win)
    win.base_xlim = (win.base_xlim[0] + 37, win.base_xlim[1] + 37)
    win.base_ylim = (win.base_ylim[0] - 21, win.base_ylim[1] - 21)
    for node in win.nodes:
        node['pos'] = (node['pos'][0] + 37, node['pos'][1] - 21)
    assert svg_size(win) == pytest.approx(before)


def test_the_multiplier_scales_the_export_linearly(win, scale):
    scene(win)
    scale(win, 1.0)
    base_w, base_h = svg_size(win)
    scale(win, 2.0)
    assert svg_size(win) == pytest.approx((2 * base_w, 2 * base_h))
    scale(win, 0.5)
    assert svg_size(win) == pytest.approx((base_w / 2, base_h / 2))


def test_the_multiplier_scales_the_strokes_with_it(win, scale):
    """Proportions never change -- only the overall size."""
    scene(win)
    for value, expected in ((0.5, 0.5), (1.0, 1.0), (2.0, 2.0)):
        scale(win, value)
        with win._absolute_scale_export_scope():
            win._update_plot_no_grid()
            assert win._zoom_lw_scale() == pytest.approx(expected)


def test_a_nonsense_multiplier_falls_back_to_one(win, scale):
    scene(win)
    for bad in (0.0, -2.0, None, 'big'):
        scale(win, bad)
        assert win._image_export_scale() == 1.0


# ---------------------------------------------------------------------------
# the canvas is handed back untouched
# ---------------------------------------------------------------------------

def test_the_figure_and_the_view_come_back(win):
    scene(win)
    win.canvas.fig.set_size_inches(9.0, 6.0, forward=False)
    win.zoom_level = 2.5
    win.base_xlim, win.base_ylim = (-3.0, 9.0), (-4.0, 8.0)
    svg_size(win)
    assert tuple(win.canvas.fig.get_size_inches()) == (9.0, 6.0)
    assert win.zoom_level == 2.5
    assert win.base_xlim == (-3.0, 9.0) and win.base_ylim == (-4.0, 8.0)


def test_the_title_comes_back_even_when_the_export_raises(win):
    scene(win)
    win.canvas.ax.set_title('Figure 3')
    with pytest.raises(RuntimeError):
        with win._image_export_scope():
            raise RuntimeError("savefig blew up")
    assert win.canvas.ax.get_title() == 'Figure 3'
    assert tuple(win.canvas.fig.get_size_inches()) != (0, 0)


def test_the_scope_centres_on_the_drawing_not_the_origin(win):
    """A graph parked far from (0, 0) still lands inside the figure."""
    add_node(win, 'A', (120.0, -80.0))
    with win._absolute_scale_export_scope():
        xlim, ylim = win._get_xlim(), win._get_ylim()
    assert xlim[0] < 120.0 < xlim[1]
    assert ylim[0] < -80.0 < ylim[1]


def test_an_empty_graph_falls_back_to_the_current_view(win):
    centre = win._image_export_centre()
    xlim, ylim = win._get_xlim(), win._get_ylim()
    assert centre == pytest.approx(((xlim[0] + xlim[1]) / 2,
                                    (ylim[0] + ylim[1]) / 2))


# ---------------------------------------------------------------------------
# a drawing larger than the export figure still exports whole
# ---------------------------------------------------------------------------

def test_a_graph_wider_than_the_figure_exports_in_full(win):
    """The figure is held at a fixed size so the render buffer stays
    bounded; the crop box is measured from the artists and may reach past
    the figure edge, which matplotlib honors."""
    for i, x in enumerate(range(-20, 21, 5)):
        add_node(win, chr(ord('A') + i), (float(x), 0.0))
    width, _height = svg_size(win)
    # 40 units of nodes at 43 pt per unit is far wider than 12 in (864 pt)
    assert width > 1500
    assert tuple(win.canvas.fig.get_size_inches()) != (0, 0)


def test_the_raster_dpi_is_capped_for_a_big_export(win):
    from matplotlib.transforms import Bbox

    assert win._image_export_dpi(Bbox.from_extents(0, 0, 5, 5)) == 300
    big = win._image_export_dpi(Bbox.from_extents(0, 0, 30, 30))
    assert big < 300
    assert 30 * big <= win.IMAGE_EXPORT_MAX_RASTER_PX
    # 'tight' has no measurable size yet, so the request stands
    assert win._image_export_dpi('tight') == 300


# ---------------------------------------------------------------------------
# paragraphulator
# ---------------------------------------------------------------------------

def test_the_export_size_ignores_the_zoom_in_para(para):
    scene(para)
    para.add_port(label='P1', pos=(-6.0, 0.0))
    sizes = {z: (para.__setattr__('zoom_level', z), svg_size(para))[1]
             for z in (0.5, 1.0, 2.0)}
    assert len(set(sizes.values())) == 1, sizes


def test_the_multiplier_scales_the_export_in_para(para, scale):
    scene(para)
    scale(para, 1.0)
    base = svg_size(para)
    scale(para, 2.0)
    assert svg_size(para) == pytest.approx((2 * base[0], 2 * base[1]))


def test_the_figure_and_the_view_come_back_in_para(para):
    scene(para)
    para.canvas.fig.set_size_inches(9.0, 6.0, forward=False)
    para.zoom_level = 2.5
    svg_size(para)
    assert tuple(para.canvas.fig.get_size_inches()) == (9.0, 6.0)
    assert para.zoom_level == 2.5


# ---------------------------------------------------------------------------
# through the real export entry points
# ---------------------------------------------------------------------------

def test_the_svg_file_export_is_zoom_independent(win, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    scene(win)
    out = []
    for zoom in (0.5, 2.0):
        path = tmp_path / f"z{zoom}.svg"
        monkeypatch.setattr(QFileDialog, 'getSaveFileName',
                            staticmethod(lambda *a, **k: (str(path), '')))
        win.zoom_level = zoom
        win._export_svg()
        text = path.read_text()
        out.append(re.search(r'width="([\d.]+)pt"', text).group(1))
    assert out[0] == out[1]


def test_the_png_file_export_is_zoom_independent(win, tmp_path, monkeypatch):
    from PIL import Image
    from PySide6.QtWidgets import QFileDialog

    scene(win)
    out = []
    for zoom in (0.5, 2.0):
        path = tmp_path / f"z{zoom}.png"
        monkeypatch.setattr(QFileDialog, 'getSaveFileName',
                            staticmethod(lambda *a, **k: (str(path), '')))
        win.zoom_level = zoom
        win._export_png()
        out.append(Image.open(path).size)
    assert out[0] == out[1]


def test_the_clipboard_copy_renders_at_the_pinned_scale(win, monkeypatch):
    from graphulator import clipboard_export

    seen = {}

    def fake_copy(fig, include_png=True, png_dpi=300, bbox=None, **kw):
        seen['lw_scale'] = win._zoom_lw_scale()
        seen['bbox_w'] = bbox.width
        seen['dpi'] = png_dpi
        return 'native', ['pdf']

    monkeypatch.setattr(clipboard_export, 'copy_figure_to_clipboard',
                        fake_copy)
    scene(win)
    win.zoom_level = 3.3
    win._copy_graph_to_clipboard_vector()
    assert seen['lw_scale'] == pytest.approx(1.0)
    assert seen['dpi'] == 300
    first = seen['bbox_w']

    win.zoom_level = 0.4
    win._copy_graph_to_clipboard_vector()
    assert seen['bbox_w'] == pytest.approx(first)


def test_the_clipboard_copy_renders_at_the_pinned_scale_in_para(para,
                                                                monkeypatch):
    from graphulator import clipboard_export

    seen = {}

    def fake_copy(fig, include_png=True, png_dpi=300, bbox=None, **kw):
        seen['lw_scale'] = para._zoom_lw_scale()
        seen['bbox_w'] = bbox.width
        return 'native', ['pdf']

    monkeypatch.setattr(clipboard_export, 'copy_figure_to_clipboard',
                        fake_copy)
    scene(para)
    para.zoom_level = 3.3
    para._copy_graph_to_clipboard_vector()
    assert seen['lw_scale'] == pytest.approx(1.0)
    first = seen['bbox_w']

    para.zoom_level = 0.4
    para._copy_graph_to_clipboard_vector()
    assert seen['bbox_w'] == pytest.approx(first)


def test_a_selection_copy_is_still_scale_pinned(win, monkeypatch):
    """The two export scopes nest: the selection narrows the scene, then
    the scale is pinned to what is left."""
    from graphulator import clipboard_export

    seen = {}

    def fake_copy(fig, include_png=True, png_dpi=300, bbox=None, **kw):
        seen['nodes'] = [n['label'] for n in win.nodes]
        seen['lw_scale'] = win._zoom_lw_scale()
        return 'native', ['pdf']

    monkeypatch.setattr(clipboard_export, 'copy_figure_to_clipboard',
                        fake_copy)
    a, b = scene(win)
    add_node(win, 'C', (40.0, 0.0))
    win.selected_nodes[:] = [a, b]
    win.zoom_level = 1.9
    win._copy_graph_to_clipboard_vector()
    assert seen['nodes'] == ['A', 'B']
    assert seen['lw_scale'] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# node outlines are quoted at the reference scale like everything else
# ---------------------------------------------------------------------------

def outlined(w, label, pos, width=4.0):
    node = add_node(w, label, pos)
    node.update({'outline_enabled': True, 'outline_color': 'black',
                 'outline_width': width, 'outline_alpha': 1.0})
    return node


def outline_linewidths(w):
    """Widths of the unfilled node-radius rings currently drawn."""
    import matplotlib.patches as mpatches

    return sorted({round(p.get_linewidth(), 4)
                   for p in w.canvas.ax.patches
                   if isinstance(p, mpatches.Circle) and not p.get_fill()
                   and abs(p.get_radius() - w.node_radius) < 1e-6})


def test_a_node_outline_is_a_literal_point_width_on_export(win):
    """It was passed to matplotlib raw, so it stayed a fixed on-screen
    hairline while the drawing around it scaled."""
    outlined(win, 'A', (0.0, 0.0), width=4.0)
    win.zoom_level = 2.6
    with win._image_export_scope():
        assert outline_linewidths(win) == [4.0]


def test_a_node_outline_follows_the_export_multiplier(win, scale):
    outlined(win, 'A', (0.0, 0.0), width=4.0)
    for value, expected in ((0.5, 2.0), (1.0, 4.0), (2.0, 8.0)):
        scale(win, value)
        with win._image_export_scope():
            assert outline_linewidths(win) == [expected]


def test_a_node_outline_follows_the_zoom_on_screen(win):
    """Same rule the conjugated ring and every edge already followed: the
    stroke keeps its thickness relative to the node it rings."""
    outlined(win, 'A', (0.0, 0.0), width=4.0)
    win.zoom_level = 1.0
    win._update_plot()
    at_one = outline_linewidths(win)
    win.zoom_level = 2.0
    win._update_plot()
    assert outline_linewidths(win) == pytest.approx([2 * w for w in at_one])


def test_a_node_outline_is_a_literal_point_width_on_export_in_para(para):
    outlined(para, 'A', (0.0, 0.0), width=3.0)
    para.zoom_level = 0.4
    with para._image_export_scope():
        assert outline_linewidths(para) == [3.0]
