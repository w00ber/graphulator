"""GUI tests for Explicit Ports mode (handoff spec 6.9), headless.

Covers: programmatic scene API (port + 2 nodes + attachments), the Settings
gate, save/load round-trip with the v3.0 sections + auto-enable, generated
code executing and matching the live S, and the legacy .pgraph
saved-then-loaded migration reproducing the golden S.
"""

import json
import os
import pickle

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    # QtWebEngine refuses to sandbox as root (CI containers)
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")

HERE = os.path.dirname(__file__)
# 3MODE_AMP_CHAIN: every B_ext port has its self-loop, so the GUI
# serializer's "null B_ext without a self-loop" rule (pre-existing) does not
# alter it on resave. (CIRC_FULL_SCATT carries a B_ext on a node without a
# self-loop, which a GUI resave has always dropped.)
LEGACY_PGRAPH = os.path.join(HERE, os.pardir,
                             "misc", "PGRAPH_TESTS", "3MODE_AMP_CHAIN.pgraph")
GOLDEN_PKL = os.path.join(HERE, "golden", "3MODE_AMP_CHAIN.pkl")


@pytest.fixture()
def para(tmp_path):
    """Fresh window per test (Explicit Ports toggles global config)."""
    try:
        from PySide6.QtWidgets import QApplication
        # the QApplication must exist before the matplotlib QtAgg backend
        # loads (imported by graphulator_para), or backend detection fails
        _app = QApplication.instance() or QApplication([])

        import graphulator.graphulator_para as gp
        from graphulator import graphulator_para_config as config
    except ImportError as exc:
        pytest.skip(f"GUI stack unavailable: {exc}")
    try:
        win = gp.Graphulator()
    except Exception as exc:
        pytest.skip(f"Could not create main window: {exc}")
    original = config.EXPLICIT_PORTS_MODE
    yield gp, win, config
    config.EXPLICIT_PORTS_MODE = original


def add_node(win, node_id, label, x, freq=5.0, B_int=0.0, conj=False):
    node = {'node_id': node_id, 'label': label, 'pos': (x, 0.0),
            'color': 'cornflowerblue', 'color_key': 'BLUE',
            'node_size_mult': 1.0, 'label_size_mult': 1.0, 'conj': conj}
    win.nodes.append(node)
    win.node_id_counter = max(win.node_id_counter, node_id + 1)
    win.scattering_assignments[node_id] = {'freq': freq, 'B_int': B_int}
    return node


def build_shared_port_scene(win, config):
    """Two modes sharing one explicit port (the headline use case)."""
    config.EXPLICIT_PORTS_MODE = True
    win._apply_explicit_ports_mode()
    add_node(win, 0, 'A', 0.0, freq=5.0)
    add_node(win, 1, 'B', 2.0, freq=6.0)
    port = win.add_port(label='P1', pos=(4.0, 0.0), monitored=True)
    win.add_port_attachment(port, 0, rate=0.2, sign=1)
    win.add_port_attachment(port, 1, rate=0.2, sign=-1)
    return port


def compute_live_S(win, f_start=-2.0, f_stop=2.0, points=21):
    """Live-pipeline S via the same job route the Show S worker uses."""
    from graphulator.graphulator_para import _compute_sparams_job
    f = np.linspace(f_start, f_stop, points)
    job = win._build_sparams_job(None, f, f_start, f_stop, points)
    assert job is not None
    result = _compute_sparams_job(job)
    assert result is not None
    return result


def test_placement_requires_explicit_mode(para):
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = False
    win._toggle_port_mode()
    assert win.placement_mode is None
    win._toggle_line_mode()
    assert win.placement_mode is None

    config.EXPLICIT_PORTS_MODE = True
    win._toggle_port_mode()
    assert win.placement_mode == 'port'
    win._toggle_port_mode()
    assert win.placement_mode is None
    win._toggle_line_mode()
    assert win.placement_mode == 'line'
    win._exit_placement_mode()
    assert win.placement_mode is None


def test_shared_port_live_S_is_hub_based(para):
    """The live pipeline builds the rank-one shared-port damping: S is 1x1,
    unitary (lossless), and channel label = hub label."""
    gp, win, config = para
    build_shared_port_scene(win, config)

    result = compute_live_S(win)
    S = result['S']
    assert S.shape[1:] == (1, 1)
    # lossless single-channel: |S11| = 1 at machine precision
    assert np.max(np.abs(np.abs(S[:, 0, 0]) - 1.0)) < 1e-12
    ref = result['port_ids'][0]
    assert result['port_dict'][ref]['label'] == 'P1'

    # cross-check the assembly against a direct hub-based computation
    from graphulator import autograph
    from tests.hub_matrix_helpers import build_static_extractor, hub_from_column
    Omega = np.diag([5.0, 6.0])
    kappa = np.array([np.sqrt(0.2), -np.sqrt(0.2)])
    ext = build_static_extractor(Omega, hubs=[hub_from_column('P1', kappa)])
    gsm = autograph.GraphScatteringMatrix(ext, np.linspace(-2, 2, 21))
    np.testing.assert_allclose(S, gsm.S, rtol=1e-12, atol=1e-14)


def test_line_component_computes_alone(para):
    """A line macro is its own component job; its S11 comes from the comb."""
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = True
    win.add_line_resonator(label='TL1', pos=(0.0, -3.0), FSR=1.5, Ztx=65.0,
                           f_max=6.0, port_end='xL', Z0_port=50.0)
    comps = win._find_connected_components()
    assert len(comps) == 1 and comps[0].get('line_ids') == [0]

    from graphulator.graphulator_para import _compute_sparams_job
    f = np.linspace(0.5, 4.0, 31)
    job = win._build_sparams_job(comps[0], f, 0.5, 4.0, 31)
    result = _compute_sparams_job(job)
    assert result is not None
    assert result['S'].shape[1:] == (1, 1)
    assert np.max(np.abs(np.abs(result['S'][:, 0, 0]) - 1.0)) < 1e-12
    ref = result['port_ids'][0]
    assert result['port_dict'][ref]['label'] == 'TL1'


def test_save_load_round_trip_and_auto_enable(para, tmp_path):
    gp, win, config = para
    port = build_shared_port_scene(win, config)
    win.add_line_resonator(label='TL1', pos=(0.0, -3.0), FSR=1.5, Ztx=65.0,
                           f_max=6.0, port_end='xL', Z0_port=50.0,
                           alpha_uniform=0.01)

    data = json.loads(json.dumps(win._serialize_graph()))  # simulate disk
    assert data['version'] == '3.0'
    # P1 plus the line's own (explicit, visible) port glyph
    assert len(data['ports']) == 2
    assert len(data['line_resonators']) == 1
    assert data['line_resonators'][0]['ends']['xL'][0]['kind'] == 'port'

    # load with the mode off: it must auto-enable and restore everything
    config.EXPLICIT_PORTS_MODE = False
    win._deserialize_graph(data)
    assert config.EXPLICIT_PORTS_MODE is True
    assert len(win.ports) == 2
    restored = win.ports[0]
    assert restored['label'] == 'P1'
    assert restored['attachments'] == port['attachments']
    line = win.line_resonators[0]
    assert (line['FSR'], line['Ztx'], line['f_max']) == (1.5, 65.0, 6.0)
    assert line['port_end'] == 'xL'
    assert line['alpha_uniform'] == 0.01

    # a graph without ports/lines keeps writing version 2.0
    win2_data = json.loads(json.dumps(win._serialize_graph()))
    assert win2_data['version'] == '3.0'
    win._init_explicit_ports_state()
    legacy_data = win._serialize_graph()
    assert legacy_data['version'] == '2.0'
    assert 'ports' not in legacy_data


def test_generated_code_matches_live_S(para):
    gp, win, config = para
    build_shared_port_scene(win, config)

    # enter scattering mode so codegen has tree/frequency state
    win._enter_scattering_mode()
    win.properties_panel.freq_center_spin.setValue(0.0)
    win.properties_panel.freq_span_spin.setValue(4.0)
    win.properties_panel.freq_points_spin.setValue(21)

    code = win.properties_panel._generate_scattering_calculation_code()
    assert code is not None
    assert 'hubs' in code and "'P1'" in code

    # execute everything up to (not including) the plotting section
    code_no_plot = code.split("# Plot S-parameters")[0].rsplit(
        "# ====", 1)[0]
    namespace = {}
    exec(compile(code_no_plot, '<generated>', 'exec'), namespace)
    gsm = namespace['scattering_matrix']

    live = compute_live_S(win, f_start=-2.0, f_stop=2.0, points=21)
    np.testing.assert_allclose(gsm.S, live['S'], rtol=1e-12, atol=1e-14)
    assert gsm.num_ports == 1
    assert gsm.port_labels == ['P1']


def test_legacy_pgraph_saved_then_loaded_is_golden_equal(para, tmp_path):
    """Stage-5 gate: legacy file -> GUI -> save -> autograph reproduces the
    Stage-0 golden S (rtol 1e-14; see test_regression_golden for the ulp
    note)."""
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = False
    win._open_graph_file(os.path.abspath(LEGACY_PGRAPH))
    # a legacy graph must NOT flip the switch
    assert config.EXPLICIT_PORTS_MODE is False
    assert win.ports == [] and win.line_resonators == []

    out = tmp_path / "resaved.pgraph"
    assert win._save_graph_to_file(str(out))
    saved = json.load(open(out))
    assert saved['version'] == '2.0'
    assert 'ports' not in saved

    from graphulator import autograph
    with open(GOLDEN_PKL, 'rb') as fh:
        art = pickle.load(fh)
    extractor = autograph.GraphExtractor()
    extractor.extract_from_pgraph(autograph.load_pgraph(str(out)))
    gsm = autograph.GraphScatteringMatrix(extractor, art['f'])
    np.testing.assert_allclose(gsm.S, art['S'], rtol=1e-14, atol=1e-16)
    assert gsm.port_ids == art['port_ids']


def test_ports_panel_populates_and_bext_column_hides(para):
    gp, win, config = para
    build_shared_port_scene(win, config)
    win._enter_scattering_mode()

    panel = win.properties_panel
    assert panel.ports_frame.isVisibleTo(win.properties_panel)
    texts = []
    for i in range(panel.ports_param_layout.count()):
        w = panel.ports_param_layout.itemAt(i).widget()
        if w is not None and hasattr(w, 'text'):
            texts.append(w.text())
    joined = ' | '.join(texts)
    assert 'P1' in joined
    assert '\N{RIGHTWARDS ARROW} A' in joined
    assert '\N{RIGHTWARDS ARROW} B' in joined

    # the node table must NOT offer a B_ext column in explicit mode
    node_texts = []
    for i in range(panel.nodes_param_layout.count()):
        w = panel.nodes_param_layout.itemAt(i).widget()
        if w is not None and hasattr(w, 'text') and not hasattr(w, 'value'):
            node_texts.append(w.text())
    assert not any('B_ext' in t for t in node_texts)


def test_delete_node_drops_attachments_and_undo_restores(para):
    gp, win, config = para
    port = build_shared_port_scene(win, config)
    assert len(port['attachments']) == 2

    node_b = win.nodes[1]
    win.selected_nodes = [node_b]
    win._delete_selected_nodes()
    assert len(win.ports[0]['attachments']) == 1
    assert win.ports[0]['attachments'][0]['node_id'] == 0

    win._undo()
    assert len(win.ports[0]['attachments']) == 2


def test_mixed_sector_attachment_rejected_end_to_end(para):
    """The Phase-1 gate reaches the GUI pipeline: a port spanning sectors
    fails the sweep with the M_pumped error."""
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = True
    add_node(win, 0, 'A', 0.0, freq=5.0)
    add_node(win, 1, 'B*', 2.0, freq=6.0, conj=True)
    port = win.add_port(label='P1', pos=(4.0, 0.0))
    win.add_port_attachment(port, 0, rate=0.2)
    win.add_port_attachment(port, 1, rate=0.2)

    f = np.linspace(-2, 2, 5)
    job = win._build_sparams_job(None, f, -2.0, 2.0, 5)
    from graphulator.graphulator_para import _compute_sparams_job
    with pytest.raises(ValueError, match="M_pumped"):
        _compute_sparams_job(job)


# ---------------------------------------------------------------------------
# Interactive canvas flows (synthetic events): edge-tool attachment in both
# click orders, drag-to-move, rotation, and angle persistence.
# ---------------------------------------------------------------------------

from types import SimpleNamespace


def canvas_event(win, x, y, button=1):
    return SimpleNamespace(xdata=x, ydata=y, inaxes=win.canvas.ax,
                           button=button)


def build_unattached_scene(win, config):
    """Two modes and a port with NO attachments, plus a line."""
    config.EXPLICIT_PORTS_MODE = True
    win._apply_explicit_ports_mode()
    add_node(win, 0, 'A', 0.0, freq=5.0)
    add_node(win, 1, 'B', 2.0, freq=6.0)
    port = win.add_port(label='P1', pos=(5.0, 0.0), monitored=True)
    line = win.add_line_resonator(label='TL1', pos=(0.0, -4.0), FSR=1.5,
                                  Ztx=65.0, f_max=6.0, port_end='xL')
    return port, line


def test_edge_tool_attachment_port_first(para):
    gp, win, config = para
    port, _ = build_unattached_scene(win, config)
    win._toggle_edge_mode()
    win._on_click_edge_mode(canvas_event(win, 5.0, 0.0))   # click the port
    assert win._attach_pending_port is port
    win._on_click_edge_mode(canvas_event(win, 0.0, 0.0))   # then the node
    assert win._attach_pending_port is None
    assert [a['node_id'] for a in port['attachments']] == [0]


def test_edge_tool_attachment_node_first(para):
    """The natural order — click the mode, then the port — must also work."""
    gp, win, config = para
    port, _ = build_unattached_scene(win, config)
    win._toggle_edge_mode()
    win._on_click_edge_mode(canvas_event(win, 0.0, 0.0))   # click node A
    assert win.edge_mode_first_node is win.nodes[0]
    win._on_click_edge_mode(canvas_event(win, 5.0, 0.0))   # then the port
    assert win.edge_mode_first_node is None
    assert [a['node_id'] for a in port['attachments']] == [0]


def test_line_gets_an_explicit_visible_port(para):
    """Placing a terminated line creates a REAL port glyph wired to that
    end — nothing is implied, and the port is editable like any other."""
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = True
    line = win.add_line_resonator(label='TL1', pos=(0.0, 0.0), FSR=1.5,
                                  Ztx=65.0, f_max=6.0, port_end='xL',
                                  Z0_port=50.0)
    assert len(win.ports) == 1
    port = win.ports[0]
    assert line['ends']['xL'] == [{'kind': 'port',
                                   'port_id': port['port_id']}]
    assert line['ends']['x0'] == []

    # the port's hub column carries the whole comb (2N+1 couplings)
    hubs = win._gui_hubs_payload()
    assert len(hubs) == 1
    assert len(hubs[0]['attachments']) == 2 * 4 + 1
    assert hubs[0]['label'] == 'TL1'


def test_line_termination_matches_implicit_port_physics(para):
    """The explicit-port refactor is physics-preserving: S is identical to
    the old implicitly-terminated line."""
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = True
    win.add_line_resonator(label='TL1', pos=(0.0, 0.0), FSR=1.5, Ztx=65.0,
                           f_max=6.0, port_end='xL', Z0_port=50.0)
    from graphulator.graphulator_para import _compute_sparams_job
    from graphulator import autograph

    f = np.linspace(0.5, 4.0, 31)
    comps = win._find_connected_components()
    result = _compute_sparams_job(win._build_sparams_job(comps[0], f, 0.5, 4.0, 31))

    ref = autograph.LineResonator(line_id='line:0', label='TL1', FSR=1.5,
                                  Ztx=65.0, f_max=6.0, port_end='xL',
                                  Z0_port=50.0)
    ext = autograph.GraphExtractor()
    ext.extract_graph_data(nodes=[], edges=[], scattering_assignments={},
                           frequency_settings={'start': 0.5, 'stop': 4.0,
                                               'points': 31},
                           line_resonators=[ref])
    gsm = autograph.GraphScatteringMatrix(ext, f)
    np.testing.assert_array_equal(result['S'][:, 0, 0], gsm.S[:, 0, 0])


def test_edge_tool_connects_line_end_to_port(para):
    """Click a line-end lead, then a port glyph -> that end is terminated.
    The comb never leaves the macro (no exploding, no extra nodes)."""
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = True
    line = win.add_line_resonator(label='TL1', pos=(0.0, 0.0), FSR=1.5,
                                  Ztx=65.0, f_max=6.0, port_end=None)
    assert win.ports == []                                 # nothing implied
    port = win.add_port(label='PX', pos=(-9.0, 0.0))
    n_nodes = len(win.nodes)

    x0_pt = win._line_end_points(line)['x0']
    win._toggle_edge_mode()
    win._on_click_edge_mode(canvas_event(win, *x0_pt))      # the end lead
    assert win._attach_pending_line_end == (line, 'x0')
    win._on_click_edge_mode(canvas_event(win, -9.0, 0.0))   # the port
    assert win._attach_pending_line_end is None
    assert line['ends']['x0'][0]['port_id'] == port['port_id']
    assert len(win.nodes) == n_nodes                        # comb stayed inside

    hubs = win._gui_hubs_payload()
    assert len(hubs[0]['attachments']) == 2 * 4 + 1
    # x0 termination is the all-plus profile u_n(0) = +1
    assert {ph for _, _, ph in hubs[0]['attachments']} == {0.0}


def test_port_first_order_also_terminates_line(para):
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = True
    line = win.add_line_resonator(label='TL1', pos=(0.0, 0.0), FSR=1.5,
                                  Ztx=65.0, f_max=6.0, port_end=None)
    port = win.add_port(label='PX', pos=(-9.0, 0.0))
    win._toggle_edge_mode()
    win._on_click_edge_mode(canvas_event(win, -9.0, 0.0))   # port first
    win._on_click_edge_mode(canvas_event(win, *win._line_end_points(line)['x0']))
    assert line['ends']['x0'][0]['port_id'] == port['port_id']


def test_second_termination_refused_as_phase2(para):
    """Both ends loaded = a two-port line: blocked until an ABCD two-port
    reference is written and verified."""
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = True
    line = win.add_line_resonator(label='TL1', pos=(0.0, 0.0), FSR=1.5,
                                  Ztx=65.0, f_max=6.0, port_end='xL')
    other = win.add_port(label='P2', pos=(-9.0, 0.0))
    with pytest.raises(ValueError, match="two-port"):
        win.connect_line_end_to_port(line, 'x0', other)
    assert line['ends']['x0'] == []


def test_line_shares_a_component_with_its_ports_nodes(para):
    """A port serving both a line and a device node puts them in one
    component (they share a hub column)."""
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = True
    add_node(win, 0, 'A', 0.0, freq=5.0)
    line = win.add_line_resonator(label='TL1', pos=(0.0, -6.0), FSR=1.5,
                                  Ztx=65.0, f_max=6.0, port_end='xL')
    port = win.ports[0]
    win.add_port_attachment(port, 0, rate=0.2)

    comps = win._find_connected_components()
    assert len(comps) == 1
    assert comps[0]['line_ids'] == [line['line_id']]
    assert 0 in comps[0]['node_ids']

    # one hub column carrying the device attachment AND the comb
    hubs = win._gui_hubs_payload()
    assert len(hubs) == 1
    assert len(hubs[0]['attachments']) == 1 + (2 * 4 + 1)


def test_legacy_port_end_migrates_to_explicit_port(para):
    """Files written before explicit ends materialize the implied port."""
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = True
    data = {
        'version': '3.0', 'format': 'pgraph', 'nodes': [], 'edges': [],
        'line_resonators': [{
            'line_id': 0, 'label': 'TLold', 'pos': [0.0, 0.0],
            'FSR': 1.5, 'Ztx': 65.0, 'f_max': 6.0, 'port_end': 'xL',
            'Z0_port': 50.0, 'alpha_uniform': 0.0,
        }],
    }
    win._deserialize_ports_and_lines(data)
    assert len(win.ports) == 1
    migrated = win.line_resonators[0]
    assert migrated['ends']['xL'][0]['port_id'] == win.ports[0]['port_id']
    assert len(win._gui_hubs_payload()[0]['attachments']) == 2 * 4 + 1


def test_drag_moves_port_with_snap(para):
    gp, win, config = para
    port, _ = build_unattached_scene(win, config)
    # click on the port in normal mode arms the drag
    assert win._maybe_handle_ports_normal_click(
        canvas_event(win, 5.0, 0.0), False, False)
    assert win._glyph_drag_pending == ('port', port)
    # move past the threshold with the button held, then release
    win._on_motion(canvas_event(win, 7.9, 1.1))
    assert win._glyph_dragging == ('port', port)
    win._on_release(canvas_event(win, 7.9, 1.1))
    assert port['pos'] == (8.0, 1.0)                       # snapped to grid
    # undo restores the original position
    win._undo()
    assert win.ports[0]['pos'] == (5.0, 0.0)


def test_click_without_motion_does_not_move(para):
    gp, win, config = para
    port, _ = build_unattached_scene(win, config)
    win._maybe_handle_ports_normal_click(canvas_event(win, 5.0, 0.0),
                                         False, False)
    win._on_release(canvas_event(win, 5.0, 0.0))
    assert port['pos'] == (5.0, 0.0)
    assert win._glyph_drag_pending is None


def test_rotate_selected_line_and_hit_test(para):
    gp, win, config = para
    _, line = build_unattached_scene(win, config)
    win.selected_lines = [line]

    # six Ctrl+I steps = 90 degrees; glyph angle, not node positions, changes
    for _ in range(6):
        win._rotate_selected_nodes(-15)
    assert line['angle'] == pytest.approx(90.0)

    # the (wide) cylinder now extends along y: a point above the center hits,
    # a point far along x (inside the unrotated glyph) misses
    r = win.node_radius
    from graphulator.para_features.explicit_ports import LINE_BODY_W
    far = LINE_BODY_W * r * 0.9
    assert win._find_line_at_position(0.0, -4.0 + far) is line
    assert win._find_line_at_position(far, -4.0) is None


def test_glyph_angle_round_trips(para):
    gp, win, config = para
    port, line = build_unattached_scene(win, config)
    port['angle'] = 180.0
    line['angle'] = 90.0
    data = json.loads(json.dumps(win._serialize_graph()))
    win._deserialize_graph(data)
    assert win.ports[0]['angle'] == 180.0
    assert win.line_resonators[0]['angle'] == 90.0
    # attachment links start at the rotated lead tip: for a 180-degree port
    # the tip sits to the LEFT of the glyph center
    tip_x, tip_y = win._port_lead_tip(win.ports[0])
    assert tip_x < win.ports[0]['pos'][0]
    assert tip_y == pytest.approx(win.ports[0]['pos'][1])


# ---------------------------------------------------------------------------
# Auto-orientation, attachment selection/deletion, rubber-band parity
# ---------------------------------------------------------------------------


def build_vertical_pair_scene(win, config):
    """Nodes above and below the port's left side (auto-orient exercises)."""
    config.EXPLICIT_PORTS_MODE = True
    win._apply_explicit_ports_mode()
    node_a = add_node(win, 0, 'A', 0.0, freq=5.0)
    node_a['pos'] = (0.0, 2.0)
    node_b = add_node(win, 1, 'B', 0.0, freq=6.0)
    node_b['pos'] = (0.0, -2.0)
    port = win.add_port(label='P1', pos=(4.0, 0.0))
    return port


def test_port_auto_orients_toward_attachments(para):
    gp, win, config = para
    port = build_vertical_pair_scene(win, config)

    # unattached: keeps the stored angle
    assert win._port_effective_angle(port) == 0.0

    # one attachment: apex points straight at the node
    win.add_port_attachment(port, 0, rate=0.2)
    expected = np.degrees(np.arctan2(2.0, -4.0))           # toward (0, 2)
    assert win._port_effective_angle(port) == pytest.approx(expected)

    # two symmetric attachments: mean direction (straight left)
    win.add_port_attachment(port, 1, rate=0.2)
    assert win._port_effective_angle(port) == pytest.approx(180.0)

    # hit-testing follows the auto-orientation: glyph now extends LEFT
    assert win._find_port_at_position(3.2, 0.0) is port
    # ... and the attachment links leave from the rotated lead tip
    tip_x, tip_y = win._port_lead_tip(port)
    assert tip_x < 4.0 and tip_y == pytest.approx(0.0)


def test_manual_rotation_pins_and_survives_save(para):
    gp, win, config = para
    port = build_vertical_pair_scene(win, config)
    win.add_port_attachment(port, 0, rate=0.2)
    auto = win._port_effective_angle(port)

    win.selected_ports = [port]
    win._rotate_selected_nodes(-15)                        # Ctrl+I step
    assert port['angle_pinned'] is True
    assert win._port_effective_angle(port) == pytest.approx((auto + 15) % 360)

    data = json.loads(json.dumps(win._serialize_graph()))
    win._deserialize_graph(data)
    assert win.ports[0]['angle_pinned'] is True

    # unpinning resumes auto-orient
    win.ports[0]['angle_pinned'] = False
    assert win._port_effective_angle(win.ports[0]) == pytest.approx(auto)


def test_attachment_link_select_delete_undo(para):
    gp, win, config = para
    port = build_vertical_pair_scene(win, config)
    win.add_port_attachment(port, 0, rate=0.2)
    win.add_port_attachment(port, 1, rate=0.2)

    tip = win._port_lead_tip(port)
    mid = ((tip[0] + 0.0) / 2, (tip[1] + 2.0) / 2)        # link to node A
    consumed = win._maybe_handle_ports_normal_click(
        canvas_event(win, *mid), False, False)
    assert consumed is True
    assert len(win.selected_attachments) == 1

    win._delete_selected_nodes()                           # D key handler
    assert [a['node_id'] for a in port['attachments']] == [1]
    assert win.selected_attachments == []

    win._undo()
    assert len(win.ports[0]['attachments']) == 2


def test_rubber_band_selects_glyphs(para):
    gp, win, config = para
    port = build_vertical_pair_scene(win, config)
    line = win.add_line_resonator(label='TL1', pos=(6.0, -6.0), FSR=1.5,
                                  Ztx=65.0, f_max=6.0)
    win.selection_window = True
    win.selection_window_start = (2.0, -8.0)
    win._on_release_selection_window(canvas_event(win, 8.0, 2.0))
    assert port in win.selected_ports
    assert line in win.selected_lines

    win._delete_selected_nodes()
    assert port not in win.ports
    assert win.line_resonators == []


def test_same_end_multiport_is_allowed(para):
    """Several loads may tap the SAME end (e.g. a stub resonator read out by
    two ports): each contributes its own rank-one u_n(end) damper to its own
    hub column, which reproduces ABCD within the comb-truncation floor."""
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = True
    line = win.add_line_resonator(label='TL1', pos=(0.0, 0.0), FSR=1.5,
                                  Ztx=65.0, f_max=6.0, port_end='xL',
                                  Z0_port=50.0)
    first = win.ports[0]
    second = win.add_port(label='P2', pos=(9.0, 3.0))
    win.connect_line_end_to_port(line, 'xL', second)

    assert [c['port_id'] for c in line['ends']['xL']] == \
        [first['port_id'], second['port_id']]
    assert win._line_end_ports(line, 'xL') == [first, second]

    # two hub columns, each carrying the whole comb at the same end
    hubs = win._gui_hubs_payload()
    assert len(hubs) == 2
    n_modes = 2 * 4 + 1
    assert all(len(h['attachments']) == n_modes for h in hubs)

    from graphulator.graphulator_para import _compute_sparams_job
    f = np.linspace(0.5, 4.0, 41)
    comps = win._find_connected_components()
    res = _compute_sparams_job(win._build_sparams_job(comps[0], f, 0.5, 4.0, 41))
    S = res['S']
    assert S.shape[1:] == (2, 2)
    # lossless: each column carries unit power out of the two channels
    power = np.abs(S[:, 0, 0]) ** 2 + np.abs(S[:, 1, 0]) ** 2
    assert np.max(np.abs(power - 1.0)) < 1e-12


def test_line_only_graph_enters_scattering_mode(para):
    """A line-only graph has no GUI nodes (its comb is inside the macro) but
    is still a valid scattering problem."""
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = True
    win.add_line_resonator(label='TL1', pos=(0.0, 0.0), FSR=1.5, Ztx=65.0,
                           f_max=6.0, port_end='xL', Z0_port=50.0)
    assert win.nodes == []
    win._toggle_scattering_mode()
    assert win.scattering_mode is True
    ok, _ = win._validate_scattering_parameters()
    assert ok is True
