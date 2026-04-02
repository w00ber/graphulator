"""
Settings manager for Graphulator.

Centralizes all settings loading, saving, and access into a single module.
Replaces the scattered settings I/O code that was previously spread across
graphulator_para.py and config modules.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from .. import graphulator_para_config as config

logger = logging.getLogger(__name__)

# User settings directory and file
USER_SETTINGS_DIR = Path.home() / '.graphulator'
USER_SETTINGS_FILE = USER_SETTINGS_DIR / 'settings.json'

# Recent files and last directory paths
RECENT_FILES_PATH = Path.home() / '.graphulator_recent'
LAST_GRAPH_PATH = Path.home() / '.graphulator_last.graph'
LAST_DIRECTORY_PATH = Path.home() / '.graphulator_last_dir'

# Maximum number of recent files to track
MAX_RECENT_FILES = 10


class SettingsManager:
    """Centralized settings management for Graphulator.

    Handles loading, saving, and accessing user settings from
    ~/.graphulator/settings.json. Consolidates settings I/O that was
    previously scattered across multiple locations.
    """

    def __init__(self):
        self._settings: Dict[str, Any] = {}
        self._export_rescale: Dict[str, Any] = {}
        self._shortcuts: Dict[str, str] = {}

    @property
    def settings_file(self) -> Path:
        return USER_SETTINGS_FILE

    @property
    def settings_dir(self) -> Path:
        return USER_SETTINGS_DIR

    def load(self) -> Dict[str, Any]:
        """Load user settings from disk and apply to config module.

        Returns the loaded settings dict (empty dict if no file or error).
        """
        if not USER_SETTINGS_FILE.exists():
            return {}

        try:
            with open(USER_SETTINGS_FILE, 'r') as f:
                self._settings = json.load(f)

            # Apply settings to config module
            for param_name, value in self._settings.items():
                if param_name == 'shortcuts':
                    self._shortcuts = value
                    continue
                if hasattr(config, param_name):
                    setattr(config, param_name, value)

            return self._settings
        except Exception as e:
            logger.warning("Could not load user settings: %s", e)
            return {}

    def save(self, settings_dict: Dict[str, Any]) -> bool:
        """Save settings to ~/.graphulator/settings.json.

        Returns True on success, False on failure.
        """
        try:
            USER_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
            with open(USER_SETTINGS_FILE, 'w') as f:
                json.dump(settings_dict, f, indent=2)
            self._settings = settings_dict
            return True
        except Exception as e:
            logger.warning("Could not save user settings: %s", e)
            return False

    def delete(self) -> bool:
        """Delete the user settings file to reset to defaults.

        Returns True on success, False on failure.
        """
        try:
            if USER_SETTINGS_FILE.exists():
                USER_SETTINGS_FILE.unlink()
            self._settings = {}
            return True
        except Exception as e:
            logger.warning("Could not delete user settings: %s", e)
            return False

    def get_export_rescale(self, defaults: Dict[str, Any]) -> Dict[str, Any]:
        """Get export rescale parameters, merging saved values with defaults.

        Args:
            defaults: Default export rescale parameter dict.

        Returns:
            Merged export rescale parameters.
        """
        result = defaults.copy()
        if USER_SETTINGS_FILE.exists():
            try:
                with open(USER_SETTINGS_FILE, 'r') as f:
                    saved = json.load(f)
                for key in result:
                    if key in saved:
                        result[key] = saved[key]
            except Exception:
                pass
        self._export_rescale = result
        return result

    def get_shortcuts(self) -> Dict[str, str]:
        """Get saved keyboard shortcut bindings."""
        if self._shortcuts:
            return self._shortcuts

        if USER_SETTINGS_FILE.exists():
            try:
                with open(USER_SETTINGS_FILE, 'r') as f:
                    saved = json.load(f)
                self._shortcuts = saved.get('shortcuts', {})
            except Exception:
                pass
        return self._shortcuts

    def get_original_config_value(self, param_name: str) -> Optional[Any]:
        """Get the original value from the config module (as defined in code).

        For export rescale params, checks the defaults dict in config.
        Otherwise gets directly from config module.
        """
        if param_name in config.EXPORT_RESCALE_DEFAULTS:
            return config.EXPORT_RESCALE_DEFAULTS[param_name]
        return getattr(config, param_name, None)


# Module-level singleton instance
_instance: Optional[SettingsManager] = None


def get_settings_manager() -> SettingsManager:
    """Get the singleton SettingsManager instance."""
    global _instance
    if _instance is None:
        _instance = SettingsManager()
    return _instance
