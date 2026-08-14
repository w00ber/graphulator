"""Port indices must follow the basis order used to build K, not sorted node ids.

`port_dict` is filled by walking `graph_data['nodes']`, so port index 0 is the
first port *in the basis*. Basis reordering can move a higher-numbered node
ahead of a lower-numbered one, at which point sorting the node ids to label the
S-matrix silently permutes the port names. CIRC_FULL_SCATT_CBA.pgraph is stored
in exactly that state (nodes C, B, A with node ids 2, 1, 0).
"""

import os

import numpy as np
import pytest

from graphulator import autograph

PGRAPH_DIR = os.path.join(os.path.dirname(__file__), os.pardir, "misc", "PGRAPH_TESTS")
REORDERED = os.path.join(PGRAPH_DIR, "CIRC_FULL_SCATT_CBA.pgraph")
IN_ORDER = os.path.join(PGRAPH_DIR, "CIRC_FULL_SCATT.pgraph")


def build(path, points=5):
    extractor = autograph.GraphExtractor()
    extractor.extract_from_pgraph(autograph.load_pgraph(path))
    return autograph.GraphScatteringMatrix(extractor, np.linspace(-2, 2, points))


def test_port_ids_follow_basis_not_sorted_node_ids():
    gsm = build(REORDERED)

    # The fixture is only meaningful while its ports stay out of id order
    assert gsm.port_ids != sorted(gsm.port_ids)
    assert gsm.port_ids == [1, 0]


def test_k_columns_match_port_ids():
    """Column c of K must carry sqrt(B_ext) in the mode row of port_ids[c]."""
    gsm = build(REORDERED)
    basis = gsm.extractor.graph_data['basis_order']

    for col, port_id in enumerate(gsm.port_ids):
        rows = np.flatnonzero(gsm.K[:, col])
        assert rows.tolist() == [basis.index(port_id)]
        assert gsm.K[rows[0], col] == pytest.approx(np.sqrt(gsm.port_dict[port_id]))


def test_sorted_port_order_would_permute_s():
    """Pin the mislabeling: same M, sorted columns, S comes out permuted."""
    gsm = build(REORDERED)
    basis = gsm.extractor.graph_data['basis_order']

    sorted_ids = sorted(gsm.port_dict.keys())
    K_sorted = np.zeros_like(gsm.K)
    for col, port_id in enumerate(sorted_ids):
        K_sorted[basis.index(port_id), col] = np.sqrt(gsm.port_dict[port_id])
    S_sorted = 1j * (K_sorted.T @ np.linalg.inv(gsm.M) @ K_sorted) - np.eye(gsm.num_ports)

    perm = [sorted_ids.index(pid) for pid in gsm.port_ids]
    assert np.allclose(gsm.S, S_sorted[:, perm][:, :, perm])
    # ...and the two orderings really do disagree, so the permutation matters
    assert not np.allclose(gsm.S, S_sorted)


def test_ascending_graph_unaffected():
    """Graphs whose ports are already in id order keep their previous indices."""
    gsm = build(IN_ORDER)
    assert gsm.port_ids == sorted(gsm.port_dict.keys())


def test_gui_component_port_ids_helper():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        # QtWebEngine refuses to sandbox as root (CI containers)
        os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")
    try:
        from PySide6.QtWidgets import QApplication

        # matplotlib.use('QtAgg') at import time needs a live QApplication
        QApplication.instance() or QApplication([])
        from graphulator.graphulator_para import _component_port_ids
    except ImportError as exc:  # no Qt / graphics libs in this environment
        pytest.skip(f"GUI stack unavailable: {exc}")

    comp = {'port_ids': [1, 0], 'port_dict': {1: {}, 0: {}}}
    assert _component_port_ids(comp) == [1, 0]

    # Results predating the stored list fall back to port_dict insertion order
    assert _component_port_ids({'port_dict': {1: {}, 0: {}}}) == [1, 0]
    assert _component_port_ids({}) == []
