"""LineResonator plumbing vs the reference numerics (cmtline_core).

The macro's expansion must equal `comb_poles_K` output BITWISE under the
unit-mapping layer (rule: import and compare against the reference, never
re-derive silently), and the full autograph build of the expanded graph must
reproduce `s11_graph_matrix` at identical N.
"""

import numpy as np
import pytest

from graphulator import autograph
from tests import cmtline_core

FSR = 150.0     # linear-frequency units (think MHz)
ZTX = 65.0
Z0 = 50.0
Z0_NAT = Z0 / ZTX


def make_line(port_end, f_max=1200.0):
    return autograph.LineResonator(line_id='TL1', label='coax', FSR=FSR,
                                   Ztx=ZTX, f_max=f_max, port_end=port_end,
                                   Z0_port=Z0)


@pytest.mark.parametrize("port_end,signs", [('xL', True), ('x0', False)])
def test_expansion_arrays_equal_reference(port_end, signs):
    """expand_arrays() == comb_poles_K under the unit mapping, exactly."""
    line = make_line(port_end)
    freqs, kappas, gamma_phys, N = line.expand_arrays()
    assert N == int(np.ceil(line.f_max / FSR)) == 8

    poles_nat, kap_nat, gam_nat = cmtline_core.comb_poles_K(
        N, Z0_NAT, signs=signs)

    # bitwise equality (same mapping applied to the reference arrays)
    np.testing.assert_array_equal(
        freqs, autograph.line_natural_frequency_to_physical(poles_nat, FSR))
    np.testing.assert_array_equal(
        kappas, autograph.line_natural_coupling_to_physical(kap_nat, FSR))
    assert gamma_phys == autograph.line_natural_frequency_to_physical(
        gam_nat, FSR)

    # sign pattern: DC always +; 'xL' alternates, 'x0' all-plus
    ks = np.array([0] + [k for n in range(1, N + 1) for k in (n, -n)])
    expected_sign = (-1.0) ** np.abs(ks) if signs else np.ones_like(ks, float)
    np.testing.assert_array_equal(np.sign(kappas), expected_sign)


def test_expand_nodes_and_hub():
    """expand() node ids/freqs and the port hub attachment vector."""
    line = make_line('xL')
    nodes, hubs = line.expand()
    freqs, kappas, _, N = line.expand_arrays()

    assert len(nodes) == 2 * N + 1
    assert [n['node_id'] for n in nodes][:5] == \
        ['TL1:n0', 'TL1:n1', 'TL1:n-1', 'TL1:n2', 'TL1:n-2']
    assert all(n['conj'] is False for n in nodes)
    np.testing.assert_array_equal([n['freq'] for n in nodes], freqs)
    # freq_k is k*FSR through the (tested) unit mapping — ~1 ulp of k*FSR
    ks = np.array([0] + [k for n in range(1, N + 1) for k in (n, -n)])
    np.testing.assert_allclose([n['freq'] for n in nodes], ks * FSR,
                               rtol=1e-14, atol=1e-11)

    assert len(hubs) == 1
    hub = hubs[0]
    assert hub['monitored'] is True
    assert hub['label'] == 'coax'
    signed = [m if p == 0.0 else -m for _, m, p in hub['attachments']]
    np.testing.assert_array_equal(signed, kappas)


def test_no_port_end_no_hub():
    line = make_line(None)
    nodes, hubs = line.expand()
    assert hubs == []
    assert len(nodes) == 2 * line.N + 1


def test_invalid_port_end_rejected():
    with pytest.raises(ValueError, match="two-port"):
        make_line('both')


def test_autograph_s11_matches_reference_matrix():
    """Full autograph S11 of the expanded graph == s11_graph_matrix at the
    same N, over an in-band sweep avoiding w = 0."""
    line = make_line('xL')
    N = line.N

    w_nat = np.linspace(0.3 * np.pi, 6.7 * np.pi, 400)
    f_phys = autograph.line_natural_frequency_to_physical(w_nat, FSR)

    extractor = autograph.GraphExtractor()
    extractor.extract_graph_data(
        nodes=[], edges=[], scattering_assignments={},
        frequency_settings={'start': float(f_phys[0]),
                            'stop': float(f_phys[-1]),
                            'points': len(f_phys)},
        line_resonators=[line],
    )
    gsm = autograph.GraphScatteringMatrix(extractor, f_phys)
    assert gsm.num_ports == 1
    assert gsm.num_modes == 2 * N + 1
    # root defaults to the first attachment of the (only) port hub
    assert extractor.graph_data['root_node_id'] == 'TL1:n0'
    assert gsm._get_port_label(gsm.port_ids[0]) == 'coax'

    poles_nat, kap_nat, _ = cmtline_core.comb_poles_K(N, Z0_NAT, signs=True)
    s11_ref = cmtline_core.s11_graph_matrix(w_nat, poles_nat, kap_nat)
    assert np.max(np.abs(gsm.S[:, 0, 0] - s11_ref)) <= 1e-13


def test_expanded_nodes_addressable_by_pump_edges():
    """User pump edges may target expanded mode ids."""
    line = make_line('xL')
    device = {'node_id': 0, 'label': 'J', 'pos': (0.0, 0.0), 'conj': False}
    edge = {'from_node_id': 0, 'to_node_id': 'TL1:n1', 'is_self_loop': False,
            'f_p': 100.0, 'rate': 0.5, 'phase': 0.0}
    assignments = {
        id(device): {'freq': 50.0, 'B_int': 0.0, 'B_ext': None},
        id(edge): {'f_p': 100.0, 'rate': 0.5, 'phase': 0.0},
    }
    extractor = autograph.GraphExtractor()
    extractor.extract_graph_data(
        nodes=[device], edges=[edge], scattering_assignments=assignments,
        frequency_settings={'start': 0.0, 'stop': 300.0, 'points': 5},
        root_node_id=0,
        line_resonators=[line],
    )
    gsm = autograph.GraphScatteringMatrix(extractor, np.linspace(0, 300, 5))
    basis = extractor.graph_data['basis_order']
    j, k = basis.index(0), basis.index('TL1:n1')
    assert gsm.M[0, j, k] != 0.0  # the edge landed on the expanded mode
