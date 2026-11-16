# Layer 0: a Qt-free document model (design note, for review)

*Status: proposal, 16 Nov 2026. No code yet. Sections tagged **[decide]**
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

## Questions for JA

1. Dataclasses vs pydantic; keep `.pgraph` + 4.0 (12.2).
2. Is it acceptable that the twin disappears from the physics and survives
   only as `sector_views`? It changes what "delete the twin" means in the UI
   (it would become "stop pumping").
3. Taps: hold `legacy_anchor` until the inverse tap profile is derived (my
   default), or derive it first?
4. Should `solve` settings travel with the document (my default: yes, so
   that a file reproduces its plot), or should they be per-session?
