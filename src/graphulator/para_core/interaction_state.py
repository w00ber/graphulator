"""
Interaction state management for Graphulator.

Replaces the numerous boolean flags (basis_ordering_mode, kron_mode,
scattering_mode, etc.) with a clean enum-based state machine.
"""

from enum import Enum, auto


class InteractionMode(Enum):
    """Primary interaction modes for the graph editor.

    Only one mode can be active at a time. Each mode changes how
    mouse clicks and keyboard shortcuts are interpreted.
    """
    NORMAL = auto()
    BASIS_ORDERING = auto()
    KRON_REDUCTION = auto()
    SCATTERING = auto()


class PlacementMode(Enum):
    """Node/edge placement sub-modes.

    These are active within NORMAL interaction mode and control
    what happens when the user clicks on the canvas.
    """
    NONE = auto()
    SINGLE = auto()
    CONTINUOUS = auto()
    CONTINUOUS_DUPLICATE = auto()
    CONJUGATION = auto()
    EDGE = auto()
    EDGE_CONTINUOUS = auto()

    @classmethod
    def from_string(cls, s):
        """Convert legacy string placement mode to enum.

        Supports None and string values from the old code.
        """
        if s is None:
            return cls.NONE
        mapping = {
            'single': cls.SINGLE,
            'continuous': cls.CONTINUOUS,
            'continuous_duplicate': cls.CONTINUOUS_DUPLICATE,
            'conjugation': cls.CONJUGATION,
            'edge': cls.EDGE,
            'edge_continuous': cls.EDGE_CONTINUOUS,
        }
        return mapping.get(s, cls.NONE)

    def to_string(self):
        """Convert to legacy string format for backward compatibility."""
        if self == PlacementMode.NONE:
            return None
        return self.name.lower()
