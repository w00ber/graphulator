"""Two bits of export polish: a sticky setting, and an on-canvas notice.

The image-export scale used to revert on relaunch, because every setting in
the dialog only reached disk through "Save as Defaults" -- right for the
DEFAULTS of objects you place next, wrong for a tool preference. STICKY_PARAMS
names the ones that persist as soon as they are applied.

The canvas toast is the feedback for an export: the status bar is far from
where the eye is during a copy, and the scale is the number worth seeing at
the moment it is used. Headless (offscreen Qt + Agg).
"""

import json
import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    # QtWebEngine refuses to sandbox as root (CI containers)
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")


@pytest.fixture()
def quiet_dialogs(monkeypatch):
    """"Settings saved" popups would block a headless run."""
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, 'information',
                        staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, 'warning',
                        staticmethod(lambda *a, **k: None))


@pytest.fixture()
def win(tmp_path):
    """Graphulator."""
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    import graphulator.graphulator_qt as gq

    w = gq.Graphulator()
    w.last_graph_path = tmp_path / "last.graph"
    w.recent_files_path = tmp_path / "recent"
    return w


@pytest.fixture()
def para(tmp_path):
    """Paragraphulator."""
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    import graphulator.graphulator_para as gp

    w = gp.Graphulator()
    w.last_graph_path = tmp_path / "last.pgraph"
    w.recent_files_path = tmp_path / "recent"
    return w


def saved_settings(namespace):
    """This app's namespace as it stands on disk."""
    from graphulator.para_core import settings_manager

    path = settings_manager.USER_SETTINGS_FILE
    if not path.exists():
        return {}
    return json.load(open(path)).get(namespace, {})


def add_node(w, label, pos):
    node = {'node_id': w.node_id_counter, 'label': label, 'pos': pos,
            'color': '#6699ff', 'color_key': 'BLUE', 'node_size_mult': 1.0,
            'label_size_mult': 1.0, 'conj': False,
            'nodelabelnudge': (0.0, 0.0)}
    w.nodes.append(node)
    if hasattr(w, 'scattering_assignments'):
        w.scattering_assignments[node['node_id']] = {'freq': 5.0,
                                                     'B_int': 0.0}
    w.node_id_counter += 1
    return node


def scene(w):
    a = add_node(w, 'A', (0.0, 0.0))
    b = add_node(w, 'B', (4.0, 0.0))
    return a, b


# ---------------------------------------------------------------------------
# the sticky export scale
# ---------------------------------------------------------------------------

def test_the_export_scale_is_declared_sticky_in_both_apps():
    from graphulator import graphulator_config, graphulator_para_config

    for config in (graphulator_config, graphulator_para_config):
        assert 'IMAGE_EXPORT_SCALE' in config.STICKY_PARAMS


def test_ok_persists_the_export_scale(win, quiet_dialogs):
    import graphulator.graphulator_qt as gq

    dialog = gq.GraphulatorSettingsDialog(win)
    dialog._set_widget_value('IMAGE_EXPORT_SCALE', 2.5)
    dialog._on_ok()
    assert saved_settings('graphulator')['IMAGE_EXPORT_SCALE'] == 2.5


def test_apply_persists_the_export_scale(win, quiet_dialogs):
    import graphulator.graphulator_qt as gq

    dialog = gq.GraphulatorSettingsDialog(win)
    dialog._set_widget_value('IMAGE_EXPORT_SCALE', 0.5)
    dialog._on_apply()
    assert saved_settings('graphulator')['IMAGE_EXPORT_SCALE'] == 0.5


def test_an_ordinary_default_is_not_dragged_to_disk_with_it(win,
                                                            quiet_dialogs):
    """Only the sticky params go; everything else still waits for
    "Save as Defaults"."""
    import graphulator.graphulator_qt as gq

    dialog = gq.GraphulatorSettingsDialog(win)
    dialog._set_widget_value('IMAGE_EXPORT_SCALE', 2.0)
    dialog._set_widget_value('DEFAULT_NODE_RADIUS', 0.9)
    dialog._on_ok()
    assert sorted(saved_settings('graphulator')) == ['IMAGE_EXPORT_SCALE']


def test_cancel_unwinds_a_scale_an_earlier_apply_persisted(win,
                                                           quiet_dialogs):
    import graphulator.graphulator_qt as gq

    dialog = gq.GraphulatorSettingsDialog(win)
    dialog._set_widget_value('IMAGE_EXPORT_SCALE', 1.5)
    dialog._on_ok()

    again = gq.GraphulatorSettingsDialog(win)
    again._set_widget_value('IMAGE_EXPORT_SCALE', 4.0)
    again._on_apply()
    assert saved_settings('graphulator')['IMAGE_EXPORT_SCALE'] == 4.0
    again._on_cancel()
    assert saved_settings('graphulator')['IMAGE_EXPORT_SCALE'] == 1.5
    assert win.APP_CONFIG.IMAGE_EXPORT_SCALE == 1.5


def test_a_saved_scale_survives_a_restart(win, quiet_dialogs, monkeypatch):
    import graphulator.graphulator_qt as gq

    dialog = gq.GraphulatorSettingsDialog(win)
    dialog._set_widget_value('IMAGE_EXPORT_SCALE', 2.5)
    dialog._on_ok()

    monkeypatch.setattr(win.APP_CONFIG, 'IMAGE_EXPORT_SCALE', 1.0)
    restarted = gq.Graphulator()            # __init__ loads the settings
    assert restarted._image_export_scale() == 2.5


def test_the_scale_persists_in_para(para, quiet_dialogs):
    from graphulator.para_ui.settings_dialog import SettingsDialog

    dialog = SettingsDialog(para)
    dialog._set_widget_value('IMAGE_EXPORT_SCALE', 1.25)
    dialog._on_ok()
    assert saved_settings('paragraphulator')['IMAGE_EXPORT_SCALE'] == 1.25


def test_update_merges_rather_than_replacing():
    """The sticky write must not wipe settings saved earlier."""
    from graphulator.para_core.settings_manager import SettingsManager
    from graphulator import graphulator_config

    manager = SettingsManager('graphulator', config_module=graphulator_config)
    manager.save({'DEFAULT_NODE_RADIUS': 0.8})
    manager.update({'IMAGE_EXPORT_SCALE': 3.0})
    assert saved_settings('graphulator') == {'DEFAULT_NODE_RADIUS': 0.8,
                                             'IMAGE_EXPORT_SCALE': 3.0}


# ---------------------------------------------------------------------------
# the on-canvas export notice
# ---------------------------------------------------------------------------

@pytest.fixture()
def spy_copy(monkeypatch):
    """Run the whole export path but put nothing on the real clipboard."""
    from graphulator import clipboard_export

    monkeypatch.setattr(clipboard_export, 'copy_figure_to_clipboard',
                        lambda fig, **kw: ('spy', ['pdf']))


def toast_text(w):
    """The toast's rendered text, tags stripped."""
    return re.sub(r'<[^>]+>', ' ', w._canvas_toast._label.text())


def test_a_copy_flashes_a_notice_naming_the_scale(win, spy_copy, monkeypatch):
    monkeypatch.setattr(win.APP_CONFIG, 'IMAGE_EXPORT_SCALE', 1.0)
    scene(win)
    win._copy_graph_to_clipboard_vector()
    text = toast_text(win)
    assert 'Exported to paste buffer' in text
    assert '1× scale' in text


def test_the_notice_names_the_selection_and_the_size(win, spy_copy):
    a, b = scene(win)
    add_node(win, 'C', (40.0, 0.0))
    port = win.add_port(label='P1', pos=(-6.0, 0.0))
    win.connect_port_to_node(port, a)
    win.selected_nodes[:] = [a, b]
    win.selected_ports = [port]

    win._copy_graph_to_clipboard_vector()
    text = toast_text(win)
    assert 'Selection exported to paste buffer' in text
    assert '2 node(s) and 1 port(s)' in text
    assert re.search(r'\d+\.\d × \d+\.\d in', text), text


def test_the_notice_follows_the_multiplier(win, spy_copy, monkeypatch):
    scene(win)
    monkeypatch.setattr(win.APP_CONFIG, 'IMAGE_EXPORT_SCALE', 2.0)
    win._copy_graph_to_clipboard_vector()
    assert '2× scale' in toast_text(win)


def test_the_notice_is_shown_and_times_itself_out(win, spy_copy):
    scene(win)
    win._copy_graph_to_clipboard_vector()
    toast = win._canvas_toast
    # the window itself is never shown in a headless run, so ask relative
    # to the canvas rather than for absolute visibility
    assert toast.isVisibleTo(win.canvas)
    assert toast._timer.isActive()
    toast._timer.timeout.emit()
    assert not toast.isVisibleTo(win.canvas)


def test_the_notice_can_never_land_inside_the_export(win):
    """It is a Qt child of the canvas, not a figure artist -- the exports
    are rendered from the figure."""
    toast = win._canvas_toast
    assert toast.parentWidget() is win.canvas
    assert toast not in list(win.canvas.ax.get_children())
    assert toast not in list(win.canvas.fig.get_children())


def test_the_notice_steps_clear_of_the_shortcut_overlay(win, spy_copy):
    """Both want the top-right corner; they must not overlap."""
    win.canvas.resize(900, 700)
    # turn the overlay on for real: the export redraws, and a redraw hides
    # an overlay the session flag says is off
    win._shortcut_overlay_on = True
    win._update_shortcut_overlay()
    overlay = win._shortcut_overlay
    assert not overlay.isHidden(), "the overlay has to be up to be avoided"

    scene(win)
    win._copy_graph_to_clipboard_vector()
    toast = win._canvas_toast
    assert not toast.geometry().intersects(overlay.geometry())
    assert toast.geometry().top() > overlay.geometry().bottom()


def test_a_copy_flashes_a_notice_in_para(para, spy_copy):
    scene(para)
    para._copy_graph_to_clipboard_vector()
    assert 'Exported to paste buffer' in toast_text(para)


def test_the_flash_is_silent_without_a_toast(win):
    """_flash_canvas is a no-op rather than an error on a window built
    before the panel existed."""
    del win._canvas_toast
    win._flash_canvas("nothing to show this on")
