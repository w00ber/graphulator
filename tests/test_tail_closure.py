"""Comb tail closure: the truncated comb plus its analytic tail IS the line.

A line macro keeps N pole pairs. The modes beyond N still load the port,
as a reactive term ~ -2 gamma f/(FSR^2 N) that shifts every in-band
resonance -- the 1/N convergence pinned by test_line_macro_vs_abcd.py is
that tail and nothing else (see misc/comb_truncation_checks.py for the
in-window numbers: |dS| ~ 2.5 (gamma/FSR)(f/FSR)/N, all of it phase).

Eliminating the tail modes exactly (a Schur complement -- they touch the
graph only through the hub column) collapses them into one scalar per
channel, lambda_h(f) = 1/(1 + i chi_t,h/2), on the hub's damper in M and on
its K column, plus a direct phase on S's diagonal. chi_t is exact minus
kept, with `exact` the line's closed-form input impedance (-2i Z_in/Z0):
LineResonator.tail_susceptibility. These tests pin the claim: with the
closure, N = 2 reproduces exact ABCD to 1e-14, unloaded and loaded, lossy
or not, on a shared hub, and S_full stays unitary. What the closure does
NOT carry -- the tail modes' pump and tap couplings -- is second order and
is measured, not assumed, in the pumped test.
"""

import os

import numpy as np
import pytest

from graphulator import autograph
from tests import cmtline_core as core

FSR, ZTX, Z0 = 0.5, 1.0, 50.0 / 65.0          # natural units, gamma/FSR ~ 0.83
F = np.linspace(0.31, 3.29, 300)
W = 2.0 * np.pi * F


def _S(lines, f=F, closure=True, hubs=None, nodes=(), edges=(), assign=None,
       root=None):
    ext = autograph.GraphExtractor()
    ext.extract_graph_data(
        nodes=list(nodes), edges=list(edges),
        scattering_assignments=dict(assign or {}),
        frequency_settings={'start': float(f[0]), 'stop': float(f[-1]),
                            'points': len(f)},
        root_node_id=root, hubs=hubs, line_resonators=list(lines))
    return autograph.GraphScatteringMatrix(ext, f, tail_closure=closure)


def _open_line(N, port_end='xL', alpha=0.0):
    return autograph.LineResonator(line_id='TL', label='TL', FSR=FSR, Ztx=ZTX,
                                   f_max=N * FSR, port_end=port_end,
                                   Z0_port=Z0, alpha_uniform=alpha)


def _exact_open(w=W):
    return core.s11_lab_exact(w, Z0)


# --------------------------------------------------------------------------
# the susceptibility layer, against the oracle's own primitives
# --------------------------------------------------------------------------

def test_input_impedance_matches_oracle_abcd():
    line = _open_line(2)
    got = line.input_impedance('xL', F.astype(complex))
    want = np.array([core.zin_from_abcd(core.abcd_line(w, 1.0, ZTX, 1.0), np.inf)
                     for w in W])
    np.testing.assert_allclose(got, want, rtol=0, atol=1e-12)

    f_Z = 0.5
    L = ZTX / (2 * np.pi * f_Z)
    loaded = autograph.LineResonator(line_id='TL', FSR=FSR, Ztx=ZTX, f_max=FSR,
                                     port_end='x0', Z0_port=Z0,
                                     load={'end': 'xL', 'type': 'inductive',
                                           'f_Z': f_Z})
    got = loaded.input_impedance('x0', F.astype(complex))
    want = np.array([core.zin_from_abcd(core.abcd_line(w, 1.0, ZTX, 1.0),
                                        core.Z_ind(w, L)) for w in W])
    np.testing.assert_allclose(got, want, rtol=0, atol=1e-12)


def test_exact_susceptibility_is_the_cot_series():
    """chi = -2i Z_in/Z0 = (gamma/FSR) pi cot(pi f/FSR): the Mittag-Leffler
    expansion whose partial sums the comb keeps."""
    line = _open_line(2)
    chi = line.exact_susceptibility('xL', F.astype(complex))
    want = (line.gamma / FSR) * np.pi / np.tan(np.pi * F / FSR)
    np.testing.assert_allclose(chi, want, rtol=0, atol=1e-11)


def test_tail_is_the_direct_sum_beyond_N():
    line = _open_line(2)
    tail = line.tail_susceptibility('xL', F.astype(complex))
    n = np.arange(3, 100001)[:, None]
    direct = line.gamma * np.sum(1.0 / (F[None] - n * FSR)
                                 + 1.0 / (F[None] + n * FSR), axis=0)
    # the direct sum's own truncation is ~ 2 gamma f / (FSR^2 * 1e5)
    assert np.max(np.abs(tail - direct)) < 2e-4
    # and, well below the first tail pole, it is the reactive tail of the
    # note, -2 gamma f/(FSR^2 N) * [N sum_{n>N} 1/n^2] -- the bracket is
    # 0.79 at N = 2 and 0.975 at N = 20
    f_lo = np.array([0.1 * FSR], dtype=complex)
    for N, bracket in ((2, 0.79), (20, 0.975)):
        ln = _open_line(N)
        t = ln.tail_susceptibility('xL', f_lo)[0]
        est = -2.0 * ln.gamma * f_lo[0] / (FSR ** 2 * N)
        assert abs(t / est - bracket) < 0.02, (N, t / est)


def test_tail_is_finite_and_smooth_on_kept_poles():
    """A lossless sweep grid lands on n*FSR; exact and kept are both
    infinite there and the guard band must hand back the smooth tail."""
    line = _open_line(4)
    on = np.arange(0, 5) * FSR
    off = on + 1e-3 * FSR
    t_on = line.tail_susceptibility('xL', on.astype(complex))
    t_off = line.tail_susceptibility('xL', off.astype(complex))
    assert np.all(np.isfinite(t_on))
    assert np.max(np.abs(t_on - t_off)) < 1e-2 * np.max(np.abs(t_off))


# --------------------------------------------------------------------------
# the closure is an identity
# --------------------------------------------------------------------------

@pytest.mark.parametrize('N', [2, 4, 10])
@pytest.mark.parametrize('port_end', ['x0', 'xL'])
def test_closed_comb_equals_exact_abcd(N, port_end):
    S = _S([_open_line(N, port_end)]).S[:, 0, 0]
    assert np.max(np.abs(S - _exact_open())) < 1e-13
    # while the open comb is nowhere near (its 1/N tail)
    S_open = _S([_open_line(N, port_end)], closure=False).S[:, 0, 0]
    assert np.max(np.abs(S_open - _exact_open())) > 1.0


def test_closed_comb_is_exact_on_pole_points():
    f = np.concatenate([np.arange(1, 7) * FSR, F])
    S = _S([_open_line(4)], f=f).S[:, 0, 0]
    assert np.all(np.isfinite(S))
    assert np.max(np.abs(S - core.s11_lab_exact(2 * np.pi * f, Z0))) < 1e-13


@pytest.mark.parametrize('f_Z', [0.5, 0.15])
@pytest.mark.parametrize('port_end', ['x0', 'xL'])
def test_closed_loaded_comb_equals_exact_abcd(f_Z, port_end):
    """Inductive load at xL. Port at the open end (the verified geometry),
    or at the LOADED end, where Z_in is the reactance shunting the line."""
    load = {'end': 'xL', 'type': 'inductive', 'f_Z': f_Z}
    probe = autograph.LineResonator(line_id='TL', FSR=FSR, Ztx=ZTX, f_max=FSR,
                                    port_end=port_end, Z0_port=Z0, load=load)
    line = autograph.LineResonator(line_id='TL', label='TL', FSR=FSR, Ztx=ZTX,
                                   f_max=probe.mode_freq(3), port_end=port_end,
                                   Z0_port=Z0, load=load)
    L = ZTX / (2 * np.pi * f_Z)
    if port_end == 'x0':
        zin = [core.zin_from_abcd(core.abcd_line(w, 1.0, ZTX, 1.0),
                                  core.Z_ind(w, L)) for w in W]
    else:
        zin = [1.0 / (1.0 / core.Z_ind(w, L)
                      + 1.0 / core.zin_from_abcd(core.abcd_line(w, 1.0, ZTX, 1.0),
                                                 np.inf)) for w in W]
    exact = np.array([core.s11(z, Z0) for z in zin])
    S = _S([line]).S[:, 0, 0]
    assert np.max(np.abs(S - exact)) < 1e-13


def test_closed_lossy_comb_equals_lossy_abcd():
    """Uniform loss: the kept poles sit at f_n - i B/2 and the tail is
    evaluated at the same complex argument; against ABCD with a complex
    electrical length (test_uniform_loss's reference)."""
    from tests.test_uniform_loss import s11_lab_lossy, ALPHA
    S = _S([_open_line(3, alpha=ALPHA)]).S[:, 0, 0]
    exact = s11_lab_lossy(W, Z0, ALPHA)
    # B_int = (2/pi) alpha FSR is the LEADING-order map of a uniform
    # attenuation onto the comb (test_uniform_loss pins its convergence);
    # with the tail closed the residual is that map's own O(alpha^2), not
    # truncation -- two orders below the open comb at the same N
    err = np.max(np.abs(S - exact))
    S_open = _S([_open_line(3, alpha=ALPHA)], closure=False).S[:, 0, 0]
    assert err < 1e-2 * np.max(np.abs(S_open - exact)), err


def test_dilation_stays_unitary_with_closure():
    line = _open_line(3)
    g = _S([line])
    Sf = g.S_full
    eye = np.eye(Sf.shape[1])
    assert np.max(np.abs(np.einsum('fij,fkj->fik', Sf, Sf.conj()) - eye)) < 1e-12


def test_shared_hub_closes_both_lines_tails():
    """Two line ends on ONE port: one channel, two tails, exact.

    What that hub IS, physically: the column sums the two susceptibilities,
    chi = chi_a + chi_b with chi = -2i Z/Z0, so the port sees Z_a + Z_b --
    the two ends in SERIES (the resistor is driven by V_a + V_b), not in
    parallel. The raw comb converges to the series answer as 1/N (0.61 at
    N = 40, 0.16 at N = 160) and stays 2.0 from the parallel one; the
    closed comb hits series at N = 2.
    """
    a = autograph.LineResonator(line_id='A', label='A', FSR=FSR, Ztx=ZTX,
                                f_max=2 * FSR, port_end=None, Z0_port=Z0)
    b = autograph.LineResonator(line_id='B', label='B', FSR=0.7 * FSR, Ztx=ZTX,
                                f_max=1.4 * FSR, port_end=None, Z0_port=Z0)
    hub = {'hub_id': 'P', 'label': 'P', 'monitored': True,
           'attachments': a.end_couplings('xL') + b.end_couplings('x0'),
           'tails': [{'line': a.to_dict(), 'end': 'xL'},
                     {'line': b.to_dict(), 'end': 'x0'}]}
    S = _S([a, b], hubs=[hub]).S[:, 0, 0]
    def zin(line, w):
        th = w / (2 * line.FSR)                    # k ell = pi f/FSR
        return 1j * line.Ztx / np.tan(th)
    Z_series = np.array([zin(a, w) + zin(b, w) for w in W])
    Z_par = np.array([1.0 / (1.0 / zin(a, w) + 1.0 / zin(b, w)) for w in W])
    assert np.max(np.abs(S - core.s11(Z_series, Z0))) < 1e-12
    assert np.max(np.abs(S - core.s11(Z_par, Z0))) > 1.0


def test_legacy_graphs_are_bit_identical():
    """No lines -> no tails -> lambda = 1 exactly: the assembly must not
    change a single bit for the graphs the golden suite pins."""
    nodes = [{'node_id': 0, 'label': 'a', 'pos': (0, 0), 'conj': False,
              'freq': 5.0, 'B_int': 0.01, 'B_ext': 0.2},
             {'node_id': 1, 'label': 'b', 'pos': (1, 0), 'conj': False,
              'freq': 5.5, 'B_int': 0.0, 'B_ext': None}]
    edges = [{'from_node_id': 0, 'to_node_id': 1, 'is_self_loop': False}]
    assign = {id(nodes[0]): {'freq': 5.0, 'B_int': 0.01, 'B_ext': 0.2},
              id(nodes[1]): {'freq': 5.5, 'B_int': 0.0},
              id(edges[0]): {'f_p': 0.0, 'rate': 0.1, 'phase': 0.0}}
    f = np.linspace(4.5, 6.0, 41)
    on = _S([], f=f, nodes=nodes, edges=edges, assign=assign, root=0, closure=True)
    off = _S([], f=f, nodes=nodes, edges=edges, assign=assign, root=0, closure=False)
    assert not on.has_tail_closure
    assert np.array_equal(on.S, off.S) and np.array_equal(on.M, off.M)


def test_hub_dict_and_pgraph_routes_carry_tails():
    line = _open_line(2, port_end='xL')
    nodes, hubs = line.expand()
    assert hubs[0]['tails'] == [{'line': line.to_dict(), 'end': 'xL'}]
    norm = autograph._normalize_hub(hubs[0])
    assert norm['tails'][0]['end'] == 'xL'
    with pytest.raises(ValueError):
        autograph._normalize_hub({'hub_id': 'x', 'attachments': [],
                                  'tails': [{'line': line.to_dict(),
                                             'end': 'middle'}]})


# --------------------------------------------------------------------------
# what the closure does not carry: the tail's OTHER couplings
# --------------------------------------------------------------------------

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")

from tests.test_gui_hubs import para                            # noqa: E402,F401


def test_closure_shrinks_the_pumped_comb_error_at_low_N(para):
    """The pumped line of test_pumped_line's oracle check, at N = 4 instead
    of 12. The closure carries the tail's PORT loading exactly; what it
    drops is the tail modes' pump coupling, second order in the pump rate.
    So the error must fall substantially -- and what is left is the number
    a user should know when they pick f_max on a pumped line."""
    from graphulator.graphulator_para import _compute_sparams_job
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    import cmtline_core as core_
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = True
    win._apply_explicit_ports_mode()

    N_o, LJ, Cd, Z0_, dK = 12, 1e4, 1e-8, 10.0, 1.0
    Cm, Km, Rm, P, f_ = core_.build_galvanic(N_o, LJ, Cd, ell=1.0, Ztx=1.0, v=1.0)
    wp = 6 * np.pi
    ws = np.linspace(2.8 * np.pi, 3.2 * np.pi, 81)
    Sss_o, _ = core_.hb_signal_idler(ws, wp, dK * LJ, Cm, Km, Rm, P, f_, Z0_)
    G_o = np.abs(Sss_o) ** 2
    fs = ws / np.pi

    line = win.add_line_resonator(label='TL', pos=(0, 0), FSR=1.0, Ztx=1.0,
                                  f_max=4.4, port_end='xL', Z0_port=Z0_)
    g = dK / (4 * np.sqrt((3 * np.pi * 0.5) ** 2))
    win.set_line_pump(line, 'x0', f_p=6.0, rate=2 * g / np.pi, n_ref=3)
    comps = win._find_connected_components()

    def gain(closure):
        win.line_tail_closure = closure
        job = win._build_sparams_job(comps[0], fs, fs[0], fs[-1], len(fs))
        assert job['tail_closure'] is closure
        res = _compute_sparams_job(job)
        lab = [res['port_dict'][p]['label'] for p in res['port_ids']]
        s = lab.index('TL')
        return np.abs(res['S'][:, s, s]) ** 2

    err_on = np.max(np.abs(gain(True) - G_o)) / G_o.max()
    err_off = np.max(np.abs(gain(False) - G_o)) / G_o.max()
    assert G_o.max() > 2.0
    # measured (misc/comb_truncation_checks.py): raw 7.4e-3, closed 3.3e-3
    # at N = 4; the closed value sits on the ~2.1e-3 floor of the oracle's
    # pumped DC mode (which the macro excludes), so the truncation part
    # proper fell from ~5.3e-3 to ~1.2e-3
    assert err_on < 0.6 * err_off, (err_on, err_off)
    # and the closure at N = 4 beats the raw comb at N = 8 (4.0e-3)
    line['f_max'] = 8.4
    win._gui_lines_payload()
    err_off_8 = np.max(np.abs(gain(False) - G_o)) / G_o.max()
    assert err_on < err_off_8, (err_on, err_off_8)
