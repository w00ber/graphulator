"""M2c groundwork (design note step4_msuper_m2.md, D3): what a capacitive tap
is, seen from the line-end plane, and what a rate alone can carry.

Exact circuit (the cmtline_core build_capacitive topology, physical units,
e^{-i w t}): TL_2's line (FSR 1.5, Ztx 65, x0 open, xL on a 50 ohm port);
a lossless tank (Cd, Ld) tapped at x0 through Cc. The tank seen from x0:

    Y_tap = -i w Cs + i w w1^2 Cb / (w^2 - w1^2),   Cs = Cc Cd/(Cc+Cd), Cb = Cc^2/(Cc+Cd),
    w1 = 1 / sqrt(Ld (Cd + Cc))

i.e. a shunt capacitor Cs plus a Foster pole PAIR (+-w1, equal residues): a
series-LC branch. It is admittance-type: open off resonance. Its leak rate
into Z_ref (decision D3) is gamma = Z_ref w1^2 Cb / (2 pi) [GHz], and the
pole pair is fixed by (f1, gamma) alone. Cs is not: at fixed gamma,
Cc = sqrt(gamma 2 pi Cd' / Z_ref)/w1 grows with the device capacitance, i.e.
falls with the device impedance Z_d = sqrt(Ld/Cd).

Models compared with the exact circuit at the same (f1, gamma):
  A  one RWA pole:        y = (i/2) gamma / (f - f1)
  B  the pole pair:       y = (i/2) gamma [1/(f - f1) + 1/(f + f1)]
  C  B + the exact Cs     (needs Z_d: an element value)
  z  the M2b block form:  z = (i/2) gamma / (f - f1)   (impedance-type)
  legacy: TL_2 with the port attachment removed (comb + tap profile).

gamma here is set from legacy's anchor (rate 0.05 at n_ref = 3, u = 1 at x0):
gamma = rate^2 2 pi Z_ref C_3, the rate that gives legacy's splitting with
mode 3 at resonance.

Run: python misc/msuper_M2c_tap_physics.py > misc/msuper_M2c_tap_physics.out
"""
import copy
import os

import numpy as np

from graphulator import model as M
from graphulator.model.legacy_job import compile_jobs, compute_job

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FSR, ZTX, Z0, ZR, F1 = 1.5, 65.0, 50.0, 50.0, 4.4


def y_line(f):
    t = np.pi * f / FSR
    A = D = np.cos(t)
    B = -1j * ZTX * np.sin(t)
    return np.array([[D / B, -1 / B], [-1 / B, A / B]])


def s11(f, y_x0):
    """Port at xL, shunt admittance Y(f) [S] at x0."""
    out = np.empty(len(f), complex)
    for i, x in enumerate(f):
        Y = y_line(x)
        Y[0, 0] += y_x0(x)
        Y[1, 1] += 1 / Z0
        V = np.linalg.solve(Y, [0, 2 / np.sqrt(Z0)])
        out[i] = V[1] / np.sqrt(Z0) - 1
    return out


def exact(Zd, gamma):
    """(Y_tap(f), Cs) of the exact circuit with pole at F1 and rate gamma."""
    w1 = 2 * np.pi * F1
    Cb = gamma * 2 * np.pi / (ZR * w1 ** 2)
    # Cb = Cc^2/(Cc+Cd), Ld = Zd^2 Cd (Zd: the bare tank's impedance),
    # w1^2 Ld (Cd + Cc) = 1: bisect on Cd (the residual is monotone)
    def cc(Cd):
        return 0.5 * (Cb + np.sqrt(Cb ** 2 + 4 * Cb * Cd))
    lo, hi = 1e-30, 1.0
    for _ in range(400):
        mid = np.sqrt(lo * hi)
        if w1 ** 2 * Zd ** 2 * mid * (mid + cc(mid)) > 1:
            hi = mid
        else:
            lo = mid
    Cd = np.sqrt(lo * hi)
    Cc = cc(Cd)
    Ld = Zd ** 2 * Cd
    Cs = Cc * Cd / (Cc + Cd)

    def Y(f):
        w = 2 * np.pi * f
        Yt = -1j * w * Cd + 1j / (w * Ld)
        Yc = -1j * w * Cc
        return Yt * Yc / (Yt + Yc)
    return Y, Cs, Cc, Cd


def f_res(f, S, S0):
    """Where the tap's feature is centred: max |S - S_no_tap| (a phase flip)."""
    return f[np.argmax(np.abs(S - S0))]


def main():
    C3 = 1 / (4 * ZTX * FSR)
    gamma = 0.05 ** 2 * 2 * np.pi * ZR * C3
    print(f"gamma (leak rate into Z_ref = 50 ohm) = {gamma:.6e} GHz  (legacy rate 0.05 at n_ref 3)")
    f = np.linspace(3.0, 6.0, 30001) + 1.234e-7
    band = np.abs(f - F1) < 0.05
    yA = lambda x: (0.5j * gamma / (x - F1)) / ZR                       # noqa: E731
    yB = lambda x: (0.5j * gamma * (1 / (x - F1) + 1 / (x + F1))) / ZR   # noqa: E731
    SA, SB = s11(f, yA), s11(f, yB)
    S0 = s11(f, lambda x: 0.0)
    # M2b's impedance form on the same plane: Y = 1 / (Z_ref z)
    Sz = s11(f, lambda x: (x - F1) / (ZR * 0.5j * gamma))
    print(f"tap effect max|S_exact - S_no_tap|, and model errors max|S_model - S_exact|, "
          f"over 3..6 GHz [and within 50 MHz of f1]")
    print(f"{'Z_d [ohm]':>10s} {'Cc [nF]':>9s} {'Cs w1 Zr':>9s} {'effect':>16s} "
          f"{'A (RWA)':>16s} {'B (pair)':>16s} {'C (pair+Cs)':>16s} {'z (M2b)':>8s}")
    for Zd in (5.0, 25.0, 125.0, 625.0, 3125.0):
        Y, Cs, Cc, Cd = exact(Zd, gamma)
        SE = s11(f, Y)
        SC = s11(f, lambda x: yB(x) - 1j * 2 * np.pi * x * Cs)
        row = [Zd, Cc, Cs * 2 * np.pi * F1 * ZR]
        e = lambda S: (np.max(np.abs(S - SE)), np.max(np.abs(S - SE)[band]))  # noqa: E731
        cells = " ".join(f"{a:7.1e} [{b:6.1e}]" for a, b in
                         (e(S0), e(SA), e(SB), e(SC)))
        print(f"{Zd:10.0f} {Cc:9.2e} {row[2]:9.2e} {cells} {np.max(np.abs(Sz - SE)):8.2f}"
              f"   f_res exact {f_res(f, SE, S0):.4f}")

    # legacy, the same circuit (TL_2 without its direct port attachment)
    doc = M.load(os.path.join(ROOT, "examples", "pgraphs", "TL_2_MODE_TAPPED_ONTO_A_LINE.pgraph"))
    d = copy.deepcopy(doc)
    d.attachments = [a for a in d.attachments if a.plane != "port1"]
    d.planes = [p for p in d.planes if p.id != "port1"]
    d.drawing.ports.pop("port1", None)
    d.drawing.order["ports"] = [x for x in d.drawing.order.get("ports", []) if x != 1]
    for scale in (1, 4):
        dd = copy.deepcopy(d)
        dd.solve.kept_poles["line0"]["f_max"] *= scale
        res = [compute_job(j) for j in compile_jobs(dd, f)]
        (L,) = [r for r in res if r is not None]
        k = [L["port_dict"][p]["label"] for p in L["port_ids"]].index("TL")
        SL = L["S"][:, k, k]
        Y, *_ = exact(3125.0, gamma)
        SE = s11(f, Y)
        print(f"legacy f_max x{scale}: max|S_legacy - S_B| = {np.max(np.abs(SL - SB)):.2e},"
              f" f_res legacy {f_res(f, SL, S0):.4f} (B: {f_res(f, SB, S0):.4f}, "
              f"A: {f_res(f, SA, S0):.4f})")
    print(f"reference: max|S_B - S_A| = {np.max(np.abs(SB - SA)):.2e} "
          f"(the counter-rotating partner)")


if __name__ == "__main__":
    main()
