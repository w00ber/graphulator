"""A pump that only converts must not produce gain.

Whether an edge couples as a beam-splitter or as two-mode squeezing is set
by the two nodes' EFFECTIVE sectors, not by their `conj` flags: in a
+-omega comb the negative-frequency member is the counter-rotating part of
the same physical mode, so the sector is conj XOR (freq < 0).

Keying on the flag alone made every signal->twin edge a squeezing edge. A
line pumped at f_p = FSR -- which can only convert, since the smallest
f_n + f_m in the comb is 2*FSR > f_p -- then showed |S_ss|^2 = 10.3 with
|S_ss|^2 - |S_is|^2 = 1 to 1e-14: clean, self-consistent, physically
impossible amplification, manufactured by pairing the signal with a
NEGATIVE-frequency idler (f_s + f_i = f_p with f_i < 0 is really
f_s - |f_i| = f_p).
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")

from tests.test_gui_hubs import para                            # noqa: E402,F401

FA, FB, NPTS = 5.6, 6.4, 401


def _sweep(win, fa=FA, fb=FB, npts=NPTS, labels=('TL1', 'TL1*')):
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


def _conversion_scene(para, f_p=0.5, rate=0.022, n_ref=12):
    """The user's coax configuration: FSR = f_p, so only conversion exists."""
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = True
    win._apply_explicit_ports_mode()
    line = win.add_line_resonator(label='TL1', pos=(0.0, 0.0), FSR=0.5,
                                  Ztx=5.0, f_max=20.0, port_end='xL',
                                  Z0_port=50.0)
    win.set_line_pump(line, 'x0', f_p=f_p, rate=rate, n_ref=n_ref,
                      twin_pos=(0.0, -5.0))
    return win, line


def test_no_amplification_pair_exists_at_f_p_equal_fsr(para):
    """The premise: with f_p = FSR nothing in the comb can amplify."""
    from graphulator.para_features.explicit_ports import pump_partners
    win, line = _conversion_scene(para)
    res = win.line_resonator_for(line)
    assert 2 * res.mode_freq(1) > 0.5          # smallest f_n + f_m beats f_p
    fams = {p['family'] for p in pump_partners(res, 12, 0.5)}
    assert fams == {'up-conversion', 'down-conversion'}, fams


def test_conversion_only_pump_conserves_flux(para):
    """No gain, and the flux that leaves the signal arrives at the idler."""
    win, line = _conversion_scene(para)
    f, g, c = _sweep(win)
    assert g.max() <= 1.0 + 1e-3, g.max()
    assert c.max() > 0.1, "the pump should still convert"
    # beam-splitter: |S_ss|^2 + |S_is|^2 = 1 (residual is comb truncation)
    assert np.max(np.abs(g + c - 1.0)) < 5e-3, np.max(np.abs(g + c - 1.0))
    # and emphatically NOT the squeezing relation
    assert np.max(np.abs(g - c - 1.0)) > 0.1


def test_unpumped_line_is_exactly_lossless(para):
    """Control: the gain was entirely the pump block, not the line."""
    win, line = _conversion_scene(para, rate=0.0)
    f, g, c = _sweep(win)
    assert abs(g.max() - 1.0) < 1e-9 and c.max() < 1e-12


def test_a_real_amplification_pair_still_amplifies(para):
    """The fix must not disarm genuine gain: f_p = 2*f_n, both members at
    POSITIVE frequency, is two-mode squeezing and must stay so."""
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
    k = int(np.argmax(g))
    assert abs(g[k] - c[k] - 1.0) < 1e-6, (g[k], c[k])   # Manley-Rowe


def test_pump_normalization_still_matches_the_oracle(para):
    """The gate that pinned the amplifier against exact harmonic balance."""
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    import cmtline_core as core
    from graphulator.graphulator_para import _compute_sparams_job
    gp, win, config = para
    N, LJ, Cd, Z0, dK = 12, 1e4, 1e-8, 10.0, 1.0
    Cm, Km, Rm, P, fv = core.build_galvanic(N, LJ, Cd, ell=1.0, Ztx=1.0, v=1.0)
    ws = np.linspace(2.8 * np.pi, 3.2 * np.pi, 81)
    Sss_o, _ = core.hb_signal_idler(ws, 6 * np.pi, dK * LJ, Cm, Km, Rm, P, fv, Z0)
    G_o = np.abs(Sss_o) ** 2
    fs = ws / np.pi
    line = win.add_line_resonator(label='TL', pos=(0, 0), FSR=1.0, Ztx=1.0,
                                  f_max=N + 0.4, port_end='xL', Z0_port=Z0)
    g = dK / (4 * np.sqrt((3 * np.pi * 0.5) ** 2))
    win.set_line_pump(line, 'x0', f_p=6.0, rate=2 * g / np.pi, n_ref=3)
    comps = win._find_connected_components()
    res = _compute_sparams_job(
        win._build_sparams_job(comps[0], fs, fs[0], fs[-1], len(fs)))
    lab = [res['port_dict'][p]['label'] for p in res['port_ids']]
    G_g = np.abs(res['S'][:, lab.index('TL'), lab.index('TL')]) ** 2
    assert G_o.max() > 2.0
    assert np.max(np.abs(G_g - G_o)) / G_o.max() < 5e-3
