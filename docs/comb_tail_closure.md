# Closing the truncated comb: an exact tail closure for transmission-line modes in coupled-mode theory

*Standalone derivation behind the "close comb tail analytically" model in the
paragraphulator. Conventions are those of the project's oracle,
`tests/cmtline_core.py` (JAA: $e^{+i\omega t}$, $Z_L = -i\omega L$,
$Z_C = +i/\omega C$); rates and frequencies are linear ($f$, not $\omega$),
matching the app. Every numbered claim is reproduced by
`misc/comb_truncation_checks.py` and pinned by `tests/test_tail_closure.py`.*

---

## 0. The result in one paragraph

A transmission-line resonator enters coupled-mode theory as a comb of modes,
and in practice the comb is truncated at $N$ pole pairs. The modes beyond $N$
are not negligible: they load the port with a reactive susceptibility
$\chi_t(f) \approx -2\gamma f/(\mathrm{FSR}^2 N)$ that shifts every in-band
resonance and makes the truncated model converge only as $1/N$. But those modes
couple to the rest of the system through *one* vector — the port column — so
they can be eliminated exactly. The elimination collapses them into a single
complex scalar per port channel,

$$
\lambda(f) = \frac{1}{1 + i\chi_t(f)/2},
$$

which multiplies the port's damper in the mode matrix and the port's coupling
column on both sides of the scattering formula, while the direct reflection
acquires the phase $\Lambda = (1 - i\chi_t/2)/(1 + i\chi_t/2)$. And $\chi_t$
itself is known in closed form, because the *full* comb sum is the line's exact
input impedance: $\chi_t = \chi_\text{exact} - \chi_\text{kept}$. With this
closure the port response of a one-port line is exact at **any** $N$ — $N = 2$
reproduces the ABCD reflection to $10^{-15}$ — and what $N$ still truncates is
only the tail modes' *other* couplings (pump edges, taps), which are second
order.

---

## 1. Coupled-mode equations with a dissipation hub

Take modes $a_n$ with (dressed) frequencies $f_n$ and internal loss $B_n$, and
one dissipation channel — a *port* — that damps them through a real coupling
vector $\kappa = (\kappa_n)$, in $\sqrt{\text{rate}}$ units. In the frequency
domain, driving the port with an incoming wave $b_\mathrm{in}$ at frequency
$f$,

$$
\Big(f - f_n + \tfrac{i}{2}B_n\Big)a_n + \sum_{m} E_{nm}\,a_m + \tfrac{i}{2}\,\kappa_n \sum_m \kappa_m^{*} a_m = \kappa_n\, b_\mathrm{in},
\qquad
b_\mathrm{out} = -\,b_\mathrm{in} + i\sum_n \kappa_n^{*} a_n .
$$

$E$ is the Hermitian matrix of conservative couplings (static or parametric
edges; in the pumped case the frame offsets are already absorbed into the
diagonal). The term $\tfrac{i}{2}\kappa\kappa^\dagger$ is the rank-one damper a
*shared* port produces: every attached mode decays through the same resistor,
and the off-diagonal entries are the cross-damping between them. In matrix
form, with $D = \operatorname{diag}(f - f_n + \tfrac{i}{2}B_n)$,

$$
M\,a = \kappa\,b_\mathrm{in},\qquad M \equiv D + E + \tfrac{i}{2}\kappa\kappa^\dagger,
\qquad
S \equiv \frac{b_\mathrm{out}}{b_\mathrm{in}} = -1 + i\,\kappa^\dagger M^{-1}\kappa .
$$

This is exactly the assembly the app performs ($S = iK^\dagger M^{-1}K - I$ over
its port columns), so everything below transfers to the code line for line.

**One port, no conservative couplings.** For $E = 0$ the Sherman–Morrison
identity gives $\kappa^\dagger(D + \tfrac{i}{2}\kappa\kappa^\dagger)^{-1}\kappa =
\chi/(1 + i\chi/2)$ with

$$
\chi(f) \equiv \kappa^\dagger D^{-1}\kappa = \sum_n \frac{\kappa_n^2}{f - f_n + iB_n/2},
\qquad\text{hence}\qquad
S = \frac{i\chi/2 - 1}{i\chi/2 + 1}.
\tag{1}
$$

Two things follow immediately and both matter. First, **the port sees the
modes only through the scalar $\chi$** — the reflection is a Möbius map of one
susceptibility, so any two mode sets with the same $\chi(f)$ are
indistinguishable from the port. Second, (1) is the reflection off an
impedance: writing $i\chi/2 = Z_\mathrm{in}/Z_0$ gives $S = (Z_\mathrm{in} -
Z_0)/(Z_\mathrm{in} + Z_0)$, so

$$
\chi(f) = -\,\frac{2i}{Z_0}\,Z_\mathrm{in}(f).
\tag{2}
$$

The mode expansion of $\chi$ is the partial-fraction (Mittag-Leffler) expansion
of the line's input impedance. That is the whole basis of the closure.

---

## 2. The comb and its tail

### 2.1 The open–open line

For a line of length $\ell$, impedance $Z_\mathrm{tx}$, phase velocity $v$, open
at both ends, the standing-wave modes are $u_n(x) = \cos(n\pi x/\ell)$ at $f_n =
n\,\mathrm{FSR}$, $\mathrm{FSR} = v/2\ell$, and the coupled-mode description uses
the $\pm n$ pairs plus the free DC mode: poles at $f = 0, \pm F, \pm 2F,
\dots$ ($F \equiv \mathrm{FSR}$), each with the same residue $\kappa_n^2 =
\gamma$. Summing all of them,

$$
\chi_\text{full}(f) = \gamma\sum_{n\in\mathbb{Z}}\frac{1}{f - nF}
= \frac{\gamma}{F}\,\pi\cot\!\Big(\frac{\pi f}{F}\Big).
\tag{3}
$$

The exact input impedance of an open line at its open end is, in this
convention, $Z_\mathrm{in} = iZ_\mathrm{tx}\cot(k\ell)$ with $k\ell = \pi f/F$
(capacitive at low frequency: $+i\cdot$large). Putting it into (2),

$$
\chi_\text{exact} = \frac{2Z_\mathrm{tx}}{Z_0}\cot\!\Big(\frac{\pi f}{F}\Big),
\qquad\text{so (3) matches (2) iff}\qquad
\gamma = \frac{2}{\pi}\,\frac{Z_\mathrm{tx}}{Z_0}\,F .
\tag{4}
$$

This is the comb macro's port rate, now seen as the *residue* that makes the
comb's partial-fraction sum equal the line — including the DC pole, whose
residue is also $\gamma$ (the $\cot$ has unit residue at every integer). The
lossless comb of infinitely many modes **is** the line; nothing is
approximated yet.

### 2.2 Truncation and its cost

Keep $\mathcal K = \{0, \pm1, \dots, \pm N\}$ and drop the rest:

$$
\chi_\text{kept} = \sum_{n\in\mathcal K}\frac{\kappa_n^2}{f - f_n},\qquad
\chi_t \equiv \chi_\text{exact} - \chi_\text{kept}
= \gamma\sum_{n>N}\Big[\frac{1}{f - nF} + \frac{1}{f + nF}\Big]
= \gamma\sum_{n>N}\frac{2f}{f^2 - n^2F^2}.
$$

For $f \ll NF$ this is

$$
\chi_t(f) \simeq -\frac{2\gamma f}{F^2}\sum_{n>N}\frac{1}{n^2}
\simeq -\frac{2\gamma f}{F^2 N}\Big[1 - \frac{1}{2N} + \dots\Big],
\tag{5}
$$

a *reactive* (real, odd in $f$) susceptibility, and in closed form for any
$N$ and $x = f/F$: $\chi_t = (\gamma/F)\,[\psi(N+1-x) - \psi(N+1+x)]$ with
$\psi$ the digamma function. Two consequences:

* **The error is in the phase.** For a lossless one-port $|S| = 1$
  identically, from (1) with real $\chi$; a dB plot cannot show truncation at
  all. What moves is *where the resonances sit*.
* **How much they move.** Near an isolated kept mode $m$, the closure term
  derived in §3 shifts the resonance by $\delta f_m \approx
  -\tfrac{1}{4}\chi_t\,\kappa_m^2$, i.e. $\delta f_m/\gamma \approx
  \tfrac12\,(\gamma/F)(f_m/F)/N$, and at the steepest point of the reflection
  phase $|dS/df| = 4/\gamma$, so $|\Delta S| \approx 4\,\delta f_m/\gamma =
  2\,(\gamma/F)(f/F)/N$. Measured over a $\pm F/2$ window against exact ABCD
  (which includes the asymmetric part): $|\Delta S| \approx
  2.3\text{–}3.0\,(\gamma/F)(f/F)/N$ across two decades of $\gamma/F$.

The scaling is what makes truncation expensive: linear in the coupling,
linear in the frequency you look at, and only $1/N$. At $\gamma/F \approx 0.8$
near $f \approx 6F$, five percent needs $N \approx 250$.

### 2.3 Loaded, lossy, and shared

Equation (2) does not care how $Z_\mathrm{in}$ arises, so the same
$\chi_\text{exact} - \chi_\text{kept}$ closes the tail of

* a line **inductively loaded** at the far end: $Z_\mathrm{in}$ from the ABCD
  cascade of the line and $Z_L = -i\omega L$, with the kept residues
  $\kappa_n^2 = u_n(\text{end})^2\gamma_n$, $\gamma_n = 1/(2\pi Z_0 C_n)$ on
  the dispersed roots (no DC pole: the inductor shorts it);
* a port **at the loaded end**: $Z_\mathrm{in} = Z_L \parallel Z_\text{line}$;
* a **lossy** line with uniform attenuation, where every kept pole sits at
  $f_n - iB/2$: the tail is the lossless expression continued to the same
  complex argument, $\chi_t(f + iB/2)$;
* **two line ends on one port**: the hub column concatenates both combs, so
  $\chi = \chi_a + \chi_b$ and, by (2), $Z_\mathrm{in} = Z_a + Z_b$. A shared
  hub is the two ends **in series** — the resistor is driven by $V_a + V_b$ —
  not in parallel. (The raw comb converges to the series answer as $1/N$; the
  closure reaches it at $N = 2$.)

More generally, *any* reactance $Z_s(f)$ in series with the port terminal is
an additive $\chi_s = -2iZ_s/Z_0$ and is closed by the identical machinery —
this is the "connector embedding" of the project's Phase-2 list, derived here
for the one case where the reactance is the line's own truncated tail. A
*shunt* element across the port composes as an admittance and is not of this
form.

---

## 3. Eliminating the tail: the Schur complement

Partition the modes into kept and tail, $a = (a_k, a_t)$, $\kappa = (\kappa_k,
\kappa_t)$, $D = \operatorname{diag}(D_k, D_t)$, and — this is the one
assumption — let the tail modes carry **no conservative couplings**: $E_{tt} =
0$, $E_{kt} = 0$. They then touch the rest of the system only through the port
column. Define the *port field*

$$
u \equiv \kappa^\dagger a = \kappa_k^\dagger a_k + \kappa_t^\dagger a_t .
$$

**Tail rows.** $D_t a_t + \tfrac{i}{2}\kappa_t u = \kappa_t b_\mathrm{in}$, so
$a_t = D_t^{-1}\kappa_t\,(b_\mathrm{in} - \tfrac{i}{2}u)$ and, contracting
with $\kappa_t^\dagger$,

$$
\kappa_t^\dagger a_t = \chi_t\,\big(b_\mathrm{in} - \tfrac{i}{2}u\big),
\qquad \chi_t \equiv \kappa_t^\dagger D_t^{-1}\kappa_t = \sum_{n\in\text{tail}}\frac{\kappa_n^2}{f - f_n + iB_n/2}.
$$

**Solve for the port field.** $u = \kappa_k^\dagger a_k + \chi_t b_\mathrm{in}
- \tfrac{i}{2}\chi_t u$, hence

$$
u = \lambda\,\big(\kappa_k^\dagger a_k + \chi_t\,b_\mathrm{in}\big),
\qquad
\boxed{\;\lambda(f) \equiv \frac{1}{1 + i\chi_t(f)/2}\;}
\tag{6}
$$

**Kept rows.** $(D_k + E_{kk})a_k + \tfrac{i}{2}\kappa_k u = \kappa_k
b_\mathrm{in}$. Substituting (6) and using $1 - \tfrac{i}{2}\lambda\chi_t =
\lambda$,

$$
\boxed{\;\Big[D_k + E_{kk} + \tfrac{i}{2}\,\lambda\,\kappa_k\kappa_k^\dagger\Big]a_k = \lambda\,\kappa_k\,b_\mathrm{in}\;}
\tag{7}
$$

**Output.** $b_\mathrm{out} = -b_\mathrm{in} + iu = -(1 - i\lambda\chi_t)\,b_\mathrm{in} + i\lambda\,\kappa_k^\dagger a_k$, and with (7),

$$
\boxed{\;S = -\Lambda + i\,\lambda^2\,\kappa_k^\dagger\Big[D_k + E_{kk} + \tfrac{i}{2}\lambda\kappa_k\kappa_k^\dagger\Big]^{-1}\kappa_k,
\qquad
\Lambda \equiv 1 - i\lambda\chi_t = \frac{1 - i\chi_t/2}{1 + i\chi_t/2}\;}
\tag{8}
$$

Nothing was approximated: (7)–(8) are the original equations with the tail
rows solved and substituted. Three remarks on the structure.

1. **$\lambda$, not $|\lambda|^2$.** The factor $\lambda^2$ in (8) is $\lambda$
   from the input side (the tail reshapes the drive that reaches the kept
   modes) times $\lambda$ from the output side (the port field is $\lambda$
   times the kept-mode field). It is *not* a rescaling $\kappa_k \to
   \sqrt\lambda\,\kappa_k$ inside a Hermitian product — for complex $\lambda$
   the two are different, and an implementation must multiply the coupling
   column by $\lambda$ on both sides without conjugating it.
2. **What $\lambda$ does to the mode matrix.** With $\lambda = (1 -
   i\chi_t/2)/(1 + \chi_t^2/4)$,
   $$
   \tfrac{i}{2}\lambda\,\kappa\kappa^\dagger
   = \underbrace{\frac{i}{2}\,\frac{\kappa\kappa^\dagger}{1 + \chi_t^2/4}}_{\text{damping, reduced}}
   \;+\;\underbrace{\frac{\chi_t/4}{1 + \chi_t^2/4}\,\kappa\kappa^\dagger}_{\text{Hermitian: a frequency shift}} .
   $$
   The tail *steals* part of the port coupling (the modes beyond $N$ share the
   resistor) and adds a rank-one reactive shift — the first-order resonance
   shift of §2.2 read off directly. In reservoir language $\lambda$ is a
   frequency-dependent self-energy on the channel: the port is no longer a
   flat (Markovian) bath but one with the structure of the discarded modes.
3. **The direct term is a phase.** $|\Lambda| = 1$ for real $\chi_t$: the tail
   is lossless, so the part of the wave that never enters a kept mode is
   reflected with unit magnitude and the tail's phase.

**Check that it is an identity.** Set $E_{kk} = 0$ and let $\chi_k =
\kappa_k^\dagger D_k^{-1}\kappa_k$. Sherman–Morrison gives
$\kappa_k^\dagger[D_k + \tfrac{i}{2}\lambda\kappa_k\kappa_k^\dagger]^{-1}\kappa_k
= \chi_k/(1 + i\lambda\chi_k/2)$, so with $\chi = \chi_k + \chi_t$,

$$
i\lambda^2\frac{\chi_k}{1 + i\lambda\chi_k/2} = \frac{i\lambda\chi_k}{\lambda^{-1} + i\chi_k/2} = \frac{i\lambda\chi_k}{1 + i\chi/2},
\qquad
S = \frac{-(1 - i\chi_t/2)(1 + i\chi/2) + i\chi_k}{(1 + i\chi_t/2)(1 + i\chi/2)}
= \frac{(i\chi/2 - 1)(1 + i\chi_t/2)}{(1 + i\chi_t/2)(1 + i\chi/2)}
= \frac{i\chi/2 - 1}{i\chi/2 + 1},
$$

which is (1) for the **full** comb. The closed truncated comb and the
infinite comb have the same one-port response — by construction, to rounding.

---

## 4. Several channels

With channels $h = 1\dots H$ (ports and loss hubs alike), each with its own
tail $\chi_{t,h}$ from whatever line ends terminate on it,

$$
M_\text{eff} = D + E + \tfrac{i}{2}\sum_h \lambda_h\,\kappa_h\kappa_h^\dagger,
\qquad
S = -\operatorname{diag}(\Lambda_h) + i\,\operatorname{diag}(\lambda_h)\,K^\dagger M_\text{eff}^{-1}K\,\operatorname{diag}(\lambda_h),
\tag{9}
$$

$K = [\kappa_1 \cdots \kappa_H]$. A channel with no tail has $\chi_t = 0$,
$\lambda = \Lambda = 1$, and (9) reduces to the plain assembly *exactly* — in
floating point too, since the closure enters as $\tfrac{i}{2}(\lambda_h -
1)\kappa_h\kappa_h^\dagger$ added to the plain Gram term, which is a matrix of
exact zeros for $\lambda_h = 1$. The same formula over all channels gives the
dilated $S_\text{full}$; because (7)–(8) are an identity, it stays unitary
when every $B_n = 0$ (verified to $10^{-15}$).

---

## 5. What the closure does not carry

The single assumption was $E_{kt} = E_{tt} = 0$. In a *pumped* line the tail
modes do carry conservative couplings: the rank-one pump block $g\,g^T$ links
kept modes of the signal comb to tail modes of the conjugate twin (and tail to
tail), with the profile $g_n \propto u_n(\text{end})/\sqrt{n}$ for a modulated
inductor. Eliminating a tail mode $n$ that carries both the port coupling and a
pump coupling produces, besides $\lambda$, a correction to the kept block of
order $g_m^2 g_n^2/(f - f_n)$ — **second order in the pump rate**, summed over
$n > N$ as $\sum_{n>N} g_n^2/(nF) \sim g^2/(FN)$ for the inductive profile —
and a cross term with $\kappa$. The present closure drops these. Measured on
the pumped line of the companion note (oracle: exact harmonic balance, gain
peak 3.18), the relative gain error is

| $N$ | 4 | 6 | 8 | 12 |
|---|---|---|---|---|
| raw comb | $7.4\times10^{-3}$ | $4.9\times10^{-3}$ | $4.0\times10^{-3}$ | $3.2\times10^{-3}$ |
| port tail closed | $3.3\times10^{-3}$ | $2.6\times10^{-3}$ | $2.3\times10^{-3}$ | $2.1\times10^{-3}$ |

where the closed values sit on the $\approx 2\times10^{-3}$ floor of a separate
effect (the oracle pumps the DC mode, which the macro excludes). So after the
port-tail closure, $N$ is chosen for the *couplings* — and the honest way to
choose it is to measure: re-solve with every comb doubled and look at the
change of the traces one cares about.

The pump tail is itself closable by the same method: for a profile
$g_n^2 \propto 1/n$ the sums $\sum_{n>N} 1/[n(f \mp nF)]$ have digamma closed
forms, and the tail block is diagonal plus two rank-one terms (port and pump),
so its elimination is again finite-rank. That is the natural next step for
the theory; it has not been done here.

---

## 6. Two methodological points

**The closure blinds the one-port test to the basis.** Because the port sees
only $\chi_\text{total}$, and $\chi_\text{total} = \chi_\text{exact}$ by
construction once the tail is closed, a one-port comparison against ABCD can no
longer detect a wrong kept residue $\kappa_n^2$ or a wrong kept pole $f_n$ —
the tail term silently compensates. The kept basis (mode frequencies, end
profiles, $C_n$, $\gamma_n$) must therefore be validated with the closure
**off**, by the $1/N$ convergence of the raw comb, and that is how the
project's basis gates are written. The closure's own gate is the identity of
§3, plus the two-line series check and the unitarity of $S_\text{full}$.

**Evaluating exact minus kept on a kept pole.** At $f = f_m$, $m \in \mathcal
K$, both $\chi_\text{exact}$ and $\chi_\text{kept}$ are infinite while $\chi_t$
is smooth; numerically the subtraction is undefined on the pole and loses
digits near it (a lossless sweep grid lands on $nF$ routinely). Within a guard
band of $10^{-5}F$ around a kept pole, $\chi_t$ is taken as the mean of its
values on the band's two symmetric edges: the linear term cancels, leaving an
$O(10^{-10})$ interpolation error against an $O(10^{-11})$ cancellation error.
Sweep points exactly on a pole then reproduce ABCD to $9\times10^{-16}$.

---

## 7. Verification summary

Complex $|S_{11}|$ error against exact ABCD, natural units ($\ell = Z_\mathrm{tx}
= v = 1$, $\gamma/F = 0.83$), 300 points over $0.6F$–$6.6F$:

| configuration | $N = 2$ | $N = 4$ | $N = 10$ | raw comb, $N = 10$ |
|---|---|---|---|---|
| open–open | $1.5\times10^{-15}$ | $1.7\times10^{-15}$ | $2.0\times10^{-15}$ | 1.11 |
| inductive load, $f_Z = 0.5F$, port at open end | $1.2\times10^{-15}$ | — | $2.1\times10^{-15}$ | 1.21 |
| inductive load, $f_Z = 0.15F$ | $9.0\times10^{-16}$ | — | $2.1\times10^{-15}$ | 1.25 |
| port at the loaded end | $8.0\times10^{-16}$ | — | $2.3\times10^{-15}$ | 1.24 |
| two lines, one port (vs. $Z_a + Z_b$) | $2.7\times10^{-14}$ | | | 1.94 |
| lossy, $\alpha\ell = 0.02$ | two orders below the raw comb at the same $N$ (residual = the $O(\alpha^2)$ of the $B_\text{int}$ map itself) | | | |

$S_\text{full}$ unitary to $10^{-15}$ with the closure; legacy graphs (no lines)
bit-identical.

---

## 8. Where it lives in the code

* `LineResonator.input_impedance(end, z)` — exact $Z_\mathrm{in}$ at complex
  linear frequency $z$ by ABCD (open, loaded, port at the loaded end);
  `exact_susceptibility` $= -2iZ_\mathrm{in}/Z_0$; `kept_susceptibility` with
  the very poles and residues placed in $M$ and $K$; `tail_susceptibility` =
  their difference with the guard band of §6.
* Hub dicts carry `tails = [{'line', 'end'}, ...]`; the extractor passes them
  through; `GraphScatteringMatrix._build_tail_closure` computes
  $\chi_{t,h}$, $\lambda_h$, $\Lambda_h$ per channel in the channel's drive
  frame; `_build_M_matrix` adds $\tfrac{i}{2}(\lambda_h - 1)\kappa_h\kappa_h^\dagger$;
  `_scatter` applies (9) to $S$ and $S_\text{full}$. Constructor flag
  `tail_closure=True`.
* GUI: *close comb tail analytically* (Ports & Lines header, default on) and
  *Check truncation (2× f_max)*, which measures §5 for the graph at hand.

Companion: `docs/pumped_line_termination.md` §8 (the measurements that
motivated this), `misc/comb_truncation_checks.py` (reproduces every number
here), `tests/test_tail_closure.py` (the gate).
