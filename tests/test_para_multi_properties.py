"""Multi-selection property editing in Paragraphulator.

Selecting several nodes, edges or port/line glyphs now offers the properties
they share, with an indeterminate marker where they disagree; editing one
field writes it to every selected object in a single undo step. Headless.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    # QtWebEngine refuses to sandbox as root (CI containers)
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")

from PySide6.QtCore import Qt  # noqa: E402


@pytest.fixture()
def para(tmp_path):
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    import graphulator.graphulator_para as gp

    w = gp.Graphulator()
    w.last_graph_path = tmp_path / "last.pgraph"
    w.recent_files_path = tmp_path / "recent"
    return w


def add_node(w, label, pos, **props):
    node = {'node_id': w.node_id_counter, 'label': label, 'pos': pos,
            'color': '#6699ff', 'color_key': 'BLUE', 'node_size_mult': 1.0,
            'label_size_mult': 1.0, 'conj': False,
            'nodelabelnudge': (0.0, 0.0)}
    node.update(props)
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


# ---------------------------------------------------------------------------
# the panel appears for a multi-selection
# ---------------------------------------------------------------------------

def test_multiple_nodes_get_an_editable_panel(para):
    a = add_node(para, 'A', (0.0, 0.0))
    b = add_node(para, 'B', (4.0, 0.0))
    para.selected_nodes = [a, b]
    para._update_properties_panel()
    title = para.properties_panel.title_label.text()
    assert 'Multiple Selection' in title and '2 node(s)' in title
    # it is not the old read-only placeholder
    assert para.properties_panel.displayed_multi is not None


def test_editing_writes_to_every_selected_node(para):
    a = add_node(para, 'A', (0.0, 0.0))
    b = add_node(para, 'B', (4.0, 0.0), node_size_mult=1.8)
    para.selected_nodes = [a, b]
    para._update_properties_panel()

    para.properties_panel._apply_to_nodes('node_size_mult', 1.25)
    assert a['node_size_mult'] == b['node_size_mult'] == 1.25

    para.properties_panel._apply_to_nodes('conj', True)
    assert a['conj'] is True and b['conj'] is True


def test_one_edit_is_one_undo_step(para):
    a = add_node(para, 'A', (0.0, 0.0))
    b = add_node(para, 'B', (4.0, 0.0))
    para.selected_nodes = [a, b]
    depth = len(para.undo_stack)
    para.properties_panel._apply_to_nodes('label_size_mult', 1.9)
    assert len(para.undo_stack) == depth + 1

    para._undo()
    assert [n['label_size_mult'] for n in para.nodes] == [1.0, 1.0]


def test_editing_writes_to_every_selected_edge(para):
    a = add_node(para, 'A', (0.0, 0.0))
    b = add_node(para, 'B', (4.0, 0.0))
    c = add_node(para, 'C', (8.0, 0.0))
    e1 = add_edge(para, a, b)
    e2 = add_edge(para, b, c, style='single')
    para.selected_edges = [e1, e2]
    para._update_properties_panel()

    para.properties_panel._apply_to_edges('style', 'double')
    assert e1['style'] == e2['style'] == 'double'
    para.properties_panel._apply_to_edges('looptheta', 55)
    assert e1['looptheta'] == e2['looptheta'] == 55


def test_a_mixed_node_and_edge_selection_offers_both_sections(para):
    a = add_node(para, 'A', (0.0, 0.0))
    b = add_node(para, 'B', (4.0, 0.0))
    e1 = add_edge(para, a, b)
    e2 = add_edge(para, b, a, looptheta=10)
    para.selected_nodes = [a, b]
    para.selected_edges = [e1, e2]
    para._update_properties_panel()
    title = para.properties_panel.title_label.text()
    assert '2 node(s)' in title and '2 edge(s)' in title


# ---------------------------------------------------------------------------
# indeterminate widgets
# ---------------------------------------------------------------------------

def test_a_shared_value_is_shown_plainly(para):
    panel = para.properties_panel
    sb = panel._make_multi_double_spinbox([1.5, 1.5], lambda v: None,
                                          0.0, 3.0, 0.1)
    assert sb.value() == pytest.approx(1.5)
    assert sb._indeterminate is False
    assert 'gray' not in sb.styleSheet()


def test_differing_values_are_shown_gray_and_do_not_auto_commit(para):
    panel = para.properties_panel
    written = []
    sb = panel._make_multi_double_spinbox([1.0, 2.0], written.append,
                                          0.0, 3.0, 0.1)
    assert sb._indeterminate is True
    assert 'gray' in sb.styleSheet()
    assert written == []            # building it must not write anything

    sb.setValue(2.5)                # a real edit commits to everything
    assert written == [pytest.approx(2.5)]
    assert sb._indeterminate is False


def test_a_differing_combo_starts_blank(para):
    panel = para.properties_panel
    written = []
    cb = panel._make_multi_combo(['loopy', 'single'], ['loopy', 'single'],
                                 written.append)
    assert cb.currentIndex() == -1
    assert written == []


def test_a_matching_combo_shows_the_shared_value(para):
    panel = para.properties_panel
    cb = panel._make_multi_combo(['loopy', 'single'], ['single', 'single'],
                                 lambda v: None)
    assert cb.currentText() == 'single'


def test_a_differing_checkbox_is_partially_checked(para):
    panel = para.properties_panel
    cb = panel._make_multi_checkbox([True, False], lambda v: None)
    assert cb.checkState() == Qt.PartiallyChecked


def test_an_agreeing_checkbox_shows_the_shared_state(para):
    panel = para.properties_panel
    cb = panel._make_multi_checkbox([True, True], lambda v: None)
    assert cb.isChecked() is True


def test_an_empty_int_spinbox_is_safe(para):
    """Building a row for a property no selected object carries must not
    raise on min() of an empty sequence."""
    panel = para.properties_panel
    sb = panel._make_multi_int_spinbox([], lambda v: None, -180, 180)
    assert sb.value() == -180


# ---------------------------------------------------------------------------
# port / line glyphs
# ---------------------------------------------------------------------------

def test_glyphs_join_the_multi_selection_panel(para):
    para._auto_enable_explicit_ports("test")
    p1 = para.add_port(label='P1', pos=(-4.0, 0.0))
    p2 = para.add_port(label='P2', pos=(-4.0, 4.0))
    line = para.add_line_resonator(label='TL1', pos=(0.0, -6.0))
    para.selected_ports = [p1, p2]
    para.selected_lines = [line]
    para._update_properties_panel()

    title = para.properties_panel.title_label.text()
    assert '2 port(s)' in title and '1 line(s)' in title

    para.properties_panel._apply_to_glyphs('h_mult', 1.6)
    assert [g['h_mult'] for g in (p1, p2, line)] == [1.6, 1.6, 1.6]


def test_auto_orient_can_be_toggled_for_several_ports_at_once(para):
    para._auto_enable_explicit_ports("test")
    p1 = para.add_port(label='P1', pos=(-4.0, 0.0))
    p2 = para.add_port(label='P2', pos=(-4.0, 4.0))
    para.selected_ports = [p1, p2]
    para._update_properties_panel()

    para.properties_panel._apply_multi_auto_orient(False)
    assert p1['angle_pinned'] and p2['angle_pinned']
    para.properties_panel._apply_multi_auto_orient(True)
    assert not p1['angle_pinned'] and not p2['angle_pinned']


def test_a_single_glyph_still_gets_its_own_panel(para):
    para._auto_enable_explicit_ports("test")
    p1 = para.add_port(label='P1', pos=(-4.0, 0.0))
    para.selected_ports = [p1]
    para._update_properties_panel()
    assert 'Multiple Selection' not in para.properties_panel.title_label.text()


def test_a_single_node_still_gets_its_own_panel(para):
    a = add_node(para, 'A', (0.0, 0.0))
    para.selected_nodes = [a]
    para._update_properties_panel()
    assert para.properties_panel.title_label.text() == 'Node: A'
    assert para.properties_panel.displayed_multi is None


def test_no_selection_clears_the_multi_signature(para):
    a = add_node(para, 'A', (0.0, 0.0))
    b = add_node(para, 'B', (4.0, 0.0))
    para.selected_nodes = [a, b]
    para._update_properties_panel()
    assert para.properties_panel.displayed_multi is not None

    para.selected_nodes = []
    para._update_properties_panel()
    assert para.properties_panel.displayed_multi is None


def test_the_panel_is_not_rebuilt_while_the_selection_is_unchanged(para):
    """Rebuilding destroys the widgets mid-edit; a multi-edit field writes on
    every change, so the rebuild would fire on the first keystroke."""
    a = add_node(para, 'A', (0.0, 0.0))
    b = add_node(para, 'B', (4.0, 0.0))
    para.selected_nodes = [a, b]
    para._update_properties_panel()
    signature = para.properties_panel.displayed_multi

    calls = []
    original = para.properties_panel.show_multi_properties

    def spy(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)
    para.properties_panel.show_multi_properties = spy

    para._update_properties_panel()
    assert calls == []
    assert para.properties_panel.displayed_multi == signature


# ---------------------------------------------------------------------------
# code export (shared with Graphulator; gated here for the para side)
# ---------------------------------------------------------------------------

def test_para_exports_both_shapes_of_drawing_code(para):
    """Both apps generate their code through the same module now, so para's
    export has to keep working -- in both shapes, with real colors."""
    from PySide6.QtWidgets import QApplication

    for i, color in enumerate(('#aab6a8', '#929ec0')):
        for j in range(3):
            add_node(para, f'A_{i}{j}', (3.0 * i, 3.0 * j), color=color,
                     color_key='RED')          # the key the picker left behind
    for i in range(5):
        add_edge(para, para.nodes[i], para.nodes[i + 1])
    para._update_plot()

    for compact, expected in ((False, 'graph.addnode(label='),
                              (True, 'NODE_STYLES')):
        QApplication.clipboard().setText('')
        para._export_code(compact=compact)
        code = QApplication.clipboard().text()
        assert expected in code
        assert "nodecolor='#aab6a8'" in code
        assert "nodecolor='#929ec0'" in code
        assert "MYCOLORS['RED']" not in code


# ---------------------------------------------------------------------------
# several wires at once (port attachments and line taps)
# ---------------------------------------------------------------------------

def two_attached_modes(para):
    """Two ports, each attached to its own mode; all four within ±12."""
    a = add_node(para, 'A', (6.0, 0.0))
    b = add_node(para, 'B', (6.0, -6.0))
    para.scattering_assignments[a['node_id']] = {'freq': 5.0, 'B_int': 0.0}
    para.scattering_assignments[b['node_id']] = {'freq': 5.0, 'B_int': 0.0}
    p1 = para.add_port(label='P1', pos=(-6.0, 0.0))
    p2 = para.add_port(label='P2', pos=(-6.0, -6.0))
    return ((p1, para.add_port_attachment(p1, a, rate=0.1)),
            (p2, para.add_port_attachment(p2, b, rate=0.3)))


def test_several_wires_get_an_editable_panel(para):
    w1, w2 = two_attached_modes(para)
    para.selected_attachments = [w1, w2]
    para._update_properties_panel()

    panel = para.properties_panel
    assert panel.displayed_multi is not None
    assert "2 wire(s)" in panel.title_label.text()


def test_editing_writes_to_every_selected_wire(para):
    w1, w2 = two_attached_modes(para)
    para.selected_attachments = [w1, w2]
    para._update_properties_panel()

    para.properties_panel._apply_to_wires('rate', 0.5)
    assert w1[1]['rate'] == pytest.approx(0.5)
    assert w2[1]['rate'] == pytest.approx(0.5)


def test_one_multi_wire_edit_is_one_undo_step(para):
    w1, w2 = two_attached_modes(para)
    para.selected_attachments = [w1, w2]
    before = len(para.undo_stack)
    para.properties_panel._apply_to_wires('sign', -1)
    assert len(para.undo_stack) == before + 1
    assert w1[1]['sign'] == w2[1]['sign'] == -1


def test_a_differing_wire_rate_is_shown_gray(para):
    from PySide6.QtWidgets import QDoubleSpinBox
    w1, w2 = two_attached_modes(para)          # 0.1 vs 0.3
    para.selected_attachments = [w1, w2]
    para._update_properties_panel()

    boxes = [b for b in para.properties_panel.findChildren(QDoubleSpinBox)
             if getattr(b, '_indeterminate', False)]
    assert boxes, "no indeterminate marker for the differing rates"


def test_attachments_and_taps_edit_together(para):
    w1, _w2 = two_attached_modes(para)
    line = para.add_line_resonator(label='TL1', pos=(0.0, -12.0),
                                   port_end=None, FSR=1.0, f_max=8.0)
    conn = para.connect_line_end_to_node(line, 'xL', para.nodes[0],
                                         rate=0.2)
    para.selected_attachments = [w1]
    para.selected_taps = [(line, 'xL', conn)]
    para._update_properties_panel()

    assert "1 wire(s)" in para.properties_panel.title_label.text()
    assert "1 tap(s)" in para.properties_panel.title_label.text()
    para.properties_panel._apply_to_wires('rate', 0.4)
    assert w1[1]['rate'] == pytest.approx(0.4)
    assert conn['rate'] == pytest.approx(0.4)


def test_a_single_wire_still_gets_its_own_panel(para):
    w1, _w2 = two_attached_modes(para)
    para.selected_attachments = [w1]
    para._update_properties_panel()
    assert para.properties_panel.current_type == 'attachment'
    assert para.properties_panel.displayed_multi is None


def test_a_wire_alongside_a_node_offers_the_shared_panel(para):
    w1, _w2 = two_attached_modes(para)
    para.selected_attachments = [w1]
    para.selected_nodes[:] = [para.nodes[0]]
    para._update_properties_panel()
    assert para.properties_panel.displayed_multi is not None


def test_resetting_the_multi_wire_color_restores_the_default(para):
    w1, w2 = two_attached_modes(para)
    w1[1]['color'] = w2[1]['color'] = 'teal'
    para.selected_attachments = [w1, w2]
    para.properties_panel._apply_to_wires('color', None)
    assert para.wire_style(w1[1])[0] == para.wire_default_color('port', 1)


# ---------------------------------------------------------------------------
# the rubber band takes the links too
# ---------------------------------------------------------------------------

def test_the_band_takes_a_link_with_both_ends_inside(para):
    w1, w2 = two_attached_modes(para)
    atts, taps = para._links_in_rect(-12.0, -12.0, 12.0, 12.0)
    assert {id(a) for _p, a in atts} == {id(w1[1]), id(w2[1])}
    assert taps == []


def test_the_band_takes_a_link_by_its_midpoint(para):
    """Same rule an edge uses. A band drawn ACROSS a bundle of wires -- how
    you actually reach for "these wires" -- encloses no endpoints at all,
    so a both-ends-in rule would select nothing."""
    w1, w2 = two_attached_modes(para)
    atts, _taps = para._links_in_rect(-1.0, -12.0, 1.0, 12.0)
    assert {id(a) for _p, a in atts} == {id(w1[1]), id(w2[1])}


def test_the_band_leaves_a_link_it_does_not_cross_alone(para):
    w1, _w2 = two_attached_modes(para)
    atts, _taps = para._links_in_rect(-1.0, -2.0, 1.0, 2.0)
    assert {id(a) for _p, a in atts} == {id(w1[1])}


def test_a_band_release_selects_the_links_it_encloses(para):
    import types
    w1, w2 = two_attached_modes(para)
    para.selection_window_start = (-12.0, -12.0)
    para.selection_window = True
    para.selection_window_rect = None
    para._on_release_selection_window(
        types.SimpleNamespace(xdata=12.0, ydata=12.0, button=1,
                              inaxes=para.canvas.ax))

    assert len(para.selected_ports) == 2
    assert {id(a) for _p, a in para.selected_attachments} == \
        {id(w1[1]), id(w2[1])}


def test_a_band_release_does_not_duplicate_an_already_selected_link(para):
    import types
    w1, _w2 = two_attached_modes(para)
    para.selected_attachments = [w1]
    para.selection_window_start = (-12.0, -12.0)
    para.selection_window = True
    para.selection_window_rect = None
    para._on_release_selection_window(
        types.SimpleNamespace(xdata=12.0, ydata=12.0, button=1,
                              inaxes=para.canvas.ax))
    ids = [id(a) for _p, a in para.selected_attachments]
    assert len(ids) == len(set(ids)) == 2


def test_deleting_a_selection_of_only_links_works(para):
    """The delete guard listed nodes, edges, glyphs and attachments but not
    taps or pump buses, so a tap-only selection reported "nothing selected"
    and did nothing."""
    a = add_node(para, 'A', (0.0, 0.0))
    para.scattering_assignments[a['node_id']] = {'freq': 5.0, 'B_int': 0.0}
    line = para.add_line_resonator(label='TL1', pos=(0.0, -8.0),
                                   port_end=None, FSR=1.0, f_max=8.0)
    conn = para.connect_line_end_to_node(line, 'xL', a, rate=0.2)
    para.selected_taps = [(line, 'xL', conn)]

    para._delete_selected_nodes()
    assert para._end_conns(line, 'xL') == []
    assert para.nodes == [a] and para.line_resonators == [line]
