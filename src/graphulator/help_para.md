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

- If you are calculating scattering, it's necessary to define "ports" for the possible source/receiver pairs. These are signaled to the computation by placing self-loops on a node. Self-loops are constructed in Edge Placement Mode (below) by double-clicking a node (defining the to/from node to be the same).

## Edge Operations
| Shortcut | Action |
|----------|--------|
| {{shortcut:edge.place_single}} | Toggle single edge placement mode |
| {{shortcut:edge.place_continuous}} | Toggle continuous edge mode |
| {{shortcut:selfloop.scale_increase}} | Increase self-loop scale |
| {{shortcut:selfloop.scale_decrease}} | Decrease self-loop scale |
| {{shortcut:selfloop.angle_decrease}} | Decrease self-loop angle / edge looptheta |
| {{shortcut:selfloop.angle_increase}} | Increase self-loop angle / edge looptheta |

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
