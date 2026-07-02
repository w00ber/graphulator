"""Tests for the shared GraphWindowCommonMixin.

Both apps' main windows must inherit the shared behavior and parametrize it
correctly. Requires a working Qt platform; skips where the GUI can't start
(run under xvfb-run to include in CI-like environments).
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    # QtWebEngine refuses to sandbox as root (CI containers)
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")


@pytest.fixture(scope="module", params=["qt", "para"])
def app_window(request):
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        pytest.skip(f"GUI stack unavailable: {exc}")
    _app = QApplication.instance() or QApplication([])  # keep the app alive
    try:
        if request.param == "qt":
            import graphulator.graphulator_qt as mod
        else:
            import graphulator.graphulator_para as mod
        win = mod.Graphulator()
    except Exception as exc:  # e.g. no usable Qt platform plugin
        pytest.skip(f"Could not create main window: {exc}")
    return request.param, win


def test_inherits_mixin(app_window):
    from graphulator.common_window import GraphWindowCommonMixin
    _, win = app_window
    assert isinstance(win, GraphWindowCommonMixin)
    assert win.APP_CONFIG is not None


def test_app_parametrization(app_window):
    kind, win = app_window
    if kind == "qt":
        assert win.APP_NAME == "Graphulator"
        assert win.FILE_EXTENSION == ".graph"
    else:
        assert win.APP_NAME == "Paragraphulator"
        assert win.FILE_EXTENSION == ".pgraph"


def test_window_title(app_window):
    kind, win = app_window
    win.current_filepath = f"/tmp/foo{win.FILE_EXTENSION}"
    win._set_modified(True)
    win._update_window_title()
    assert win.windowTitle() == f"{win.APP_NAME} - foo{win.FILE_EXTENSION} *"
    win._set_modified(False)
    win.current_filepath = None


def test_recent_files(app_window):
    _, win = app_window
    win.recent_files = []
    win._add_to_recent_files("/tmp/a.graph")
    win._add_to_recent_files("/tmp/b.graph")
    win._add_to_recent_files("/tmp/a.graph")  # re-add moves to front, no dup
    assert win.recent_files[0] == "/tmp/a.graph"
    assert win.recent_files.count("/tmp/a.graph") == 1


def test_grid_toggles(app_window):
    _, win = app_window
    original = win.grid_type
    win._toggle_grid_type()
    assert win.grid_type != original
    win._toggle_grid_type()
    assert win.grid_type == original
    rotation = win.grid_rotation
    win._rotate_grid()
    assert win.grid_rotation != rotation


def test_empty_undo_redo_do_not_crash(app_window):
    _, win = app_window
    win.undo_stack.clear()
    win.redo_stack.clear()
    win._undo()
    win._redo()
