"""Reactively loaded lines: the dispersed basis of docs/pumped_line_termination.md §7.

An open-open comb is the f_Z -> 0 inductive limit, not the general case: a
shunt reactance at one end moves the modes off n*FSR and moves u_n(end), C_n
and gamma_n with them (§4, §7.4). These tests are the gate on that basis.

The one that matters is `test_loaded_s11_converges_to_exact_abcd`: the loaded
comb driven through the ORDINARY hub pipeline, compared to exact ABCD in the
project's JAA convention (Z_ind = -i w L), converging like 1/N exactly as the
unloaded macro does -- i.e. the residual is the truncated tail and nothing
else. Measured (max in-band |dS11|, w_nat in [0.3 pi, 6.7 pi], Z0 = 50/65):

    w_Z = pi     N=10: 1.260   N=20: 0.569   N=40: 0.276   N=80: 0.137
    w_Z = 0.3 pi N=10: 1.256   N=20: 0.567   N=40: 0.275   N=80: 0.136
    (unloaded, for reference)  1.112         0.537         0.268     0.134

Capacitive loads are REFUSED (§7.5): their error plateaus near 0.94 instead of
falling, which means a direct non-resonant term is missing from the comb.
`misc/loaded_line_checks.py` reproduces all of it standalone.
"""

import numpy as np
import pytest

from graphulator import autograph
from tests import cmtline_core

# natural units: ell = Ztx = v = 1  =>  linear FSR = v/2ell = 1/2, w = 2 pi f
FSR = 0.5
ZTX = 1.0
Z0 = 50.0 / 65.0
W_NAT = np.linspace(0.3 * np.pi, 6.7 * np.pi, 400)
N_LADDER = (10, 20, 40, 80)


def _line(N, f_Z, end='xL', port_end='x0', kind='inductive'):
    """A loaded line whose comb holds exactly N pole pairs."""
    load = {'end': end, 'type': kind, 'f_Z': f_Z}
    probe = autograph.LineResonator(line_id='TL', FSR=FSR, Ztx=ZTX,
                                    f_max=FSR, port_end=port_end,
                                    Z0_port=Z0, load=load)
    line = autograph.LineResonator(line_id='TL', label='TL', FSR=FSR, Ztx=ZTX,
                                   f_max=probe.mode_freq(N), port_end=port_end,
                                   Z0_port=Z0, load=load)
    assert line.N == N
    return line


# --------------------------------------------------------------------------
# the roots
# --------------------------------------------------------------------------

@pytest.mark.parametrize('kind', ['inductive', 'capacitive'])
@pytest.mark.parametrize('f_Z', [0.15, 0.5, 1.5, 6.0])
def test_roots_satisfy_the_resonance_condition(kind, f_Z):
    """cot(k_n ell) = X_elem/Ztx -- the source-free condition itself (§7.1).

    The solver handles both element types; it is the macro that refuses a
    capacitive LOAD, and for a different reason (§7.5).
    """
    for n in range(1, 9):
        th = autograph.line_loaded_theta(n, FSR, f_Z, kind)
        f = th * FSR / np.pi
        x = autograph.line_load_reactance(f, f_Z, kind)
        assert abs(1.0 / np.tan(th) - x) < 1e-11, (n, th, x)


@pytest.mark.parametrize('kind', ['inductive', 'capacitive'])
def test_roots_are_bracketed_one_per_interval(kind):
    for n in range(1, 9):
        th = autograph.line_loaded_theta(n, FSR, 1.5, kind)
        assert (n - 1) * np.pi < th < n * np.pi


def test_inductive_short_limit_is_the_quarter_wave_comb():
    """f_Z -> infinity is L -> 0, a SHORT: cot(theta) = 0, theta = (n-1/2)pi."""
    for n in (1, 2, 5):
        th = autograph.line_loaded_theta(n, FSR, 1e9, 'inductive')
        assert abs(th - (n - 0.5) * np.pi) < 1e-7


def test_inductive_open_limit_is_the_open_open_comb_shifted_by_one():
    """f_Z -> 0 is L -> infinity, an OPEN: theta -> (n-1)pi, so mode n
    becomes harmonic n-1 of the open-open comb and mode 1 becomes the free
    DC mode. This is the sense in which load=None is a LIMIT of the loaded
    basis rather than a separate model.

    The approach is asymptotically slow and differently so for n = 1, which
    is the whole content of the limit, so the tolerances are the predicted
    rates rather than a single fudged number: with a = FSR/(pi f_Z),
    cot(theta) = a theta gives theta_1 ~ 1/sqrt(a) and, for n >= 2,
    theta_n - (n-1)pi ~ 1/(a (n-1) pi).
    """
    f_Z = 1e-9
    a = FSR / (np.pi * f_Z)
    th1 = autograph.line_loaded_theta(1, FSR, f_Z, 'inductive')
    assert abs(th1 / (1.0 / np.sqrt(a)) - 1.0) < 1e-3
    for n in (2, 5):
        eps = autograph.line_loaded_theta(n, FSR, f_Z, 'inductive') \
            - (n - 1) * np.pi
        assert abs(eps / (1.0 / (a * (n - 1) * np.pi)) - 1.0) < 1e-3


@pytest.mark.parametrize('kind', ['inductive', 'capacitive'])
@pytest.mark.parametrize('f_Z', [1.0, 3.0, 12.0, 60.0])
@pytest.mark.parametrize('n', [1, 2, 3, 5])
def test_target_resonance_inversion_is_exact(kind, f_Z, n):
    """§7.3's closed form put through the root solver: no iteration, and the
    n-th LOADED mode lands on the target to machine precision."""
    f_t = 6.0
    fsr = autograph.line_fsr_for_target(f_t, n, f_Z, kind)
    got = autograph.line_loaded_theta(n, fsr, f_Z, kind) * fsr / np.pi
    assert abs(got - f_t) < 1e-12 * f_t


# --------------------------------------------------------------------------
# what the load is allowed to be
# --------------------------------------------------------------------------

def test_capacitive_load_is_refused_with_its_reason():
    with pytest.raises(ValueError, match=r'7\.5'):
        autograph.LineResonator(line_id='TL', FSR=FSR, Ztx=ZTX, f_max=3.0,
                                load={'end': 'xL', 'type': 'capacitive',
                                      'f_Z': 1.0})


@pytest.mark.parametrize('bad', [
    {'end': 'middle', 'type': 'inductive', 'f_Z': 1.0},
    {'end': 'xL', 'type': 'galvanic', 'f_Z': 1.0},
    {'end': 'xL', 'type': 'inductive', 'f_Z': 0.0},
    {'end': 'xL', 'type': 'inductive', 'f_Z': -2.0},
    {'end': 'xL', 'type': 'inductive'},
])
def test_bad_loads_are_rejected(bad):
    with pytest.raises(ValueError):
        autograph.LineResonator(line_id='TL', FSR=FSR, Ztx=ZTX, f_max=3.0,
                                load=bad)


def test_no_load_is_the_default_and_changes_nothing():
    line = autograph.LineResonator(line_id='TL', FSR=FSR, Ztx=ZTX, f_max=3.0)
    assert line.load is None and not line.loaded
    assert isinstance(line.gamma, float)
    assert line.mode_node_id(0) in line.comb_mode_ids()
    assert line.mode_freq(3) == 3 * FSR


# --------------------------------------------------------------------------
# the loaded basis
# --------------------------------------------------------------------------

def test_inductive_load_drops_the_dc_mode():
    """An inductor shorts DC, so the free n=0 mode is gone (§7.4)."""
    line = _line(6, f_Z=1.5)
    assert line.mode_node_id(0) not in line.comb_mode_ids()
    assert len(line.comb_mode_ids()) == 2 * line.N
    assert [a[0] for a in line.end_couplings('xL')] == line.comb_mode_ids()


def test_N_is_the_comb_that_reaches_f_max():
    """f_N >= f_max > f_{N-1}: the loaded modes are not at n*FSR, so the
    count follows the roots, and is never below ceil(f_max/FSR)."""
    for f_Z in (0.2, 1.5, 20.0):
        for f_max in (2.0, 3.7, 6.0):
            line = autograph.LineResonator(
                line_id='TL', FSR=FSR, Ztx=ZTX, f_max=f_max, Z0_port=Z0,
                load={'end': 'xL', 'type': 'inductive', 'f_Z': f_Z})
            assert line.mode_freq(line.N) >= f_max
            assert line.N == 1 or line.mode_freq(line.N - 1) < f_max
            assert line.N >= int(np.ceil(f_max / FSR))


def test_loaded_gamma_is_mode_dependent_and_tends_to_the_open_value():
    """gamma_n = 1/(2 pi Z0 C_n) is no longer n-independent -- one more
    thing the open-open basis gets wrong -- but the high modes forget the
    load and return to (2/pi)(Ztx/Z0) FSR."""
    line = _line(40, f_Z=1.5)
    gam_open = (2.0 / np.pi) * (ZTX / Z0) * FSR
    gam = [line.mode_gamma(n) for n in range(1, line.N + 1)]
    assert max(gam) - min(gam) > 0.05 * gam_open       # genuinely dispersed
    assert abs(gam[-1] / gam_open - 1.0) < 0.02        # and asymptotically open
    unloaded = autograph.LineResonator(line_id='TL', FSR=FSR, Ztx=ZTX,
                                       f_max=3.0, Z0_port=Z0)
    assert abs(unloaded.mode_gamma(3) - gam_open) < 1e-12


def test_end_couplings_are_the_profile_times_root_gamma():
    """kappa_n = u_n(end) sqrt(gamma_n), with u = 1 at the open end and
    cos(k_n ell) at the loaded one."""
    line = _line(8, f_Z=1.5, end='xL')
    for end in ('x0', 'xL'):
        got = line.end_couplings(end)
        for (node_id, mag, phase), k in zip(got, line._comb_ks()):
            n = abs(k)
            u = 1.0 if end == 'x0' else np.cos(line.mode_theta(n))
            want = u * np.sqrt(line.mode_gamma(n))
            assert abs(mag - abs(want)) < 1e-12
            assert phase == (0.0 if want >= 0 else 180.0)


def test_load_at_x0_mirrors_load_at_xL():
    """Which end carries the reactance is a relabeling: the open end is
    always the profile's x = 0."""
    a = _line(6, f_Z=1.5, end='xL', port_end='x0')
    b = _line(6, f_Z=1.5, end='x0', port_end='xL')
    assert a.mode_freqs() == b.mode_freqs()
    assert [m for _, m, _ in a.end_couplings('x0')] == \
           [m for _, m, _ in b.end_couplings('xL')]


@pytest.mark.parametrize('coupling', ['capacitive', 'inductive'])
@pytest.mark.parametrize('end', ['x0', 'xL'])
def test_tap_general_form_matches_the_closed_form_when_unloaded(coupling, end):
    """The loaded branch computes the profile from (u_n, f_n, C_n); the
    unloaded branch keeps the closed form (n/n_ref)^(+-1/2) so pinned
    goldens stay bit-identical. They must be the SAME function -- this
    checks the shortcut, rather than letting it hide a discrepancy."""
    line = autograph.LineResonator(line_id='TL', FSR=FSR, Ztx=ZTX, f_max=5.0,
                                   Z0_port=Z0)
    n_ref, exponent = 3, (0.5 if coupling == 'capacitive' else -0.5)

    def amp(n):
        return line.mode_freq(n) ** exponent * line.mode_mass(n) ** -0.5

    ref = abs(line.mode_profile(n_ref, end)) * amp(n_ref)
    for node_id, weight, phase in line.tap_couplings(end, n_ref, coupling):
        n = abs(int(node_id.rsplit('n', 1)[1]))
        u = line.mode_profile(n, end)
        assert abs(weight - abs(u) * amp(n) / ref) < 1e-12 * max(1.0, weight)
        assert phase == (0.0 if u >= 0 else 180.0)


def test_loaded_tap_profile_follows_the_loaded_quantities():
    line = _line(8, f_Z=1.5)
    got = {i: (w, p) for i, w, p in line.tap_couplings('xL', 2, 'inductive')}
    assert line.mode_node_id(0) not in got
    assert got[line.mode_node_id(2)][0] == pytest.approx(1.0)
    # not the unloaded shorthand: the loaded weights differ from sqrt(2/n)
    naive = [np.sqrt(2.0 / n) for n in range(1, line.N + 1)]
    loaded = [got[line.mode_node_id(n)][0] for n in range(1, line.N + 1)]
    assert max(abs(a - b) for a, b in zip(naive, loaded)) > 0.05


def test_nearest_harmonic_uses_the_loaded_frequencies():
    line = _line(8, f_Z=1.5)
    for n in range(1, line.N + 1):
        assert line.nearest_harmonic(line.mode_freq(n)) == n
        assert line.nearest_harmonic(-line.mode_freq(n)) == n
    # and it is NOT the same answer as rounding f/FSR
    assert any(line.nearest_harmonic(line.mode_freq(n))
               != int(round(line.mode_freq(n) / FSR))
               for n in range(1, line.N + 1))


def test_load_survives_serialization():
    line = _line(6, f_Z=1.5)
    again = autograph._normalize_line(line.to_dict())
    assert again.load == line.load
    assert again.mode_freqs() == line.mode_freqs()
    from_pgraph = autograph.pgraph_line_to_resonator(
        {'line_id': 7, 'FSR': FSR, 'Ztx': ZTX, 'f_max': 3.0,
         'load': {'end': 'xL', 'type': 'inductive', 'f_Z': 1.5}})
    assert from_pgraph.load == {'end': 'xL', 'type': 'inductive', 'f_Z': 1.5}


# --------------------------------------------------------------------------
# the gate: the loaded comb vs exact ABCD
# --------------------------------------------------------------------------

def _macro_s11(N, f_Z):
    line = _line(N, f_Z)
    f_phys = W_NAT / (2.0 * np.pi)
    extractor = autograph.GraphExtractor()
    extractor.extract_graph_data(
        nodes=[], edges=[], scattering_assignments={},
        frequency_settings={'start': float(f_phys[0]),
                            'stop': float(f_phys[-1]),
                            'points': len(f_phys)},
        line_resonators=[line])
    return autograph.GraphScatteringMatrix(extractor, f_phys).S[:, 0, 0]


def _exact_s11(f_Z):
    L = ZTX / (2.0 * np.pi * f_Z)          # |X| = Ztx at f_Z
    return np.array([
        cmtline_core.s11(
            cmtline_core.zin_from_abcd(cmtline_core.abcd_line(w, 1.0, ZTX, 1.0),
                                       cmtline_core.Z_ind(w, L)), Z0)
        for w in W_NAT])


@pytest.fixture(scope="module")
def loaded_errors():
    return {(f_Z, N): float(np.max(np.abs(_macro_s11(N, f_Z) - _exact_s11(f_Z))))
            for f_Z in (0.5, 0.15) for N in N_LADDER}


@pytest.mark.parametrize('f_Z', [0.5, 0.15])
def test_loaded_s11_converges_to_exact_abcd(loaded_errors, f_Z):
    """~1/N, the same tail-limited convergence the unloaded macro shows.
    A basis that merely looked plausible would not halve on each doubling."""
    errs = [loaded_errors[(f_Z, N)] for N in N_LADDER]
    assert all(a > b for a, b in zip(errs, errs[1:])), errs
    for a, b in zip(errs[1:], errs[2:]):           # the asymptotic pairs
        assert 1.9 < a / b < 2.3, errs
    assert errs[-1] < 0.15, errs


def test_ignoring_the_load_is_much_worse_than_the_truncation(loaded_errors):
    """The reason this exists: at N=80 the loaded basis is at the truncation
    floor while the open-open basis -- same line, load ignored -- is not."""
    f_Z = 0.5
    naive = autograph.LineResonator(line_id='TL', label='TL', FSR=FSR,
                                    Ztx=ZTX, f_max=80 * FSR, port_end='x0',
                                    Z0_port=Z0)
    f_phys = W_NAT / (2.0 * np.pi)
    extractor = autograph.GraphExtractor()
    extractor.extract_graph_data(
        nodes=[], edges=[], scattering_assignments={},
        frequency_settings={'start': float(f_phys[0]), 'stop': float(f_phys[-1]),
                            'points': len(f_phys)},
        line_resonators=[naive])
    err = np.max(np.abs(
        autograph.GraphScatteringMatrix(extractor, f_phys).S[:, 0, 0]
        - _exact_s11(f_Z)))
    assert err > 5.0 * loaded_errors[(f_Z, 80)], (err, loaded_errors[(f_Z, 80)])


# --------------------------------------------------------------------------
# the GUI path: setting, serializing and pumping a loaded line
# --------------------------------------------------------------------------

import os                                                       # noqa: E402

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")

from tests.test_gui_hubs import para                            # noqa: E402,F401

LOAD = {'end': 'xL', 'type': 'inductive', 'f_Z': 3.0}


def _scene(para, **kw):
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = True
    win._apply_explicit_ports_mode()
    return win, win.add_line_resonator(label='TL1', pos=(0.0, 0.0), FSR=1.5,
                                       Ztx=65.0, f_max=6.0, port_end=None,
                                       **kw)


def test_set_line_load_redefines_the_comb(para):
    win, line = _scene(para)
    before = win.line_resonator_for(line)
    assert before.mode_freqs() == [1.5, 3.0, 4.5, 6.0]

    win.set_line_load(line, LOAD)
    after = win.line_resonator_for(line)
    assert after.load == LOAD
    assert after.mode_freqs() != before.mode_freqs()
    assert after.mode_node_id(0) not in after.comb_mode_ids()

    win.set_line_load(line, None)
    assert win.line_resonator_for(line).mode_freqs() == before.mode_freqs()


def test_capacitive_load_is_refused_through_the_gui(para):
    win, line = _scene(para)
    with pytest.raises(ValueError, match=r'7\.5'):
        win.set_line_load(line, {'end': 'xL', 'type': 'capacitive',
                                 'f_Z': 3.0})
    assert line.get('load') is None          # and nothing was half-applied


def test_load_survives_save_and_reload(para):
    win, line = _scene(para, load=LOAD)
    data = win._serialize_ports_and_lines({'nodes': [], 'edges': []})
    assert data['line_resonators'][0]['load'] == LOAD
    win.line_resonators = []
    win._deserialize_ports_and_lines(data)
    assert win.line_resonators[0]['load'] == LOAD
    assert win.line_resonator_for(win.line_resonators[0]).loaded


def test_pumped_twin_carries_the_same_load(para):
    """The twin is the same physical line in the idler sector, so it must
    see the same dispersed basis — otherwise the pump would couple two
    different combs."""
    win, line = _scene(para, load=LOAD)
    twin = win.set_line_pump(line, 'xL', f_p=5.0, rate=0.05, n_ref=2,
                             coupling='inductive')
    assert twin['load'] == LOAD
    sig = win.line_resonator_for(line)
    idl = win.line_resonator_for(twin)
    assert idl.mode_freqs() == sig.mode_freqs()

    # and a load edit propagates
    win.set_line_load(line, {'end': 'xL', 'type': 'inductive', 'f_Z': 9.0})
    win._gui_lines_payload()                 # syncs twins, as extraction does
    assert twin['load']['f_Z'] == 9.0


def test_pump_partner_is_found_on_the_loaded_comb(para):
    """f_p - f_n, not f_p - n*FSR: on a dispersed comb those name different
    partners, and the rank-one block is built around the one chosen here."""
    win, line = _scene(para, load={'end': 'xL', 'type': 'inductive',
                                   'f_Z': 1.0})
    win.set_line_pump(line, 'xL', f_p=5.0, rate=0.05, n_ref=2,
                      coupling='inductive')
    res = win.line_resonator_for(line)
    n_ref, m_ref = win._pump_reference_pair(line)
    want = int(min(range(1, res.N + 1),
                   key=lambda k: abs(res.mode_freq(k) - abs(5.0 - res.mode_freq(2))))) 
    assert (n_ref, m_ref) == (2, want)
    naive = int(min(max(int(round((5.0 - 2 * res.FSR) / res.FSR)), 1), res.N))
    assert m_ref != naive                     # the shortcut would be wrong


def test_pump_edges_use_the_loaded_profile(para):
    win, line = _scene(para, load=LOAD)
    win.set_line_pump(line, 'xL', f_p=5.0, rate=0.05, n_ref=2,
                      coupling='inductive')
    edges = win._gui_pump_edges()
    assert edges
    res = win.line_resonator_for(line)
    ids = set(res.comb_mode_ids())
    assert all(e['from_node_id'] in ids for e, _ in edges)
    assert all(':n0' not in e['to_node_id'] for e, _ in edges)


def test_stale_reference_mode_is_clamped_not_fatal(para):
    """Lowering f_max (or adding a load) shrinks N under taps and pumps that
    already named a mode; drawing must survive that."""
    win, line = _scene(para)
    node = {'node_id': 0, 'label': 'A', 'pos': (0.0, 4.0), 'conj': False,
            'color': 'cornflowerblue', 'color_key': 'BLUE',
            'node_size_mult': 1.0, 'label_size_mult': 1.0}
    win.nodes.append(node)
    win.scattering_assignments[0] = {'freq': 4.5, 'B_int': 0.0}
    win.connect_line_end_to_node(line, 'xL', 0, rate=0.1, n_ref=4)
    line['f_max'] = 2.0                       # N: 4 -> 2, tap still says 4
    edges = win._gui_tap_edges()
    assert edges and all(abs(int(e['to_node_id'].rsplit('n', 1)[1])) <= 2
                         for e, _ in edges)


def test_line_properties_page_exposes_the_load(para):
    from PySide6.QtWidgets import QLabel, QComboBox
    win, line = _scene(para, load=LOAD)
    panel = win.properties_panel
    panel.show_line_properties(line)

    texts = [w.text() for w in panel.findChildren(QLabel) if w.text()]
    assert any('Loaded modes' in t for t in texts), texts
    assert any('shorted away' in t for t in texts), texts

    # the capacitive entries are listed but disabled, not hidden: the user
    # should see that the case exists and is refused
    def is_load_combo(c):
        return any(isinstance(c.itemData(i), tuple)
                   and c.itemData(i)[1] == 'capacitive'
                   for i in range(c.count()))

    combo = next(c for c in panel.findChildren(QComboBox) if is_load_combo(c))
    for i in range(combo.count()):
        data = combo.itemData(i)
        enabled = combo.model().item(i).isEnabled()
        assert enabled == (data is None or data[1] == 'inductive'), data


def test_line_properties_solver_sets_fsr_from_a_target(para):
    """The ergonomic point of sec. 7.3: name the loaded resonance, get the
    line, instead of guessing FSR and re-checking where the mode landed."""
    from PySide6.QtWidgets import QPushButton, QDoubleSpinBox, QSpinBox
    win, line = _scene(para, load=LOAD)
    panel = win.properties_panel
    panel.show_line_properties(line)

    target = next(s for s in panel.findChildren(QDoubleSpinBox)
                  if s.toolTip().startswith('Where the chosen LOADED mode'))
    mode = next(s for s in panel.findChildren(QSpinBox)
                if s.prefix() == 'mode ')
    button = next(b for b in panel.findChildren(QPushButton)
                  if b.text() == 'Set FSR')
    target.setValue(4.0)
    mode.setValue(1)
    button.click()

    res = win.line_resonator_for(line)
    assert abs(res.mode_freq(1) - 4.0) < 1e-9
    assert abs(res.FSR - 4.0) > 1e-3          # FSR is v/2l, not the mode


def test_codegen_emits_the_load(para):
    win, line = _scene(para, load=LOAD)
    payload = win._gui_lines_payload()[0]
    assert payload['load'] == LOAD


def test_loaded_fundamental_may_sit_below_fsr():
    """FSR is the geometric parameter v/2l once an end is loaded, so
    f_max >= FSR is the wrong invariant there: a strongly loaded line's
    fundamental is far below FSR and the comb still holds it."""
    line = autograph.LineResonator(line_id='TL', FSR=19.5, Ztx=ZTX,
                                   f_max=6.0, Z0_port=Z0,
                                   load={'end': 'xL', 'type': 'inductive',
                                         'f_Z': 3.0})
    assert line.mode_freq(1) < line.FSR
    assert line.N >= 1 and line.mode_freq(line.N) >= line.f_max
    with pytest.raises(ValueError, match='f_max'):
        autograph.LineResonator(line_id='TL', FSR=19.5, Ztx=ZTX, f_max=6.0)


def test_twin_of_a_strongly_loaded_line_can_be_created(para):
    """Regression: the twin was built before its load was mirrored, so a
    line whose FSR exceeds f_max (legal only when loaded) could not be
    pumped at all -- the twin failed the open-open f_max >= FSR check."""
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = True
    win._apply_explicit_ports_mode()
    f_Z = 3.0
    fsr = autograph.line_fsr_for_target(4.0, 1, f_Z, 'inductive')
    line = win.add_line_resonator(label='TL1', pos=(0.0, 0.0), FSR=fsr,
                                  Ztx=65.0, f_max=14.0, port_end=None,
                                  load={'end': 'x0', 'type': 'inductive',
                                        'f_Z': f_Z})
    assert fsr > 14.0                           # the case that used to fail
    twin = win.set_line_pump(line, 'x0', f_p=9.0, rate=0.05, n_ref=1)
    assert twin['load'] == line['load']
    assert abs(win.line_resonator_for(twin).mode_freq(1) - 4.0) < 1e-9


def test_loaded_scene_round_trips():
    """The bundled LINE_PUMPED_LOADED scene loads and its line is loaded."""
    import json
    import os
    path = os.path.join(os.path.dirname(__file__), os.pardir, 'examples',
                        'test_scenes', 'LINE_PUMPED_LOADED.pgraph')
    if not os.path.exists(path):
        pytest.skip("scene not generated")
    with open(path) as fh:
        data = json.load(fh)
    primary = next(l for l in data['line_resonators']
                   if l.get('twin_of') is None)
    res = autograph.pgraph_line_to_resonator(primary)
    assert res.loaded and abs(res.mode_freq(1) - 4.0) < 1e-9
