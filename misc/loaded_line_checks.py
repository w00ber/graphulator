"""Reproduce the numbers in §7 of docs/pumped_line_termination.md.

A transmission line, open at x = 0 (where the port sits) and terminated at
x = l by a shunt reactance. Everything is checked against exact ABCD through
tests/cmtline_core.py, in the project's JAA convention (Z_ind = -i w L,
Z_cap = +i/(w C)).

  1. the resonance condition cot(kl) = X_elem/Ztx, vs the raw admittance;
  2. the closed-form length for a TARGET loaded resonance;
  3. the loaded mode quantities (roots, u_n(l), C_n, gamma_n) fed through the
     ordinary hub pipeline vs exact ABCD: ~1/N for an inductive load (as for
     the unloaded macro), and NOT yet converging for a capacitive one.

    python misc/loaded_line_checks.py

The inductive case is now implemented in the app (LineResonator(load=...));
tests/test_loaded_line.py is its gate and re-measures check 3 through the
shipped macro. This script stays as the standalone, dependency-light
derivation -- in particular it is the only place the capacitive case is
computed at all, since the macro refuses it.
"""
import os
import sys

import numpy as np
from scipy.optimize import brentq

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

from graphulator import autograph            # noqa: E402
import cmtline_core as core                  # noqa: E402

ZTX = V = ELL = 1.0                          # natural units: k = omega
Z0 = 50.0 / 65.0                             # same natural port as the ABCD test


def x_of(w, wZ, kind):
    """Normalized reactance X_elem/Ztx at angular frequency w."""
    return w / wZ if kind == 'L' else -wZ / w


def z_elem(w, wZ, kind):
    return (core.Z_ind(w, ZTX / wZ) if kind == 'L'
            else core.Z_cap(w, 1.0 / (ZTX * wZ)))


def loaded_modes(wZ, kind, N):
    """[(omega_n, gamma_n^linear)] for the loaded line, port at x = 0."""
    c_elem = 0.0 if kind == 'L' else 1.0 / (ZTX * wZ)
    ws = []
    for n in range(0, N + 3):
        lo, hi = n * np.pi + 1e-12, (n + 1) * np.pi - 1e-12
        g = lambda w: 1 / np.tan(w) - x_of(w, wZ, kind)      # noqa: E731
        try:
            if g(lo) * g(hi) < 0:
                ws.append(brentq(g, lo, hi, xtol=1e-14))
        except Exception:
            pass
    ws = np.array(ws[:N])
    # mode mass: the line's own, plus a shunt capacitor's KINETIC energy
    cn = ((ELL / 2 + np.sin(2 * ws * ELL) / (4 * ws)) / (ZTX * V)
          + c_elem * np.cos(ws * ELL) ** 2)
    out = [(w, 1.0 / (2 * np.pi * Z0 * c)) for w, c in zip(ws, cn)]
    if kind == 'C':
        # a shunt C is an open at DC, so the free mode survives
        c0 = ELL / (ZTX * V) + c_elem
        out.insert(0, (0.0, 1.0 / (2 * np.pi * Z0 * c0)))
    return out


def graph_s11(wZ, kind, N, w_nat):
    """S11 of the loaded comb through the ordinary hub pipeline."""
    nodes, atts = [], []
    for i, (w, gam) in enumerate(loaded_modes(wZ, kind, N)):
        for sgn in ((+1,) if w == 0.0 else (+1, -1)):
            nid = f"m{i}{'p' if sgn > 0 else 'n'}"
            nodes.append({'node_id': nid, 'label': nid, 'pos': (i, 0),
                          'conj': False, 'freq': sgn * w / (2 * np.pi),
                          'B_int': 0.0, 'B_ext': None})
            atts.append((nid, float(np.sqrt(gam)), 0.0))     # u_n(0) = +1
    assign = {id(n): {'freq': n['freq'], 'B_int': 0.0, 'B_ext': None}
              for n in nodes}
    f = w_nat / (2 * np.pi)
    ext = autograph.GraphExtractor()
    ext.extract_graph_data(
        nodes=nodes, edges=[], scattering_assignments=assign,
        frequency_settings={'start': float(f[0]), 'stop': float(f[-1]),
                            'points': len(f)},
        root_node_id=nodes[0]['node_id'],
        hubs=[{'hub_id': 'P', 'label': 'P', 'monitored': True,
               'attachments': atts}])
    return autograph.GraphScatteringMatrix(ext, f).S[:, 0, 0]


def exact_s11(wZ, kind, w_nat):
    return np.array([core.s11(core.zin_from_abcd(
        core.abcd_line(w, ELL, ZTX, V), z_elem(w, wZ, kind)), Z0)
        for w in w_nat])


def check_condition():
    print("1. cot(kl) = X/Ztx vs the raw admittance Y_line + Y_elem:")
    for kind in ('L', 'C'):
        for wZ in (0.3 * np.pi, np.pi, 3 * np.pi):
            ws = [w for w, _ in loaded_modes(wZ, kind, 6) if w > 0]
            worst = max(abs(1.0 / (1j * ZTX / np.tan(w))
                            + 1.0 / z_elem(w, wZ, kind)) for w in ws)
            print(f"   {kind} w_Z={wZ/np.pi:4.1f}pi: max|Ytot| = {worst:.1e}")


def check_target_length():
    """Closed-form line length for a TARGET loaded resonance.

    Worked in LINEAR frequency throughout (kl = pi f / FSR), independent of
    the natural-unit helpers above:  cot(pi f/FSR) = x(f)  evaluated AT the
    target gives  FSR = pi f_t / (arccot(x(f_t)) + (n-1) pi).
    """
    def x_lin(f, fZ, kind):
        return f / fZ if kind == 'L' else -fZ / f

    def roots_lin(fsr, fZ, kind, nmax):
        out = []
        for n in range(0, nmax + 2):
            lo = (n * np.pi + 1e-12) * fsr / np.pi
            hi = ((n + 1) * np.pi - 1e-12) * fsr / np.pi
            g = lambda f: 1 / np.tan(np.pi * f / fsr) - x_lin(f, fZ, kind)  # noqa: E731
            try:
                if g(lo) * g(hi) < 0:
                    out.append(brentq(g, lo, hi, xtol=1e-13))
            except Exception:
                pass
        return out

    f_t = 6.0
    print("2. closed-form FSR so a chosen loaded mode lands on f = 6.0:")
    for kind in ('L', 'C'):
        for fZ in (1.0, 3.0, 12.0, 60.0):
            for mode in (1, 3):
                x = x_lin(f_t, fZ, kind)
                fsr = np.pi * f_t / (np.arctan2(1.0, x) + (mode - 1) * np.pi)
                got = roots_lin(fsr, fZ, kind, mode + 1)[mode - 1]
                print(f"   {kind} f_Z={fZ:5.1f} mode {mode}: FSR = {fsr:9.4f}"
                      f" -> f = {got:.6f}  (err {abs(got - f_t):.1e},"
                      f" f/FSR = {got/fsr:.4f})")


def check_abcd():
    w_nat = np.linspace(0.3 * np.pi, 6.7 * np.pi, 400)
    print("3. loaded comb vs exact ABCD (complex S11, matched-ish port):")
    for kind, wZ in (('L', np.pi), ('L', 0.3 * np.pi), ('C', np.pi)):
        errs = [np.max(np.abs(graph_s11(wZ, kind, N, w_nat)
                              - exact_s11(wZ, kind, w_nat)))
                for N in (10, 20, 40, 80)]
        ratios = " ".join(f"{a/b:.2f}" for a, b in zip(errs, errs[1:]))
        print(f"   {kind} w_Z={wZ/np.pi:4.1f}pi: "
              + " ".join(f"N={N}:{e:.3e}" for N, e in zip((10, 20, 40, 80), errs))
              + f"   ratios {ratios}")
    print("   inductive ~2x per doubling (1/N, the truncated tail);")
    print("   capacitive PLATEAUS -> an unresolved direct term (see 7.5).")


if __name__ == "__main__":
    check_condition()
    check_target_length()
    check_abcd()
