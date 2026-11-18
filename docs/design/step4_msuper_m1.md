# Step 4, milestone 1: the M_super compiler for the abstract workflow (design, for review)

*Status: proposal, 18 Nov 2026. No code yet. Items tagged **[decide]** need
JA's call. The numbers below come from throwaway survey scripts run against
the shipped examples (68 `.pgraph` files, of which 54 are lumped: 59 jobs,
8 of which legacy refuses for missing parameters). Physics remarks marked
*(speculation)* are mine and untested.*

## Scope (from the decisions already taken)

- Abstract workflow only: lumped modes, static and pumped mode-mode
  couplings, ports (explicit planes with attachments, and legacy `B_ext`
  ports). Loss ports (unmonitored plane + matched `R`) are included, since
  they are lumped too.
- Solved **exactly as drawn**: one row per drawn mode, no sector expansion.
  `solve.sectors` is ignored for lumped documents (it belongs to element
  pumps, milestone 2).
- A document with lines, other blocks or element pumps is refused with a
  clear message ("milestone 2").
- Oracle: `compile_jobs` + `compute_job` (model/legacy_job.py).
  Gate: S bit for bit on every lumped shipped job, or an explained exception.

## What the legacy engine computes, in M_super language

For one connected component, with the sweep variable f (negated when the
root mode is conjugated), legacy builds an N x N matrix over the drawn
modes and a real N x P port matrix K:

    M_kk = (f + nu_k) - f_k + i B_int,k / 2 + (i/2) (K K^dag)_kk        (k not conjugated)
    M_kk = (f + nu_k) + f_k + i B_int,k / 2 + (i/2) (K K^dag)_kk        (k conjugated)
    M_jk = (g/2) e^{i phi} + (i/2) (K K^dag)_jk,   M_kj = sigma conj((g/2) e^{i phi}) + (i/2) (K K^dag)_kj
    S = -1 + i K^dag M^{-1} K

- j is the earlier of the two modes in mode order.
- sigma = +1 if j and k are both conjugated or both unconjugated, and -1
  otherwise. So a conversion coupling is Hermitian and a gain coupling is
  anti-Hermitian (docs/pump_sector_rule.md).
- K has one column per port. Its entries are +-sqrt(rate) for an explicit
  port attachment and sqrt(B_ext) for a legacy port.

**What nu_k is.** nu_k is the frame offset of mode k: the frequency, relative
to the root, at which mode k is driven when the root is driven at f. In
M_super terms it is the mode's **sector**. With pump tones f_1..f_T, it is
nu_k = m_k . f, where m_k is a vector of T integers. A full M_super would have
a row for every pair (mode k, sector m). "Solved as drawn" means the drawing
keeps exactly one of those rows per mode, (k, m_k): that choice is the user's
RWA. With only ports in Sigma_0, the Schur reduction onto the mode rows is
the constant (i/2) K K^dag, so milestone 1 has no frequency-dependent
Sigma_0 term. A Sigma_0 that depends on frequency comes in with embedding
circuits (milestone 2).

So the compiler's real work is:
1. split the document into components;
2. pick each component's root;
3. assign each mode its sector m_k (**frames**);
4. build K, M_iso and the port loading from model objects;
5. solve.

Everything except step 3 turned out to be mechanical. Step 3 is the
physics decision.

## Findings from the gate's input (read before the design)

**F1. Legacy frames come from a DFS spanning tree, and loops are not
checked.**
- `compute_job` rebuilds a spanning tree from the root on every solve. It
  does not use the tree saved in `legacy_frames`, which is stale in 2 of the
  49 files that have one.
- Each tree edge moves the frame by +-f_p. The sign says whether the edge
  converts up or down. It is decided by comparing the effective frequencies
  of the two modes, where a conjugated mode counts as -f_0.
- A non-tree (chord) edge never constrains anything. Its f_p is
  *overwritten* by the difference of its endpoints' frames.
- Which edges end up as chords depends on the DFS order, and that order
  comes from Python `set` iteration.

What this means for the data:
- **f_p = None means "derived", not "static".** Legacy requires f_p on tree
  edges and returns no result otherwise. A coupling saved with f_p = None
  only works because the DFS made it a chord. Migration turned those into
  `Coupling` objects (documented as static). A *static* edge is one with
  f_p = 0, which migration turned into a `Pumped` with a 0 Hz tone.
- Some drawings are genuinely **frame-inconsistent**: going around a loop,
  the signed pump frequencies do not sum to zero. TUTORIAL_PARACIRCULATOR
  only works because its static-drawn A-B edge (6 vs 7 GHz) is a derived
  chord at 1.0 GHz. In FPJA_PRA, A-B has f_p = 0 but the two pumps imply
  1.601 GHz. In DTWPA_2_WIDE, one loop carries pumps at 12.0 and 12.12 GHz.

Physically, a loop is frame-consistent when one choice of rotating frames
makes every drawn coupling time-independent. The condition is that the
signed pump frequencies around the loop sum to zero. It is the frequency
analogue of the loop phase (the synthetic flux), which is the sum of the
coupling phases. When the sum is a nonzero delta, no frame works. The
as-drawn system is then really a Floquet problem at frequency delta. The
legacy tree silently treats one edge of the loop as if it were resonant,
which is a detuning error of size delta. *(speculation)* The level-2 RWA
check, or M_super with sectors opened, is what can settle what such a
drawing "should" give.

**F2. The coupling phase belongs to the earlier mode in mode order, not to
the drawn direction.** In 16 lumped files, 17 edges are drawn from a later
mode to an earlier one with a phase outside {0, 180}. Examples are the
TUTORIAL_PARACIRCULATOR e3_1 (90 deg), FPJA_PRA and 4MODE_ISOLATOR. In those
files the loop flux depends on node creation order, which is invisible on
the canvas.

**F3. Frame offsets are rounded to 12 decimals** (`round(acc, 12)`). This
helps: integer sectors combined as m . f and the legacy float path sums can
differ by an ulp, and the rounding makes them agree on every shipped job.

**F4. Tones at 0 Hz exist** (static edges stored as `Pumped`). They must
not count as sector dimensions.

**F5. Parallel edges:** if two edges join the same pair, the later one
silently replaces the earlier in M. No shipped file has this.

**F6. The root rule is clean.** "solve.root if the document has one
component and that mode is attached to a port; otherwise the first
port-attached mode in mode order; otherwise the first mode" reproduces the
legacy root on 59 of 59 jobs. For a document with several components, the
saved root is ignored, as in legacy.

## Proposed module

A new Qt-free package, so the engine stays separate from the document model:

```
src/graphulator/engine/
  __init__.py   solve(doc, f=None) -> [ComponentResult]; compile(doc) -> [MSuper]
  frames.py     sector assignment + loop-consistency issues (the RWA nanny reuses it)
  msuper.py     Document -> MSuper per component (rows, couplings, channels, root)
  kernel.py     MSuper + grid -> M blocks, S (the arithmetic)
```

### Data structures (sketch)

```python
@dataclass(frozen=True)
class Row:                       # one (mode, sector) row of M_super
    mode: str                    # Mode.id
    sector: Tuple[int, ...]      # m over the document's nonzero tones, root = 0
    nu: float                    # frame offset, round(m . f_tones, 12)
    f0: float; B_int: float; conj: bool

@dataclass(frozen=True)
class Channel:                   # a plane after the (closed-form) Schur reduction
    plane: str; label: str; monitored: bool
    k: np.ndarray                # (N,) real signed weights over rows

@dataclass
class MSuper:                    # one connected component
    rows: List[Row]
    couplings: List[Tuple[int, int, complex, float]]   # (j<k, beta, sigma)
    channels: List[Channel]      # monitored first (legacy order), then loss
    root: str; root_conj: bool
    issues: List[Issue]          # frames, missing params, refusals
    def static(self) -> np.ndarray       # couplings + (i/2) K_full K_full^dag
    def diag(self, f) -> np.ndarray      # (n_f, N)
    def M(self, f) -> np.ndarray         # full stack, for inspection / an M_super tab
```

`ComponentResult` holds S, the port plane ids and labels, the root, the
rows (sectors included) and the issues. When a parameter is missing it
holds `S = None` (legacy returns `None` there).

### Pipeline (all from model objects; no `to_legacy`)

1. **Refuse** anything that is not lumped.
2. **Components:** connected through couplings, pumped couplings and shared
   port planes. Ordered by size, largest first; equal sizes keep the order
   of their first mode in mode order (legacy rule).
3. **Root:** rule F6.
4. **Frames:** see the next section.
5. **Channels:**
   - explicit monitored port planes in document order whose attachments lie
     in the component;
   - then legacy `B_ext` planes in mode order;
   - then loss planes.

   Weights are sqrt(max(rate, 0)) with sign from `phase_deg` in {0, 180}
   (other phases are refused, as in legacy Phase 1). A plane that mixes
   conjugated and unconjugated modes is refused, as in legacy.
6. **Couplings:**
   - beta = (rate / 2) e^{i phase pi / 180}, put on (earlier, later) in mode
     order (F2);
   - sigma from the conjugation flags;
   - self-loops are ignored;
   - parallel edges are summed **[decide M5]**.
7. **Missing parameters** (freq or B_int on a mode, rate or phase on an
   edge, an undeterminable frame) make that component's result None and are
   listed as issues.

### Kernel: independent, but the same arithmetic

I propose **not** sharing `GraphScatteringMatrix`. The reasons:
- it is tied to the extractor, the line-comb tail closure and `drive_signals`;
- milestone 2 needs a frequency-dependent Sigma_0 Schur step that legacy
  does not have;
- an independent kernel lets the gate check the arithmetic as well as the
  translation.

Bit-for-bit then means copying legacy's operation order exactly:
- the static part is `zeros((N, N), complex)`, then the coupling
  assignments, then `+= 0.5j * (K_full @ K_full.conj().T)`, with K_full
  complex;
- the diagonal is `(f + nu) + sign * f0 + B_int * 1j / 2`;
- each block is `block[...] = static; block[:, idx, idx] += diag`;
- frequency blocks are 2^22 // N^2 points;
- `np.linalg.solve(block, broadcast(K))` with K real float64;
- `S = 1j * (K.T @ MinvK) - eye(P)`.

If one of these steps cannot be matched, I will say which one and give the
ulp-level difference rather than hide it. *(speculation)* The batched LAPACK
solve should not depend on the block size, but I copy the blocking anyway
rather than rely on that.

## Frames: the one physics decision **[decide M1]**

**Proposed rule (deterministic, no DFS):**
- Edge classes and the sector step from a to b:
  - *pumped* (`Pumped`, tone f != 0): the step is +e_t if eff_b > eff_a,
    else -e_t (legacy's sign rule). A tie with f != 0 is an issue;
    there is none in the shipped files.
  - *static* (`Pumped` with a 0 Hz tone): the step is 0.
  - *port bridge* (two modes on one port plane): the step is 0. A resistor
    does not convert frequency.
  - *derived* (`Coupling`, f_p = None): no constraint. Its implied pump
    frequency |nu_b - nu_a| is reported, as the legacy chord column shows
    it.
- Grow a tree from the root. At each step take the eligible edge with the
  lowest (class, document index), with classes ordered pumped < static <
  bridge < derived. The tree uses a derived edge only if nothing else
  reaches that mode. Then the frame is undetermined: the result is None and
  an issue is raised (legacy fails in the same place).
- Every non-tree pumped or static edge whose step disagrees with its
  endpoints' sectors gives a **frame-inconsistency warning**. The warning
  names the loop, the mismatch delta in GHz, and the edge that is being
  solved as if it were resonant.

**Measured against legacy:** identical frames, after the 12-decimal
rounding, on **50 of the 51** computing jobs, including FPJA_PRA and the
TUTORIAL_PARACIRCULATOR.

The exception is **DTWPA_2_WIDE**. Its loop 10-12-14-13 carries pumps at
12.0 and 12.12 GHz, so no frame is right:
- the proposed rule keeps both pump conditions and treats a static 13-14
  coupling as resonant across 0.12 GHz;
- legacy's DFS keeps the static edges and treats the 12.0 pump as if it
  were at 12.12.

Both are detuning errors of the same size.

**Options:**
- **(a) the proposed rule (recommended).** Frames are a stated function of
  the drawing, inconsistencies are reported, and there is one explained
  gate exception (DTWPA_2_WIDE). Its plot will change when the GUI switches
  engines.
- **(b) reproduce legacy's DFS** (import `compute_spanning_tree` and the
  accumulation as a shared leaf). Bit for bit everywhere, but the new engine
  inherits a tree picked by set iteration.
- **(c) explicit sectors in the document** (`Mode.sector`). Migration fills
  it with legacy's frames, so every file is bit for bit by construction, and
  rule (a) is the default for modes that have none.
  - This is the natural end state: the drawn RWA becomes visible, editable
    data, and it is what the "same resonator" tag (W2) and the sector glyphs
    need.
  - It has no consumer until the GUI holds the model (C1): until then, every
    Show S snapshot re-migrates from the legacy state anyway.

My recommendation: **(a) now, and (c) with C1.** For DTWPA_2_WIDE the gate
asserts two things:
- the inconsistency is reported;
- with legacy's frames injected through a test-only override, S is bit for
  bit.

So the only difference is the frame choice, and it is pinned. If you would
rather keep the plot, (b) costs about 20 lines and can be removed at C1.

## Gate (tests/test_engine_msuper.py, Qt-free)

- For every lumped shipped file: `engine.solve(doc)` against
  `[compute_job(j) for j in compile_jobs(doc)]`. The checks:
  - the same number of components in the same order, and the same root;
  - the same None-ness (the 8 jobs with missing parameters);
  - S `np.array_equal`;
  - port order equal under the map `port<k>` <-> `port:<k>` and
    `bext<n>` <-> `n`, with the same port labels.
- DTWPA_2_WIDE: the exception described above (if option a).
- Edits the files have not seen, built directly on the Document: TEUFELATOR
  at roots 4 and 6 (a conjugated root flips the sweep), a custom grid, an
  edited rate and frequency, a deleted mode (components recomputed), a loss
  port, and an added frame-inconsistent edge (the warning fires and S is
  unchanged).
- Non-lumped files are refused with the milestone-2 message. The package
  imports no Qt.

## Questions for JA

- **M1, frames:** (a), (b) or (c) above. I recommend (a) now and (c) at C1.
- **M2, phase reference (F2):** for milestone 1, keep legacy's convention
  (the phase sits on the earlier mode in mode order). Bit for bit requires
  it.
  - Later, probably at C1: refer the phase to the drawn direction a -> b,
    with migration converting it so that no loop flux changes. Same-sector
    edges convert exactly (phi -> -phi). Cross-sector edges need
    phi -> 180 - phi, which is good to about an ulp but not bit for bit.
- **M3, f_p semantics in the schema (F1, F4):** for milestone 1 the
  compiler reads `Coupling` as "derived" and a 0 Hz `Pumped` as "static",
  with no schema change. The clean schema would be
  `Coupling.frame = "static" | "derived"`, with no 0 Hz tones. Do that at
  C1, together with M2?
- **M4, 12-decimal rounding (F3):** keep it for milestone 1. Drop it once
  bit-for-bit against legacy is no longer the gate (nu = m . f exactly).
- **M5, parallel edges:** sum them (physically right; no shipped file has
  them), or refuse with an issue?
- **M6, multi-component root:** legacy ignores `solve.root` when there are
  several components. Keep that for milestone 1?

## Not in milestone 1

- Lines, blocks and element pumps; sector windows; Sigma_0 with internal
  planes (milestone 2).
- The RWA check (it will reuse `frames.py`).
- GUI wiring. Show S stays on the legacy engine. Switching it, or adding an
  "engine" setting, is a later slice once you have chosen M1.
