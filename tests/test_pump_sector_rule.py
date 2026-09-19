"""OPEN BUG: a conversion-only pump produces gain.

Reported from a coax configuration (FSR = 0.5, f_p = 0.5 = FSR, n = 12).
That comb cannot amplify -- amplification needs f_n + f_m = f_p and the
smallest available sum is 2*FSR = 1.0 -- yet S comes back with
|S_ss|^2 ~ 10 and, cleanly, |S_ss|^2 - |S_is|^2 = 1 to 1e-14: the exact
Manley-Rowe signature of two-mode squeezing. Not noise; the model is
deliberately amplifying a process that cannot amplify.

MECHANISM. The twin channel is read at f_p - f_s = 0.5 - 6.0 = -5.5, and
the pair is taken as f_s + f_i = 6.0 + (-5.5) = 0.5 = f_p, which only
holds because the idler frequency is NEGATIVE. With f_i < 0 that identity
is really f_s - |f_i| = f_p: down-conversion, a beam-splitter.

WHY IT IS NOT A ONE-LINE FIX. `_gui_pump_edges` emits ONLY signal->twin
edges, and `_build_M_matrix` makes every such edge anti-Hermitian because
the two ends' `conj` flags differ. Conversion (a_n <-> a_m) lives in the
SAME sector, so representing it needs intra-comb edges, which the macro
never builds -- the conversion block is simply absent from the model.

Two repairs were tried and rejected, both recorded here so they are not
retried blind:

  1. Effective sector = conj XOR (freq < 0), applied to the edge branch.
     Rejected: an ordinary node below the drive frame has freq < 0 without
     being anyone's counter-rotating partner, so this flips Hermitian
     edges in plain graphs and destroys unitarity
     (tests/test_hub_identity.py, whose random Omega has negative diagonal
     entries, fails at 3.2).
  2. The same, restricted to comb members by an explicit
     `counter_rotating` flag. Unitarity is then fine, but reinterpreting a
     signal->twin edge as a beam-splitter IN PLACE breaks the
     para-Hermitian structure the Manley-Rowe identity rests on:
     test_pumped_line_amplifies_and_is_pseudo_unitary goes from 1e-15 to
     1.7e-3. A real conversion edge connects signal +n to signal +m, not
     signal +n to twin -m, so the edge cannot simply change character.

The fix is therefore structural: the pump must emit a SECOND block of
intra-comb (and intra-twin) beam-splitter edges for pairs with
|f_n - f_m| = f_p, alongside the existing cross-comb squeezing block --
and the squeezing block must be restricted to pairs whose partner
frequency is positive. That needs the derivation and an oracle gate, like
every other block in this model.

Until then these tests DOCUMENT the defect rather than assert correct
behaviour, so it stays executable and cannot be quietly forgotten.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")

from tests.test_gui_hubs import para                            # noqa: E402,F401


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
    """The premise, independent of the bug: with f_p = FSR nothing in the
    comb can amplify, and the partner enumeration says so correctly."""
    from graphulator.para_features.explicit_ports import pump_partners
    win, line = _conversion_scene(para)
    res = win.line_resonator_for(line)
    assert 2 * res.mode_freq(1) > 0.5          # smallest f_n + f_m beats f_p
    fams = {p['family'] for p in pump_partners(res, 12, 0.5)}
    assert fams == {'up-conversion', 'down-conversion'}, fams


def test_unpumped_line_is_exactly_lossless(para):
    """Control: the line, port and tail closure are NOT the problem."""
    win, line = _conversion_scene(para, rate=0.0)
    f, g, c = _sweep(win)
    assert abs(g.max() - 1.0) < 1e-9 and c.max() < 1e-12


def test_conversion_only_pump_currently_amplifies(para):
    """The defect, pinned. Delete this test when the structural fix lands;
    test_conversion_only_pump_should_conserve_flux below is its replacement."""
    win, line = _conversion_scene(para)
    f, g, c = _sweep(win)
    assert g.max() > 5.0, g.max()
    k = int(np.argmax(g))
    # and it is clean two-mode squeezing, not numerical debris
    assert abs(g[k] - c[k] - 1.0) < 1e-9, (g[k], c[k])


@pytest.mark.xfail(reason="conversion block absent from the pump macro; see "
                          "this module's docstring", strict=True)
def test_conversion_only_pump_should_conserve_flux(para):
    """What the model owes: no gain, and beam-splitter flux conservation."""
    win, line = _conversion_scene(para)
    f, g, c = _sweep(win)
    assert g.max() <= 1.0 + 1e-3, g.max()
    assert np.max(np.abs(g + c - 1.0)) < 5e-3


def test_a_real_amplification_pair_still_amplifies(para):
    """Unaffected by the defect: f_p = 2*f_n with both members at POSITIVE
    frequency is genuine two-mode squeezing and is pinned against the
    oracle elsewhere (tests/test_pumped_line.py)."""
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
    assert abs(g[k] - c[k] - 1.0) < 1e-6, (g[k], c[k])
