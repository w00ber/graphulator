"""M2a vs legacy on the pumped files (design note step4_msuper_m2.md, gate 5:
reported, not gated).

For each pumped M2a file, on its own sweep:
- legacy (comb + twin, tail closure on) at the stored f_max, and at 2x / 4x
  f_max (more comb pairs, so more pump couplings);
- M2a at the window {-1..0} (legacy's two sectors) and at the auto window.

Columns: max_f |S_legacy - S_M2a| over the sector-0 reflection, and the peak
|S|^2 in dB. Reading: the legacy -> M2a{-1..0} gap that shrinks as f_max
grows is the dropped pump-tail couplings (legacy pumps only comb pairs; its
tail closure covers the port, not the pump). What is left at large f_max is
what the comb never has: for an unloaded line, the DC (n = 0) mode, which
the legacy pump does not couple (tap_couplings excludes n = 0). The
M2a{-1..0} -> M2a{auto} gap is the window.

Run:  python misc/msuper_M2a_vs_legacy.py > misc/msuper_M2a_vs_legacy.out
"""
import copy
import glob
import os

import numpy as np

from graphulator import engine
from graphulator import model as M
from graphulator.model.legacy_job import compile_jobs, compute_job

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = {os.path.basename(f): f for f in
         glob.glob(os.path.join(ROOT, "examples", "**", "*.pgraph"), recursive=True)}


def legacy(doc, f, scale):
    d = copy.deepcopy(doc)
    for k, v in d.solve.kept_poles.items():
        v["f_max"] = v["f_max"] * scale
    (job,) = compile_jobs(d, f)
    res = compute_job(job)
    return res["S"][:, 0, 0]


def dB(S):
    return 10 * np.log10(np.max(np.abs(S) ** 2))


def main():
    names = []
    for k in sorted(FILES):
        doc = M.load(FILES[k])
        try:
            if engine.classify(doc) == "network" and doc.pumped:
                names.append(k)
        except engine.NotSupportedError:
            pass
    print("max_f |S11_legacy(f_max x s) - S11_M2a(legacy's two sectors)|, peak |S11|^2 [dB]")
    print("two sectors = {-1..0}, or {0..1} for an up-conversion anchor (legacy twin at f + f_p)")
    print("f_worst: where the x4 residual peaks; f_p: the pump; DC: the line has a free DC mode")
    print(f"{'file':40s} {'x1':>9s} {'x2':>9s} {'x4':>9s} {'f_worst':>8s} {'f_p':>6s}  "
          f"{'leg x1':>8s} {'2 sect':>8s} {'auto':>8s} window  DC")
    for k in names:
        doc = M.load(FILES[k])
        (ra,) = engine.solve(doc)
        f = ra.f
        doc2 = M.load(FILES[k])
        _, info = engine.pump_depth(doc, doc.pumped[0])
        win = [0, 1] if info["family"] == "up-conversion" else [-1, 0]   # legacy's twin frame
        doc2.solve.sectors = win
        (r2,) = engine.solve(doc2, f)
        S2 = r2.S[:, 0, 0]
        row, leg1 = [], None
        for s in (1, 2, 4):
            L = legacy(doc, f, s)
            leg1 = L if s == 1 else leg1
            row.append(np.nanmax(np.abs(L - S2)))
            if s == 4:
                f_worst = f[np.nanargmax(np.abs(L - S2))]
        loaded = any(b.type == "L" for b in doc.blocks)
        print(f"{k[:40]:40s} " + " ".join(f"{x:9.2e}" for x in row)
              + f" {f_worst:8.4f} {ra.f_p:6.3f}  {dB(leg1):8.3f} {dB(S2):8.3f} {dB(ra.S[:, 0, 0]):8.3f} "
              f"{ra.sectors[0]}..{ra.sectors[-1]}  {'no (L load)' if loaded else 'yes'}")


if __name__ == "__main__":
    main()
