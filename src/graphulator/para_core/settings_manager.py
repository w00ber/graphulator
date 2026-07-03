"""
Settings manager for Graphulator and Paragraphulator.

Centralizes all settings loading, saving, and access into a single module.
Both applications persist their overrides to ~/.graphulator/settings.json,
namespaced per app::

    {
      "graphulator": { ... },
      "paragraphulator": { ... }
    }

Legacy flat files (written before namespacing) belonged to Paragraphulator —
the only app that had settings then — and are migrated in place on first read.
"""

import copy
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

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

# Per-app namespaces in the settings file. A file whose top-level keys are
# not a subset of these is a legacy flat (pre-namespacing) file.
KNOWN_NAMESPACES = ('graphulator', 'paragraphulator')


class SettingsManager:
    """Centralized settings management for one application namespace.

    Handles loading, saving, and accessing user settings from
    ~/.graphulator/settings.json. Each app reads and writes only its own
    namespace, so Graphulator and Paragraphulator defaults never collide.
    """

    def __init__(self, namespace: str = 'paragraphulator',
                 config_module=None):
        if config_module is None:
            # Historical default: this module predates namespacing and was
            # Paragraphulator-only.
            from .. import graphulator_para_config as config_module
        self.namespace = namespace
        self._config = config_module
        self._settings: Dict[str, Any] = {}
        self._export_rescale: Dict[str, Any] = {}
        self._shortcuts: Dict[str, str] = {}
        # Snapshot the as-coded constants before any override is applied so
        # "Reset to Defaults" can restore true code values even after the
        # config module has been mutated by load() or the Settings dialog.
        self._code_defaults: Dict[str, Any] = {}
        for name, value in vars(config_module).items():
            if name.isupper():
                try:
                    self._code_defaults[name] = copy.deepcopy(value)
                except Exception:
                    self._code_defaults[name] = value

    @property
    def settings_file(self) -> Path:
        return USER_SETTINGS_FILE

    @property
    def settings_dir(self) -> Path:
        return USER_SETTINGS_DIR

    # ---- Whole-file helpers (namespace-aware) ----

    def _read_all(self) -> Dict[str, Any]:
        """Read the whole settings file, migrating a legacy flat file.

        Legacy files (top-level keys not a subset of KNOWN_NAMESPACES) are
        wrapped as {"paragraphulator": <old dict>} and persisted once.
        """
        if not USER_SETTINGS_FILE.exists():
            return {}
        try:
            with open(USER_SETTINGS_FILE, 'r') as f:
                raw = json.load(f)
        except Exception as e:
            logger.warning("Could not read user settings: %s", e)
            return {}
        if not isinstance(raw, dict):
            logger.warning("Unexpected settings file format; ignoring")
            return {}
        if raw and not set(raw) <= set(KNOWN_NAMESPACES):
            raw = {'paragraphulator': raw}
            logger.info("Migrating legacy flat settings file to per-app namespaces")
            self._write_all(raw)
        return raw

    def _write_all(self, whole: Dict[str, Any]) -> bool:
        try:
            USER_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
            with open(USER_SETTINGS_FILE, 'w') as f:
                json.dump(whole, f, indent=2)
            return True
        except Exception as e:
            logger.warning("Could not save user settings: %s", e)
            return False

    # ---- Namespace-scoped API ----

    def load(self) -> Dict[str, Any]:
        """Load this app's settings from disk and apply to its config module.

        Returns the loaded settings dict (empty dict if no file or error).
        """
        self._settings = self._read_all().get(self.namespace, {})

        # Apply settings to the config module
        for param_name, value in self._settings.items():
            if param_name == 'shortcuts':
                self._shortcuts = value
                continue
            if hasattr(self._config, param_name):
                setattr(self._config, param_name, value)

        return self._settings

    def save(self, settings_dict: Dict[str, Any]) -> bool:
        """Save this app's settings under its namespace.

        Returns True on success, False on failure.
        """
        whole = self._read_all()
        whole[self.namespace] = settings_dict
        if self._write_all(whole):
            self._settings = settings_dict
            return True
        return False

    def delete(self) -> bool:
        """Reset this app to defaults by clearing only its namespace.

        The other app's settings are preserved; the file is removed only when
        no namespaces remain. Returns True on success, False on failure.
        """
        try:
            whole = self._read_all()
            whole.pop(self.namespace, None)
            self._settings = {}
            self._shortcuts = {}
            if whole:
                return self._write_all(whole)
            if USER_SETTINGS_FILE.exists():
                USER_SETTINGS_FILE.unlink()
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
        saved = self._read_all().get(self.namespace, {})
        for key in result:
            if key in saved:
                result[key] = saved[key]
        self._export_rescale = result
        return result

    def get_shortcuts(self) -> Dict[str, str]:
        """Get saved keyboard shortcut bindings."""
        if self._shortcuts:
            return self._shortcuts

        saved = self._read_all().get(self.namespace, {})
        self._shortcuts = saved.get('shortcuts', {})
        return self._shortcuts

    def get_original_config_value(self, param_name: str) -> Optional[Any]:
        """Get the original value from the config module (as defined in code).

        For export rescale params, checks the defaults dict in config (apps
        without one fall through to plain config attributes).
        """
        rescale_defaults = self._code_defaults.get(
            'EXPORT_RESCALE_DEFAULTS',
            getattr(self._config, 'EXPORT_RESCALE_DEFAULTS', {}))
        if param_name in rescale_defaults:
            return rescale_defaults[param_name]
        if param_name in self._code_defaults:
            return copy.deepcopy(self._code_defaults[param_name])
        return getattr(self._config, param_name, None)


# Per-namespace instances
_instances: Dict[str, SettingsManager] = {}


def get_settings_manager(namespace: str = 'paragraphulator',
                         config_module=None) -> SettingsManager:
    """Get the SettingsManager instance for an app namespace."""
    if namespace not in _instances:
        _instances[namespace] = SettingsManager(namespace, config_module)
    return _instances[namespace]
