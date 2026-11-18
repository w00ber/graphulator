# Layer 0: a Qt-free document model (design note, for review)

*Status: proposal, 16 Nov 2026; steps 1-2 built 17 Nov, step 3 slices 1-4
built 17-18 Nov (see "as built" sections near the end). Sections tagged **[decide]**
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
  - At exactly f = 0, a port sharing an inductively loaded line end gives
    NaN (`input_impedance`: ZL = 0, Z_open -> inf). **JA: not a bug.** The
    impedance there is undefined, and NaN is the right placeholder in the
    arrays. Leave it.
  - **JA: keep `FREQ_CENTER_MIN = 0`.** Nothing sweeps below zero today, so
    there is no reason to open it now.
- **JA on Q2 scope:** quantizing only the sweep is accepted. Other
  user-entered numbers are rounded when the GUI reads through the model
  (step 3 proper), together with GUI-side rounding at load.
- **Q3 (tail closure).** The GUI writes `scattering.tail_closure` and
  restores it on load. A file without the key, and File > New, reset it to
  the app default (on). It is no longer session state that leaks between
  files. Migration maps it to `solve.tail_closure`.

Gates: round-trip (all shipped files), compiler == GUI field for field and
S bit-identical (now with the saved root), plus new tests for TEUFELATOR's
root, file-sequence independence, and tail-closure save/restore.

## Step 3, slice 1 as built: file I/O through the model (17 Nov 2026)

JA chose option (a): the GUI writes 4.0, and a legacy copy is available for
older builds.

- `CommonWindow` has two identity hooks, `_file_dict_from_state` and
  `_state_dict_from_file`. They are used by Save / Save As, Open, recent
  files, Reload Last Graph and the close-time autosave. The Graphulator
  (non-para) app is unchanged.
- Paragraphulator overrides both hooks:
  - **Open** (and Examples): `model.from_dict` -> `to_legacy` -> the
    existing `_deserialize_graph`. Every 2.0/3.0/4.0 file takes the one
    migration path. `.graph` files, and pgraph versions the model rejects,
    go to the GUI loader unchanged.
  - **Save**: `_serialize_graph()` -> `from_legacy` -> `model.to_file_dict`,
    which writes 4.0. If the conversion raises, the legacy dict is written
    and logged, so a save never loses work.
  - **File > Save Legacy 3.0 Copy...** writes the old layout (via the model,
    so it is quantized like a 4.0 save). It is a copy: the open file's path
    and the modified flag are not touched.
- **4.0-only settings carried across the GUI.** `solve.sectors`,
  `sector_tol`, `sector_max` and `units` have no slot in the GUI's legacy
  state. They are stashed at Open and restored at Save, so Open -> Save
  does not reset them. File > New and every Open reset the stash.
- `model.to_file_dict(doc)` is the 4.0 dict that `save()` writes.

Gate (`tests/test_gui_model_io.py`, every shipped file):
- opening through the model leaves the GUI in the same state as the raw
  open: same `_serialize_graph()` and the same Show S jobs;
- a GUI save is valid 4.0 (no validation errors), and reopening it gives
  the same state as the equivalent reopen without the model;
- 4.0-only settings survive Open -> Save and do not leak into the next file;
- the legacy copy is 2.0/3.0 and reads back.

The comparisons exclude the `svg`/`kron_svg` renderings and the
serializer's timestamps.

**Pre-existing GUI quirk found (not fixed, model-independent).** The view
limits a file saves are not the view a reload shows. The first load into a
fresh window and the first reload of a GUI save both refit the view (e.g.
AMP_BA saves xlim ±7.776, and a reload shows ±5.4), and it is stable after
that. Opening a file twice therefore does not give the same view. The tests
compare against the same model-free reload instead of the file's view.

**Other readers of `.pgraph`:**
- `autograph.load_pgraph`, which scripts and `extract_from_pgraph` use, now
  converts 4.0 files through the model. A GUI-saved file still feeds the
  script path, gated by `test_gui_hubs`' golden-S test, which now goes
  through a 4.0 save.
- `misc/make_test_scenes.py` and `misc/make_line_examples.py` keep writing
  the legacy layout on purpose. The shipped examples are the 2.0/3.0
  fixtures the migration and compiler gates run on.
- Two GUI tests that read raw `scattering` keys from a saved file now read
  it through `model.load`.

**Note:** a GUI-saved 4.0 file records `meta.migrated_from` = the GUI's
internal layout (2.0/3.0). That is accurate for now, since the GUI state
still is that layout. It goes away when the GUI holds the model natively.

## Step 3, slice 2 as built: Show S compiles from the model (18 Nov 2026)

The GUI no longer builds its S jobs from its own widgets. Show S, the
background worker path and the truncation check all call
`Graphulator._sparams_jobs(f)`, which does
`compile_jobs(_model_document(), f_root_s=f, tail_closure=live flag)`:
- `_model_document()` is the live state as a Document: `_serialize_graph(
  render=False)` (no SVG thumbnails; rendering is the only slow part of a
  serialize) -> `from_legacy`, plus the 4.0-only settings carried from the
  opened file. A save writes the same Document, so the GUI cannot compute
  something its file would not reproduce.
- The connected components and the injection root are recomputed from the
  snapshot by the compiler, not read from the GUI's cached
  `scattering_components`. The root is the combo's choice (it reaches the
  model as `solve.root`), with the Q1 fallback.
- The sweep grid is still the spin boxes' (`f` is passed in), so an edited,
  unsaved sweep is what is solved.
- If the model cannot represent the state, `_sparams_jobs` logs the error and
  builds the jobs with the old live-widget builder (`_build_sparams_job`),
  so Show S keeps working. That builder stays only as this fallback and as
  the test oracle; it can go when the GUI holds the model natively.

Cost: 1-6 ms per Show S on the shipped examples (snapshot + migrate +
compile), against 1-15 ms for the solve itself at 401 points.

Gate (`tests/test_gui_show_s_model.py`):
- every shipped file, opened as File > Open does: model-path jobs equal the
  live-builder jobs field by field, and S is bit-identical;
- the same after live edits a file has not seen: an edited mode frequency and
  coupling rate, an unsaved sweep, a different injection-combo choice
  (TEUFELATOR root 4), a line's `f_max` with tail closure off, a deleted node
  (components and stale `B_ext` recomputed), two lines in two components;
- the truncation check's two solves go through the model (the doubled
  `f_max` reaches the Document), and a compile failure falls back to the
  live builder with a logged error.

**Next in step 3 (proposed order):**
1. Slice 3: the scattering-code export (done, below).
2. Slice 4: the rest of decision Q2 (done, below: residue snapping,
   option A).
3. Live state: the GUI holds a Document and its tables and dialogs edit it,
   with the widgets as views. That removes the snapshot, the legacy
   `_build_sparams_job`, and `meta.migrated_from` on GUI saves. This is the
   large one and wants its own design pass before code.

## Step 3, slice 3 as built: the scattering-code export from the model (18 Nov 2026)

`model/export_script.py` (no Qt): `scattering_script(doc, f_root_s=None,
tail_closure=None, traces=None, source=None)` renders the Export to .py /
Paste Buffer script from `compile_jobs(doc)`, the jobs Show S solves. The
GUI's `_generate_scattering_calculation_code` is now a thin wrapper: it
passes `_model_document()`, the spin-box grid, the tail-closure switch, the
checked S-parameter boxes and the file path. The ~600-line widget reader is
gone.

The script carries the job data literally (nodes, edges with the
synthesized tap / pump-bus edges, assignments, hubs, line macros, root) and
a `solve()` function that is `compute_job` written out against the public
autograph API. One component gives `scattering_matrix` / `gsm`, several give
`gsm_components[i]`, as before.

**What changed in exported scripts (the old exporter disagreed with Show S):**
- **Conjugated root.** Show S sweeps `-f` when the injection node is
  conjugated; the old script did not, so its S was the other sector's.
  Now the script flips like Show S. (This only bites a graph whose root is
  a drawn conjugated node. Line-only graphs such as the Lee-2013 scenes have
  no root, and the old export already matched them exactly.)
- **Spanning tree.** The old script reused the GUI's cached tree; Show S
  recomputes it from the root with hub bridge links. The script now does
  the same.
- **Tail closure.** The old script always used the default (on); now it
  writes the GUI's switch.
- **Numbers are exact** (`repr`), not `round(x, 9)`: a rounded literal is a
  slightly different circuit. Once slice 4 quantizes user-entered numbers,
  the literals are the clean values anyway.
- **Constraint groups** still become shared variables (`gP_group1 = ...`),
  but a member uses the variable only if its value equals the group's
  exactly; an edited-away member keeps its own literal.
- Node and edge dicts carry their parameters (as the job does), and the
  dead duplicate-label comment was dropped.

Gates:
- `tests/test_model_export_script.py` (Qt-free): for every shipped file the
  script, run, gives `compute_job`'s S bit for bit with the same port order;
  plus a custom grid with tail closure off, TEUFELATOR at both roots,
  constraint variables, multi-component trace selection, the full script
  (with plotting) running, and no Qt import.
- `tests/test_gui_show_s_model.py`: the GUI's export, run, equals Show S on
  every shipped file; an unsaved grid, the tail switch and the checked
  traces reach the script.
- The older export tests (`test_gui_hubs`, `test_pumped_line`,
  `test_stepped_line`, `test_intermode_lee2013`) pass unchanged.

## Step 3, slice 4 as built: residue snapping, Q2 option A (18 Nov 2026)

**Why not full quantization.** Rounding every user-entered number to its
widget's precision would have changed up to 36 values in the shipped
files (counted with the properties-panel precisions, e.g. FSR to 4). The
values fall into two groups:
- **Residue:** a few ulps off a clean number, e.g. 14.999999999999996,
  0.10000000000000003, 0.028399999999999998.
- **Deliberate digits:** values computed by the scene scripts and finer than
  any widget. The Lee-2013 FSR 4.008568771762118 puts f_A at exactly 1.840
  GHz. Z0_port 38718.407... gives exactly 2.9 MHz. The pump f_p equals
  f_B - f_A exactly.

Rounding the second group moves f_A by 13.5 kHz and detunes the conversion
pump by 23 kHz. That breaks the property the scene was built to have. Widget
precision is also not one number: B_int has 3 decimals (milli-units) in the
table but 1 in the node dialog, and f_p has 3 in the table but 4 in the pump
panel. **JA chose option A:** snap residue only.

**Rule** (`quantize.snap`): x becomes quantize(x, d) only when
`|x - q| <= 1e-12 * max(|x|, |q|, 10^-d)`. Otherwise x is unchanged. `d` is
the finest widget's precision in stored units, where milli-unit displays add
3 (`model.PRECISION`: freq 3, B_int 6, rates 5, pump rate 6, phases 1, tones
4, FSR 9, Ztx 2, Z0 2, f_max 4, f_ref 4, section Z 2, load f_Z 6). Derived
numbers are not touched: alpha (entered as a loss rate) and section
fractions (entered as angles). The sweep keeps its unconditional
quantization, since it only ever comes from its spin boxes.

**Where it runs** (`model/snap.py`, `snap_document`):
- at the end of `from_legacy`;
- in `from_dict` for 4.0 files;
- in `to_file_dict` (on a copy).

Every path goes through one of these: GUI Open, Save, Show S's snapshot, the
export and scripts. So the GUI rounds at load "together with migration" for
free. Tones that coincide after snapping are merged.

**Effect on the shipped files:**
- 10 values in 9 files move, all residue (AMP_BA, BOGO_AB_AMP x2,
  DTWPA_MINIMAL2, FIG15, FPJA_PRA, the degenerate Lee pump 3.68, TMP,
  WIDE_AB_AMP_2pole);
- every deliberate digit is kept;
- S moves by at most 1.5e-15.

**Gates re-baselined once.** The GUI's raw-file reference opens are now taken
on the snapped file: `test_model_legacy_job._gui_jobs` and
`test_gui_model_io`'s pre-model path. The round-trip canonicalization also
snaps. The snapped file is produced by `tests/snap_helpers.py`. It restates
the rule against the *legacy* field names, so the model's Document-level
field list is checked against an independent list. It is not checked against
itself. New tests:
- residue vs deliberate cases;
- shipped residue snapped;
- the Lee scene's computed numbers untouched;
- tone merge;
- 4.0 load and save;
- S change below 1e-13 on the affected files.

## Step 3, live state: design pass (for review, 18 Nov 2026)

*Proposal only, no code yet. Sections tagged **[decide]** need JA's call.*

### Where things stand

The GUI's editable state is still the legacy layout:
- `nodes` and `edges` are dicts that mix physics and style, and edges hold
  references to the node dicts;
- `scattering_assignments` is keyed by node id and `(from, to)`;
- `ports`, and `line_resonators` with the twin as a second, synced line;
- constraint groups keyed by *labels*;
- whole-state undo snapshots (`_capture_state`).

The model reaches the GUI only as a snapshot (`_model_document()`), taken at
Show S, export and save (slices 1-4). Rough size of a switch, counted with
grep over the GUI modules:

| touch point | sites |
|---|---|
| `scattering_assignments` (55 of them writes) | 114 |
| `nodes` / `edges` | 150 / 114 |
| `line_resonators` / `ports` | 68 / 39 |
| constraint groups | 44 |
| `_save_state()` (undo points) | 58 |
| edge -> node-dict references | 47 |
| twin sync calls | 21 |

### What live state buys, and what it does not

It does **not** gate step 4. The M_super compiler needs a Document, and
`_model_document()` already gives one for the live state at 1-6 ms. The
MCP does not exist yet. When it does, it can work on files or on that same
snapshot.

What it does buy:
1. **One representation.** This removes the snapshot, `_build_sparams_job`,
   the GUI normalization that `legacy_job._load_state` re-implements, twin
   sync, and `meta.migrated_from` on GUI saves.
2. **4.0-only settings get a home.** Sector windows, `kept_poles` beyond
   `f_max`, and `sector_views` have no slot in the legacy state today.
   Slice 1 needed the `_model_carry` stash just to keep `solve.sectors`
   alive from Open to Save. Every M_super-era GUI feature would need another
   stash.
3. **Decision 2 becomes real in the UI.** Today TL* is a line object that
   can be selected and deleted. In the model it is a drawing of sector -1,
   and removing the idler physics means removing the pump.
4. **Edits can only produce what the model can represent.** The
   model-failure fallbacks in Save and Show S then go away.

### Options

- **A. Big bang:** replace the dicts with Document objects everywhere at
  once. Rejected. It touches ~600 sites in one change, with no oracle
  between start and end.
- **B. Write-through proxies:** `self.nodes` etc. become dict-like views
  over the Document. Rejected. Identity semantics (selection lists, edge ->
  node references, undo snapshots holding the same dicts) make the proxies
  subtle, and they hide the cost rather than remove it.
- **C. Physics first, one object kind per slice (recommended).** The
  Document owns the physics. The GUI dicts keep only drawing state plus the
  model id. Every physics edit goes through a small Qt-free edit API,
  `model/edit.py`: plain functions on a Document, such as
  `set_mode(doc, mid, freq=...)`, `set_coupling(...)`,
  `set_line_param(...)`, `add_mode(...)`, `delete(...)`. Each returns a
  change record (which ids changed, and whether the topology did). The GUI
  turns the record into table and plot refreshes. The MCP and tests can
  call the same functions.
- **D. Status quo.** Keep the legacy state as the editable one and the
  model as a snapshot, indefinitely. That stays viable until (2) bites.

### Proposed slices under C

Each slice keeps the snapshot path alive as its oracle until the slice's
last commit.

1. **C1, assignments:** move frequencies, rates, phases, f_p and B_ext
   (the 55 writes, the tables, the dialogs) to `doc.modes`, `couplings`,
   `pumped` and `attachments`, and the GUI reads them back from the doc.
   Constraint groups are promoted to the model and keyed by object id, not
   by label (labels can be duplicated; the old exporter had a
   duplicate-label warning for this reason). **[decide L4]**
2. **C2, lines:** physics params, load, pump and sections move to blocks,
   `pumped` and `kept_poles`. The twin becomes `drawing.sector_views`, and
   `sync_twin` is deleted. This is where decision 2 lands in the UI.
   **[decide L3]**
3. **C3, ports, attachments and taps:** move to planes and attachments.
4. **C4, topology and undo:** add/delete for each kind goes through the
   edit API. An undo point becomes (Document copy, drawing copy).
   `_serialize_graph` becomes `to_file_dict` plus drawing. Then
   `_build_sparams_job`, `legacy_job._load_state`'s GUI normalization and
   the model-failure fallbacks are deleted, and `legacy_job` becomes a pure
   model -> job compiler.

**Gate for each slice:**
- after a scripted edit sequence through the real widgets (tables,
  dialogs, panels), the live Document equals `_model_document()` taken from
  the remaining legacy dicts;
- every existing GUI test still passes;
- undo/redo round-trips the Document exactly.

The bit-identical Show S gate stays in place throughout.

### Questions for JA

- **L1, order.** My recommendation: **step 4 (the M_super compiler) next,
  then C1-C4**, starting each C slice when an M_super GUI feature needs
  that object kind in the model (point 2 above). Step 4 does not depend on
  live state, and it is where the physics payoff is. The alternative is C1
  now: it is the cheapest slice, and it removes the `value / 1000` residue
  at its source.
- **L2, edit API shape.** Plain functions plus a change record (my
  default: Qt-free and easy to call from the MCP), or an observable
  Document that emits signals (more automatic, but it couples the model to
  an event system)?
- **L3, twin UI (C2).** Under decision 2, "delete TL*" hides the view.
  Should the same context menu offer "Stop pumping" (remove the pump) next
  to it, so the physics change is one click away and named honestly?
- **L4, constraint groups (C1).** Promote them to the model, keyed by
  object id (my default), or keep them verbatim in `legacy_frames`?

## Questions for JA (original, answered above)

1. Dataclasses vs pydantic; keep `.pgraph` + 4.0 (12.2).
2. Is it acceptable that the twin disappears from the physics and survives
   only as `sector_views`? It changes what "delete the twin" means in the UI
   (it would become "stop pumping").
3. Taps: hold `legacy_anchor` until the inverse tap profile is derived (my
   default), or derive it first?
4. Should `solve` settings travel with the document (my default: yes, so
   that a file reproduces its plot), or should they be per-session?
