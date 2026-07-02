"""
Core data models and utilities for paragraphulator.
"""

from .interaction_state import InteractionMode, PlacementMode
from .settings_manager import SettingsManager, get_settings_manager

__all__ = [
    'SettingsManager',
    'get_settings_manager',
    'InteractionMode',
    'PlacementMode',
]
