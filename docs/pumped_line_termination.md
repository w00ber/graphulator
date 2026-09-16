# A transmission line terminated in a modulated inductor: rank-one coupling, self-phase-matching, dispersion

*Working note for the pumped-termination macro (Phase 2). Numbers quoted here are
reproduced by `misc/pumped_termination_checks.py` against the `tests/cmtline_core.py`
oracle; nothing below is an ansatz.*

**Setting.** An open–open transmission line of length ℓ, impedance Z_tx, phase
velocity v, with mode functions u_n(x) and mode fluxes φ_n(t):

    Φ(x, t) = Σ_n u_n(x) φ_n(t),      u_n(0) = 1,   u_n(ℓ) = (−1)^n.

Some lumped element sits at one point x₀ (an end): a resistor (the port), or an
inductor whose inverse inductance is modulated, 1/L(t) = 1/L₀ + δ·cos(ω_p t).
JAA conventions as everywhere in this project: e^{+iωt}, decaying poles in the
lower half plane, M diagonal f_drive ± f₀ + (i/2)B.

---

## 1. One element at one point ⇒ rank one (the unified argument)

A lumped element at x₀ can only "see" the field through **one scalar**, the flux
(or voltage) at that point,

    Φ(x₀) = Σ_n u_n(x₀) φ_n  =  uᵀφ,          u ≡ (u_n(x₀))_n .

Whatever energy the element stores or dissipates is therefore a function of that
single linear combination of the mode amplitudes, and its second derivative with
respect to the amplitudes — which is the coupling matrix — is the outer product
u uᵀ. That is the whole argument; the two elements just differ in which scalar
function of uᵀφ they contribute.

**Resistor (the port).** The dissipated power is P = V(x₀)²/R = (uᵀV)²/R. The
damping matrix is R⁻¹ u uᵀ; in the a-basis it is the familiar rank-one
(i/2)κκ† with κ_n ∝ u_n(x₀). This is the power-balance argument already in the
code base: the energy leaving the modes must equal the power entering one
resistor through one voltage,

    d/dt Σ_n |a_n|² = −|Σ_n κ_n a_n|² = −|κ†a|²,

and only a rank-one anti-Hermitian part of M is consistent with that. (It is the
reason a shared port cross-damps its modes, and why non-diagonal external
dissipation was needed in the first place.)

**Modulated inductor (the pump).** The inductor's energy is

    U = Φ(x₀)² / (2 L(t)) = ½ (uᵀφ)² · (1/L₀ + δ cos ω_p t).

The Hessian ∂²U/∂φ_n∂φ_m = u_n u_m / L(t) is rank one for every n, m. The static
part u uᵀ/L₀ is the boundary condition that loads the line (§4); the modulated part
is the parametric coupling. The pump does work on the modes only through that
one scalar:

    dE_modes/dt = ½ Φ(x₀)² · d(1/L)/dt .

Check on the oracle: `build_galvanic` builds exactly this geometry and its pump
matrix is literally `P = np.outer(e, e)/LJ` — numerically rank 1 on the 11×11
mode space (`misc/pumped_termination_checks.py`).

So the modulated inductor is the **parametric twin of the dissipative hub**: one
element at one point gives a rank-one damper *within* each frequency sector, or a
rank-one coupling *between* sectors, from the same spatial vector u.

## 2. Into the a-basis: one outer product, two blocks

Write φ_n = φ_n^zpf (a_n + a_n*) with φ_n^zpf ∝ 1/√(ω_n C_n) (the flux quadrature
scale of mode n), and define g_n ≡ u_n(x₀) φ_n^zpf. For the open–open comb C_n
is n-independent for n ≥ 1, so

    g_n ∝ u_n(x₀) / √ω_n ∝ u_n(x₀) / √n ,

which is the *inductive* tap profile already pinned to machine precision against
the same oracle (`tests/test_line_taps.py`). Then

    Φ(x₀)² = Σ_{n,m} g_n g_m (a_n + a_n*)(a_m + a_m*)
           = Σ_{n,m} g_n g_m [ a_n a_m + a_n* a_m* + a_n* a_m + a_n a_m* ] .

Multiplying by δ cos(ω_p t) = (δ/2)(e^{iω_p t} + e^{−iω_p t}) and keeping the
slowly varying terms gives two blocks, **both** with the same rank-one matrix
g gᵀ:

| term | slow when | process | graph edge |
|---|---|---|---|
| a_n* a_m* e^{−iω_p t} + c.c. | ω_n + ω_m = ω_p | amplification (sum-frequency) | non-conjugate ↔ conjugate |
| a_n* a_m e^{∓iω_p t} + c.c. | ω_n − ω_m = ±ω_p | conversion (difference-frequency) | non-conjugate ↔ conjugate, *negative-frequency member* (§4) |

One pump therefore drives both families at once, through one outer product.

**What the rotating-wave approximation does to it.** In the isolated-mode limit
FSR ≫ κ, only the (n, m) entries of g gᵀ that satisfy a resonance condition
survive the RWA; the rest of the outer product is what gets swept away, and one
is left with the textbook one- or two-mode parametric amplifier. That is the
regime that has been measured. In the overlapping limit κ ~ FSR (a coax comb has
γ/FSR = (2/π)(Z_tx/Z₀) ≈ 0.83 at 65 Ω on 50 Ω) the sweep is not allowed: every
entry of g gᵀ is within a linewidth of a resonance and the whole block stays —
exactly as diagonal damping stops being allowed for the same comb.

## 3. The power-balance analogue: Manley–Rowe

The port argument was a *dissipative* balance. The parametric analogue is a
*conservative* exchange with a stiff pump, and it is the Manley–Rowe relation.

Because the amplification block has the form Σ g_n g_m (a_n† b_m† + h.c.), it
commutes with N_a − N_b (the photon-number difference between the two
clusters): signal and idler photons are created in pairs, cluster-wide, not pair
by pair. The conversion block Σ g_n g_m (a_n† b_m + h.c.) commutes with
N_a + N_b. Translated into scattering data at a single port with power-wave
normalization,

    amplification (ω_i = ω_p − ω_s > 0):   |S_ss|² − 1 = (ω_s/ω_i) |S_is|²
    conversion    (ω_i < 0):               |S_ss|² + (ω_s/|ω_i|) |S_is|² = 1 .

Note that these follow from the *cross-cluster Hermitian form* of the coupling,
not from its rank; what rank one adds is that the coupling and the damping come
from the same u — a single physical location.

Verified on the oracle (lossless line + modulated inductor, `hb_signal_idler`):

| regime | pump | peak |S_is|² | Manley–Rowe residual |
|---|---|---|---|
| matched port, Z₀ = Z_tx | δ = 0.9 | 0.082 | 8.8 × 10⁻¹⁵ |
| weakly coupled port, Z₀ = 10 Z_tx | δ = 0.25 | 0.71 | 3.4 × 10⁻¹⁴ |
| conversion band (ω_i < 0) | δ = 0.9 | 0.006 | 4.3 × 10⁻¹⁵ |

So the relation holds to machine precision in the two-rung solution, in both
processes, in the overlapping regime.

## 4. Self-phase-matching — and why a real loaded line is *not* quite

**Harmonic comb.** If ω_n = n·FSR and ω_p = P·FSR, then every pair with
n + m = P is *exactly* resonant for amplification, and every pair with
|n − m| = P for conversion, all at once from one pump. For P = 6 that is
(0,6), (1,5), (2,4), (3,3) — the last being the degenerate, self-paired case —
plus the negative-frequency partners such as (−1, 7), plus every pair one FSR off,
which at γ/FSR ≈ 0.83 sits inside a linewidth.

**How both families live in a two-cluster graph.** With the comb in the signal
frame (drive ω) and its conjugated twin in the idler frame (ω_p − ω), a pump edge
between *any* pair is frame-consistent with the same offset. Amplification is the
edge to the +m member of the twin (resonant at ω = ω_p − ω_m). Conversion is
the edge to the **−m member** of the twin (resonant at ω = ω_p + ω_m): the
classical idler at ω_p − ω_s comes out negative when ω_s > ω_p, and a conjugated
negative-frequency component *is* the down-converted signal. It does **not**
appear as a non-conjugate ↔ non-conjugate edge inside one cluster, because that
would need a third frame ω ± ω_p. The DC-complete ±n comb — the two partial
fractions of each mode's exact second-order response — is what lets a two-rung
truncation hold both processes; rungs at ω ± 2ω_p are dropped, at O(δ²).

**Dispersion.** An inductor L to ground at x = ℓ is not a uniform frequency
shift. The resonance condition is

    cot(kℓ) = ω L / Z_tx ,

whose roots interpolate between the open–short (quarter-wave) comb
k_nℓ = (n − ½)π at low frequency, where the inductor looks like a short, and the
open–open comb k_nℓ = nπ at high frequency, where it looks open, with the
crossover near ω ~ Z_tx/L. The spacing is non-uniform in between:

| L/Z_tx | k₁ℓ/π | k₂ℓ/π | k₃ℓ/π | k₄ℓ/π | successive spacings (units of π) |
|---|---|---|---|---|---|
| 0.001 | 0.500 | 1.499 | 2.498 | 3.497 | 0.999 0.999 0.999 |
| 0.3 | 0.388 | 1.227 | 2.146 | 3.105 | 0.839 0.919 0.959 |
| 1 | 0.274 | 1.090 | 2.049 | 3.033 | 0.817 0.959 0.984 |
| 1000 | 0.010 | 1.000 | 2.000 | 3.000 | 0.990 1.000 1.000 |

Only a perfect short or open is dispersionless. Consequences: (i) exact
self-phase-matching is lost — one pair can be matched and the mismatch of the
others grows with their distance from it, so which pairs participate is set by
that mismatch against the linewidth (a TWPA-style phase-matching question);
(ii) the n = 0 free mode acquires a finite frequency; (iii) the macro's comb must
use the loaded-line roots, not n·FSR. The oracle already does this: `Km` carries
the static (1/L₀) u uᵀ term.

## 5. The reduction viewpoint (treating the termination as a node)

Take the terminal flux Φ(ℓ) as the one variable of interest and Schur-complement
the comb out. The result is the line's end impedance, and it has a closed form:

    Z_end(ω) = −i Z_tx cot(kℓ)  =  −i Z_tx [ 1/(kℓ) + Σ_{n≥1} 2kℓ / ((kℓ)² − n²π²) ] .

The bracket is the Mittag-Leffler partial-fraction expansion of cot, one term per
comb mode. Numerically the N-mode comb reproduces cot(kℓ) with maximum error
4.8 × 10⁻¹ (N = 5), 1.1 × 10⁻¹ (20), 2.8 × 10⁻² (80), 7.0 × 10⁻³ (320) — the
~1/N tail, the same residual the ABCD study attributed to the truncated comb.
So "Kron-reducing the line away" is exact and closed-form for the static line:
it *is* the transcendental boundary condition, and the comb is its truncated
expansion.

Two remarks on modelling the inductor as a graph node with ω₀ = 0. A bare
inductor to ground is not a mode — it has no capacitance and nothing to
oscillate — so such a node is really the terminal flux carrying a
**frequency-dependent self-energy** Z_end(ω) from the reduced line; specifying it
by an impedance and a slope sign is Foster's reactance theorem, i.e. the
Phase-2 "λ(ω) / connector embedding" item. For the pumped case the reduction
leaves a 2×2 signal/idler problem in Z_end(ω) and Z_end(ω_p − ω)* coupled by
δ — the classical boundary-condition treatment of a parametric resonator. The
trade is clear: the reduced form is closed-form and truncation-free but its
matrix elements depend on frequency, which the constant-M solver (and det-M
stability analysis) cannot take; the explicit comb keeps M constant at the cost
of N modes and a 1/N tail. The comb is the representation the app uses; the
reduction is the analytic cross-check.

## 6. Implications for the macro and its visual language

*Macro emission* (not user wiring — the rank-one block is (2N+1)² edges): the
loaded-line comb in the signal sector, its conjugated twin in the idler sector,
the single rank-one pump block between them, and one port hub per sector (a
resistor does not convert frequency, so each hub stays single-sector).

*Visual language.* One glyph per rank-one object, mirroring "one port glyph per
hub column": the line, a hollow conjugate twin (the conjugated-node styling),
each with its own port glyph, joined at the pumped ends by a single **double-line
bus**. The double line keeps its existing meaning — the edge crosses sectors —
and with the ±n comb that same bus carries the conversion pairs too; "the pump
exceeds the fundamental" is the condition for it to contain resonant
amplification pairs at all. Bus parameters: ω_p; the pump strength δ normalized
at a reference pair (n_ref, P − n_ref) by analogy with the tap's n_ref; a pump
phase.

*Gates before shipping:* pin the a-basis normalization of g gᵀ against
`build_galvanic` + `hb_signal_idler` in the overlapping regime (the reference
exists as-is); loaded-line roots in the macro; and the det-M / Routh–Hurwitz
stability flag, since a comb with many simultaneously matched gain channels is a
natural oscillator.
