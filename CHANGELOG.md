# Changelog

## [Unreleased]
### Added
- **Explicit Ports & Lines (hub-based dissipation)**, gated by a new
  Settings → Interface switch (off = the app behaves exactly as before;
  files containing ports/lines auto-enable it for the session).
  - `DissipationHub` model in `autograph`: monitored hubs are ports (shared
    between modes; a rank-one damper `(i/2)κκ†` in M *and* a channel of S),
    unmonitored hubs are loss channels. M's external anti-Hermitian part is
    now computed from the same K used in S (single source of truth), so
    lossless unitarity/passivity hold by construction; legacy per-node
    `B_ext` auto-wraps to single-attachment ports, reproducing the previous
    numerics to machine precision (golden-file regression suite pins this).
    New API: `assign_hub`, `extract_graph_data(..., hubs=, line_resonators=)`,
    `.K_loss`, `.K_full`, `.S_full` (dilated, unitary at `B_int=0`),
    `.absorption` (per-channel energy audit), `.port_labels`.
  - `LineResonator` macro: an open–open transmission-line standing-wave comb
    parameterized by `{FSR, Ztx, f_max, port_end, Z0_port, alpha_uniform}`,
    expanded at extraction into the full comb from DC with signed couplings
    `κ_n = (±1)ⁿ√γ`, `γ/FSR = (2/π)(Ztx/Z0)`; expansion pinned bitwise to
    the `cmtline_core` reference and validated against exact ABCD microwave
    calculations (monotone ~1/N convergence, residual attributed to the
    truncated comb tail). Uniform loss maps to per-mode
    `B_int = (2/π)·α·FSR`, verified against a lossy-ABCD reference.
  - Paragraphulator GUI: port glyph (`P`/`Shift+P`; pentagon + lead), loss
    hub (hatched placeholder glyph, Insert menu), transmission-line cylinder
    glyph (`L`) connected by its **end leads** to explicit port glyphs (the
    comb never leaves the macro and a line is never implicitly terminated;
    loading both ends is refused pending a verified ABCD two-port
    reference), attachment wires created with the edge tool, a third
    **Ports & Lines** parameter panel (per-attachment rates + signs; legacy
    `B_ext` shown there as auto-ports while its Nodes-table column hides),
    `.pgraph` format 3.0 with loader migration, hub/macro-aware exported
    scripts, and a one-way *Explode Line to Nodes* action.
  - **Node taps onto line ends**: one drawn connection (edge tool, line end
    → node) couples a graph mode conservatively to every comb mode at once.
    The per-mode profile is pinned against the reference circuit model
    (a-basis extraction): capacitive taps couple as `g_n ∝ u_n(end)·√n`,
    inductive as `g_n ∝ u_n(end)/√n`; the coupling type is a property of
    the line *end* (set in the line dialog), shared by everything tapped
    there. The entered rate is defined at a user-chosen **reference
    harmonic** `n_ref` (the tap dialog highlights the harmonic nearest the
    mode's frequency; rate/sign/`n_ref` stay editable in the Ports & Lines
    panel, and the canvas tap link carries an `n=…` chip). Several loads
    may share one physical line end (e.g. a stub read out by two ports —
    verified against the ABCD reference), and a standalone terminated line
    is a complete scattering problem by itself. Exported scripts reproduce
    the live model in both templates: taps emit as pre-expanded static
    edges, and multi-component graphs now export one literal block per
    component (mirroring the live per-component jobs, including comb-mode
    hub attachments), replacing the runtime component filter.
  - **Glyph aesthetics & routed wiring** (aligned with the diagrammer
    reference art): the port is a boxy home-plate pentagon with a long
    terminal lead and the transmission line a slender coax cylinder
    (closed left cap, open right mouth, terminal stubs). Both glyphs are
    stretchable (length/height, arrow keys or dialog), with per-glyph
    stroke width, stroke color and fill color (dialogs, serialized in
    .pgraph). Wires route as smooth rounded curves in the ComfyUI/Blender
    node style: every wire leaves its terminal colinear with the lead (a
    multi-wire fan collimates through the port lead before spreading),
    enters nodes normal to the circle, and line-end links arrive at ports
    along their leads; selection hit-testing follows the curves. Ports
    auto-orient toward the CENTER of their attached group, with an
    explicit Auto-orient toggle (dialog + context menu; manual rotation
    still pins). Auto-fit ('a') now includes port/line glyphs. A new
    **File → Test** menu ships seven canonical
    explicit-ports scenes (regenerable via misc/make_test_scenes.py) used
    for aesthetics iteration and physics checks; each is load-validated in
    the test suite. Fixed: several nodes tapped onto the same line (or
    joined only through a shared line) now compute as ONE component — the
    component discovery previously left the extra tap partners in
    separate components.
  - **Properties panel for glyphs**: selecting a port or transmission
    line now fills the Properties tab with its live-applied properties
    (label, monitored/loss, auto-orient, auto-size, length/height, stroke
    width, stroke and fill color; for a line also FSR, Ztx, f_max, Z0,
    alpha and the per-end tap coupling, each validated through the
    numerics schema before it is committed). Port bodies auto-size so the
    label always fits, and a manual length edit takes over from that.
    Rotation (`Ctrl+U`/`Ctrl+I`) is also on the glyph right-click menu,
    and the shortcut-hint overlay gains a "Port / line selected" context.
  - **Whole-graph rotation carries the glyphs.** `Ctrl+A` now selects
    ports and lines as well as nodes and edges, and rotating a selection
    that contains nodes turns the whole drawing as a rigid body — glyph
    positions travel with the modes and each glyph's orientation turns by
    the same angle (an auto-orienting port is deliberately left unpinned,
    since its attachments moved too and it re-aims itself). Selecting only
    glyphs still spins each one in place. Glyph labels now ride their
    body, flipping past a quarter turn so they never read upside down,
    and a port's label is centered in the straight part of the body — the
    same width budget its auto-size grows to satisfy.
  - **Wires carry edge-parity properties, and are solid.** The dashed
    linestyle is gone — a wire reaching a port glyph already says
    "dissipative", so the dash carried no extra information. Every wire
    (port attachment, line-end termination, node tap) now takes the same
    controls an ordinary graph edge has: line width (the shared
    Thin/Medium/Thick/X-Thick multipliers), color with a "Default" reset,
    label text and label size. Selecting a wire opens a Properties page
    holding those alongside its physics — rate and sign, plus the
    reference harmonic for a tap — and the styling round-trips through
    `.pgraph` without touching the physics. Role-encoding defaults
    survive: gray for an attachment, firebrick plus a `−` mark when the
    sign is inverted, teal for a tap (labelled `n=…` until the user sets
    a label).
  - **Pumped line termination (gain).** A line end can carry a modulated
    element pumped at f_p (right-click → *Add pumped termination…*): the app
    creates a linked **conjugate twin** glyph (the same line in the idler
    sector — own layout, mirrored physics, its own port glyphs) and one
    **double-line pump bus** between the pumped ends, which expands at
    extraction into the rank-one parametric block g gᵀ of the end profile
    (`docs/pumped_line_termination.md`). The rate is defined at a reference
    pair (n_ref, its idler partner), with the inductive (or capacitive)
    envelope for every other pair; the bus is selectable, editable in the
    Properties panel, serialized, exported, and deleting the twin un-pumps
    the line. Verified: the block is rank one; the pumped graph is
    pseudo-unitary (|S_ss|² − |S_is|² = 1 to 1e-15) with real gain; and the
    normalization rate = 2·FSR·g/π (g from the circuit model) reproduces
    the oracle's gain and idler lineshapes to 3e-3 in the isolated-mode
    regime and 3e-2 at a matched port, the residuals being the excluded DC
    mode and the missing comb tail closure. Node taps on a pumped line are
    refused for now. `LineResonator` gained `conj`.

### Fixed
- Export: copying the graph to the clipboard (and the PNG/SVG/PDF exports)
  refused any graph made only of port or transmission-line glyphs — they
  guarded on "no nodes", but an image export captures the figure, so a
  terminated line is perfectly exportable. All four paths now test for
  drawable content (nodes, ports, or lines). The drawing-*code* export
  still requires nodes, since it regenerates matplotlib calls from
  nodes/edges and cannot represent glyphs; its message now says that.
- S-parameters tab: the trace-selection column was hard-capped at 120 px
  with horizontal scrolling disabled, so longer port labels were silently
  clipped. It now sizes to its widest entry (between 120 and 340 px).
  Trace names also drop the redundant `S_` (the column is headed
  "S-parameters:") and name the pair explicitly as `out ← in`, since bare
  concatenation is ambiguous once labels are more than one character
  (`S_TL1TL1*`). Checkbox state is keyed on the port-label tuple rather
  than the rendered text, so this rename did not reset selections.
- Core: spanning-tree edges were stored as the canonically *sorted* pair
  while the frame accumulation read them as parent→child, so any hop
  traversed toward a smaller (or lexically earlier) id credited its pump
  offset to the parent and left the child with no frame — silently
  falling back to the root drive. Static graphs were unaffected (every
  offset is zero) and graphs rooted at their lowest id were as well, which
  is why it went unnoticed; a pumped comb of string ids exposed it. Tree
  edges are now oriented by traversal, and a node left without a frame is
  logged instead of defaulted.
- Core: pumped edges are oriented by comparing the endpoints' natural
  frequencies, which cannot handle a conjugate comb's negative-frequency
  members. Edges may now carry an explicit `frame_rule='sector'`
  (crossing into the conjugate sector is −f_p); macro-emitted pump buses
  use it, hand-drawn edges keep the heuristic.

### Added (continued)
  - **Pump bus: three strokes.** In the PRXQ visual language a single line
    is conversion (beam-splitter) coupling and a double line is amplification
    (two-mode squeezing). A pump bus is neither — one pump on a comb drives
    both families at once through the same rank-one block — so it draws their
    union, three strokes, always. Deliberately NOT computed per graph: on a
    harmonic comb the two families are satisfied together (separating them
    needs real dispersion engineering), and a band-edge reachability test
    measures `f_max` rather than the device — the same line and pump flip
    from "amplification only" to "both" when `f_max` is raised, because the
    conversion partners were real modes the short comb omitted. That test is
    kept for the question it does answer: `pump_truncation_gaps` warns when
    the comb holds no partner for a family the line has, surfaced as a "raise
    f_max" note in the bus Properties page and the Ports & Lines row. See
    `docs/pumped_line_termination.md` §7.6.
  - Phase-2 items are explicitly blocked pending derivations (complex /
    mixed-sector hub weights, band-limited combs, two-port lines,
    frequency-dependent weights); attachments enforce real signed weights
    and single-sector spans with errors naming the missing `M_pumped`
    derivation.

### Fixed
- Keyboard: shortcuts bound to punctuation typed WITH Shift (`?` for the
  hint overlay, `+` for zoom in) never fired, because the key arrives with
  `ShiftModifier` and a bare `QKeySequence("?")` cannot match it. Every
  unmodified punctuation binding now also registers a companion
  `Shift+<key>` shortcut (letters and digits are excluded, so `G` and
  `Shift+G` stay distinct), kept in sync when a binding is remapped.
- Keyboard: single-key shortcuts are suppressed while an input widget has
  focus (so typing in a spinbox doesn't zoom or place nodes), but clicking
  back onto the canvas did not release that focus — leaving every
  single-key shortcut silently dead after any panel edit, with no visible
  cue. A canvas click now clears input focus (the canvas itself still
  stays out of the Tab chain).
- Keyboard: the "Explicit Ports enabled" auto-enable notice was a
  non-modal popup that took keyboard activation, swallowing every
  window-scoped single-key shortcut until it was dismissed — so `+`/`-`
  and `?` appeared broken for any file containing ports or lines. It now
  shows without activating and hands focus straight back to the canvas.
- Scattering: S-matrix port labels were wrong for graphs whose ports are not in
  ascending node-id order. The K columns are built by walking the nodes in
  basis order, but every label path (S-parameter checkboxes, plot legends,
  frequency-row labels, exported scripts) mapped a port index back to a node
  via `sorted(port_dict)`. Committing a basis reordering that permutes the
  ports desynchronizes the two, so each trace was drawn under another port's
  name — e.g. on a two-port graph the whole matrix was transposed relative to
  its labels. `GraphScatteringMatrix` now exposes `port_ids` as the single
  source of truth for port index → node, and all label paths use it. The
  computed S values were always correct; only the names attached to them were
  wrong.

## [0.14.1] - 2026-07-06
### Fixed
- macOS: LaTeX mode (`Ctrl+L`) rendered node/edge labels in a serif fallback
  font when the app was launched by double-clicking its icon. A Finder-launched
  app inherits a minimal `PATH` that omits `/Library/TeX/texbin`, so matplotlib
  couldn't find `latex` and silently fell back to the mathtext renderer (it
  worked when launched via `open` from a terminal, which inherits the shell's
  `PATH`). The app now prepends the standard macOS TeX/Ghostscript locations to
  `PATH` at startup, so LaTeX mode behaves the same however the app is launched.
  Toggling LaTeX on when no `latex` binary can be found now shows a one-time
  warning instead of silently degrading to serif.

## [0.14.0] - 2026-07-06
### Added
- Optional context-sensitive keyboard-shortcut hints: a small overlay in a
  chosen corner of the canvas shows the shortcuts relevant to the current
  selection (nothing / node / coupling edge / self-loop). Enable it and pick
  the corner under Settings → Interface, or toggle it any time with `?`. Off
  by default. A "Show All Shortcuts" option switches each context from a
  curated essentials list to the full set of shortcuts for that context. In
  Paragraphulator the hint keys track the ShortcutManager, so they stay
  correct if you remap. The panel is a Qt overlay, never part of the figure,
  so it never appears in exports or clipboard copies.

## [0.13.0] - 2026-07-06
### Fixed
- Clipboard and PDF export flattened conjugated-node transparency (and any
  other semi-transparent art, e.g. Paragraphulator's scattering-mode
  dimming): matplotlib encodes `alpha` as SVG `opacity`, but the PyMuPDF
  SVG→PDF step silently dropped it, and the PDF is the preferred clipboard
  flavour. The opacity is now baked into the fill/stroke color over white
  before conversion, so the paste matches the on-canvas appearance. The SVG
  and PNG flavours (which already kept true alpha) are unchanged.

## [0.12.0] - 2026-07-03
### Added
- Graphulator now has a Settings dialog (File → Settings…, `Ctrl+,`) for
  styling defaults, with a live sample preview pane. Both apps store their
  settings in per-app sections of `~/.graphulator/settings.json` (existing
  files migrate automatically); Paragraphulator's dialog gains the same
  preview pane (appearance tabs only) and a new Conventions tab.
- New arrowhead styles in Graphulator: `open` (classic), `filled`
  (publication-style closed triangle), and `stealth` (swept-back), with a
  per-edge relative scale. Editable in the edge Properties Panel
  (single and multi-select), the edge right-click menu, and as app
  defaults in Settings (with an "Apply to Existing…" button).
- Conjugated-mode appearance is organized as an "inversion" of the
  unconjugated look in both apps: node style (Dimmed / Hollow ring in
  node color / Custom color) and label color (Auto-derived, same as
  normal, node color, or custom), plus label scale — all live-applied
  conventions.
- Per-node outlines in Graphulator (enabled/color/width/opacity),
  matching Paragraphulator: config defaults, Properties Panel controls,
  save/copy round-trip, and code-export support.
- Graphulator Settings now covers the full set of new-object defaults:
  node color/label scale/label color, edge style, line width, loopy
  curvature θ, edge label scale/offset, arrowheads, and self-loop
  angle/size/line width — all shown in the preview pane.
- Undo now has a matching Redo (`Ctrl+Shift+Z` / `Ctrl+Y`) in both apps.

### Changed
- Placing an edge in Graphulator no longer opens a dialog: new edges and
  self-loops inherit the properties of the last placed or modified one,
  and any per-edge change (Properties Panel, context menu, edit dialog)
  carries forward to subsequent placements.
- Each edge and its arrowhead are now drawn as one compound path, so
  SVG exports contain a single named group per edge (`edge_<n>`) that
  stays together when edited in Illustrator/Inkscape.
- The Settings preview renders node labels in the apps' bold sans-serif
  math style and reflects every appearance default, including pending
  (unapplied) values.
- The S-parameter sweep is vectorized (~15× faster) and runs on a
  background thread, so large frequency point counts no longer freeze
  the GUI.
- Requires Python 3.10+ (3.9 is EOL and Paragraphulator never actually
  imported on it).

### Fixed
- Undo restored only a subset of node/edge properties (curved edges
  straightened to 30°, label background colors and outline styling were
  lost, and Paragraphulator dropped all scattering assignments). Undo
  snapshots are now full-fidelity.
- Paragraphulator's scattering parameter assignments survive undo,
  copy/paste, and reload (they were keyed by transient object identity).
- Copy/paste preserved neither edge curvature (`looptheta`) nor label
  flip/rotation in Graphulator.
- "Reset to Defaults" in Settings now restores true as-coded values
  (it previously re-read the already-overridden values), and both Apply
  and Reset propagate changed defaults to newly placed objects (dialog
  memory was never resynced, so applying settings only worked
  sporadically).
- Single/double edge styles regained their flush (butt) endcaps; the
  compound-path rewrite had given them rounded caps, which broke the
  double-line rendering into a rounded capsule.
- Paragraphulator's self-loop "Linewidth" setting was mislabeled — it
  scales the arrowhead length and is now labeled accordingly.

## [0.11.0] - 2026-06-30
### Changed
- Canvas text labels (node, edge, and self-loop) are now rendered from cached
  vector glyph paths: each unique LaTeX/MathText label is compiled once and
  reused across pan/zoom/rescale via cheap transforms. LaTeX-quality labels stay
  crisp at any zoom, and the fast/slow MathText↔LaTeX debounce toggle is gone.
- Pan and zoom no longer rebuild the whole scene each frame. View changes update
  only the axis limits (and zoom-dependent stroke widths) on the existing
  artists, making interaction dramatically smoother in both Graphulator and
  Paragraphulator.

### Fixed
- A node could begin dragging on plain cursor movement after a click+release;
  dragging now requires the left mouse button to be held (a real click-drag).

## [0.10.0] - 2026-05-08
### Changed
- _TODO: describe changes._

All notable changes to graphulator are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.9.1] - 2026-04-27
### Added
- Help → About dialog in both Graphulator and Paragraphulator, showing
  the app logo, version, Qt/PySide6/Python versions, copyright, and
  project URL.
- `graphulator/_resources.py` with a `resource_path()` helper for
  locating bundled assets across dev, pip-installed, and PyInstaller
  frozen builds.

### Changed
- Runtime PNG icons moved from `misc/` to `src/graphulator/assets/` and
  declared as package data so they ship with the wheel; PyInstaller
  specs updated to bundle them into frozen builds. (`.icns`/`.ico`
  app-bundle icons remain in `misc/` — they're build-time only.)
- Icon lookups in both `main()` entry points now go through
  `resource_path()` instead of walking up from `__file__`, fixing the
  silent "no icon" case under `pip install`.

## [0.9.0] - 2026-04-21
### Added
- Initial public release.
