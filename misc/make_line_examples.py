"""Worked transmission-line examples for File -> Examples, each with Notes.

Unlike the bare test scenes in examples/test_scenes (layout checks), these
are teaching graphs: every file carries a Notes tab that says what the
drawing is, what to look at in the S-parameters, and which knob does what.
They live in examples/pgraphs so the Examples menu lists them (TL_ prefix).

    QT_QPA_PLATFORM=offscreen python misc/make_line_examples.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")

from PySide6.QtWidgets import QApplication  # noqa: E402
QApplication.instance() or QApplication([])

import graphulator.graphulator_para as gp                    # noqa: E402
from graphulator import graphulator_para_config as config    # noqa: E402
from graphulator.autograph import line_fsr_for_target         # noqa: E402

OUT_DIR = os.path.join(ROOT, "examples", "pgraphs")


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


def sweep(win, center, span, points=801):
    """Enter scattering mode and set the sweep, so the saved file opens
    ready to 'Show S' on the window the notes talk about (the scattering
    section is only written while the mode is on)."""
    if not win.scattering_mode:
        win._enter_scattering_mode()
    panel = win.properties_panel
    panel.freq_center_spin.setValue(center)
    panel.freq_span_spin.setValue(span)
    panel.freq_points_spin.setValue(points)


def save(win, name, notes):
    win.properties_panel.notes_editor.setPlainText(notes.strip() + "\n")
    path = os.path.join(OUT_DIR, f"{name}.pgraph")
    assert win._save_graph_to_file(path), name
    print(f"  wrote {os.path.relpath(path, ROOT)}")


# ---------------------------------------------------------------------------

def ex_open_line():
    win = fresh_window()
    win.add_line_resonator(label='TL', pos=(0.0, 0.0), FSR=1.5, Ztx=65.0,
                           f_max=9.0, port_end='xL', Z0_port=50.0)
    sweep(win, 4.5, 6.2)
    save(win, "TL_1_OPEN_LINE_ON_A_PORT", r"""
# A transmission line terminated on a port

The cylinder is an **open–open transmission-line resonator**: a comb of
standing-wave modes at $f_n = n\cdot\mathrm{FSR}$ (here FSR = 1.5, so
1.5, 3, 4.5, 6, 7.5, 9). Its right end (x = L) is terminated on the port
**TL**, which is a 50 Ω resistor; the line's own impedance is Ztx = 65 Ω.

**What to look at.** *Ctrl+R*, then *Show S*. The reflection $S_{TL\leftarrow TL}$
has unit magnitude (the line is lossless) — all the physics is in the
**phase**: switch the plot to *Phase* and watch it wind through $2\pi$ at
every comb mode. The linewidth of each mode is
$$\gamma = \tfrac{2}{\pi}\,\tfrac{Z_\mathrm{tx}}{Z_0}\,\mathrm{FSR} \approx 0.83\,\mathrm{FSR},$$
comparable to the spacing — the *overlapping* regime, where the modes are
not independent: they all damp through the same resistor and the shared
port column couples them (cross-damping).

**Knobs.** In the *Ports & Lines* panel: raise Ztx toward Z0 = 50 and the
modes sharpen (γ/FSR → 0.64); lower it and they broaden. Add α (uniform
loss) and $|S|$ dips below 0 dB at each mode. Change **f_max** — nothing
happens to the port response: the modes beyond f_max are folded back in
analytically (*close comb tail analytically*), so N only matters once
something *couples* to the comb. Untick that box to see what truncation
alone does to a raw comb: every resonance shifts by a fraction of a
linewidth, more so at high frequency.
""")


def ex_tapped_node():
    win = fresh_window()
    a = add_node(win, 0, 'a', (-8.0, 0.0), freq=4.4)
    tl = win.add_line_resonator(label='TL', pos=(0.0, 0.0), FSR=1.5,
                                Ztx=65.0, f_max=9.0, port_end='xL')
    win.connect_line_end_to_node(tl, 'x0', a, rate=0.05)
    p = win.add_port(label='Pa', pos=(-12.0, 0.0))
    win.add_port_attachment(p, a['node_id'], rate=0.1, sign=1)
    sweep(win, 4.5, 3.0)
    save(win, "TL_2_MODE_TAPPED_ONTO_A_LINE", r"""
# A mode tapped onto a transmission line

Mode **a** (4.4) has its own port **Pa** and is *tapped* onto the open
end (x = 0) of the line **TL**, whose other end is terminated on port
**TL**. One drawn connection stands for the conservative couplings of
**a** to *every* comb mode at once, with the verified **capacitive**
profile $g_n \propto u_n(\text{end})\sqrt{n}$ (change the tap type per
end in the line dialog — inductive is $\propto 1/\sqrt{n}$).

**What to look at.** $S_{TL\leftarrow Pa}$ is a two-port transmission
through the line: **a** sits between comb modes 3 (4.5) and 2 (3.0), so
the response is the hybridization of **a** with its nearest comb
neighbor. The rate you set (50 mau) is the coupling **at the reference
harmonic** n = 3, the mode nearest 4.4 — shown as the chip on the tap
wire; every other mode follows the profile from there.

**Knobs.** Drag **a**'s frequency in the Nodes table onto 4.5 to see the
avoided crossing with comb mode 3; the *n=* spinbox on the tap row
changes which mode the rate is referenced to. Because the tap couples to
the comb's high modes too, this is a graph where **f_max matters**: press
*Check truncation (2× f_max)* in Ports & Lines to see how much.
""")


def ex_pumped_amp():
    win = fresh_window()
    tl = win.add_line_resonator(label='TL', pos=(0.0, 2.0), FSR=1.5,
                                Ztx=65.0, f_max=9.0, port_end='xL')
    win.set_line_pump(tl, 'x0', f_p=9.0, rate=0.05, n_ref=3,
                      twin_pos=(0.0, -2.0))
    sweep(win, 4.5, 3.0)
    save(win, "TL_3_PUMPED_TERMINATION_AMPLIFIER", r"""
# A line terminated in a modulated inductor (parametric amplifier)

The left end (x = 0) of **TL** is terminated in an inductor whose inverse
inductance is modulated at $f_p = 9$. Because one element at one point
sees the field only through $\Phi(0)$, its coupling to the comb is
**rank one**: an outer product $g\,g^T$ of the end profile. The macro
draws that as a **conjugate twin** of the line (**TL\***, the idler
sector) and one **triple-line pump bus** between them — three strokes
because on a harmonic comb the same pump drives *amplification* pairs
($f_n + f_m = f_p$: 4.5 + 4.5, 3 + 6, 1.5 + 7.5) *and* frequency
*conversion* pairs ($|f_n - f_m| = f_p$) at once; you cannot pick one
without engineering dispersion into the line.

**What to look at.** $S_{TL\leftarrow TL}$ shows gain around 4.5 (the
degenerate pair, n = m = 3) and $S_{TL^*\leftarrow TL}$ is the idler
output. Their frequency axes differ: the twin's channel is labelled in its
own frame, $f_p - f$. Manley–Rowe holds on this graph to machine
precision.

**Knobs.** The pump row in *Ports & Lines* has $f_p$, the rate (defined
at the pair (n, m) = (3, 3) and propagated to every other pair by the
inductive profile), the phase and the reference mode. Raise the rate
toward threshold and watch the gain peak grow and narrow (there is no
stability flag yet — past threshold the linear model is simply wrong).
The rate normalization is pinned to the exact harmonic-balance oracle:
`rate = 2·FSR·g/π`.
""")


def ex_loaded_line():
    win = fresh_window()
    f_Z = 3.0
    fsr = line_fsr_for_target(4.0, 1, f_Z, 'inductive')
    tl = win.add_line_resonator(label='TL', pos=(0.0, 2.0), FSR=fsr,
                                Ztx=65.0, f_max=14.0, port_end='xL',
                                load={'end': 'x0', 'type': 'inductive',
                                      'f_Z': f_Z})
    win.set_line_pump(tl, 'x0', f_p=8.0, rate=0.05, n_ref=1,
                      twin_pos=(0.0, -2.0))
    sweep(win, 4.0, 3.0)
    save(win, "TL_4_INDUCTIVELY_LOADED_LINE", r"""
# The same amplifier, with the inductor's reactance included

The modulated inductor of example 3 is also a **load** on the line, and a
reactive load *disperses* the comb: the modes leave $n\cdot\mathrm{FSR}$,
their end profiles $u_n(L)$ leave $(-1)^n$, and even the port coupling
$\gamma_n = 1/(2\pi Z_0 C_n)$ becomes mode-dependent. Here the load is
specified as a type (inductive) plus $f_Z = 3$, the frequency at which
$|X_L| = Z_\mathrm{tx}$ — one number, no reference frequency to agree on,
and an explicit type rather than a sign, because this project's convention
$Z_L = -i\omega L$ makes an inductor's reactance *negative*.

**The ergonomic point.** FSR here is 19.5 — not a mode spacing at all but
the geometric parameter $v/2\ell$, solved in closed form so that the
**loaded fundamental lands exactly on 4.0**:
$$\mathrm{FSR} = \frac{\pi f}{\operatorname{arccot}\,x(f) + (n-1)\pi}.$$
Open the line's Properties page: *Target resonance → Set FSR* does this
for any mode. The loaded modes are listed there (4.0, 20.9, …); the DC
mode is gone, shorted by the inductor.

**What to look at.** Compare with example 3: the pump at $f_p = 8$ pairs the
fundamental with itself, and the idler sits where the *loaded* mode
frequencies say, not at $n\cdot\mathrm{FSR}$. The basis is validated
against exact ABCD to $\sim 1/N$ (the residual is truncation, and the
port loading of the truncated tail is closed analytically). Capacitive
loads are listed but disabled: their comb does not yet converge.
""")


def ex_two_lines_one_port():
    win = fresh_window()
    p = win.add_port(label='P', pos=(0.0, 0.0))
    a = win.add_line_resonator(label='TLa', pos=(-7.0, 0.0), FSR=1.5,
                               Ztx=65.0, f_max=9.0, port_end=None)
    b = win.add_line_resonator(label='TLb', pos=(7.0, 0.0), FSR=1.0,
                               Ztx=40.0, f_max=8.0, port_end=None, angle=180.0)
    win.connect_line_end_to_port(a, 'xL', p)
    win.connect_line_end_to_port(b, 'xL', p)
    sweep(win, 4.5, 6.0)
    save(win, "TL_5_TWO_LINES_ONE_PORT", r"""
# Two lines on one port

Both lines end on the **same** resistor **P**. In the hub model a port is
one dissipation channel whose column is the union of everything attached
to it, so the two combs damp through one channel and are cross-damped
through it. The channel's susceptibility is the **sum** of the two lines':
$\chi = \chi_a + \chi_b$ with $\chi = -2i\,Z_\mathrm{in}/Z_0$ — i.e. the
port sees the two ends **in series**, $Z_a + Z_b$ (the resistor is driven
by $V_a + V_b$), not in parallel. The raw truncated comb converges to that
series answer as 1/N; with the tail closure it is exact at any N.

**What to look at.** One reflection trace, two interleaved combs (spacings
1.5 and 1.0) with different linewidths (Ztx = 65 vs 40 Ω on 50 Ω). Where a
mode of one line lands near a mode of the other, the shared channel
couples them and the phase response shows the avoided crossing.
""")


if __name__ == '__main__':
    os.makedirs(OUT_DIR, exist_ok=True)
    print("Generating transmission-line examples:")
    ex_open_line()
    ex_tapped_node()
    ex_pumped_amp()
    ex_loaded_line()
    ex_two_lines_one_port()
    print("done.")
