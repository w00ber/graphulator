"""App-level tests for the Settings dialogs.

Requires a working Qt platform; skips where the GUI can't start (run under
xvfb-run to include). The settings file is redirected into tmp so real user
settings are never touched.
"""

import json
import os
from unittest import mock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    # QtWebEngine refuses to sandbox as root (CI containers)
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")


@pytest.fixture()
def settings_tmp(tmp_path):
    """Redirect the settings file into tmp for the duration of a test."""
    settings_file = tmp_path / "settings.json"
    with mock.patch(
        "graphulator.para_core.settings_manager.USER_SETTINGS_FILE", settings_file,
    ), mock.patch(
        "graphulator.para_core.settings_manager.USER_SETTINGS_DIR", tmp_path,
    ):
        yield settings_file


@pytest.fixture(scope="module")
def qt_window():
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        pytest.skip(f"GUI stack unavailable: {exc}")
    _app = QApplication.instance() or QApplication([])  # keep the app alive
    try:
        import graphulator.graphulator_qt as gq
        win = gq.Graphulator()
    except Exception as exc:  # e.g. no usable Qt platform plugin
        pytest.skip(f"Could not create main window: {exc}")
    return gq, win


def test_dialog_apply_updates_config_and_new_edges(qt_window, settings_tmp):
    gq, win = qt_window
    config = gq.config
    original = config.DEFAULT_EDGE_ARROWSTYLE
    dialog = gq.GraphulatorSettingsDialog(win)
    try:
        dialog._set_widget_value("DEFAULT_EDGE_ARROWSTYLE", "filled")
        dialog._on_apply()
        assert config.DEFAULT_EDGE_ARROWSTYLE == "filled"
    finally:
        config.DEFAULT_EDGE_ARROWSTYLE = original


def test_dialog_cancel_reverts(qt_window, settings_tmp):
    gq, win = qt_window
    config = gq.config
    original = config.DEFAULT_EDGE_ARROWSCALE
    dialog = gq.GraphulatorSettingsDialog(win)
    dialog._set_widget_value("DEFAULT_EDGE_ARROWSCALE", original + 0.5)
    dialog._apply_all_values()
    assert config.DEFAULT_EDGE_ARROWSCALE == pytest.approx(original + 0.5)
    dialog._on_cancel()
    assert config.DEFAULT_EDGE_ARROWSCALE == pytest.approx(original)


def test_dialog_save_writes_graphulator_namespace(qt_window, settings_tmp):
    gq, win = qt_window
    dialog = gq.GraphulatorSettingsDialog(win)
    with mock.patch("graphulator.settings_dialog.QMessageBox"):
        dialog._on_save_defaults()
    on_disk = json.loads(settings_tmp.read_text())
    assert "graphulator" in on_disk
    assert "DEFAULT_EDGE_ARROWSTYLE" in on_disk["graphulator"]


def test_dialog_has_preview_pane(qt_window, settings_tmp):
    gq, win = qt_window
    dialog = gq.GraphulatorSettingsDialog(win)
    assert dialog._sample_canvas is not None
    dialog._refresh_sample()  # must not raise


def test_apply_to_existing_is_one_undo_step(qt_window, settings_tmp):
    gq, win = qt_window
    config = gq.config

    # Build a tiny graph directly
    n1 = {'node_id': 0, 'label': 'A', 'pos': (0.0, 0.0), 'color': 'indianred',
          'color_key': 'RED'}
    n2 = {'node_id': 1, 'label': 'B', 'pos': (3.0, 0.0), 'color': 'cornflowerblue',
          'color_key': 'BLUE'}
    edge = {'from_node': n1, 'to_node': n2, 'from_node_id': 0, 'to_node_id': 1,
            'label1': '', 'label2': '', 'linewidth_mult': 1.5,
            'label_size_mult': 1.0, 'style': 'loopy', 'direction': 'both',
            'is_self_loop': False, 'arrowstyle': 'open', 'arrowscale': 1.0}
    win.nodes = [n1, n2]
    win.edges = [edge]
    win.undo_stack.clear()

    original = config.DEFAULT_EDGE_ARROWSTYLE
    dialog = gq.GraphulatorSettingsDialog(win)
    try:
        dialog._set_widget_value("DEFAULT_EDGE_ARROWSTYLE", "stealth")
        with mock.patch("graphulator.graphulator_qt.QMessageBox") as mb:
            mb.question.return_value = mb.Yes
            mb.Yes = mb.question.return_value  # identity for the comparison
            dialog._on_apply_to_existing()
        assert win.edges[0]['arrowstyle'] == 'stealth'
        assert len(win.undo_stack) == 1
        win._undo()
        assert win.edges[0]['arrowstyle'] == 'open'
    finally:
        config.DEFAULT_EDGE_ARROWSTYLE = original
        win.nodes = []
        win.edges = []


def test_para_dialog_still_constructs(qt_window, settings_tmp):
    """The decoupled base must keep serving the para subclass."""
    try:
        import graphulator.graphulator_para as gp
        from graphulator.para_ui.settings_dialog import SettingsDialog
    except Exception as exc:
        pytest.skip(f"Could not import paragraphulator: {exc}")
    win = gp.Graphulator()
    dialog = SettingsDialog(win)
    tabs = [dialog.tab_widget.tabText(i) for i in range(dialog.tab_widget.count())]
    assert "Color Palettes" in tabs
