"""Capture golden regression artifacts for the hub-based dissipation refactor.

This is a SCRIPT, not a test. It was run once on the pre-refactor code
(main @ eb6fa69) to pickle {M, K, S, port order, port dict, labels} for a set
of representative graphs. `test_regression_golden.py` reloads the artifacts
and asserts the post-refactor build reproduces them.

Do not re-run this after the refactor lands unless you intend to re-baseline
(which defeats the purpose of the regression gate). If you must re-baseline,
check out the pre-refactor commit, run `python tests/capture_golden.py`, and
commit the refreshed artifacts under tests/golden/.

Coverage (per the handoff spec):
- multi-node graphs with conj nodes           (3MODE_AMP_CHAIN, DTWPA_MINIMAL2)
- cross-sector pump edges, nonzero phases     (DTWPA_MINIMAL2, 3MODE_AMP_CHAIN)
- >= 2 legacy B_ext ports                     (all fixtures)
- nonzero B_int                               (3MODE_AMP_CHAIN, programmatic)
- basis-reordered port ordering               (CIRC_FULL_SCATT_CBA)
- programmatic extract_graph_data build       (TWO_MODE_CONVERTER, FOUR_MODE_MIX)
"""

import pickle
from pathlib import Path

import numpy as np

from graphulator import autograph

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"

PGRAPH_FILES = [
    REPO_ROOT / "misc" / "PGRAPH_TESTS" / "CIRC_FULL_SCATT.pgraph",
    REPO_ROOT / "misc" / "PGRAPH_TESTS" / "CIRC_FULL_SCATT_CBA.pgraph",
    REPO_ROOT / "misc" / "PGRAPH_TESTS" / "DTWPA_MINIMAL2.pgraph",
    REPO_ROOT / "misc" / "PGRAPH_TESTS" / "3MODE_AMP_CHAIN.pgraph",
]

FREQ_GRID = np.linspace(-5.0, 5.0, 401)


def build_two_mode_converter():
    """Minimal two-mode frequency converter (same construction as
    test_scattering_matrix_vectorized.test_m_diagonal_formula_two_mode_graph,
    with a second port added so >= 2 K columns are exercised)."""
    nodes = [
        {'node_id': 0, 'label': 'A', 'pos': (0, 0), 'conj': False,
         'freq': 5.0, 'B_int': 0.1, 'B_ext': 1.0},
        {'node_id': 1, 'label': 'B', 'pos': (1, 0), 'conj': False,
         'freq': 7.0, 'B_int': 0.2, 'B_ext': 0.4},
    ]
    edges = [
        {'from_node_id': 0, 'to_node_id': 0, 'is_self_loop': True,
         'f_p': None, 'rate': None, 'phase': None},
        {'from_node_id': 1, 'to_node_id': 1, 'is_self_loop': True,
         'f_p': None, 'rate': None, 'phase': None},
        {'from_node_id': 0, 'to_node_id': 1, 'is_self_loop': False,
         'f_p': 2.0, 'rate': 0.5, 'phase': 30.0},
    ]
    assignments = {}
    for node in nodes:
        assignments[id(node)] = {'freq': node['freq'], 'B_int': node['B_int'],
                                 'B_ext': node['B_ext']}
    for edge in edges:
        if not edge['is_self_loop']:
            assignments[id(edge)] = {'f_p': edge['f_p'], 'rate': edge['rate'],
                                     'phase': edge['phase']}

    extractor = autograph.GraphExtractor()
    extractor.extract_graph_data(
        nodes=nodes, edges=edges,
        scattering_assignments=assignments,
        frequency_settings={'start': -5.0, 'stop': 5.0, 'points': 401},
        root_node_id=0,
    )
    return extractor


def build_four_mode_mix():
    """Four modes, one conj, a cross-sector pump edge with nonzero phase,
    two ports, nonzero B_int everywhere. Built programmatically."""
    nodes = [
        {'node_id': 0, 'label': 'a', 'pos': (0, 0), 'conj': False,
         'freq': 4.0, 'B_int': 0.05, 'B_ext': 0.8},
        {'node_id': 1, 'label': 'b', 'pos': (1, 0), 'conj': False,
         'freq': 6.0, 'B_int': 0.10, 'B_ext': None},
        {'node_id': 2, 'label': 'c*', 'pos': (2, 0), 'conj': True,
         'freq': 8.0, 'B_int': 0.15, 'B_ext': 0.3},
        {'node_id': 3, 'label': 'd', 'pos': (3, 0), 'conj': False,
         'freq': 10.0, 'B_int': 0.20, 'B_ext': None},
    ]
    edges = [
        {'from_node_id': 0, 'to_node_id': 0, 'is_self_loop': True,
         'f_p': None, 'rate': None, 'phase': None},
        {'from_node_id': 2, 'to_node_id': 2, 'is_self_loop': True,
         'f_p': None, 'rate': None, 'phase': None},
        {'from_node_id': 0, 'to_node_id': 1, 'is_self_loop': False,
         'f_p': 2.0, 'rate': 0.6, 'phase': 0.0},
        # cross-sector (normal -> conj): amplification-type coupling
        {'from_node_id': 1, 'to_node_id': 2, 'is_self_loop': False,
         'f_p': 14.0, 'rate': 0.4, 'phase': 45.0},
        {'from_node_id': 2, 'to_node_id': 3, 'is_self_loop': False,
         'f_p': 18.0, 'rate': 0.3, 'phase': 120.0},
    ]
    assignments = {}
    for node in nodes:
        assignments[id(node)] = {'freq': node['freq'], 'B_int': node['B_int'],
                                 'B_ext': node['B_ext']}
    for edge in edges:
        if not edge['is_self_loop']:
            assignments[id(edge)] = {'f_p': edge['f_p'], 'rate': edge['rate'],
                                     'phase': edge['phase']}

    extractor = autograph.GraphExtractor()
    extractor.extract_graph_data(
        nodes=nodes, edges=edges,
        scattering_assignments=assignments,
        frequency_settings={'start': -5.0, 'stop': 5.0, 'points': 401},
        root_node_id=0,
    )
    return extractor


def capture(name, extractor):
    gsm = autograph.GraphScatteringMatrix(extractor, FREQ_GRID)
    labels = {pid: gsm._get_port_label(pid) for pid in gsm.port_ids}
    artifact = {
        'name': name,
        'f': FREQ_GRID.copy(),
        'M': gsm.M.copy(),
        'K': gsm.K.copy(),
        'S': gsm.S.copy(),
        'det_M': gsm.det_M.copy(),
        'num_ports': gsm.num_ports,
        'port_ids': list(gsm.port_ids),
        'port_dict': dict(gsm.port_dict),
        'port_labels': labels,
        'basis_order': list(extractor.graph_data['basis_order']),
        'root_node_id': extractor.graph_data['root_node_id'],
    }
    GOLDEN_DIR.mkdir(exist_ok=True)
    path = GOLDEN_DIR / f"{name}.pkl"
    with open(path, 'wb') as fh:
        pickle.dump(artifact, fh)
    print(f"captured {name}: modes={gsm.num_modes} ports={gsm.num_ports} -> {path}")
    return artifact


def build_all():
    """Return {name: extractor} for every golden graph (shared with the test)."""
    extractors = {}
    for path in PGRAPH_FILES:
        extractor = autograph.GraphExtractor()
        extractor.extract_from_pgraph(autograph.load_pgraph(path))
        extractors[path.stem] = extractor
    extractors['TWO_MODE_CONVERTER'] = build_two_mode_converter()
    extractors['FOUR_MODE_MIX'] = build_four_mode_mix()
    return extractors


def main():
    for name, extractor in build_all().items():
        capture(name, extractor)


if __name__ == '__main__':
    main()
