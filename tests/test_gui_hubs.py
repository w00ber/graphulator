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
    assert len(data['ports']) == 1
    assert len(data['line_resonators']) == 1

    # load with the mode off: it must auto-enable and restore everything
    config.EXPLICIT_PORTS_MODE = False
    win._deserialize_graph(data)
    assert config.EXPLICIT_PORTS_MODE is True
    assert len(win.ports) == 1
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
