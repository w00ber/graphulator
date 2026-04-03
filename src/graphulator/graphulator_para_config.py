"""
Graphulator Para Configuration File
Settings and default values for the parametric graph editor

This file is self-contained and does not depend on graphulator_config.py
"""

# =============================================================================
# COLOR PALETTE
# =============================================================================

# Color palette for nodes and other elements
MYCOLORS = {
    'RED': 'indianred',
    'BLUE': 'cornflowerblue',
    'GREEN': 'darkseagreen',
    'ORANGE': 'sandybrown',
    'PURPLE': 'mediumpurple',
    'TEAL': 'mediumaquamarine',
    'WHITE': 'white',
    'BLACK': 'black',
    'GRAY': 'gray',
    'LIGHTGRAY': 'lightgray',
    'DARKGRAY': 'darkgray',
}

# =============================================================================
# NODE APPEARANCE DEFAULTS
# =============================================================================

# Default node properties for new nodes
DEFAULT_NODE_COLOR = 'indianred'
DEFAULT_NODE_COLOR_KEY = 'RED'
DEFAULT_NODE_RADIUS = 0.6  # Base radius in axis units
DEFAULT_NODE_SIZE_MULT = 1.0  # Multiplier for node radius
DEFAULT_NODE_LABEL_SIZE_MULT = 1.4  # Multiplier for label font size
DEFAULT_NODE_CONJUGATED = False

# Node outline (circle border) settings
DEFAULT_NODE_OUTLINE_COLOR_KEY = 'BLACK'  # Key into MYCOLORS for outline color
DEFAULT_NODE_OUTLINE_COLOR = 'black'  # Actual color value (derived from MYCOLORS[DEFAULT_NODE_OUTLINE_COLOR_KEY])
DEFAULT_NODE_OUTLINE_WIDTH = 2.5  # Line width for node circle border
DEFAULT_NODE_OUTLINE_ALPHA = 1.0  # Transparency for node outline (0.0 = transparent, 1.0 = opaque)
DEFAULT_NODE_OUTLINE_ENABLED = False  # Whether to draw node outlines

# Node label settings
DEFAULT_NODE_LABEL_COLOR = 'white'
DEFAULT_NODE_LABEL_SIZE = 28  # Base font size in points

# Node size slider settings (in Properties panel and dialogs)
NODE_SIZE_SLIDER_MIN = 50  # 0.5x multiplier
NODE_SIZE_SLIDER_MAX = 200  # 2.0x multiplier
NODE_SIZE_SLIDER_DEFAULT = 100  # 1.0x multiplier

# Node label size slider settings
NODE_LABEL_SIZE_SLIDER_MIN = 50  # 0.5x multiplier
NODE_LABEL_SIZE_SLIDER_MAX = 200  # 2.0x multiplier
NODE_LABEL_SIZE_SLIDER_DEFAULT = 140  # 1.4x multiplier

# Node size adjustment via keyboard (Up/Down when node selected)
NODE_SIZE_KEYBOARD_INCREMENT = 0.2  # Change per keypress
NODE_SIZE_MIN = 0.2  # Minimum node size multiplier
NODE_SIZE_MAX = 3.0  # Maximum node size multiplier

# Node label size adjustment via keyboard (Left/Right when node selected)
NODE_LABEL_SIZE_KEYBOARD_INCREMENT = 0.2  # Change per keypress
NODE_LABEL_SIZE_MIN = 0.2  # Minimum label size multiplier
NODE_LABEL_SIZE_MAX = 3.0  # Maximum label size multiplier

# =============================================================================
# EDGE APPEARANCE DEFAULTS
# =============================================================================

# Default edge properties
DEFAULT_EDGE_LINEWIDTH_MULT = 1.5  # Medium linewidth
DEFAULT_EDGE_LABEL_SIZE_MULT = 1.0
DEFAULT_EDGE_LABEL_OFFSET_MULT = 1.0
DEFAULT_EDGE_STYLE = 'single'  # or 'double', 'loopy'
DEFAULT_EDGE_DIRECTION = 'both'  # or 'forward', 'backward'
DEFAULT_EDGE_FLIP_LABELS = False

# Edge linewidth options
EDGE_LINEWIDTH_OPTIONS = {
    'Thin': 1.0,
    'Medium': 1.25,
    'Thick': 1.5,
    'X-Thick': 2.0
}
DEFAULT_EDGE_LINEWIDTH_NAME = 'Medium'

# =============================================================================
# SELF-LOOP APPEARANCE DEFAULTS
# =============================================================================

# Self-loop specific defaults
DEFAULT_SELFLOOP_ANGLE = 90  # degrees (90° = Up)
DEFAULT_SELFLOOP_SCALE = 1.0  # Medium
DEFAULT_SELFLOOP_FLIP = False
DEFAULT_SELFLOOP_ARROWLENGTH = 1.0

# Self-loop scale options
SELFLOOP_SCALE_OPTIONS = {
    'Small (0.7x)': 0.7,
    'Medium (1.0x)': 1.0,
    'Large (1.3x)': 1.3,
    'X-Large (1.6x)': 1.6
}
DEFAULT_SELFLOOP_SCALE_NAME = 'Medium (1.0x)'

# Self-loop angle options (degrees)
SELFLOOP_ANGLE_OPTIONS = [
    ('0° (Right)', 0),
    ('45° (Up-Right)', 45),
    ('90° (Up)', 90),
    ('135° (Up-Left)', 135),
    ('180° (Left)', 180),
    ('225° (Down-Left)', 225),
    ('270° (Down)', 270),
    ('315° (Down-Right)', 315)
]

# Self-loop adjustment via keyboard (Ctrl+Up/Down when self-loop selected)
SELFLOOP_SCALE_KEYBOARD_PERCENT = 0.20  # 20% of current value per keypress
SELFLOOP_LINEWIDTH_KEYBOARD_PERCENT = 0.20  # 20% of current value per keypress
SELFLOOP_LINEWIDTH_MIN = 0.2
SELFLOOP_LINEWIDTH_MAX = 8.0

# Self-loop angle adjustment via keyboard (Ctrl+Left/Right when self-loop selected)
SELFLOOP_ANGLE_KEYBOARD_INCREMENT = 15  # degrees per keypress (must be multiple of 5)

# Auto-adjust self-loop angle to avoid overlapping with existing edges
AUTO_ADJUST_SELFLOOP_ANGLE = True  # When True, new self-loops auto-orient away from edges

# =============================================================================
# REGULAR EDGE SPECIFIC DEFAULTS
# =============================================================================

# Loop theta for regular edges (curvature parameter)
DEFAULT_EDGE_LOOPTHETA = 30  # degrees
EDGE_LOOPTHETA_MIN = -180  # degrees
EDGE_LOOPTHETA_MAX = 180  # degrees

# Edge looptheta adjustment via keyboard (Ctrl+Left/Right when regular edge selected)
EDGE_LOOPTHETA_KEYBOARD_INCREMENT = 15  # degrees per keypress

# =============================================================================
# SCATTERING PARAMETER DEFAULTS
# =============================================================================

# NODE PARAMETER DEFAULTS---------------------------
# Default values for node scattering parameters (when not assigned by user)
DEFAULT_NODE_FREQ = 6.0  # arb. units
DEFAULT_NODE_B_INT = 0.0  # milliarb. units (display value)
DEFAULT_NODE_B_EXT = 100.0  # milliarb. units (display value)

# Frequency spinbox settings
FREQ_SPINBOX_MIN = 0.0
FREQ_SPINBOX_MAX = 1e6
FREQ_SPINBOX_DECIMALS = 3
FREQ_SPINBOX_STEP = 0.1
FREQ_SPINBOX_WIDTH = 65  # pixels

# B_int spinbox settings
B_INT_SPINBOX_MIN = 0.0
B_INT_SPINBOX_MAX = 1e6
B_INT_SPINBOX_DECIMALS = 3
B_INT_SPINBOX_STEP = 1.0
B_INT_SPINBOX_WIDTH = 65  # pixels

# B_ext spinbox settings
B_EXT_SPINBOX_MIN = 0.0
B_EXT_SPINBOX_MAX = 1e6
B_EXT_SPINBOX_DECIMALS = 2
B_EXT_SPINBOX_STEP = 1.0
B_EXT_SPINBOX_WIDTH = 65  # pixels

# EDGE PARAMETER DEFAULTS---------------------------
# Default values for tree edge scattering parameters (when not assigned by user)
DEFAULT_EDGE_F_P = 0.0  # arb. units
DEFAULT_EDGE_RATE = 1.0  # milliarb. units (display value)
DEFAULT_EDGE_PHASE = 0.0  # degrees
# Edge f_p spinbox settings
F_P_SPINBOX_MIN = 0.0
F_P_SPINBOX_MAX = 1e6
F_P_SPINBOX_DECIMALS = 3
F_P_SPINBOX_STEP = 0.1
F_P_SPINBOX_WIDTH = 65  # pixels

# Edge rate spinbox settings (if used)
RATE_SPINBOX_MIN = 0.0
RATE_SPINBOX_MAX = 1e6
RATE_SPINBOX_DECIMALS = 2
RATE_SPINBOX_STEP = 1.0
RATE_SPINBOX_WIDTH = 65  # pixels

# Edge phase spinbox settings (if used)
PHASE_SPINBOX_MIN = -360.0
PHASE_SPINBOX_MAX = 360.0
PHASE_SPINBOX_DECIMALS = 1
PHASE_SPINBOX_STEP = 5.0
PHASE_SPINBOX_WIDTH = 65  # pixels

# =============================================================================
# FREQUENCY ARRAY SETTINGS
# =============================================================================
# For setting the signal frequency array
# Frequency center spinbox
FREQ_CENTER_MIN = 0.0
FREQ_CENTER_MAX = 1e6
FREQ_CENTER_DECIMALS = 2
FREQ_CENTER_STEP = 0.1
FREQ_CENTER_DEFAULT = 6.00 # GHz

# Frequency span spinbox
FREQ_SPAN_MIN = 0.01
FREQ_SPAN_MAX = 1e6
FREQ_SPAN_DECIMALS = 2
FREQ_SPAN_STEP = 0.1
FREQ_SPAN_DEFAULT = 2.0  # GHz

# Frequency points spinbox
FREQ_POINTS_MIN = 2
FREQ_POINTS_MAX = 10000
FREQ_POINTS_DECIMALS = 0
FREQ_POINTS_DEFAULT = 801

# =============================================================================
# EXPORT RESCALE PARAMETERS
# =============================================================================

# Default export rescale values
EXPORT_RESCALE_DEFAULTS = {
    'NODELABELSCALE': 1.000,
    'SLCC': 0.650,  # Self-loop center correction
    'SELFLOOP_LABELSCALE': 0.140,
    'SLLW': 6.000,  # Self-loop linewidth
    'SLSC': 0.900,  # Self-loop scale
    'SLLNOFFSET': (0.0, 0.0),  # Self-loop label nudge offset
    'SELFLOOP_LABELNUDGE_SCALE': 1.000,
    'EDGEFONTSCALE': 0.850,
    'EDGELWSCALE': 2.700,
    'EDGELABELOFFSET': 1.000,
    'GUI_SELFLOOP_LABEL_SCALE': 1.300,
    'EXPORT_SELFLOOP_LABEL_DISTANCE': 1.000,
}

# Export rescale parameter ranges (for spinbox UI)
EXPORT_RESCALE_RANGES = {
    'GUI_SELFLOOP_LABEL_SCALE': (0.1, 5.0, 0.1),  # (min, max, step)
    'EXPORT_SELFLOOP_LABEL_DISTANCE': (0.1, 5.0, 0.1),
    'NODELABELSCALE': (0.1, 2.0, 0.05),
    'SELFLOOP_LABELSCALE': (0.1, 2.0, 0.05),
    'SLLW': (0.1, 8.0, 0.1),
    'SLSC': (0.1, 3.0, 0.1),
    'SELFLOOP_LABELNUDGE_SCALE': (0.1, 3.0, 0.1),
    'EDGEFONTSCALE': (0.1, 5.0, 0.1),
    'EDGELWSCALE': (0.1, 5.0, 0.1),
    'EDGELABELOFFSET': (0.1, 3.0, 0.05),
}

# =============================================================================
# GRID SETTINGS
# =============================================================================

# Grid defaults
DEFAULT_GRID_SPACING = 1.0
DEFAULT_GRID_TYPE = "square"  # "square" or "triangular"

# Grid rotation increments (degrees)
SQUARE_GRID_ROTATION_INCREMENT = 45
TRIANGULAR_GRID_ROTATION_INCREMENT = 30

# =============================================================================
# VIEW AND NAVIGATION SETTINGS
# =============================================================================

# View defaults
DEFAULT_XLIM = (-10, 10)
DEFAULT_YLIM = (-10, 10)
DEFAULT_FIGURE_SIZE = (12, 12)

# Pan settings
PAN_FRACTION = 0.10  # Pan by 10% of current view width/height

# Zoom settings
ZOOM_KEYBOARD_FACTOR = 1.2
ZOOM_SCROLL_FACTOR = 1.15
AUTOFIT_PADDING_FACTOR = 1.5

# Rotation settings
NODE_ROTATION_KEYBOARD_INCREMENT = 15  # degrees per Ctrl+U (CCW) or Ctrl+I (CW)

# Label nudge settings
LABEL_NUDGE_INCREMENT = 0.05  # grid units per Shift+Arrow keypress

# =============================================================================
# DIALOG AND WIDGET SETTINGS
# =============================================================================

# Node input dialog size
NODE_DIALOG_WIDTH = 350
NODE_DIALOG_HEIGHT = 230

# Spinbox label width for consistency
SPINBOX_LABEL_MIN_WIDTH = 60  # pixels for multiplier labels like "1.234x"

# =============================================================================
# PLOTTING APPEARANCE PARAMETERS
# =============================================================================

# Main graph plotting (calibrated for figsize=12)
PLOT_NODE_LABEL_FONT_SCALE = 0.35  # Font size as fraction of node diameter in points
PLOT_EDGE_LABEL_BASE_FONTSIZE = 20  # Base font size for edge labels
PLOT_SELECTION_RING_SCALE = 1.3  # Selected node ring radius multiplier
PLOT_SELECTION_LINEWIDTH_SCALE = 0.04  # Selection ring line width as fraction of node diameter
PLOT_INVALID_RING_SCALE = 1.35  # Invalid node ring radius multiplier (red)
PLOT_INVALID_LINEWIDTH_SCALE = 0.05  # Invalid ring line width as fraction of node diameter
PLOT_BASIS_RING_SCALE = 1.4  # Basis node ring radius multiplier (green/purple)
PLOT_BASIS_LINEWIDTH_SCALE = 0.05  # Basis ring line width as fraction of node diameter

# Scattering plot appearance (uses seaborn 'talk' context)
SPARAMS_PLOT_LINEWIDTH = 2.0  # Line width for S-parameter traces
SPARAMS_PLOT_GRID_LINEWIDTH_SCALE = 0.6  # Grid line width relative to talk context
SPARAMS_PLOT_BACKGROUND_COLOR = '#EAEAF2'  # Light gray background
SPARAMS_PLOT_GRID_COLOR = 'white'  # Grid line color
SPARAMS_PLOT_FIGURE_BACKGROUND = 'white'  # Figure background color
SPARAMS_FONT_SCALE = 0.8  # Master scale for ALL plot fonts (axis labels, ticks, legend, port labels)
SPARAMS_LEGEND_FONTSIZE_SCALE = 0.8  # Additional legend scale (multiplied with SPARAMS_FONT_SCALE)

# S-parameter plot margins (figure coordinates, 0.0-1.0)
# Single frequency group (diagonal S_jj only, same frequencies)
SPARAMS_MARGIN_BOTTOM_SINGLE = 0.15  # Bottom margin for single freq group
SPARAMS_MARGIN_LEFT_SINGLE = 0.15  # Left margin for single freq group
# Multiple frequency groups (off-diagonal or different freq arrays)
SPARAMS_MARGIN_BOTTOM_BASE = 0.05  # Base bottom margin before adding rows
SPARAMS_MARGIN_BOTTOM_PER_ROW = 0.065  # Additional margin per frequency row
SPARAMS_MARGIN_BOTTOM_XLABEL = 0.05  # Extra margin for x-axis label
SPARAMS_MARGIN_LEFT_MULTI = 0.16  # Left margin when showing port labels
# Frequency row positioning
# SPARAMS_FREQ_ROW_Y_START = -0.08  # Y position of first frequency row (axes coords)
# SPARAMS_FREQ_ROW_Y_SPACING = 0.065  # Vertical spacing between rows
SPARAMS_FREQ_ROW_Y_START = -0.03  # Y position of first frequency row (axes coords)
SPARAMS_FREQ_ROW_Y_SPACING = 0.03  # Vertical spacing between rows
# SPARAMS_PORT_LABEL_X = -0.08  # X position of port labels (axes coords)
# SPARAMS_XLABEL_Y_OFFSET = -0.04  # Additional offset for x-axis label below freq rows
SPARAMS_PORT_LABEL_X = -0.03  # X position of port labels (axes coords)
SPARAMS_XLABEL_Y_OFFSET = -0.0  # Additional offset for x-axis label below freq rows

# S-parameter plot mode and phase settings
SPARAMS_PLOT_MODE_DEFAULT = 'dB'  # Default plot mode: 'dB', 'phase', or 'both'
SPARAMS_PHASE_YMIN_DEFAULT = -180.0  # Default phase y-axis minimum (degrees)
SPARAMS_PHASE_YMAX_DEFAULT = 180.0   # Default phase y-axis maximum (degrees)
SPARAMS_PHASE_UNWRAP_DEFAULT = False  # Default unwrap setting for phase display

# S-parameter trace color palette (independent from node colors)
SPARAMS_TRACE_COLORS = [
    'indianred',
    'cornflowerblue',
    'darkseagreen',
    'sandybrown',
    'mediumpurple',
    'mediumaquamarine',
    'gray',
]

# Constraint group colors (RGBA tuples for spinbox background tinting)
CONSTRAINT_GROUP_COLORS = [
    (255, 100, 100, 60),   # Red
    (100, 100, 255, 60),   # Blue
    (100, 200, 100, 60),   # Green
    (255, 180, 100, 60),   # Orange
    (180, 100, 255, 60),   # Purple
    (100, 200, 200, 60),   # Cyan
]

# Export code generation (for figsize=12)
EXPORT_EDGE_LABEL_BASE_FONTSIZE = 20.0  # Base font size for edge labels in exported code (50 * 0.4)

# =============================================================================
# GRAPH PLACEMENT DEFAULTS
# =============================================================================

# Auto-increment mode settings
AUTO_INCREMENT_ENABLED = False  # Start in normal mode
AUTO_INCREMENT_START_LETTER = 'A'  # Starting label for auto-increment
AUTO_INCREMENT_START_NUMBER = 0  # Starting number for numeric auto-increment

# =============================================================================
# PERFORMANCE AND DISPLAY SETTINGS
# =============================================================================

# Auto-recalculate scattering parameters on value change
AUTO_RECALCULATE_SPARAMS = True

# Highlight duration for parameter changes
PARAM_HIGHLIGHT_DURATION_MS = 800  # milliseconds

# Matrix display zoom increments
MATRIX_ZOOM_INCREMENT = 0.25  # 25% zoom in/out per button click
BASIS_ZOOM_INCREMENT = 0.25  # 25% zoom in/out per button click

# =============================================================================
# UNITS AND CONVERSIONS
# =============================================================================

# Scattering parameter units
# Internal storage: arbitrary units (arb. units)
# Display: milliarbitrary units (millarb. units)
# Conversion factor: 1 arb. unit = 1000 millarb. units
SCATTERING_DISPLAY_UNIT_FACTOR = 1000.0

# Frequency units
FREQUENCY_UNIT = "GHz"  # Display unit for frequencies

# =============================================================================
# FILE FORMAT SETTINGS
# =============================================================================

# pgraph file format version
PGRAPH_FORMAT_VERSION = "2.0"
PGRAPH_FORMAT_NAME = "pgraph"

# Precision for saving numeric values
SAVE_NUMERIC_PRECISION = 9  # decimal places for rounding
