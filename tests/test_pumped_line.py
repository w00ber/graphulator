"""Pumped line termination: linked conjugate twin + rank-one pump bus.

Physics: docs/pumped_line_termination.md. The modulated element at one end
couples the comb to its conjugate twin through the outer product g g^T of
the end profile (rank one), and one pump drives amplification AND
conversion pairs through that block. Ports stay one hub column per sector.

Also pins two core fixes the macro exposed:
  * spanning-tree edges are stored parent->child (they were stored as the
    canonically sorted pair, so a hop traversed in decreasing-id order
    credited the pump offset to the parent and left the child with no
    frame — silently falling back to the root drive);
  * an explicit per-edge 'sector' frame rule (crossing into the conjugate
    sector is -f_p), because the frequency-ordering heuristic cannot
    orient pump edges onto a +-n comb.
"""

import json
import os

import numpy as np
import pytest

from graphulator import autograph
from graphulator.autograph import LineResonator

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")

HERE = os.path.dirname(__file__)
SCENES_DIR = os.path.join(HERE, os.pardir, "examples", "test_scenes")


# ---------------------------------------------------------------------------
# core
# ---------------------------------------------------------------------------

def _chain(ids, freqs, f_p, root):
    """Linear pumped chain over arbitrary ids, rooted anywhere."""
    nodes = [{'node_id': i, 'label': str(i), 'pos': (k, 0), 'conj': False,
              'freq': f, 'B_int': 0.0, 'B_ext': 0.1 if k in (0, len(ids) - 1)
              else None}
             for k, (i, f) in enumerate(zip(ids, freqs))]
    edges = [{'from_node_id': a, 'to_node_id': b, 'is_self_loop': False}
             for a, b in zip(ids[:-1], ids[1:])]
    assign = {}
    for n in nodes:
        assign[id(n)] = {'freq': n['freq'], 'B_int': 0.0, 'B_ext': n['B_ext']}
    for e in edges:
        assign[id(e)] = {'f_p': f_p, 'rate': 0.02, 'phase': 0.0}
    ext = autograph.GraphExtractor()
    ext.extract_graph_data(nodes=nodes, edges=edges,
                           scattering_assignments=assign,
                           frequency_settings={'start': 4.0, 'stop': 6.0,
                                               'points': 5},
                           root_node_id=root)
    return ext


def test_tree_edges_are_oriented_parent_to_child():
    """Rooting a chain at its HIGH-id end must give every node a frame:
    the old canonical (sorted) storage credited hops traversed downward to
    the wrong endpoint."""
    ids = [0, 1, 2]
    for root in (0, 2):
        ext = _chain(ids, [5.0, 6.0, 7.0], 1.0, root)
        branches = ext.graph_data['tree_edges']
        parents = [b[0][0] for b in branches]
        assert root in parents
        gsm = autograph.GraphScatteringMatrix(ext, np.array([5.0]))
        assert set(gsm.drive_signals) == set(ids), \
            f"root {root}: nodes without a frame"
        # up-conversion chain 5 -> 6 -> 7: frames step by +f_p away from
        # the root's frequency, whichever end is the root
        frames = {i: float(np.atleast_1d(gsm.drive_signals[i])[0])
                  for i in ids}
        assert frames[1] - frames[0] == pytest.approx(1.0)
        assert frames[2] - frames[1] == pytest.approx(1.0)


def test_string_ids_get_frames_when_traversed_downward():
    """String ids sort in a way unrelated to traversal order (the comb's
    'line:0:n-1' < 'line:0:n0'); every node must still get a frame."""
    ids = ['line:0:n0', 'line:0:n-1', 'line:0:n1']
    ext = _chain(ids, [5.0, 6.0, 7.0], 1.0, 'line:0:n0')
    gsm = autograph.GraphScatteringMatrix(ext, np.array([5.0]))
    assert set(gsm.drive_signals) == set(ids)


def test_sector_frame_rule_overrides_ordering_heuristic():
    """With frame_rule='sector' an edge into a conjugate node is -f_p
    regardless of the nodes' natural frequencies (a negative-frequency
    twin member would fool the eff_to > eff_from heuristic)."""
    nodes = [
        {'node_id': 'a', 'label': 'a', 'pos': (0, 0), 'conj': False,
         'freq': 5.0, 'B_int': 0.0, 'B_ext': 0.1},
        # a negative-frequency twin member: eff_to = -(-6) = 6 > eff_from = 5
        # fools the ordering heuristic into calling this up-conversion
        {'node_id': 'b', 'label': 'b', 'pos': (1, 0), 'conj': True,
         'freq': -6.0, 'B_int': 0.0, 'B_ext': 0.1},
    ]
    edge = {'from_node_id': 'a', 'to_node_id': 'b', 'is_self_loop': False}
    for rule, expected in ((None, +9.0), ('sector', -9.0)):
        assign = {id(nodes[0]): {'freq': 5.0, 'B_int': 0.0, 'B_ext': 0.1},
                  id(nodes[1]): {'freq': -6.0, 'B_int': 0.0, 'B_ext': 0.1},
                  id(edge): {'f_p': 9.0, 'rate': 0.02, 'phase': 0.0}}
        if rule:
            assign[id(edge)]['frame_rule'] = rule
        ext = autograph.GraphExtractor()
        ext.extract_graph_data(nodes=nodes, edges=[edge],
                               scattering_assignments=assign,
                               frequency_settings={'start': 5.0, 'stop': 5.0,
                                                   'points': 1},
                               root_node_id='a')
        gsm = autograph.GraphScatteringMatrix(ext, np.array([5.0]))
        offset = float(np.atleast_1d(gsm.drive_signals['b'])[0]) - 5.0
        assert offset == pytest.approx(expected), rule


def test_line_resonator_conj_expands_conjugate_comb():
    line = LineResonator(line_id='t', label='T*', FSR=1.5, Ztx=65.0,
                         f_max=6.0, conj=True)
    nodes, _ = line.expand()
    assert nodes and all(n['conj'] for n in nodes)
    assert line.to_dict()['conj'] is True
    # dict form survives the extractor's normalization
    norm = autograph._normalize_line(line.to_dict())
    assert norm.conj is True
    assert autograph.pgraph_line_to_resonator(
        {'line_id': 1, 'FSR': 1.5, 'Ztx': 65.0, 'f_max': 6.0,
         'conj': True}).conj is True


# ---------------------------------------------------------------------------
# GUI macro
# ---------------------------------------------------------------------------

@pytest.fixture()
def para(tmp_path):
    try:
        from PySide6.QtWidgets import QApplication
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
    config.EXPLICIT_PORTS_MODE = True
    win._apply_explicit_ports_mode()
    yield gp, win, config
    config.EXPLICIT_PORTS_MODE = original


def build_pumped_line(win, f_p=9.0, rate=0.05, n_ref=3, Z0=50.0):
    line = win.add_line_resonator(label='TL1', pos=(0.0, 0.0), FSR=1.5,
                                  Ztx=65.0, f_max=6.0, port_end='xL',
                                  Z0_port=Z0)
    twin = win.set_line_pump(line, 'x0', f_p=f_p, rate=rate, n_ref=n_ref)
    return line, twin


def live_S(win, f_start, f_stop, points):
    from graphulator.graphulator_para import _compute_sparams_job
    comps = win._find_connected_components()
    assert len(comps) == 1
    f = np.linspace(f_start, f_stop, points)
    job = win._build_sparams_job(comps[0], f, f_start, f_stop, points)
    res = _compute_sparams_job(job)
    assert res is not None
    labels = [res['port_dict'][p]['label'] for p in res['port_ids']]
    return res['S'], labels, job


def test_set_line_pump_creates_linked_twin_and_port(para):
    gp, win, config = para
    line, twin = build_pumped_line(win)
    assert twin['conj'] is True and twin['twin_of'] == line['line_id']
    assert twin['label'] == 'TL1*'
    assert line['pump']['twin_id'] == twin['line_id']
    # the twin mirrors the primary's physics
    for key in ('FSR', 'Ztx', 'f_max', 'Z0_port', 'alpha_uniform'):
        assert twin[key] == line[key]
    # ... and carries its own port at the same end as the primary's
    assert [p['label'] for p in win.ports] == ['TL1', 'TL1*']
    assert [c['kind'] for c in win._end_conns(twin, 'xL')] == ['port']
    # editing the primary propagates
    line['FSR'] = 2.0
    win._sync_all_twins()
    assert twin['FSR'] == 2.0
    # a twin cannot be pumped itself; taps are refused on both
    with pytest.raises(ValueError):
        win.set_line_pump(twin, 'x0', f_p=9.0, rate=0.05)
    node = {'node_id': 0, 'label': 'A', 'pos': (5.0, 0.0), 'conj': False,
            'color': 'cornflowerblue', 'color_key': 'BLUE',
            'node_size_mult': 1.0, 'label_size_mult': 1.0}
    win.nodes.append(node)
    win.scattering_assignments[0] = {'freq': 4.4, 'B_int': 0.0}
    with pytest.raises(ValueError):
        win.connect_line_end_to_node(line, 'x0', node, rate=0.03)


def test_pump_block_is_rank_one_with_reference_pair_normalization(para):
    gp, win, config = para
    line, twin = build_pumped_line(win, f_p=9.0, rate=0.05, n_ref=3)
    N = win.line_resonator_for(line).N
    pe = win._gui_pump_edges()
    assert len(pe) == (2 * N) ** 2          # DC excluded on both combs
    sig = sorted({e['from_node_id'] for e, _ in pe})
    idl = sorted({e['to_node_id'] for e, _ in pe})
    B = np.zeros((len(sig), len(idl)))
    for e, prm in pe:
        assert prm['f_p'] == 9.0 and prm['frame_rule'] == 'sector'
        B[sig.index(e['from_node_id']), idl.index(e['to_node_id'])] = \
            prm['rate'] * np.cos(np.radians(prm['phase']))
    assert np.linalg.matrix_rank(B, tol=1e-12) == 1
    # the (n_ref, m_ref) = (3, 3) entry carries the user's rate exactly
    n_ref, m_ref = win._pump_reference_pair(line)
    assert (n_ref, m_ref) == (3, 3)
    ref = B[sig.index(f"line:{line['line_id']}:n3"),
            idl.index(f"line:{twin['line_id']}:n3")]
    assert abs(ref) == pytest.approx(0.05)
    # inductive envelope: |B_nm| = rate * (n m / 9)^(-1/2)
    for n in (1, 2, 4):
        for m in (1, 4):
            v = B[sig.index(f"line:{line['line_id']}:n{n}"),
                  idl.index(f"line:{twin['line_id']}:n{m}")]
            assert abs(v) == pytest.approx(0.05 * (n * m / 9.0) ** -0.5)


def test_pumped_line_is_one_component_with_consistent_frames(para):
    gp, win, config = para
    line, twin = build_pumped_line(win)
    S, labels, job = live_S(win, 3.5, 5.5, 5)
    assert labels == ['TL1', 'TL1*']
    ext = autograph.GraphExtractor()
    ext.extract_graph_data(nodes=job['nodes'], edges=job['edges'],
                           scattering_assignments=job['scattering_assignments'],
                           frequency_settings={'start': 4.5, 'stop': 4.5,
                                               'points': 1},
                           root_node_id=job['root_node_id'],
                           hubs=job['hubs'],
                           line_resonators=job['line_resonators'])
    gsm = autograph.GraphScatteringMatrix(ext, np.array([4.5]))
    frames = {}
    for nd in ext.graph_data['nodes']:
        assert nd['node_id'] in gsm.drive_signals, nd['node_id']
        frames.setdefault(nd['conj'], set()).add(
            round(float(np.atleast_1d(gsm.drive_signals[nd['node_id']])[0]), 9))
    assert frames[False] == {4.5}            # signal cluster: omega
    assert frames[True] == {4.5 - 9.0}       # twin cluster: omega - f_p


def test_pumped_line_amplifies_and_is_pseudo_unitary(para):
    """Lossless: |S_ss|^2 - |S_is|^2 = 1 (Manley-Rowe / symplectic), with
    real gain at the degenerate point."""
    gp, win, config = para
    build_pumped_line(win, f_p=9.0, rate=0.05, n_ref=3)
    S, labels, _ = live_S(win, 3.5, 5.5, 81)
    s, i = labels.index('TL1'), labels.index('TL1*')
    gain = np.abs(S[:, s, s]) ** 2
    conv = np.abs(S[:, i, s]) ** 2
    assert np.max(np.abs(gain - conv - 1.0)) < 1e-12
    assert gain.max() > 1.005 and conv.max() > 0.005
    # the roles are symmetric: pumping harder gives more gain
    win.line_resonators[0]['pump']['rate'] = 0.15
    win._invalidate_scattering_data()
    S2, _, _ = live_S(win, 3.5, 5.5, 81)
    assert np.max(np.abs(S2[:, s, s]) ** 2) > gain.max()


def test_pumped_line_round_trip_and_invariants(para):
    gp, win, config = para
    line, twin = build_pumped_line(win)
    data = json.loads(json.dumps(win._serialize_graph()))
    win._deserialize_graph(data)
    r_line = next(l for l in win.line_resonators if l.get('pump'))
    r_twin = win.line_twin(r_line)
    assert r_twin is not None and r_twin['conj'] is True
    assert r_line['pump']['f_p'] == 9.0 and r_line['pump']['n_ref'] == 3
    assert [p['label'] for p in win.ports] == ['TL1', 'TL1*']

    # deleting the twin un-pumps the primary; clearing the pump removes the
    # twin and its now-unused port
    win.remove_line_resonator(r_twin)
    assert r_line['pump'] is None
    assert len(win.line_resonators) == 1
    assert [p['label'] for p in win.ports] == ['TL1']
    twin2 = win.set_line_pump(r_line, 'x0', f_p=9.0, rate=0.05, n_ref=3)
    assert len(win.ports) == 2
    win.clear_line_pump(r_line)
    assert twin2 not in win.line_resonators
    assert [p['label'] for p in win.ports] == ['TL1']


def test_pumped_line_generated_code_matches_live_S(para):
    gp, win, config = para
    build_pumped_line(win)
    win._enter_scattering_mode()
    win.properties_panel.freq_center_spin.setValue(4.5)
    win.properties_panel.freq_span_spin.setValue(2.0)
    win.properties_panel.freq_points_spin.setValue(41)
    code = win.properties_panel._generate_scattering_calculation_code()
    assert code is not None
    assert 'conj=True' in code and "'frame_rule': 'sector'" in code
    head = code.split("# Plot S-parameters")[0].rsplit("# ====", 1)[0]
    ns = {}
    exec(compile(head, '<generated>', 'exec'), ns)
    gsm = ns['scattering_matrix']
    S, labels, _ = live_S(win, 3.5, 5.5, 41)
    np.testing.assert_allclose(gsm.S, S, rtol=1e-12, atol=1e-14)
    assert gsm.port_labels == labels


def test_pump_bus_selection_delete_and_panel(para):
    gp, win, config = para
    line, twin = build_pumped_line(win)
    pts = win._pump_bus_wire(line)
    assert pts is not None
    mx, my = pts[len(pts) // 2]
    assert win._find_pump_bus_at_position(mx, my) is line

    win.selected_pump_buses = [line]
    win._update_properties_panel()
    assert win.properties_panel.current_type == 'pump'
    assert win.properties_panel.current_object is line['pump']

    win._select_all()
    assert win.selected_pump_buses == [line]
    win.selected_nodes, win.selected_ports, win.selected_lines = [], [], []
    win.selected_attachments, win.selected_taps = [], []
    win.selected_pump_buses = [line]
    assert win._delete_selected_ports_lines() == 1
    assert line['pump'] is None and len(win.line_resonators) == 1


def test_bundled_pumped_scene_loads(para):
    gp, win, config = para
    win._open_graph_file(os.path.join(SCENES_DIR,
                                      "LINE_PUMPED_TERMINATION.pgraph"))
    line = next(l for l in win.line_resonators if l.get('pump'))
    assert win.line_twin(line) is not None
    ok, msg = win._validate_scattering_parameters()
    assert ok, msg


# ---------------------------------------------------------------------------
# normalization vs the oracle (docs/pumped_line_termination.md, sec. 6)
# ---------------------------------------------------------------------------

def test_pump_rate_normalization_matches_oracle(para):
    """rate = 2 g FSR / pi with g = dK / (4 sqrt(w_n C_n w_m C_m)).

    Line terminated in a modulated inductor at x0 (build_galvanic), port at
    xL, negligible static loading so the oracle comb is the open-open one.
    In the isolated-mode regime the graph reproduces the oracle's gain and
    idler lineshapes to a few 1e-3; the residual floor is the DC comb mode,
    which the macro excludes (free mode) but the oracle pumps.
    """
    import sys
    sys.path.insert(0, os.path.join(HERE))
    import cmtline_core as core
    from graphulator.graphulator_para import _compute_sparams_job
    gp, win, config = para

    N, LJ, Cd, Z0, dK = 12, 1e4, 1e-8, 10.0, 1.0
    Cm, Km, Rm, P, f = core.build_galvanic(N, LJ, Cd, ell=1.0, Ztx=1.0, v=1.0)
    wp = 6 * np.pi
    ws = np.linspace(2.8 * np.pi, 3.2 * np.pi, 81)
    Sss_o, Sis_o = core.hb_signal_idler(ws, wp, dK * LJ, Cm, Km, Rm, P, f, Z0)
    wi = wp - ws
    G_o = np.abs(Sss_o) ** 2
    C_o = (ws / wi) * np.abs(Sis_o) ** 2      # power-wave -> photon-flux

    fs = ws / np.pi                            # natural omega = n*pi <-> f = n
    line = win.add_line_resonator(label='TL', pos=(0, 0), FSR=1.0, Ztx=1.0,
                                  f_max=N + 0.4, port_end='xL', Z0_port=Z0)
    g = dK / (4 * np.sqrt((3 * np.pi * 0.5) ** 2))     # (n, m) = (3, 3)
    win.set_line_pump(line, 'x0', f_p=6.0, rate=2 * g / np.pi, n_ref=3)
    comps = win._find_connected_components()
    job = win._build_sparams_job(comps[0], fs, fs[0], fs[-1], len(fs))
    res = _compute_sparams_job(job)
    lab = [res['port_dict'][p]['label'] for p in res['port_ids']]
    s, i = lab.index('TL'), lab.index('TL*')
    G_g = np.abs(res['S'][:, s, s]) ** 2
    C_g = np.abs(res['S'][:, i, s]) ** 2

    assert G_o.max() > 2.0                      # real gain (> 3 dB)
    assert np.max(np.abs(G_g - G_o)) / G_o.max() < 5e-3
    assert np.max(np.abs(C_g - C_o)) / C_o.max() < 8e-3
    # and it is the normalization, not a coincidence: 2x the rate is wrong
    line['pump']['rate'] = 4 * g / np.pi
    win._invalidate_scattering_data()
    res2 = _compute_sparams_job(win._build_sparams_job(comps[0], fs, fs[0],
                                                       fs[-1], len(fs)))
    G_2 = np.abs(res2['S'][:, s, s]) ** 2
    assert np.max(np.abs(G_2 - G_o)) / G_o.max() > 0.1


# ---------------------------------------------------------------------------
# Pump-bus stroke count (PRXQ visual language, docs sec. 7.6)
# ---------------------------------------------------------------------------

def test_pump_bus_always_draws_three_strokes(para):
    """The bus draws the UNION of the families, always.

    Computing the count instead would claim selectivity the device does not
    have (on a harmonic comb both families are satisfied together) and would
    in fact be measuring f_max: the test below shows the same line and pump
    changing "reachability" purely because the comb was truncated shorter.
    """
    from graphulator.para_features.explicit_ports import PUMP_BUS_STROKES
    assert PUMP_BUS_STROKES == 3

    gp, win, config = para
    line = win.add_line_resonator(label='TL1', pos=(0.0, 2.0), FSR=1.5,
                                  Ztx=65.0, f_max=6.0, port_end='xL')
    win.set_line_pump(line, 'x0', f_p=9.0, rate=0.05, n_ref=3,
                      twin_pos=(0.0, -2.0))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for f_p in (1.5, 4.5, 9.0, 20.0):
        line['pump']['f_p'] = f_p
        fig, ax = plt.subplots()
        win._draw_ports_and_lines(ax=ax)
        buses = [ln for ln in ax.lines
                 if len(ln.get_xdata()) == len(win._pump_bus_wire(line))]
        assert len(buses) >= 3, (f_p, len(buses))
        plt.close(fig)


def test_pump_truncation_gaps_flag_f_max_not_the_device(para):
    """The reachability test measures the TRUNCATION, so it is reported as a
    'raise f_max' warning rather than driving the glyph."""
    gp, win, config = para
    line = win.add_line_resonator(label='TL1', pos=(0.0, 2.0), FSR=1.5,
                                  Ztx=65.0, f_max=6.0, port_end='xL')
    win.set_line_pump(line, 'x0', f_p=9.0, rate=0.05, n_ref=3,
                      twin_pos=(0.0, -2.0))
    # comb reaches 6.0; the nearest conversion partner is 9 + 1.5 = 10.5,
    # outside it, so the model has NO conversion pair at all
    assert win.pump_truncation_gaps(line) == {'conversion'}

    # the SAME device modelled with a longer comb has no gap: 10.5 = 7 x FSR
    # is a real mode the short comb merely omitted
    line['f_max'] = 18.0
    win._sync_all_twins()
    assert win.pump_truncation_gaps(line) == set()

    # a pump beyond twice the last harmonic loses amplification too
    line['f_max'] = 6.0
    line['pump']['f_p'] = 40.0
    assert win.pump_truncation_gaps(line) == {'amplification', 'conversion'}
    # ... but a pump below twice the FUNDAMENTAL has no amplification pair in
    # the line either, so that is a real absence and not flagged
    line['pump']['f_p'] = 1.0
    assert 'amplification' not in win.pump_truncation_gaps(line)

    # an unpumped line has nothing to report
    other = win.add_line_resonator(label='TL2', pos=(9.0, 0.0), FSR=1.0,
                                   Ztx=65.0, f_max=4.0, port_end=None)
    assert win.pump_truncation_gaps(other) == set()
    assert win._pump_bus_wire(other) is None


def test_multi_wire_draws_requested_stroke_count(para):
    """The strokes are offset along the curve normal, so the count survives
    curvature — and each stroke stays close to the path."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    gp, win, config = para
    line = win.add_line_resonator(label='TL1', pos=(0.0, 2.0), FSR=1.5,
                                  Ztx=65.0, f_max=6.0, port_end='xL')
    win.set_line_pump(line, 'x0', f_p=4.5, rate=0.05, n_ref=2,
                      twin_pos=(0.0, -2.0))
    pts = win._pump_bus_wire(line)
    assert pts is not None

    for n in (1, 2, 3):
        fig, ax = plt.subplots()
        win._draw_multi_wire(ax, pts, n, 'black', 1.5)
        drawn = [ln for ln in ax.lines]
        assert len(drawn) == n, (n, len(drawn))
        for ln in drawn:
            xy = np.column_stack(ln.get_data())
            assert xy.shape == pts.shape
            # every stroke hugs the routed path
            assert np.max(np.hypot(*(xy - pts).T)) < 0.4 * win.node_radius
        plt.close(fig)
