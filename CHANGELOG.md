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
    terminating both ends is refused pending a verified ABCD two-port
    reference), dashed attachment links created with the edge tool, a third
    **Ports & Lines** parameter panel (per-attachment rates + signs; legacy
    `B_ext` shown there as auto-ports while its Nodes-table column hides),
    `.pgraph` format 3.0 with loader migration, hub/macro-aware exported
    scripts, and a one-way *Explode Line to Nodes* action.
  - Phase-2 items are explicitly blocked pending derivations (complex /
    mixed-sector hub weights, band-limited combs, two-port lines,
    frequency-dependent weights); attachments enforce real signed weights
    and single-sector spans with errors naming the missing `M_pumped`
    derivation.

### Fixed
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
