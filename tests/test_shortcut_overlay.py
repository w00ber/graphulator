"""Tests for the context-sensitive keyboard-shortcut overlay (both apps).

Requires a working Qt platform; skips where the GUI can't start (run under
xvfb-run to include). Settings are redirected into tmp so real user settings
are never touched.
"""

import os
from unittest import mock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")


@pytest.fixture()
def settings_tmp(tmp_path):
    settings_file = tmp_path / "settings.json"
    with mock.patch(
        "graphulator.para_core.settings_manager.USER_SETTINGS_FILE", settings_file,
    ), mock.patch(
        "graphulator.para_core.settings_manager.USER_SETTINGS_DIR", tmp_path,
    ):
        yield settings_file


@pytest.fixture(scope="module")
def _app():
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        pytest.skip(f"GUI stack unavailable: {exc}")
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def qt_win(_app):
    try:
        import graphulator.graphulator_qt as gq
        win = gq.Graphulator()
    except Exception as exc:
        pytest.skip(f"Could not create Graphulator: {exc}")
    return gq, win


@pytest.fixture(scope="module")
def para_win(_app):
    try:
        import graphulator.graphulator_para as gp
        win = gp.Graphulator()
    except Exception as exc:
        pytest.skip(f"Could not create Paragraphulator: {exc}")
    return gp, win


NODE = {'node_id': 0, 'label': 'A', 'pos': (0.0, 0.0), 'color': 'indianred',
        'color_key': 'RED', 'node_size_mult': 1.0, 'label_size_mult': 1.4,
        'conj': False}


def _select(win, nodes=(), edges=()):
    win.selected_nodes = list(nodes)
    win.selected_edges = list(edges)


# ---- shared widget ---------------------------------------------------

def test_overlay_widget_hides_without_rows(_app):
    from PySide6.QtWidgets import QWidget

    from graphulator.shortcut_overlay import ShortcutOverlay
    host = QWidget()
    host.resize(400, 300)
    ov = ShortcutOverlay(host)
    ov.set_rows("Title", [])
    assert ov.isHidden()
    ov.set_rows("Title", [("G", "Add node")])
    ov.show()
    assert not ov.isHidden()
    # corner anchoring keeps it inside the host
    ov.set_corner("bottom-right")
    assert ov.x() >= 0 and ov.y() >= 0


# ---- context derivation (both apps share the mixin) ------------------

@pytest.mark.parametrize("nodes,edges,is_loop,expected", [
    ([], [], None, 'none'),
    ([NODE], [], None, 'node'),
    ([], [{'is_self_loop': False}], False, 'edge'),
    ([], [{'is_self_loop': True}], True, 'selfloop'),
    ([NODE], [{'is_self_loop': False}], None, 'none'),  # mixed -> none
])
def test_shortcut_context(qt_win, settings_tmp, nodes, edges, is_loop, expected):
    _gq, win = qt_win
    try:
        _select(win, nodes, edges)
        assert win._shortcut_context() == expected
    finally:
        _select(win)


# ---- Graphulator (static hints) --------------------------------------

def test_qt_overlay_parented_to_canvas_not_figure(qt_win, settings_tmp):
    _gq, win = qt_win
    ov = win._shortcut_overlay
    assert ov is not None
    # Parented to the Qt canvas widget => never part of matplotlib exports
    assert ov.parent() is win.canvas


def test_qt_overlay_off_by_default(qt_win, settings_tmp):
    _gq, win = qt_win
    assert win.APP_CONFIG.SHOW_SHORTCUT_OVERLAY is False


@pytest.mark.parametrize("context", ['none', 'node', 'edge', 'selfloop'])
def test_qt_hint_rows_present(qt_win, settings_tmp, context):
    _gq, win = qt_win
    rows = win._shortcut_hint_rows(context)
    assert rows and all(len(r) == 2 and r[0] and r[1] for r in rows)


def test_qt_toggle_shows_and_hides(qt_win, settings_tmp):
    _gq, win = qt_win
    ov = win._shortcut_overlay
    win._shortcut_overlay_on = False
    win._update_shortcut_overlay()
    assert ov.isHidden()
    win._toggle_shortcut_overlay()  # -> on
    assert not ov.isHidden()
    win._toggle_shortcut_overlay()  # -> off
    assert ov.isHidden()


# ---- Paragraphulator (live keys from ShortcutManager) ----------------

def test_para_overlay_parented_to_canvas(para_win, settings_tmp):
    _gp, win = para_win
    assert win._shortcut_overlay.parent() is win.original_canvas


@pytest.mark.parametrize("context", ['none', 'node', 'edge', 'selfloop'])
def test_para_hint_rows_resolve_keys(para_win, settings_tmp, context):
    _gp, win = para_win
    rows = win._shortcut_hint_rows(context)
    assert rows and all(r[0] and r[1] for r in rows)


def test_para_hints_reflect_remap(para_win, settings_tmp):
    _gp, win = para_win
    sm = win.shortcut_manager
    # Default '?' for the overlay toggle appears in the 'none' context
    rows = dict((label, keys) for keys, label in win._shortcut_hint_rows('none'))
    assert rows.get('Hide hints') == sm.get_key_sequence_display('overlay.toggle')
    # Remap it and confirm the overlay content follows
    original = sm.get_key_sequence('overlay.toggle')
    try:
        sm.set_key_sequence('overlay.toggle', 'F2')
        rows2 = dict((label, keys) for keys, label in win._shortcut_hint_rows('none'))
        assert rows2.get('Hide hints') == sm.get_key_sequence_display('overlay.toggle')
        assert rows2.get('Hide hints') != rows.get('Hide hints')
    finally:
        sm.set_key_sequence('overlay.toggle', original)


# ---- settings plumbing ----------------------------------------------

def test_settings_params_expose_overlay_rows():
    import graphulator.graphulator_config as gcfg
    from graphulator import graphulator_para as gp
    for table in (gcfg.SETTINGS_PARAMS, gp.SETTINGS_PARAMS):
        names = {row[0] for rows in table.values() for row in rows}
        assert 'SHOW_SHORTCUT_OVERLAY' in names
        assert 'SHORTCUT_OVERLAY_CORNER' in names
    # both live-apply so toggling is instant
    assert 'SHOW_SHORTCUT_OVERLAY' in gcfg.LIVE_PARAMS
    assert 'SHOW_SHORTCUT_OVERLAY' in gp.LIVE_PARAMS
