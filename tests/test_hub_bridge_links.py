"""Hub bridge links: shared ports keep the pump-frame accumulation intact.

A multi-attachment hub can join parts of the graph no real (pump) edge
connects. The spanning tree must still reach those parts — through a
zero-offset link (a resistor does not convert frequency) — so their f_p
accumulation is not silently dropped. Links are only created between
real-edge-disconnected components, so pump-derived frames are never
rerouted within a connected region.

Also covers extract_from_pgraph reading the .pgraph v3.0 'ports' /
'line_resonators' sections (the programmatic route must match the GUI).
"""

import numpy as np
import pytest

from graphulator import autograph


def bridged_extractor(hub=True):
    """A (root) -- [shared port] -- B --pump(f_p=2)--> C; no real edge A-B."""
    nodes = [
        {'node_id': 0, 'label': 'A', 'pos': (0, 0), 'conj': False},
        {'node_id': 1, 'label': 'B', 'pos': (2, 0), 'conj': False},
        {'node_id': 2, 'label': 'C', 'pos': (3, 0), 'conj': False},
    ]
    edges = [{'from_node_id': 1, 'to_node_id': 2, 'is_self_loop': False,
              'f_p': 2.0, 'rate': 0.4, 'phase': 0.0}]
    assignments = {}
    for node, freq in zip(nodes, (5.0, 3.0, 6.0)):
        assignments[id(node)] = {'freq': freq, 'B_int': 0.0, 'B_ext': None}
    assignments[id(edges[0])] = {'f_p': 2.0, 'rate': 0.4, 'phase': 0.0}

    hubs = []
    if hub:
        hubs = [{'hub_id': 'P0', 'label': 'P0', 'monitored': True,
                 'attachments': [(0, 0.5), (1, 0.5)]}]

    extractor = autograph.GraphExtractor()
    extractor.extract_graph_data(
        nodes=nodes, edges=edges,
        scattering_assignments=assignments,
        frequency_settings={'start': -1.0, 'stop': 1.0, 'points': 3},
        root_node_id=0,
        hubs=hubs,
    )
    return extractor


def test_bridged_subgraph_keeps_pump_accumulation():
    extractor = bridged_extractor()
    assert extractor.graph_data['is_connected'] is True

    f = np.linspace(-1.0, 1.0, 3)
    gsm = autograph.GraphScatteringMatrix(extractor, f)
    basis = extractor.graph_data['basis_order']
    iA, iB, iC = basis.index(0), basis.index(1), basis.index(2)

    # A and B share the port's frame (offset 0); C accumulates the pump:
    # freqs (5, 3, 6) make B->C an upconversion, so C's drive is f + 2.
    # (Real parts carry the frames; A and B also carry the port's
    # (i/2) kappa^2 = 0.125j diagonal damping.)
    np.testing.assert_allclose(gsm.M[:, iA, iA], f - 5.0 + 0.125j)
    np.testing.assert_allclose(gsm.M[:, iB, iB], f - 3.0 + 0.125j)
    np.testing.assert_allclose(gsm.M[:, iC, iC], (f + 2.0) - 6.0)

    # ... and the shared-port cross-damping is present between A and B
    assert gsm.M[0, iA, iB] == pytest.approx(0.5j * 0.5 * 0.5)


def test_without_hub_subgraph_is_disconnected():
    """Control: no hub -> no link, the far subgraph stays unreached (its
    drive falls back to f_root) — the historical disconnected behavior."""
    extractor = bridged_extractor(hub=False)
    assert extractor.graph_data['is_connected'] is False


def test_links_never_reroute_pump_frames():
    """A hub across a pump-CONNECTED pair adds no link: the frame still
    comes from the pump edge, not the resistor."""
    nodes = [
        {'node_id': 0, 'label': 'A', 'pos': (0, 0), 'conj': False},
        {'node_id': 1, 'label': 'B', 'pos': (1, 0), 'conj': False},
    ]
    edges = [{'from_node_id': 0, 'to_node_id': 1, 'is_self_loop': False,
              'f_p': 2.0, 'rate': 0.4, 'phase': 0.0}]
    assignments = {}
    for node, freq in zip(nodes, (3.0, 5.0)):
        assignments[id(node)] = {'freq': freq, 'B_int': 0.0, 'B_ext': None}
    assignments[id(edges[0])] = {'f_p': 2.0, 'rate': 0.4, 'phase': 0.0}
    hubs = [{'hub_id': 'P0', 'label': 'P0', 'monitored': True,
             'attachments': [(0, 0.5), (1, 0.5)]}]

    extractor = autograph.GraphExtractor()
    extractor.extract_graph_data(
        nodes=nodes, edges=edges, scattering_assignments=assignments,
        frequency_settings={'start': -1.0, 'stop': 1.0, 'points': 3},
        root_node_id=0, hubs=hubs)

    assert extractor._hub_link_pairs == set()
    f = np.linspace(-1.0, 1.0, 3)
    gsm = autograph.GraphScatteringMatrix(extractor, f)
    basis = extractor.graph_data['basis_order']
    # B keeps its pump-derived frame f + 2 (upconversion 3 -> 5)
    np.testing.assert_allclose(gsm.M[:, basis.index(1), basis.index(1)].real,
                               f + 2.0 - 5.0)


def test_extract_from_pgraph_reads_v3_sections():
    """The programmatic route must not drop GUI-saved ports/lines."""
    pgraph = {
        'version': '3.0',
        'format': 'pgraph',
        'nodes': [
            {'node_id': 0, 'label': 'A', 'pos': [0, 0], 'conj': False,
             'freq': 5.0, 'B_int': 0.0, 'B_ext': None},
            {'node_id': 1, 'label': 'B', 'pos': [1, 0], 'conj': False,
             'freq': 6.0, 'B_int': 0.0, 'B_ext': None},
        ],
        'edges': [],
        'ports': [
            {'port_id': 0, 'label': 'P1', 'pos': [2, 0], 'monitored': True,
             'attachments': [
                 {'node_id': 0, 'rate': 0.2, 'sign': 1},
                 {'node_id': 1, 'rate': 0.2, 'sign': -1},
             ]},
        ],
        'line_resonators': [
            {'line_id': 0, 'label': 'TL1', 'pos': [0, -3], 'FSR': 1.5,
             'Ztx': 65.0, 'f_max': 6.0, 'port_end': 'xL', 'Z0_port': 50.0,
             'alpha_uniform': 0.0},
        ],
    }
    extractor = autograph.GraphExtractor()
    extractor.extract_from_pgraph(pgraph)
    gsm = autograph.GraphScatteringMatrix(extractor, np.linspace(-2, 2, 5))

    # 2 GUI nodes + (2N+1 = 9) comb modes; 2 ports (shared + line)
    assert gsm.num_modes == 2 + 9
    assert gsm.num_ports == 2
    assert gsm.port_labels == ['P1', 'TL1']
    kappa = gsm.K[[extractor.graph_data['basis_order'].index(0),
                   extractor.graph_data['basis_order'].index(1)], 0]
    np.testing.assert_allclose(kappa, [np.sqrt(0.2), -np.sqrt(0.2)])
