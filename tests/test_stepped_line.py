"""Stepped-impedance lines: several sections of different Ztx (docs sec. 9).

The loaded basis (sec. 7) assumed one impedance. A stepped line keeps the
same recipe -- roots of a source-free condition, an energy normalization,
end profiles -- with the standing wave propagated PIECEWISE through the
steps (u and w = du/ds / Z_j both continuous), and the exact Z_in becomes
the section cascade, so the tail closure comes along unchanged.

Every gate here is against an INDEPENDENT reference: cmtline_core's
abcd_line per section cascaded by hand and terminated in its Z_ind (the
project's JAA convention), never the macro's own input_impedance.

Measured (misc/stepped_line_checks.py), 30/80 ohm sections 0.4/0.6, an
inductive load f_Z = 2.5 FSR at xL, port at x0:

    closure OFF   N=10 2.459e-01   N=20 1.161e-01   N=40 5.666e-02   N=80 2.801e-02
                  ratios 2.117 / 2.050 / 2.023   (~1/N, the truncated tail)
    closure ON    1.5e-15 at every N              (the basis AND the cascade)

and the geometry of Lee, Spietz & Aumentado (2013) -- 47.3 ohm over 2/3 of
the line at the port, 51.4 ohm over 1/3 at the SQUID, L_SQ = 0.40 nH --
PREDICTS f_B/f_A = 3.089 with nothing fitted, against the paper's measured
3.077 (bias) and ~3.095 (zero flux); a uniform line gives 3.004.
"""

import json
import os

# Set BEFORE anything that may pull in Qt: the GUI half of this module
# builds a window, and the platform plugin is chosen at import time. Ruff's
# I001 autofix will hoist the imports above this block if the noqa goes
# missing -- the suite masks it (another module gets there first), so it
# only bites when this file is run alone.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")

import numpy as np                                          # noqa: E402
import pytest                                               # noqa: E402

from graphulator import autograph                           # noqa: E402
from graphulator.autograph import LineResonator             # noqa: E402
from tests import cmtline_core as core                      # noqa: E402

FSR, ZREF, Z0 = 1.0, 50.0, 50.0
SECS = [{'Z': 30.0, 'frac': 0.4}, {'Z': 80.0, 'frac': 0.6}]
LOAD = {'end': 'xL', 'type': 'inductive', 'f_Z': 2.5}
W = np.linspace(0.3, 6.7, 400) / 2.0          # in-band, off the exact poles


def exact_zin(line, end, f):
    """Independent ABCD: cascade of cmtline_core.abcd_line per section from
    `end`, physical units (ell_j / v = frac_j / 2 FSR), terminated in
    Z_ind or open. Mirrors nothing in the macro."""
    secs = line.sections or [{'Z': line.Ztx, 'frac': 1.0}]
    seq = [(s['Z'], s['frac']) for s in secs]
    if end == 'xL':
        seq = seq[::-1]
    w = 2.0 * np.pi * f
    M = np.eye(2, dtype=complex)
    for Z, frac in seq:
        M = M @ core.abcd_line(w, ell=frac / (2.0 * line.FSR), Ztx=Z, v=1.0)
    if line.load is None:
        return core.zin_from_abcd(M, np.inf)
    ZL = core.Z_ind(w, line.Ztx / (2.0 * np.pi * line.load['f_Z']))
    if line.load['end'] == end:
        return 1.0 / (1.0 / ZL + 1.0 / core.zin_from_abcd(M, np.inf))
    return core.zin_from_abcd(M, ZL)


def _line(N, sections=SECS, load=LOAD, port_end='x0'):
    probe = LineResonator(line_id='TL', FSR=FSR, Ztx=ZREF, f_max=FSR,
                          port_end=port_end, Z0_port=Z0, sections=sections,
                          load=load)
    line = LineResonator(line_id='TL', label='TL', FSR=FSR, Ztx=ZREF,
                         f_max=probe.mode_freq(N), port_end=port_end,
                         Z0_port=Z0, sections=sections, load=load)
    assert line.N == N
    return line


# ---------------------------------------------------------------------------
# the uniform limit: equal sections ARE the uniform line
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('load', [None, {'end': 'x0', 'type': 'inductive',
                                         'f_Z': 3.0}])
def test_equal_sections_reproduce_the_uniform_line(load):
    u = LineResonator(line_id=0, FSR=1.0, Ztx=50.0, f_max=6.0, port_end='xL',
                      Z0_port=50.0, load=load)
    s = LineResonator(line_id=1, FSR=1.0, Ztx=50.0, f_max=6.0, port_end='xL',
                      Z0_port=50.0, load=load,
                      sections=[{'Z': 50.0, 'frac': 0.3}, {'Z': 50.0, 'frac': 0.7}])
    assert s.N == u.N
    for n in range(1, u.N + 1):
        assert abs(s.mode_freq(n) - u.mode_freq(n)) < 1e-12
        assert abs(s.mode_mass(n) - u.mode_mass(n)) < 1e-15
        for end in ('x0', 'xL'):
            assert abs(s.mode_profile(n, end) - u.mode_profile(n, end)) < 1e-12
    fu, ku, gu, _ = u.expand_arrays()
    fs, ks, gs, _ = s.expand_arrays()
    assert np.max(np.abs(fu - fs)) < 1e-12
    assert np.max(np.abs(ku - ks)) < 1e-12
    assert np.max(np.abs(gu - gs)) < 1e-15
    z = np.linspace(0.3, 5.7, 7) + 0.01j
    for end in ('x0', 'xL'):
        zu, zs = u.input_impedance(end, z), s.input_impedance(end, z)
        assert np.max(np.abs(zu - zs) / np.abs(zu)) < 1e-13


def test_no_sections_is_the_default_and_changes_nothing():
    line = LineResonator(line_id=0, FSR=1.5, Ztx=65.0, f_max=9.0, port_end='xL')
    assert line.sections is None and not line.stepped
    assert line.to_dict()['sections'] is None


# ---------------------------------------------------------------------------
# the roots are the zeros of the source-free admittance
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('sections, load', [
    (SECS, None),
    (SECS, LOAD),
    ([{'Z': 47.3, 'frac': 1 / 3}, {'Z': 65.0, 'frac': 1 / 3},
      {'Z': 51.4, 'frac': 1 / 3}],
     {'end': 'x0', 'type': 'inductive', 'f_Z': 4.0}),
])
def admittance_numerator(line, end, f):
    """The independent cascade's Y_in numerator, finite everywhere: with
    Z_in = (A ZL + B)/(C ZL + D) the modes are the zeros of C ZL + D (open
    far end: the zeros of C). Lossless, so it is purely real or imaginary
    -- return it as a real number with its sign."""
    secs = line.sections or [{'Z': line.Ztx, 'frac': 1.0}]
    seq = [(s['Z'], s['frac']) for s in secs]
    if end == 'xL':
        seq = seq[::-1]
    w = 2.0 * np.pi * f
    M = np.eye(2, dtype=complex)
    for Z, frac in seq:
        M = M @ core.abcd_line(w, ell=frac / (2.0 * line.FSR), Ztx=Z, v=1.0)
    if line.load is None:
        num = M[1, 0]                         # C: -i sin/Z form, imaginary
    else:
        ZL = core.Z_ind(w, line.Ztx / (2.0 * np.pi * line.load['f_Z']))
        num = M[1, 0] * ZL + M[1, 1]          # C ZL + D, real
    return num.real if abs(num.real) >= abs(num.imag) else num.imag


@pytest.mark.parametrize('sections, load', [
    (SECS, None),
    (SECS, LOAD),
    ([{'Z': 47.3, 'frac': 1 / 3}, {'Z': 65.0, 'frac': 1 / 3},
      {'Z': 51.4, 'frac': 1 / 3}],
     {'end': 'x0', 'type': 'inductive', 'f_Z': 4.0}),
])
def test_roots_are_the_zeros_of_the_independent_admittance(sections, load):
    line = LineResonator(line_id=0, FSR=1.0, Ztx=ZREF, f_max=8.0,
                         sections=sections, load=load)
    origin = line._origin_end
    assert line.N >= 8
    for n in range(1, line.N + 1):
        f_n = line.mode_freq(n)
        h = admittance_numerator(line, origin, f_n)
        # slope scale: the numerator one part in 1e3 away
        h_off = admittance_numerator(line, origin, f_n * (1.0 + 1e-3))
        assert abs(h) < 1e-10 * abs(h_off), (n, f_n, h, h_off)
    # and none are missed: the numerator is finite and smooth, so its sign
    # flips on a fine grid count its zeros exactly
    fg = np.linspace(1e-4, line.mode_freq(line.N) * (1 + 1e-6), 60000)
    H = np.array([admittance_numerator(line, origin, f) for f in fg])
    zeros = int(np.sum(np.sign(H[1:]) != np.sign(H[:-1])))
    assert zeros == line.N, (zeros, line.N)


def test_roots_are_ordered_and_distinct():
    line = LineResonator(line_id=0, FSR=1.0, Ztx=ZREF, f_max=12.0,
                         sections=SECS, load=LOAD)
    fs = line.mode_freqs()
    assert all(b > a for a, b in zip(fs, fs[1:]))
    assert fs[-1] >= 12.0 and fs[-2] < 12.0


# ---------------------------------------------------------------------------
# S11 against the independent cascade
# ---------------------------------------------------------------------------

def _macro_s11(N, closure):
    line = _line(N)
    ex = autograph.GraphExtractor()
    ex.extract_graph_data(nodes=[], edges=[], scattering_assignments={},
                          frequency_settings={'start': float(W[0]),
                                              'stop': float(W[-1]),
                                              'points': len(W)},
                          line_resonators=[line])
    return autograph.GraphScatteringMatrix(ex, W, tail_closure=closure).S[:, 0, 0]


@pytest.fixture(scope='module')
def exact_s11():
    line = _line(2)
    return np.array([core.s11(exact_zin(line, 'x0', f), Z0) for f in W])


@pytest.fixture(scope='module')
def errors(exact_s11):
    return {N: float(np.max(np.abs(_macro_s11(N, False) - exact_s11)))
            for N in (10, 20, 40, 80)}


def test_truncated_basis_converges_like_one_over_N(errors):
    errs = [errors[N] for N in (10, 20, 40, 80)]
    assert all(a > b for a, b in zip(errs, errs[1:])), errs
    for a, b in zip(errs[1:], errs[2:]):
        assert 1.9 < a / b < 2.3, errs
    assert errs[-1] < 0.05, errs


@pytest.mark.parametrize('N', [10, 20, 40])
def test_closed_comb_matches_the_independent_cascade_exactly(exact_s11, N):
    """Basis AND cascade: with the tail closed the macro is the ABCD answer
    to rounding, at any N."""
    S = _macro_s11(N, True)
    assert np.max(np.abs(S - exact_s11)) < 1e-12
    assert np.max(np.abs(np.abs(S) - 1.0)) < 1e-12       # lossless => unitary


def test_stepped_open_open_keeps_a_flat_dc_mode(exact_s11):
    """No load: the DC mode survives (u_0 = 1 at both ends, C_0 = C_line) and
    the closed comb still equals the cascade."""
    line = LineResonator(line_id='TL', label='TL', FSR=FSR, Ztx=ZREF,
                         f_max=9.0, port_end='x0', Z0_port=Z0, sections=SECS)
    freqs, kap, gam, _ = line.expand_arrays()
    assert freqs[0] == 0.0 and abs(kap[0] ** 2 - gam[0]) < 1e-15
    assert abs(gam[0] - 1.0 / (np.pi * Z0 * line.C_line)) < 1e-15
    ex = autograph.GraphExtractor()
    ex.extract_graph_data(nodes=[], edges=[], scattering_assignments={},
                          frequency_settings={'start': float(W[0]),
                                              'stop': float(W[-1]),
                                              'points': len(W)},
                          line_resonators=[line])
    S = autograph.GraphScatteringMatrix(ex, W, tail_closure=True).S[:, 0, 0]
    ref = np.array([core.s11(exact_zin(line, 'x0', f), Z0) for f in W])
    assert np.max(np.abs(S - ref)) < 1e-12


# ---------------------------------------------------------------------------
# the mode quantities behave as a stepped line's must
# ---------------------------------------------------------------------------

def test_mass_is_the_sum_of_the_sections_energies():
    """C_n from the closed-form per-section integrals equals an adaptive
    quadrature of c u_n^2 along the line, section by section, with the
    same continuous (u, w) state -- the closed form is exact, not fitted."""
    from scipy.integrate import quad

    from graphulator.autograph import _stepped_state
    line = LineResonator(line_id=0, FSR=1.0, Ztx=ZREF, f_max=6.0,
                         sections=SECS, load=LOAD)
    secs = line._sections_from(line._origin_end)
    for n in (1, 2, 5):
        th = line.mode_theta(n)
        _, _, pieces = _stepped_state(th, secs)
        total = 0.0
        for u0, w0, Z, d in pieces:
            val, _ = quad(lambda t: (u0 * np.cos(t) + Z * w0 * np.sin(t)) ** 2,
                          0.0, d, epsabs=1e-14, epsrel=1e-14, limit=200)
            total += val / (2.0 * Z * line.FSR * th)
        assert abs(total - line.mode_mass(n)) < 1e-13 * line.mode_mass(n)
    # continuity of voltage and current across the step
    th = line.mode_theta(2)
    _, _, pieces = _stepped_state(th, secs)
    (u0, w0, Z, d), (u1, w1, _, _) = pieces[0], pieces[1]
    assert abs(u0 * np.cos(d) + Z * w0 * np.sin(d) - u1) < 1e-14
    assert abs(-(u0 / Z) * np.sin(d) + w0 * np.cos(d) - w1) < 1e-14


def test_lee2013_geometry_predicts_the_measured_harmonic_shift():
    """The stepped impedance of the 2013 experiment, PHYSICAL values only:
    47.3 ohm over 2/3 (port side), 51.4 ohm over 1/3 (SQUID side),
    L_SQ = Phi0 / 2 pi I_SQ with I_SQ = 0.82 uA. Measured f_B/f_A = 3.077
    at the bias of Figs. 3-4 (~3.095 at zero flux, Fig. 1b); a uniform
    line gives 3.004. Nothing here is fitted."""
    Phi0, I_SQ = 2.067833848e-15, 0.82e-6
    L = Phi0 / (2 * np.pi * I_SQ)                        # 0.4013 nH
    fZ = 50.0 / (2 * np.pi * L) / 1e9                    # GHz, Zref = 50
    secs = [{'Z': 47.3, 'frac': 2 / 3}, {'Z': 51.4, 'frac': 1 / 3}]
    load = {'end': 'xL', 'type': 'inductive', 'f_Z': fZ}
    stepped = LineResonator(line_id=0, FSR=4.0, Ztx=50.0, f_max=8.0,
                            sections=secs, load=load)
    uniform = LineResonator(line_id=0, FSR=4.0, Ztx=50.0, f_max=8.0, load=load)
    r_step = stepped.mode_freq(2) / stepped.mode_freq(1)
    r_unif = uniform.mode_freq(2) / uniform.mode_freq(1)
    assert abs(r_unif - 3.004) < 0.002
    assert abs(r_step - 3.089) < 0.002
    assert abs(r_step - 3.077) / 3.077 < 0.005            # within 0.5 % of measured
    assert r_step > r_unif + 0.05                         # the step does the work


def test_validation():
    with pytest.raises(ValueError, match="at least two"):
        LineResonator(line_id=0, FSR=1.0, Ztx=50.0, f_max=3.0,
                      sections=[{'Z': 50.0, 'frac': 1.0}])
    with pytest.raises(ValueError, match="Z > 0"):
        LineResonator(line_id=0, FSR=1.0, Ztx=50.0, f_max=3.0,
                      sections=[{'Z': -1.0, 'frac': 0.5}, {'Z': 50.0, 'frac': 0.5}])
    with pytest.raises(ValueError, match="'Z' and 'frac'"):
        LineResonator(line_id=0, FSR=1.0, Ztx=50.0, f_max=3.0,
                      sections=[{'Z': 30.0}, {'Z': 50.0, 'frac': 0.5}])
    # fractions are normalized
    line = LineResonator(line_id=0, FSR=1.0, Ztx=50.0, f_max=3.0,
                         sections=[{'Z': 30.0, 'frac': 2.0}, {'Z': 80.0, 'frac': 3.0}])
    assert [round(s['frac'], 12) for s in line.sections] == [0.4, 0.6]


# ---------------------------------------------------------------------------
# through the GUI: set, mirror to the twin, save, load, export
# ---------------------------------------------------------------------------

from tests.test_gui_hubs import para  # noqa: E402,F401


def test_sections_through_the_gui_round_trip_and_reach_the_twin(para):
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = True
    win._apply_explicit_ports_mode()
    line = win.add_line_resonator(label='TL', pos=(0.0, 2.0), FSR=1.0,
                                  Ztx=50.0, f_max=6.0, port_end='x0',
                                  load=LOAD)
    win.set_line_sections(line, SECS)
    res = win.line_resonator_for(line)
    assert res.stepped and res.N == _line(res.N).N
    twin = win.set_line_pump(line, 'xL', f_p=2 * res.mode_freq(1), rate=0.01,
                             n_ref=1, twin_pos=(0.0, -2.0))
    assert twin['sections'] == line['sections']
    data = json.loads(json.dumps(win._serialize_graph()))
    win._deserialize_graph(data)
    r_line = next(l for l in win.line_resonators if l.get('pump'))
    r_twin = win.line_twin(r_line)
    assert r_line['sections'] == SECS and r_twin['sections'] == SECS
    with pytest.raises(ValueError, match="primary"):
        win.set_line_sections(r_twin, None)
    # export carries the sections into the generated LineResonator literal
    win._enter_scattering_mode()
    code = win.properties_panel._generate_scattering_calculation_code()
    assert code is not None and "sections=[{'Z': 30.0, 'frac': 0.4}" in code


# ---------------------------------------------------------------------------
# the drawing says so: bands, dividers, caption, panel row
# ---------------------------------------------------------------------------

def test_glyph_draws_one_band_per_section_thinner_for_higher_Z(para):
    """A stepped line must LOOK stepped. Band thickness follows the
    transmission-line reading -- higher Z is a thinner conductor -- and the
    length-weighted mean is the nominal height, so a uniform line is drawn
    exactly as before and a stepped one keeps its footprint."""
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = True
    win._apply_explicit_ports_mode()
    uni = win.add_line_resonator(label='U', pos=(0.0, 4.0), FSR=1.0, Ztx=50.0,
                                 f_max=6.0, port_end='xL')
    assert win._line_section_bands(uni) is None          # unchanged path

    line = win.add_line_resonator(label='S', pos=(0.0, 0.0), FSR=1.0,
                                  Ztx=50.0, f_max=6.0, port_end='xL',
                                  sections=[{'Z': 20.0, 'frac': 0.35},
                                            {'Z': 90.0, 'frac': 0.4},
                                            {'Z': 45.0, 'frac': 0.25}])
    bands = win._line_section_bands(line)
    assert len(bands) == 3
    lx, ly, w, h, _ = win._line_geometry(line)
    # bands tile the body exactly, in order, with the right lengths
    assert bands[0][0] == pytest.approx(lx - w)
    assert bands[-1][1] == pytest.approx(lx + w)
    for (_, x_hi, _, _, _), (x_lo, _, _, _, _) in zip(bands, bands[1:]):
        assert x_hi == pytest.approx(x_lo)
    for (x_lo, x_hi, _, _, frac) in bands:
        assert x_hi - x_lo == pytest.approx(2 * w * frac)
    # higher Z -> thinner, monotonically
    hs = {Z: bh for _, _, bh, Z, _ in bands}
    assert hs[20.0] > hs[45.0] > hs[90.0]
    lo_f, hi_f = win.LINE_SECTION_H_RANGE
    for _, _, bh, _, _ in bands:
        assert lo_f * h - 1e-12 <= bh <= hi_f * h + 1e-12

    # equal impedances reproduce the uniform height exactly
    flat = win.add_line_resonator(label='F', pos=(0.0, -4.0), FSR=1.0,
                                  Ztx=50.0, f_max=6.0, port_end='xL',
                                  sections=[{'Z': 50.0, 'frac': 0.3},
                                            {'Z': 50.0, 'frac': 0.7}])
    _, _, _, h_flat, _ = win._line_geometry(flat)
    for _, _, bh, _, _ in win._line_section_bands(flat):
        assert bh == pytest.approx(h_flat)
    # ... and so do its lead tips, which follow the END sections' caps
    assert (win._line_end_points(flat)['x0'][0]
            == pytest.approx(win._line_end_points(uni)['x0'][0]))


def test_sections_are_stored_canonically(para):
    """line['sections'] always holds NORMALIZED fractions, whichever door
    they came in by -- the glyph lays the body out from these numbers
    directly, so raw 'Z:2, Z:1' input would draw a body twice too long."""
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = True
    win._apply_explicit_ports_mode()
    raw = [{'Z': 25.0, 'frac': 1.0}, {'Z': 75.0, 'frac': 3.0}]
    line = win.add_line_resonator(label='A', pos=(0.0, 0.0), FSR=1.0,
                                  Ztx=50.0, f_max=6.0, port_end='xL',
                                  sections=raw)
    assert [s['frac'] for s in line['sections']] == [0.25, 0.75]
    win.set_line_sections(line, [{'Z': 47.3, 'frac': 2.0},
                                 {'Z': 51.4, 'frac': 1.0}])
    assert [round(s['frac'], 10) for s in line['sections']] == [
        round(2 / 3, 10), round(1 / 3, 10)]
    # and the bands then tile the body exactly
    lx, _, w, _, _ = win._line_geometry(line)
    bands = win._line_section_bands(line)
    assert bands[-1][1] == pytest.approx(lx + w)


def test_caption_and_panel_row_name_the_sections(para):
    """The parameter has to be READABLE: it was clipped off the physics row
    and absent from the glyph caption, which is how a stepped line looked
    exactly like a uniform one."""
    from PySide6.QtWidgets import QLineEdit

    from graphulator.para_features.explicit_ports import format_sections, parse_sections
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = True
    win._apply_explicit_ports_mode()
    line = win.add_line_resonator(label='TL', pos=(0.0, 0.0), FSR=1.0,
                                  Ztx=50.0, f_max=6.0, port_end='xL',
                                  sections=SECS)
    assert format_sections(SECS) == '30:0.4, 80:0.6'
    assert parse_sections('30:0.4, 80:0.6') == SECS
    assert parse_sections('  ') is None
    with pytest.raises(ValueError, match="Z:frac"):
        parse_sections('30, 80')

    win._enter_scattering_mode()
    panel = win.properties_panel
    panel._update_scattering_ports_table()
    # the editable spec field is on the panel, showing the canonical spec
    edits = [e for e in panel.ports_param_holder.findChildren(QLineEdit)
             if e.text() == format_sections(SECS)] \
        if hasattr(panel, 'ports_param_holder') else []
    if not edits:            # holder name differs; search the whole panel
        edits = [e for e in panel.findChildren(QLineEdit)
                 if e.text() == format_sections(SECS)]
    assert edits, "no sections field showing the spec"

    # editing it applies through set_line_sections, canonically
    edits[0].setText('25:1, 75:3')
    edits[0].editingFinished.emit()
    assert [s['frac'] for s in line['sections']] == [0.25, 0.75]
    assert edits[0].text() == '25:0.25, 75:0.75'
    # an invalid spec is refused and the field reverts
    edits[0].setText('nonsense')
    edits[0].editingFinished.emit()
    assert line['sections'][0]['Z'] == 25.0
    assert edits[0].text() == '25:0.25, 75:0.75'
