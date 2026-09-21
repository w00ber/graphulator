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

| term | slow when | process | graph edge | coupling |
|---|---|---|---|---|
| $a_n^* a_m^*\,e^{-i\omega_p t}$ + c.c. | $\omega_n + \omega_m = \omega_p$ | amplification (sum-frequency) | non-conjugate $\leftrightarrow$ conjugate | anti-Hermitian |
| $a_n^* a_m\,e^{\mp i\omega_p t}$ + c.c. | $\omega_n - \omega_m = \pm\omega_p$ | conversion (difference-frequency) | non-conjugate $\leftrightarrow$ conjugate, *negative-frequency member* (§4) | **Hermitian** |

One pump therefore drives both families at once, through one outer product.

The last column is not decoration. Both families ride the same cross-cluster
edges, so the cluster flag cannot tell them apart — the **sign of the twin
member** does, through the sector
$s = (-1)^{\texttt{conj}\,\oplus\,\texttt{counter\_rotating}}$, and the
coupling obeys $M_{kj} = s_j s_k \overline{M_{jk}}$. Assembling every
cross-cluster edge as anti-Hermitian makes a conversion-only pump amplify:
against the oracle in the conversion band it returned $\max|S_{ss}|^2 = 4.58$
where the circuit gives $0.999$. Derivation, matrices and oracle numbers:
`docs/pump_sector_rule.md`.

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
$\omega \pm \omega_p$.

**Which frame the twin takes.** The frame $\omega_p - \omega$ holds
amplification and down-conversion; *up*-conversion of a signal below the pump
($\omega_m - \omega_n = \omega_p$) is the rung at $\omega + \omega_p$, which
that frame reaches only at $-\omega$ — off the sweep. A two-frame truncation
cannot hold both, so the pump macro puts the twin in the frame of the pair the
rate is **anchored** to: the partner of $n_\mathrm{ref}$ closest to resonance
under the pump (ties: amplification, then down-, then up-conversion, which
reproduces the historical anchoring on a harmonic comb). Frame rule `sector`
is $\omega - \omega_p$, `sector+` is $\omega + \omega_p$; the two give
$S(\omega) = \overline{S(-\omega)}$ to machine precision, and the Ports &
Lines panel names the frame and marks the partners it cannot show. The
SQUID-terminated $\lambda/4$ scenes (`INTERMODE_LEE2013_*`, File → Test)
are the worked case: the conversion "hole" of that experiment is an
up-conversion and lives in `sector+`. The DC-complete $\pm n$ comb — the two partial fractions of each
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
**triple-line pump bus** between the pumped ends (§7.6). At extraction the bus becomes
the rank-one block: every signal-comb mode $n$ to every twin mode $m$ with

$$
\text{rate}_{nm} = \text{rate}\cdot w_n w_m,\qquad
w_n = \Big(\tfrac{n}{n_\mathrm{ref}}\Big)^{\mp 1/2},\qquad
\text{phase}_{nm} = \phi_p + \arg\big(u_n(x_0)\,u_m(x_0)\big),
$$

the exponent $-\tfrac12$ for a modulated inductor (flux couples, $g_n \propto
1/\sqrt{\omega_n}$) and $+\tfrac12$ for a modulated capacitor. The DC comb mode
is excluded on both combs, as for taps. Ports stay one hub column per sector.

**What the number means: a pair anchor, and a geometric mean.** The profiles
are normalized to weight 1 at the reference mode on each comb, so
$w_{n_\mathrm{ref}} = w_{m_\mathrm{ref}} = 1$ and the user's `rate` **is** the
coupling at the pair $(n_\mathrm{ref}, m_\mathrm{ref})$ exactly — not a bare
coefficient. ($m_\mathrm{ref}$ is derived: the twin mode nearest
$|\omega_p - \omega_{n_\mathrm{ref}}|$, i.e. the one the pump pairs resonantly
with $n_\mathrm{ref}$; the panel names it and gives the residual detuning.)

The scaling to every other pair is a **geometric mean of per-mode
participations**, as the circuit form below requires. Writing
$\tilde w_n = u_n(x_0)/\sqrt{\omega_n C_n}$, the normalization result
$g_{nm} = \tfrac14\,\delta(1/L)\,\tilde w_n\tilde w_m$ factorizes, so with
$p_n \equiv \tilde w_n^2 = u_n(x_0)^2/(\omega_n C_n)$ — mode $n$'s participation
in the modulated element —

$$
\frac{\text{rate}_{nm}}{\text{rate}_{n_\mathrm{ref}m_\mathrm{ref}}}
= \sqrt{\frac{p_n\,p_m}{p_{n_\mathrm{ref}}\,p_{m_\mathrm{ref}}}} .
$$

On the open–open comb $C_n$ is $n$-independent, so $p_n \propto 1/n$ (inductive)
or $\propto \omega_n$ (capacitive) and this collapses to
$\text{rate}\,\sqrt{n_\mathrm{ref}m_\mathrm{ref}/(nm)}$ and its inverse — the
$w_n w_m$ shorthand above. On a **loaded** line the $p_n$ carry the dispersed
$C_n$ and $u_n(x_0) = \cos k_n\ell$, which is why the code evaluates the general
form rather than the harmonic ratio (§7.4).

One consequence worth stating: the anchor is a *pair*, so the quantity invariant
under re-anchoring is the **device** $\delta(1/L)$, not the number in the box.
Changing $n_\mathrm{ref}$ while holding `rate` fixed rescales the entire block by
$\sqrt{p_{n_\mathrm{ref}}p_{m_\mathrm{ref}}/p_{n'_\mathrm{ref}}p_{m'_\mathrm{ref}}}$
— i.e. it re-specifies the modulation depth. Parameterizing by $\delta(1/L)$
directly would remove the anchor at the cost of a number less comparable to an
ordinary graph edge's rate; the app keeps the pair anchor and reports the pair.

**The modulation depth behind the rate.** A rate in arb. units says little about
how hard the element is driven. The physically readable version is the
participation-weighted *fractional* modulation. Writing $\beta = \delta(1/L)L_J
= \delta L_J/L_J$ for the element's own modulation and

$$
p_n \;=\; \frac{u_n(x_0)^2}{\omega_n^2 C_n L_J}
\;=\; \frac{\text{inductive energy of mode }n\text{ in }L_J}{\text{its total inductive energy}}
$$

for mode $n$'s participation in the element, the same factorization gives

$$
\boxed{\ \varepsilon_{nm} \;\equiv\; \frac{4\,g_{nm}}{\sqrt{\omega_n\omega_m}}
\;=\; \beta\,\sqrt{p_n\,p_m} \;=\; \frac{\delta L_J}{L_\mathrm{tot}},
\qquad L_\mathrm{tot} \equiv \frac{L_J}{\sqrt{p_np_m}}\ }
$$

$L_\mathrm{tot}$ being the pair's effective inductance referred to the element,
and $\varepsilon = \beta p_n$ exactly for a degenerate pump. Because the left
side is dimensionless it may be evaluated in the app's linear units, where
$g_\mathrm{lin} = \text{rate}/2$:

$$
\varepsilon = \frac{2\,\text{rate}}{\sqrt{f_n f_m}} .
$$

Verified against `build_galvanic`'s independently known $(\delta(1/L), L_J,
\omega_n, C_n)$ to twelve digits. The panel and the bus Properties page report
it beside the rate as $\delta L/L_\mathrm{tot}$ (a modulated capacitor gives the
same expression read as $\delta C/C_\mathrm{tot}$, frequency-independent as a
capacitance ratio must be).

Note $\varepsilon$ is *pair-referred*, like the rate: $p_n \propto 1/n^2$ on the
open–open comb, so $\varepsilon \propto 1/nm$ while the rate goes as
$1/\sqrt{nm}$. What it buys is dimensionlessness — it compares against a design
target directly. The genuinely anchor-free number is $\beta$ itself, which
requires $L_J$ and is therefore available only once the end load is specified
(§7.2 gives $L_J = Z_\mathrm{tx}/2\pi f_Z$).

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

## 7. Parameterizing the loaded line

§4 showed the termination *disperses* the comb; §6 measured the cost of ignoring
it. This section settles how the load is specified, and reports what is verified
so far. Numbers here come from `misc/loaded_line_checks.py`.

### 7.1 Why the reactance is the right handle, and why not its sign

Whatever the element, the source-free condition at a shunt termination is

$$
Z_\mathrm{line}(\ell) + Z_\mathrm{elem} = 0
\quad\Longleftrightarrow\quad
\cot(k\ell) = \frac{\omega L}{Z_\mathrm{tx}}\ \ \text{(inductive)},\qquad
\cot(k\ell) = -\frac{1}{\omega C\,Z_\mathrm{tx}}\ \ \text{(capacitive)},
$$

verified against the raw admittance $Y_\mathrm{line} + Y_\mathrm{elem}$ to
$\sim10^{-14}$ for both types. So *one* frequency-dependent number, the
normalized reactance, sets the whole basis.

It is tempting — and it was the first proposal — to let the **sign** of that
reactance pick the element type. Two reasons not to:

1. **The project's sign convention is not the textbook one.** `cmtline_core`
   declares `Z_ind = -1j*w*L` and `Z_cap = +1j/(w*C)` (JAA, $e^{+i\omega t}$),
   so here an *inductor* has negative reactance and a *capacitor* positive —
   the opposite of the usual reading. A bare signed field would be a standing
   trap. (The resonance condition above is of course convention-independent.)
2. A sign only works for a *one-element* reactance. The moment the termination
   is a series LC or any richer Foster network, sign no longer determines the
   frequency dependence, and that is the Phase-2 $\lambda(\omega)$ /
   connector-embedding item.

So the load is stored as **an explicit type plus one magnitude**, and for a
pumped termination the type is already known: the modulated element *is* the
load, so `pump['coupling']` names it.

### 7.2 The magnitude: one frequency

Store the magnitude as $f_Z$, **the frequency at which $\lvert X_\mathrm{elem}\rvert = Z_\mathrm{tx}$**
($f_Z = Z_\mathrm{tx}/2\pi L$ inductive, $1/2\pi C Z_\mathrm{tx}$ capacitive). Then

$$
x(f) \equiv \frac{X_\mathrm{elem}}{Z_\mathrm{tx}} = \frac{f}{f_Z}\ \ \text{(inductive)},
\qquad -\frac{f_Z}{f}\ \ \text{(capacitive)},
$$

in absolute frequency with **no reference frequency to agree on**. That matters:
the obvious alternative — "the reactance at the fundamental" — is circular once
the user wants to specify a *target* resonance, because the loaded fundamental
is what we are solving for. $f_Z$ has no such loop, and it is physically
readable: an inductor looks like a short below $f_Z$ and an open above it.

### 7.3 Solving for the length from a target resonance

This is the ergonomic request: specify the **loaded** resonance and let the app
find the line. Evaluating the condition *at* the target gives a closed form —
no iteration:

$$
\boxed{\ \mathrm{FSR} = \frac{\pi f_\mathrm{target}}{\operatorname{arccot}\big(x(f_\mathrm{target})\big) + (n-1)\pi}\ }
\qquad \operatorname{arccot} \in (0,\pi),
$$

for putting the $n$-th loaded mode at $f_\mathrm{target}$ ($n = 1$ is the
quarter-wave-like fundamental). Verified to $<10^{-15}$ for both element types
across $f_Z$ spanning two decades. The resulting ratio $f_1/\mathrm{FSR}$ shows
where you are between the two limits:

| | $f_Z \to \infty$ | $f_Z$ moderate | $f_Z \to 0$ |
|---|---|---|---|
| inductive | $f_1/\mathrm{FSR} \to 1/2$ (quarter-wave, end shorted) | 0.15–0.47 | $\to 0$ (end open; the mode becomes the free DC mode) |
| capacitive | $f_1/\mathrm{FSR} \to 1$ (open–open half-wave) | 0.55–0.97 | $\to 1/2$ (end shorted) |

Note FSR then means *the geometric parameter* $v/2\ell$, not the literal mode
spacing — the loaded spacings are not uniform. The UI should say so.

### 7.4 The loaded mode quantities

With the port at the open end $x = 0$ and the element at $x = \ell$, the modes
are still $u_n(x) = \cos(k_n x)$, now at the loaded roots, and three things
change together:

$$
\omega_n:\ \cot(k_n\ell) = x(\omega_n), \qquad
u_n(\ell) = \cos(k_n\ell), \qquad
C_n = \frac{1}{Z_\mathrm{tx}v}\!\left[\frac{\ell}{2} + \frac{\sin 2k_n\ell}{4k_n}\right] + C_\mathrm{elem}\,u_n(\ell)^2 ,
$$

the last term present **only for a capacitive load**: a shunt capacitor's energy
$\tfrac12 C\dot\Phi(\ell)^2$ is *kinetic*, so it adds to the mode's mass, while
an inductor's $\tfrac12\Phi(\ell)^2/L$ is potential and is already accounted for
by the eigenvalue. The port rate follows from the same normalization,

$$
\gamma_n = \frac{u_n(0)^2}{2\pi Z_0 C_n},
$$

which reproduces the open–open result $\gamma/\mathrm{FSR} = (2/\pi)(Z_\mathrm{tx}/Z_0)$
exactly, and is now **mode-dependent** — one more thing the open–open basis gets
wrong.

The DC mode differs by type, which resolves the §6 open item: an **inductive**
load shorts DC, so the free $n=0$ mode is *gone* (replaced by the quarter-wave
mode); a **capacitive** load is an open at DC, so it *survives*, with
$C_0 = c\ell + C_\mathrm{elem}$.

### 7.5 Status: inductive implemented, capacitive refused

Feeding these quantities into the ordinary hub pipeline and comparing the
complex $S_{11}$ against exact ABCD (JAA convention, matched port), the
**inductive** case converges exactly like the open–open macro does:

| | $N=10$ | $N=20$ | $N=40$ | $N=80$ | ratios |
|---|---|---|---|---|---|
| open–open (existing test, for reference) | 1.112 | 0.537 | 0.268 | 0.134 | ~2 |
| inductive, $\omega_Z = \pi$ | 1.260 | 0.569 | 0.276 | 0.137 | 2.21 / 2.06 / 2.02 |
| inductive, $\omega_Z = 0.3\pi$ | 1.256 | 0.566 | 0.275 | 0.136 | 2.22 / 2.06 / 2.02 |

i.e. $\sim 1/N$, residual = the truncated tail, same as the unloaded macro. The
loaded inductive basis is therefore verified — and it is the case the pumped
termination needs, since a modulated inductor is the device.
(`tests/test_loaded_line.py` re-measures the same ladder through the shipped
macro and reproduces it to the printed digits.)

The **capacitive** case is not closed: adding the surviving DC mode took the
error from 1.78 to 1.28 and the element's kinetic term took it to 0.94, but it
**plateaus** with $N$ instead of falling. A residual that does not shrink with
mode count is a *direct* (non-resonant) term — a Foster pole at infinity that no
finite sum of resonators reproduces — so something in the capacitive termination
must be represented outside the comb. That is an open item, not a mystery in
principle, but it is not verified and must not ship as if it were.

**What shipped.** `LineResonator` takes an opt-in
`load = {'end', 'type', 'f_Z'}` (default `None` = both ends open, which
reproduces every pinned golden bit-for-bit and is itself the $f_Z \to 0$
inductive limit). When it is set, the comb is re-derived on the loaded basis:
roots by bisection on the pole-free residual
$s\,(\cos\theta - x\sin\theta)$, $s = (-1)^{n-1}$, which is exactly $+1$ and
$-1$ at the ends of $((n-1)\pi, n\pi)$; the DC mode dropped; $u_n(\text{end})$,
$C_n$ and $\gamma_n$ from §7.4; and the tap/pump profiles rebuilt from
$(u_n, f_n, C_n)$ instead of the $(-1)^n/\sqrt{n}$ shorthand, which the
unloaded branch keeps. `line_fsr_for_target` exposes §7.3 in the line dialog,
the line's Properties page and the pump dialog. The table above is the gate,
`tests/test_loaded_line.py`.

Three things the loaded basis changed elsewhere, each a real defect rather
than a refactor:

* `N` now counts the modes that *reach* $f_\mathrm{max}$, not
  $\lceil f_\mathrm{max}/\mathrm{FSR}\rceil$ — identical unloaded, right when
  dispersed.
* `f_max >= FSR` was the wrong invariant for a loaded line: FSR is the
  geometric parameter $v/2\ell$ there and the fundamental can sit far below
  it (§7.3's table bottoms out at $f_1/\mathrm{FSR} \to 0$). It is now
  enforced only on the open–open comb.
* The idler partner is the mode nearest $f_p - f_n$, not $f_p - n\,\mathrm{FSR}$;
  on a dispersed comb those name different modes, and the rank-one block is
  built around whichever one is chosen.

The **capacitive** load is refused at construction with a message pointing
here, in the macro, the line dialog, the Properties page and the pump dialog
— listed and disabled rather than hidden, so the case is visibly open rather
than silently missing.

### 7.6 Visual language: the bus is always three strokes

The PRXQ graph language reserves a **single line** for conversion
(beam-splitter) coupling and a **double line** for amplification (two-mode
squeezing). A pump bus is neither: one pump on a comb drives both families at
once through the same rank-one block (§2), and silently getting conversion when
you only meant to amplify is a common and costly surprise. So the bus draws the
**union — three strokes, always**.

It is tempting to *compute* the count instead, showing one or two strokes when
only one family is "reachable". That was the first design here and it is wrong,
for two reasons:

1. **On a harmonic comb the families come together.** $\omega_n + \omega_m = \omega_p$
   and $|\omega_n - \omega_m| = \omega_p$ are satisfied by many pairs
   simultaneously (§4). Separating them takes deliberate dispersion engineering
   — a stepped-impedance resonator, or the loaded-line dispersion of this
   section — and at $\kappa \sim \mathrm{FSR}$ a near-resonant partner is
   within a linewidth regardless. A glyph that reports selectivity the device
   does not have is exactly the error the triple line exists to prevent.
2. **A band-edge reachability test measures $f_\mathrm{max}$, not the device.**
   Worse than imprecise: it is not about the physical line at all. With
   $\mathrm{FSR} = 1.5$ and $f_p = 9$, the same line and pump report

   | $f_\mathrm{max}$ | 6.0 ($N{=}4$) | 9.0 ($N{=}6$) | 12.0 ($N{=}8$) | 18.0 ($N{=}12$) |
   |---|---|---|---|---|
   | families "reachable" | amp | amp | amp + conv | amp + conv |

   because the conversion partners at $f_p + f_m = 10.5, 12, \dots$ are *real
   modes of the line* ($10.5 = 7\times\mathrm{FSR}$) that a short comb merely
   omits. Nothing about the device changed between those columns.

What that test *is* good for is the question it actually answers: **is
$f_\mathrm{max}$ big enough for this pump?** `pump_truncation_gaps` reports a
family when the truncated comb holds **no** partner for it while the line does
— conversion when $f_p + \mathrm{FSR} > N\,\mathrm{FSR}$, amplification when
$f_p > 2N\,\mathrm{FSR}$ (a pump below $2\,\mathrm{FSR}$ has no amplification
pair in the line either, so that is a real absence and is not flagged). It
surfaces as a "raise f_max" warning on the bus's Properties page and in the
Ports & Lines row, never as a change to the glyph.

## 8. Truncating the comb — and closing what you cut off

*The full, self-contained derivation of the closure — equations of motion,
the Schur step written out, the Sherman–Morrison identity check, the
multi-channel form, and what is dropped — is `docs/comb_tail_closure.md`.
This section keeps the measurements and the result.*

Every macro in this note keeps $N$ pole pairs. §6 and §7 measured the cost of
that in the whole-band maximum; this section asks the question a user actually
has — *how wrong is the plot I am looking at, near the modes I care about?* —
and then removes the question. Numbers from `misc/comb_truncation_checks.py`.

### 8.1 The error is the reactive tail, and it is all in the phase

For a lossless one-port $|S_{11}| \equiv 1$, so truncation cannot show up in a
dB plot at all: what it moves is *where the resonances sit*. Inside a window of
$\pm\mathrm{FSR}/2$ around mode $n_w$, the complex error against exact ABCD is

| $\gamma/\mathrm{FSR}$ | window | $N{=}n_w{+}1$ | $n_w{+}4$ | $n_w{+}16$ | $n_w{+}64$ | $\ \varepsilon N\big/\big[(\gamma/\mathrm{FSR})(f/\mathrm{FSR})\big]$ |
|---|---|---|---|---|---|---|
| 0.828 | mode 1 | 0.977 | 0.450 | 0.142 | 0.038 | 2.4 → 3.0 |
| 0.828 | mode 3 | 1.291 | 0.771 | 0.297 | 0.086 | 2.1 → 2.3 |
| 0.318 | mode 1 | 0.421 | 0.177 | 0.055 | 0.015 | 2.6 → 3.0 |
| 0.064 | mode 3 | 0.130 | 0.064 | 0.023 | 0.007 | 2.7 → 2.3 |

i.e. one law across two decades of coupling,

$$
|\Delta S| \;\approx\; 2.5\,\frac{\gamma}{\mathrm{FSR}}\,\frac{f}{\mathrm{FSR}}\,\frac{1}{N},
$$

linear in the coupling, linear in the frequency you look at, and only $1/N$ in
the comb size. That is the tail of the Mittag-Leffler sum: the modes beyond $N$
contribute $\sum_{n>N}\gamma\,[\,(f-nF)^{-1}+(f+nF)^{-1}] \approx -2\gamma f/(F^2 N)$,
a *reactive* load on the port that shifts every in-band resonance by a fraction
of its linewidth. This is why "adequate $N$" felt high: at $\gamma/\mathrm{FSR}
\approx 0.83$ and $f \approx 6\,\mathrm{FSR}$, 5 % accuracy needs $N \approx 250$.

### 8.2 Closing the tail exactly

But the *full* sum is known in closed form. A one-port line's reflection depends
on its modes only through the scalar $\chi(f) = \sum_n \kappa_n^2/(f - f_n)$,
$S = (i\chi/2 - 1)/(i\chi/2 + 1)$ — and that scalar is the line's input impedance,

$$
\chi(f) = -\frac{2i}{Z_0}\,Z_\mathrm{in}(f),\qquad
Z_\mathrm{in}^{\text{open–open}} = iZ_\mathrm{tx}\cot(k\ell)
\;\Rightarrow\; \chi = \frac{\gamma}{F}\,\pi\cot\!\big(\pi f/F\big),
$$

whose partial sums *are* the comb. So the tail is simply $\chi_\text{exact} -
\chi_\text{kept}$, for the unloaded line, the loaded line (ABCD with the
reactance), a lossy line ($f \to f + iB_\text{int}/2$), and a port at the loaded
end ($Z_L \parallel Z_\text{line}$) alike — no asymptotics, no digamma.

Eliminating the tail modes from the coupled-mode equations is then a Schur
complement, exact because they touch the rest of the graph only through the hub
column. With $u \equiv \kappa^\dagger a$ the port field and $\chi_t$ the tail
sum, the tail equation gives $\kappa_t^\dagger a_t = \chi_t\,(b_\mathrm{in} -
\tfrac{i}{2}u)$, and everything collapses into one scalar per channel,

$$
\lambda(f) = \frac{1}{1 + i\chi_t(f)/2}:\qquad
\big[D_k + \tfrac{i}{2}\lambda\,\kappa_k\kappa_k^\dagger\big]a_k = \lambda\,\kappa_k\,b_\mathrm{in},\qquad
S = -\frac{1 - i\chi_t/2}{1 + i\chi_t/2} + i\,\lambda^2\,\kappa_k^\dagger
\big[D_k + \tfrac{i}{2}\lambda\,\kappa_k\kappa_k^\dagger\big]^{-1}\kappa_k .
$$

The hub's damper in $M$ is scaled by $\lambda$, its $K$ column by $\lambda$ on
both sides, and the direct reflection acquires a phase. $\operatorname{Re}\lambda
< 1$ says the tail *steals* part of the port coupling; $\operatorname{Im}\lambda$
is the reactive shift of §8.1, now carried exactly. Channels without a tail have
$\lambda = 1$ identically, so graphs without lines are assembled bit-for-bit as
before (the golden suite pins this).

**It is an identity.** With the closure, against exact ABCD:

| | $N{=}2$ | $N{=}4$ | $N{=}10$ | raw comb at $N{=}10$ |
|---|---|---|---|---|
| open–open | 1.5e-15 | 1.7e-15 | 2.0e-15 | 1.11 |
| inductive load, $f_Z = 0.5\,\mathrm{FSR}$ | 1.2e-15 | — | 2.1e-15 | 1.21 |
| inductive load, $f_Z = 0.15\,\mathrm{FSR}$ | 9.0e-16 | — | 2.1e-15 | 1.25 |
| port at the loaded end | 8.0e-16 | — | 2.3e-15 | 1.24 |

and the dilated $S_\text{full}$ stays unitary to $10^{-15}$. Two ends of
different lines on one hub close both tails into the one channel (`tests/test_tail_closure.py`).
One numerical care point: exactly on a kept pole, $\chi_\text{exact}$ and
$\chi_\text{kept}$ are both infinite while their difference is smooth, so within
$10^{-5}\,\mathrm{FSR}$ of a kept pole the tail is taken as the mean of its two
symmetric guard-band values (the linear term cancels; the residual is
$\sim10^{-10}$, and on-pole sweep points come out at $9\times10^{-16}$).

### 8.3 What the closure does not carry, and what $N$ is now for

The tail modes also carry the *other* couplings — pump edges and taps onto modes
beyond $N$. The closure drops those; they are second order in the coupling rate
and fall with $N$ themselves. On the pumped line of §6 (oracle: `build_galvanic`
+ `hb_signal_idler`, gain peak 3.18), the relative gain error is

| $N$ | 4 | 6 | 8 | 12 |
|---|---|---|---|---|
| raw comb | 7.4e-3 | 4.9e-3 | 4.0e-3 | 3.2e-3 |
| tail closed | 3.3e-3 | 2.6e-3 | 2.3e-3 | 2.1e-3 |

The closed residual sits on the $\sim 2\times10^{-3}$ floor of §6 — the oracle's
pumped DC mode, which the macro excludes — from $N = 4$ on. So **$N$ no longer has
to span the modes that load the port; it only has to span the modes whose pump
or tap couplings matter**, and the honest way to know whether it does is to
measure it: the Ports & Lines panel's *Check truncation (2× f_max)* re-solves the
graph with every comb doubled and reports the largest change of each displayed
trace over the window. For a plain terminated line that number is $10^{-15}$
with the closure and $\sim 1$ without; for a pumped line it is the second-order
tail above. The closure is on by default and can be switched off there to see
the raw truncated comb — which is what every table in §6 and §7 measured.

## 9. Stepped-impedance lines

§7 assumed one characteristic impedance. Real resonators are often *stepped* —
the experiment of Lee, Spietz & Aumentado (2013) uses two CPW sections,
$\approx 47.3\,\Omega$ over two thirds of the length at the port and
$\approx 51.4\,\Omega$ over the third at the SQUID, precisely to move the first
harmonic off $3 f_A$ so that the conversion pump $f_B - f_A$ separates from the
degenerate-gain pump $2 f_A$. A uniform-line model cannot represent that, and
substituting an *effective* load to hit the measured frequencies gets them right
by distorting the mode profiles at the element, the participations and the port
linewidths up the ladder — the very quantities the multimode model exists to get
right. So the basis is generalized. Numbers here come from
`misc/stepped_line_checks.py`; the gate is `tests/test_stepped_line.py`.

### 9.1 Parameterization

`sections = [{'Z': Z_1, 'frac': s_1}, …]` ordered from $x_0$ to $x_L$, the $s_j$
fractions of the **electrical** length (normalized to sum to 1). Phase velocity
is taken common to all sections — the CPW-on-one-substrate case; a per-section
$v$ would only rescale the fractions. `sections = None` is the uniform line,
bit-for-bit. With sections, $Z_\mathrm{tx}$ becomes the **reference** impedance
the load's $f_Z$ is defined against ($L = Z_\mathrm{tx}/2\pi f_Z$), so the
physical element keeps its meaning when the line around it is stepped.

### 9.2 The piecewise standing wave

Carry the state $(u, w)$ along the line, $u$ the voltage (flux-rate) amplitude
and $w = Z_j^{-1}\,du/ds$ the current amplitude, $s$ the electrical distance.
Both are continuous across a step (voltage and current are), and inside a
section of impedance $Z_j$ they rotate,

$$
u(s) = u_0\cos s + Z_j w_0 \sin s,\qquad
w(s) = -\frac{u_0}{Z_j}\sin s + w_0\cos s .
$$

Start at the open end with $(u, w) = (1, 0)$ and propagate through the sections
to $\theta = k\ell$. The source-free condition at the far end is

$$
\text{open:}\ \ w(\theta) = 0,\qquad
\text{inductive:}\ \ u(\theta) + Z_\mathrm{tx}\,x(f)\,w(\theta) = 0,\quad x = f/f_Z ,
$$

which for one section is $\cos\theta - x\sin\theta$, the pole-free form of §7.
The residual is smooth, so the roots $\theta_n$ are found by a sign scan (fine
relative to the shortest section) and bisection to adjacent floats; they are
**not** one per $\pi$ interval any more, so they are counted rather than indexed.
An inductive load still shorts DC; an open–open stepped line keeps the free
mode with $C_0 = \sum_j s_j/(2 Z_j\,\mathrm{FSR})$ and, since it has no
negative-frequency partner, the residue $\kappa_0^2 = 1/(\pi Z_0 C_0)$ — twice
the $n \ge 1$ form — which reproduces the uniform comb's DC coupling exactly.

### 9.3 Normalization and the mode quantities

The mode mass is the capacitive energy summed over sections, in closed form:
with $a_j = u_0$, $b_j = Z_j w_0$ at the start of section $j$ and $\delta_j =
\theta_n s_j$ its electrical length,

$$
C_n = \sum_j \frac{1}{2 Z_j\,\mathrm{FSR}\,\theta_n}
\left[ a_j^2\!\left(\tfrac{\delta_j}{2} + \tfrac{\sin 2\delta_j}{4}\right)
     + b_j^2\!\left(\tfrac{\delta_j}{2} - \tfrac{\sin 2\delta_j}{4}\right)
     + a_j b_j\,\tfrac{1 - \cos 2\delta_j}{2} \right] ,
$$

which reduces to $C_\mathrm{line}\,(\tfrac12 + \sin 2\theta/4\theta)$ for one
section. Checked against an adaptive quadrature of $c(x)\,u_n^2$ section by
section: agreement to $2\times10^{-16}$. Everything downstream is unchanged in
form: $u_n(\text{end})$ from the propagated state, $\gamma_n = u_n(\text{port})^2
/ 2\pi Z_0 C_n$, the participation $p_n = u_n(\ell)^2/\omega_n^2 C_n L$, the tap
and pump profiles through the same three quantities.

### 9.4 The exact input impedance is the cascade

`input_impedance` becomes the product of the sections' ABCD matrices,
$\prod_j \begin{pmatrix}\cos\delta_j & -iZ_j\sin\delta_j\\ -i\sin\delta_j/Z_j & \cos\delta_j\end{pmatrix}$
walking away from the port end, terminated in the load or left open. Since the
tail closure (§8) is "exact minus kept", it carries over with no other change.

### 9.5 Verification

All against an **independent** reference — `cmtline_core.abcd_line` per section,
cascaded by hand and terminated in its `Z_ind` — never the macro's own
`input_impedance`.

*Roots.* For three geometries (two sections open–open; two sections with $L$ at
$x_L$; three sections with $L$ at $x_0$) every $\theta_n$ zeroes the cascade's
admittance numerator to $2\times10^{-13}$ of its value one part in $10^3$ away,
and a sign scan of that numerator finds exactly $N$ zeros.

*$S_{11}$* (30/80 Ω sections 0.4/0.6, $L$ at $x_L$ with $f_Z = 2.5\,\mathrm{FSR}$,
port at $x_0$):

| | $N=10$ | $N=20$ | $N=40$ | $N=80$ | ratios |
|---|---|---|---|---|---|
| closure off | $2.46\times10^{-1}$ | $1.16\times10^{-1}$ | $5.67\times10^{-2}$ | $2.80\times10^{-2}$ | 2.12 / 2.05 / 2.02 |
| closure on | $1.5\times10^{-15}$ | $1.4\times10^{-15}$ | $1.6\times10^{-15}$ | $2.1\times10^{-15}$ | — |

The truncated basis converges like $1/N$ exactly as the uniform and loaded ones
do (§7.5); with the tail closed the macro **is** the cascaded ABCD answer to
rounding at every $N$, and $|S_{11}| = 1$ to $10^{-15}$. Equal sections
reproduce the uniform line to $10^{-15}$, loaded or not.

*A prediction.* With the 2013 experiment's physical values only — 47.3 Ω over
$2/3$, 51.4 Ω over $1/3$, $L_\mathrm{SQ} = \Phi_0/2\pi I_\mathrm{SQ} = 0.401$ nH
from $I_\mathrm{SQ} = 0.82\,\mu$A — the stepped basis gives

$$
\frac{f_B}{f_A} = 3.089\qquad(\text{uniform line: } 3.004;\ \text{measured: } 3.077 \text{ at the bias of Figs. 3–4},\ \approx 3.095 \text{ at zero flux, Fig. 1b}),
$$

with nothing fitted: a 0.4 % first-principles account of the harmonic shift the
step was designed to produce. The `INTERMODE_LEE2013_*` test scenes (File → Test)
are built on this geometry.

### 9.6 Specifying a line by what it is: $Z\!:\!\theta^\circ$ at $f_\mathrm{ref}$

A line is physically a run of impedance $Z$ that is some number of degrees long
at a stated frequency. Asking the user instead for a *fraction* plus an FSR — or
worse, back-solving a length from a target resonance — states the same thing
less directly. So the input convention is

$$
Z_1\!:\!\theta_1,\ Z_2\!:\!\theta_2,\ \dots \quad\text{at}\quad f_\mathrm{ref},
$$

from which the stored quantities follow in closed form:

$$
\boxed{\ \mathrm{FSR} = \frac{180\,f_\mathrm{ref}}{\sum_j \theta_j^\circ}\ },
\qquad
\mathrm{frac}_j = \frac{\theta_j}{\sum_k \theta_k},
$$

because $\theta_j = 360 f_\mathrm{ref}\ell_j/v$ and $\mathrm{FSR} = v/2\ell_\mathrm{tot}$.
$\theta = 90^\circ$ is a quarter wave at $f_\mathrm{ref}$, $180^\circ$ a half wave.
A **single** section is not a stepped line at all — it is an ordinary uniform
line whose *length* was given as an angle, and its $Z$ becomes $Z_\mathrm{tx}$.

$(Z, \mathrm{frac})$ + FSR remains the canonical stored form. $f_\mathrm{ref}$
is an input and display convention only, carried per line and serialized, so
**re-quoting at a different $f_\mathrm{ref}$ changes the printed angles and
cannot move $S$** — gated by
`test_requoting_at_another_f_ref_cannot_move_S`, which pins every mode
frequency to bitwise equality across the change. A newly placed line inherits
the $f_\mathrm{ref}$ last edited on any line (falling back to 6), and that
sticky default is persisted to the user settings.

### 9.7 Composition: placing lines and joining them

A chain of sections joined end to end is **one resonator with one set of normal
modes**, not several coupled ones. The junction is a continuity condition —
voltage and current match across it — not a coupling rate, and each piece's own
standing-wave modes are the wrong basis for the composite. So joining two line
glyphs *composes* them into a single macro whose `sections` are their
impedances, which is the field §9.1 already defines; the drawing mechanic is a
front-end over it, not a second model.

Lengths add, so with $\ell = v/2\,\mathrm{FSR}$,

$$
\frac{1}{\mathrm{FSR}} = \frac{1}{\mathrm{FSR}_a} + \frac{1}{\mathrm{FSR}_b},
\qquad
\mathrm{frac}_j \leftarrow \mathrm{frac}_j\,\frac{\ell_\mathrm{piece}}{\ell_\mathrm{total}} ,
$$

and which ends are clicked sets the order of the section list and which two
ends stay free. Composing two pieces lands on *exactly* the line you would have
typed directly — verified bitwise on FSR and on every mode frequency, for all
four end pairings. Separating at a junction is the inverse and takes no
confirmation: each piece recovers its share of the length, and a piece left
with one section becomes an ordinary uniform line again.

The compound is **one object**: one label, one row in Ports & Lines, and the
junctions drawn on the glyph (the §9 band dividers already mark them).

**Junctions carry no attachments.** They are snap points for composition only,
and joining is refused at an end that holds a port, a tap, a pumped element or
the end load — the last because a shunt reactance *inside* the line makes the
structure a tree rather than a line. Two separate open cases sit behind that
refusal, and the message names both:

* **(A) a lumped device tapped at an interior point.** Tractable now: the tap
  profile becomes $u_n(s)$ at the tap position instead of $u_n(\text{end})$,
  and it is gateable against the reference's a-basis transform exactly as the
  end taps were (§ tap couplings).
* **(B) a stub.** Not tractable by the same move: the structure becomes a tree,
  so the modes come from a recursive $Y_\mathrm{in}$ built from the leaves with
  $Y_\mathrm{left} + Y_\mathrm{right} + Y_\mathrm{stub} = 0$ at the junction and
  the mass summed over branches — **not** a coupling matrix between two mode
  combs.

**What shipped.** `LineResonator(sections=…)`, `set_line_sections`, the
"Sections" field of the line dialog (`Z:frac, Z:frac` from $x_0$ to $x_L$, live
mode preview), the Ports & Lines summary, serialization, twin mirroring, code
export, and `line_fsr_for_target_general` (closed form when unloaded — $\theta_n$
is then geometric — bisection on FSR when loaded). Then §9.6: the
$Z\!:\!\theta^\circ$ at $f_\mathrm{ref}$ input convention
(`set_line_geometry_theta`, `set_line_fref`, sticky and persisted), and §9.7:
composition (`can_join_lines`, `join_lines`, `split_line_at_junction`,
`junction_points`, and the canvas gesture — click one line's end, then
another's, to join; click a junction to separate). Not shipped: per-section
phase velocity, per-section loss, a capacitive load (still §7.5), and
attachments at a junction (cases A and B above).
