"""E0 cross-check against JA's immsuper.py oracle.

Independent re-computation of misc/msuper_E0_tl3_sectors.out (TABLE + FINE SCAN)
using immsuper.py (CMT-Theory repo: claude/project_export/claude/immsuper.py) for
the line Y-matrix, port, sector bookkeeping, HB assembly and S extraction.

Circuit (TL_3_PUMPED_TERMINATION_AMPLIFIER.pgraph), PHYSICAL units:
  node 0 = x=0 end, node 1 = x=ell end.
  Line(0, 1, Z=65 ohm, theta(w) = w / (2 FSR))   -> f_n = n FSR = 1.5 n
  Port(1, Z0 = 50 ohm)
  x=0 end to ground through an inductor with 1/L(t) = delta_phys cos(wP t),
  wP = 2 pi * 9, ZERO static inverse inductance.

PUMP ELEMENT.  immsuper.PumpL(node, L0, eps) is L(t) = L0 (1 + eps cos wP t), and
its HB block is  Y = inv(-i diag(w_m) L0 T),  T = I + (eps/2)(shift_up + shift_dn),
i.e.  Y = Gamma_mat . diag(i/w_m)  with  Gamma_mat = (L0 T)^{-1}  -- the inverse of
the TRUNCATED L matrix.  TL_3 has <1/L> = 0 (L0 = infinity), which PumpL cannot
express.  So we add PumpGamma(node, gammas): 1/L(t) = sum_n Gamma_n cos(n wP t)
(gammas[0] = static 1/L), with  Gamma_mat[a,b] = Gamma_{|a-b|} (x1/2 for n>=1),
Y = Gamma_mat . diag(i/w_m), injected exactly as immsuper itself injects PumpSquid
(patch of Network.YHB).  This is the TRUNCATED-1/L convention, the one E0 uses.
Section 0 below checks PumpGamma (full Fourier series of 1/L) against native
PumpL: the two truncation conventions must converge to each other as the window
grows (they differ at finite window by construction).

CONVERSION natural -> physical (E0 uses v = ell = Ztx = 1):
  w_nat = pi f / FSR,  w_phys = 2 pi f  =>  w_phys = 2 FSR w_nat
  Y_phys = Y_nat / Ztx, and Y = Gamma i/w  =>  Gamma_phys = Gamma_nat * 2 FSR / Ztx
  delta_nat = 3 pi^2 rate / FSR = 19.739209 rate
  delta_phys = delta_nat * 2 FSR / Ztx = 6 pi^2 rate / Ztx   [1/H in units where f is in the pgraph's unit]

Run:  python misc/msuper_E0_immsuper_crosscheck.py
      (IMMSUPER_DIR=<dir containing immsuper.py>, default ../cmt-theory/claude/project_export/claude)
Output: misc/msuper_E0_immsuper_crosscheck.out
"""
import os
import re
import sys
from dataclasses import dataclass

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
IMM = os.environ.get("IMMSUPER_DIR", os.path.join(
    os.path.dirname(ROOT), "cmt-theory", "claude", "project_export", "claude"))
sys.path.insert(0, IMM)
import immsuper as im  # noqa: E402

sys.path.insert(0, HERE)
import msuper_E0_tl3_sectors as E0  # noqa: E402  (only for the direct S-vector comparison)


# ---------------------------------------------------------------------------
# PumpGamma: 1/L(t) modulation, injected the way immsuper injects PumpSquid
# ---------------------------------------------------------------------------
@dataclass
class PumpGamma:
    node: int
    gammas: tuple   # (Gamma_0, Gamma_1, Gamma_2, ...): 1/L(t) = G0 + sum G_n cos(n wP t)


_prev_YHB = im.Network.YHB


def _YHB(self, ws, wP, MSET):
    Y, wm = _prev_YHB(self, ws, wP, MSET)
    N, ns = self.nnodes, len(wm)
    for e in self.elements:
        if isinstance(e, PumpGamma):
            G = np.zeros((ns, ns), complex)
            for n, g in enumerate(e.gammas):
                if n == 0:
                    G += g * np.eye(ns)
                elif n < ns:
                    G += (g / 2) * (np.eye(ns, k=n) + np.eye(ns, k=-n))
            YL = G @ np.diag(1j / wm)          # I = Gamma(t) phi, phi_m = V_m / (-i w_m)
            for a in range(ns):
                for b in range(ns):
                    Y[a * N + e.node, b * N + e.node] += YL[a, b]
    return Y, wm


im.Network.YHB = _YHB

# ---------------------------------------------------------------------------
FSR, ZTX, Z0P, FP = 1.5, 65.0, 50.0, 9.0
WP = 2 * np.pi * FP


def to_dphys(rate):
    return 6 * np.pi ** 2 * rate / ZTX


def tl3(rate):
    net = im.Network(2)
    net.add(im.Line(0, 1, ZTX, lambda w: w / (2 * FSR)),
            PumpGamma(0, (0.0, to_dphys(rate))),
            im.Port(1, Z0P))
    return net


def sss(net, f, MSET):
    k0 = list(MSET).index(0)
    out = np.empty(len(f), complex)
    for i, fi in enumerate(f):
        S, chans, wm = net.S(2 * np.pi * fi, WP, MSET)
        out[i] = S[k0, k0]
    return out


def peak(rate, MSET, f):
    G = np.abs(sss(tl3(rate), f, MSET)) ** 2
    k = G.argmax()
    return G[k], f[k]


def win(lo, hi):
    return list(range(lo, hi + 1))


def parse_E0_out():
    txt = open(os.path.join(HERE, "msuper_E0_tl3_sectors.out")).read()
    table, fine = {}, {}
    sec = txt.split("TABLE:")[1].split("excess gain")[0]
    for line in sec.splitlines():
        m = re.match(r"\s+(\d\.\d\d)\s+\d\.\d+\s+(.*)", line)
        if m:
            vals = re.findall(r"(-?\d+\.\d+) @\s*(\d\.\d+)", m.group(2))
            table[float(m.group(1))] = [(float(a), float(b)) for a, b in vals]
    sec = txt.split("FINE SCAN")[1].split("AUDIT")[0]
    for line in sec.splitlines():
        m = re.match(r"\s+(\d\.\d\d)\s+(-?\d+\.\d+ @.*)", line)
        if m:
            vals = re.findall(r"(-?\d+\.\d+) @\s*(\d\.\d+)", m.group(2))
            fine[float(m.group(1))] = [(float(a), float(b)) for a, b in vals]
    return table, fine


def main():
    print(f"immsuper.py from: {os.path.relpath(IMM, ROOT)}")
    print(f"delta_phys = 6 pi^2 rate / Ztx = {6*np.pi**2/ZTX:.9f} * rate"
          f"   (delta_nat = {3*np.pi**2/FSR:.6f} * rate)")
    print()

    # -- 0. PumpGamma vs native PumpL (finite L0, generic circuit) -------------
    print("SECTION 0: PumpGamma (truncated-1/L) vs native immsuper.PumpL (truncated-L)")
    print("  same line+port, L0 = 2 nH-equivalent shunt at x=0, eps = 0.1; 1/L(t) Fourier series")
    print("  1/(L0(1+eps cos)) = (1/(L0 s))[1 + 2 sum (-r)^n cos n], s = sqrt(1-eps^2), r = (1-s)/eps.")
    print("  max|dS_ss| over f in [3,6] (301 pts) should fall with window size:")
    L0, eps = 2.0 / (2 * np.pi * 4.5) * ZTX, 0.1   # |Z_L| ~ 2 Ztx at mid-band
    s = np.sqrt(1 - eps ** 2); r = (1 - s) / eps
    gam = tuple([1 / (L0 * s)] + [2 * (-r) ** n / (L0 * s) for n in range(1, 30)])
    fg = np.linspace(3, 6, 301) + 1.234e-7
    for lo, hi in ((-1, 0), (-2, 1), (-4, 3), (-6, 5), (-8, 7)):
        ms = win(lo, hi)
        nL = im.Network(2).add(im.Line(0, 1, ZTX, lambda w: w / (2 * FSR)),
                               im.PumpL(0, L0, eps), im.Port(1, Z0P))
        nG = im.Network(2).add(im.Line(0, 1, ZTX, lambda w: w / (2 * FSR)),
                               PumpGamma(0, gam), im.Port(1, Z0P))
        d = np.max(np.abs(sss(nL, fg, ms) - sss(nG, fg, ms)))
        print(f"  {{{lo}..{hi}}}: {d:.2e}")
    print()

    # -- 1. full S-vector agreement with the E0 oracle ------------------------
    print("SECTION 1: immsuper(+PumpGamma) S_ss vs E0 hb_sectors, full grid f in [3,6] (3001 pts)")
    print("  max |dS_ss| / max |S_ss|: all points / excluding |f - n FSR| < 1e-3")
    print("  (at f = n FSR + 1.234e-7, sin(theta) ~ 2.6e-7, so the line Y-matrix ~ 4e6:")
    print("   rounding there is amplified by ~1/sin(theta); this is conditioning, not physics)")
    fine = np.linspace(3.0, 6.0, 3001) + 1.234e-7
    Z0n = Z0P / ZTX; wpn = np.pi * FP / FSR
    worst = worst_far = 0.0
    far = np.abs(fine / FSR - np.round(fine / FSR)) * FSR > 1e-3
    for rate in (0.05, 0.4, 0.8, 1.6):
        row = f"  rate {rate:4.2f}:"
        for lo, hi in ((-1, 0), (-2, 1), (-4, 3), (-6, 5)):
            ms = win(lo, hi)
            a = sss(tl3(rate), fine, ms)
            b = E0.hb_sectors(np.pi * fine / FSR, wpn, 3 * np.pi ** 2 * rate / FSR, ms, Z0n)[0]
            d = np.abs(a - b) / np.max(np.abs(b))
            worst = max(worst, d.max()); worst_far = max(worst_far, d[far].max())
            row += f"  {{{lo}..{hi}}} {d.max():.1e}/{d[far].max():.1e}"
        print(row, flush=True)
    print(f"  worst: {worst:.1e} (all) / {worst_far:.1e} (away from n FSR)")
    print()

    # -- 2. TABLE comparison --------------------------------------------------
    table, fs = parse_E0_out()
    cols = {(-1, 0): 0, (-2, 1): 1, (-4, 3): 3, (-6, 5): 4}   # column index in E0 TABLE
    print("SECTION 2: peak |S_ss|^2 over f in [3,6] (3001 pts), immsuper vs E0 TABLE (2-decimal dB)")
    print(f"  {'rate':>5s} {'MSET':>8s} {'immsuper dB':>14s} {'@f':>7s} {'E0 dB':>7s} {'@f':>7s}  {'G-1 (immsuper)':>15s}")
    worst_db = worst_f = 0.0
    for rate in (0.05, 0.4, 0.8, 1.6):
        for (lo, hi), c in cols.items():
            G, fpk = peak(rate, win(lo, hi), fine)
            e_db, e_f = table[rate][c]
            dB = 10 * np.log10(G)
            worst_db = max(worst_db, abs(round(dB, 2) - e_db)); worst_f = max(worst_f, abs(round(fpk, 3) - e_f))
            print(f"  {rate:5.2f} {'{'+str(lo)+'..'+str(hi)+'}':>8s} {dB:14.6f} {fpk:7.3f} {e_db:7.2f} {e_f:7.3f}  {G-1:15.6e}")
    print(f"  worst |dB (rounded) - E0| = {worst_db:.2f}; worst |df| = {worst_f:.3f}")
    print()
    for rate in (0.05, 0.4, 0.8, 1.6):
        g2 = peak(rate, win(-1, 0), fine)[0] - 1
        g12 = peak(rate, win(-6, 5), fine)[0] - 1
        print(f"  rate {rate:4.2f}: (G-1)_{{-1..0}} / (G-1)_{{-6..5}} = {g2/g12:.3f}")
    print()

    # -- 3. FINE SCAN comparison ----------------------------------------------
    print("SECTION 3: FINE SCAN rate 0.70..1.60, immsuper peak dB @ f  [E0 value in brackets]")
    print(f"  {'rate':>5s}{'{-1..0}':>30s}{'{-6..5}':>30s}{'{-8..7}':>30s}")
    worst_db = worst_f = 0.0
    for rate in np.round(np.arange(0.70, 1.61, 0.1), 2):
        row = f"  {rate:5.2f}"
        for c, ms in enumerate(([-1, 0], win(-6, 5), win(-8, 7))):
            G, fpk = peak(rate, ms, fine)
            e_db, e_f = fs[rate][c]
            dB = 10 * np.log10(G)
            worst_db = max(worst_db, abs(round(dB, 2) - e_db)); worst_f = max(worst_f, abs(round(fpk, 3) - e_f))
            row += f"  {dB:8.4f} @{fpk:6.3f} [{e_db:6.2f}@{e_f:5.3f}]"
        print(row, flush=True)
    print(f"  worst |dB (rounded) - E0| = {worst_db:.2f}; worst |df| = {worst_f:.3f}")


if __name__ == "__main__":
    main()
