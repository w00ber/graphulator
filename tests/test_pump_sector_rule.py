"""The sigma_z sector rule for pump couplings on a +-n comb.

A comb macro puts each physical mode in the basis TWICE -- at +f_n and at
-f_n -- because those are the two partial fractions of the mode's exact
second-order response. The two halves are the co- and counter-rotating
parts of the SAME mode, so they sit in opposite sigma_z sectors inside one
cluster:

    s = (-1)^[conj XOR counter_rotating]

A real quadratic modulation of Phi = sum_n u_n (a_n + a_n^dagger) gives a
dynamical matrix sigma_z H with H Hermitian, so a coupling obeys

    M[k, j] = (s_j s_k) conj(M[j, k])

-- Hermitian within a sector (beam-splitter, conversion), anti-Hermitian
across it (two-mode squeezing, gain).

Reading the sector off the raw CLUSTER flag instead made every signal->twin
edge anti-Hermitian, which turned a conversion-only pump into an amplifier.
The configuration that surfaced it: FSR = 0.5, f_p = 0.5 = FSR, n_ref = 12.
That comb holds no amplification pair at all (the smallest f_n + f_m is
2*FSR = 1.0 > f_p), yet |S_ss|^2 reached ~10.

Full derivation, matrices and oracle numbers: docs/pump_sector_rule.md.
The oracle gate for the same physics is
tests/test_pumped_line.py::test_conversion_band_matches_oracle.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")

from tests.test_gui_hubs import para  # noqa: E402,F401


def _sweep(win, fa=5.6, fb=6.4, npts=401, labels=('TL1', 'TL1*')):
    from graphulator.graphulator_para import _compute_sparams_job
    if not win.scattering_mode:
        win._enter_scattering_mode()
    f = np.linspace(fa, fb, npts)
    res = _compute_sparams_job(win._build_sparams_job(None, f, fa, fb, npts))
    assert res is not None
    lab = [res['port_dict'][p]['label'] for p in res['port_ids']]
    S = res['S']
    s, i = lab.index(labels[0]), lab.index(labels[1])
    return f, np.abs(S[:, s, s]) ** 2, np.abs(S[:, i, s]) ** 2


def _conversion_scene(para, rate=0.022):
    """The reported coax configuration: f_p = FSR, so only conversion exists."""
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = True
    win._apply_explicit_ports_mode()
    line = win.add_line_resonator(label='TL1', pos=(0.0, 0.0), FSR=0.5,
                                  Ztx=5.0, f_max=20.0, port_end='xL',
                                  Z0_port=50.0)
    win.set_line_pump(line, 'x0', f_p=0.5, rate=rate, n_ref=12,
                      twin_pos=(0.0, -5.0))
    return win, line


def test_no_amplification_pair_exists_at_f_p_equal_fsr(para):
    """The premise: with f_p = FSR nothing in the comb can amplify, and the
    partner enumeration says so."""
    from graphulator.para_features.explicit_ports import pump_partners
    win, line = _conversion_scene(para)
    res = win.line_resonator_for(line)
    assert 2 * res.mode_freq(1) > 0.5          # smallest f_n + f_m beats f_p
    fams = {p['family'] for p in pump_partners(res, 12, 0.5)}
    assert fams == {'up-conversion', 'down-conversion'}, fams


def test_unpumped_line_is_exactly_lossless(para):
    """Control: the line, port and tail closure are not in question here."""
    win, line = _conversion_scene(para, rate=0.0)
    f, g, c = _sweep(win)
    assert abs(g.max() - 1.0) < 1e-9 and c.max() < 1e-12


def test_conversion_only_pump_conserves_flux(para):
    """The fix, at the port: no gain, and beam-splitter flux conservation.

    The resonant partner of the signal at f_12 = 6.0 is the twin's -11
    member, at f_p + f_11 = 0.5 + 5.5 = 6.0, i.e. f_s - f_11 = f_p. Same
    sigma_z sector as the signal, so the coupling is Hermitian and the two
    ports exchange flux instead of creating it.
    """
    win, line = _conversion_scene(para)
    f, g, c = _sweep(win)
    assert g.max() <= 1.0 + 1e-3, g.max()
    assert c.max() > 0.5, c.max()              # conversion really happens
    assert np.max(np.abs(g + c - 1.0)) < 5e-3


def test_resonant_partner_is_the_counter_rotating_twin_member(para):
    """Where the sector rule bites, read off the assembled matrix: the twin
    node that goes resonant carries counter_rotating, so its coupling to the
    signal is Hermitian while its +m sibling's stays anti-Hermitian."""
    from graphulator.autograph import GraphExtractor, GraphScatteringMatrix
    win, line = _conversion_scene(para)
    if not win.scattering_mode:
        win._enter_scattering_mode()
    job = win._build_sparams_job(None, np.array([6.0]), 5.9, 6.1, 1)
    ex = GraphExtractor()
    ex.extract_graph_data(
        nodes=job['nodes'], edges=job['edges'],
        scattering_assignments=job['scattering_assignments'],
        frequency_settings={'start': 5.9, 'stop': 6.1, 'points': 1},
        root_node_id=None, precomputed_tree_edges=None,
        precomputed_chord_edges=None, hubs=job.get('hubs') or [],
        line_resonators=job.get('line_resonators') or [])
    gsm = GraphScatteringMatrix(ex, np.array([6.0]),
                                tail_closure=job.get('tail_closure', True))
    basis = ex.graph_data['basis_order']
    by_id = {n['node_id']: n for n in ex.graph_data['nodes']}

    sig = next(i for i in basis if i.endswith(':n12') and ':0:' in i)
    conv = next(i for i in basis if i.endswith(':n-11') and ':1:' in i)
    amp = next(i for i in basis if i.endswith(':n11') and ':1:' in i)

    # the twin's -11 member is the one on resonance at f = 6.0
    assert abs(gsm.M[0, basis.index(conv), basis.index(conv)].real) < 1e-3
    assert abs(gsm.M[0, basis.index(amp), basis.index(amp)].real) > 1.0
    assert by_id[conv]['counter_rotating'] and not by_id[amp]['counter_rotating']
    assert not by_id[sig]['counter_rotating']

    def block(a, b):
        j, k = basis.index(a), basis.index(b)
        return gsm.M[0, j, k], gsm.M[0, k, j]

    fwd, rev = block(sig, conv)
    assert abs(fwd) > 1e-6 and abs(rev - np.conj(fwd)) < 1e-12 * abs(fwd) + 1e-15
    fwd, rev = block(sig, amp)
    assert abs(fwd) > 1e-6 and abs(rev + np.conj(fwd)) < 1e-12 * abs(fwd) + 1e-15


def test_a_real_amplification_pair_still_amplifies(para):
    """The other sector is untouched: f_p = 2*f_n with both members at
    POSITIVE frequency is genuine two-mode squeezing, and it still gains."""
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = True
    win._apply_explicit_ports_mode()
    line = win.add_line_resonator(label='TL1', pos=(0.0, 0.0), FSR=0.5,
                                  Ztx=5.0, f_max=20.0, port_end='xL',
                                  Z0_port=50.0)
    win.set_line_pump(line, 'x0', f_p=12.0, rate=0.02, n_ref=12,
                      twin_pos=(0.0, -5.0))
    f, g, c = _sweep(win)
    assert g.max() > 1.0, g.max()
    assert abs(g[int(np.argmax(g))] - c[int(np.argmax(g))] - 1.0) < 5e-3
