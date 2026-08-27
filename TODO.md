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
- [x] Dragging + rotation of port/line glyphs (drag to move with grid
  snap; Ctrl+U/Ctrl+I rotate the selected glyph's orientation in 15-degree
  steps; angle persists in .pgraph).
- [ ] GUI conveniences still deferred: ghost placement previews for
  ports/lines, port glyphs in clipboard copy/paste.
