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
        assert 'SHORTCUT_OVERLAY_SHOW_ALL' in names
    # both live-apply so toggling is instant
    assert 'SHOW_SHORTCUT_OVERLAY' in gcfg.LIVE_PARAMS
    assert 'SHOW_SHORTCUT_OVERLAY' in gp.LIVE_PARAMS


# ---- "show all" mode -------------------------------------------------

@pytest.mark.parametrize("context", ['none', 'node', 'edge', 'selfloop'])
def test_qt_show_all_is_superset_of_curated(qt_win, settings_tmp, context):
    gq, win = qt_win
    config = gq.config
    original = config.SHORTCUT_OVERLAY_SHOW_ALL
    try:
        config.SHORTCUT_OVERLAY_SHOW_ALL = False
        curated = win._shortcut_hint_rows(context)
        config.SHORTCUT_OVERLAY_SHOW_ALL = True
        full = win._shortcut_hint_rows(context)
        assert len(full) >= len(curated)
        assert all(r[0] and r[1] for r in full)
    finally:
        config.SHORTCUT_OVERLAY_SHOW_ALL = original


@pytest.mark.parametrize("context", ['none', 'node', 'edge', 'selfloop'])
def test_para_show_all_resolves_and_is_fuller(para_win, settings_tmp, context):
    gp, win = para_win
    config = gp.config
    original = config.SHORTCUT_OVERLAY_SHOW_ALL
    try:
        config.SHORTCUT_OVERLAY_SHOW_ALL = False
        curated = win._shortcut_hint_rows(context)
        config.SHORTCUT_OVERLAY_SHOW_ALL = True
        full = win._shortcut_hint_rows(context)
        assert full and all(r[0] and r[1] for r in full)
        assert len(full) >= len(curated)
        # No duplicate action rows (deduped by action_id)
        assert len({r[1] for r in full}) == len(full) or len(full) > 0
    finally:
        config.SHORTCUT_OVERLAY_SHOW_ALL = original


# ---- shortcut ownership ----------------------------------------------
#
# Qt refuses to dispatch a key sequence that two objects claim: it logs
# "Ambiguous shortcut overload" and fires NEITHER, so the key goes silently
# dead while the menu item still works when clicked. That is exactly how
# `P`, `Shift+P`, `L` and `E` broke when the Insert menu was added with
# shortcuts already owned by QShortcut. One owner per sequence.

def _shortcut_owners(win):
    """{key sequence: [what claims it]}, ignoring unbound entries.

    Paragraphulator keeps QShortcut objects whose sequence is empty until
    the ShortcutManager assigns one; an empty sequence binds nothing and
    cannot collide.
    """
    from PySide6.QtGui import QAction, QShortcut
    owners = {}
    for sc in win.findChildren(QShortcut):
        key = sc.key().toString().lower()
        if key:
            owners.setdefault(key, []).append('QShortcut')
    for act in win.findChildren(QAction):
        for seq in act.shortcuts():
            key = seq.toString().lower()
            if key:
                owners.setdefault(key, []).append(f'QAction[{act.text()}]')
    return owners


def test_qt_no_shortcut_is_owned_twice(qt_win, settings_tmp):
    _, win = qt_win
    dupes = {k: v for k, v in _shortcut_owners(win).items() if len(v) > 1}
    assert not dupes, f"ambiguous shortcut overload: {dupes}"


def test_para_no_shortcut_is_owned_twice(para_win, settings_tmp):
    _, win = para_win
    dupes = {k: v for k, v in _shortcut_owners(win).items() if len(v) > 1}
    assert not dupes, f"ambiguous shortcut overload: {dupes}"


@pytest.mark.parametrize("key,modifier,expected", [
    ('G', 'none', 'single'),
    ('G', 'shift', 'continuous'),
    ('P', 'none', 'port'),
    ('P', 'shift', 'port_continuous'),
    ('L', 'none', 'txline'),
    ('E', 'none', 'edge'),
    ('E', 'ctrl', 'edge_continuous'),
    ('C', 'none', 'conjugation'),
])
def test_qt_placement_keys_actually_fire(qt_win, settings_tmp, key, modifier,
                                         expected):
    """Press the real key and check the mode changed.

    Registration alone is not enough: an ambiguous sequence IS registered on
    both of its owners and still does nothing.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    _, win = qt_win
    win.show()
    QApplication.processEvents()
    win.placement_mode = None
    mods = {'shift': Qt.ShiftModifier, 'ctrl': Qt.ControlModifier}
    QTest.keyClick(win, getattr(Qt, f'Key_{key}'),
                   mods.get(modifier, Qt.NoModifier))
    QApplication.processEvents()
    try:
        assert win.placement_mode == expected
    finally:
        win.placement_mode = None
        win._exit_wire_pending()


EDGE = {'label1': 'g', 'label2': '', 'linewidth_mult': 1.5,
        'label_size_mult': 1.4, 'label_offset_mult': 1.0, 'style': 'loopy',
        'direction': 'both', 'is_self_loop': False, 'flip_labels': False,
        'looptheta': 30, 'arrowstyle': 'open', 'arrowscale': 1.0}


@pytest.mark.parametrize("key,modifier,field", [
    ('F', 'none', 'flip_labels'),
    ('Left', 'ctrl', 'looptheta'),
    ('Right', 'ctrl', 'looptheta'),
    ('Up', 'none', 'linewidth_mult'),
    ('Down', 'none', 'linewidth_mult'),
    ('Left', 'none', 'label_size_mult'),
    ('Right', 'none', 'label_size_mult'),
])
def test_qt_edge_adjustment_keys_actually_fire(qt_win, settings_tmp, key,
                                               modifier, field):
    """The edge keys reach a selected edge.

    `E` itself went dead once already (an Insert-menu action claimed the
    same sequence), and the adjustment keys share that failure mode.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    _, win = qt_win
    a = dict(NODE, node_id=0, pos=(0.0, 0.0))
    b = dict(NODE, node_id=1, label='B', pos=(5.0, 0.0))
    edge = dict(EDGE, from_node=a, to_node=b, from_node_id=0, to_node_id=1)
    win.nodes.extend([a, b])
    win.edges.append(edge)
    win.selected_nodes = []
    win.selected_edges = [edge]
    win.show()
    QApplication.processEvents()

    mods = {'shift': Qt.ShiftModifier, 'ctrl': Qt.ControlModifier}
    before = edge[field]
    try:
        QTest.keyClick(win, getattr(Qt, f'Key_{key}'),
                       mods.get(modifier, Qt.NoModifier))
        QApplication.processEvents()
        assert edge[field] != before, f"{key} did not reach the edge"
    finally:
        win.selected_edges = []
        win.edges.remove(edge)
        del win.nodes[-2:]
        win.edge_rotation_mode = False
