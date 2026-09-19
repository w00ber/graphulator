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
  - **Click a mode marker to anchor the pump's rate there** — closes the loop
    the overlay exists for. Inert while the navigation toolbar is in
    pan/zoom; clicking an idler image explains that *m* is derived from f_p
    and n rather than silently doing nothing.
  - **δL_ℓ/L_ℓ** (the load element's own fractional modulation) reported
    beside α, when the end load is set and the pumped element *is* the
    termination. This is the number invariant under re-anchoring — verified
    to 12 digits through the real edge fan-out — where α and ε are
    pair-referred. Subscript ℓ for "load": the element is whatever reactance
    terminates the line, and a capacitive load reads δC_ℓ/C_ℓ, the same
    statement with C for L.
  - **Line loss is entered as a rate**, `B_int [mau]`, like every other rate
    in the app, through the verified map B_int = (2/π)·α·FSR. Retires the
    α that collided with the pump's α. Tooltip is explicit that the single
    rate is derived and gated for the **open–open** comb only: a reactive
    load stores energy the loss does not act on, so per-mode uniformity is
    not established there (an f_Z = 0.5·FSR line's fundamental sits near
    *half* the open–open value).
  - **Mode-marker appearance is in Settings → S-Parameter Plot** (colour,
    style, width × trace, opacity, cutoff width, label size), inheriting the
    dialog's existing *Reset to Defaults* / *Save as Defaults*. New defaults:
    black dashed with round dash caps at half the trace linewidth, and the
    comb cutoff solid — a different kind of statement from a mode.
### Fixed (continued)
  - **The pump's mode index was capped at whatever N the row was built
    with.** Raise f_max from 3 to 20 (N: 6 → 40) and `n` still refused to
    pass 6, because the rows are not rebuilt per keystroke (that would steal
    focus). Ranges are now re-ranged in place, for tap indices too. The
    field was also one digit wide; widened.
  - **The pump description named only the amplification partner.** One pump
    satisfies *three* conditions — f_n + f_m = f_p, f_m − f_n = f_p
    (up-conversion, which always has a target) and f_n − f_m = f_p
    (down-conversion) — so the panel now names the anchored pair's family
    and lists the others the same pump drives. Understating the conversion
    is precisely the error the triple-line bus exists to prevent.
  - **Pump strength α** (PRX Quantum convention, α = ε/4 = g/√(ω_nω_m))
    reported beside the rate, with δL/L_tot alongside. **α ≥ 1 is flagged**
    — the rate box takes a translucent red wash and the label turns dark
    red and says "unphysical" — because where that limit sits is not
    obvious on a loaded comb, whose participations move with the dispersed
    roots. The line's uniform attenuation is relabelled **α_loss**: two
    different αs in adjacent rows is exactly the collision that gets
    misread.
### Fixed (continued)
  - **Mode markers were invisible.** The palette opened on `#e8e8e8`,
    against a `#EAEAF2` plot ground — the overlay drew, and could not be
    seen. Darker, contrast-checked colours now.
  - **Index labels never appeared.** A signal mode and a twin's idler image
    routinely coincide (f_n and f_p − f_m), so the all-or-nothing density
    test saw a zero gap and suppressed *every* label. Coincident markers
    now share one chip (`1/2*`, conjugate starred) and thinning is greedy
    left-to-right, so crowding costs that one label rather than the set.
    Hover names every mode at a shared frequency, not just one of them.
  - **Ports & Lines no longer needs horizontal scrolling.** The pump was
    one wide strip of header + four spinboxes + the full pair description,
    pushing the pane's minimum past ~1400 px and stopping the plot being
    kept at half the window. Split into a header (carrying α), an indented
    control strip, and a word-wrapped description: minimum width now
    639 px, measured in the tests.
  - **Mode-frequency overlay on the S-parameter plot** (*Mark Line Modes*,
    beside *Conjugate Freqs*). Marks every transmission line's normal-mode
    frequencies — the **loaded** ones when an end load is set — labels them
    by index, and reports line, index and frequency on hover. Markers run to
    the comb cutoff (mode N), which is drawn heavier because beyond it the
    model keeps no explicit modes. Positions are not simply f_n: each
    channel is read in its own drive frame, so a pumped line's conjugate
    twin is marked at `f_p − f_m`, where its idler image actually resonates.
    The frame is inverted from the sweep's own `drive_signals` rather than
    re-derived per topology, which keeps plain, loaded, conjugated and
    pumped lines all correct. Intended use: read off which `n` to name in
    the pump's reference pair. Persists in the `.pgraph` plot settings.
  - **Worked transmission-line examples** under File → Examples (`TL_1` …
    `TL_5`), each with a Notes tab explaining the drawing, what to look at
    in S and which knob does what: an open line on a port; a mode tapped
    onto a line; the pumped-termination amplifier; the same with the
    inductor's reactance as an end load and the loaded fundamental solved
    onto 4.0; two lines on one port (series). `misc/make_line_examples.py`.
  - In-app help gained a *Ports, Loss Hubs & Transmission Lines* section
    (shortcuts, connection rules, glyph meanings, end load, truncation,
    where to tune); the `?` overlay shows *Add port* / *Add transmission
    line* when the mode is on; README shortcut list updated.
### Changed
  - The Explicit Ports & Lines toggle moved from Settings → Interface to its
    own **Experimental** tab, labelled "EXPERIMENTAL!!! Use at your own
    risk".
  - **Comb tail closure.** A line macro keeps N pole pairs, but the modes
    beyond f_max still load the port: a reactive tail ~ 2γf/(FSR²N) that
    shifts every in-band resonance and converges only as 1/N (measured law
    in `misc/comb_truncation_checks.py`: |ΔS| ≈ 2.5 (γ/FSR)(f/FSR)/N, all
    of it in the phase). That tail is now folded back into the port channel
    in closed form — exact minus kept, with `exact` the line's input
    impedance from ABCD (open–open, inductively loaded, port at the loaded
    end, lossy) — as a per-channel scalar λ(f) = 1/(1 + iχ_t/2) on the hub's
    damper in M and its K column, plus a direct phase on S. It is a Schur
    complement, i.e. an identity: N = 2 reproduces exact ABCD to 1e-15 where
    the raw comb was off by 2, and S_full stays unitary. Channels without a
    tail have λ = 1 exactly, so legacy graphs are bit-identical. What it
    does not carry is the tail modes' pump/tap couplings (second order):
    on the §6 pumped line the closed residual sits on the 2e-3 DC-mode
    floor from N = 4. Toggle in the Ports & Lines panel ("close comb tail
    analytically", default on); `GraphScatteringMatrix(..., tail_closure=)`;
    exported code carries hub `tails`. Docs §8, full derivation in
    `docs/comb_tail_closure.md`; gate `tests/test_tail_closure.py`.
  - **Check truncation (2× f_max)** button in Ports & Lines: re-solves every
    component with all combs doubled and reports the largest change of each
    displayed trace over the window — the honest way to size N for THIS
    graph, including the couplings the closure does not carry.
  - **Ports & Lines is tunable without a graph node.** The panel now spans
    the full width under Nodes | Edges and carries live spinboxes for each
    line's FSR/Ztx/f_max/Z0/α, its end load's f_Z, and its pump's
    f_p/rate/phase/n_ref (partner shown beside), with a per-line note giving
    N, the closure state and — with the closure off — the truncation
    estimate at the top of the window. A conjugate twin lists its
    terminations and points at its primary. The Nodes placeholder for a
    glyph-only graph now says where the controls are instead of "Enter
    Scattering mode".
### Fixed (continued)
  - S-parameter plot lost its frequency-axis numbers when every channel was
    a hub port: the per-port frequency rows looked channels up in
    `self.nodes`, found nothing, hid the tick labels and drew no rows. Hubs
    now carry a drive frame (`drive_signals[hub_id]`) and the plot labels
    channels from `port_dict`.
  - Ctrl+U/I on a selection of several port/line glyphs (no node) spun each
    glyph about its own center; two or more selected objects now rotate
    rigidly about the selection centroid. A single glyph still spins in
    place.
  - **Loaded (reactively terminated) lines.** A `LineResonator` can now carry
    a shunt reactance at ONE end, `load={'end','type','f_Z'}`, and the comb is
    re-derived on that dispersed basis: loaded roots `cot(kℓ) = X_elem/Ztx`
    (bisection on a pole-free residual), the DC mode dropped for an inductive
    load, and `u_n(end) = cos(k_nℓ)`, `C_n` and `γ_n = 1/(2π Z0 C_n)` all
    moving with them — γ is no longer the same for every mode. The end
    couplings and the tap/pump profiles are rebuilt from `(u_n, f_n, C_n)`;
    the open–open branch keeps its closed form, so `load=None` (the default)
    reproduces every pinned golden bit-for-bit and is itself the `f_Z → 0`
    inductive limit. Gated against exact ABCD in the project's JAA convention
    at ~1/N, the same tail-limited convergence the unloaded macro shows
    (1.260/0.569/0.276/0.137 at N=10/20/40/80): `tests/test_loaded_line.py`.
    The load is parameterized by an explicit TYPE plus f_Z — the frequency
    where |X_elem| = Ztx — rather than a signed reactance, because this
    project's `Z_ind = -iωL` makes an inductor's reactance negative, the
    opposite of the textbook. `line_fsr_for_target` inverts §7.3 in closed
    form, so you name the LOADED resonance and get the line instead of
    guessing FSR: offered in the line dialog, the line's Properties page and
    the pump dialog, where the modulated element is itself the load.
    **Capacitive loads are refused**, listed-and-disabled rather than hidden:
    their comb S11 plateaus near 0.94 from N=10 to N=80 instead of falling,
    so a direct non-resonant term is missing (docs §7.5). New scene:
    `LINE_PUMPED_LOADED`.
  - Fixed along the way, each a real defect the loaded basis exposed: `N`
    counted `ceil(f_max/FSR)` rather than the modes that reach `f_max`;
    `f_max >= FSR` was enforced on loaded lines, where FSR is the geometric
    parameter `v/2ℓ` and the fundamental can sit far below it; the idler
    partner was found at `f_p - n·FSR` instead of `f_p - f_n`, which names a
    different mode on a dispersed comb; a pumped line's twin was validated
    before its load was mirrored onto it, so a strongly loaded line could not
    be pumped at all; and a tap or pump naming a mode outside a shrunken comb
    raised instead of clamping with a warning.
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
