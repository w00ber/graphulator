# TODO
## BUGFIXES: GRAPHULATOR (not PARAGRAPHULATOR)
- [x] there's a weird thing where the focus gets kicked out of the edge label string field in the properties panel when I'm trying to write text in it.
  - Fixed: every keystroke triggered `textChanged` → `_update_plot` → `_do_plot_render` → `_update_properties_panel`, which called `show_edge_properties`/`show_node_properties` → `clear_properties`. That `deleteLater()`'d and recreated the `QLineEdit` on every character, so focus was lost. Added a `displayed_single` tracker on `PropertiesPanel` (set in `show_node_properties`/`show_edge_properties`, cleared in `show_no_selection`/multi-select) and made `_update_properties_panel` skip rebuilding when the same single object is already shown. The panel now only rebuilds on selection change, so the field keeps focus while typing. (graphulator_qt.py)
- [x] it seems that there's a thing where the Loop Theta property is not getting saved or reconstituted correctly when I load a graph from a file. It seems to revert to the default value of 30.0 degrees
  - Fixed: `_serialize_graph` never wrote `looptheta` into the saved edge data, while `_deserialize_graph` read it with a default of 30 (`edge_data.get("looptheta", 30)`), so it always reverted on load. Added `"looptheta": edge.get("looptheta", 30)` to the serialized `edge_data`. (graphulator_qt.py)
- [x] I would like to be able to select multiple objects and change any common properties together via the properties panel. When the property values are different, then they should default to the smallest value but shown in gray. Only when the user tabs in and hits Enter or change the number should it set that property value for all selected objects. This is a common feature in many graphics programs and would be very useful here.
  - Done: replaced the old "Multiple Selection" placeholder with an editable `show_multi_properties(nodes, edges)` panel. It builds rows only for properties common to the whole selection — Node Size, Node Label Size, Conjugate, Color (when nodes are selected); Line Width for any edges, plus Style/Direction/Loop Theta when all edges are regular, or Loop Size/Flip when all are self-loops. Numeric fields use indeterminate spin boxes (`_make_multi_int_spinbox`/`_make_multi_double_spinbox`): when the selected objects share a value it shows normally, when they differ it shows the **smallest value grayed out** and only writes to every selected object once the user changes it or presses Enter (Enter-without-change commits only while still indeterminate, so a build/redraw never silently applies the gray default). Combos go blank when values differ (commit on user pick via the `activated` signal); booleans use a partially-checked tri-state box. Each apply-to-all is one undo step (`_save_state` once, then `_update_plot`). The panel participates in the same rebuild guard as the single-object fix (`displayed_multi` selection signature) so fields keep focus while editing. (graphulator_qt.py)

## FEATURES: GRAPHULATOR (not PARAGRAPHULATOR)
- [ ] Add a zoom box interaction, triggered by the Z key, with Esc to get out of zoom box mode. See Diagrammer for an example of this

## OPEN DECISIONS: EXPLICIT PORTS (PARAGRAPHULATOR)
- [ ] Loss-hub glyph: currently a hatched variant of the port pentagon
  (placeholder). The final dissipative-hub glyph is an open schema decision —
  "H" is reserved for the reactive hub in the proposed vocabulary — decide
  whether the dissipative hub gets its own glyph or a decorated H/P.
- [ ] Phase 2 (blocked on derivations, see autograph.py module comments):
  complex/mixed-sector hub weights (M_pumped + harmonic balance),
  band-limited comb expansion (low-side closure), two-port line macro
  (verified ABCD two-port reference), frequency-dependent hub weights /
  connector embedding (free-Y_L-pole convention). NOTE the comb tail
  closure (docs sec. 8) IS a frequency-dependent hub weight -- a scalar
  lambda_h(f) on the channel -- derived exactly for the one case of a
  line's own truncated tail; the general connector embedding (a lumped
  reactance between port and line) would reuse the same assembly hook
  (`GraphScatteringMatrix._build_tail_closure`, `_scatter`).
- [ ] The programmatic `extract_from_pgraph` route builds port hubs from the
  saved 'ports' entries only; a line END terminated on a port (the GUI's
  `line['ends']`) is merged into the hub column by `_gui_hubs_payload` and
  is NOT reproduced by that route (nor are its `tails`). Exported code and
  the GUI are consistent; the pgraph-file route lags.
- [x] **Node taps** (the conservative "reactive hub" fan-out) SHIPPED:
  one drawn line-end→node connection stands for the conservative couplings
  to every comb mode. Profile pinned exactly against the reference's
  a-basis transform (`cmtline_core.a_basis_A` over the tapped Cm/Km
  circuits, constant ratios to machine precision, n = 1..10): capacitive
  g_n ∝ u_n(end)·√(ω_n/C_n) (∝ √n for the comb), inductive
  g_n ∝ u_n(end)/√(ω_n·C_n) (∝ 1/√n); DC decoupled/excluded. The
  coupling type is a per-END property (set in the line dialog); the
  normalization is harmonic-referenced — the user's rate is the coupling
  AT a chosen reference harmonic n_ref (nearest harmonic highlighted when
  tapping; editable in the Ports & Lines panel). See
  `LineResonator.tap_couplings` and tests/test_line_taps.py.
  - Remaining niceties: a *galvanic* tap type (cf. `build_galvanic`) is
    not offered yet; only capacitive/inductive are derived and exposed.
- [x] Dragging + rotation of port/line glyphs (drag to move with grid
  snap; Ctrl+U/Ctrl+I rotate the selected glyph's orientation in 15-degree
  steps; angle persists in .pgraph).
- [ ] **Port / txline glyphs in the drawing-code export.** `_export_code`
  (graphulator_para.py, "Export graph as Python code", Ctrl+Shift+E) walks
  `self.nodes` / `self.edges` and emits matplotlib calls that redraw the
  figure; it has no representation for port or line glyphs, so it still
  requires nodes and says so. To add them, emit the same geometry
  `ExplicitPortsMixin._draw_ports_and_lines` draws: `_port_geometry` +
  `_port_effective_angle` for the pentagon and lead, `_line_geometry` +
  `_line_end_points` for the cylinder/caps/stubs, and the routed wires from
  `_attachment_wire` / `_tap_wire` / `_line_end_port_wire` / `_pump_bus_wire`
  (all sampled polylines already, so they emit as plain `plot` calls). The
  per-glyph style keys (w_mult, h_mult, linewidth, color, fill) and the wire
  style keys (color, linewidth_mult, label, label_size_mult) should come
  along. Note the IMAGE exports (PNG/SVG/PDF/clipboard) already handle glyph
  -only graphs — this item is only about the code export.
- [ ] GUI conveniences still deferred: ghost placement previews for
  ports/lines, port glyphs in clipboard copy/paste.
- [x] **Loaded-line basis** SHIPPED (docs/pumped_line_termination.md sec. 7;
  gate: tests/test_loaded_line.py). The load is stored per end as {type, f_Z},
  f_Z being the frequency at which |X_elem| = Ztx — one number, no reference frequency to
  agree on, and an explicit type rather than a sign (the project's JAA
  convention gives an inductor NEGATIVE reactance, so a bare sign field would
  be a trap). Default None = open, so today's numbers and every golden stay
  pinned. What that took:
  - loaded roots cot(kl) = x(w); u_n(l) = cos(k_n l); C_n = c*int u_n^2 (+
    C_elem u_n(l)^2 for a capacitive load, whose energy is kinetic);
    gamma_n = u_n(0)^2/(2 pi Z0 C_n), now MODE-DEPENDENT.
  - every derived profile currently assumes the open-open basis (kappa_n, the
    tap envelope, gamma, B_int per mode, the pump profile) and must be
    re-derived on the loaded one; the existing tests stay valid as the
    unloaded limit.
  - "solve FSR for a target loaded resonance" helper in the line and pump
    dialogs: FSR = pi f_t / (arccot(x(f_t)) + (n-1) pi), closed form, verified
    to 1e-15 for both types and for modes 1 and 3.
  - the DC mode differs by type: an inductive load shorts DC (free mode gone,
    replaced by the quarter-wave mode), a capacitive one keeps it.
  - REFUSE capacitive loads until sec. 7.5 is closed: with the DC mode and the
    element's kinetic term included the ABCD error still PLATEAUS with N
    (~0.94) instead of falling, i.e. an unresolved direct/Foster-at-infinity
    term. The inductive case converges ~1/N exactly like the unloaded macro
    (1.260/0.569/0.276/0.137 at N=10/20/40/80), so it is the one to ship.
  - All of the above is done. Surfaced as `LineResonator(load=...)` /
    `set_line_load`, an End-load row in the line dialog and on the line's
    Properties page, and a load section in the pump dialog (the modulated
    element IS the load, so its type is already known there). Capacitive
    entries are LISTED AND DISABLED everywhere rather than hidden, with the
    7.5 reason in the tooltip. Bundled scene: LINE_PUMPED_LOADED.
  - Three defects the loaded basis exposed, all fixed: N counted
    ceil(f_max/FSR) rather than the modes that reach f_max; `f_max >= FSR`
    was enforced on loaded lines, where FSR is v/2l and the fundamental can
    sit far below it; the idler partner was found at f_p - n*FSR instead of
    f_p - f_n. A pumped line's twin is also BORN with the load now (it was
    validated before the load was mirrored onto it).
  - Still open here: the capacitive load's direct term (sec. 7.5), and
    loading BOTH ends (one reactance only; two needs its own root equation
    and its own ABCD gate).
- [x] **Pumped line termination (gain)** SHIPPED as a macro: linked
  conjugate twin + one double-line pump bus = the rank-one block g g^T
  (`docs/pumped_line_termination.md`). Normalization pinned against
  build_galvanic + hb_signal_idler: rate = 2 FSR g / pi. Two core bugs fixed
  on the way (sorted-vs-traversal tree orientation; explicit 'sector' frame
  rule for pump edges onto a +-n comb).
  - Tail closure SHIPPED (docs sec. 8): the port loading of the modes beyond
    f_max is exact at any N; the remaining N-dependence is the tail modes'
    pump coupling (second order) -- measured, not assumed, with the panel's
    "Check truncation (2x f_max)". The old "tail closure (3e-2 residual at a
    matched port)" item is this.
  - Remaining: the DC mode's pumped coupling on an UNLOADED line (with an
    inductive load the question is gone — that end shorts DC and the free
    mode with it; unloaded it is still the 2e-3 residual floor vs the
    oracle);
    tail closure (the 3e-2 residual at a matched port); taps on a pumped
    line (the tapped mode needs its own idler copy — same open question as
    "is the same port connected to signal and conjugate?"); the det-M
    stability flag (the near-threshold row in the note's table).
- [ ] **Pumped taps** (conversion-type pumping of a line-end tap):
  mechanically the pipeline already computes it — the tap fan-out edges are
  ordinary edges, and a probe with f_p injected on them ran frame-consistent
  and unitary (2e-15) with the expected conversion feature — but it is NOT
  exposed, pending the derivation gate: verify that the modulated part of
  the coupler inherits the static (n/n_ref)^(+-1/2) profile, against a
  pumped-coupler sideband reference (extend cmtline_core.hb_signal_idler's
  P matrix to modulate the coupling element instead of the device L_J).
  Then: per-tap f_p + pump phase in the connection dict/dialog/panel/
  serialization/codegen; refuse a pumped tap whose node shares a hub with
  the same comb (zero-offset bridge links), and two taps on one line with
  different pump frequencies (one frame per comb). The DC-complete +-n comb
  should capture both modulation sidebands with a single f_p — same
  reference check adjudicates. Gain-type (squeezing) node<->comb pumping
  stays blocked on the Phase-2 M_pumped derivation regardless.

## FEATURES: PARAGRAPHULATOR / autograph
- [ ] **Autocompute stability.** Need to find the zeros of the M-matrix as we update coupling. Add experimental/optional setting to display the zeros in the complex plane. Since the determinant is always in the denominator of the scattering matrix, it tells us about stability via the Routh-Hurwitz criterion. We want to flag whether a set of given graph parameters is actually not stable and would like this to be highlighted in indianred or darkred at the top of the window (or wherever you think is the most effective for the user interface).
- [ ] **Add group delay view*** 
- [ ] **Add Smith chart view***
- [ ] **plot panel reconfiguration** With more than just S-parameter and magnitude and phase, probably want to change over to a more flexible scheme where the user can add plots and configure what they display. Doesn't need to be vertically stacked; someone might prefer side-by-side (1,2) or (2,2) subplot layouts. We should keep the frequency axes locked. In the case of a Smith chart, we could reduce the opacity of points outside the displayed frequency axis limits in other plots and toggle a preference to zoom into selected points or lock the chart axes. The plot scaling preferences can be set up as tabs for each plot style at the bottom. Don't display a tab for a data plot unless it's displayed. I could use your advice in how to add/subtract plots and select their displayed data. It would be nice to have multiple views on the same data in different subplots, but I assume that we'd need to figure out whether the axis scaling tabs would need to be duplicated or if we just do subtabs within a particular data plot style. 


## BUGFIXES: PARAGRAPHULATOR / autograph
- [ ] **Conjugated-node hop sign.** `autograph.GraphScatteringMatrix._build_M_matrix` writes `+beta` for an edge whose two endpoints are both conjugated (the `conj_j == conj_k` branch treats conj/conj like unconj/unconj). The row of a conjugated node is minus the complex conjugate of the unconjugated row, so a real resonant coupling between two conjugated nodes must enter as `-beta` (the pump edges already carry `-conj(beta)`; the diagonal already flips the sign of `f0`). Consequence today: |S| is unaffected only up to a pi-per-cell pump phase step (verified DTWPA_A ledger 55), but any pump phase derived from a physical pump wavenumber is off by pi per cell. Fix: in the `conj_j == conj_k` branch, when both are conjugated write `-beta` / `-conj(beta)`; check the symbolic M display and any code-generation path do the same; add a test with a 4-node two-rail amplifier comparing against the DTWPA_A `stagger.py` builder (now -beta_B). Found 2026-09-07 while fixing the DTWPA_A convention.

- [x] **Widen the S-parameter selection section in S-parameters tab** to accommodate the labels. We can actually remove the "S_" part of the checkbox text because it's redundant.
  - Done: the column was hard-capped at 120 px with horizontal scrolling off,
    so long labels were clipped; it now sizes to its widest entry (120-340 px).
    Trace names dropped the "S_" AND gained an out <- in arrow, because bare
    concatenation is ambiguous for multi-character labels ("S_TL1TL1*"); they
    now read "TL1 <- TL1*". Checkbox state is keyed on the label tuple rather
    than the rendered text, so the rename did not reset anyone's selections.

- [x] **Copy vectors doesn't work** for port and txline elements. It seems to work if I add a graph node though.
  - Fixed: copy-to-clipboard and the PNG/SVG/PDF exports all guarded on
    `not self.nodes`, but an image export captures the FIGURE, so a graph of
    only port/line glyphs is perfectly exportable — hence "works if I add a
    graph node". They now use `_has_drawable_content()` (nodes OR ports OR
    lines). The drawing-CODE export still requires nodes, since it
    regenerates matplotlib calls from nodes/edges and has no representation
    for glyphs; its message now says so.

- [x] need to add the port and txline placement options to the on-screen help and update any menus/documentation with these new actions
  - Done: help_para.md has a "Ports, Loss Hubs & Transmission Lines" section
    (shortcut templates, what the glyphs mean, end load, truncation, where to
    tune); the '?' overlay lists Add port / Add transmission line in the idle
    context whenever Explicit Ports is on; README shortcut list + an
    "Experimental" banner on the ports section. The Insert menu already
    carried Place Port / Loss Hub / Transmission Line / Explode.

- [x] need to construct some transmission line examples (with accompanying notes explaining what's happening)
  - Done: File -> Examples -> TL_1..TL_5 (open line on a port; a mode
    tapped onto a line; the pumped-termination amplifier; the same with the
    inductor's reactance as an end load and the fundamental solved onto 4.0;
    two lines on one port = series). Each carries a Notes tab: what it is,
    what to look at in S, which knob does what. Generated by
    misc/make_line_examples.py -- edit the notes there, not the files.

- [x] need a better place to put the port mode toggle in Settings. It should also be labeled *Experimental!!! Use at your own risk* for now.
  - Done: its own Settings tab "Experimental", labelled "Explicit Ports &
    Lines (hub dissipation, transmission lines) -- EXPERIMENTAL!!! Use at
    your own risk".
---
# Physics things to work out
- in the full port-inclusive graph picture, we need to understand what it means to drive a system a little more thoughtfully. When we conjugate a set of modes, is the same port connected to both the signal and the conjugate?

- need to decide what we should do about the M matrix (symbolic) display. Add and M_super tab? What about sympy code export?

- can our code actually handle resonant coupling in chained transmission lines like a stepped impedance resonator (multiple sections of different impedance transmission line)? Can we just kluge it from a cascade of ABCD matrices and then compute the loaded normal modes from there? What about a transmission line set up as a stub? Can we actually create a shorted stub filter (set L load to zero?) if we wanted?
  - Partial answer (docs sec. 8): the comb tail closure already takes an
    ARBITRARY exact Z_in -- `LineResonator.input_impedance` is an ABCD
    cascade -- so a stepped-impedance or stub line's PORT response could be
    exact today with zero kept modes. What a cascade lacks is the kept
    basis: the sections' normal modes u_n(x), C_n and the end profiles the
    pump/tap couplings need (the roots come from det of the cascade, the
    normalization from the per-section energy integrals). That is the
    follow-on to the loaded-line basis, same recipe. A shorted stub is the
    inductive load with f_Z -> infinity (L -> 0); the dialog allows 1e12.
- [ ] **Reference impedance / design language (open decision).** Proposal
  from the impedance discussion: one graph-level reference impedance Z_ref
  (default 50) that every impedance in the graph is referred to -- ports
  are Z_ref unless overridden (moving Z0_port off the line, where a port
  shared by two lines can currently disagree with itself), lines carry
  Ztx and display Ztx/Z_ref, nodes may carry an OPTIONAL Z_r (their B_ext
  at a matched Z_ref port is then the mismatch Z_r/Z_ref) used by a
  "derive rate from circuit" calculator in the tap/attachment dialogs that
  WRITES the rate rather than replacing it. Only ratios enter the physics
  (gamma/FSR = (2/pi) Ztx/Z0, B_ext/w0 = Z_r/Z0), so Z_ref is a units
  choice like the a.u. frequency. Needs the user's go-ahead: it changes the
  file format (Z0_port migrates to the port) and the design language.