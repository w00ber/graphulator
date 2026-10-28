"""Shift+Cmd+J copies the SELECTION, unhighlighted, in both apps.

The clipboard copy renders the live canvas, so a copy made with a
sub-circuit selected came out as the whole graph with selection rings and
halos drawn on part of it -- useless for lifting a sub-graph into a figure.
These cover the narrowing (nodes, the edges between them, glyphs and their
wiring), the highlighting going away, "nothing selected means everything",
and the scene being put back exactly as it was. Headless (offscreen Qt +
Agg).
"""

import os

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


def add_edge(w, a, b):
    edge = {'from_node': a, 'to_node': b, 'from_node_id': a['node_id'],
            'to_node_id': b['node_id'], 'label1': '', 'label2': '',
            'linewidth_mult': 1.0, 'label_size_mult': 1.0,
            'label_offset_mult': 1.0, 'style': 'solid', 'direction': 'none',
            'looptheta': 30, 'is_self_loop': a is b}
    w.edges.append(edge)
    return edge


def scene(w):
    """Two wired modes to copy, and a third well away from them."""
    a = add_node(w, 'A', (0.0, 0.0))
    b = add_node(w, 'B', (4.0, 0.0))
    far = add_node(w, 'C', (20.0, 0.0))
    add_edge(w, a, b)
    add_edge(w, b, far)
    return a, b, far


# ---------------------------------------------------------------------------
# narrowing
# ---------------------------------------------------------------------------

def test_nothing_selected_exports_the_whole_graph(win):
    scene(win)
    with win._export_selection_scope() as summary:
        assert summary is None
        assert len(win.nodes) == 3 and len(win.edges) == 2


def test_a_selection_narrows_the_drawn_scene(win):
    a, b, far = scene(win)
    win.selected_nodes[:] = [a, b]
    with win._export_selection_scope() as summary:
        assert [n['label'] for n in win.nodes] == ['A', 'B']
        assert summary == "2 node(s) and 1 edge(s)"


def test_an_edge_comes_along_when_both_its_modes_do(win):
    """Not just the ones in selected_edges: shift-clicking two modes
    selects no edge at all, and two bare dots is not the sub-graph."""
    a, b, far = scene(win)
    win.selected_nodes[:] = [a, b]
    win.selected_edges.clear()
    with win._export_selection_scope():
        assert len(win.edges) == 1


def test_an_edge_leaving_the_selection_is_dropped(win):
    a, b, far = scene(win)
    win.selected_nodes[:] = [a, b]
    win.selected_edges[:] = list(win.edges)      # B->C selected as well
    with win._export_selection_scope():
        assert len(win.edges) == 1


def test_the_selection_highlighting_is_off_while_exporting(win):
    a, b, far = scene(win)
    win.selected_nodes[:] = [a, b]
    win.selected_edges[:] = [win.edges[0]]
    win.selected_ports = [win.add_port(label='P1', pos=(-6.0, 0.0))]
    with win._export_selection_scope():
        assert win.selected_nodes == []
        assert win.selected_edges == []
        assert win.selected_ports == []
        assert win.selected_wires == []


def test_the_scene_and_the_selection_come_back(win):
    a, b, far = scene(win)
    port = win.add_port(label='P1', pos=(-6.0, 0.0))
    nodes, edges, ports = win.nodes, win.edges, win.ports
    win.selected_nodes[:] = [a]
    win.selected_ports = [port]
    with win._export_selection_scope():
        pass
    assert win.nodes is nodes and win.edges is edges and win.ports is ports
    assert len(win.nodes) == 3 and len(win.ports) == 1
    assert win.selected_nodes == [a] and win.selected_ports == [port]


def test_the_scene_comes_back_even_when_the_export_raises(win):
    a, b, far = scene(win)
    win.selected_nodes[:] = [a]
    with pytest.raises(RuntimeError):
        with win._export_selection_scope():
            raise RuntimeError("render blew up")
    assert len(win.nodes) == 3


# ---------------------------------------------------------------------------
# glyphs and their wiring
# ---------------------------------------------------------------------------

def test_a_selected_port_is_exported_with_its_wire(win):
    a, b, far = scene(win)
    port = win.add_port(label='P1', pos=(-6.0, 0.0))
    win.connect_port_to_node(port, a)
    win.selected_nodes[:] = [a]
    win.selected_ports = [port]
    with win._export_selection_scope() as summary:
        assert [p['label'] for p in win.ports] == ['P1']
        assert win._wire_for(port, port['connections'][0]) is not None
        assert '1 port(s)' in summary


def test_a_wire_leaving_the_selection_draws_nothing(win):
    """The far end is resolved against the DRAWN node list, so a wire to a
    mode that stayed behind drops out on its own."""
    a, b, far = scene(win)
    port = win.add_port(label='P1', pos=(-6.0, 0.0))
    win.connect_port_to_node(port, far)
    win.selected_ports = [port]                  # the mode is not selected
    with win._export_selection_scope():
        assert win._wire_for(port, port['connections'][0]) is None


def test_an_unselected_port_is_left_out(win):
    a, b, far = scene(win)
    keep = win.add_port(label='P1', pos=(-6.0, 0.0))
    win.add_port(label='P2', pos=(26.0, 0.0))
    win.selected_nodes[:] = [a]
    win.selected_ports = [keep]
    with win._export_selection_scope():
        assert [p['label'] for p in win.ports] == ['P1']


def test_a_glyph_only_selection_still_narrows(win):
    scene(win)
    port = win.add_port(label='P1', pos=(-6.0, 0.0))
    win.selected_ports = [port]
    with win._export_selection_scope() as summary:
        assert win.nodes == [] and win.edges == []
        assert summary == "1 port(s)"


def test_a_selection_only_export_crops_to_the_selection(win):
    """The crop follows the drawn artists, so narrowing the scene is what
    makes the pasted art the sub-graph rather than the whole canvas."""
    from graphulator import clipboard_export

    a, b, far = scene(win)
    win._update_plot_no_grid()
    whole = clipboard_export.content_bbox_inches(win.canvas.fig)

    win.selected_nodes[:] = [a, b]
    with win._export_selection_scope():
        win._update_plot_no_grid()
        part = clipboard_export.content_bbox_inches(win.canvas.fig)
    assert part.width < whole.width


# ---------------------------------------------------------------------------
# paragraphulator
# ---------------------------------------------------------------------------

def test_a_selection_narrows_the_drawn_scene_in_para(para):
    a, b, far = scene(para)
    port = para.add_port(label='P1', pos=(-6.0, 0.0))
    para.add_port_attachment(port, a, rate=0.25)
    para.selected_nodes[:] = [a, b]
    para.selected_ports = [port]
    with para._export_selection_scope() as summary:
        assert [n['label'] for n in para.nodes] == ['A', 'B']
        assert [p['label'] for p in para.ports] == ['P1']
        assert summary == "2 node(s) and 1 edge(s) and 1 port(s)"


def test_the_links_lose_their_highlighting_in_para(para):
    a, b, far = scene(para)
    port = para.add_port(label='P1', pos=(-6.0, 0.0))
    att = para.add_port_attachment(port, a, rate=0.25)
    para.selected_nodes[:] = [a]
    para.selected_ports = [port]
    para.selected_attachments = [(port, att)]
    with para._export_selection_scope():
        assert para.selected_attachments == []
        assert para.selected_taps == []
        assert para.selected_ports == []


def test_a_selected_line_brings_its_end_port_along(para):
    """add_line_resonator places that port as part of making the line, so
    a line drawn without it stops in mid-air."""
    line = para.add_line_resonator(label='TL1', pos=(0.0, 0.0))
    para.add_port(label='P9', pos=(30.0, 0.0))     # unrelated, stays out
    para.selected_lines = [line]
    with para._export_selection_scope() as summary:
        assert [ln['label'] for ln in para.line_resonators] == ['TL1']
        assert [p['label'] for p in para.ports] == ['TL1']
        assert summary == "1 port(s) and 1 line(s)"


def test_nothing_selected_exports_the_whole_graph_in_para(para):
    a, b, far = scene(para)
    para.add_port(label='P1', pos=(-6.0, 0.0))
    with para._export_selection_scope() as summary:
        assert summary is None
        assert len(para.nodes) == 3 and len(para.ports) == 1


def test_the_kron_canvas_always_copies_whole(para):
    """The reduction is computed data with a node list of its own; the
    main-canvas selection means nothing there."""
    a, b, far = scene(para)
    para.selected_nodes[:] = [a]
    with para._export_selection_scope(enabled=False) as summary:
        assert summary is None
        assert len(para.nodes) == 3


def test_the_scene_and_the_selection_come_back_in_para(para):
    a, b, far = scene(para)
    port = para.add_port(label='P1', pos=(-6.0, 0.0))
    para.selected_nodes[:] = [a]
    para.selected_ports = [port]
    with para._export_selection_scope():
        pass
    assert len(para.nodes) == 3 and len(para.ports) == 1
    assert para.selected_nodes == [a] and para.selected_ports == [port]


# ---------------------------------------------------------------------------
# end to end through the real copy
# ---------------------------------------------------------------------------

def test_the_clipboard_copy_reports_the_selection(win, monkeypatch):
    from graphulator import clipboard_export

    seen = {}

    def fake_copy(fig, include_png=True, **kw):
        seen['nodes'] = [n['label'] for n in win.nodes]
        seen['bbox'] = clipboard_export.content_bbox_inches(fig)
        return 'native', ['pdf']

    monkeypatch.setattr(clipboard_export, 'copy_figure_to_clipboard',
                        fake_copy)
    a, b, far = scene(win)
    port = win.add_port(label='P1', pos=(-6.0, 0.0))
    win.connect_port_to_node(port, a)
    win.selected_nodes[:] = [a, b]
    win.selected_ports = [port]

    win._copy_graph_to_clipboard_vector()
    assert seen['nodes'] == ['A', 'B']
    # and the live scene is whole again, selection and all
    assert len(win.nodes) == 3
    assert win.selected_nodes == [a, b] and win.selected_ports == [port]


def test_the_clipboard_copy_reports_the_selection_in_para(para, monkeypatch):
    from graphulator import clipboard_export

    seen = {}

    def fake_copy(fig, include_png=True, **kw):
        seen['nodes'] = [n['label'] for n in para.nodes]
        return 'native', ['pdf']

    monkeypatch.setattr(clipboard_export, 'copy_figure_to_clipboard',
                        fake_copy)
    a, b, far = scene(para)
    port = para.add_port(label='P1', pos=(-6.0, 0.0))
    para.add_port_attachment(port, a, rate=0.25)
    para.selected_nodes[:] = [a, b]
    para.selected_ports = [port]

    para._copy_graph_to_clipboard_vector()
    assert seen['nodes'] == ['A', 'B']
    assert len(para.nodes) == 3
    assert para.selected_nodes == [a, b] and para.selected_ports == [port]


def test_a_glyph_only_graph_is_still_copyable(win, monkeypatch):
    """The guard is "nothing drawn", not "no nodes": a terminated txline is
    a perfectly good figure."""
    from graphulator import clipboard_export

    seen = {}

    def fake_copy(fig, include_png=True, **kw):
        seen['hit'] = True
        return 'native', ['pdf']

    monkeypatch.setattr(clipboard_export, 'copy_figure_to_clipboard',
                        fake_copy)
    win.add_port(label='P1', pos=(0.0, 0.0))
    win._copy_graph_to_clipboard_vector()
    assert seen.get('hit') is True


# ---------------------------------------------------------------------------
# the canvas is left as the user had it, not showing the selection alone
# ---------------------------------------------------------------------------

def drawn_node_centres(w):
    """Centres of the node-sized circles currently on the canvas."""
    import matplotlib.patches as mpatches

    radius = w.node_radius
    return sorted(
        (round(p.center[0], 3), round(p.center[1], 3))
        for p in w.canvas.ax.patches
        if isinstance(p, mpatches.Circle) and p.get_fill()
        and abs(p.get_radius() - radius) < 1e-6)


def spy_on_copy(w, monkeypatch):
    """Make the clipboard copy a no-op that still runs the export scopes."""
    from graphulator import clipboard_export

    monkeypatch.setattr(clipboard_export, 'copy_figure_to_clipboard',
                        lambda fig, **kw: ('spy', ['pdf']))


def test_the_whole_graph_is_back_on_the_canvas_after_a_selection_copy(win,
                                                                      monkeypatch):
    """The redraw used to happen while the scene was still narrowed, so the
    canvas kept showing the exported sub-graph alone -- it looked like the
    rest of the drawing had been hidden until the next click put it back."""
    spy_on_copy(win, monkeypatch)
    a, b, far = scene(win)
    win.selected_nodes[:] = [a, b]

    win._copy_graph_to_clipboard_vector()

    assert drawn_node_centres(win) == [(0.0, 0.0), (4.0, 0.0), (20.0, 0.0)]


def test_the_selection_is_highlighted_again_after_the_copy(win, monkeypatch):
    spy_on_copy(win, monkeypatch)
    a, b, far = scene(win)
    port = win.add_port(label='P1', pos=(-6.0, 0.0))
    win.connect_port_to_node(port, a)
    win.selected_nodes[:] = [a, b]
    win.selected_ports = [port]

    win._copy_graph_to_clipboard_vector()

    assert win.selected_nodes == [a, b] and win.selected_ports == [port]
    assert len(win.ports) == 1 and len(win.nodes) == 3


def test_the_whole_graph_is_back_after_a_selection_copy_in_para(para,
                                                                monkeypatch):
    spy_on_copy(para, monkeypatch)
    a, b, far = scene(para)
    port = para.add_port(label='P1', pos=(-6.0, 0.0))
    para.add_port_attachment(port, a, rate=0.25)
    para.selected_nodes[:] = [a, b]
    para.selected_ports = [port]

    para._copy_graph_to_clipboard_vector()

    assert drawn_node_centres(para) == [(0.0, 0.0), (4.0, 0.0), (20.0, 0.0)]
    assert para.selected_nodes == [a, b] and para.selected_ports == [port]


def test_a_whole_graph_copy_leaves_the_canvas_alone_too(win, monkeypatch):
    spy_on_copy(win, monkeypatch)
    scene(win)
    win._copy_graph_to_clipboard_vector()
    assert drawn_node_centres(win) == [(0.0, 0.0), (4.0, 0.0), (20.0, 0.0)]


def test_a_file_export_still_redraws_on_its_own(win, tmp_path, monkeypatch):
    """Only the clipboard copy hands the redraw to an outer scope; the file
    exports have no narrowing to wait for."""
    from PySide6.QtWidgets import QFileDialog

    scene(win)
    path = tmp_path / "out.svg"
    monkeypatch.setattr(QFileDialog, 'getSaveFileName',
                        staticmethod(lambda *a, **k: (str(path), '')))
    win._export_svg()
    assert drawn_node_centres(win) == [(0.0, 0.0), (4.0, 0.0), (20.0, 0.0)]
