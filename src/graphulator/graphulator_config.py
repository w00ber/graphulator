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
DEFAULT_NODE_COLOR = 'indianred'
DEFAULT_NODE_RADIUS = 0.6
DEFAULT_NODE_OUTLINE_COLOR = 'black'
DEFAULT_NODE_OUTLINE_WIDTH = 2.5
DEFAULT_NODE_LABEL_COLOR = 'white'
DEFAULT_NODE_LABEL_SIZE = 28

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
SELFLOOP_ANGLE_KEYBOARD_INCREMENT = 15  # degrees per keypress (must be multiple of 5)
AUTO_ADJUST_SELFLOOP_ANGLE = True  # When True, new self-loops auto-orient away from edges
DYNAMIC_ADJUST_SELFLOOP_ANGLE = True  # When True, unpinned self-loops reorient on drag-end
