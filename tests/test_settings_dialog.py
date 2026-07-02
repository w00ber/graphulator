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


def test_para_preview_hidden_on_non_appearance_tabs(qt_window, settings_tmp):
    """The preview pane only shows on the appearance-related tabs in para."""
    try:
        import graphulator.graphulator_para as gp
        from graphulator.para_ui.settings_dialog import SettingsDialog
    except Exception as exc:
        pytest.skip(f"Could not import paragraphulator: {exc}")
    win = gp.Graphulator()
    dialog = SettingsDialog(win)
    appearance = {'Node & Edge Defaults', 'Conventions', 'Self-Loop Defaults'}
    seen = set()
    for i in range(dialog.tab_widget.count()):
        dialog.tab_widget.setCurrentIndex(i)
        name = dialog.tab_widget.tabText(i)
        seen.add(name)
        # isHidden reflects the explicit setVisible state even while the
        # dialog itself is not shown
        assert dialog._preview_box.isHidden() == (name not in appearance), name
    assert appearance <= seen  # the appearance tabs must actually exist


def test_qt_preview_shown_on_every_tab(qt_window, settings_tmp):
    """Graphulator passes no preview_tabs → the pane stays on all tabs."""
    gq, win = qt_window
    dialog = gq.GraphulatorSettingsDialog(win)
    for i in range(dialog.tab_widget.count()):
        dialog.tab_widget.setCurrentIndex(i)
        assert not dialog._preview_box.isHidden()


def test_qt_dialog_exposes_outline_defaults(qt_window, settings_tmp):
    gq, win = qt_window
    dialog = gq.GraphulatorSettingsDialog(win)
    for param in ('DEFAULT_NODE_OUTLINE_ENABLED', 'DEFAULT_NODE_OUTLINE_COLOR',
                  'DEFAULT_NODE_OUTLINE_WIDTH', 'DEFAULT_NODE_OUTLINE_ALPHA'):
        assert param in dialog._widgets, param


def test_new_qt_node_seeds_outline_fields(qt_window, settings_tmp):
    """A node placed on the canvas carries the configured outline defaults."""
    gq, win = qt_window
    config = gq.config
    original_enabled = config.DEFAULT_NODE_OUTLINE_ENABLED
    original_mode = win.placement_mode
    original_props = win.last_node_props
    n_before = len(win.nodes)
    try:
        config.DEFAULT_NODE_OUTLINE_ENABLED = True
        win.placement_mode = 'continuous_duplicate'
        win.last_node_props = {
            'label': 'Z', 'color': config.MYCOLORS['RED'], 'color_key': 'RED',
            'node_size_mult': 1.0, 'label_size_mult': 1.4, 'conj': False,
        }
        event = mock.Mock()
        event.inaxes = win.canvas.ax
        event.button = 1
        event.xdata, event.ydata = 7.0, 7.0
        win._on_click(event)
        assert len(win.nodes) == n_before + 1
        node = win.nodes[-1]
        assert node['outline_enabled'] is True
        assert node['outline_color'] == config.DEFAULT_NODE_OUTLINE_COLOR
        assert node['outline_width'] == config.DEFAULT_NODE_OUTLINE_WIDTH
        assert node['outline_alpha'] == config.DEFAULT_NODE_OUTLINE_ALPHA
    finally:
        config.DEFAULT_NODE_OUTLINE_ENABLED = original_enabled
        win.placement_mode = original_mode
        win.last_node_props = original_props
        win.nodes = win.nodes[:n_before]
        win._update_plot()


def test_apply_to_existing_covers_node_outlines(qt_window, settings_tmp):
    """Apply to Existing restyles node outlines and edges in one undo step."""
    gq, win = qt_window
    config = gq.config

    n1 = {'node_id': 0, 'label': 'A', 'pos': (0.0, 0.0), 'color': 'indianred',
          'color_key': 'RED', 'outline_enabled': False}
    n2 = {'node_id': 1, 'label': 'B', 'pos': (3.0, 0.0), 'color': 'cornflowerblue',
          'color_key': 'BLUE', 'outline_enabled': False}
    win.nodes = [n1, n2]
    win.edges = []
    win.undo_stack.clear()

    original_enabled = config.DEFAULT_NODE_OUTLINE_ENABLED
    dialog = gq.GraphulatorSettingsDialog(win)
    try:
        dialog._set_widget_value("DEFAULT_NODE_OUTLINE_ENABLED", True)
        with mock.patch("graphulator.graphulator_qt.QMessageBox") as mb:
            mb.question.return_value = mb.Yes
            dialog._on_apply_to_existing()
        assert all(n['outline_enabled'] for n in win.nodes)
        assert all(n['outline_color'] == config.DEFAULT_NODE_OUTLINE_COLOR
                   for n in win.nodes)
        assert len(win.undo_stack) == 1
        win._undo()
        assert not win.nodes[0]['outline_enabled']
    finally:
        config.DEFAULT_NODE_OUTLINE_ENABLED = original_enabled
        win.nodes = []
        win.edges = []


def test_apply_and_reset_resync_dialog_defaults(qt_window, settings_tmp):
    """Apply and Reset both push the changed defaults into dialog memory.

    New-node appearance flows through NodeInputDialog.last_* and
    window.last_node_props, not config lookups at creation time — the
    'Apply only works sporadically' bug was these never being resynced.
    """
    gq, win = qt_window
    config = gq.config
    original_key = config.DEFAULT_NODE_COLOR_KEY
    dialog = gq.GraphulatorSettingsDialog(win)
    try:
        # Simulate stale dialog memory from prior node placements
        gq.NodeInputDialog.last_color = 'BLUE'
        win.last_node_props = {'label': 'C', 'color_key': 'BLUE'}

        dialog._set_widget_value('DEFAULT_NODE_COLOR_KEY', 'GREEN')
        dialog._on_apply()
        assert config.DEFAULT_NODE_COLOR_KEY == 'GREEN'
        assert config.DEFAULT_NODE_COLOR == config.MYCOLORS['GREEN']
        assert gq.NodeInputDialog.last_color == 'GREEN'
        assert win.last_node_props is None  # duplicate template rebuilds from config

        # Reset must resync the same way (back to the code defaults)
        gq.NodeInputDialog.last_color = 'BLUE'
        win.last_node_props = {'label': 'C', 'color_key': 'BLUE'}
        with mock.patch("graphulator.settings_dialog.QMessageBox"):
            dialog._on_reset_defaults()
        assert config.DEFAULT_NODE_COLOR_KEY == original_key
        assert gq.NodeInputDialog.last_color == original_key
        assert win.last_node_props is None
    finally:
        config.DEFAULT_NODE_COLOR_KEY = original_key
        config.DEFAULT_NODE_COLOR = config.MYCOLORS[original_key]
        gq.sync_dialog_defaults_from_config(win)


def test_sample_scene_previews_radius_and_outline(qt_window, settings_tmp):
    """The preview scene reads pending radius/outline values, not config."""
    import matplotlib.patches as mpatches
    from matplotlib.figure import Figure

    gq, _win = qt_window
    from graphulator.settings_dialog import make_style_sample_scene
    draw = make_style_sample_scene(gq.config)
    fig = Figure()
    ax = fig.add_subplot()
    draw(ax, {'DEFAULT_NODE_RADIUS': 1.0,
              'DEFAULT_NODE_OUTLINE_ENABLED': True,
              'DEFAULT_NODE_OUTLINE_WIDTH': 4.0})
    circles = [p for p in ax.patches if isinstance(p, mpatches.Circle)]
    assert any(abs(c.radius - 1.0) < 1e-6 for c in circles)  # pending radius
    rings = [c for c in circles if not c.get_fill()]
    assert len(rings) >= 2  # outline on both sample nodes
    assert any(abs(c.get_linewidth() - 4.0) < 1e-6 for c in rings)

    # With outlines off, no unfilled ring circles are drawn
    ax2 = fig.add_subplot()
    draw(ax2, {'DEFAULT_NODE_RADIUS': 0.6,
               'DEFAULT_NODE_OUTLINE_ENABLED': False,
               'CONJ_NODE_FILL_MODE': 'dimmed'})
    circles2 = [p for p in ax2.patches if isinstance(p, mpatches.Circle)]
    assert not [c for c in circles2 if not c.get_fill()]
