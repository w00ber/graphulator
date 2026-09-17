# A transmission line terminated in a modulated inductor: rank-one coupling, self-phase-matching, dispersion

*Working note for the pumped-termination macro (Phase 2). Numbers quoted here are
reproduced by `misc/pumped_termination_checks.py` against the `tests/cmtline_core.py`
oracle; nothing below is an ansatz.*

**Setting.** An open–open transmission line of length $\ell$, impedance $Z_\mathrm{tx}$,
phase velocity $v$, with mode functions $u_n(x)$ and mode fluxes $\varphi_n(t)$:

$$
\Phi(x,t) = \sum_n u_n(x)\,\varphi_n(t), \qquad u_n(0) = 1, \qquad u_n(\ell) = (-1)^n .
$$

Some lumped element sits at one point $x_0$ (an end): a resistor (the port), or an
inductor whose inverse inductance is modulated,

$$
\frac{1}{L(t)} = \frac{1}{L_0} + \delta\cos(\omega_p t).
$$

JAA conventions as everywhere in this project: $e^{+i\omega t}$, decaying poles in the
lower half plane, $M$ diagonal $f_\mathrm{drive} \pm f_0 + \tfrac{i}{2}B$.

---

## 1. One element at one point $\Rightarrow$ rank one (the unified argument)

A lumped element at $x_0$ can only "see" the field through **one scalar**, the flux
(or voltage) at that point,

$$
\Phi(x_0) = \sum_n u_n(x_0)\,\varphi_n = \mathbf{u}^{\mathsf T}\boldsymbol\varphi,
\qquad \mathbf{u} \equiv \big(u_n(x_0)\big)_n .
$$

Whatever energy the element stores or dissipates is therefore a function of that
single linear combination of the mode amplitudes, and its second derivative with
respect to the amplitudes — which *is* the coupling matrix — is the outer product
$\mathbf{u}\mathbf{u}^{\mathsf T}$. That is the whole argument; the two elements just
differ in which scalar function of $\mathbf{u}^{\mathsf T}\boldsymbol\varphi$ they contribute.

**Resistor (the port).** The dissipated power is

$$
P = \frac{V(x_0)^2}{R} = \frac{(\mathbf{u}^{\mathsf T}\mathbf{V})^2}{R},
$$

so the damping matrix is $R^{-1}\mathbf{u}\mathbf{u}^{\mathsf T}$; in the $a$-basis it is the
familiar rank-one $\tfrac{i}{2}\boldsymbol\kappa\boldsymbol\kappa^\dagger$ with
$\kappa_n \propto u_n(x_0)$. This is the power-balance argument already in the code
base: the energy leaving the modes must equal the power entering one resistor through
one voltage,

$$
\frac{d}{dt}\sum_n |a_n|^2 = -\Big|\sum_n \kappa_n a_n\Big|^2 = -\,|\boldsymbol\kappa^\dagger\mathbf a|^2 ,
$$

and only a rank-one anti-Hermitian part of $M$ is consistent with that. (It is the
reason a shared port cross-damps its modes, and why non-diagonal external
dissipation was needed in the first place.)

**Modulated inductor (the pump).** The inductor's energy is

$$
U = \frac{\Phi(x_0)^2}{2L(t)} = \tfrac12\,(\mathbf{u}^{\mathsf T}\boldsymbol\varphi)^2
\left(\frac{1}{L_0} + \delta\cos\omega_p t\right).
$$

The Hessian $\partial^2 U/\partial\varphi_n\partial\varphi_m = u_n u_m / L(t)$ is rank one for
every $n, m$. The static part $\mathbf{u}\mathbf{u}^{\mathsf T}/L_0$ is the boundary condition
that loads the line (§4); the modulated part is the parametric coupling. The pump does
work on the modes only through that one scalar:

$$
\frac{dE_\mathrm{modes}}{dt} = \tfrac12\,\Phi(x_0)^2\,\frac{d}{dt}\!\left(\frac{1}{L}\right).
$$

Check on the oracle: `build_galvanic` builds exactly this geometry and its pump
matrix is literally `P = np.outer(e, e)/LJ` — numerically rank 1 on the $11\times 11$
mode space (`misc/pumped_termination_checks.py`).

So the modulated inductor is the **parametric twin of the dissipative hub**: one
element at one point gives a rank-one damper *within* each frequency sector, or a
rank-one coupling *between* sectors, from the same spatial vector $\mathbf{u}$.

## 2. Into the $a$-basis: one outer product, two blocks

Write $\varphi_n = \varphi_n^{\mathrm{zpf}}\,(a_n + a_n^*)$ with
$\varphi_n^{\mathrm{zpf}} \propto 1/\sqrt{\omega_n C_n}$ (the flux quadrature scale of
mode $n$), and define $g_n \equiv u_n(x_0)\,\varphi_n^{\mathrm{zpf}}$. For the open–open
comb $C_n$ is $n$-independent for $n \ge 1$, so

$$
g_n \;\propto\; \frac{u_n(x_0)}{\sqrt{\omega_n}} \;\propto\; \frac{u_n(x_0)}{\sqrt{n}} ,
$$

which is the *inductive* tap profile already pinned to machine precision against the
same oracle (`tests/test_line_taps.py`). Then

$$
\Phi(x_0)^2 = \sum_{n,m} g_n g_m\,(a_n + a_n^*)(a_m + a_m^*)
            = \sum_{n,m} g_n g_m\,\big[\,a_n a_m + a_n^* a_m^* + a_n^* a_m + a_n a_m^*\,\big].
$$

Multiplying by $\delta\cos\omega_p t = \tfrac{\delta}{2}\,(e^{i\omega_p t} + e^{-i\omega_p t})$
and keeping the slowly varying terms gives two blocks, **both** with the same rank-one
matrix $\mathbf g\mathbf g^{\mathsf T}$:

| term | slow when | process | graph edge |
|---|---|---|---|
| $a_n^* a_m^*\,e^{-i\omega_p t}$ + c.c. | $\omega_n + \omega_m = \omega_p$ | amplification (sum-frequency) | non-conjugate $\leftrightarrow$ conjugate |
| $a_n^* a_m\,e^{\mp i\omega_p t}$ + c.c. | $\omega_n - \omega_m = \pm\omega_p$ | conversion (difference-frequency) | non-conjugate $\leftrightarrow$ conjugate, *negative-frequency member* (§4) |

One pump therefore drives both families at once, through one outer product.

**What the rotating-wave approximation does to it.** In the isolated-mode limit
$\mathrm{FSR} \gg \kappa$, only the $(n,m)$ entries of $\mathbf g\mathbf g^{\mathsf T}$ that
satisfy a resonance condition survive the RWA; the rest of the outer product is what
gets swept away, and one is left with the textbook one- or two-mode parametric
amplifier. That is the regime that has been measured. In the overlapping limit
$\kappa \sim \mathrm{FSR}$ (a coax comb has $\gamma/\mathrm{FSR} = \tfrac{2}{\pi}\,Z_\mathrm{tx}/Z_0
\approx 0.83$ at $65\,\Omega$ on $50\,\Omega$) the sweep is not allowed: every entry of
$\mathbf g\mathbf g^{\mathsf T}$ is within a linewidth of a resonance and the whole block
stays — exactly as diagonal damping stops being allowed for the same comb.

## 3. The power-balance analogue: Manley–Rowe

The port argument was a *dissipative* balance. The parametric analogue is a
*conservative* exchange with a stiff pump, and it is the Manley–Rowe relation.

Because the amplification block has the form
$\sum_{n,m} g_n g_m\,(a_n^\dagger b_m^\dagger + \mathrm{h.c.})$, it commutes with
$N_a - N_b$ (the photon-number difference between the two clusters): signal and idler
photons are created in pairs, cluster-wide, not pair by pair. The conversion block
$\sum_{n,m} g_n g_m\,(a_n^\dagger b_m + \mathrm{h.c.})$ commutes with $N_a + N_b$.
Translated into scattering data at a single port with power-wave normalization,

$$
\text{amplification } (\omega_i = \omega_p - \omega_s > 0):\qquad
|S_{ss}|^2 - 1 = \frac{\omega_s}{\omega_i}\,|S_{is}|^2 ,
$$

$$
\text{conversion } (\omega_i < 0):\qquad
|S_{ss}|^2 + \frac{\omega_s}{|\omega_i|}\,|S_{is}|^2 = 1 .
$$

Note that these follow from the *cross-cluster Hermitian form* of the coupling, not
from its rank; what rank one adds is that the coupling and the damping come from the
same $\mathbf u$ — a single physical location.

Verified on the oracle (lossless line + modulated inductor, `hb_signal_idler`):

| regime | pump | peak $\lvert S_{is}\rvert^2$ | Manley–Rowe residual |
|---|---|---|---|
| matched port, $Z_0 = Z_\mathrm{tx}$ | $\delta = 0.9$ | 0.082 | $8.8\times 10^{-15}$ |
| weakly coupled port, $Z_0 = 10\,Z_\mathrm{tx}$ | $\delta = 0.25$ | 0.71 | $3.4\times 10^{-14}$ |
| conversion band ($\omega_i < 0$) | $\delta = 0.9$ | 0.006 | $4.3\times 10^{-15}$ |

So the relation holds to machine precision in the two-rung solution, in both
processes, in the overlapping regime.

## 4. Self-phase-matching — and why a real loaded line is *not* quite

**Harmonic comb.** If $\omega_n = n\,\mathrm{FSR}$ and $\omega_p = P\,\mathrm{FSR}$, then every
pair with $n + m = P$ is *exactly* resonant for amplification, and every pair with
$|n - m| = P$ for conversion, all at once from one pump. For $P = 6$ that is
$(0,6), (1,5), (2,4), (3,3)$ — the last being the degenerate, self-paired case — plus
the negative-frequency partners such as $(-1, 7)$, plus every pair one FSR off, which
at $\gamma/\mathrm{FSR} \approx 0.83$ sits inside a linewidth.

**How both families live in a two-cluster graph.** With the comb in the signal frame
(drive $\omega$) and its conjugated twin in the idler frame ($\omega_p - \omega$), a pump
edge between *any* pair is frame-consistent with the same offset. Amplification is the
edge to the $+m$ member of the twin (resonant at $\omega = \omega_p - \omega_m$).
Conversion is the edge to the $-m$ **member** of the twin (resonant at
$\omega = \omega_p + \omega_m$): the classical idler at $\omega_p - \omega_s$ comes out
negative when $\omega_s > \omega_p$, and a conjugated negative-frequency component *is*
the down-converted signal. It does **not** appear as a non-conjugate $\leftrightarrow$
non-conjugate edge inside one cluster, because that would need a third frame
$\omega \pm \omega_p$. The DC-complete $\pm n$ comb — the two partial fractions of each
mode's exact second-order response — is what lets a two-rung truncation hold both
processes; rungs at $\omega \pm 2\omega_p$ are dropped, at $O(\delta^2)$.

**Dispersion.** An inductor $L$ to ground at $x = \ell$ is not a uniform frequency
shift. The resonance condition is

$$
\cot(k\ell) = \frac{\omega L}{Z_\mathrm{tx}} ,
$$

whose roots interpolate between the open–short (quarter-wave) comb
$k_n\ell = (n - \tfrac12)\pi$ at low frequency, where the inductor looks like a short,
and the open–open comb $k_n\ell = n\pi$ at high frequency, where it looks open, with
the crossover near $\omega \sim Z_\mathrm{tx}/L$. The spacing is non-uniform in between:

| $L/Z_\mathrm{tx}$ | $k_1\ell/\pi$ | $k_2\ell/\pi$ | $k_3\ell/\pi$ | $k_4\ell/\pi$ | successive spacings (units of $\pi$) |
|---|---|---|---|---|---|
| 0.001 | 0.500 | 1.499 | 2.498 | 3.497 | 0.999 0.999 0.999 |
| 0.3 | 0.388 | 1.227 | 2.146 | 3.105 | 0.839 0.919 0.959 |
| 1 | 0.274 | 1.090 | 2.049 | 3.033 | 0.817 0.959 0.984 |
| 1000 | 0.010 | 1.000 | 2.000 | 3.000 | 0.990 1.000 1.000 |

Only a perfect short or open is dispersionless. Consequences: (i) exact
self-phase-matching is lost — one pair can be matched and the mismatch of the others
grows with their distance from it, so which pairs participate is set by that mismatch
against the linewidth (a TWPA-style phase-matching question); (ii) the $n = 0$ free
mode acquires a finite frequency; (iii) the macro's comb must use the loaded-line
roots, not $n\,\mathrm{FSR}$. The oracle already does this: `Km` carries the static
$\mathbf{u}\mathbf{u}^{\mathsf T}/L_0$ term.

## 5. The reduction viewpoint (treating the termination as a node)

Take the terminal flux $\Phi(\ell)$ as the one variable of interest and
Schur-complement the comb out. The result is the line's end impedance, and it has a
closed form:

$$
Z_\mathrm{end}(\omega) = -i Z_\mathrm{tx}\cot(k\ell)
 = -i Z_\mathrm{tx}\left[\frac{1}{k\ell} + \sum_{n\ge 1}\frac{2k\ell}{(k\ell)^2 - n^2\pi^2}\right].
$$

The bracket is the Mittag-Leffler partial-fraction expansion of $\cot$, one term per
comb mode. Numerically the $N$-mode comb reproduces $\cot(k\ell)$ with maximum error
$4.8\times 10^{-1}$ ($N = 5$), $1.1\times 10^{-1}$ (20), $2.8\times 10^{-2}$ (80),
$7.0\times 10^{-3}$ (320) — the $\sim 1/N$ tail, the same residual the ABCD study
attributed to the truncated comb. So "Kron-reducing the line away" is exact and
closed-form for the static line: it *is* the transcendental boundary condition, and
the comb is its truncated expansion.

Two remarks on modelling the inductor as a graph node with $\omega_0 = 0$. A bare
inductor to ground is not a mode — it has no capacitance and nothing to oscillate —
so such a node is really the terminal flux carrying a **frequency-dependent
self-energy** $Z_\mathrm{end}(\omega)$ from the reduced line; specifying it by an
impedance and a slope sign is Foster's reactance theorem, i.e. the Phase-2
"$\lambda(\omega)$ / connector embedding" item. For the pumped case the reduction
leaves a $2\times 2$ signal/idler problem in $Z_\mathrm{end}(\omega)$ and
$Z_\mathrm{end}(\omega_p - \omega)^*$ coupled by $\delta$ — the classical
boundary-condition treatment of a parametric resonator. The trade is clear: the
reduced form is closed-form and truncation-free but its matrix elements depend on
frequency, which the constant-$M$ solver (and $\det M$ stability analysis) cannot
take; the explicit comb keeps $M$ constant at the cost of $N$ modes and a $1/N$ tail.
The comb is the representation the app uses; the reduction is the analytic
cross-check.

## 6. The macro, its normalization, and what the oracle says

**Shipped.** A line's end can carry a *pumped termination* (`set_line_pump`;
right-click a line → *Add pumped termination…*). The app then holds a linked
**conjugate twin** — the same physical line seen in the idler sector: its own
position, rotation and appearance, physics mirrored from the primary — with its
own port glyph(s) mirroring the primary's terminations, and draws one
**double-line pump bus** between the pumped ends. At extraction the bus becomes
the rank-one block: every signal-comb mode $n$ to every twin mode $m$ with

$$
\text{rate}_{nm} = \text{rate}\cdot w_n w_m,\qquad
w_n = \Big(\tfrac{n}{n_\mathrm{ref}}\Big)^{\mp 1/2},\qquad
\text{phase}_{nm} = \phi_p + \arg\big(u_n(x_0)\,u_m(x_0)\big),
$$

the exponent $-\tfrac12$ for a modulated inductor (flux couples, $g_n \propto
1/\sqrt{\omega_n}$) and $+\tfrac12$ for a modulated capacitor. The user's
`rate` is the coupling at the reference pair $(n_\mathrm{ref}, m_\mathrm{ref})$,
$m_\mathrm{ref}$ being the harmonic nearest $\omega_p - \omega_{n_\mathrm{ref}}$
(the idler partner; the dialog shows it and its mismatch). The DC comb mode is
excluded on both combs, as for taps. Ports stay one hub column per sector.

**Two core fixes the macro forced.** (i) The spanning tree stored each hop as
its canonically *sorted* pair while the frame accumulation read it as
parent→child, so a hop traversed toward a smaller id credited the pump offset
to the parent and left the child with *no frame* (silently the root drive).
Static graphs never noticed (all offsets zero); a pumped comb of string ids
did. Tree edges are now oriented by traversal. (ii) The extractor orients a
pumped edge by comparing natural frequencies (`eff_to > eff_from`); a twin's
negative-frequency member defeats that. Bus edges carry an explicit
`frame_rule = 'sector'`: crossing into the conjugate sector is $-\omega_p$,
whatever the members' frequencies. Hand-drawn edges keep the heuristic.

**Normalization, pinned.** Deriving the rate from the circuit (natural units
$v=\ell=Z_\mathrm{tx}=1$, so $\omega_n = n\pi$, $C_n = \tfrac12$): with
$\varphi_n = \mathrm{Re}[A_n e^{i\omega_n t}]$ the modulated term
$\Delta K_{nm}\cos(\omega_p t)\,\varphi_m$ in $C\ddot\varphi + K\varphi = 0$ gives,
after the rotating-wave step and $a_n = A_n\sqrt{C_n\omega_n/2}$,

$$
\dot a_n = i\,g_{nm}\,a_m^*,\qquad
g_{nm} = \frac{\Delta K_{nm}}{4\sqrt{\omega_n C_n\,\omega_m C_m}},\qquad
\Delta K_{nm} = \delta\!\left(\tfrac{1}{L}\right) u_n(x_0)\,u_m(x_0).
$$

The app's off-diagonal is $\beta = \text{rate}/2$ in linear-frequency units and
the line's unit map is $\omega = n\pi \leftrightarrow f = n\,\mathrm{FSR}$, so

$$
\boxed{\ \text{rate} = \frac{2\,\mathrm{FSR}}{\pi}\,g_{nm}\ }
$$

Tested against `build_galvanic` + `hb_signal_idler` with negligible static
loading ($L_J = 10^4$, so the oracle comb is the open–open one) and the port at
$x = \ell$, comparing $|S_{ss}|^2$ and the photon-flux idler transmission
$(\omega_s/\omega_i)\,|S_{is}|^2$ (`misc/pumped_termination_checks.py`,
`tests/test_pumped_line.py`):

| regime | $\delta(1/L)$ | oracle peak gain | graph | max rel. dev. $\lvert S_{ss}\rvert^2$ | idler |
|---|---|---|---|---|---|
| isolated modes, $Z_0 = 10 Z_\mathrm{tx}$, $N=12$ | 1.0 | 5.02 dB | 5.04 dB | $3.2\times10^{-3}$ | $4.7\times10^{-3}$ |
| same, $N = 48$ | 1.0 | 5.02 dB | 5.03 dB | $2.3\times10^{-3}$ | $3.3\times10^{-3}$ |
| near threshold, $N=24$ | 2.5 | 11.21 dB | 11.12 dB | $2.0\times10^{-2}$ | $2.2\times10^{-2}$ |
| overlapping, matched port $Z_0 = Z_\mathrm{tx}$, $N=48$ | 6.0 | 1.84 dB | 1.97 dB | $3.3\times10^{-2}$ | $9.7\times10^{-2}$ |

The alternatives $\tfrac12\times$ and $2\times$ this rate miss by 50–100 %, so the
constant is identified, not fitted. The residual floor in the isolated regime is
the **DC mode**: the oracle pumps it (with $\omega_0 \to 0$ its inductive
coupling is large) while the macro excludes it; in the overlapping regime the
missing **tail closure** adds to that (the oracle closes its comb with two tail
tanks, the macro does not), and both residuals fall with $N$. Both are the
known Phase-1 truncation items, now quantified for the pumped case.

**Still open.** Loaded-line roots (§4 dispersion) in the macro; the DC mode's
pumped coupling (needs the loaded $\omega_0$); tail closure; node taps on a
pumped line (the tapped mode would need its own idler-sector copy — the "is
the same port connected to signal and conjugate?" question); and the
$\det M$ / Routh–Hurwitz stability flag, which the near-threshold row above
shows is not optional.
