"""Regression tests for the vectorized GraphScatteringMatrix builds.

The M/S/det builds were vectorized over the frequency axis (batched
np.linalg.inv/det). These tests pin the numerics to the original
per-frequency-point algorithm, reimplemented as a reference here.
"""

from pathlib import Path

import numpy as np
import pytest
from more_itertools import collapse

from graphulator import autograph

REPO_ROOT = Path(__file__).resolve().parents[1]

PGRAPH_FILES = [
    REPO_ROOT / "misc" / "PGRAPH_TESTS" / "CIRC_FULL_SCATT.pgraph",
    REPO_ROOT / "misc" / "PGRAPH_TESTS" / "DTWPA_MINIMAL2.pgraph",
    REPO_ROOT / "misc" / "PGRAPH_TESTS" / "3MODE_AMP_CHAIN.pgraph",
]


def reference_build(gsm):
    """The pre-vectorization per-frequency-point algorithm, verbatim."""
    ext = gsm.extractor
    f_root_s = gsm.f_root_s
    num_modes = len(ext.graph_data['nodes'])
    M = np.zeros((len(f_root_s), num_modes, num_modes), dtype=complex)
    acc = list(collapse(ext.get_accumulated_frequencies(), base_type=tuple))

    # Diagonals: rebuild the drive-signal dict once per frequency point
    for idx, node in enumerate(ext.graph_data['nodes']):
        node_id = node['node_id']
        f0 = node['freq']
        Btot = node['B_int'] if node['B_ext'] is None else node['B_int'] + node['B_ext']
        conj_state = node['conj']
        for f_idx, f_root in enumerate(f_root_s):
            drive_signals = {nid: f_root + f_offset for nid, f_offset in acc}
            f_drive = drive_signals.get(node_id, f_root)
            if conj_state:
                M[f_idx, idx, idx] = f_drive + f0 + Btot * 1j / 2
            else:
                M[f_idx, idx, idx] = f_drive - f0 + Btot * 1j / 2

    # Off-diagonals were already vectorized before the change; copy them over
    for f_idx in range(len(f_root_s)):
        offdiag = gsm.M[f_idx].copy()
        np.fill_diagonal(offdiag, 0)
        M[f_idx] += offdiag

    K = gsm.K
    nports = gsm.num_ports
    S = np.empty((len(f_root_s), nports, nports), dtype=complex)
    detM = np.empty(len(f_root_s), dtype=complex)
    for i in range(len(f_root_s)):
        S[i] = 1j * K.T @ np.linalg.inv(M[i]) @ K - np.eye(nports)
        detM[i] = np.linalg.det(M[i])
    return M, S, detM


@pytest.mark.parametrize("pgraph_path", PGRAPH_FILES, ids=lambda p: p.stem)
def test_vectorized_matches_reference(pgraph_path):
    pg = autograph.load_pgraph(pgraph_path)
    extractor = autograph.GraphExtractor()
    extractor.extract_from_pgraph(pg)

    f = np.linspace(-5, 5, 501)
    gsm = autograph.GraphScatteringMatrix(extractor, f)
    M_ref, S_ref, det_ref = reference_build(gsm)

    assert np.allclose(gsm.M, M_ref, rtol=1e-12, atol=0)
    assert np.allclose(gsm.S, S_ref, rtol=1e-10, atol=1e-14)
    assert np.allclose(gsm.det_M, det_ref, rtol=1e-10, atol=0)
    assert np.allclose(gsm.SdB, 20 * np.log10(np.abs(S_ref)), rtol=1e-10)
    assert np.allclose(gsm.det_M_dB, 20 * np.log10(np.abs(det_ref)), rtol=1e-10)


def test_m_diagonal_formula_two_mode_graph():
    """Hand-check the M diagonal on a minimal two-mode frequency converter."""
    nodes = [
        {'node_id': 0, 'label': 'A', 'pos': (0, 0), 'conj': False,
         'freq': 5.0, 'B_int': 0.1, 'B_ext': 1.0},
        {'node_id': 1, 'label': 'B', 'pos': (1, 0), 'conj': False,
         'freq': 7.0, 'B_int': 0.2, 'B_ext': None},
    ]
    edges = [
        {'from_node_id': 0, 'to_node_id': 0, 'is_self_loop': True,
         'f_p': None, 'rate': None, 'phase': None},
        {'from_node_id': 0, 'to_node_id': 1, 'is_self_loop': False,
         'f_p': 2.0, 'rate': 0.5, 'phase': 0.0},
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
        frequency_settings={'start': -1.0, 'stop': 1.0, 'points': 5},
        root_node_id=0,
    )

    f = np.linspace(-1.0, 1.0, 5)
    gsm = autograph.GraphScatteringMatrix(extractor, f)

    # Node A is the root: drive = f; node B accumulates the pump: drive = f + f_p
    expected_00 = f - 5.0 + (0.1 + 1.0) * 1j / 2
    expected_11 = (f + 2.0) - 7.0 + 0.2 * 1j / 2
    assert np.allclose(gsm.M[:, 0, 0], expected_00)
    assert np.allclose(gsm.M[:, 1, 1], expected_11)

    # Off-diagonal coupling beta = rate/2 * exp(i*phase)
    assert np.allclose(gsm.M[:, 0, 1], 0.25)
    assert np.allclose(gsm.M[:, 1, 0], 0.25)
