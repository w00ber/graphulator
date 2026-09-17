"""Where a transmission-line comb may be truncated -- and why it need not be.

Reproduces the numbers behind docs/pumped_line_termination.md section 8 and
the "Check truncation" / "close comb tail analytically" controls in the
Ports & Lines panel. Everything runs against tests/cmtline_core.py (exact
ABCD, JAA conventions). Natural units: ell = Ztx = v = 1, linear FSR = 1/2.

  1. the in-WINDOW error of the truncated comb (max |S11_graph - S11_ABCD|
     within +-FSR/2 of a chosen mode) vs N and gamma/FSR: ~ 2.5 (gamma/FSR)
     (f/FSR)/N, all of it in the phase (a lossless one-port has |S11| = 1);
  2. the analytic tail closure: kept comb + exact-minus-kept tail reproduces
     ABCD to 1e-15 at N = 2, unloaded and inductively loaded;
  3. the second-order residual the closure does NOT carry, on a pumped line
     (the tail modes' pump couplings), vs N.

    python misc/comb_truncation_checks.py
"""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

from graphulator import autograph            # noqa: E402
import cmtline_core as core                  # noqa: E402

FSR, ZTX = 0.5, 1.0


def graph_s11(N, Z0, f, closure, load=None, port_end='xL'):
    kw = dict(line_id='TL', label='TL', FSR=FSR, Ztx=ZTX, port_end=port_end,
              Z0_port=Z0, load=load)
    if load is None:
        line = autograph.LineResonator(f_max=N * FSR, **kw)
    else:
        probe = autograph.LineResonator(f_max=FSR, **kw)
        line = autograph.LineResonator(f_max=probe.mode_freq(N), **kw)
    assert line.N == N
    ext = autograph.GraphExtractor()
    ext.extract_graph_data(
        nodes=[], edges=[], scattering_assignments={},
        frequency_settings={'start': float(f[0]), 'stop': float(f[-1]),
                            'points': len(f)},
        line_resonators=[line])
    return autograph.GraphScatteringMatrix(ext, f, tail_closure=closure).S[:, 0, 0]


def in_window_error():
    print("1. truncated comb, error INSIDE a +-FSR/2 window around mode n_w")
    print("   (complex |dS11|; |S11| itself is 1 for a lossless one-port, so "
          "this is all phase = resonance position)")
    for Z0 in (50 / 65, 2.0, 10.0):
        gfsr = (2 / np.pi) * (ZTX / Z0)
        print(f"   gamma/FSR = {gfsr:.3f}")
        for n_w in (1, 3):
            f = np.linspace((n_w - 0.5) * FSR, (n_w + 0.5) * FSR, 201)
            ex = core.s11_lab_exact(2 * np.pi * f, Z0)
            Ns = [n_w + 1, n_w + 4, n_w + 16, n_w + 64]
            errs = [np.max(np.abs(graph_s11(N, Z0, f, False) - ex)) for N in Ns]
            fit = [e * N / (gfsr * n_w) for e, N in zip(errs, Ns)]
            print(f"     mode {n_w}: " + "  ".join(f"N={N}:{e:.3f}" for N, e in zip(Ns, errs))
                  + "   -> err*N/((gamma/FSR)(f/FSR)) = "
                  + " ".join(f"{c:.1f}" for c in fit))
    print("   => |dS| ~ 2.5 (gamma/FSR)(f/FSR)/N: the reactive tail "
          "-2 gamma f/(FSR^2 N) of the modes beyond N.")


def closure_is_exact():
    print("2. analytic tail closure (kept comb + exact-minus-kept tail):")
    f = np.linspace(0.31, 3.29, 300)
    w = 2 * np.pi * f
    Z0 = 50 / 65
    ex = core.s11_lab_exact(w, Z0)
    for N in (2, 4, 10):
        print(f"   open-open   N={N:2d}: closed {np.max(np.abs(graph_s11(N, Z0, f, True) - ex)):.1e}"
              f"   raw {np.max(np.abs(graph_s11(N, Z0, f, False) - ex)):.2f}")
    for f_Z in (0.5, 0.15):
        L = ZTX / (2 * np.pi * f_Z)
        exl = np.array([core.s11(core.zin_from_abcd(core.abcd_line(wi, 1, ZTX, 1),
                                                    core.Z_ind(wi, L)), Z0) for wi in w])
        load = {'end': 'xL', 'type': 'inductive', 'f_Z': f_Z}
        for N in (2, 10):
            print(f"   inductive f_Z={f_Z:4.2f} N={N:2d}: closed "
                  f"{np.max(np.abs(graph_s11(N, Z0, f, True, load, 'x0') - exl)):.1e}"
                  f"   raw {np.max(np.abs(graph_s11(N, Z0, f, False, load, 'x0') - exl)):.2f}")


def pumped_residual():
    """The closure carries the tail's port loading; a pumped line's tail
    modes ALSO carry pump couplings ~ g_n g_m, which it drops. Measure that
    residual vs N against the harmonic-balance oracle (needs the GUI macro
    to build the rank-one pump block, so this runs offscreen)."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")
    try:
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        import graphulator.graphulator_para as gp
        from graphulator import graphulator_para_config as config
        from graphulator.graphulator_para import _compute_sparams_job
    except Exception as exc:                          # pragma: no cover
        print("3. (pumped residual skipped: GUI stack unavailable:", exc, ")")
        return
    N_o, LJ, Cd, Z0, dK = 12, 1e4, 1e-8, 10.0, 1.0
    Cm, Km, Rm, P, fv = core.build_galvanic(N_o, LJ, Cd, ell=1.0, Ztx=1.0, v=1.0)
    wp = 6 * np.pi
    ws = np.linspace(2.8 * np.pi, 3.2 * np.pi, 81)
    Sss_o, _ = core.hb_signal_idler(ws, wp, dK * LJ, Cm, Km, Rm, P, fv, Z0)
    G_o = np.abs(Sss_o) ** 2
    fs = ws / np.pi
    print("3. pumped line (oracle: build_galvanic + hb_signal_idler, gain peak "
          f"{G_o.max():.2f}): relative gain error vs N")
    config.EXPLICIT_PORTS_MODE = True
    win = gp.Graphulator()
    win._apply_explicit_ports_mode()
    g = dK / (4 * np.sqrt((3 * np.pi * 0.5) ** 2))
    for N in (4, 6, 8, 12):
        win.ports, win.line_resonators = [], []
        line = win.add_line_resonator(label='TL', pos=(0, 0), FSR=1.0, Ztx=1.0,
                                      f_max=N + 0.4, port_end='xL', Z0_port=Z0)
        win.set_line_pump(line, 'x0', f_p=6.0, rate=2 * g / np.pi, n_ref=3)
        comps = win._find_connected_components()
        out = []
        for closure in (True, False):
            win.line_tail_closure = closure
            res = _compute_sparams_job(win._build_sparams_job(
                comps[0], fs, fs[0], fs[-1], len(fs)))
            lab = [res['port_dict'][p]['label'] for p in res['port_ids']]
            G = np.abs(res['S'][:, lab.index('TL'), lab.index('TL')]) ** 2
            out.append(np.max(np.abs(G - G_o)) / G_o.max())
        print(f"   N={N:2d}: closed {out[0]:.2e}   raw {out[1]:.2e}")
    print("   the closed residual is the tail modes' PUMP coupling (second "
          "order) plus the oracle's pumped DC mode the macro excludes.")


if __name__ == "__main__":
    in_window_error()
    closure_is_exact()
    pumped_residual()
