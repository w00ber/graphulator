"""The SQUID-terminated lambda/4 resonator of Lee, Spietz & Aumentado (2013)
as three bundled test scenes (File -> Test, INTERMODE_LEE2013_*).

One circuit, the paper's three pump frequencies. These load the SHIPPED
files -- the same bytes the menu loads -- and check the physics each scene
is there to show, so the scenes cannot drift from what their notes claim:

    CONVERSION        f_p = f_B - f_A   the Fig. 4 "hole": A -> B up-
                                        conversion, a beam-splitter, no gain
    DEGENERATE_AMP    f_p = 2 f_A       Fig. 2: gain in the fundamental
    NONDEGENERATE_AMP f_p = f_A + f_B   Fig. 3: A/B two-mode squeezing

The conversion scene is also the worked case for the twin's frame: the
up-conversion rung lives at omega + f_p ('sector+'), which the historical
omega - f_p frame reaches only at -omega.
"""

import json
import os
import sys

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")

from tests.test_gui_hubs import para                            # noqa: E402,F401

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCENES = os.path.join(ROOT, 'examples', 'test_scenes')
F_A, F_B = 1.840, 5.661                     # GHz, the paper's measured modes


def _load(win, which):
    path = os.path.join(SCENES, f"INTERMODE_LEE2013_{which}.pgraph")
    data = json.load(open(path))
    win._deserialize_graph(data)
    if not win.scattering_mode:
        win._enter_scattering_mode()
    return data


def _S(win, f):
    from graphulator.graphulator_para import _compute_sparams_job
    res = _compute_sparams_job(win._build_sparams_job(None, f, f[0], f[-1],
                                                      len(f)))
    lab = [res['port_dict'][p]['label'] for p in res['port_ids']]
    s, i = lab.index('TL'), lab.index('TL*')
    return res['S'][:, s, s], res['S'][:, i, s]


def _window():
    return np.linspace(F_A - 0.015, F_A + 0.015, 601)   # Fig. 4's f_VNA axis


def test_scenes_are_shipped_with_notes():
    for which in ('CONVERSION', 'DEGENERATE_AMP', 'NONDEGENERATE_AMP'):
        data = json.load(open(os.path.join(
            SCENES, f"INTERMODE_LEE2013_{which}.pgraph")))
        notes = data.get('notes', '')
        assert notes.startswith('# Intermode coupling'), which
        for must in ('How the circuit became this graph', 'loaded basis',
                     'stepped', 'f_Z', 'Z_0', 'delta L', 'Which rung'):
            assert must in notes, (which, must)
        assert data['scattering']['frequency']['center'] == pytest.approx(F_A)


def test_modes_land_on_the_measured_frequencies(para):
    """The effective load reproduces BOTH measured modes: bisection on f_Z
    with the closed-form FSR inversion, no fitting by hand."""
    gp, win, config = para
    _load(win, 'CONVERSION')
    line = next(l for l in win.line_resonators if l.get('pump'))
    res = win.line_resonator_for(line)
    assert res.mode_freq(1) == pytest.approx(F_A, abs=1e-6)
    assert res.mode_freq(2) == pytest.approx(F_B, abs=1e-6)
    # and the port rate at mode 1 is the paper's 2.9 MHz bandwidth
    g1 = res.mode_gamma(1) * res.mode_profile(1, 'xL') ** 2
    assert g1 == pytest.approx(0.0029, rel=1e-6)


def test_conversion_scene_is_the_fig4_hole(para):
    gp, win, config = para
    _load(win, 'CONVERSION')
    line = next(l for l in win.line_resonators if l.get('pump'))
    assert win._pump_anchor(line) == (1, 2, 'up-conversion')
    assert 'twin frame f + f_p' in win.pump_pair_description(line)
    S, C = _S(win, _window())
    G, X = np.abs(S) ** 2, np.abs(C) ** 2
    assert G.max() <= 1.0 + 1e-3                       # no gain anywhere
    assert 10 * np.log10(G.min()) < -25.0              # a deep hole ...
    k = int(np.argmin(G))
    assert abs(_window()[k] - F_A) < 0.005             # ... at the A mode
    assert X[k] > 0.99                                 # it all went to B
    assert np.max(np.abs(G + X - 1.0)) < 5e-3          # beam-splitter


def test_up_conversion_frame_is_the_mirror_of_the_other(para):
    """'sector+' on the sweep equals 'sector' at -omega: S(f) = conj S(-f)."""
    gp, win, config = para
    _load(win, 'CONVERSION')
    f = _window()
    S_plus, _ = _S(win, f)
    win.pump_frame_rule = staticmethod(lambda family: 'sector')
    win._invalidate_scattering_data()
    S_minus, _ = _S(win, -f[::-1])
    assert np.max(np.abs(S_plus - np.conj(S_minus[::-1]))) < 1e-12
    # and in the historical frame the hole is NOT on the positive sweep
    S_hist, _ = _S(win, f)
    assert np.abs(S_hist).min() ** 2 > 0.99


def test_degenerate_scene_amplifies_in_the_fundamental(para):
    gp, win, config = para
    _load(win, 'DEGENERATE_AMP')
    line = next(l for l in win.line_resonators if l.get('pump'))
    assert win._pump_anchor(line)[:2] == (1, 1)
    S, C = _S(win, _window())
    G, X = np.abs(S) ** 2, np.abs(C) ** 2
    k = int(np.argmax(G))
    assert G[k] > 2.0 and abs(_window()[k] - F_A) < 0.002
    # Manley-Rowe for squeezing: exact at the peak, O(rate^2) over the
    # window (the two-rung truncation, tests/test_pumped_line.py)
    assert abs(G[k] - X[k] - 1.0) < 1e-9
    assert np.max(np.abs(G - X - 1.0)) < 1e-4


def test_nondegenerate_scene_squeezes_A_with_B(para):
    gp, win, config = para
    _load(win, 'NONDEGENERATE_AMP')
    line = next(l for l in win.line_resonators if l.get('pump'))
    assert win._pump_anchor(line) == (1, 2, 'amplification')
    S, C = _S(win, _window())
    G, X = np.abs(S) ** 2, np.abs(C) ** 2
    k = int(np.argmax(G))
    assert G[k] > 10.0 and abs(_window()[k] - F_A) < 0.002
    assert abs(G[k] - X[k] - 1.0) < 1e-9                # exact at the peak
    assert np.max(np.abs(G - X - 1.0)) < 5e-3           # O(rate^2) elsewhere


def test_generated_code_carries_the_frame(para):
    """Export to .py reproduces the conversion scene, frame rule included."""
    gp, win, config = para
    _load(win, 'CONVERSION')
    panel = win.properties_panel
    panel.freq_center_spin.setValue(F_A)
    panel.freq_span_spin.setValue(0.03)
    panel.freq_points_spin.setValue(61)
    code = panel._generate_scattering_calculation_code()
    assert code is not None and "'frame_rule': 'sector+'" in code
    head = code.split("# Plot S-parameters")[0].rsplit("# ====", 1)[0]
    ns = {}
    exec(compile(head, '<generated>', 'exec'), ns)
    gsm = ns['scattering_matrix']
    S, _ = _S(win, np.linspace(F_A - 0.015, F_A + 0.015, 61))
    got = np.abs(gsm.S[:, 0, 0]) ** 2 if gsm.S.shape[1] else None
    assert got is not None
    assert np.max(np.abs(np.sort(got) - np.sort(np.abs(S) ** 2))) < 1e-9
