# The $\sigma_z$ sector rule: which pump couplings are Hermitian on a $\pm n$ comb

*Why a conversion-only pump produced gain, what the fix is, and the oracle
numbers that settle it. Conventions are the project's
(`tests/cmtline_core.py`; JAA: $e^{+i\omega t}$, $Z_L = -i\omega L$,
$Z_C = +i/\omega C$); rates and frequencies are linear ($f$, not $\omega$),
matching the app. Gates: `tests/test_pump_sector_rule.py`,
`tests/test_pumped_line.py::test_conversion_band_matches_oracle`,
`tests/test_line_taps.py::test_tap_sector_matches_the_reference_a_basis_generator`.*

---

## 0. The result in one paragraph

A comb macro puts every physical mode into the basis **twice**, at $+f_n$ and
at $-f_n$, because those are the two partial fractions of the mode's exact
second-order response. The two halves are the co- and counter-rotating parts of
the *same* mode, so they sit in **opposite $\sigma_z$ sectors inside one
cluster**. The assembly code was reading a node's sector off the cluster flag
(`conj`) alone, which is constant across a cluster, so every signal $\to$ twin
coupling came out anti-Hermitian — two-mode squeezing — including the ones that
are beam-splitters. A pump that can only *convert* therefore amplified. The
correct sector is

$$
s_j = (-1)^{\,\texttt{conj}_j \;\oplus\; \texttt{counter\_rotating}_j},
\qquad
M_{kj} = s_j s_k \, \overline{M_{jk}} ,
$$

Hermitian within a sector, anti-Hermitian across it. Against the
harmonic-balance oracle in the conversion band the old rule gave
$\max|S_{ss}|^2 = 4.58$ where the circuit gives $0.999$; the new rule gives
$0.9992$. In the amplification band the new rule is also **8× closer** to the
oracle.

---

## 1. The basis, and what each node actually holds

A pumped line is two clusters: the comb $A$ (`conj = False`) in the drive frame
$\omega$, and its conjugated twin $B$ (`conj = True`) in the frame
$\omega - \omega_p$. Each cluster carries the DC-complete $\pm n$ comb. The
diagonal the assembler writes is

$$
M_{jj} = f_{\mathrm{drive}} + \sigma_j f_{0,j} + \tfrac{i}{2} B_{\mathrm{int}},
\qquad \sigma_j = \begin{cases} -1 & \texttt{conj} = 0\\ +1 & \texttt{conj} = 1\end{cases}
$$

with $f_{0,j} = \mathrm{sign}(k)\,f_{|k|}$ for comb node $k$. Four kinds of node
result. Measured on the reported file ($\mathrm{FSR} = 0.5$, $f_p = 0.5$,
$\omega = 6.0$, so $f_{\mathrm{drive}}^A = 6.0$ and $f_{\mathrm{drive}}^B = 5.5$):

| node | `conj` | `freq` | diagonal | resonant at | operator content | $s$ |
|---|---|---|---|---|---|---|
| $A{:}{+}n$ | 0 | $+f_n$ | $\omega - f_n$ | $\omega = f_n$ | $a_n[\omega]$ | $+1$ |
| $A{:}{-}n$ | 0 | $-f_n$ | $\omega + f_n$ | $\omega = -f_n$ | $a_n^\dagger[-\omega]$ | $-1$ |
| $B{:}{+}m$ | 1 | $+f_m$ | $\omega - \omega_p + f_m$ | $\omega = \omega_p - f_m$ | $b_m^\dagger[\omega_p - \omega]$ | $-1$ |
| $B{:}{-}m$ | 1 | $-f_m$ | $\omega - \omega_p - f_m$ | $\omega = \omega_p + f_m$ | $b_m[\omega - \omega_p]$ | $+1$ |

The last row is the whole story. The twin cluster stores *conjugated* idler
amplitudes $b^\dagger[\omega_p - \omega]$; when the argument comes out negative
the amplitude is the conjugate of the one at the positive argument, so the
$-m$ member is an **un-daggered** $b_m[\omega - \omega_p]$. `conj` says which
cluster; the sign of `freq` says which half of that cluster's doubled pair. The
operator character is the **XOR of the two**, which is what $s_j$ above encodes.

---

## 2. The two families, in mode notation

A real quadratic modulation of the flux at the pumped end,

$$
H_p(t) = \tfrac{1}{2}\,\delta\!\left(\tfrac{1}{L}\right)\cos(\omega_p t)\;
\Phi(x_e)^2 ,
\qquad
\Phi(x_e) = \sum_n u_n(x_e)\,\varphi_n \left(a_n + a_n^\dagger\right),
$$

couples to the **field**, not to $a_n$ alone, so one outer product
$\mathbf g \mathbf g^{\mathsf T}$ reaches every $(n, \pm) \times (m, \pm)$ entry
with the same coefficient. The two-rung truncation keeps the frames $\omega$ and
$\omega - \omega_p$ and drops $\omega \pm 2\omega_p$, at $O(\delta^2)$. What
survives:

**Amplification** — the edge to the $+m$ member of the twin,

$$
\boxed{\;a_n[\omega] \;\longleftrightarrow\; b_m^\dagger[\omega_p - \omega],
\qquad \omega_p - \omega = +f_m > 0 \;}
$$

$$
H \supset g_n g_m \left(a_n^\dagger b_m^\dagger + \mathrm{h.c.}\right),
\qquad f_n + f_m = f_p ,
$$

which commutes with $N_a - N_b$: photons made in pairs, gain,
$|S_{ss}|^2 - |S_{is}|^2 = 1$. Sectors $s_A s_B = (+1)(-1) = -1$:
**anti-Hermitian**.

**Conversion** — the edge to the $-m$ member of the twin,

$$
\boxed{\;a_n[\omega] \;\longleftrightarrow\; b_m[\omega - \omega_p],
\qquad \omega - \omega_p = +f_m > 0 \;}
$$

$$
H \supset g_n g_m \left(a_n^\dagger b_m + \mathrm{h.c.}\right),
\qquad f_n - f_m = f_p ,
$$

which commutes with $N_a + N_b$: photons moved, no gain,
$|S_{ss}|^2 + |S_{is}|^2 = 1$. Sectors $s_A s_B = (+1)(+1) = +1$:
**Hermitian**.

Both are *cross-cluster* edges — conversion does not need an intra-comb edge,
which would require a third frame $\omega \pm \omega_p$
(`docs/pumped_line_termination.md` §4). The families are distinguished by the
**sign of the twin member**, and that is exactly the information the cluster
flag throws away.

### The reported file

$\mathrm{FSR} = 0.5$, $f_p = 0.5$, signal driven at $f_{12} = 6.0$. The
resonant twin member is $B{:}{-}11$, at $\omega = f_p + f_{11} = 0.5 + 5.5 = 6.0$:

$$
a_{12}[\omega]\;\longleftrightarrow\; b_{11}[\omega - \omega_p],
\qquad \omega - \omega_p = 5.5 = f_{11},
\qquad f_{12} - f_{11} = f_p .
$$

Pure down-conversion $12 \to 11$. There is no amplification pair in this comb
at all: the smallest available $f_n + f_m$ is $2\,\mathrm{FSR} = 1.0 > f_p$.
Read through the cluster flag, the same edge was assembled as
$a_{12}^\dagger b_{11}^\dagger$ — pair creation at an "idler frequency" of
$-5.5$ — and the graph returned $|S_{ss}|^2 \approx 10$.

---

## 3. The matrix, symbolically

Take one $(n, m)$ pair and order the basis
$\left(A{:}{+}n,\; A{:}{-}n,\; B{:}{+}m,\; B{:}{-}m\right)$, with sectors
$s = (+1,\,-1,\,-1,\,+1)$ and diagonals

$$
D_1 = \omega - f_n,\quad D_2 = \omega + f_n,\quad
D_3 = \omega - \omega_p + f_m,\quad D_4 = \omega - \omega_p - f_m
$$

(plus $\tfrac{i}{2}\Gamma$). The pump writes $\beta = \tfrac{1}{2}\,\mathrm{rate}\,e^{i\phi}$
into **all four** cross entries — that is the rank-one structure, and it is not
in question here. Only the reverse block differs.

**Before — sector from the cluster flag.** Every cross entry anti-Hermitian:

$$
M_{\text{old}} =
\begin{pmatrix}
D_1 & 0 & \beta & \beta \\
0 & D_2 & \beta & \beta \\
-\bar\beta & -\bar\beta & D_3 & 0 \\
-\bar\beta & -\bar\beta & 0 & D_4
\end{pmatrix}
$$

**After — sector from $\texttt{conj} \oplus \texttt{counter\_rotating}$.** The
reverse block is multiplied entrywise by $s_j s_k$:

$$
M_{\text{new}} =
\begin{pmatrix}
D_1 & 0 & \beta & \beta \\
0 & D_2 & \beta & \beta \\
-\bar\beta & +\bar\beta & D_3 & 0 \\
+\bar\beta & -\bar\beta & 0 & D_4
\end{pmatrix}
$$

The two changed entries are the conversion couplings: $A{:}{+}n \leftrightarrow
B{:}{-}m$ (the physical process in the reported file) and its mirror
$A{:}{-}n \leftrightarrow B{:}{+}m$. The amplification couplings
$A{:}{+}n \leftrightarrow B{:}{+}m$ and $A{:}{-}n \leftrightarrow B{:}{-}m$
are untouched.

### It is a change of metric, not of model class

Write $\Sigma = \mathrm{diag}(s_j)$. The new rule is exactly

$$
\Sigma\,M_{\text{coupling}}\,\Sigma = M_{\text{coupling}}^\dagger ,
$$

i.e. the coupling is para-Hermitian in the **mode-level** metric
$\Sigma = \mathrm{diag}(+1, -1, -1, +1)$. This is what a real quadratic form in
$\Phi$ must give: a Hamiltonian $H = \tfrac12 v^\dagger H_{\mathrm{BdG}} v$ with
$H_{\mathrm{BdG}}$ Hermitian has dynamical matrix $\sigma_z H_{\mathrm{BdG}}$,
whence $N_{kj} = s_j s_k \overline{N_{jk}}$.

The old rule was *also* exactly para-Hermitian — in the **cluster-level** metric
$\Sigma_{\mathrm{cl}} = \mathrm{diag}(+1, +1, -1, -1)$. That is why it satisfied
$|S_{ss}|^2 - |S_{is}|^2 = 1$ to $10^{-15}$: a clean symplectic structure in the
wrong metric. **The exactness was the symptom, not the evidence.**

---

## 4. Oracle arbitration

`cmtline_core.hb_signal_idler` solves the two-frame harmonic balance on the
actual circuit (lossless line + modulated inductor at $x_0$, port at $x_L$,
$N = 12$, $Z_0 = 10$, $\omega_p = 6\pi$) and is the arbiter, not either model.

**Conversion band** — signal on mode 7, $\omega_i = \omega_p - \omega_s = -\pi < 0$,
so the process is down-conversion $7 \to 1$:

| | $\max|S_{ss}|^2$ | $\max C$ | $\left| |S_{ss}|^2 + C - 1 \right|$ | rel. err. vs oracle |
|---|---|---|---|---|
| oracle | 0.999043 | 0.780434 | $1.6\times 10^{-15}$ | — |
| cluster flag | **4.577508** | 3.577508 | $7.2$ | $4.4$ |
| $\sigma_z$ sector | 0.999174 | 0.779410 | $1.4\times 10^{-2}$ | $1.9\times 10^{-2}$ |

with $C = (\omega_s/|\omega_i|)\,|S_{is}|^2$ the photon-flux conversion. The
circuit cannot amplify and does not; the old rule produced a factor-4.6
parametric amplifier out of a beam splitter.

**Amplification band** — degenerate pair $(3,3)$, $\omega_p = 6\pi$:

| | $\max|S_{ss}|^2$ | $\left| |S_{ss}|^2 - C - 1 \right|$ | rel. err. vs oracle |
|---|---|---|---|
| oracle | 3.180424 | $4.0\times 10^{-15}$ | — |
| cluster flag | 3.187190 | $6.7\times 10^{-15}$ | $2.1\times 10^{-3}$ |
| $\sigma_z$ sector | 3.181254 | $1.7\times 10^{-4}$ | $2.6\times 10^{-4}$ |

The $\sigma_z$ sector is **8× closer to the oracle** while satisfying the
two-port relation only to $10^{-4}$. That residual is the two-rung truncation,
and it is measured, not assumed — halving the rate quarters it:

| rate | 0.0125 | 0.025 | 0.05 | 0.1 |
|---|---|---|---|---|
| $\left| |S_{ss}|^2 - |S_{is}|^2 - 1 \right|$ | $1.06\times10^{-4}$ | $4.25\times10^{-4}$ | $1.71\times10^{-3}$ | $7.06\times10^{-3}$ |
| ratio | — | $4.01$ | $4.03$ | $4.12$ |

$O(\delta^2)$ exactly — the order at which the $\omega \pm 2\omega_p$ rungs were
dropped. `test_pumped_line_amplifies_and_is_pseudo_unitary` now gates that
**scaling**, which is the sharper statement, rather than a fixed tolerance.

---

## 5. The static taps carry the same rule

The rule is not about pumps. A node tapped onto the line couples to the field
$\Phi$, so it too reaches both partial fractions, Hermitian-ly to the $+n$ half
and anti-Hermitian-ly to the $-n$ half. This is readable straight off the
reference's own doubled generator — `cmtline_core.a_basis_A` returns
$\sigma_z H$ in the $(a, a^*)$ basis — with no graph code involved. For a
capacitively tapped device on an $N = 6$ line, every mode:

$$
\frac{N_{kd}}{\overline{N_{dk}}} =
\begin{cases}
+1 & k = \text{mode's } a \text{ half} \\
-1 & k = \text{mode's } a^* \text{ half}
\end{cases}
\qquad = \; s_d s_k \quad \text{to } 10^{-9}.
$$

Twelve couplings, twelve agreements. Keying on the cluster flag made all twelve
Hermitian. This is pinned by
`test_tap_sector_matches_the_reference_a_basis_generator`.

---

## 6. What is *not* changed

**The diagonal keeps the raw cluster flag.** $\sigma_j$ there sets the sign of
$f_0$ — *where* a node resonates — and the counter-rotating member must keep its
own sign, which is the entire point of carrying it. Only the couplings read
$\Sigma$.

**The rank-one block is untouched.** Magnitudes, phases, the reference-pair
normalization and the tail closure are all as before; only the reverse entry's
sign moves. `test_pump_block_is_rank_one_with_reference_pair_normalization` and
`test_pump_rate_normalization_matches_oracle` pass unchanged.

**Ordinary graphs are untouched.** `counter_rotating` is set only by
`LineResonator.expand()`, on the $k < 0$ comb nodes. A hand-built node does not
carry it, so hub identities, dilation, ABCD and uniform-loss gates are
bit-identical.
