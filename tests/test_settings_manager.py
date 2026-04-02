"""Tests for the SettingsManager module."""

import json
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from graphulator.para_core.settings_manager import SettingsManager


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

    def test_settings_file_path(self):
        """settings_file returns the expected path."""
        assert self.manager.settings_file.name == "settings.json"
        assert ".graphulator" in str(self.manager.settings_file)

    def test_save_and_load(self, tmp_path):
        """Settings can be saved and loaded."""
        settings_file = tmp_path / "settings.json"

        with mock.patch(
            "graphulator.para_core.settings_manager.USER_SETTINGS_FILE",
            settings_file,
        ), mock.patch(
            "graphulator.para_core.settings_manager.USER_SETTINGS_DIR",
            tmp_path,
        ):
            test_settings = {"key1": "value1", "key2": 42}
            assert self.manager.save(test_settings) is True
            assert settings_file.exists()

            # Verify file contents
            with open(settings_file) as f:
                saved = json.load(f)
            assert saved == test_settings

    def test_load_nonexistent_file(self, tmp_path):
        """Loading from non-existent file returns empty dict."""
        settings_file = tmp_path / "nonexistent.json"

        with mock.patch(
            "graphulator.para_core.settings_manager.USER_SETTINGS_FILE",
            settings_file,
        ):
            result = self.manager.load()
            assert result == {}

    def test_delete(self, tmp_path):
        """Delete removes the settings file."""
        settings_file = tmp_path / "settings.json"
        settings_file.write_text("{}")

        with mock.patch(
            "graphulator.para_core.settings_manager.USER_SETTINGS_FILE",
            settings_file,
        ):
            assert self.manager.delete() is True
            assert not settings_file.exists()

    def test_delete_nonexistent(self, tmp_path):
        """Delete on non-existent file succeeds."""
        settings_file = tmp_path / "nonexistent.json"

        with mock.patch(
            "graphulator.para_core.settings_manager.USER_SETTINGS_FILE",
            settings_file,
        ):
            assert self.manager.delete() is True

    def test_get_export_rescale_defaults(self, tmp_path):
        """get_export_rescale returns defaults when no saved settings."""
        settings_file = tmp_path / "nonexistent.json"
        defaults = {"NODELABELSCALE": 1.0, "SLCC": 0.65}

        with mock.patch(
            "graphulator.para_core.settings_manager.USER_SETTINGS_FILE",
            settings_file,
        ):
            result = self.manager.get_export_rescale(defaults)
            assert result == defaults

    def test_get_export_rescale_with_saved(self, tmp_path):
        """get_export_rescale merges saved values with defaults."""
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(json.dumps({"NODELABELSCALE": 2.0, "other": "ignored"}))
        defaults = {"NODELABELSCALE": 1.0, "SLCC": 0.65}

        with mock.patch(
            "graphulator.para_core.settings_manager.USER_SETTINGS_FILE",
            settings_file,
        ):
            result = self.manager.get_export_rescale(defaults)
            assert result["NODELABELSCALE"] == 2.0  # overridden
            assert result["SLCC"] == 0.65  # kept default

    def test_get_shortcuts_empty(self, tmp_path):
        """get_shortcuts returns empty dict when no saved shortcuts."""
        settings_file = tmp_path / "nonexistent.json"

        with mock.patch(
            "graphulator.para_core.settings_manager.USER_SETTINGS_FILE",
            settings_file,
        ):
            result = self.manager.get_shortcuts()
            assert result == {}
