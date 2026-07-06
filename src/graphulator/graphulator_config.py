"""
Graphulator Configuration File
Settings and color palettes for the graph drawing GUI
"""

# Color palette
MYCOLORS = dict(
    RED='indianred',
    BLUE='cornflowerblue',
    GREEN='darkseagreen',
    ORANGE='sandybrown',
    PURPLE='mediumpurple',
    TEAL='mediumaquamarine',
    WHITE='white',
    BLACK='black',
    GRAY='gray',
    LIGHTGRAY='lightgray',
    DARKGRAY='darkgray',
)

# Default node settings
DEFAULT_NODE_COLOR_KEY = 'RED'  # key into MYCOLORS; the node dialogs work in keys
DEFAULT_NODE_COLOR = MYCOLORS[DEFAULT_NODE_COLOR_KEY]  # derived; kept in sync
DEFAULT_NODE_RADIUS = 0.6
DEFAULT_NODE_LABEL_SIZE_MULT = 1.4  # label scale for new nodes (dialog 'Large')
DEFAULT_NODE_OUTLINE_ENABLED = False
DEFAULT_NODE_OUTLINE_COLOR = 'black'
DEFAULT_NODE_OUTLINE_WIDTH = 2.5
DEFAULT_NODE_OUTLINE_ALPHA = 1.0
DEFAULT_NODE_LABEL_COLOR = 'white'
DEFAULT_NODE_LABEL_SIZE = 28

# Conjugated-mode rendering convention (applies to the whole graph at draw
# time; nodes store only their 'conj' flag). Conjugation reads as an
# "inversion" of the unconjugated appearance, so the styles derive from the
# node's own colors; 'custom' escapes to an explicit color where needed.
CONJ_NODE_FILL_MODE = 'dimmed'  # 'dimmed' (alpha fill) | 'transparent' (hollow: ring in node color) | 'custom'
CONJ_NODE_FILL_ALPHA = 0.5      # fill alpha for 'dimmed' mode
CONJ_NODE_FILL_COLOR = 'lightsteelblue'  # fill for 'custom' mode
CONJ_LABEL_COLOR_AUTO = True    # True: derive (hollow -> node color, else normal label color)
CONJ_LABEL_COLOR_MODE = 'default'  # literal choice when AUTO is off: 'default' | 'node' | 'custom'
CONJ_NODE_LABEL_COLOR = 'white'    # label color for the 'custom' literal choice
CONJ_LABEL_SCALE = 0.92         # label shrink to accommodate the asterisk

# Default edge settings
DEFAULT_EDGE_STYLE = 'loopy'      # 'loopy' | 'single' | 'double' (for new edges)
DEFAULT_EDGE_LINEWIDTH_MULT = 1.5  # line width for new edges (dialog 'Medium')
DEFAULT_EDGE_LOOPTHETA = 30       # loopy-style curvature angle for new edges (degrees)
DEFAULT_EDGE_LABEL_SIZE_MULT = 1.4    # edge label scale for new edges (dialog 'Medium')
DEFAULT_EDGE_LABEL_OFFSET_MULT = 0.8  # edge label offset for new edges (dialog 'Medium')
DEFAULT_EDGE_ARROWSTYLE = 'open'  # 'open' | 'filled' | 'stealth'
DEFAULT_EDGE_ARROWSCALE = 1.0     # relative arrowhead scaling for new edges
ARROWHEAD_OPEN_ANGLE = 60         # arrowhead opening angle in degrees (convention; applies at draw time)

# Grid settings
DEFAULT_GRID_SPACING = 1.0
DEFAULT_GRID_TYPE = "square"  # "square" or "triangular"

# View settings
DEFAULT_XLIM = (-10, 10)
DEFAULT_YLIM = (-10, 10)
DEFAULT_FIGURE_SIZE = (12, 12)

# Zoom settings
ZOOM_KEYBOARD_FACTOR = 1.2
ZOOM_SCROLL_FACTOR = 1.15
AUTOFIT_PADDING_FACTOR = 1.5

# Grid rotation increments (degrees)
SQUARE_GRID_ROTATION_INCREMENT = 45
TRIANGULAR_GRID_ROTATION_INCREMENT = 30

# Self-loop settings
DEFAULT_SELFLOOP_ANGLE = 90  # degrees (90° = Up)
DEFAULT_SELFLOOP_SCALE = 1.0  # size scale for new self-loops
DEFAULT_SELFLOOP_LINEWIDTH_MULT = 1.5  # line width for new self-loops (dialog 'Medium')
SELFLOOP_ANGLE_KEYBOARD_INCREMENT = 15  # degrees per keypress (must be multiple of 5)
AUTO_ADJUST_SELFLOOP_ANGLE = True  # When True, new self-loops auto-orient away from edges
DYNAMIC_ADJUST_SELFLOOP_ANGLE = True  # When True, unpinned self-loops reorient on drag-end

# Interface settings
SHOW_SHORTCUT_OVERLAY = False  # optional on-canvas context-sensitive shortcut hints
SHORTCUT_OVERLAY_CORNER = 'top-right'  # 'top-left'|'top-right'|'bottom-left'|'bottom-right'
SHORTCUT_OVERLAY_SHOW_ALL = False  # False: curated essentials; True: every shortcut for the context

# =============================================================================
# SETTINGS DIALOG PARAMETER DEFINITIONS
# =============================================================================
# Format: {tab_name: [(config_attr, display_name, type, min, max, step), ...]}
# For 'dropdown' the min slot holds the options (list of (display, value)).
SETTINGS_PARAMS = {
    'Node Defaults': [
        ('DEFAULT_NODE_COLOR_KEY', 'Node Color', 'dropdown', 'MYCOLORS_KEYS', None, None),
        ('DEFAULT_NODE_RADIUS', 'Node Base Radius', 'float', 0.1, 2.0, 0.1),
        ('DEFAULT_NODE_LABEL_SIZE_MULT', 'Node Label Scale (×)', 'float', 0.5, 3.0, 0.1),
        ('DEFAULT_NODE_LABEL_COLOR', 'Node Label Color', 'color', None, None, None),
        ('DEFAULT_NODE_OUTLINE_ENABLED', 'Show Node Outline', 'bool', None, None, None),
        ('DEFAULT_NODE_OUTLINE_COLOR', 'Outline Color', 'color', None, None, None),
        ('DEFAULT_NODE_OUTLINE_WIDTH', 'Outline Width', 'float', 0.5, 10.0, 0.5),
        ('DEFAULT_NODE_OUTLINE_ALPHA', 'Outline Opacity', 'float', 0.0, 1.0, 0.05),
    ],
    'Edge Defaults': [
        ('DEFAULT_EDGE_STYLE', 'Edge Style', 'dropdown',
         [('Loopy', 'loopy'), ('Single', 'single'), ('Double', 'double')], None, None),
        ('DEFAULT_EDGE_LINEWIDTH_MULT', 'Edge Line Width (×)', 'float', 0.5, 3.0, 0.25),
        ('DEFAULT_EDGE_LOOPTHETA', 'Loopy Curvature θ (°)', 'int', -180, 180, 5),
        ('DEFAULT_EDGE_LABEL_SIZE_MULT', 'Edge Label Scale (×)', 'float', 0.5, 3.0, 0.1),
        ('DEFAULT_EDGE_LABEL_OFFSET_MULT', 'Edge Label Offset (×)', 'float', 0.3, 3.0, 0.1),
        ('DEFAULT_EDGE_ARROWSTYLE', 'Arrowhead Style', 'dropdown',
         [('Open', 'open'), ('Filled', 'filled'), ('Stealth', 'stealth')], None, None),
        ('DEFAULT_EDGE_ARROWSCALE', 'Arrowhead Scale (×)', 'float', 0.2, 3.0, 0.1),
        ('ARROWHEAD_OPEN_ANGLE', 'Arrowhead Opening Angle (°)', 'int', 20, 120, 5),
    ],
    'Conventions': [
        ('CONJ_NODE_FILL_MODE', 'Conjugated Node Style', 'dropdown',
         [('Dimmed (reduced opacity)', 'dimmed'),
          ('Hollow (ring in node color)', 'transparent'),
          ('Custom color', 'custom')], None, None),
        ('CONJ_NODE_FILL_ALPHA', 'Conjugated Fill Opacity', 'float', 0.1, 1.0, 0.05),
        ('CONJ_NODE_FILL_COLOR', 'Custom Fill Color', 'color', None, None, None),
        ('CONJ_LABEL_COLOR_AUTO', 'Auto Conjugated Label Color', 'bool', None, None, None),
        ('CONJ_LABEL_COLOR_MODE', 'Conjugated Label Color', 'dropdown',
         [('Same as normal labels', 'default'),
          ('Unconjugated node color', 'node'),
          ('Custom color', 'custom')], None, None),
        ('CONJ_NODE_LABEL_COLOR', 'Custom Label Color', 'color', None, None, None),
        ('CONJ_LABEL_SCALE', 'Conjugated Label Scale', 'float', 0.5, 1.0, 0.02),
    ],
    'Self-Loop Defaults': [
        ('DEFAULT_SELFLOOP_ANGLE', 'Default Angle (°)', 'int', 0, 355, 15),
        ('DEFAULT_SELFLOOP_SCALE', 'Size Scale (×)', 'float', 0.5, 2.0, 0.1),
        ('DEFAULT_SELFLOOP_LINEWIDTH_MULT', 'Line Width (×)', 'float', 0.5, 3.0, 0.25),
        ('AUTO_ADJUST_SELFLOOP_ANGLE', 'Auto-Orient New Self-Loops', 'bool', None, None, None),
        ('DYNAMIC_ADJUST_SELFLOOP_ANGLE', 'Re-Orient Unpinned on Drag', 'bool', None, None, None),
    ],
    'Interface': [
        ('SHOW_SHORTCUT_OVERLAY', 'Show Shortcut Hints', 'bool', None, None, None),
        ('SHORTCUT_OVERLAY_CORNER', 'Hints Corner', 'dropdown',
         [('Top Left', 'top-left'), ('Top Right', 'top-right'),
          ('Bottom Left', 'bottom-left'), ('Bottom Right', 'bottom-right')], None, None),
        ('SHORTCUT_OVERLAY_SHOW_ALL', 'Show All Shortcuts (not just essentials)', 'bool', None, None, None),
    ],
}

# Parameters that are rendering conventions (read at draw time): the Settings
# dialog live-applies these to the open graph, debounced, as they change.
LIVE_PARAMS = (
    'CONJ_NODE_FILL_MODE',
    'CONJ_NODE_FILL_ALPHA',
    'CONJ_NODE_FILL_COLOR',
    'CONJ_LABEL_COLOR_AUTO',
    'CONJ_LABEL_COLOR_MODE',
    'CONJ_NODE_LABEL_COLOR',
    'CONJ_LABEL_SCALE',
    'ARROWHEAD_OPEN_ANGLE',
    'DEFAULT_NODE_RADIUS',
    'DEFAULT_NODE_LABEL_COLOR',  # read at draw time for nodes without an override
    'SHOW_SHORTCUT_OVERLAY',     # toggling/corner/detail apply to the overlay immediately
    'SHORTCUT_OVERLAY_CORNER',
    'SHORTCUT_OVERLAY_SHOW_ALL',
)
