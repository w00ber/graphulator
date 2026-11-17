# Layer 0: a Qt-free document model (design note, for review)

*Status: proposal, 16 Nov 2026; steps 1-2 built 17 Nov (see "as built"
sections near the end; step 2 has open quirks Q1-Q3). Sections tagged **[decide]**
need JA's call (they map to HANDOFF §12). Everything else is a default I'll
build unless told otherwise.*

## Goal

There should be one in-memory model of a paragraphulator document. The GUI,
the M_super engine, `misc/make_*` and the MCP all read and write it, and none
of them imports Qt. Today a document exists only as the `Graphulator` widget's
attributes, and three translators disagree about what it means (GUI payload,
code export, `extract_from_pgraph`). The model replaces all three. Each
consumer then becomes either a *view* of the model (GUI, figure export) or a
*compiler* from it (engine assembly, source-level export).

The design rule: **the document stores physical objects, never their
expansion.** A line is one block, not 2N comb nodes. A pump is one object,
not (2N)² edges. A twin is a view of sector −1, not a second line. Which
poles become modes, how many sectors, and whether the tail is closed are
*solve settings*, so they live in the document's solve section, not in the
circuit.

## Package layout

```
src/graphulator/model/
  __init__.py      Document, load(), save(), validate()
  schema.py        dataclasses (below); to_dict()/from_dict(), no Qt, no matplotlib
  validate.py      structural + physical checks -> list[Issue(level, path, msg)]
  migrate.py       pgraph 2.0 / 3.0 -> 4.0 (pure dict -> dict)
  units.py         frequency/impedance unit handling (engine is scale-free)
```

**Dataclasses (stdlib), no pydantic.** The reasons: no new dependency in a
conda/PySide6 app, dataclasses are trivially picklable for the existing
worker-process `_compute_sparams_job` path, and validation here is mostly
*physical* (sector consistency, plane references, signature rules), which a
type library does not do for us anyway. Hand-written `from_dict` with explicit
defaults is also where migration tolerance lives. **[decide 12.2]**

## File format

- Same `.pgraph` extension, `"format": "pgraph"`, `"version": "4.0"`.
  **[decide 12.2]**
- `load()` accepts 2.0 / 3.0 / 4.0. Older versions go through `migrate.py`,
  which is pure dict→dict, so its tests need no GUI. `save()` always writes 4.0.
- Unknown top-level and per-object keys are preserved in `extras` and written
  back, so a 4.0 file edited by a newer build survives an older one.
- The embedded `svg` thumbnail stays an optional blob (the GUI writes it; the
  MCP may omit it).

## Objects

```
Document
  meta        {created, modified, title}
  units       {frequency: "GHz", impedance: "ohm"}   # display only; engine sees ratios
  sweep       {start, stop, points}                  # center/span is GUI sugar
  tones       [Tone{id, f, label}]                   # pump tones; vector sector index m ∈ Z^len(tones)
  planes      [Plane]
  blocks      [Block]
  modes       [Mode]
  couplings   [Coupling]                             # static mode–mode (M_iso off-diagonals)
  attachments [Attachment]                           # K entries: mode ↔ plane
  pumped      [Pumped]
  solve       SolveSettings
  drawing     Drawing
  notes       str (markdown)
  code        {imports, node_code, edge_code, global_code}   # today's code_properties, verbatim
  extras      {}
```

**Plane** — a terminal pair (single-ended, ground implicit).
`{id, label, kind: "port" | "internal", Z0: float | None}`.
A `port` plane is a scattering channel and **carries its own Z0**. That fixes
the `Z0_port`-lives-on-the-line defect in `TODO.md`. An `internal` plane is
any other node of the circuit (a line end, an attachment point, a pumped
element's node). Ports carry no sector or signature (L Ch. 9). The engine
makes one port row per sector.

**Block** — one LTI element: `{id, type, params, terminals: {name: plane_id}}`.

| type | params | terminals |
|---|---|---|
| `line` | `Z` or `sections[{Z, frac}]`; length as `FSR` **or** `theta_deg@f_ref`; `alpha` | `x0`, `xL` |
| `L`, `C`, `R` | value (or `f_Z` reactance spec, as today's `load`) | `a`, `b` (`b` omitted = ground) |
| `coupler`, `inverter`, `gyrator`, `circulator` | per type (circulator: `handedness`) | per type |
| `touchstone` | `path`, `ref_Z`, `convention: "j"|"i"`, `out_of_band` | `p1..pn` |
| `subcircuit` | `path` (`.dgm`, §10) or inline `Document` | declared terminals |

Phase 1 implements `line`, `L`, `C`, `R`, open and short. The rest are
reserved names so the schema does not churn later. Each block type gets a
pure function `(params, ω) → (A, B)` hybrid rows over its terminals (HANDOFF
§8). That belongs to the engine, not the schema; the schema only guarantees
that the terminals resolve to planes.

**Mode** — a dynamical degree of freedom with a row in M_iso.
`{id, label, freq, B_int, conj: bool, origin}`.
- Hand-drawn nodes: `origin = {"kind": "lumped"}`, and `conj` is kept as
  today. The legacy frame and spanning-tree machinery still assigns its
  sector (HANDOFF §6, "Frames").
- Promoted line poles: `origin = {"kind": "line_pole", "block": id, "n": int,
  "polarity": ±1}`. `freq` is then *derived* and not stored, or stored only
  as a cache that validation checks. A line with no promoted poles is
  entirely in Σ₀ ("no modes").
- The generated label (HANDOFF §7.4, e.g. `a*_TL,3[ω−ω_P]`) is computed from
  `origin` and the sector, never stored. `label` is the user's name for the
  element X.

**Coupling** — static mode–mode: `{id, a, b, rate, phase}`. Today's edges
without `f_p`.

**Attachment** — a K entry: `{mode, plane, weight, phase_deg, kind:
"shunt"|"series"}`.
- Today's port attachments (`node_id, rate, sign`) map to `weight =
  sqrt(rate)`, `phase = 0 | 180`. The Phase-1 restriction to {0, 180} becomes
  a *validation* warning, not a schema limit (L Ch. 4: the attachment phase
  is exact).
- Legacy per-node `B_ext` migrates to an implicit port plane plus one
  attachment. That is what `get_effective_hubs` already does at build time;
  it now happens once, at load.
- A loss hub (`monitored=False`) is an internal plane terminated in an `R`
  block. It is no longer a special hub flavour.
- **Taps of a mode onto a line end** (`ends.x0 = [{kind: node, rate, sign,
  n_ref}]`) become an Attachment of the mode to the line's end plane. **Open
  point:** today's tap `rate` is anchored at `n_ref`, like the pump. Turning
  it into a plane weight means writing the anchor formula backwards (the tap
  profile, `test_line_taps.py`). Migration keeps the legacy `{rate, n_ref}`
  under `legacy_anchor` until that inverse has been derived and gated. No
  ansatz.

**Pumped** — one object per modulated thing, never flattened:
- `{kind: "element", block: id, param: "1/L"|"C", tone, depth, phase,
  profile?}`: a modulated element at a plane. Today's line `pump` is a
  modulated `L` block at the pumped end. Its `rate`/`n_ref` pair migrates to
  `depth = δ(1/L)` through the pinned conversion `rate = (2 FSR/π) g_nm`
  (docs/pumped_line_termination.md §6), which E0 just exercised. `twin_id`
  is dropped from physics.
- `{kind: "coupling", a, b, tone, rate, phase, frame_rule?}`: a modulated
  mode–mode coupling. Today's hand-drawn edges with `f_p`. Tones are
  deduplicated by frequency at migration.

**SolveSettings** — `{sectors: {tone_id: [m_lo, m_hi]} | "auto",
kept_poles: {block_id: [n...] | "f_max:<f>"}, tail_closure: bool, rwa:
{...}}`. This is where today's `f_max` and the tail checkbox live. **[decide
12.3]** for the default window; E0 says two sectors is not a safe default
for TL_3 (see `misc/msuper_E0_tl3_sectors.out`).

**Drawing** — everything visual, keyed by the physics ids:
`{view, nodes: {mode_id: {...}}, edges: {coupling_or_pump_id: {...}},
ports: {plane_id: {...}}, blocks: {block_id: {...}}, sector_views: [...]}`.
The per-object style keys are exactly today's (`pos, color, color_key,
node_size_mult, ...`, port/line glyph keys from `glyphs.py` and
`explicit_ports.py`), so the GUI round-trips unchanged. `sector_views` is
where a "twin" lives after migration: `{block, sector: -1, pos, angle,
style}`. The GUI can keep drawing TL* exactly as now while the physics no
longer duplicates it.

## Validation

`validate(doc) -> [Issue]`, which never raises on user content:
- referential: every terminal, attachment and pump resolves; ids are unique;
- structural: each port plane has a Z0 > 0; a line has exactly one length
  spec;
- physical (warnings): attachment phase ∉ {0, 180} while the legacy engine is
  selected; a pumped element whose sector window is narrower than
  `solve.sectors`; a sweep that crosses a line pole on the grid (suggest a
  nudge).

## Migration map (3.0 → 4.0), summary

| 3.0 | 4.0 |
|---|---|
| `nodes[i]` (+ `scattering_assignments` freq/B_int) | `Mode(origin=lumped)` + `drawing.nodes` |
| node `B_ext` (no explicit port) | implicit `Plane(port, Z0=…)` + `Attachment` |
| `edges` without `f_p` | `Coupling` |
| `edges` with `f_p` | `Pumped(kind=coupling)` + `Tone` |
| `ports[j]` + `attachments` | `Plane(port)` + `Attachment`s + `drawing.ports` |
| `line_resonators[k]` (primary) | `Block(line)` + two internal planes (or the port plane at a port end) + `drawing.blocks` |
| line `Z0_port` | the port plane's `Z0` |
| line `load` | `Block(L, f_Z)` on the loaded end plane |
| line `pump` | `Block(L)` (or open) at that end + `Pumped(kind=element)` |
| twin line (`conj`, `twin_of`) | `drawing.sector_views` only |
| `f_max`, tail checkbox | `solve.kept_poles`, `solve.tail_closure` |
| `scattering.frequency` | `sweep` |
| `code_properties`, `notes`, `view`, `svg` | verbatim |

## How I'd build it (order)

1. `schema.py` + `migrate.py` + round-trip tests: every file in
   `examples/pgraphs` and `examples/test_scenes` must load, migrate, save
   and reload to an equal `Document`.
2. A **compiler** `model → legacy payload` (`nodes, edges,
   scattering_assignments, hubs, line_resonators`) that reproduces today's
   `_build_sparams_job` input. The gate: S is bit-identical to the GUI path on
   every example (E1 and E12 in miniature). This is what lets the GUI,
   export and `extract_from_pgraph` all switch to the model *before* the new
   engine exists.
3. The GUI reads and writes through the model (serialize/deserialize first,
   then live state).
4. The engine (Workstream A) compiles the same model directly to M_super,
   with the legacy compiler kept as the regression oracle.

## Decisions (JA, 17 Nov 2026)

1. **12.2:** stdlib dataclasses, no pydantic. Keep `.pgraph`, version 4.0.
2. **Twin:** the twin leaves the physics and survives only as
   `drawing.sector_views`. Deleting the twin view hides it; removing the
   idler physics means removing the pump (or setting the sector window to {0}).
3. **Taps:** keep the legacy `{rate, n_ref}` under `legacy_anchor` and compile
   it through the comb path until the inverse tap profile is derived and
   gated (tracked follow-up).
4. **Solve settings** travel with the document.
5. **12.3 default sector window:** accepted: `sectors: "auto"`
   (grow symmetrically from {-1..0}, stop when max_sweep |dS| relative to
   (G-1) < `sector_tol` = 1e-3, hard cap `sector_max` = 16 with a
   not-converged warning); an explicit `[m_lo, m_hi]` overrides.

## Step 1 as built (17 Nov 2026)

`src/graphulator/model/` (schema, migrate, validate; `units.py` deferred until
something needs it) and `tests/test_model_roundtrip.py`. Gate: all 70 shipped
`.pgraph` files migrate with no validation errors, save/reload as 4.0 to an
equal Document, and `to_legacy()` reproduces the original 2.0/3.0 dict
exactly (only canonicalizations: line-end connections in list form, and the
derived edge `from_to` string, which is stale in a few files). `to_legacy()`
is also the bridge for steps 2-3: the GUI and engine can consume a 4.0
document through today's loader before they read the model natively.

Deviations from the text above, all for exact round-trip:
- `Attachment` stores the legacy `rate` (+ `phase_deg`); `weight = sqrt(rate)`
  is derived.
- `Sweep` stores `center/span/points` as the GUI does (start/stop derived);
  the oldest files' start/stop form is kept verbatim.
- Line pumps keep a `legacy_anchor {rate, n_ref, coupling, end}` like taps
  (3a); `depth = delta(1/L)` is computed by the engine, not stored, until the
  anchor inverse is gated for loaded/stepped lines.
- A line end is the port plane it terminates on, else an internal plane
  `line<id>.<end>`; more than one port on one end is rejected.
- Unmonitored ports (loss hubs) -> internal plane + `R` block with
  `params = {"R": "matched"}`. No shipped file has one yet.
- Self-loops without physics (the legacy `B_ext` marker) are drawing-only.
- Ids are deterministic from legacy ids (`n<node>`, `e<from>_<to>`,
  `port<id>`, `line<id>`, `bext<node>`, ...); legacy list order is kept in
  `drawing.order`.

## Step 2 as built (17 Nov 2026)

`src/graphulator/model/legacy_job.py`: `compile_jobs(doc, f_root_s=None,
tail_closure=None)` returns the job list that Show S builds for the same file
(`_compute_and_plot_sparams` -> `_build_sparams_job`), and `compute_job(job)`
turns one job into S. `compute_job` is the old
`graphulator_para._compute_sparams_job` moved out of the Qt module. The old
name is kept as an alias, so the worker thread and the scripts are unchanged.
The module imports no Qt (a test checks this).

**Gate** (`tests/test_model_legacy_job.py`, 143 tests). Each of the 70 shipped
files is opened in a fresh window the way File > Open does it, and the GUI's
jobs are built. They are compared with `compile_jobs(load(path))`:
- every job matches field by field;
- S matches bit for bit (`np.array_equal`), and so do `port_ids` and
  `port_dict`;
- the document's sweep grid is the GUI's grid.

TL_3 is also checked with the tail closure switched off. All of it passes on
the first run of the compiler.

**How it works.** The compiler takes `to_legacy(doc)` (exact, from step 1) and
redoes, without Qt, everything the GUI does between opening a file and
building a job:
- the loader's normalization: dropped dangling attachments and ends, float
  coercion, sections canonicalized, implied `port_end` ports materialized;
- twin sync;
- `_find_connected_components`;
- the injection-root rule;
- hub, tap-edge and pump-bus synthesis.

The pure leaves the two paths share now live in `legacy_job.py`, and
`explicit_ports.py` imports them from there. They are `line_payload`,
`port_hub_payload`, `pump_partners`, the pump anchor and frame rule,
`clamp_mode`, `end_conns` and `TWIN_MIRRORED_KEYS`. With one copy of each, the
two paths cannot disagree about the physics. What the gate tests is the
translation around those leaves, which is the part that was duplicated.

Going through `to_legacy` is deliberate. This compiler is the regression
oracle for step 4, so its job is to equal today's GUI, not to be elegant. The
M_super compiler will read the model objects directly.

**GUI quirks the compiler reproduces on purpose (for JA: fix or keep?)**
- **Q1: the saved injection root is ignored on load.** `_deserialize_graph`
  tries to select `scattering.injection_node_id` in the injection combo
  before `_enter_scattering_mode` has filled the combo. On a fresh window the
  selection silently fails, and the root becomes the first port node in node
  order. Three shipped files are affected:
  - `TEUFELATOR` saved root 6 but gets root 4. Node 4 is conjugated and node 6
    is not, so the sweep axis flips sector, and |S| differs by up to ≈10
    between the two roots.
  - `DTWPA_8MODE` and `DTWPA_MINIMAL2` saved ids that no longer exist.

  In a window that already had a file open, the stale combo can make the
  selection succeed, so today the root depends on what was open before. My
  suggestion: restore the root after the combo is filled, and fall back to
  the current rule when the saved id is not a port node. That changes the
  TEUFELATOR plot, which is why it is your call. Once decided, the root
  belongs in `solve` rather than `legacy_frames`.
- **Q2: the sweep is rounded by the spin boxes.** Files store spin-box
  stepping residue, e.g. center 5.9999999999999964 or span 0.2999999999999994.
  The GUI rounds that to 2 decimals and clamps it to the boxes' ranges, and
  the plot is computed from the rounded values. `sweep_grid` does the same,
  reading the live `graphulator_para_config` limits. Six shipped files would
  give a slightly different grid without it. A center below 0 is clamped to
  0, so a sweep across zero cannot be saved from the GUI. Tests build such
  sweeps directly.
- **Q3: tail closure is not saved.** `line_tail_closure` is session state.
  The compiler uses `solve.tail_closure` and falls back to the app default
  (on). Per decision 4 the GUI should save it in step 3.

## Decisions on Q1-Q3 (JA, 17 Nov 2026) -- to do first in step 3

1. **Q1: restore the saved root.** Select `scattering.injection_node_id`
   after `_enter_scattering_mode` has filled the combo. Fall back to today's
   rule (first port node) only when the saved id is not a port node of the
   shown component. The compiler follows the same rule, and the root moves
   into `solve`. Expected effect: `TEUFELATOR` goes back to the plot its
   author saved (root 6), not the one a fresh open shows today (root 4).
2. **Q2: store and use sensible numbers.** User-entered quantities are
   quantized to their widget's precision as sgn(x) * round(|x|, d), half
   away from zero. That is what `QDoubleSpinBox` already does (checked:
   -0.125 -> -0.13), while Python's `f"{x:.2f}"`/`round` round half to even
   (-0.125 -> -0.12). `_spin` in `legacy_job.py` uses the Python rule and
   must be switched. No shipped file hits an exact half, so the gate did not
   catch it.
   - The current GUI already saves rounded values, because `value()` returns
     the rounded number. The residue in old files (center
     5.9999999999999964) comes from older builds and scripts. Quantize at
     migration and at save, so the model stores sensible values.
   - Derived numbers (linspace grids, computed rates) are NOT rounded.
   - Keep the center clamp at 0 only if the center is always a lab-frame
     frequency. A rotating-frame detuning sweep needs `FREQ_CENTER_MIN < 0`
     (open: check whether anything downstream assumes center > 0).
3. **Q3: save `tail_closure`** in the document (`solve.tail_closure`). It
   is a setting of the legacy discrete-comb engine, which stays the GUI's
   engine until step 4. Under M_super, a line's non-promoted part is exact
   (Σ0), so there is no truncated tail and the flag is ignored.

## Step 3a as built: Q1-Q3 (17 Nov 2026)

- **Q1 (root).** `SolveSettings.root` (a mode id, `n<node>`) now holds the
  injection root. Migration moves `scattering.injection_node_id` into it, and
  `to_legacy` writes it back. The GUI clears the injection combo on every
  load and remembers the saved id. `_enter_scattering_mode` applies it right
  after it fills the combo (`_apply_pending_injection_node`, signals
  blocked, so the spanning tree saved in the file is kept). If the id is not
  a port node of the shown component, the combo keeps its first port node.
  `compile_jobs` follows the same rule. A root that does not name a mode is a
  validation *warning*. Effects:
  - TEUFELATOR is solved at root 6 again.
  - DTWPA_8MODE and DTWPA_MINIMAL2 fall back as before.
  - The root no longer depends on which file was open before (tested by
    opening files in sequence in one window).
- **Q2 (quantize).** `model/quantize.py` does `quantize(x, d)` with Decimal
  `ROUND_HALF_UP` on the exact binary value. It matches `QDoubleSpinBox` on
  40k values, exact ties included (-0.125 -> -0.13; 2.675 -> 2.67, because
  the double is 2.67499...). `sweep_grid`'s `_spin` uses it. The sweep is
  quantized at migration (start/stop files become center/span, as in the GUI
  loader) and in `save()`; the in-memory doc is not modified. The range clamp
  stays in `sweep_grid` only. It is a widget limit, not a property of the
  data. The round-trip gate's canonicalization now includes the quantized
  sweep.
  - **Scope, deliberately narrow:** only the sweep is quantized. Other
    user-entered numbers (mode freq, rates, FSR, ...) are held by table
    cells and dialogs, not by the sweep spin boxes. Quantizing them at
    migration would change S relative to today's GUI, which loads them
    unrounded, and would break the bit-identical gate. That needs the GUI to
    quantize at load in the same step. Left for step 3 proper.
- **Q2 open point (center < 0), audited.** No physics assumes f > 0. M is
  linear in f, the comb holds ±n·FSR, and the conjugate flips are
  sign-agnostic. A sweep can already cross zero today (center 0.1, span 2).
  What lowering `FREQ_CENTER_MIN` would also need:
  - `sweep_grid` clamps to the same constant, so it follows automatically.
  - The manual x-limit spin boxes are `setRange(0, 1000)` (para ~8452/8482)
    and would clamp negative xlims.
  - Mode markers loop over `n = 1..N` only, so the -n half gets no markers
    on a negative sweep (cosmetic).
  - **Pre-existing bug, reachable now:** exactly f = 0 gives NaN when a port
    shares an inductively loaded line end. `input_impedance` does
    `1/(1/ZL + 1/Z_open)` with ZL = 0 and Z_open = A/C -> inf. An odd point
    count over a zero-crossing sweep lands on it. Tracked separately.
  - Not changed yet: whether to lower the minimum is your call.
- **Q3 (tail closure).** The GUI writes `scattering.tail_closure` and
  restores it on load. A file without the key, and File > New, reset it to
  the app default (on). It is no longer session state that leaks between
  files. Migration maps it to `solve.tail_closure`.

Gates: round-trip (all shipped files), compiler == GUI field for field and
S bit-identical (now with the saved root), plus new tests for TEUFELATOR's
root, file-sequence independence, and tail-closure save/restore.

## Questions for JA (original, answered above)

1. Dataclasses vs pydantic; keep `.pgraph` + 4.0 (12.2).
2. Is it acceptable that the twin disappears from the physics and survives
   only as `sector_views`? It changes what "delete the twin" means in the UI
   (it would become "stop pumping").
3. Taps: hold `legacy_anchor` until the inverse tap profile is derived (my
   default), or derive it first?
4. Should `solve` settings travel with the document (my default: yes, so
   that a file reproduces its plot), or should they be per-session?
