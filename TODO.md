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
  connector embedding (free-Y_L-pole convention).
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
- [ ] GUI conveniences still deferred: ghost placement previews for
  ports/lines, port glyphs in clipboard copy/paste.
- [ ] **Pumped line termination (gain)** — derivation note in
  `docs/pumped_line_termination.md` (numbers reproduced by
  `misc/pumped_termination_checks.py`): the modulated inductor is a rank-one
  parametric block g g^T between the comb and its conjugate twin (the twin of
  the rank-one port damper); one pump drives amplification AND conversion
  pairs through the same block; Manley-Rowe verified to 3e-14 on the oracle;
  an inductive termination DISPERSES the comb (cot(kl) = wL/Ztx), so the macro
  needs loaded-line roots, not n*FSR. Plan: macro emission (signal comb +
  hollow conjugate twin + one double-line pump bus + per-sector ports; the
  attached mockup), then pin the a-basis normalization of g g^T against
  build_galvanic + hb_signal_idler in the overlapping regime; det-M stability
  is a prerequisite.
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

- [ ] **Widen the S-parameter selection section in S-parameters tab** to accommodate the labels. We can actually remove the "S_" part of the checkbox text because it's redundant.

- [ ] **Copy vectors doesn't work** for port and txline elements. It seems to work if I add a graph node though.

---
# Physics things to work out
- in the full port-inclusive graph picture, we need to understand what it means to drive a system a little more thoughtfully. When we conjugate a set of modes, is the same port connected to both the signal and the conjugate?

- need to decide what we should do about the M matrix (symbolic) display. Add and M_super tab? What about sympy code export?