# Graphulator Keyboard Shortcuts

## File Operations
| Shortcut | Action |
|----------|--------|
| {{shortcut:file.new}} | New graph |
| {{shortcut:file.open}} | Open graph |
| {{shortcut:file.save}} | Save graph |
| {{shortcut:file.save_as}} | Save graph as |
| {{shortcut:file.quit}} | Quit |

## View & Navigation
| Shortcut | Action |
|----------|--------|
| {{shortcut:view.auto_fit}} | Auto-fit view to graph |
| {{shortcut:view.zoom_in}} or {{shortcut:view.zoom_in_equals}} | Zoom in (canvas) |
| {{shortcut:view.zoom_out}} | Zoom out (canvas) |
| {{shortcut:matrix.zoom_in}} or {{shortcut:matrix.zoom_in_plus}} | Zoom in (matrix/basis/notes display) |
| {{shortcut:matrix.zoom_out}} | Zoom out (matrix/basis/notes display) |
| {{shortcut:matrix.zoom_reset}} | Reset zoom (matrix/basis display) |
| {{shortcut:matrix.pan_left}}/{{shortcut:matrix.pan_right}}/{{shortcut:matrix.pan_up}}/{{shortcut:matrix.pan_down}} | Pan matrix/basis display |

## Grid Controls
| Shortcut | Action |
|----------|--------|
| {{shortcut:grid.rotate}} | Rotate grid (45 degrees for square, 30 degrees for triangular) |
| {{shortcut:grid.toggle_type}} | Toggle grid type (square / triangular) |

## Node Placement
| Shortcut | Action |
|----------|--------|
| {{shortcut:node.place_single}} | Place single node |
| {{shortcut:node.place_continuous}} | Toggle continuous node placement mode |
| {{shortcut:node.place_duplicate}} | Toggle auto-increment mode |
| {{shortcut:node.toggle_conjugation}} | Toggle conjugation mode |
| {{shortcut:node.exit_placement}} | Exit placement mode / Clear selection |

- You can click and drag any node.

- In single node placement mode ({{shortcut:node.place_single}}), you get a pop up dialog that lets you set node color, size, label size, and label string. If you enter continuous mode after, it will increment the label (numbers or letters) and continue in the same style.

- If you are calculating scattering, it's necessary to define "ports" for the possible source/receiver pairs. These are signaled to the computation by placing self-loops on a node. Self-loops are constructed in Edge Placement Mode (below) by double-clicking a node (defining the to/from node to be the same). With **Explicit Ports & Lines** enabled (Settings > Experimental) a port can instead be a real glyph shared by several modes — see *Ports, Loss Hubs & Transmission Lines* below.

## Edge Operations
| Shortcut | Action |
|----------|--------|
| {{shortcut:edge.place_single}} | Toggle single edge placement mode |
| {{shortcut:edge.place_continuous}} | Toggle continuous edge mode |
| {{shortcut:selfloop.scale_increase}} | Increase self-loop scale |
| {{shortcut:selfloop.scale_decrease}} | Decrease self-loop scale |
| {{shortcut:selfloop.angle_decrease}} | Decrease self-loop angle / edge looptheta |
| {{shortcut:selfloop.angle_increase}} | Increase self-loop angle / edge looptheta |

## Ports, Loss Hubs & Transmission Lines  (Experimental — Settings > Experimental)
| Shortcut | Action |
|----------|--------|
| {{shortcut:port.place_single}} | Place a port glyph (click the canvas) |
| {{shortcut:port.place_continuous}} | Toggle continuous port placement |
| {{shortcut:line.place}} | Place a transmission-line glyph (dialog: FSR, Ztx, f_max, Z0, α, end load) |
| `Insert > Place Loss Hub` | Place an unmonitored dissipation hub (no scattering channel) |
| {{shortcut:edge.place_single}} then click | **Connect**: port → node attaches a mode to that port; a line's **end lead** → port terminates that end; a line's end lead → node **taps** the mode onto the whole comb |
| {{shortcut:rotate.ccw}} / {{shortcut:rotate.cw}} | Rotate the selected glyph in place; two or more selected objects rotate rigidly about their centroid |
| `←/→`, `↑/↓` | Stretch a selected glyph's length / height |
| `Double-click` | Edit a port, line, attachment, tap or pump bus |
| `Right-click` a line | Add / edit / remove its **pumped termination** (creates the conjugate twin and the triple-line pump bus), rotate, auto-orient, delete |
| `Ctrl+A` | Selects glyphs too, so a whole amplifier drawing moves and rotates as one |

**What the glyphs mean.** A **port** (pentagon) is one physical resistor; every mode attached to it shares that dissipation channel, which is what makes ports *shared* (cross-damping between the attached modes falls out of the same column). A **transmission line** (cylinder) is a standing-wave mode comb parameterized by FSR, Ztx and f_max; its comb never appears on the canvas — terminating an end on a port couples all of it through that port's single channel, and tapping a node onto an end couples the node to every comb mode with the verified capacitive or inductive profile. A **pumped termination** (right-click the line) models a modulated inductor at one end as one rank-one block to a **conjugate twin** of the line; the **triple-line bus** is always three strokes because one pump drives amplification *and* conversion pairs together on a harmonic comb.

**End load.** A shunt inductance at one end disperses the comb (the modes leave n·FSR). Set it in the line dialog or Properties page as a type plus f_Z, the frequency at which |X| = Ztx, and use *Target resonance → Set FSR* to put the loaded fundamental where you want it. Capacitive loads are listed but disabled until their direct term is derived.

**Truncation.** f_max sets how many comb modes are kept explicitly. The modes beyond it still load the port; with *close comb tail analytically* (Ports & Lines panel, default on) that loading is folded back in closed form and is exact at any N — what f_max still truncates is the pump/tap couplings onto those modes. Press *Check truncation (2× f_max)* to measure it for the graph you have.

**Reading off mode indices.** The pump's reference pair is named by mode index, so the S-params tab has a **Mark Line Modes** toggle (bottom right of *Axis Controls*, beside *Conjugate Freqs*) that draws each line's normal-mode frequencies on the plot with their indices in small chips along the top, and names the line, index and frequency on hover. Where a signal mode and a twin's idler image coincide the chip shows both (`1/2*`, the starred one being the conjugate). With an end load set these are the *loaded* mode frequencies, which is the case where counting `n·FSR` by eye goes wrong. Markers stop at the comb cutoff (mode N, drawn heavier); a pumped line's twin is marked where its idler image actually lands, at `f_p − f_m`.

**Pump strength.** Beside the pump's rate the panel reports **α** = ε/4 = g/√(ω_nω_m), the dimensionless drive strength, with δL/L_tot alongside. α must stay below 1; past it the rate box turns red and the label says so, since on a loaded comb the participations move with the dispersed roots and the limit is not where you would guess. Note the line's own **α_loss** is the uniform attenuation — a different quantity.

**Where to tune.** In scattering mode the **Ports & Lines** panel (full width under Nodes | Edges) holds every line's FSR/Ztx/f_max/Z0/α, its load's f_Z, the pump's f_p/rate/phase/n, and each attachment's rate and sign — so a line-only graph is fully tunable without any graph node. Selecting a glyph or bus on the canvas shows the same on the Properties tab.

## Selection & Editing
| Shortcut | Action |
|----------|--------|
| `Left click` | Select / drag node |
| `Right click` | Color/type menu |
| `Shift+click` | Multi-select |
| `Click+drag` | Selection window |
| `Double-click` | Edit properties |
| {{shortcut:select.all}} | Select all |
| {{shortcut:clipboard.copy}} | Copy selection |
| {{shortcut:clipboard.cut}} | Cut selection |
| {{shortcut:clipboard.paste}} | Paste |
| {{shortcut:edit.undo}} | Undo |
| {{shortcut:edit.redo_basis}} | Redo |
| {{shortcut:edit.delete_d}} or {{shortcut:edit.delete}} | Delete selection |

## Node/Edge Size & Labels
With a node selected (red ring around it):
| Shortcut | Action |
|----------|--------|
| {{shortcut:pan.up}} | Increase node/edge size |
| {{shortcut:pan.down}} | Decrease node/edge size |
| {{shortcut:pan.left}} | Decrease label size |
| {{shortcut:pan.right}} | Increase label size |
| {{shortcut:label.nudge_left}}/{{shortcut:label.nudge_right}}/{{shortcut:label.nudge_up}}/{{shortcut:label.nudge_down}} | Nudge selected labels |

## Graph Rotation
| Shortcut | Action |
|----------|--------|
| {{shortcut:rotate.ccw}} | Rotate selected nodes 15 degrees CCW |
| {{shortcut:rotate.cw}} | Rotate selected nodes 15 degrees CW |
| {{shortcut:graph.flip_horizontal}} | Flip selected nodes horizontally (left-right) |
| {{shortcut:graph.flip_vertical}} | Flip selected nodes vertically (up-down) |

## Scattering Mode

| Shortcut | Action |
|----------|--------|
| {{shortcut:analysis.scattering}} | Enter/exit scattering mode |
| {{shortcut:tab.toggle_sparams}} | Toggle S-parameters plot |

- When in scattering mode, the Scattering tab appears in the right panel for assigning node/edge parameters.
- The S-params plot shows computed scattering parameters when all assignments are complete.

## Basis Ordering
| Shortcut | Action |
|----------|--------|
| {{shortcut:analysis.basis_mode}} | Toggle basis ordering mode |
| `Click nodes` | Select basis order (when in basis mode) |
| {{shortcut:analysis.commit_mode}} | Commit basis order |
| {{shortcut:node.exit_placement}} | Cancel basis ordering |
| {{shortcut:edit.undo}} | Undo last basis selection |
| {{shortcut:edit.redo_basis}} | Redo basis selection |

## Kron Reduction
| Shortcut | Action |
|----------|--------|
| {{shortcut:analysis.kron_mode}} | Enter Kron reduction mode |
| {{shortcut:analysis.kron_mode_keyboard}} | Enter Kron mode (alternative) |
| {{shortcut:analysis.commit_mode}} | Commit Kron reduction |
| {{shortcut:node.exit_placement}} | Cancel Kron reduction |

## Tab Navigation
| Shortcut | Action |
|----------|--------|
| {{shortcut:tab.matrix}} | Switch to Matrix tab (inside Symbolic) |
| {{shortcut:tab.basis}} | Switch to Basis tab (inside Symbolic) |
| {{shortcut:tab.code}} | Switch to SymPy Code tab (inside Symbolic) |
| {{shortcut:tab.switch_1}}/{{shortcut:tab.switch_2}}/{{shortcut:tab.switch_3}}/{{shortcut:tab.switch_4}} | Switch to Nth visible graph tab |

## Export & LaTeX
| Shortcut | Action |
|----------|--------|
| {{shortcut:file.export_code}} | Export graph drawing code |
| {{shortcut:clipboard.copy_graph_image}} | Copy graph to clipboard (paste into Keynote/PowerPoint/Illustrator) |
| {{shortcut:clipboard.copy_graph_vector}} | Copy graph to clipboard, vector only (forces vector paste in Keynote/PowerPoint) |
| {{shortcut:edit.toggle_latex}} | Toggle LaTeX rendering |
| {{shortcut:clipboard.copy_matrix_latex}} | Copy matrix LaTeX to clipboard |
| {{shortcut:clipboard.export_sympy}} | Export SymPy code to clipboard |

*Note:* LaTeX rendering is kind of slow (and also requires you to have LaTeX configured on your computer). It's best practice to turn it on to render a final (nicer-looking) graph.

## Spinbox Fine Control

When a spinbox (numeric input) has focus:
| Shortcut | Action |
|----------|--------|
| `Up/Down` | Change by normal step |
| `Shift+Up/Down` | Fine control (1/10 of normal step) |
| `Alt+Up/Down` | Coarse control (10x normal step) |

## Other
| Shortcut | Action |
|----------|--------|
| {{shortcut:edit.clear_all}} | Clear all nodes and edges |

---

## Settings

**Settings Dialog**: Access via {{shortcut:file.settings}} (or File > Settings on Windows/Linux, paragraphulator > Preferences on macOS) to adjust node/edge defaults, self-loop appearance, and display options.

**Settings File Location**: Use File > "Show Settings File Location" to open the folder containing your settings file (`~/.graphulator/settings.json`). This JSON file stores your preferences and can be edited directly for fine-grained control.

The settings file contains all configurable parameters organized by category. If the file doesn't exist, it will be created with default values when you first access this menu item. You can:

- Edit values directly in a text editor
- Delete the file to reset all settings to defaults
- Back up the file to preserve your configuration

**Caution**: The application reads the settings file at startup. Invalid JSON or incorrect values may cause unexpected behavior. Keep a backup before making manual edits.

---

## Misc Notes
- **Matrix/Basis Display**: The zoom and pan controls ({{shortcut:matrix.zoom_in}}/{{shortcut:matrix.zoom_out}}/{{shortcut:matrix.zoom_reset}} and Alt+Arrow) work when the Matrix or Basis view has focus.

- **Notes Tab**: The Notes tab supports Markdown with LaTeX math (use `$...$` for inline, `$$...$$` for display). Switch between Edit and Preview subtabs to see rendered output.

- **Trackpad**: Pinch-to-zoom works in Matrix/Basis displays via built-in browser support.

- **Auto-increment mode**: When enabled with {{shortcut:node.place_duplicate}}, each new node's label automatically increments.

- **Basis ordering**: Selected nodes are highlighted in the canvas and numbered in order.

- **Kron reduction**: Selected nodes are colored differently to indicate they will be eliminated.
