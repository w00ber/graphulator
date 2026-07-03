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
        # Simulate stale dialog memory from prior node/edge placements
        gq.NodeInputDialog.last_color = 'BLUE'
        gq.EdgeInputDialog.last_style = 'loopy'
        win.last_node_props = {'label': 'C', 'color_key': 'BLUE'}
        win.last_edge_props = {'style': 'loopy'}

        dialog._set_widget_value('DEFAULT_NODE_COLOR_KEY', 'GREEN')
        dialog._set_widget_value('DEFAULT_EDGE_STYLE', 'double')
        dialog._on_apply()
        assert config.DEFAULT_NODE_COLOR_KEY == 'GREEN'
        assert config.DEFAULT_NODE_COLOR == config.MYCOLORS['GREEN']
        assert gq.NodeInputDialog.last_color == 'GREEN'
        assert gq.EdgeInputDialog.last_style == 'double'
        assert win.last_node_props is None  # duplicate template rebuilds from config
        assert win.last_edge_props is None  # continuous-edge template too

        # Reset must resync the same way (back to the code defaults)
        gq.NodeInputDialog.last_color = 'BLUE'
        win.last_node_props = {'label': 'C', 'color_key': 'BLUE'}
        with mock.patch("graphulator.settings_dialog.QMessageBox"):
            dialog._on_reset_defaults()
        assert config.DEFAULT_NODE_COLOR_KEY == original_key
        assert gq.NodeInputDialog.last_color == original_key
        assert gq.EdgeInputDialog.last_style == 'loopy'  # code default
        assert win.last_node_props is None
    finally:
        config.DEFAULT_NODE_COLOR_KEY = original_key
        config.DEFAULT_NODE_COLOR = config.MYCOLORS[original_key]
        config.DEFAULT_EDGE_STYLE = 'loopy'
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


def test_sample_scene_labels_use_app_mathtext_convention(qt_window, settings_tmp):
    """Preview labels render with the apps' bold sans-serif mathtext."""
    from matplotlib.figure import Figure

    gq, _win = qt_window
    from graphulator.settings_dialog import make_style_sample_scene
    draw = make_style_sample_scene(gq.config)
    fig = Figure()
    ax = fig.add_subplot()
    draw(ax, {})
    texts = [t.get_text() for t in ax.texts]
    assert any(r'\mathsf' in t and t.startswith('$') for t in texts)
    assert any(r'\ast' in t for t in texts)  # conjugated sample label


def test_sample_scene_previews_default_edge_style(qt_window, settings_tmp):
    """The qt preview honors the pending DEFAULT_EDGE_STYLE value."""
    import matplotlib.patches as mpatches
    from matplotlib.figure import Figure

    gq, _win = qt_window
    from graphulator.settings_dialog import make_style_sample_scene
    draw = make_style_sample_scene(gq.config)
    fig = Figure()
    ax = fig.add_subplot()
    draw(ax, {'DEFAULT_EDGE_STYLE': 'double'})
    # The double style draws a fat stroke plus a white overlay, both with
    # flush butt caps; the loopy default would draw no white path patch
    whites = [p for p in ax.patches
              if isinstance(p, mpatches.PathPatch)
              and p.get_edgecolor()[:3] == (1.0, 1.0, 1.0)]
    assert len(whites) == 1
    assert whites[0].get_capstyle() == 'butt'


def test_qt_dialog_exposes_edge_style_default(qt_window, settings_tmp):
    gq, win = qt_window
    dialog = gq.GraphulatorSettingsDialog(win)
    assert 'DEFAULT_EDGE_STYLE' in dialog._widgets


def test_sample_scene_scales_labels_with_label_size_mult(qt_window, settings_tmp):
    """The preview label size follows the node label scale setting."""
    from matplotlib.figure import Figure

    gq, _win = qt_window
    from graphulator.settings_dialog import make_style_sample_scene
    draw = make_style_sample_scene(gq.config)
    fig = Figure()
    sizes = {}
    for mult in (1.0, 2.0):
        ax = fig.add_subplot()
        draw(ax, {'DEFAULT_NODE_LABEL_SIZE_MULT': mult})
        # Node labels only (the edge label scales with its own setting)
        sizes[mult] = max(t.get_fontsize() for t in ax.texts
                          if r'\mathsf{A}' in t.get_text())
        fig.clear()
    assert sizes[2.0] == pytest.approx(2 * sizes[1.0])


def test_sample_scene_conjugated_modes(qt_window, settings_tmp):
    """The preview honors the conjugated fill mode and label-color choice."""
    import matplotlib.colors as mcolors
    import matplotlib.patches as mpatches
    from matplotlib.figure import Figure

    gq, _win = qt_window
    from graphulator.settings_dialog import make_style_sample_scene
    draw = make_style_sample_scene(gq.config)
    fig = Figure()

    # Custom fill + literal custom label color
    ax = fig.add_subplot()
    draw(ax, {'CONJ_NODE_FILL_MODE': 'custom',
              'CONJ_NODE_FILL_COLOR': 'navy',
              'CONJ_LABEL_COLOR_AUTO': False,
              'CONJ_LABEL_COLOR_MODE': 'custom',
              'CONJ_NODE_LABEL_COLOR': 'yellow'})
    fills = [p for p in ax.patches if isinstance(p, mpatches.Circle)
             and p.get_facecolor()[:3] == mcolors.to_rgb('navy')]
    assert len(fills) == 1  # the conjugated sample node
    conj_texts = [t for t in ax.texts if r'\ast' in t.get_text()]
    assert conj_texts and conj_texts[0].get_color() == 'yellow'

    # Hollow + auto: label derives the node color so it never vanishes
    fig.clear()
    ax = fig.add_subplot()
    draw(ax, {'CONJ_NODE_FILL_MODE': 'transparent',
              'CONJ_LABEL_COLOR_AUTO': True,
              'DEFAULT_NODE_COLOR_KEY': 'GREEN'})
    conj_texts = [t for t in ax.texts if r'\ast' in t.get_text()]
    assert conj_texts[0].get_color() == gq.config.MYCOLORS['GREEN']


def test_qt_conjugated_modes_render_on_canvas(qt_window, settings_tmp):
    """Conjugated fill mode and label choice apply at draw time (live)."""
    import matplotlib.colors as mcolors
    import matplotlib.patches as mpatches

    gq, win = qt_window
    config = gq.config
    node = {'node_id': 0, 'label': 'A', 'pos': (0.0, 0.0),
            'color': 'indianred', 'color_key': 'RED',
            'node_size_mult': 1.0, 'label_size_mult': 1.4, 'conj': True}
    win.nodes = [node]
    win.edges = []
    try:
        # Custom fill mode
        config.CONJ_NODE_FILL_MODE = 'custom'
        config.CONJ_NODE_FILL_COLOR = 'navy'
        win._update_plot()
        circles = [p for p in win.canvas.ax.patches
                   if isinstance(p, mpatches.Circle)]
        assert any(c.get_facecolor()[:3] == mcolors.to_rgb('navy')
                   for c in circles if c.get_fill())

        # Hollow mode: unfilled ring in the node's own color (facecolor
        # 'none' -> fully transparent face)
        config.CONJ_NODE_FILL_MODE = 'transparent'
        win._update_plot()
        rings = [p for p in win.canvas.ax.patches
                 if isinstance(p, mpatches.Circle)
                 and p.get_facecolor()[3] == 0.0]
        assert any(c.get_edgecolor()[:3] == mcolors.to_rgb('indianred')
                   for c in rings)

        # Label resolver: auto follows the fill mode; literal choices win
        assert win._resolve_conj_label_color(node) == 'indianred'  # hollow+auto
        config.CONJ_LABEL_COLOR_AUTO = False
        config.CONJ_LABEL_COLOR_MODE = 'custom'
        config.CONJ_NODE_LABEL_COLOR = 'yellow'
        assert win._resolve_conj_label_color(node) == 'yellow'
        config.CONJ_LABEL_COLOR_MODE = 'node'
        assert win._resolve_conj_label_color(node) == 'indianred'
        config.CONJ_LABEL_COLOR_MODE = 'default'
        assert (win._resolve_conj_label_color(node)
                == config.DEFAULT_NODE_LABEL_COLOR)
    finally:
        config.CONJ_NODE_FILL_MODE = 'dimmed'
        config.CONJ_LABEL_COLOR_AUTO = True
        config.CONJ_LABEL_COLOR_MODE = 'default'
        win.nodes = []
        win._update_plot()


def test_conjugation_dependent_rows_enable(qt_window, settings_tmp):
    """Dependent settings rows activate with the controlling choices."""
    gq, win = qt_window
    dialog = gq.GraphulatorSettingsDialog(win)
    w = {name: dialog._widgets[name][0] for name in (
        'CONJ_NODE_FILL_ALPHA', 'CONJ_NODE_FILL_COLOR',
        'CONJ_LABEL_COLOR_MODE', 'CONJ_NODE_LABEL_COLOR')}
    # Defaults: dimmed fill + auto label
    assert w['CONJ_NODE_FILL_ALPHA'].isEnabled()
    assert not w['CONJ_NODE_FILL_COLOR'].isEnabled()
    assert not w['CONJ_LABEL_COLOR_MODE'].isEnabled()
    assert not w['CONJ_NODE_LABEL_COLOR'].isEnabled()

    dialog._set_widget_value('CONJ_NODE_FILL_MODE', 'custom')
    assert w['CONJ_NODE_FILL_COLOR'].isEnabled()
    assert not w['CONJ_NODE_FILL_ALPHA'].isEnabled()

    dialog._set_widget_value('CONJ_LABEL_COLOR_AUTO', True)  # no-op state
    dialog._widgets['CONJ_LABEL_COLOR_AUTO'][0].setChecked(False)
    assert w['CONJ_LABEL_COLOR_MODE'].isEnabled()
    assert not w['CONJ_NODE_LABEL_COLOR'].isEnabled()
    dialog._set_widget_value('CONJ_LABEL_COLOR_MODE', 'custom')
    assert w['CONJ_NODE_LABEL_COLOR'].isEnabled()

    dialog._on_cancel()  # revert any applied state


def _click(win, x, y):
    event = mock.Mock()
    event.inaxes = win.canvas.ax
    event.button = 1
    event.xdata, event.ydata = x, y
    win._on_click(event)


def test_edge_placement_without_dialog_carries_forward(qt_window, settings_tmp):
    """Placing an edge never opens a dialog; new edges inherit the last-used
    (or modified) edge properties."""
    gq, win = qt_window
    config = gq.config
    nodes = [{'node_id': i, 'label': lbl, 'pos': pos, 'color': 'indianred',
              'color_key': 'RED', 'node_size_mult': 1.0,
              'label_size_mult': 1.4, 'conj': False}
             for i, (lbl, pos) in enumerate(
                 (('A', (0.0, 0.0)), ('B', (4.0, 0.0)), ('C', (0.0, 4.0))))]
    original_mode = win.placement_mode
    win.nodes = nodes
    win.edges = []
    win.last_edge_props = None
    win.last_selfloop_props = None
    win.placement_mode = 'edge_continuous'
    win.edge_mode_first_node = None
    try:
        with mock.patch.object(gq.EdgeInputDialog, '__init__',
                               side_effect=AssertionError('dialog opened')):
            # First edge A->B: defaults (no dialog)
            _click(win, 0, 0)
            _click(win, 4, 0)
            assert len(win.edges) == 1
            assert win.edges[0]['style'] == config.DEFAULT_EDGE_STYLE
            assert win.edges[0]['label1'] == ''

            # Modify the placed edge's properties; next edge inherits them
            win.edges[0]['style'] = 'double'
            win.edges[0]['label1'] = 'g'
            win._remember_edge_props(win.edges[0])
            _click(win, 0, 0)
            _click(win, 0, 4)
            assert len(win.edges) == 2
            assert win.edges[1]['style'] == 'double'
            assert win.edges[1]['label1'] == 'g'

            # Self-loop placement uses its own template (also dialog-free)
            _click(win, 4, 0)
            _click(win, 4, 0)
            loops = [e for e in win.edges if e['is_self_loop']]
            assert len(loops) == 1
            assert loops[0]['style'] == 'loopy'
    finally:
        win.placement_mode = original_mode
        win.edge_mode_first_node = None
        win.nodes = []
        win.edges = []
        win.last_edge_props = None
        win.last_selfloop_props = None
        win._update_plot()


def test_qt_dialog_exposes_new_layout_defaults(qt_window, settings_tmp):
    gq, win = qt_window
    dialog = gq.GraphulatorSettingsDialog(win)
    for param in ('DEFAULT_NODE_LABEL_SIZE_MULT', 'DEFAULT_EDGE_LOOPTHETA',
                  'DEFAULT_EDGE_LABEL_SIZE_MULT',
                  'DEFAULT_EDGE_LABEL_OFFSET_MULT', 'DEFAULT_SELFLOOP_SCALE',
                  'DEFAULT_EDGE_LINEWIDTH_MULT',
                  'DEFAULT_SELFLOOP_LINEWIDTH_MULT'):
        assert param in dialog._widgets, param


def test_qt_layout_defaults_flow_to_placed_edges(qt_window, settings_tmp):
    """Looptheta, edge-label size/offset, and self-loop scale defaults reach
    newly placed edges after a settings change (sync clears templates)."""
    gq, win = qt_window
    config = gq.config
    originals = {k: getattr(config, k) for k in (
        'DEFAULT_EDGE_LOOPTHETA', 'DEFAULT_EDGE_LABEL_SIZE_MULT',
        'DEFAULT_EDGE_LABEL_OFFSET_MULT', 'DEFAULT_SELFLOOP_SCALE',
        'AUTO_ADJUST_SELFLOOP_ANGLE', 'DEFAULT_SELFLOOP_ANGLE',
        'DEFAULT_EDGE_LINEWIDTH_MULT', 'DEFAULT_SELFLOOP_LINEWIDTH_MULT')}
    nodes = [{'node_id': i, 'label': lbl, 'pos': pos, 'color': 'indianred',
              'color_key': 'RED', 'node_size_mult': 1.0,
              'label_size_mult': 1.4, 'conj': False}
             for i, (lbl, pos) in enumerate((('A', (0.0, 0.0)),
                                             ('B', (4.0, 0.0))))]
    original_mode = win.placement_mode
    win.nodes = nodes
    win.edges = []
    win.placement_mode = 'edge_continuous'
    win.edge_mode_first_node = None
    try:
        config.DEFAULT_EDGE_LOOPTHETA = 55
        config.DEFAULT_EDGE_LABEL_SIZE_MULT = 1.8
        config.DEFAULT_EDGE_LABEL_OFFSET_MULT = 1.2
        config.DEFAULT_SELFLOOP_SCALE = 1.3
        config.AUTO_ADJUST_SELFLOOP_ANGLE = False
        config.DEFAULT_SELFLOOP_ANGLE = 135
        config.DEFAULT_EDGE_LINEWIDTH_MULT = 2.0
        config.DEFAULT_SELFLOOP_LINEWIDTH_MULT = 2.5
        gq.sync_dialog_defaults_from_config(win)

        _click(win, 0, 0)
        _click(win, 4, 0)
        edge = win.edges[-1]
        assert edge['looptheta'] == 55
        assert edge['label_size_mult'] == pytest.approx(1.8)
        assert edge['label_offset_mult'] == pytest.approx(1.2)
        assert edge['linewidth_mult'] == pytest.approx(2.0)

        _click(win, 4, 0)
        _click(win, 4, 0)
        loop = [e for e in win.edges if e['is_self_loop']][-1]
        assert loop['selfloopscale'] == pytest.approx(1.3)
        assert loop['selfloopangle'] == 135  # auto-orient off -> the default
        assert loop['linewidth_mult'] == pytest.approx(2.5)
    finally:
        for k, v in originals.items():
            setattr(config, k, v)
        win.placement_mode = original_mode
        win.edge_mode_first_node = None
        win.nodes = []
        win.edges = []
        gq.sync_dialog_defaults_from_config(win)
        win._update_plot()
