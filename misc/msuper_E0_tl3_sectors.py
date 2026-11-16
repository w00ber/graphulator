"""E0 -- TL_3 sector-convergence check (HANDOFF sec. 4).

Question: the pumped-line macro (signal comb + conjugate twin) keeps two
frequency sectors, omega and omega - omega_p. How far is that from the
converged multi-sector answer for the TL_3 example?

ORACLE (independent of the app and of any comb):
  nodal harmonic balance on the exact circuit, any sector window.
  Circuit: open-open uniform line (Ztx, length ell), x = 0 end to ground
  through an inductor with 1/L(t) = 1/L0 + delta*cos(omega_p t + phi)
  (TL_3: 1/L0 = 0, no static load), x = ell end on a resistive port Z0.
  Each sector m has omega_m = omega + m*omega_p; the line enters by its
  exact 2x2 Y-matrix at omega_m (no modes, no truncation), the port by 1/Z0,
  and sectors couple only through the modulated inductor.
  Time convention of this script: e^{-i omega t}, so V = -i omega Phi,
  Y_line = (1/Ztx) [[ i cot t, -i csc t], [-i csc t, i cot t]], t = omega ell / v.

  NOT immsuper.py: that file lives on JA's machine and was not reachable
  from this session. This is a from-scratch equivalent of the same idea;
  it is gated below against tests/cmtline_core.hb_signal_idler (the repo's
  two-sector oracle, comb + tail tanks) before being trusted.

RATE CONVERSION (docs/pumped_line_termination.md sec. 6, pinned):
  natural units v = ell = Ztx = 1, omega_n = n pi, C_n = 1/2,
  g_nm = delta u_n u_m / (4 sqrt(omega_n C_n omega_m C_m)),
  rate = (2 FSR / pi) g_nm at the anchor pair (n_ref, m_ref).
  TL_3: n_ref = m_ref = 3, u_3(0) = 1  =>  delta = 3 pi^2 rate / FSR.
  Frequencies: omega_nat = pi f / FSR.

Run:  QT_QPA_PLATFORM=offscreen python misc/msuper_E0_tl3_sectors.py
Output: misc/msuper_E0_tl3_sectors.out (this script's stdout).
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "src"))
PGRAPH = os.path.join(ROOT, "examples", "pgraphs",
                      "TL_3_PUMPED_TERMINATION_AMPLIFIER.pgraph")


# ---------------------------------------------------------------------------
# oracle
# ---------------------------------------------------------------------------

def y_line(w, Ztx=1.0, ell=1.0, v=1.0):
    t = w * ell / v
    c, s = np.cos(t) / np.sin(t), 1.0 / np.sin(t)
    return (1.0 / Ztx) * np.array([[1j * c, -1j * s], [-1j * s, 1j * c]])


def hb_sectors(ws, wp, delta, msect, Z0, invL0=0.0, phi=0.0, Ztx=1.0):
    """Multi-sector nodal HB. Returns dict m -> b_m/a (power-wave S, port
    reflection/conversion from sector 0 into sector m), shape (len(ws),).
    Node 0 = pumped end (x = 0), node 1 = port end (x = ell)."""
    msect = list(msect)
    assert 0 in msect
    K = len(msect)
    idx = {m: k for k, m in enumerate(msect)}
    out = {m: np.empty(len(ws), complex) for m in msect}
    for i, w in enumerate(ws):
        A = np.zeros((2 * K, 2 * K), complex)
        rhs = np.zeros(2 * K, complex)
        for m in msect:
            wm = w + m * wp
            r = 2 * idx[m]
            A[r:r + 2, r:r + 2] += y_line(wm, Ztx)
            A[r + 1, r + 1] += 1.0 / Z0
            # static inductor at node 0: I = Phi/L0 = (i/wm) V / L0
            A[r, r] += invL0 * 1j / wm
            # modulated part: I_m = (d/2)[e^{-i phi} Phi_{m-1} + e^{+i phi} Phi_{m+1}]
            for dm, ph in ((-1, np.exp(-1j * phi)), (+1, np.exp(1j * phi))):
                if m + dm in idx:
                    c = 2 * idx[m + dm]
                    wk = w + (m + dm) * wp
                    A[r, c] += 0.5 * delta * ph * 1j / wk
        a = 1.0
        rhs[2 * idx[0] + 1] = 2 * a / np.sqrt(Z0)
        V = np.linalg.solve(A, rhs)
        for m in msect:
            b = V[2 * idx[m] + 1] / np.sqrt(Z0) - (a if m == 0 else 0.0)
            out[m][i] = b / a
    return out


def window(n_lo, n_hi):
    return list(range(n_lo, n_hi + 1))


# ---------------------------------------------------------------------------
# gate 1: oracle vs tests/cmtline_core.hb_signal_idler at two sectors
# ---------------------------------------------------------------------------

def gate_vs_cmtline_core():
    import cmtline_core as core
    print("GATE 1: this oracle at sectors {0,-1} vs cmtline_core.hb_signal_idler")
    print("  (comb N + 2 tail tanks, LJ = 1e4 static, Cd = 1e-8; same circuit as")
    print("   test_pump_rate_normalization_matches_oracle). Residual should fall with N.")
    Z0, dK, LJ = 10.0, 1.0, 1e4
    wp = 6 * np.pi
    ws = np.linspace(2.8 * np.pi, 3.2 * np.pi, 81) + 1.234e-6
    mine = hb_sectors(ws, wp, dK, [0, -1], Z0, invL0=1.0 / LJ)
    # cmtline_core's S_is is the conjugated idler; compare |.|
    for N in (12, 48, 192):
        Cm, Km, Rm, P, f = core.build_galvanic(N, LJ, 1e-8)
        Sss, Sis = core.hb_signal_idler(ws, wp, dK * LJ, Cm, Km, Rm, P, f, Z0)
        e1 = np.max(np.abs(mine[0] - Sss))
        e2 = np.max(np.abs(np.abs(mine[-1]) - np.abs(Sis)))
        print(f"  N={N:4d}: max|dS_ss| = {e1:.2e}   max|d|S_is|| = {e2:.2e}")
    G = np.abs(mine[0]) ** 2
    print(f"  oracle peak |S_ss|^2 = {G.max():.4f} ({10*np.log10(G.max()):.2f} dB)")
    # Manley-Rowe at two sectors, photon-flux (w_i = w_p - w_s > 0 here)
    wi = np.abs(ws - wp)
    mr = np.abs(mine[0]) ** 2 - (ws / wi) * np.abs(mine[-1]) ** 2 - 1.0
    print(f"  two-sector Manley-Rowe residual {np.max(np.abs(mr)):.1e}")
    print()


def flux_audit(ws, wp, S, msect):
    """sum_m sgn(w_m) |S^ph_m0|^2 - 1 = 0 for a lossless, stable pumped
    network (photon-number weighted by sign of frequency). Power-wave b/a
    -> photon flux: |S^ph_m0|^2 = |S_m0|^2 * w / |w_m|."""
    tot = np.zeros(len(ws))
    for m in msect:
        wm = ws + m * wp
        tot += np.sign(wm) * np.abs(S[m]) ** 2 * ws / np.abs(wm)
    return np.max(np.abs(tot - 1.0))


# ---------------------------------------------------------------------------
# the app's number for TL_3 (GUI payload -> _compute_sparams_job)
# ---------------------------------------------------------------------------

_WIN = None


def app_window():
    global _WIN
    if _WIN is None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")
        from PySide6.QtWidgets import QApplication
        _app = QApplication.instance() or QApplication([])
        import graphulator.graphulator_para as gp
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            win = gp.Graphulator()
            win._open_graph_file(PGRAPH)
        _WIN = (gp, win, _app)
    return _WIN


def app_S(f, rate=None, tail=True):
    gp, win, _ = app_window()
    line = next(l for l in win.line_resonators if l.get('pump'))
    if rate is not None:
        line['pump']['rate'] = rate
    win.line_tail_closure = tail
    win._invalidate_scattering_data()
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        comps = win._find_connected_components()
        job = win._build_sparams_job(comps[0], f, f[0], f[-1], len(f))
        job['tail_closure'] = tail
        res = gp._compute_sparams_job(job)
    lab = [res['port_dict'][p]['label'] for p in res['port_ids']]
    return res['S'], lab


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    np.set_printoptions(linewidth=140)
    gate_vs_cmtline_core()

    d = json.load(open(PGRAPH))
    line = next(l for l in d['line_resonators'] if l.get('pump'))
    FSR, Ztx, Z0p = line['FSR'], line['Ztx'], line['Z0_port']
    pump = line['pump']
    f_p, rate0, nref = pump['f_p'], pump['rate'], pump['n_ref']
    print("TL_3 parameters (from the .pgraph):")
    print(f"  FSR={FSR}  Ztx={Ztx}  Z0_port={Z0p}  f_max={line['f_max']}  "
          f"load={line['load']}  pump end={pump['end']}  f_p={f_p}  rate={rate0}  "
          f"phase={pump['phase']}  n_ref={nref}  coupling={pump['coupling']}")
    sc = d['scattering']['frequency']
    print(f"  sweep: center {sc['center']} span {sc['span']} points {sc['points']}")
    assert line['load'] is None and pump['coupling'] == 'inductive' and nref == 3
    Z0 = Z0p / Ztx
    wp = np.pi * f_p / FSR
    to_delta = 3 * np.pi ** 2 / FSR          # delta = to_delta * rate (anchor (3,3))
    print(f"  natural units: Z0/Ztx = {Z0:.6f}, omega_p = {wp/np.pi:.3f} pi,"
          f" delta = 3 pi^2 rate / FSR = {to_delta:.6f} * rate")
    print()

    # frequency grid: the example's own sweep, nudged off the line poles
    # (f = n FSR is a pole of the open-open Y-matrix)
    f = np.linspace(sc['center'] - sc['span'] / 2, sc['center'] + sc['span'] / 2,
                    sc['points']) + 1.234e-7
    ws = np.pi * f / FSR

    # -- gate 2: two-sector oracle vs the app at the example's rate ---------
    print("GATE 2: two-sector oracle {0,-1} vs the app (TL_3 as shipped)")
    S2 = hb_sectors(ws, wp, to_delta * rate0, [0, -1], Z0)
    for tail in (True, False):
        S_app, lab = app_S(f, rate0, tail=tail)
        s = lab.index('TL')
        Ga = np.abs(S_app[:, s, s]) ** 2
        G2 = np.abs(S2[0]) ** 2
        print(f"  tail closure {'on ' if tail else 'off'}: app peak "
              f"{10*np.log10(Ga.max()):.3f} dB @ f={f[Ga.argmax()]:.4f};"
              f" oracle {10*np.log10(G2.max()):.3f} dB @ f={f[G2.argmax()]:.4f};"
              f" max|d|S_ss|^2|/max = {np.max(np.abs(Ga-G2))/G2.max():.2e}")
    print()

    # -- rate scan per window ---------------------------------------------
    wins = [(0, -1), (-2, 1), (-3, 2), (-4, 3), (-6, 5)]
    fine = np.linspace(3.0, 6.0, 3001) + 1.234e-7
    wfine = np.pi * fine / FSR

    def peak(rate, msect, wgrid=wfine, fgrid=fine):
        S = hb_sectors(wgrid, wp, to_delta * rate, msect, Z0)
        G = np.abs(S[0]) ** 2
        k = G.argmax()
        return G[k], fgrid[k], S

    rates = [rate0, 0.1, 0.2, 0.4, 0.8, 1.6, 3.2]
    print("TABLE: peak |S_ss|^2 over f in [3,6] (3001 pts), dB @ f, vs sector window")
    print("  (mirror-symmetric windows m <-> -1-m).  'app' = shipped macro, tail closure on.")
    print("  eps_33 = 2 rate / f_3 = delta L/L_tot at the anchor pair.")
    hdr = "  rate   eps33 " + "".join(f"{'{'+str(min(a,b))+'..'+str(max(a,b))+'}':>17s}"
                                 for a, b in wins) + f"{'app':>17s}"
    print(hdr)
    peaks = {}
    for r in rates:
        row = f"  {r:5.2f} {2*r/4.5:6.3f}"
        for lo, hi in wins:
            ms = window(min(lo, hi), max(lo, hi))
            G, fpk, _ = peak(r, ms)
            peaks[(r, lo)] = G
            row += f"{10*np.log10(G):8.2f} @{fpk:6.3f}"
        S_app, lab = app_S(fine, r, tail=True)
        s = lab.index('TL')
        Ga = np.abs(S_app[:, s, s]) ** 2
        peaks[(r, 'app')] = Ga.max()
        row += f"{10*np.log10(Ga.max()):8.2f} @{fine[Ga.argmax()]:6.3f}"
        print(row, flush=True)
    print()
    print("  excess gain (G_peak - 1): two-sector and app relative to widest window")
    for r in rates:
        ref = peaks[(r, -6)] - 1
        print(f"  rate {r:5.2f}: G-1 converged {ref:.4e};  two-sector/conv = "
              f"{(peaks[(r, 0)]-1)/ref:.3f};  app/conv = {(peaks[(r, 'app')]-1)/ref:.3f};"
              f"  {{-4..3}}/{{-6..5}} = {(peaks[(r, -4)]-1)/ref:.6f}")
    print()

    # -- where the two-sector model and the converged one part ways -------
    print("FINE SCAN, rate 0.70..1.60 (f in [3,6], 3001 pts): peak dB @ f")
    print("  converged gain should grow monotonically; a peak that rises and then")
    print("  FALLS with rate is a pole crossing the real axis (instability) [inferred")
    print("  from the lineshape, not from an argument-principle count].")
    print(f"  {'rate':>5s}{'{-1..0}':>17s}{'{-6..5}':>17s}{'{-8..7}':>17s}")
    for r in np.round(np.arange(0.70, 1.61, 0.1), 2):
        row = f"  {r:5.2f}"
        for ms in ([-1, 0], window(-6, 5), window(-8, 7)):
            G, fpk, _ = peak(r, ms)
            row += f"{10*np.log10(G):8.2f} @{fpk:6.3f}"
        print(row, flush=True)
    print()

    # -- audit: photon-flux conservation in the widest window --------------
    print("AUDIT: sum_m sgn(w_m)|S^ph_m0|^2 - 1 (lossless => 0) per window, at rate0")
    for lo, hi in wins:
        ms = window(min(lo, hi), max(lo, hi))
        S = hb_sectors(ws, wp, to_delta * rate0, ms, Z0)
        print(f"  {ms[0]}..{ms[-1]}: {flux_audit(ws, wp, S, ms):.1e}")
    print()

    # -- where does the extra weight go: |S_m0|^2 by sector at the peak -----
    lo, hi = wins[-1]
    ms = window(min(lo, hi), max(lo, hi))
    for r in rates:
        G, fpk, _ = peak(r, ms)
        S = hb_sectors(np.array([np.pi * fpk / FSR]), wp, to_delta * r, ms, Z0)
        w0 = np.pi * fpk / FSR
        parts = "  ".join(f"m={m}:{np.abs(S[m][0])**2 * w0/abs(w0+m*wp):.2e}"
                          for m in ms)
        print(f"  rate {r:.4f} @f={fpk:.4f}, photon-flux |S_m0|^2: {parts}")


if __name__ == "__main__":
    main()
