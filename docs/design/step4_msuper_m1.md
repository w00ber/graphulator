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

**F1. Frames come from the spanning tree; a stored chord f_p is not an
input.** *(Corrected 18 Nov after JA's reply. The first version of this
note said some drawings had conflicting pump frequencies. That was my
misreading.)*
- The design is right: f_p is entered on tree edges only. A chord's f_p is
  derived from its cycle. The GUI shows it read-only ("(chord)", in blue)
  and never writes it back.
- But the document does not record which edges are chords. `compute_job`
  rebuilds the tree from the root on every solve. It does not use the tree
  saved in `legacy_frames`, which is stale in 2 of the 49 files that have
  one.
- An edge that was a tree edge when its f_p was typed in keeps that value
  after it becomes a chord. The value is then dead but still stored:
  - FPJA_PRA: A-B is a chord with derived f_p 1.601, but 0.0 is stored;
  - DTWPA_2_WIDE: 10-13 is a chord with derived f_p 12.12, but 12.0 is
    stored.
- My first compiler draft read every stored f_p as an input. That is what
  produced the apparent loop conflicts. They are not in the physics.
- **The real hazard:** the tree depends on the root, and on DFS order
  (Python set iteration over int-tuple keys, deterministic but arbitrary).
  If the tree changes, a stale value becomes an input again, silently.
  Example: FPJA_PRA with the root moved from A to B. The tree changes, A-B
  becomes a tree edge carrying the stale 0.0, the 13.671 GHz C-B pump
  becomes the chord, and the frames change (B at 0 instead of +1.601
  relative to A).
- Data semantics:
  - f_p = None marks an edge that has only ever been a chord.
    Migration made it a `Coupling` (documented as "static"), which is
    misleading.
  - f_p = 0 is a static tree edge. Migration made it a `Pumped` with a 0 Hz
    tone.
  - Legacy refuses a tree edge whose f_p is None.

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

## Frames: the one physics decision **[decide M1]** (revised)

The frames must come from the same tree legacy uses, because that tree is
what decides which stored f_p values are inputs. The priority rule I
proposed first reads every stored f_p as an input. It matched 50 of 51 jobs
only by luck, and it is wrong on DTWPA_2_WIDE, where it uses the dead 12.0
value. **Withdrawn.**

**Options:**
- **(b) legacy tree as a shared leaf (now recommended for milestone 1).**
  `frames.py` calls autograph's `compute_spanning_tree` and the pump-sign
  rule (the same root, edges and hub bridge links as `compute_job`). It then
  carries integer sector vectors along the tree instead of float sums.
  - Expected: bit for bit on all 51 computing jobs.
  - Issues reported:
    - **stale chord f_p**: a chord whose stored f_p is not None and differs
      from the derived value (FPJA_PRA, DTWPA_2_WIDE, and others to be
      listed). It is information only; S does not use it.
    - a tree edge with no f_p: legacy's refusal, kept.
- **(c) the tree, or the per-mode sectors, as document data at C1.** Then a
  change of root cannot reshuffle which f_p are inputs. The root only picks
  the sweep axis, and the tree changes only when the user edits topology,
  re-rooting explicitly. Migration fills it from legacy's tree, so nothing
  moves.
  - Open sub-question for C1: should the GUI keep the user's tree when the
    root changes (re-root the same tree), rather than rebuilding it by DFS?
  - Re-rooting a fixed tree leaves every relative frame unchanged. That is
    the behaviour the "derive chords" design implies.

Recommendation: **(b) for milestone 1, (c) at C1**, plus a validation
warning for stale chord values from now on.

## Gate (tests/test_engine_msuper.py, Qt-free)

- For every lumped shipped file: `engine.solve(doc)` against
  `[compute_job(j) for j in compile_jobs(doc)]`. The checks:
  - the same number of components in the same order, and the same root;
  - the same None-ness (the 8 jobs with missing parameters);
  - S `np.array_equal`;
  - port order equal under the map `port<k>` <-> `port:<k>` and
    `bext<n>` <-> `n`, with the same port labels.
- Stale chord f_p values are reported (FPJA_PRA, DTWPA_2_WIDE) and S
  ignores them.
- Edits the files have not seen, built directly on the Document: TEUFELATOR
  at roots 4 and 6 (a conjugated root flips the sweep), a custom grid, an
  edited rate and frequency, a deleted mode (components recomputed), a loss
  port, and FPJA_PRA re-rooted at B (pins legacy's tree-dependent behaviour;
  (c) fixes it at C1).
- Non-lumped files are refused with the milestone-2 message. The package
  imports no Qt.

## Questions for JA

- **M1, frames:** (b) now, (c) at C1 (revised after JA's reply; (a) is withdrawn).
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
