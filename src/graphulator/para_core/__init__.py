"""
Core data models and utilities for paragraphulator.
"""

from .settings_manager import SettingsManager, get_settings_manager
from .interaction_state import InteractionMode, PlacementMode

__all__ = [
    'SettingsManager',
    'get_settings_manager',
    'InteractionMode',
    'PlacementMode',
]
