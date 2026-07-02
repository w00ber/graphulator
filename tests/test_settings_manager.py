"""Tests for the SettingsManager module (per-app namespacing + migration)."""

import json
from unittest import mock

from graphulator.para_core.settings_manager import SettingsManager


def patched_paths(tmp_path):
    """Patch the module-level settings paths into a temp directory."""
    settings_file = tmp_path / "settings.json"
    return settings_file, mock.patch(
        "graphulator.para_core.settings_manager.USER_SETTINGS_FILE",
        settings_file,
    ), mock.patch(
        "graphulator.para_core.settings_manager.USER_SETTINGS_DIR",
        tmp_path,
    )


class TestSettingsManager:
    """Tests for SettingsManager."""

    def setup_method(self):
        """Create a fresh SettingsManager for each test."""
        self.manager = SettingsManager()

    def test_initial_state(self):
        """SettingsManager starts with empty settings."""
        assert self.manager._settings == {}
        assert self.manager._export_rescale == {}
        assert self.manager._shortcuts == {}
        assert self.manager.namespace == "paragraphulator"

    def test_settings_file_path(self):
        """settings_file returns the expected path."""
        assert self.manager.settings_file.name == "settings.json"
        assert ".graphulator" in str(self.manager.settings_file)

    def test_save_and_load(self, tmp_path):
        """Settings are saved under the app namespace and load back."""
        settings_file, patch_file, patch_dir = patched_paths(tmp_path)
        with patch_file, patch_dir:
            test_settings = {"key1": "value1", "key2": 42}
            assert self.manager.save(test_settings) is True
            assert settings_file.exists()

            with open(settings_file) as f:
                saved = json.load(f)
            assert saved == {"paragraphulator": test_settings}
            assert self.manager.load() == test_settings

    def test_load_nonexistent_file(self, tmp_path):
        """Loading from non-existent file returns empty dict."""
        _, patch_file, patch_dir = patched_paths(tmp_path)
        with patch_file, patch_dir:
            assert self.manager.load() == {}

    def test_delete(self, tmp_path):
        """Delete clears this namespace; the file goes when nothing remains."""
        settings_file, patch_file, patch_dir = patched_paths(tmp_path)
        settings_file.write_text(json.dumps({"paragraphulator": {"a": 1}}))
        with patch_file, patch_dir:
            assert self.manager.delete() is True
            assert not settings_file.exists()

    def test_delete_nonexistent(self, tmp_path):
        """Delete on non-existent file succeeds."""
        _, patch_file, patch_dir = patched_paths(tmp_path)
        with patch_file, patch_dir:
            assert self.manager.delete() is True

    def test_get_export_rescale_defaults(self, tmp_path):
        """get_export_rescale returns defaults when no saved settings."""
        _, patch_file, patch_dir = patched_paths(tmp_path)
        defaults = {"NODELABELSCALE": 1.0, "SLCC": 0.65}
        with patch_file, patch_dir:
            assert self.manager.get_export_rescale(defaults) == defaults

    def test_get_export_rescale_with_saved(self, tmp_path):
        """get_export_rescale merges namespaced saved values with defaults."""
        settings_file, patch_file, patch_dir = patched_paths(tmp_path)
        settings_file.write_text(json.dumps(
            {"paragraphulator": {"NODELABELSCALE": 2.0, "other": "ignored"}}))
        defaults = {"NODELABELSCALE": 1.0, "SLCC": 0.65}
        with patch_file, patch_dir:
            result = self.manager.get_export_rescale(defaults)
            assert result["NODELABELSCALE"] == 2.0  # overridden
            assert result["SLCC"] == 0.65  # kept default

    def test_get_shortcuts_empty(self, tmp_path):
        """get_shortcuts returns empty dict when no saved shortcuts."""
        _, patch_file, patch_dir = patched_paths(tmp_path)
        with patch_file, patch_dir:
            assert self.manager.get_shortcuts() == {}


class TestNamespacing:
    """Per-app namespace isolation and legacy migration."""

    def test_legacy_flat_file_migrates_to_paragraphulator(self, tmp_path):
        """A pre-namespacing flat file is wrapped and persisted once."""
        settings_file, patch_file, patch_dir = patched_paths(tmp_path)
        legacy = {"DEFAULT_NODE_RADIUS": 0.8, "shortcuts": {"edit.undo": "Ctrl+U"}}
        settings_file.write_text(json.dumps(legacy))
        with patch_file, patch_dir:
            manager = SettingsManager("paragraphulator")
            loaded = manager.load()
            assert loaded == legacy
            # File was rewritten in namespaced form
            with open(settings_file) as f:
                on_disk = json.load(f)
            assert on_disk == {"paragraphulator": legacy}
            # Migrated legacy shortcuts still retrievable
            assert manager.get_shortcuts() == {"edit.undo": "Ctrl+U"}

    def test_namespaces_do_not_clobber_each_other(self, tmp_path):
        """Saving one app's settings preserves the other's."""
        settings_file, patch_file, patch_dir = patched_paths(tmp_path)
        with patch_file, patch_dir:
            para = SettingsManager("paragraphulator")
            qt = SettingsManager("graphulator")
            assert para.save({"a": 1}) is True
            assert qt.save({"b": 2}) is True
            with open(settings_file) as f:
                on_disk = json.load(f)
            assert on_disk == {"paragraphulator": {"a": 1},
                               "graphulator": {"b": 2}}
            assert para.load() == {"a": 1}
            assert qt.load() == {"b": 2}

    def test_delete_clears_only_own_namespace(self, tmp_path):
        """Reset-to-defaults in one app must not nuke the other app."""
        settings_file, patch_file, patch_dir = patched_paths(tmp_path)
        settings_file.write_text(json.dumps(
            {"paragraphulator": {"a": 1}, "graphulator": {"b": 2}}))
        with patch_file, patch_dir:
            assert SettingsManager("paragraphulator").delete() is True
            with open(settings_file) as f:
                on_disk = json.load(f)
            assert on_disk == {"graphulator": {"b": 2}}

    def test_load_applies_to_injected_config_module(self, tmp_path):
        """A custom config module receives the overrides on load."""
        settings_file, patch_file, patch_dir = patched_paths(tmp_path)

        class FakeConfig:
            SOME_VALUE = 1

        settings_file.write_text(json.dumps({"graphulator": {"SOME_VALUE": 7}}))
        with patch_file, patch_dir:
            manager = SettingsManager("graphulator", config_module=FakeConfig)
            manager.load()
            assert FakeConfig.SOME_VALUE == 7

    def test_get_original_config_value_without_rescale_defaults(self, tmp_path):
        """Config modules without EXPORT_RESCALE_DEFAULTS fall through."""

        class FakeConfig:
            SOME_VALUE = 3

        manager = SettingsManager("graphulator", config_module=FakeConfig)
        assert manager.get_original_config_value("SOME_VALUE") == 3
        assert manager.get_original_config_value("MISSING") is None
