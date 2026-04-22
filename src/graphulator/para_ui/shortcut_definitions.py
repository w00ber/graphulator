"""
Shortcut definitions for Graphulator/Paragraphulator.

This module contains all keyboard shortcut definitions with OS-specific defaults.
Each shortcut is defined with platform-specific key bindings that are automatically
selected based on the user's operating system.

Platform keys:
- "darwin": macOS
- "win32": Windows
- "linux": Linux and other Unix-like systems
- "default": Fallback for any platform not explicitly listed

Note on Qt key handling:
- Qt automatically maps "Ctrl" to Command (⌘) on macOS and Ctrl on Windows/Linux
- "Meta" in Qt means Control (⌃) on macOS and Windows key on Windows
- Therefore, use "Ctrl+X" for cross-platform shortcuts - Qt handles display correctly
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ShortcutDefinition:
    """Definition of a keyboard shortcut with platform-specific defaults."""

    action_id: str
    """Unique identifier for this shortcut action (e.g., 'file.new', 'node.place_single')"""

    display_name: str
    """Human-readable name shown in settings UI (e.g., 'New Graph')"""

    category: str
    """Category for grouping in settings UI (e.g., 'File', 'Node Placement')"""

    description: str
    """Description/tooltip text explaining what the shortcut does"""

    default_keys: Dict[str, str]
    """Platform -> key sequence mapping. Use 'default' as fallback."""

    is_single_key: bool = False
    """If True, shortcut needs input focus protection (won't trigger in text fields)"""

    is_menu_action: bool = False
    """If True, this shortcut is attached to a menu action (not just a QShortcut)"""


# Ordered list of categories for UI display
SHORTCUT_CATEGORIES = [
    "File",
    "Edit",
    "View",
    "Node Placement",
    "Edge Operations",
    "Selection & Clipboard",
    "Grid Controls",
    "Graph Rotation",
    "Label Adjustments",
    "Self-Loop Adjustments",
    "Canvas Navigation",
    "Matrix Display",
    "Tabs",
    "Scattering & Analysis",
    "Help",
]


# All shortcut definitions
# Note: "Ctrl+" is used for cross-platform shortcuts.
# Qt automatically displays this as Cmd on macOS and Ctrl on Windows/Linux.
SHORTCUT_DEFINITIONS: List[ShortcutDefinition] = [

    # ===== FILE =====
    ShortcutDefinition(
        action_id="file.new",
        display_name="New Graph",
        category="File",
        description="Create a new empty graph",
        default_keys={"default": "Ctrl+N"},
        is_menu_action=True,
    ),
    ShortcutDefinition(
        action_id="file.open",
        display_name="Open Graph",
        category="File",
        description="Open an existing graph file",
        default_keys={"default": "Ctrl+O"},
        is_menu_action=True,
    ),
    ShortcutDefinition(
        action_id="file.save",
        display_name="Save Graph",
        category="File",
        description="Save the current graph",
        default_keys={"default": "Ctrl+S"},
        is_menu_action=True,
    ),
    ShortcutDefinition(
        action_id="file.save_as",
        display_name="Save Graph As",
        category="File",
        description="Save the current graph with a new name",
        default_keys={"default": "Ctrl+Shift+S"},
        is_menu_action=True,
    ),
    ShortcutDefinition(
        action_id="file.export_code",
        display_name="Export Python Code",
        category="File",
        description="Export the graph as Python code",
        default_keys={"default": "Ctrl+Shift+E"},
        is_menu_action=True,
    ),
    ShortcutDefinition(
        action_id="file.settings",
        display_name="Settings",
        category="File",
        description="Open the settings dialog",
        default_keys={"default": "Ctrl+,"},
        is_menu_action=True,
    ),
    ShortcutDefinition(
        action_id="file.quit",
        display_name="Quit",
        category="File",
        description="Exit the application",
        default_keys={"default": "Ctrl+Q"},
        is_menu_action=True,
    ),

    # ===== EDIT =====
    ShortcutDefinition(
        action_id="edit.undo",
        display_name="Undo",
        category="Edit",
        description="Undo the last action",
        default_keys={"default": "Ctrl+Z"},
    ),
    ShortcutDefinition(
        action_id="edit.redo_basis",
        display_name="Redo Basis Selection",
        category="Edit",
        description="Redo basis selection",
        default_keys={"default": "Ctrl+Shift+Z"},
    ),
    ShortcutDefinition(
        action_id="edit.delete",
        display_name="Delete Selected",
        category="Edit",
        description="Delete selected nodes and edges",
        default_keys={"darwin": "Backspace", "default": "Delete"},
    ),
    ShortcutDefinition(
        action_id="edit.delete_d",
        display_name="Delete Selected (D key)",
        category="Edit",
        description="Delete selected nodes and edges using D key",
        default_keys={"default": "D"},
        is_single_key=True,
    ),
    ShortcutDefinition(
        action_id="edit.clear_all",
        display_name="Clear All Nodes",
        category="Edit",
        description="Clear all nodes from the graph",
        default_keys={"default": "Ctrl+Shift+C"},
    ),
    ShortcutDefinition(
        action_id="edit.toggle_latex",
        display_name="Toggle LaTeX Rendering",
        category="Edit",
        description="Toggle LaTeX rendering mode for labels",
        default_keys={"default": "Ctrl+L"},
    ),

    # ===== VIEW =====
    ShortcutDefinition(
        action_id="view.auto_fit",
        display_name="Auto-Fit View",
        category="View",
        description="Automatically fit all nodes in the view",
        default_keys={"default": "A"},
        is_single_key=True,
    ),
    ShortcutDefinition(
        action_id="view.zoom_in",
        display_name="Zoom In",
        category="View",
        description="Zoom in on the canvas",
        default_keys={"default": "+"},
        is_single_key=True,
    ),
    ShortcutDefinition(
        action_id="view.zoom_in_equals",
        display_name="Zoom In (= key)",
        category="View",
        description="Zoom in on the canvas using = key",
        default_keys={"default": "="},
        is_single_key=True,
    ),
    ShortcutDefinition(
        action_id="view.zoom_out",
        display_name="Zoom Out",
        category="View",
        description="Zoom out on the canvas",
        default_keys={"default": "-"},
        is_single_key=True,
    ),

    # ===== NODE PLACEMENT =====
    ShortcutDefinition(
        action_id="node.place_single",
        display_name="Place Single Node",
        category="Node Placement",
        description="Enter single node placement mode",
        default_keys={"default": "G"},
        is_single_key=True,
    ),
    ShortcutDefinition(
        action_id="node.place_continuous",
        display_name="Continuous Node Placement",
        category="Node Placement",
        description="Toggle continuous node placement mode",
        default_keys={"default": "Shift+G"},
    ),
    ShortcutDefinition(
        action_id="node.place_duplicate",
        display_name="Continuous Duplicate Mode",
        category="Node Placement",
        description="Toggle continuous duplicate mode with auto-increment labels",
        default_keys={"default": "Ctrl+G"},
    ),
    ShortcutDefinition(
        action_id="node.exit_placement",
        display_name="Exit Placement Mode",
        category="Node Placement",
        description="Exit current placement mode or clear selection",
        default_keys={"default": "Escape"},
    ),
    ShortcutDefinition(
        action_id="node.toggle_conjugation",
        display_name="Toggle Conjugation Mode",
        category="Node Placement",
        description="Toggle conjugation mode for clicking nodes",
        default_keys={"default": "C"},
        is_single_key=True,
    ),

    # ===== EDGE OPERATIONS =====
    ShortcutDefinition(
        action_id="edge.place_single",
        display_name="Place Edge",
        category="Edge Operations",
        description="Enter single edge placement mode",
        default_keys={"default": "E"},
        is_single_key=True,
    ),
    ShortcutDefinition(
        action_id="edge.place_continuous",
        display_name="Continuous Edge Mode",
        category="Edge Operations",
        description="Toggle continuous edge placement mode",
        default_keys={"default": "Ctrl+E"},
    ),

    # ===== SELECTION & CLIPBOARD =====
    ShortcutDefinition(
        action_id="select.all",
        display_name="Select All",
        category="Selection & Clipboard",
        description="Select all nodes and edges",
        default_keys={"default": "Ctrl+A"},
    ),
    ShortcutDefinition(
        action_id="clipboard.copy",
        display_name="Copy",
        category="Selection & Clipboard",
        description="Copy selected nodes and edges",
        default_keys={"default": "Ctrl+C"},
    ),
    ShortcutDefinition(
        action_id="clipboard.cut",
        display_name="Cut",
        category="Selection & Clipboard",
        description="Cut selected nodes and edges",
        default_keys={"default": "Ctrl+X"},
    ),
    ShortcutDefinition(
        action_id="clipboard.paste",
        display_name="Paste (Smart)",
        category="Selection & Clipboard",
        description="Paste with smart label autoincrement",
        default_keys={"default": "Ctrl+V"},
    ),
    ShortcutDefinition(
        action_id="clipboard.paste_raw",
        display_name="Paste (Raw)",
        category="Selection & Clipboard",
        description="Paste with original labels (no autoincrement)",
        default_keys={"default": "Ctrl+Shift+V"},
    ),
    ShortcutDefinition(
        action_id="clipboard.copy_matrix_latex",
        display_name="Copy Matrix LaTeX",
        category="Selection & Clipboard",
        description="Copy the matrix as LaTeX to clipboard",
        default_keys={"default": "Ctrl+Shift+L"},
    ),
    ShortcutDefinition(
        action_id="clipboard.export_sympy",
        display_name="Export SymPy Code",
        category="Selection & Clipboard",
        description="Export SymPy code to clipboard",
        default_keys={"default": "Alt+E"},
    ),

    # ===== GRID CONTROLS =====
    ShortcutDefinition(
        action_id="grid.rotate",
        display_name="Rotate Grid",
        category="Grid Controls",
        description="Rotate the grid (45 degrees square, 30 degrees triangular)",
        default_keys={"default": "R"},
        is_single_key=True,
    ),
    ShortcutDefinition(
        action_id="grid.toggle_type",
        display_name="Toggle Grid Type",
        category="Grid Controls",
        description="Toggle between square and triangular grid",
        default_keys={"default": "T"},
        is_single_key=True,
    ),

    # ===== GRAPH ROTATION =====
    ShortcutDefinition(
        action_id="rotate.ccw",
        display_name="Rotate Selection CCW",
        category="Graph Rotation",
        description="Rotate selected nodes 15 degrees counter-clockwise",
        default_keys={"default": "Ctrl+U"},
    ),
    ShortcutDefinition(
        action_id="rotate.cw",
        display_name="Rotate Selection CW",
        category="Graph Rotation",
        description="Rotate selected nodes 15 degrees clockwise",
        default_keys={"default": "Ctrl+I"},
    ),
    ShortcutDefinition(
        action_id="graph.flip_horizontal",
        display_name="Flip Horizontal",
        category="Graph Rotation",
        description="Flip selected nodes horizontally (left-right mirror)",
        default_keys={"default": "F"},
        is_single_key=True,
    ),
    ShortcutDefinition(
        action_id="graph.flip_vertical",
        display_name="Flip Vertical",
        category="Graph Rotation",
        description="Flip selected nodes vertically (up-down mirror)",
        default_keys={"default": "Shift+F"},
    ),

    # ===== LABEL ADJUSTMENTS =====
    ShortcutDefinition(
        action_id="label.nudge_left",
        display_name="Nudge Label Left",
        category="Label Adjustments",
        description="Nudge the node label to the left",
        default_keys={"default": "Shift+Left"},
    ),
    ShortcutDefinition(
        action_id="label.nudge_right",
        display_name="Nudge Label Right",
        category="Label Adjustments",
        description="Nudge the node label to the right",
        default_keys={"default": "Shift+Right"},
    ),
    ShortcutDefinition(
        action_id="label.nudge_up",
        display_name="Nudge Label Up",
        category="Label Adjustments",
        description="Nudge the node label up",
        default_keys={"default": "Shift+Up"},
    ),
    ShortcutDefinition(
        action_id="label.nudge_down",
        display_name="Nudge Label Down",
        category="Label Adjustments",
        description="Nudge the node label down",
        default_keys={"default": "Shift+Down"},
    ),

    # ===== SELF-LOOP ADJUSTMENTS =====
    ShortcutDefinition(
        action_id="selfloop.scale_increase",
        display_name="Increase Self-Loop Scale",
        category="Self-Loop Adjustments",
        description="Increase the scale of self-loops on selected nodes",
        default_keys={"default": "Ctrl+Up"},
    ),
    ShortcutDefinition(
        action_id="selfloop.scale_decrease",
        display_name="Decrease Self-Loop Scale",
        category="Self-Loop Adjustments",
        description="Decrease the scale of self-loops on selected nodes",
        default_keys={"default": "Ctrl+Down"},
    ),
    ShortcutDefinition(
        action_id="selfloop.angle_decrease",
        display_name="Rotate Self-Loop/Edge CCW",
        category="Self-Loop Adjustments",
        description="Adjust self-loop angle or edge looptheta counter-clockwise",
        default_keys={"default": "Ctrl+Left"},
    ),
    ShortcutDefinition(
        action_id="selfloop.angle_increase",
        display_name="Rotate Self-Loop/Edge CW",
        category="Self-Loop Adjustments",
        description="Adjust self-loop angle or edge looptheta clockwise",
        default_keys={"default": "Ctrl+Right"},
    ),

    # ===== CANVAS NAVIGATION =====
    ShortcutDefinition(
        action_id="pan.left",
        display_name="Pan Left / Adjust",
        category="Canvas Navigation",
        description="Pan view left or adjust selected element",
        default_keys={"default": "Left"},
    ),
    ShortcutDefinition(
        action_id="pan.right",
        display_name="Pan Right / Adjust",
        category="Canvas Navigation",
        description="Pan view right or adjust selected element",
        default_keys={"default": "Right"},
    ),
    ShortcutDefinition(
        action_id="pan.up",
        display_name="Pan Up / Adjust",
        category="Canvas Navigation",
        description="Pan view up or adjust selected element (e.g., increase size)",
        default_keys={"default": "Up"},
    ),
    ShortcutDefinition(
        action_id="pan.down",
        display_name="Pan Down / Adjust",
        category="Canvas Navigation",
        description="Pan view down or adjust selected element (e.g., decrease size)",
        default_keys={"default": "Down"},
    ),

    # ===== MATRIX DISPLAY =====
    ShortcutDefinition(
        action_id="matrix.zoom_in",
        display_name="Zoom Matrix In",
        category="Matrix Display",
        description="Zoom in on the matrix display",
        default_keys={"default": "Ctrl+="},
    ),
    ShortcutDefinition(
        action_id="matrix.zoom_in_plus",
        display_name="Zoom Matrix In (+)",
        category="Matrix Display",
        description="Zoom in on the matrix display using + key",
        default_keys={"default": "Ctrl++"},
    ),
    ShortcutDefinition(
        action_id="matrix.zoom_out",
        display_name="Zoom Matrix Out",
        category="Matrix Display",
        description="Zoom out on the matrix display",
        default_keys={"default": "Ctrl+-"},
    ),
    ShortcutDefinition(
        action_id="matrix.zoom_reset",
        display_name="Reset Matrix Zoom",
        category="Matrix Display",
        description="Reset the matrix display zoom to default",
        default_keys={"default": "Ctrl+0"},
    ),
    ShortcutDefinition(
        action_id="matrix.pan_left",
        display_name="Pan Matrix Left",
        category="Matrix Display",
        description="Pan the matrix display left",
        default_keys={"default": "Alt+Left"},
    ),
    ShortcutDefinition(
        action_id="matrix.pan_right",
        display_name="Pan Matrix Right",
        category="Matrix Display",
        description="Pan the matrix display right",
        default_keys={"default": "Alt+Right"},
    ),
    ShortcutDefinition(
        action_id="matrix.pan_up",
        display_name="Pan Matrix Up",
        category="Matrix Display",
        description="Pan the matrix display up",
        default_keys={"default": "Alt+Up"},
    ),
    ShortcutDefinition(
        action_id="matrix.pan_down",
        display_name="Pan Matrix Down",
        category="Matrix Display",
        description="Pan the matrix display down",
        default_keys={"default": "Alt+Down"},
    ),

    # ===== TABS =====
    ShortcutDefinition(
        action_id="tab.matrix",
        display_name="Show Matrix Tab",
        category="Tabs",
        description="Switch to the Symbolic > Matrix subtab",
        default_keys={"default": "M"},
        is_single_key=True,
    ),
    ShortcutDefinition(
        action_id="tab.basis",
        display_name="Show Basis Tab",
        category="Tabs",
        description="Switch to the Symbolic > Basis subtab",
        default_keys={"default": "B"},
        is_single_key=True,
    ),
    ShortcutDefinition(
        action_id="tab.code",
        display_name="Show Code Tab",
        category="Tabs",
        description="Switch to the SymPy Code tab",
        default_keys={"default": "S"},
        is_single_key=True,
    ),
    ShortcutDefinition(
        action_id="tab.toggle_sparams",
        display_name="Toggle S-Params Tab",
        category="Tabs",
        description="Toggle the S-Parameters tab visibility",
        default_keys={"default": "Ctrl+Shift+R"},
    ),
    ShortcutDefinition(
        action_id="tab.switch_1",
        display_name="Switch to Tab 1",
        category="Tabs",
        description="Switch to the first visible tab",
        default_keys={"default": "Ctrl+1"},
    ),
    ShortcutDefinition(
        action_id="tab.switch_2",
        display_name="Switch to Tab 2",
        category="Tabs",
        description="Switch to the second visible tab",
        default_keys={"default": "Ctrl+2"},
    ),
    ShortcutDefinition(
        action_id="tab.switch_3",
        display_name="Switch to Tab 3",
        category="Tabs",
        description="Switch to the third visible tab",
        default_keys={"default": "Ctrl+3"},
    ),
    ShortcutDefinition(
        action_id="tab.switch_4",
        display_name="Switch to Tab 4",
        category="Tabs",
        description="Switch to the fourth visible tab",
        default_keys={"default": "Ctrl+4"},
    ),

    # ===== SCATTERING & ANALYSIS =====
    ShortcutDefinition(
        action_id="analysis.basis_mode",
        display_name="Enter Basis Ordering Mode",
        category="Scattering & Analysis",
        description="Enter basis ordering mode to reorder the matrix basis",
        default_keys={"default": "Ctrl+B"},
        is_menu_action=True,
    ),
    ShortcutDefinition(
        action_id="analysis.scattering",
        display_name="Enable Scattering",
        category="Scattering & Analysis",
        description="Toggle scattering mode",
        default_keys={"default": "Ctrl+R"},
        is_menu_action=True,
    ),
    ShortcutDefinition(
        action_id="analysis.kron_mode",
        display_name="Start Kron Reduction",
        category="Scattering & Analysis",
        description="Enter Kron reduction mode",
        default_keys={"default": "Ctrl+K"},
        is_menu_action=True,
    ),
    ShortcutDefinition(
        action_id="analysis.kron_mode_keyboard",
        display_name="Kron Reduction (Keyboard)",
        category="Scattering & Analysis",
        description="Enter Kron reduction mode via keyboard",
        default_keys={"default": "Ctrl+Shift+K"},
    ),
    ShortcutDefinition(
        action_id="analysis.commit_mode",
        display_name="Commit Current Mode",
        category="Scattering & Analysis",
        description="Commit the current mode (basis ordering or Kron reduction)",
        default_keys={"default": "Ctrl+Shift+Return"},
    ),

    # ===== HELP =====
    ShortcutDefinition(
        action_id="help.show",
        display_name="Show Help",
        category="Help",
        description="Show the help dialog",
        default_keys={"default": "F1"},
        is_menu_action=True,
    ),
]


def get_definitions_by_category() -> Dict[str, List[ShortcutDefinition]]:
    """Get all shortcut definitions grouped by category."""
    result: Dict[str, List[ShortcutDefinition]] = {}
    for defn in SHORTCUT_DEFINITIONS:
        if defn.category not in result:
            result[defn.category] = []
        result[defn.category].append(defn)
    return result


def get_definition(action_id: str) -> ShortcutDefinition | None:
    """Get a shortcut definition by its action ID."""
    for defn in SHORTCUT_DEFINITIONS:
        if defn.action_id == action_id:
            return defn
    return None
