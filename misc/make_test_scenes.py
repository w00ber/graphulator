"""Regenerate the canonical explicit-ports test scenes (File -> Test).

Headless: builds each scene through the live GUI API and saves it with the
app's own serializer, so the files always match the current .pgraph format.

    QT_QPA_PLATFORM=offscreen python misc/make_test_scenes.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
OUT_DIR = os.path.join(ROOT, "examples", "test_scenes")

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

import graphulator.graphulator_para as gp                    # noqa: E402
from graphulator import graphulator_para_config as config    # noqa: E402
from graphulator.autograph import line_fsr_for_target         # noqa: E402


def fresh_window():
    config.EXPLICIT_PORTS_MODE = True
    win = gp.Graphulator()
    win._apply_explicit_ports_mode()
    return win


def add_node(win, node_id, label, pos, freq, B_int=0.0):
    node = {'node_id': node_id, 'label': label,
            'pos': (float(pos[0]), float(pos[1])),
            'color': 'cornflowerblue', 'color_key': 'BLUE',
            'node_size_mult': 1.0, 'label_size_mult': 1.0, 'conj': False}
    win.nodes.append(node)
    win.node_id_counter = max(win.node_id_counter, node_id + 1)
    win.scattering_assignments[node_id] = {'freq': freq, 'B_int': B_int}
    return node


def save(win, name):
    path = os.path.join(OUT_DIR, f"{name}.pgraph")
    assert win._save_graph_to_file(path), name
    print(f"  wrote {os.path.relpath(path, ROOT)}")


def scene_port_1node():
    win = fresh_window()
    a = add_node(win, 0, 'a', (-3.0, 0.0), freq=5.0)
    p = win.add_port(label='P1', pos=(1.5, 0.0))
    win.add_port_attachment(p, a['node_id'], rate=0.2, sign=1)
    save(win, "PORT_1NODE")


def scene_port_2nodes_stack():
    win = fresh_window()
    a = add_node(win, 0, 'a', (-3.0, 1.5), freq=5.0)
    b = add_node(win, 1, 'b', (-3.0, -1.5), freq=6.0)
    p = win.add_port(label='P1', pos=(1.5, 0.0))
    win.add_port_attachment(p, a['node_id'], rate=0.2, sign=1)
    win.add_port_attachment(p, b['node_id'], rate=0.2, sign=-1)
    save(win, "PORT_2NODES_STACK")


def scene_port_3nodes_arc():
    win = fresh_window()
    freqs = (4.5, 5.0, 5.5)
    pts = ((-3.5, 2.5), (-4.5, 0.0), (-3.5, -2.5))
    p = win.add_port(label='P1', pos=(1.5, 0.0))
    for k, (pos, f) in enumerate(zip(pts, freqs)):
        n = add_node(win, k, chr(ord('a') + k), pos, freq=f)
        win.add_port_attachment(p, n['node_id'], rate=0.15,
                                sign=1 if k % 2 == 0 else -1)
    save(win, "PORT_3NODES_ARC")


def scene_port_3nodes_surround():
    # nodes on three sides of the port: stresses the collimated exit and
    # the wrap-around wire to the node BEHIND the lead direction
    win = fresh_window()
    freqs = (4.5, 5.0, 5.5)
    pts = ((-4.0, 0.0), (1.0, 3.5), (1.0, -3.5))
    p = win.add_port(label='P1', pos=(1.0, 0.0))
    for k, (pos, f) in enumerate(zip(pts, freqs)):
        n = add_node(win, k, chr(ord('a') + k), pos, freq=f)
        win.add_port_attachment(p, n['node_id'], rate=0.15, sign=1)
    save(win, "PORT_3NODES_SURROUND")


def scene_port_shared_2lines():
    # one physical resistor shared by two lines AND a device mode
    win = fresh_window()
    a = add_node(win, 0, 'a', (0.0, 3.5), freq=4.4)
    p = win.add_port(label='P1', pos=(0.0, 0.0))
    tl1 = win.add_line_resonator(label='TL1', pos=(-7.0, 0.0), FSR=1.5,
                                 Ztx=65.0, f_max=6.0, port_end=None)
    tl2 = win.add_line_resonator(label='TL2', pos=(7.0, 0.0), FSR=2.0,
                                 Ztx=65.0, f_max=8.0, port_end=None)
    win.connect_line_end_to_port(tl1, 'xL', p)
    win.connect_line_end_to_port(tl2, 'x0', p)
    win.add_port_attachment(p, a['node_id'], rate=0.2, sign=1)
    save(win, "PORT_SHARED_2LINES")


def scene_line_tap_2nodes():
    win = fresh_window()
    a = add_node(win, 0, 'a', (-8.0, 2.8), freq=4.4)
    b = add_node(win, 1, 'b', (-8.0, -2.8), freq=2.9)
    tl = win.add_line_resonator(label='TL1', pos=(0.0, 0.0), FSR=1.5,
                                Ztx=65.0, f_max=6.0, port_end='xL')
    win.connect_line_end_to_node(tl, 'x0', a, rate=0.03)
    win.connect_line_end_to_node(tl, 'x0', b, rate=0.02)
    save(win, "LINE_TAP_2NODES")


def scene_node_2lines_tap():
    win = fresh_window()
    a = add_node(win, 0, 'a', (0.0, 0.0), freq=4.4)
    tl1 = win.add_line_resonator(label='TL1', pos=(-7.5, 2.0), FSR=1.5,
                                 Ztx=65.0, f_max=6.0, port_end='x0')
    tl2 = win.add_line_resonator(label='TL2', pos=(7.5, -2.0), FSR=2.0,
                                 Ztx=65.0, f_max=8.0, port_end='xL')
    win.connect_line_end_to_node(tl1, 'xL', a, rate=0.03)
    win.connect_line_end_to_node(tl2, 'x0', a, rate=0.03)
    save(win, "NODE_2LINES_TAP")


def scene_line_pumped():
    # a line terminated in a modulated inductor at x0, port at xL: the
    # conjugate twin, its own port and the rank-one pump bus are all
    # created by set_line_pump (docs/pumped_line_termination.md)
    win = fresh_window()
    # f_max = 9 -> N = 6. The port loading is exact at any N (the comb tail
    # is closed analytically, docs sec. 8); N here sizes the PUMP couplings
    # the closure does not carry -- check with 'Check truncation (2x f_max)'.
    tl = win.add_line_resonator(label='TL1', pos=(0.0, 2.0), FSR=1.5,
                                Ztx=65.0, f_max=9.0, port_end='xL')
    win.set_line_pump(tl, 'x0', f_p=9.0, rate=0.05, n_ref=3,
                      twin_pos=(0.0, -2.0))
    save(win, "LINE_PUMPED_TERMINATION")


def scene_line_pumped_both():
    # f_p = 4.5 on an FSR=1.5, N=4 comb reaches BOTH families (sum pairs
    # 1.5+3 and difference pairs 6-1.5), so the bus draws three strokes
    win = fresh_window()
    tl = win.add_line_resonator(label='TL1', pos=(0.0, 2.0), FSR=1.5,
                                Ztx=65.0, f_max=9.0, port_end='xL')
    win.set_line_pump(tl, 'x0', f_p=4.5, rate=0.05, n_ref=2,
                      twin_pos=(0.0, -2.0))
    save(win, "LINE_PUMPED_AMP_AND_CONV")


def scene_line_pumped_loaded():
    # the self-consistent version of scene_line_pumped: the modulated
    # inductor is ALSO the line's end load, so the comb is the dispersed
    # one (docs sec. 7). FSR comes from the closed-form inversion, so the
    # loaded fundamental lands exactly on 4.0 -- no guessing.
    win = fresh_window()
    f_Z = 3.0
    fsr = line_fsr_for_target(4.0, 1, f_Z, 'inductive')
    tl = win.add_line_resonator(label='TL1', pos=(0.0, 2.0), FSR=fsr,
                                Ztx=65.0, f_max=14.0, port_end='xL',
                                load={'end': 'x0', 'type': 'inductive',
                                      'f_Z': f_Z})
    win.set_line_pump(tl, 'x0', f_p=9.0, rate=0.05, n_ref=1,
                      twin_pos=(0.0, -2.0))
    save(win, "LINE_PUMPED_LOADED")


# ---------------------------------------------------------------------------
# Lee, Spietz & Aumentado, "Parametric Intermode Coupling in Superconducting
# lambda/4 Resonators" (2013): a SQUID-terminated lambda/4 CPW pumped through
# the SQUID flux. Fundamental A and first harmonic B; pump at 2 f_A
# (degenerate gain), f_B - f_A (A <-> B conversion, the Fig. 4 "hole") and
# f_A + f_B (nondegenerate gain). Both scenes carry a Notes tab with the
# circuit -> graph methodology; the numbers in the notes are computed here
# so they can never drift from the file.
# ---------------------------------------------------------------------------

def _solve_fz_for_harmonic_ratio(fA, fB, Ztx):
    """Effective inductive-load f_Z putting loaded mode 1 at fA AND mode 2
    at fB. Bisection on f_Z; FSR follows from the closed form each step."""
    from graphulator.autograph import LineResonator
    def f2(fZ):
        fsr = line_fsr_for_target(fA, 1, fZ, 'inductive')
        r = LineResonator(line_id=0, FSR=fsr, Ztx=Ztx, f_max=4 * fB,
                          port_end='xL', Z0_port=50.0,
                          load={'end': 'x0', 'type': 'inductive', 'f_Z': fZ})
        return r.mode_freq(2)
    lo, hi = 2.0, 60.0                 # f2 decreases toward 3 fA as fZ grows
    assert f2(lo) > fB > f2(hi), (f2(lo), fB, f2(hi))
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if f2(mid) > fB:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def intermode_scene(which):
    """which in ('CONVERSION', 'DEGENERATE_AMP', 'NONDEGENERATE_AMP')."""
    import numpy as np
    from graphulator.autograph import LineResonator
    from graphulator.para_features.explicit_ports import (
        pump_alpha, pump_load_modulation)

    # --- the paper's numbers, GHz as the app's a.u. -------------------------
    fA, fB = 1.840, 5.661           # Fig. 4 stripe; f_B^fit
    kappaA = 0.0029                 # 2.9 MHz fundamental bandwidth
    Ztx = 50.0                      # uniform stand-in for the 47.3/51.4 step
    Phi0, I_SQ, bias = 2.067833848e-15, 0.82e-6, 0.026
    L_SQ = Phi0 / (2 * np.pi * I_SQ) / abs(np.cos(np.pi * bias))
    fZ_SQ = Ztx / (2 * np.pi * L_SQ) / 1e9        # the SQUID alone
    fZ = _solve_fz_for_harmonic_ratio(fA, fB, Ztx)  # SQUID + step, as one load
    L_eff = Ztx / (2 * np.pi * fZ) * 1.0            # nH when fZ in GHz
    fsr = line_fsr_for_target(fA, 1, fZ, 'inductive')

    # port: a 62 fF coupler is a weak port; in the galvanic port model that
    # is a large Z0_port. Set it so mode 1's port rate is the paper's kappa_A.
    probe = LineResonator(line_id=0, FSR=fsr, Ztx=Ztx, f_max=4 * fB,
                          port_end='xL', Z0_port=50.0,
                          load={'end': 'x0', 'type': 'inductive', 'f_Z': fZ})
    g1_at_50 = probe.mode_gamma(1) * probe.mode_profile(1, 'xL') ** 2
    Z0_port = 50.0 * g1_at_50 / kappaA
    res = LineResonator(line_id=0, FSR=fsr, Ztx=Ztx, f_max=4 * fB,
                        port_end='xL', Z0_port=Z0_port,
                        load={'end': 'x0', 'type': 'inductive', 'f_Z': fZ})
    f1, f2 = res.mode_freq(1), res.mode_freq(2)
    gam = {n: res.mode_gamma(n) * res.mode_profile(n, 'xL') ** 2 for n in (1, 2)}

    # pump strength: anchored on the device, dL_l/L_l. The rate box is the
    # coupling at the reference pair (1, m_ref); m_ref is the mode nearest
    # f_p - f_1, which is mode 1 for all three pumps here. Choose beta so the
    # A<->B coupling g_12 = rate*w_2/2 sits at the paper's stated operating
    # point g_AB ~ sqrt(kappa_A kappa_B) (conversion) or a bit above it
    # (visible gain) -- the paper reports 0.5-3% flux modulation there.
    w2 = dict((nid, w) for nid, w, _ in res.tap_couplings('x0', 1, 'inductive'))
    w2 = w2[res.mode_node_id(2)]
    target = {'CONVERSION': 1.0, 'DEGENERATE_AMP': 0.9, 'NONDEGENERATE_AMP': 0.9}[which]
    if which == 'DEGENERATE_AMP':
        rate = 2 * target * gam[1]                 # g_11 = rate/2 vs kappa_A
    else:
        rate = 2 * target * np.sqrt(gam[1] * gam[2]) / w2
    f_p = {'CONVERSION': f2 - f1, 'DEGENERATE_AMP': 2 * f1,
           'NONDEGENERATE_AMP': f1 + f2}[which]
    beta = pump_load_modulation(res, 'inductive', rate, 1, 1, 'x0')
    dPhi = beta / (np.pi * np.tan(np.pi * bias))   # dL/L = pi tan(pi Phi/Phi0) dPhi/Phi0
    alpha = pump_alpha(rate, f1, f1)

    win = fresh_window()
    tl = win.add_line_resonator(label='TL', pos=(0.0, 2.0), FSR=fsr, Ztx=Ztx,
                                f_max=4 * fB, port_end='xL', Z0_port=Z0_port,
                                load={'end': 'x0', 'type': 'inductive',
                                      'f_Z': fZ})
    win.set_line_pump(tl, 'x0', f_p=float(f_p), rate=float(rate), n_ref=1,
                      twin_pos=(0.0, -2.0))
    if not win.scattering_mode:
        win._enter_scattering_mode()
    panel = win.properties_panel
    center = f1 if which != 'NONDEGENERATE_AMP' else f1
    panel.freq_center_spin.setValue(round(center, 4))
    panel.freq_span_spin.setValue(0.030)           # Fig. 4's 1.825-1.855
    panel.freq_points_spin.setValue(601)

    hole_db = -33.9   # measured on this scene; tests/test_intermode_lee2013.py pins < -25 dB
    look = {
        'CONVERSION': r"""
**What to look at — the Fig. 4 "hole".** *Show S*, trace $S_{TL\leftarrow TL}$
(reflection at the A-mode port). The pump sits at $f_p = f_B - f_A$: a
signal at $f_A$ is **up-converted to $f_B$** and leaves through the B-mode's
own port loading — so $|S_{11}|$ shows a *dip*, not a peak, exactly the deep
hole of Fig. 4 at $f_P \approx 3.83$ GHz. Tick $S_{TL^*\leftarrow TL}$ too:
that is the converted power at $f_B$ (the twin port reads the idler
sector), and $|S_{TL\,TL}|^2 + |S_{TL^*TL}|^2 = 1$ to a few $10^{-3}$ — a
beam-splitter, no photons created. The two-mode coupling is
$g_{AB}/\sqrt{\kappa_A\kappa_B} = %(target).1f$, the paper's stated
operating point, so the hole is the *onset* of the A–B normal-mode
splitting, as in the text.

**Why this scene exists.** It is the case a cluster-flag sector rule got
wrong: the same edge assembled as two-mode squeezing turns this hole into
gain. The $\sigma_z$ sector rule (`docs/pump_sector_rule.md`) makes it a
beam-splitter — here a %(hole).0f dB hole with
$|S_{TL\,TL}|^2 + |S_{TL^*TL}|^2 = 1$ to $3\times10^{-4}$ — and the
harmonic-balance oracle agrees to 2%%.
Raise **rate** and the hole deepens then splits into two — the
strong-coupling normal modes the paper could not reach for heating.
""",
        'DEGENERATE_AMP': r"""
**What to look at — the Fig. 2/4 gain ridge.** *Show S*, trace
$S_{TL\leftarrow TL}$. The pump is at $f_p = 2 f_A$, so signal and idler both
sit in the fundamental (the twin's $+1$ member, resonant at
$f_p - f_A = f_A$): degenerate phase-preserving gain, a *peak* above 0 dB
at $f_A$. Here $g_{11}/\kappa_A = %(target).1f$, just under the
oscillation threshold; the paper's $\sim$20 dB needs $g \to \kappa$.
Tick $S_{TL^*\leftarrow TL}$: the idler, with
$|S_{TL\,TL}|^2 - |S_{TL^*TL}|^2 = 1$ to $O(\text{rate}^2)$ (Manley–Rowe
for squeezing). Nudge **f_p** down by 0.14 and you are on the conversion
pump of the sibling scene: the peak becomes a hole.
""",
        'NONDEGENERATE_AMP': r"""
**What to look at — Fig. 3.** *Show S*, trace $S_{TL\leftarrow TL}$. The
pump is at $f_p = f_A + f_B$: two-mode squeezing between the fundamental
and the first harmonic, gain at $f_A$ with the idler emerging at $f_B$ (the
twin's $+2$ member, resonant at $f_p - f_B = f_A$). $S_{TL^*\leftarrow TL}$ is
that idler; $|S_{TL\,TL}|^2 - |S_{TL^*TL}|^2 = 1$ to $O(\text{rate}^2)$.
$g_{AB}/\sqrt{\kappa_A\kappa_B} = %(target).1f$. Step **f_p** by a few
MHz either side, as Fig. 3(a) does, and the gain peak walks across the
resonance.
""",
    }[which] % dict(target=target, hole=hole_db)

    notes = r"""
# Intermode coupling in a SQUID-terminated $\lambda/4$ resonator

Lee, Spietz & Aumentado, *Parametric Intermode Coupling in Superconducting
$\lambda/4$ Resonators* (2013). A Nb coplanar-waveguide $\lambda/4$
resonator, open at the port end (62 fF coupler to 50 Ω) and terminated at
ground by a dc SQUID whose inductance is flux-pumped. The fundamental **A**
($f_A$ = %(fA).3f GHz, bandwidth 2.9 MHz) and first harmonic **B**
($f_B$ = %(fB).3f GHz) are the two "resonators" of the toy circuit in its
Fig. 1(a); one pump reaches degenerate gain ($2f_A$ = %(fpsd).3f), A↔B
conversion ($f_B - f_A$ = %(fpfc).3f, Fig. 4) and nondegenerate gain
($f_A + f_B$ = %(fpnd).3f, Fig. 3). Units: **GHz as the app's a.u.**
%(look)s
## How the circuit became this graph

1. **The resonator is one line macro, on the loaded basis** (docs §7). A
   $\lambda/4$ line is open at one end and *nearly* shorted at the other by
   the SQUID: that is an open line with an **inductive end load** at x0,
   whose comb is the quarter-wave family $f_1, \sim 3f_1, \sim 5f_1, \dots$
   pulled by the load's dispersion. The load is parameterized by $f_Z$, the
   frequency where $\omega L = Z_\mathrm{tx}$.

2. **The SQUID inductance.** $I_\mathrm{SQ}$ = 0.82 µA gives
   $L_\mathrm{SQ,0} = \Phi_0/2\pi I_\mathrm{SQ}$ = 0.401 nH, or 0.403 nH at
   the paper's bias $\Phi = -0.026\,\Phi_0$ — $f_Z$ = %(fZsq).2f GHz on a
   50 Ω line. That alone puts $f_B/f_A$ = 3.004: the near-ideal $\lambda/4$
   spacing, and exactly the problem the paper solves with a **stepped
   impedance** (47.3 / 51.4 Ω, step 1/3 from the SQUID) that moves $f_B$ to
   3.077 $f_A$ so the conversion pump ($f_B - f_A$) separates from the
   degenerate-gain pump ($2f_A$) by 141 MHz instead of 7.

3. **The step is not in the macro** (one $Z_\mathrm{tx}$ per line), so it is
   emulated by the only dispersion knob the loaded basis has: a single
   effective end inductance chosen so the loaded modes 1 and 2 land on the
   *measured* $f_A$ and $f_B$ — solved by bisection on $f_Z$ with the
   closed-form FSR inversion at each step. Result: $f_Z$ = %(fZ).3f GHz,
   $L_\mathrm{eff}$ = %(Leff).2f nH, FSR (the geometric $v/2\ell$, not a
   spacing) = %(fsr).4f GHz. The excess over 0.4 nH stands in for the
   step; the mode *profiles* at the SQUID are therefore those of a heavier
   load than the real one, which is the approximation to remember.

4. **The port.** A 62 fF coupler is a *weak* port. The macro terminates the
   line galvanically in $Z_0$, so weak coupling is a **large $Z_0$**:
   $Z_0$ = %(Z0).0f Ω makes mode 1's port rate the measured
   $\kappa_A$ = 2.9 MHz (mode 2 then gets %(kB).2f MHz — a galvanic port
   loads the harmonics nearly equally, a capacitive one would load B about
   $(f_B/f_A)^2 \approx 9\times$ harder; the paper could not see B
   directly, so this is unconstrained). The comb tail beyond f_max is
   closed analytically, so the port loading is exact at this N.

5. **The pump is the load.** The modulated element *is* the terminating
   inductor, so the pump is put on the loaded end x0 with inductive
   coupling: the block between the comb and its conjugate twin is the
   rank-one outer product of the load's mode profile. The rate box is the
   coupling at the reference pair (n = 1, m = 1); every other pair follows
   the participation profile, and the panel reports the device number it
   implies, $\delta L_\ell/L_\ell$ = %(beta).4f. Through
   $L_\mathrm{SQ} \propto 1/|\cos(\pi\Phi/\Phi_0)|$ that is a flux swing
   $\delta\Phi/\Phi_0$ = %(dPhi).3f at the bias — the paper quotes
   0.5–3%% for gain, so the linearized SQUID on this uniform line wants
   several times more modulation than the experiment used. $\alpha$ =
   %(alpha).4f, far from the $\alpha \to 1$ limit.

6. **What one pump does at once.** In the two-cluster graph the twin's
   $+m$ member is resonant at $f_p - f_m$ and its $-m$ member at
   $f_p + f_m$, so a single $f_p$ satisfies three conditions
   (`pump_partners`): $f_n + f_m = f_p$ (squeezing), $f_m - f_n = f_p$ and
   $f_n - f_m = f_p$ (beam-splitter). The coupling's Hermitian /
   anti-Hermitian character follows the $\sigma_z$ sector
   $s = (-1)^{\texttt{conj}\oplus\texttt{counter\_rotating}}$, not the
   cluster — which is what distinguishes the hole from the peak.

7. **Which rung is on the sweep.** A two-frame truncation holds the
   signal frame $\omega$ and ONE idler frame. The twin sits at
   $\omega - f_p$ for a pump anchored on amplification or down-conversion
   (twin $+m$ resonant at $f_p - f_m$, twin $-m$ at $f_p + f_m$) and at
   $\omega + f_p$ for up-conversion (twin $-m$ at $f_m - f_p$). Fig. 4's
   hole is an *up*-conversion ($f_A < f_p$), so that scene's bus carries
   the frame rule `sector+`; in the other frame the same process exists
   only at $-\omega$ — the two agree to $10^{-15}$ as
   $S(f) = \overline{S(-f)}$ — where the sweep cannot go. The anchored
   pair is the partner closest to resonance under the pump (for the
   conversion pump $m = 2$, exactly resonant, against $m = 1$
   amplification detuned by 141 MHz); the Ports & Lines panel names the
   frame and marks partners the frame cannot show.

**Not modelled:** the stepped impedance itself, the SQUID's Kerr
nonlinearity (the paper's gain ceiling), and the capacitive character of
the coupler. Sibling scenes: `INTERMODE_LEE2013_CONVERSION`,
`INTERMODE_LEE2013_DEGENERATE_AMP`, `INTERMODE_LEE2013_NONDEGENERATE_AMP`
— same circuit, the three pump frequencies of the paper.
""" % dict(fA=f1, fB=f2, fpsd=2 * f1, fpfc=f2 - f1, fpnd=f1 + f2, look=look,
           fZsq=fZ_SQ, fZ=fZ, Leff=L_eff, fsr=fsr, Z0=Z0_port,
           kB=gam[2] * 1e3, beta=beta, dPhi=dPhi, alpha=alpha)
    win.properties_panel.notes_editor.setPlainText(notes.strip() + "\n")
    save(win, f"INTERMODE_LEE2013_{which}")
    return dict(f1=f1, f2=f2, f_p=f_p, rate=rate, Z0=Z0_port, fZ=fZ, fsr=fsr,
                gam=gam, beta=beta, dPhi=dPhi, alpha=alpha, w2=w2)


def scene_intermode_lee2013():
    for which in ('CONVERSION', 'DEGENERATE_AMP', 'NONDEGENERATE_AMP'):
        intermode_scene(which)


if __name__ == '__main__':
    os.makedirs(OUT_DIR, exist_ok=True)
    print("Generating test scenes:")
    scene_port_1node()
    scene_port_2nodes_stack()
    scene_port_3nodes_arc()
    scene_port_3nodes_surround()
    scene_port_shared_2lines()
    scene_line_tap_2nodes()
    scene_node_2lines_tap()
    scene_line_pumped()
    scene_line_pumped_both()
    scene_line_pumped_loaded()
    scene_intermode_lee2013()
    print("done.")
