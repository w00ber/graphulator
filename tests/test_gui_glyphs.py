"""GUI tests for Graphulator's schematic glyphs (ports, txlines, wires).

Covers the programmatic scene API, hit testing, auto-orientation, the
keyboard stretch/rotate/label controls, deletion and undo, the save/load
round trip, the multi-selection panel, and an exported script that actually
runs and reproduces the same glyph layout. Headless (offscreen Qt + Agg).
"""

import os
import types

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture()
def win(tmp_path):
    """A fresh window per test.

    It is never close()d: closeEvent prompts about unsaved changes (a modal
    dialog nothing would answer) and autosaves the session graph. The
    session paths are redirected into tmp_path regardless, so nothing here
    can touch the user's real ~/.graphulator_* files.
    """
    from PySide6.QtWidgets import QApplication
    # the QApplication must exist before the matplotlib QtAgg backend loads
    _app = QApplication.instance() or QApplication([])
    import graphulator.graphulator_qt as gq

    w = gq.Graphulator()
    w.last_graph_path = tmp_path / "last.graph"
    w.recent_files_path = tmp_path / "recent"
    return w


def add_node(w, label, pos):
    node = {'node_id': w.node_id_counter, 'label': label, 'pos': pos,
            'color': '#6699ff', 'color_key': 'BLUE', 'node_size_mult': 1.0,
            'label_size_mult': 1.0, 'conj': False,
            'nodelabelnudge': (0.0, 0.0)}
    w.nodes.append(node)
    w.node_id_counter += 1
    w.node_counter += 1
    return node


def click(x, y, button=1):
    """A minimal stand-in for a matplotlib MouseEvent."""
    return types.SimpleNamespace(xdata=x, ydata=y, button=button,
                                 inaxes=None)


# ---------------------------------------------------------------------------
# scene API
# ---------------------------------------------------------------------------

def test_ports_and_txlines_get_sequential_labels_and_ids(win):
    t1 = win.add_port()
    t2 = win.add_port()
    c1 = win.add_txline()
    assert (t1['label'], t2['label'], c1['label']) == ('P1', 'P2', 'TL1')
    assert t1['port_id'] != t2['port_id']
    assert win._has_glyphs


def test_a_new_port_auto_orients(win):
    term = win.add_port(pos=(0.0, 0.0))
    assert term['angle_pinned'] is False


def test_wire_from_a_port_aims_its_lead(win):
    node = add_node(win, 'A', (5.0, 0.0))
    term = win.add_port(label='P1', pos=(0.0, 0.0))
    win.connect_port_to_node(term, node)
    assert win._port_effective_angle(term) == pytest.approx(0.0, abs=1e-9)

    node['pos'] = (0.0, 5.0)
    assert win._port_effective_angle(term) == pytest.approx(90.0, abs=1e-9)


def test_a_pinned_port_ignores_its_wires(win):
    node = add_node(win, 'A', (5.0, 0.0))
    term = win.add_port(label='P1', pos=(0.0, 0.0), angle=137.0)
    term['angle_pinned'] = True
    win.connect_port_to_node(term, node)
    assert win._port_effective_angle(term) == pytest.approx(137.0)


def test_txline_end_wires_reach_nodes_and_ports(win):
    a = add_node(win, 'A', (10.0, 0.0))
    term = win.add_port(label='P1', pos=(-10.0, 0.0))
    cx = win.add_txline(label='TL1', pos=(0.0, 0.0))
    win.connect_txline_end(cx, 'xL', a)
    win.connect_txline_end(cx, 'x0', term)
    wires = list(win._iter_glyph_wires())
    assert len(wires) == 2
    for owner, end, conn, pts in wires:
        assert owner is cx
        assert pts.shape[1] == 2
        assert len(pts) > 2


def test_a_wire_to_a_missing_node_is_simply_not_drawn(win):
    term = win.add_port(label='P1', pos=(0.0, 0.0))
    term['connections'].append(
        win._default_wire_conn(kind='node', node_id=999))
    assert list(win._iter_glyph_wires()) == []


# ---------------------------------------------------------------------------
# hit testing
# ---------------------------------------------------------------------------

def test_hit_testing_finds_each_kind_of_glyph(win):
    a = add_node(win, 'A', (10.0, 0.0))
    term = win.add_port(label='P1', pos=(-10.0, 0.0))
    cx = win.add_txline(label='TL1', pos=(0.0, -10.0))
    win.connect_port_to_node(term, a)

    assert win._find_port_at_position(-10.0, 0.0) is term
    assert win._find_txline_at_position(0.0, -10.0) is cx
    assert win._find_port_at_position(50.0, 50.0) is None

    end_hit = win._find_txline_end_at_position(*win._txline_end_points(cx)['xL'])
    assert end_hit == (cx, 'xL')

    _, _, _, pts = next(iter(win._iter_glyph_wires()))
    mid = pts[len(pts) // 2]
    hit = win._find_glyph_wire_at_position(mid[0], mid[1])
    assert hit is not None and hit[0] is term


def test_hit_testing_ignores_none_coordinates(win):
    win.add_port(label='P1', pos=(0.0, 0.0))
    assert win._find_port_at_position(None, None) is None
    assert win._find_txline_at_position(None, None) is None
    assert win._find_txline_end_at_position(None, None) is None
    assert win._find_glyph_wire_at_position(None, None) is None


# ---------------------------------------------------------------------------
# keyboard controls
# ---------------------------------------------------------------------------

def test_arrow_keys_stretch_length_and_height(win):
    cx = win.add_txline(label='TL1', pos=(0.0, 0.0))
    win.selected_txlines = [cx]

    win._pan_arrow('right')
    assert cx['w_mult'] > 1.0
    win._pan_arrow('up')
    assert cx['h_mult'] > 1.0
    win._pan_arrow('left')
    assert cx['w_mult'] == pytest.approx(1.0)


def test_stretch_is_clamped(win):
    from graphulator.glyphs import GLYPH_SIZE_MAX, GLYPH_SIZE_MIN
    cx = win.add_txline(label='TL1', pos=(0.0, 0.0))
    win.selected_txlines = [cx]
    for _ in range(200):
        win._pan_arrow('right')
    assert cx['w_mult'] == pytest.approx(GLYPH_SIZE_MAX)
    for _ in range(200):
        win._pan_arrow('left')
    assert cx['w_mult'] == pytest.approx(GLYPH_SIZE_MIN)


def test_ctrl_arrows_rotate_and_pin_a_port(win):
    a = add_node(win, 'A', (5.0, 0.0))
    term = win.add_port(label='P1', pos=(0.0, 0.0))
    win.connect_port_to_node(term, a)
    win.selected_ports = [term]

    win._ctrl_arrow_action('left')
    assert term['angle_pinned'] is True
    # rotation starts from the auto-orientation it was showing (0 deg)
    assert term['angle'] == pytest.approx(15.0)
    # ...and the wire no longer steers it
    a['pos'] = (0.0, 5.0)
    assert win._port_effective_angle(term) == pytest.approx(15.0)


def test_ctrl_up_down_changes_glyph_label_size(win):
    cx = win.add_txline(label='TL1', pos=(0.0, 0.0))
    win.selected_txlines = [cx]
    win._adjust_selfloop_scale('increase')
    assert cx['label_size_mult'] > 1.0
    win._adjust_selfloop_scale('decrease')
    assert cx['label_size_mult'] == pytest.approx(1.0)


def test_shift_arrows_nudge_the_glyph_label(win):
    term = win.add_port(label='P1', pos=(0.0, 0.0))
    win.selected_ports = [term]
    win._nudge_label('right')
    win._nudge_label('up')
    dx, dy = term['labelnudge']
    assert dx > 0 and dy > 0


def test_rotating_one_glyph_spins_it_in_place(win):
    cx = win.add_txline(label='TL1', pos=(3.0, 4.0))
    win.selected_txlines = [cx]
    win._rotate_selected_nodes(15)
    assert cx['pos'] == (3.0, 4.0)          # did not travel
    assert cx['angle'] == pytest.approx(345.0)


def test_rotating_a_layout_moves_glyphs_with_the_nodes(win):
    a = add_node(win, 'A', (1.0, 0.0))
    cx = win.add_txline(label='TL1', pos=(-1.0, 0.0))
    win.selected_nodes = [a]
    win.selected_txlines = [cx]
    win._rotate_selected_nodes(90)
    # pivot is the node centroid (1, 0); the txline swings about it
    assert cx['pos'][0] == pytest.approx(1.0, abs=1e-9)
    assert cx['angle'] == pytest.approx(270.0)


def test_an_auto_orienting_port_stays_unpinned_in_a_layout_rotation(win):
    a = add_node(win, 'A', (1.0, 0.0))
    b = add_node(win, 'B', (3.0, 0.0))
    term = win.add_port(label='P1', pos=(-1.0, 0.0))
    win.connect_port_to_node(term, a)
    win.selected_nodes = [a, b]
    win.selected_ports = [term]
    win._rotate_selected_nodes(90)
    assert term['angle_pinned'] is False    # its target moved too


def test_select_all_takes_the_glyphs(win):
    add_node(win, 'A', (0.0, 0.0))
    win.add_port(label='P1', pos=(-5.0, 0.0))
    win.add_txline(label='TL1', pos=(5.0, 0.0))
    win._select_all()
    assert len(win.selected_ports) == 1
    assert len(win.selected_txlines) == 1
    assert len(win.selected_nodes) == 1


def test_shortcut_context_reports_glyph(win):
    term = win.add_port(label='P1', pos=(0.0, 0.0))
    assert win._shortcut_context() == 'none'
    win.selected_ports = [term]
    assert win._shortcut_context() == 'glyph'
    assert win._shortcut_hint_rows('glyph')


# ---------------------------------------------------------------------------
# wiring with the edge tool
# ---------------------------------------------------------------------------

def test_edge_tool_wires_a_port_to_a_node(win):
    a = add_node(win, 'A', (10.0, 0.0))
    term = win.add_port(label='P1', pos=(-10.0, 0.0))
    win.placement_mode = 'edge'

    assert win._maybe_handle_glyph_edge_click(click(-10.0, 0.0)) is True
    assert win._wire_pending[1] is term
    assert win._maybe_handle_glyph_edge_click(click(10.0, 0.0)) is True

    assert len(term['connections']) == 1
    assert term['connections'][0]['node_id'] == a['node_id']
    assert win._wire_pending is None
    assert win.placement_mode is None      # single-edge mode exits


def test_edge_tool_refuses_a_duplicate_wire(win):
    a = add_node(win, 'A', (10.0, 0.0))
    term = win.add_port(label='P1', pos=(-10.0, 0.0))
    win.connect_port_to_node(term, a)
    win.placement_mode = 'edge_continuous'
    win._maybe_handle_glyph_edge_click(click(-10.0, 0.0))
    win._maybe_handle_glyph_edge_click(click(10.0, 0.0))
    assert len(term['connections']) == 1


def test_edge_tool_wires_a_txline_end_to_a_port(win):
    term = win.add_port(label='P1', pos=(-12.0, 0.0))
    cx = win.add_txline(label='TL1', pos=(0.0, 0.0))
    win.placement_mode = 'edge_continuous'
    ex, ey = win._txline_end_points(cx)['x0']
    assert win._maybe_handle_glyph_edge_click(click(ex, ey)) is True
    assert win._maybe_handle_glyph_edge_click(click(-12.0, 0.0)) is True
    # a txline-to-port wire is recorded on the TXLINE, so a wire always has
    # exactly one owner however it was drawn
    assert len(cx['ends']['x0']) == 1
    assert cx['ends']['x0'][0]['kind'] == 'port'
    assert cx['ends']['x0'][0]['port_id'] == term['port_id']
    assert term['connections'] == []


def test_escape_cancels_a_pending_wire(win):
    win.add_port(label='P1', pos=(0.0, 0.0))
    win.placement_mode = 'edge'
    win._maybe_handle_glyph_edge_click(click(0.0, 0.0))
    assert win._wire_pending is not None
    win._exit_placement_mode()
    assert win._wire_pending is None


# ---------------------------------------------------------------------------
# deletion, undo, clear
# ---------------------------------------------------------------------------

def test_deleting_a_port_drops_the_wires_that_named_it(win):
    term = win.add_port(label='P1', pos=(-10.0, 0.0))
    cx = win.add_txline(label='TL1', pos=(0.0, 0.0))
    win.connect_txline_end(cx, 'x0', term)
    win.selected_ports = [term]
    win._delete_selected_nodes()
    assert win.ports == []
    assert cx['ends']['x0'] == []


def test_deleting_a_node_drops_the_wires_that_reached_it(win):
    a = add_node(win, 'A', (10.0, 0.0))
    term = win.add_port(label='P1', pos=(-10.0, 0.0))
    win.connect_port_to_node(term, a)
    win.selected_nodes = [a]
    win._delete_selected_nodes()
    assert term['connections'] == []


def test_deleting_one_wire_leaves_its_glyphs(win):
    a = add_node(win, 'A', (10.0, 0.0))
    term = win.add_port(label='P1', pos=(-10.0, 0.0))
    conn = win.connect_port_to_node(term, a)
    win.selected_wires = [(term, conn)]
    win._delete_selected_nodes()
    assert term in win.ports
    assert term['connections'] == []


def test_undo_restores_deleted_glyphs(win):
    win.add_port(label='P1', pos=(-10.0, 0.0))
    win.add_txline(label='TL1', pos=(0.0, 0.0))
    win.selected_ports = list(win.ports)
    win.selected_txlines = list(win.txlines)
    win._delete_selected_nodes()
    assert not win._has_glyphs
    win._undo()
    assert len(win.ports) == 1
    assert len(win.txlines) == 1


def test_clear_all_takes_the_glyphs_too(win):
    add_node(win, 'A', (0.0, 0.0))
    win.add_port(label='P1', pos=(-10.0, 0.0))
    win._clear_nodes()
    assert win.ports == [] and win.nodes == []


def test_new_graph_resets_the_glyph_counters(win):
    win.add_port(label='P1', pos=(0.0, 0.0))
    win.is_modified = False
    win._new_graph()
    assert win.ports == []
    assert win.add_port()['label'] == 'P1'


# ---------------------------------------------------------------------------
# save / load
# ---------------------------------------------------------------------------

def test_save_load_round_trip_keeps_glyphs_and_wiring(win):
    a = add_node(win, 'A', (10.0, 0.0))
    term = win.add_port(label='P_1', pos=(-10.0, 0.0), w_mult=1.4,
                            color='firebrick')
    cx = win.add_txline(label='TL1', pos=(0.0, -10.0), angle=30.0, h_mult=2.0)
    win.connect_port_to_node(term, a)
    win.connect_txline_end(cx, 'xL', a)
    win.connect_txline_end(cx, 'x0', term)

    data = win._serialize_graph()
    assert data['version'] == '1.1'

    win._deserialize_graph(data)
    assert [t['label'] for t in win.ports] == ['P_1']
    assert win.ports[0]['w_mult'] == pytest.approx(1.4)
    assert win.ports[0]['color'] == 'firebrick'
    assert win.txlines[0]['angle'] == pytest.approx(30.0)
    assert win.txlines[0]['h_mult'] == pytest.approx(2.0)
    assert len(win.ports[0]['connections']) == 1
    assert len(win.txlines[0]['ends']['x0']) == 1
    assert len(win.txlines[0]['ends']['xL']) == 1
    # the id counters stay ahead of what was loaded
    assert win.add_port()['port_id'] not in [
        t['port_id'] for t in win.ports[:-1]]


def test_a_glyph_free_graph_serializes_exactly_as_before(win):
    add_node(win, 'A', (0.0, 0.0))
    data = win._serialize_graph()
    assert data['version'] == '1.0'
    assert 'ports' not in data and 'txlines' not in data


# ---------------------------------------------------------------------------
# framing, drawing, properties panel
# ---------------------------------------------------------------------------

def test_extents_grow_to_include_a_distant_txline(win):
    add_node(win, 'A', (0.0, 0.0))
    narrow = win._calculate_graph_extents()
    win.add_txline(label='TL1', pos=(0.0, -40.0))
    wide = win._calculate_graph_extents()
    assert wide[2] < narrow[2] - 30


def test_a_glyph_only_graph_can_be_framed_and_drawn(win):
    win.add_port(label='P1', pos=(-6.0, 0.0))
    win.add_txline(label='TL1', pos=(6.0, 0.0))
    win._auto_fit_view()                # must not bail on an empty node list
    win._update_plot()
    assert win.canvas.ax.patches


def test_drawing_emits_artists_for_glyphs_and_wires(win):
    a = add_node(win, 'A', (10.0, 0.0))
    term = win.add_port(label='P1', pos=(-10.0, 0.0))
    win.connect_port_to_node(term, a)
    win._update_plot()
    before = len(win.canvas.ax.lines)
    win.add_txline(label='TL1', pos=(0.0, -10.0))
    win._update_plot()
    assert len(win.canvas.ax.lines) > before


def test_properties_panel_shows_each_glyph_kind(win):
    a = add_node(win, 'A', (10.0, 0.0))
    term = win.add_port(label='P1', pos=(-10.0, 0.0))
    conn = win.connect_port_to_node(term, a)
    cx = win.add_txline(label='TL1', pos=(0.0, -10.0))
    panel = win.properties_panel

    win.selected_ports = [term]
    win._update_properties_panel()
    assert panel.current_type == 'port'
    assert 'P1' in panel.title_label.text()

    win.selected_ports = []
    win.selected_txlines = [cx]
    win._update_properties_panel()
    assert panel.current_type == 'txline'

    win.selected_txlines = []
    win.selected_wires = [(term, conn)]
    win._update_properties_panel()
    assert panel.current_type == 'glyph_wire'


def test_multi_panel_edits_every_selected_glyph(win):
    t1 = win.add_port(label='P1', pos=(-10.0, 0.0))
    t2 = win.add_port(label='P2', pos=(-10.0, 5.0), w_mult=1.5)
    cx = win.add_txline(label='TL1', pos=(0.0, -10.0))
    win.selected_ports = [t1, t2]
    win.selected_txlines = [cx]
    win._update_properties_panel()
    assert 'Multiple Selection' in win.properties_panel.title_label.text()

    win.properties_panel._apply_to_glyphs('h_mult', 1.75)
    assert [g['h_mult'] for g in (t1, t2, cx)] == [1.75, 1.75, 1.75]

    win.properties_panel._apply_multi_auto_orient(False)
    assert t1['angle_pinned'] and t2['angle_pinned']


# ---------------------------------------------------------------------------
# self-loop auto-orientation
# ---------------------------------------------------------------------------

def test_a_wire_steers_the_self_loop_away_from_itself(win):
    a = add_node(win, 'A', (0.0, 0.0))
    term = win.add_port(label='P1', pos=(-10.0, 0.0))
    win.connect_port_to_node(term, a)

    avoid = win._selfloop_avoid_angles(a)
    assert avoid, "the wire should contribute a direction to avoid"
    best = win._compute_best_selfloop_angle(a)
    # the wire comes in from the west; the loop must not sit on top of it
    separation = min(abs(best - ang) % 360 for ang in avoid)
    assert min(separation, 360 - separation) > 45


# ---------------------------------------------------------------------------
# code export
# ---------------------------------------------------------------------------

def test_exported_code_runs_and_rebuilds_the_same_glyphs(win, tmp_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from PySide6.QtWidgets import QApplication

    a = add_node(win, 'A', (0.0, 0.0))
    b = add_node(win, 'B', (8.0, 3.0))
    # delete a node first, so the surviving ids are NOT 0..N-1 -- the export
    # has to name them explicitly or the wires land on the wrong nodes
    doomed = add_node(win, 'C', (20.0, 20.0))
    win.selected_nodes = [doomed]
    win._delete_selected_nodes()

    term = win.add_port(label='P_1', pos=(-8.0, 0.0))
    cx = win.add_txline(label='TL1', pos=(0.0, -10.0), w_mult=1.3)
    win.connect_port_to_node(term, a)
    win.connect_txline_end(cx, 'xL', b)
    win.connect_txline_end(cx, 'x0', term)
    win._update_plot()

    win._export_code()
    code = QApplication.clipboard().text()
    assert 'graph.addport(' in code
    assert 'graph.addtxline(' in code
    assert code.count('graph.addwire(') == 3
    assert f"end=('node', {a['node_id']})" in code

    out = tmp_path / "exported.py"
    code = code.replace('plt.show()', f'plt.savefig(r"{out.parent}/out.png")')
    ns = {'__name__': '__main__'}
    exec(compile(code, str(out), 'exec'), ns)

    circuit = ns['graph']
    assert [t['label'] for t in circuit.ports] == ['P_1']
    assert [c['label'] for c in circuit.txlines] == ['TL1']
    assert len(circuit.wires) == 3
    assert circuit.txlines[0]['length'] == pytest.approx(1.3)
    # auto-orientation survives: the exported port re-derives its angle
    assert circuit.ports[0]['autoorient'] is True
    assert circuit._portangle(circuit.ports[0]) == pytest.approx(
        win._port_effective_angle(term), abs=1e-6)
    plt.close('all')


def test_export_is_skipped_for_an_empty_graph(win):
    from PySide6.QtWidgets import QApplication
    QApplication.clipboard().setText('SENTINEL')
    win._export_code()
    assert QApplication.clipboard().text() == 'SENTINEL'


# ---------------------------------------------------------------------------
# dialogs
# ---------------------------------------------------------------------------
# Construction gates, in the spirit of tests/test_gui_dialogs.py: a
# NameError in a widget constructor is exactly the break a model-level test
# misses and a user hits on the first click.

def test_port_dialog_builds_and_round_trips(win):
    from graphulator import glyphs

    fresh = glyphs.PortInputDialog(default_label='P7')
    out = fresh.get_result()
    assert out['label'] == 'P7'
    assert out['auto_orient'] is True
    for key in ('w_mult', 'h_mult', 'label_size_mult', 'linewidth', 'color',
                'fill', 'label_color'):
        assert key in out, key

    term = win.add_port(label='Pa', pos=(0.0, 0.0), w_mult=1.3,
                            h_mult=0.8, linewidth=3.0, color='indianred')
    term['angle_pinned'] = True
    edit = glyphs.PortInputDialog(default_label='Pa', editing=True,
                                      port=term)
    got = edit.get_result()
    assert got['label'] == 'Pa'
    assert got['auto_orient'] is False        # pinned == auto-orient off
    assert got['w_mult'] == pytest.approx(1.3)
    assert got['h_mult'] == pytest.approx(0.8)
    assert got['linewidth'] == pytest.approx(3.0)
    assert got['color'] == 'indianred'


def test_txline_dialog_builds_and_round_trips(win):
    from graphulator import glyphs

    fresh = glyphs.TxLineInputDialog(default_label='TL7')
    out = fresh.get_result()
    assert out['label'] == 'TL7'
    assert out['angle'] == pytest.approx(0.0)

    cx = win.add_txline(label='TLa', pos=(0.0, 0.0), angle=45.0, w_mult=2.0,
                      fill='#dddddd')
    edit = glyphs.TxLineInputDialog(default_label='TLa', editing=True, txline=cx)
    got = edit.get_result()
    assert got['label'] == 'TLa'
    assert got['angle'] == pytest.approx(45.0)
    assert got['w_mult'] == pytest.approx(2.0)
    assert got['fill'] == '#dddddd'


def test_applying_a_dialog_result_pins_a_port_at_what_is_on_screen(win):
    """Turning auto-orient OFF must freeze the angle the user can see, not
    snap back to a stale stored one."""
    a = add_node(win, 'A', (0.0, 10.0))
    term = win.add_port(label='P1', pos=(0.0, 0.0), angle=0.0)
    win.connect_port_to_node(term, a)
    assert win._port_effective_angle(term) == pytest.approx(90.0)

    win._apply_port_style(term, {'auto_orient': False})
    assert term['angle'] == pytest.approx(90.0)


def test_exported_labels_survive_backslashes_and_quotes(win, tmp_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from PySide6.QtWidgets import QApplication

    add_node(win, 'A', (0.0, 0.0))
    win.add_port(label=r'\Delta_{in}', pos=(-8.0, 0.0))
    win._update_plot()
    win._export_code()
    code = QApplication.clipboard().text()

    out = tmp_path / "exported.py"
    code = code.replace('plt.show()', f'plt.savefig(r"{tmp_path}/out.png")')
    ns = {'__name__': '__main__'}
    exec(compile(code, str(out), 'exec'), ns)
    assert ns['graph'].ports[0]['label'] == r'\Delta_{in}'
    plt.close('all')


# ---------------------------------------------------------------------------
# txline end handles: wiring and dragging
# ---------------------------------------------------------------------------

def test_clicking_a_txline_body_resolves_to_its_nearer_end(win):
    """A txline is a two-terminal object, so "wire this line" always means
    one of its two ends -- never its center. The end dots are far too small
    to be the only target (0.12 R across), so the body counts too."""
    cx = win.add_txline(label='TL1', pos=(0.0, 0.0))
    left, right = win._txline_end_points(cx)['x0'], win._txline_end_points(cx)['xL']
    body_left = ((left[0] + 0.0) / 2, 0.0)
    body_right = ((right[0] + 0.0) / 2, 0.0)
    assert win._txline_end_for_click(*body_left) == (cx, 'x0')
    assert win._txline_end_for_click(*body_right) == (cx, 'xL')
    # and well off the glyph, nothing
    assert win._txline_end_for_click(0.0, 50.0) is None


def test_wiring_a_txline_by_its_body_works(win):
    """The reported bug: the end stubs were the only target and were
    effectively unhittable, so txlines could not be wired at all."""
    a = add_node(win, 'A', (10.0, 0.0))
    cx = win.add_txline(label='TL1', pos=(0.0, 0.0))
    win.placement_mode = 'edge_continuous'

    # click the right half of the BODY, not the tiny end dot
    assert win._maybe_handle_glyph_edge_click(click(1.0, 0.0)) is True
    assert win._wire_pending == ('txline', cx, 'xL')
    assert win._maybe_handle_glyph_edge_click(click(10.0, 0.0)) is True
    assert len(cx['ends']['xL']) == 1
    assert cx['ends']['xL'][0]['node_id'] == a['node_id']
    assert cx['ends']['x0'] == []


def test_a_wire_can_land_on_a_txline_body_too(win):
    port = win.add_port(label='P1', pos=(-12.0, 0.0))
    cx = win.add_txline(label='TL1', pos=(0.0, 0.0))
    win.placement_mode = 'edge_continuous'
    win._maybe_handle_glyph_edge_click(click(-12.0, 0.0))     # start at port
    assert win._maybe_handle_glyph_edge_click(click(-1.0, 0.0)) is True
    assert len(cx['ends']['x0']) == 1                          # nearer end
    assert cx['ends']['x0'][0]['port_id'] == port['port_id']


def test_dragging_one_end_holds_the_other_exactly(win):
    cx = win.add_txline(label='TL1', pos=(0.0, 0.0))
    fixed_before = win._txline_end_points(cx)['x0']

    win.set_txline_end(cx, 'xL', (5.0, 3.0))

    ends = win._txline_end_points(cx)
    assert ends['x0'] == pytest.approx(fixed_before, abs=1e-9)
    assert ends['xL'] == pytest.approx((5.0, 3.0), abs=1e-9)


def test_dragging_an_end_sets_length_and_angle(win):
    cx = win.add_txline(label='TL1', pos=(0.0, 0.0))
    x0 = win._txline_end_points(cx)['x0']
    # put xL straight above x0: the glyph must end up vertical
    win.set_txline_end(cx, 'xL', (x0[0], x0[1] + 8.0))
    assert cx['angle'] == pytest.approx(90.0, abs=1e-6)
    assert cx['w_mult'] > 1.0          # 8 units is longer than the default


def test_dragging_the_other_end_aims_the_line_the_other_way(win):
    cx = win.add_txline(label='TL1', pos=(0.0, 0.0))
    xL = win._txline_end_points(cx)['xL']
    win.set_txline_end(cx, 'x0', (xL[0], xL[1] + 8.0))
    # x0 is now ABOVE xL, so the x0 -> xL axis points down
    assert cx['angle'] == pytest.approx(270.0, abs=1e-6)
    assert win._txline_end_points(cx)['xL'] == pytest.approx(xL, abs=1e-9)


def test_a_clamped_length_still_anchors_the_fixed_end(win):
    from graphulator.glyphs import GLYPH_SIZE_MIN
    cx = win.add_txline(label='TL1', pos=(0.0, 0.0))
    fixed = win._txline_end_points(cx)['x0']
    win.set_txline_end(cx, 'xL', (fixed[0] + 0.05, fixed[1]))
    assert cx['w_mult'] == pytest.approx(GLYPH_SIZE_MIN)
    assert win._txline_end_points(cx)['x0'] == pytest.approx(fixed, abs=1e-9)


def test_end_drag_snaps_to_the_grid(win):
    cx = win.add_txline(label='TL1', pos=(0.0, 0.0))
    ex, ey = win._txline_end_points(cx)['xL']
    win._maybe_handle_glyph_click(click(ex, ey), False, False)
    assert win._txline_end_drag_pending == (cx, 'xL')

    # drag well past the threshold, release off-grid
    win._maybe_handle_glyph_motion(click(6.3, 2.7))
    assert win._txline_end_dragging == (cx, 'xL')
    win._maybe_handle_glyph_release(click(6.3, 2.7))

    landed = win._txline_end_points(cx)['xL']
    assert landed == pytest.approx(win._snap_to_grid(6.3, 2.7), abs=1e-9)
    assert win._txline_end_dragging is None
    assert win._txline_end_drag_preview == []


def test_grabbing_the_body_still_moves_the_whole_glyph(win):
    cx = win.add_txline(label='TL1', pos=(0.0, 0.0))
    win._maybe_handle_glyph_click(click(0.0, 0.0), False, False)
    assert win._txline_end_drag_pending is None
    assert win._glyph_drag_pending == ('txline', cx)


# ---------------------------------------------------------------------------
# wire appearance
# ---------------------------------------------------------------------------

def test_wires_are_black_and_solid_by_default(win):
    a = add_node(win, 'A', (10.0, 0.0))
    port = win.add_port(label='P1', pos=(-10.0, 0.0))
    conn = win.connect_port_to_node(port, a)
    color, lw, style = win.wire_style(conn)
    assert color == 'black'
    assert style == '-'
    assert lw > 0


def test_wire_color_width_and_style_are_settable(win):
    a = add_node(win, 'A', (10.0, 0.0))
    port = win.add_port(label='P1', pos=(-10.0, 0.0))
    conn = win.connect_port_to_node(port, a)

    conn.update(color='indianred', linewidth_mult=2.5, linestyle='--')
    color, lw, style = win.wire_style(conn)
    assert (color, style) == ('indianred', '--')
    assert lw == pytest.approx(win.wire_style({'linewidth_mult': 2.5})[1])

    # clearing the override falls back to the default, not to None
    conn['color'] = None
    assert win.wire_style(conn)[0] == 'black'


def test_wire_style_reaches_the_canvas(win):
    import matplotlib.lines as mlines
    a = add_node(win, 'A', (10.0, 0.0))
    port = win.add_port(label='P1', pos=(-10.0, 0.0))
    conn = win.connect_port_to_node(port, a)
    conn.update(linestyle=':', color='teal')
    win._update_plot()
    drawn = [ln for ln in win.canvas.ax.lines
             if isinstance(ln, mlines.Line2D)
             and ln.get_color() == 'teal' and ln.get_linestyle() == ':']
    assert drawn, "the dotted teal wire never reached the axes"


def test_wire_panel_exposes_color_width_and_style(win):
    from PySide6.QtWidgets import QComboBox
    a = add_node(win, 'A', (10.0, 0.0))
    port = win.add_port(label='P1', pos=(-10.0, 0.0))
    conn = win.connect_port_to_node(port, a)
    win.selected_wires = [(port, conn)]
    win._update_properties_panel()

    combos = win.properties_panel.findChildren(QComboBox)
    assert combos, "no style combo in the wire panel"
    combos[0].setCurrentText('Dashed')
    assert conn['linestyle'] == '--'


def test_wire_style_survives_save_load_and_export(win, tmp_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from PySide6.QtWidgets import QApplication

    a = add_node(win, 'A', (10.0, 0.0))
    port = win.add_port(label='P1', pos=(-10.0, 0.0))
    conn = win.connect_port_to_node(port, a)
    conn.update(color='indianred', linestyle='--', linewidth_mult=2.0)

    data = win._serialize_graph()
    win._deserialize_graph(data)
    restored = win.ports[0]['connections'][0]
    assert restored['linestyle'] == '--'
    assert restored['color'] == 'indianred'

    win._update_plot()
    win._export_code()
    code = QApplication.clipboard().text()
    assert "linestyle='--'" in code
    ns = {'__name__': '__main__'}
    exec(compile(code.replace('plt.show()', f'plt.savefig(r"{tmp_path}/o.png")'),
                 'exported.py', 'exec'), ns)
    assert ns['graph'].wires[0]['linestyle'] == '--'
    plt.close('all')


# ---------------------------------------------------------------------------
# clipboard
# ---------------------------------------------------------------------------

def wired_scene(win):
    """A node, a port wired to it, and a txline wired to both."""
    a = add_node(win, 'A', (0.0, 0.0))
    port = win.add_port(label='P1', pos=(-8.0, 0.0), color='indianred',
                        w_mult=1.4)
    cx = win.add_txline(label='TL1', pos=(0.0, -8.0), w_mult=1.6)
    conn = win.connect_port_to_node(port, a)
    conn.update(linestyle='--', color='teal')
    win.connect_txline_end(cx, 'x0', port)
    win.connect_txline_end(cx, 'xL', a)
    return a, port, cx


def test_copy_carries_glyphs_and_their_wiring(win):
    a, port, cx = wired_scene(win)
    win.selected_nodes = [a]
    win.selected_ports = [port]
    win.selected_txlines = [cx]
    win._copy_nodes()

    assert len(win.clipboard['ports']) == 1
    assert len(win.clipboard['txlines']) == 1
    assert len(win.clipboard['ports'][0]['connections']) == 1
    assert {e: len(v) for e, v in
            win.clipboard['txlines'][0]['ends'].items()} == {'x0': 1, 'xL': 1}


def test_paste_rewires_the_copy_to_itself(win):
    """The copy must wire to the pasted node/port, not quietly share the
    original's."""
    a, port, cx = wired_scene(win)
    win.selected_nodes = [a]
    win.selected_ports = [port]
    win.selected_txlines = [cx]
    win._copy_nodes()
    win._paste_nodes()

    new_node = win.selected_nodes[0]
    new_port = win.selected_ports[0]
    new_cx = win.selected_txlines[0]
    assert new_node is not a and new_port is not port and new_cx is not cx
    assert new_port['port_id'] != port['port_id']
    assert new_cx['txline_id'] != cx['txline_id']

    assert new_port['connections'][0]['node_id'] == new_node['node_id']
    assert new_cx['ends']['x0'][0]['port_id'] == new_port['port_id']
    assert new_cx['ends']['xL'][0]['node_id'] == new_node['node_id']
    # and the original is untouched
    assert port['connections'][0]['node_id'] == a['node_id']
    assert len(list(win._iter_glyph_wires())) == 6


def test_paste_keeps_glyph_styling(win):
    a, port, cx = wired_scene(win)
    win.selected_nodes = [a]
    win.selected_ports = [port]
    win.selected_txlines = [cx]
    win._copy_nodes()
    win._paste_nodes()

    new_port = win.selected_ports[0]
    assert new_port['color'] == 'indianred'
    assert new_port['w_mult'] == pytest.approx(1.4)
    assert win.selected_txlines[0]['w_mult'] == pytest.approx(1.6)
    wire = new_port['connections'][0]
    assert (wire['linestyle'], wire['color']) == ('--', 'teal')


def test_paste_offsets_a_glyph_only_copy(win):
    """A glyph-only copy has no node centroid; without the glyph positions
    it would paste exactly on top of the original."""
    port = win.add_port(label='P1', pos=(-8.0, 0.0))
    win.selected_ports = [port]
    win._copy_nodes()
    win._paste_nodes()

    assert len(win.ports) == 2
    assert win.selected_ports[0]['pos'] != port['pos']


def test_a_wire_whose_far_end_was_not_copied_is_dropped(win):
    """Half a wire cannot travel: re-pointing it at the original's target
    would make the copy silently share the original's wiring."""
    a, port, cx = wired_scene(win)
    win.selected_nodes = []
    win.selected_txlines = []
    win.selected_ports = [port]          # the node is NOT in the selection
    win._copy_nodes()
    assert win.clipboard['ports'][0]['connections'] == []

    win._paste_nodes()
    assert win.selected_ports[0]['connections'] == []
    assert len(port['connections']) == 1      # the original kept its wire


def test_cut_removes_the_glyphs_and_keeps_them_on_the_clipboard(win):
    a, port, cx = wired_scene(win)
    win.selected_nodes = [a]
    win.selected_ports = [port]
    win.selected_txlines = [cx]
    win._cut_nodes()

    assert win.ports == [] and win.txlines == [] and win.nodes == []
    assert len(win.clipboard['ports']) == 1
    assert len(win.clipboard['ports'][0]['connections']) == 1

    win._paste_nodes()
    assert len(win.ports) == 1 and len(win.txlines) == 1
    assert len(list(win._iter_glyph_wires())) == 3


def test_cutting_a_node_drops_the_wires_that_reached_it(win):
    a, port, cx = wired_scene(win)
    win.selected_nodes = [a]             # cut the node, leave the glyphs
    win.selected_ports = []
    win.selected_txlines = []
    win._cut_nodes()

    assert port in win.ports
    assert port['connections'] == []
    assert cx['ends']['xL'] == []
    assert cx['ends']['x0']               # the port wire survives


def test_cut_then_undo_restores_the_glyphs(win):
    a, port, cx = wired_scene(win)
    win.selected_nodes = [a]
    win.selected_ports = [port]
    win.selected_txlines = [cx]
    win._cut_nodes()
    win._undo()

    assert len(win.ports) == 1 and len(win.txlines) == 1
    assert len(list(win._iter_glyph_wires())) == 3


def test_copy_with_nothing_selected_leaves_the_clipboard_alone(win):
    port = win.add_port(label='P1', pos=(-8.0, 0.0))
    win.selected_ports = [port]
    win._copy_nodes()
    win._clear_glyph_selection()
    win._copy_nodes()                     # nothing selected now
    assert len(win.clipboard['ports']) == 1


# ---------------------------------------------------------------------------
# the port owns no lead; the txline mouth is a bore
# ---------------------------------------------------------------------------

def test_a_port_draws_no_lead_of_its_own(win):
    """The line leaving a port is the CONNECTION's stroke, so its width
    always agrees with whatever it connects to. A glyph-owned lead had its
    own width and frequently disagreed."""
    import matplotlib.lines as mlines
    win.add_port(label='P1', pos=(0.0, 0.0))
    win._update_plot()
    strokes = [ln for ln in win.canvas.ax.lines
               if isinstance(ln, mlines.Line2D) and ln.get_gid() != 'grid']
    assert strokes == []


def test_a_port_wire_anchors_inside_the_body_and_sits_behind_it(win):
    a = add_node(win, 'A', (12.0, 0.0))
    port = win.add_port(label='P1', pos=(0.0, 0.0))
    win.connect_port_to_node(port, a)

    x, y, w, h, apex_x = win._port_geometry(port)
    anchor, tangent = win._port_wire_start(port)
    assert x - w / 2 < anchor[0] < apex_x          # buried in the polygon
    apex = win._port_apex(port)
    assert anchor[0] < apex[0]

    win._update_plot()
    import matplotlib.patches as mpatches
    body = next(p for p in win.canvas.ax.patches
                if isinstance(p, mpatches.Polygon))
    wires = [ln for ln in win.canvas.ax.lines if ln.get_gid() != 'grid']
    # the polygon covers the wire's hidden end cap
    assert all(ln.get_zorder() < body.get_zorder() for ln in wires)


def test_the_port_extent_no_longer_includes_a_lead(win):
    port = win.add_port(label='P1', pos=(0.0, 0.0))
    x, y, w, h, apex_x = win._port_geometry(port)
    xs = [p[0] for p in win._glyph_extent_points()]
    assert max(xs) == pytest.approx(apex_x)


def test_txline_mouth_stub_comes_out_of_the_bore(win):
    cx = win.add_txline(label='TL1', pos=(0.0, 0.0), h_mult=3.0)
    lx, ly, w, h, rx = win._txline_geometry(cx)
    win._update_plot()

    stub = max((ln for ln in win.canvas.ax.lines if ln.get_gid() != 'grid'),
               key=lambda ln: max(ln.get_xdata()))
    assert min(stub.get_xdata()) == pytest.approx(lx + w)   # bore center
    assert stub.get_solid_capstyle() == 'round'

    import matplotlib.patches as mpatches
    # exactly Ellipse: Arc and the Circle end-marks are both subclasses
    mouth = max((p for p in win.canvas.ax.patches
                 if type(p) is mpatches.Ellipse),
                key=lambda e: e.center[0])
    assert stub.get_zorder() > mouth.get_zorder()
    # ...but the end-mark dot still sits on top of the stub tip
    dot = max((p for p in win.canvas.ax.patches
               if type(p) is mpatches.Circle), key=lambda c: c.center[0])
    assert dot.get_zorder() > stub.get_zorder()


def test_txline_label_tracks_the_body_and_the_multiplier(win):
    """Both spinboxes must visibly move the label: the height used to be
    capped at 1.1 R, which left the size control scaling a tiny base."""
    from matplotlib.patches import PathPatch

    def drawn_height(**props):
        cx.update(props)
        win._update_plot()
        patch = [p for p in win.canvas.ax.patches
                 if isinstance(p, PathPatch)][-1]
        bb = patch.get_path().get_extents(
            patch.get_transform() - win.canvas.ax.transData)
        return bb.height

    cx = win.add_txline(label='X', pos=(0.0, 0.0))
    short = drawn_height(h_mult=2.0, label_size_mult=1.0)
    tall = drawn_height(h_mult=4.0, label_size_mult=1.0)
    assert tall > 1.5 * short

    bigger = drawn_height(h_mult=4.0, label_size_mult=2.0)
    assert bigger == pytest.approx(2 * tall, rel=0.05)
