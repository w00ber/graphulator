"""Phase-1 guard rail: a hub spanning both conj sectors must be rejected.

The conjugation placement for hub attachments on conj-sector nodes is exactly
the deferred M_pumped two-sector derivation; until that lands, mixed-sector
hubs raise a ValueError that names it.
"""

import numpy as np
import pytest

from graphulator import autograph


def two_sector_extractor(hubs=None):
    nodes = [
        {'node_id': 0, 'label': 'a', 'pos': (0.0, 0.0), 'conj': False},
        {'node_id': 1, 'label': 'b*', 'pos': (1.0, 0.0), 'conj': True},
    ]
    edges = [{'from_node_id': 0, 'to_node_id': 1, 'is_self_loop': False,
              'f_p': 10.0, 'rate': 0.2, 'phase': 0.0}]
    assignments = {}
    for node, freq in zip(nodes, (4.0, 6.0)):
        assignments[id(node)] = {'freq': freq, 'B_int': 0.0, 'B_ext': None}
    assignments[id(edges[0])] = {'f_p': 10.0, 'rate': 0.2, 'phase': 0.0}

    extractor = autograph.GraphExtractor()
    extractor.extract_graph_data(
        nodes=nodes, edges=edges,
        scattering_assignments=assignments,
        frequency_settings={'start': -1.0, 'stop': 1.0, 'points': 3},
        root_node_id=0,
        hubs=hubs,
    )
    return extractor


MIXED_HUB = {'hub_id': 'P0', 'label': 'P0', 'monitored': True,
             'attachments': [(0, 0.5), (1, 0.5)]}


def test_assign_hub_rejects_mixed_sector():
    extractor = two_sector_extractor()
    with pytest.raises(ValueError, match="M_pumped"):
        extractor.assign_hub('P0', attachments=[(0, 0.5), (1, 0.5)])


def test_extract_rejects_mixed_sector():
    with pytest.raises(ValueError, match="M_pumped"):
        two_sector_extractor(hubs=[MIXED_HUB])


def test_build_rejects_mixed_sector_after_edit():
    """Editing a stored hub into a mixed-sector state is caught at build."""
    extractor = two_sector_extractor(
        hubs=[{'hub_id': 'P0', 'label': 'P0', 'monitored': True,
               'attachments': [(0, 0.5)]}])
    # simulate a stale/hand-edited graph_data entry
    extractor.graph_data['hubs'][0]['attachments'].append((1, 0.5, 0.0))
    with pytest.raises(ValueError, match="M_pumped"):
        autograph.GraphScatteringMatrix(extractor, np.array([0.0]))


def test_phase_other_than_0_or_180_rejected():
    """Companion Phase-1 gate: complex weights await the same derivation."""
    extractor = two_sector_extractor()
    with pytest.raises(ValueError, match="M_pumped"):
        extractor.assign_hub('P0', attachments=[(0, 0.5, 90.0)])


def test_single_sector_conj_hub_accepted():
    """All-conj hubs are fine — the restriction is on MIXING sectors."""
    extractor = two_sector_extractor()
    extractor.assign_hub('P0', attachments=[(1, 0.5)])
    gsm = autograph.GraphScatteringMatrix(extractor, np.array([0.0]))
    assert gsm.num_ports == 1
