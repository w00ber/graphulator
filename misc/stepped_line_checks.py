"""Reproduce the numbers in sec. 9 of docs/pumped_line_termination.md.

A transmission line made of SECTIONS of different characteristic impedance
(a stepped-impedance resonator), open at one end and terminated at the
other by a shunt inductor or left open. Everything is checked against an
INDEPENDENT reference -- tests/cmtline_core.py's abcd_line per section,
cascaded by hand and terminated in its Z_ind (JAA convention) -- never the
macro's own input_impedance.

  1. the roots are the zeros of the cascade's admittance numerator;
  2. the mode mass equals an adaptive quadrature of the sections' energies;
  3. complex S11 through the ordinary hub pipeline vs the cascade:
     ~1/N with the tail closure off, rounding with it on;
  4. equal sections reproduce the uniform line to rounding;
  5. the geometry of Lee, Spietz & Aumentado (2013) PREDICTS its measured
     harmonic ratio with nothing fitted.

    python misc/stepped_line_checks.py

The gate is tests/test_stepped_line.py, which re-measures 1-5 through the
shipped macro.
"""
import os
import sys

import numpy as np
from scipy.integrate import quad

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

from graphulator import autograph                        # noqa: E402
from graphulator.autograph import LineResonator, _stepped_state  # noqa: E402
import cmtline_core as core                              # noqa: E402

FSR, ZREF, Z0 = 1.0, 50.0, 50.0
SECS = [{'Z': 30.0, 'frac': 0.4}, {'Z': 80.0, 'frac': 0.6}]
LOAD = {'end': 'xL', 'type': 'inductive', 'f_Z': 2.5}
W = np.linspace(0.3, 6.7, 400) / 2.0


def cascade(line, end, f):
    secs = line.sections or [{'Z': line.Ztx, 'frac': 1.0}]
    seq = [(s['Z'], s['frac']) for s in secs]
    if end == 'xL':
        seq = seq[::-1]
    w = 2.0 * np.pi * f
    M = np.eye(2, dtype=complex)
    for Z, frac in seq:
        M = M @ core.abcd_line(w, ell=frac / (2.0 * line.FSR), Ztx=Z, v=1.0)
    ZL = (np.inf if line.load is None
          else core.Z_ind(w, line.Ztx / (2.0 * np.pi * line.load['f_Z'])))
    return M, ZL


def exact_zin(line, end, f):
    M, ZL = cascade(line, end, f)
    if line.load is not None and line.load['end'] == end:
        return 1.0 / (1.0 / ZL + 1.0 / core.zin_from_abcd(M, np.inf))
    return core.zin_from_abcd(M, ZL)


def admittance_numerator(line, end, f):
    M, ZL = cascade(line, end, f)
    num = M[1, 0] if np.isinf(ZL) else M[1, 0] * ZL + M[1, 1]
    return num.real if abs(num.real) >= abs(num.imag) else num.imag


def check_roots():
    print("1. roots are the zeros of the cascade's admittance numerator")
    for label, secs, load in (
            ("2 sections, open-open", SECS, None),
            ("2 sections, L at xL", SECS, LOAD),
            ("3 sections, L at x0",
             [{'Z': 47.3, 'frac': 1 / 3}, {'Z': 65.0, 'frac': 1 / 3},
              {'Z': 51.4, 'frac': 1 / 3}],
             {'end': 'x0', 'type': 'inductive', 'f_Z': 4.0})):
        ln = LineResonator(line_id=0, FSR=FSR, Ztx=ZREF, f_max=8.0,
                           sections=secs, load=load)
        o = ln._origin_end
        worst = max(abs(admittance_numerator(ln, o, ln.mode_freq(n)))
                    / abs(admittance_numerator(ln, o, ln.mode_freq(n) * 1.001))
                    for n in range(1, ln.N + 1))
        fg = np.linspace(1e-4, ln.mode_freq(ln.N) * (1 + 1e-6), 60000)
        H = np.array([admittance_numerator(ln, o, f) for f in fg])
        zeros = int(np.sum(np.sign(H[1:]) != np.sign(H[:-1])))
        print(f"   {label:24s} N={ln.N:2d}  max|h(f_n)|/|h(1.001 f_n)| = "
              f"{worst:.1e}   zeros on grid = {zeros}")
        print(f"   {'':24s} modes: "
              + ", ".join(f"{ln.mode_freq(n):.4f}" for n in range(1, ln.N + 1)))


def check_mass():
    print("\n2. mode mass: closed form vs adaptive quadrature")
    ln = LineResonator(line_id=0, FSR=FSR, Ztx=ZREF, f_max=6.0,
                       sections=SECS, load=LOAD)
    secs = ln._sections_from(ln._origin_end)
    for n in (1, 2, 5):
        th = ln.mode_theta(n)
        _, _, pieces = _stepped_state(th, secs)
        tot = 0.0
        for u0, w0, Z, d in pieces:
            val, _ = quad(lambda t: (u0 * np.cos(t) + Z * w0 * np.sin(t)) ** 2,
                          0.0, d, epsabs=1e-14, epsrel=1e-14, limit=200)
            tot += val / (2.0 * Z * ln.FSR * th)
        print(f"   n={n}: closed {ln.mode_mass(n):.15e}  quad {tot:.15e}  "
              f"rel {(ln.mode_mass(n) - tot) / tot:+.1e}")


def macro_s11(N, closure, secs=SECS, load=LOAD):
    probe = LineResonator(line_id='TL', FSR=FSR, Ztx=ZREF, f_max=FSR,
                          port_end='x0', Z0_port=Z0, sections=secs, load=load)
    ln = LineResonator(line_id='TL', label='TL', FSR=FSR, Ztx=ZREF,
                       f_max=probe.mode_freq(N), port_end='x0', Z0_port=Z0,
                       sections=secs, load=load)
    assert ln.N == N
    ex = autograph.GraphExtractor()
    ex.extract_graph_data(nodes=[], edges=[], scattering_assignments={},
                          frequency_settings={'start': float(W[0]),
                                              'stop': float(W[-1]),
                                              'points': len(W)},
                          line_resonators=[ln])
    return autograph.GraphScatteringMatrix(ex, W, tail_closure=closure).S[:, 0, 0]


def check_s11():
    print("\n3. complex S11 vs the independent cascade (30/80 ohm, L at xL)")
    ln = LineResonator(line_id=0, FSR=FSR, Ztx=ZREF, f_max=1.0,
                       sections=SECS, load=LOAD)
    ref = np.array([core.s11(exact_zin(ln, 'x0', f), Z0) for f in W])
    errs = []
    for N in (10, 20, 40, 80):
        off = np.max(np.abs(macro_s11(N, False) - ref))
        on = np.max(np.abs(macro_s11(N, True) - ref))
        errs.append(off)
        print(f"   N={N:3d}: closure OFF {off:.3e}   closure ON {on:.3e}")
    print("   ratios OFF:", " / ".join(f"{a / b:.3f}" for a, b in zip(errs, errs[1:])))


def check_uniform_limit():
    print("\n4. equal sections reproduce the uniform line")
    for load in (None, {'end': 'x0', 'type': 'inductive', 'f_Z': 3.0}):
        u = LineResonator(line_id=0, FSR=1.0, Ztx=50.0, f_max=6.0, port_end='xL',
                          Z0_port=50.0, load=load)
        s = LineResonator(line_id=1, FSR=1.0, Ztx=50.0, f_max=6.0, port_end='xL',
                          Z0_port=50.0, load=load,
                          sections=[{'Z': 50.0, 'frac': 0.3}, {'Z': 50.0, 'frac': 0.7}])
        fu, ku, _, _ = u.expand_arrays()
        fs, ks, _, _ = s.expand_arrays()
        print(f"   load={'none' if load is None else 'L'}: max|df| = "
              f"{np.max(np.abs(fu - fs)):.1e}  max|dkappa| = "
              f"{np.max(np.abs(ku - ks)):.1e}")


def check_lee2013():
    print("\n5. Lee, Spietz & Aumentado (2013): predicted harmonic ratio")
    Phi0, I_SQ = 2.067833848e-15, 0.82e-6
    L = Phi0 / (2 * np.pi * I_SQ)
    fZ = 50.0 / (2 * np.pi * L) / 1e9
    secs = [{'Z': 47.3, 'frac': 2 / 3}, {'Z': 51.4, 'frac': 1 / 3}]
    load = {'end': 'xL', 'type': 'inductive', 'f_Z': fZ}
    st = LineResonator(line_id=0, FSR=4.0, Ztx=50.0, f_max=8.0, sections=secs, load=load)
    un = LineResonator(line_id=0, FSR=4.0, Ztx=50.0, f_max=8.0, load=load)
    print(f"   L_SQ = {L * 1e9:.4f} nH, f_Z = {fZ:.2f} GHz (Zref 50)")
    print(f"   stepped f_B/f_A = {st.mode_freq(2) / st.mode_freq(1):.4f}   "
          f"uniform {un.mode_freq(2) / un.mode_freq(1):.4f}   "
          f"measured 5.661/1.840 = {5.661 / 1.840:.4f} (bias), ~3.095 (zero flux)")


if __name__ == '__main__':
    check_roots()
    check_mass()
    check_s11()
    check_uniform_limit()
    check_lee2013()
