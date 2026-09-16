"""Reproduce the numbers in docs/pumped_line_termination.md.

Everything here runs against the tests/cmtline_core.py oracle (exact circuit
model, no coupled-mode assumptions):

  1. the pump matrix of a line terminated in a modulated inductor is rank one;
  2. the Manley-Rowe relations hold to machine precision in the two-rung
     harmonic-balance solution, for amplification and for conversion;
  3. an inductive termination disperses the comb (cot(kl) = wL/Ztx);
  4. Schur-complementing the comb out reproduces -i Ztx cot(kl) with a ~1/N tail.

    python misc/pumped_termination_checks.py
"""
import os
import sys

import numpy as np
from scipy.optimize import brentq

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import cmtline_core as core  # noqa: E402


def rank_one_pump():
    Cm, Km, Rm, P, f = core.build_galvanic(N=8, LJ=1.0, Cd=1e-3, Ztx=1.0)
    print("1. pump-matrix rank:", np.linalg.matrix_rank(P, tol=1e-12),
          "on", P.shape)


def manley_rowe():
    N, LJ, Cd = 30, 0.5, 0.02
    Cm, Km, Rm, P, f = core.build_galvanic(N, LJ, Cd, ell=1.0, Ztx=1.0, v=1.0)
    w = np.sort(np.real(np.sqrt(np.linalg.eigvals(np.linalg.solve(Cm, Km)))))
    w = w[w > 1e-6]
    wp = w[2] + w[3]                      # non-degenerate (mode 3, mode 4) pair
    print("2. Manley-Rowe on the oracle:")
    for Z0, eps in ((1.0, 0.9), (10.0, 0.25)):
        ws = np.linspace(0.97 * w[2], 1.03 * w[2], 1001)
        Sss, Sis = core.hb_signal_idler(ws, wp, eps, Cm, Km, Rm, P, f, Z0)
        wi = wp - ws
        res = np.abs(Sss) ** 2 - 1 - (ws / wi) * np.abs(Sis) ** 2
        print(f"   amplification Z0/Ztx={Z0:4.0f} eps={eps}: "
              f"peak |S_is|^2 = {np.max(np.abs(Sis)**2):.3f}, "
              f"residual {np.max(np.abs(res)):.1e}")
    ws_c = np.linspace(wp + 0.3 * w[0], wp + 1.2 * w[1], 401)
    Sss, Sis = core.hb_signal_idler(ws_c, wp, 0.9, Cm, Km, Rm, P, f, 1.0)
    wi = wp - ws_c
    res = np.abs(Sss) ** 2 + (ws_c / np.abs(wi)) * np.abs(Sis) ** 2 - 1
    print(f"   conversion (wi<0) eps=0.9: peak |S_is|^2 = "
          f"{np.max(np.abs(Sis)**2):.3f}, residual {np.max(np.abs(res)):.1e}")


def loaded_line_dispersion():
    Ztx = 1.0
    print("3. loaded-line roots k_n l / pi  (open-open comb = n):")
    for L in (1e-3, 0.3, 1.0, 1e3):
        xs = []
        for n in range(0, 6):
            lo, hi = n * np.pi + 1e-9, (n + 1) * np.pi - 1e-9
            g = lambda x: 1 / np.tan(x) - x * L / Ztx
            if g(lo) * g(hi) < 0:
                xs.append(brentq(g, lo, hi))
        xs = np.array(xs[:4])
        print(f"   L/Ztx={L:7.3g}: " + " ".join(f"{x/np.pi:6.3f}" for x in xs)
              + "   spacings " + " ".join(f"{s/np.pi:5.3f}" for s in np.diff(xs)))


def comb_reproduces_cot():
    x = np.linspace(0.3, 11.0, 2000)
    x = x[np.abs(np.sin(x)) > 0.05]
    exact = 1 / np.tan(x)
    print("4. comb (Mittag-Leffler) vs cot(kl):")
    for N in (5, 20, 80, 320):
        n = np.arange(1, N + 1)[:, None]
        comb = 1 / x + np.sum(2 * x / (x ** 2 - (n * np.pi) ** 2), axis=0)
        print(f"   N={N:3d}: max|err| = {np.max(np.abs(comb - exact)):.2e}")


if __name__ == "__main__":
    rank_one_pump()
    manley_rowe()
    loaded_line_dispersion()
    comb_reproduces_cot()
