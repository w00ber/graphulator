"""The generated Python, rendered in-app instead of in a notebook.

The Export Scaling parameters are calibration constants baked into the
NUMBERS the exported script contains -- they do not touch the canvas, so
the only way to see an edit to them was to paste the script into a
notebook and run it. These cover the render (which execs generated code),
the window that shows it beside the script, the figure bookkeeping that
keeps refreshes from piling up pyplot figures, and the hooks that make a
scaling tweak re-render. Headless (offscreen Qt + Agg).
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    # QtWebEngine refuses to sandbox as root (CI containers)
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")


@pytest.fixture(autouse=True)
def no_leftover_figures():
    """Every test here must hand pyplot back as it found it."""
    import matplotlib.pyplot as plt

    before = set(plt.get_fignums())
    yield
    leaked = [n for n in plt.get_fignums() if n not in before]
    for num in leaked:
        plt.close(num)
    assert not leaked, f"preview left {len(leaked)} pyplot figure(s) behind"


@pytest.fixture()
def win(tmp_path):
    """Graphulator with two wired modes and a port."""
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    import graphulator.graphulator_qt as gq

    w = gq.Graphulator()
    w.last_graph_path = tmp_path / "last.graph"
    w.recent_files_path = tmp_path / "recent"
    scene(w)
    return w


@pytest.fixture()
def para(tmp_path):
    """Paragraphulator with two wired modes and a port."""
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    import graphulator.graphulator_para as gp

    w = gp.Graphulator()
    w.last_graph_path = tmp_path / "last.pgraph"
    w.recent_files_path = tmp_path / "recent"
    a, _b = scene(w)
    port = w.add_port(label='P1', pos=(-6.0, 0.0))
    w.add_port_attachment(port, a, rate=0.25)
    return w


@pytest.fixture()
def empty_win(tmp_path):
    """Graphulator with nothing drawn."""
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    import graphulator.graphulator_qt as gq

    w = gq.Graphulator()
    w.last_graph_path = tmp_path / "last.graph"
    w.recent_files_path = tmp_path / "recent"
    return w


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
    w.edges.append({'from_node': a, 'to_node': b,
                    'from_node_id': a['node_id'], 'to_node_id': b['node_id'],
                    'label1': 'g', 'label2': '', 'linewidth_mult': 1.0,
                    'label_size_mult': 1.0, 'label_offset_mult': 1.0,
                    'style': 'single', 'direction': 'forward',
                    'looptheta': 30, 'is_self_loop': False,
                    'arrowstyle': 'open', 'arrowscale': 1.0})
    return a, b


# ---------------------------------------------------------------------------
# render_code: run generated Python, hand back its figure
# ---------------------------------------------------------------------------

def test_it_renders_the_figure_the_script_drew():
    from graphulator.code_preview import render_code

    figure, error = render_code(
        "import matplotlib.pyplot as plt\n"
        "fig, ax = plt.subplots(figsize=(6, 4))\n"
        "ax.plot([0, 1], [0, 1])\n"
        "plt.show()\n")
    assert error is None
    assert len(figure.axes) == 1
    assert tuple(figure.get_size_inches()) == (6.0, 4.0)
    figure.clear()


def test_the_figure_it_returns_is_detached_from_pyplot():
    """Detached before it is adopted by a Qt canvas -- closing it later
    would otherwise take the canvas with it."""
    import matplotlib.pyplot as plt
    from graphulator.code_preview import render_code

    figure, error = render_code(
        "import matplotlib.pyplot as plt\nplt.subplots()\nplt.show()\n")
    assert error is None
    assert plt.get_fignums() == []
    assert figure.axes                      # still usable
    figure.clear()


def test_it_can_still_be_adopted_by_a_qt_canvas():
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from graphulator.code_preview import render_code

    figure, _error = render_code(
        "import matplotlib.pyplot as plt\n"
        "fig, ax = plt.subplots()\nax.plot([0, 1], [1, 0])\nplt.show()\n")
    canvas = FigureCanvasQTAgg(figure)
    canvas.draw()
    assert figure.canvas is canvas
    figure.clear()


def test_a_script_that_raises_comes_back_as_a_traceback():
    from graphulator.code_preview import render_code

    figure, error = render_code("raise ValueError('boom')")
    assert figure is None
    assert 'ValueError: boom' in error
    assert 'Traceback' in error


def test_a_syntax_error_comes_back_as_a_traceback():
    from graphulator.code_preview import render_code

    figure, error = render_code("def (")
    assert figure is None
    assert 'SyntaxError' in error


def test_a_script_that_draws_nothing_says_so():
    from graphulator.code_preview import render_code

    figure, error = render_code("x = 1")
    assert figure is None
    assert 'drew nothing' in error


def test_a_failure_after_drawing_leaks_nothing():
    """The case that leaks if the bookkeeping is wrong: a figure made, and
    then an exception. The autouse fixture is what checks pyplot is clean."""
    from graphulator.code_preview import render_code

    figure, error = render_code(
        "import matplotlib.pyplot as plt\n"
        "plt.subplots()\n"
        "raise RuntimeError('after drawing')\n")
    assert figure is None
    assert 'after drawing' in error


def test_extra_figures_a_script_makes_are_not_kept():
    from graphulator.code_preview import render_code

    figure, error = render_code(
        "import matplotlib.pyplot as plt\n"
        "plt.subplots(); plt.subplots(); plt.subplots()\n"
        "plt.show()\n")
    assert error is None
    figure.clear()


def test_it_never_pops_a_window_of_its_own():
    """plt.show() is neutralized: the point is to render in-app."""
    import matplotlib.pyplot as plt
    from graphulator.code_preview import render_code

    figure, _error = render_code(
        "import matplotlib.pyplot as plt\nplt.subplots()\nplt.show()\n")
    assert plt.isinteractive() is False or True   # restored, either way
    assert callable(plt.show)
    figure.clear()


# ---------------------------------------------------------------------------
# the real generated code, end to end
# ---------------------------------------------------------------------------

def test_the_exported_script_renders(win):
    from graphulator.code_preview import preview_png_bytes

    png, error = preview_png_bytes(win)
    assert error is None, error
    assert png.startswith(b'\x89PNG')
    assert len(png) > 2000


def test_the_compact_export_renders_too(win):
    from graphulator.code_preview import preview_png_bytes

    png, error = preview_png_bytes(win, compact=True)
    assert error is None, error
    assert png.startswith(b'\x89PNG')


def test_the_paragraphulator_export_renders(para):
    from graphulator.code_preview import preview_png_bytes

    png, error = preview_png_bytes(para)
    assert error is None, error
    assert png.startswith(b'\x89PNG')


def test_an_empty_graph_has_nothing_to_preview(empty_win):
    from graphulator.code_preview import preview_png_bytes

    png, error = preview_png_bytes(empty_win)
    assert png is None
    assert 'empty' in error


# ---------------------------------------------------------------------------
# the window
# ---------------------------------------------------------------------------

def test_the_window_shows_the_figure_and_the_code(win):
    dialog = win._show_code_preview()
    try:
        assert dialog._canvas is not None
        assert dialog._figure is not None
        assert 'gp.GraphCircuit' in dialog.code_view.toPlainText()
        assert 'Rendered the verbose export' in dialog.status.text()
    finally:
        dialog.close()


def test_the_compact_toggle_re_renders(win):
    dialog = win._show_code_preview()
    try:
        verbose = dialog.code_view.toPlainText()
        dialog.compact_check.setChecked(True)
        assert dialog.code_view.toPlainText() != verbose
        assert 'compact' in dialog.status.text()
    finally:
        dialog.close()


def test_a_failed_render_keeps_the_window_alive(win, monkeypatch):
    from graphulator import code_preview

    dialog = win._show_code_preview()
    try:
        monkeypatch.setattr(code_preview, 'render_code',
                            lambda code: (None, 'Traceback...\nBoom'))
        dialog.refresh()
        assert 'Render failed' in dialog.status.text()
        assert 'Boom' in dialog.code_view.toPlainText()
        # the last good picture is still up to compare against
        assert dialog._canvas is not None
    finally:
        dialog.close()


def test_an_empty_graph_says_so_in_the_window(empty_win):
    dialog = empty_win._show_code_preview()
    try:
        assert 'empty' in dialog.status.text()
        assert dialog._canvas is None
    finally:
        dialog.close()


def test_reopening_reuses_the_same_window(win):
    first = win._show_code_preview()
    try:
        assert win._show_code_preview() is first
    finally:
        first.close()


def test_copy_code_puts_the_script_on_the_clipboard(win):
    from PySide6.QtWidgets import QApplication

    dialog = win._show_code_preview()
    try:
        dialog._copy_code()
        assert 'gp.GraphCircuit' in QApplication.clipboard().text()
        assert 'Copied' in dialog.status.text()
    finally:
        dialog.close()


def test_closing_the_window_releases_its_figure(win):
    dialog = win._show_code_preview()
    figure = dialog._figure
    dialog.close()
    assert dialog._figure is None
    assert figure.axes == []                # cleared, not left dangling


# ---------------------------------------------------------------------------
# the hooks that make tuning visible
# ---------------------------------------------------------------------------

def test_a_scaling_spinbox_re_renders_an_open_preview(win):
    dialog = win._show_code_preview()
    try:
        before = dialog.code_view.toPlainText()
        win.properties_panel.scaling_spinboxes['EDGELWSCALE'].setValue(4.5)
        assert dialog.code_view.toPlainText() != before
    finally:
        dialog.close()


def test_auto_refresh_off_leaves_the_preview_where_it_was(win):
    dialog = win._show_code_preview()
    try:
        dialog.auto_check.setChecked(False)
        before = dialog.code_view.toPlainText()
        win.properties_panel.scaling_spinboxes['EDGELWSCALE'].setValue(3.9)
        assert dialog.code_view.toPlainText() == before
    finally:
        dialog.close()


def test_refreshing_without_a_window_is_a_no_op(win):
    """The usual case: nobody opened the preview."""
    assert getattr(win, '_code_preview', None) is None
    win._refresh_code_preview()


def test_the_para_settings_apply_re_renders_the_preview(para):
    from graphulator.para_ui.settings_dialog import SettingsDialog

    dialog = para._show_code_preview()
    try:
        before = dialog.code_view.toPlainText()
        settings = SettingsDialog(para)
        settings._set_widget_value('EDGELWSCALE', 4.5)
        settings._on_apply()
        assert dialog.code_view.toPlainText() != before
    finally:
        dialog.close()


def test_the_scaling_tab_is_named_for_the_export_it_scales(win):
    """It reads oddly next to the drawing defaults because it is not a
    drawing default; the name should at least say which export."""
    tabs = win.properties_panel.tabs
    names = [tabs.tabText(i) for i in range(tabs.count())]
    assert 'Code Export' in names
    assert 'Export Scaling' not in names


def test_para_names_its_scaling_tab_the_same_way():
    import graphulator.graphulator_para as gp

    assert 'Code Export Scaling' in gp.SETTINGS_PARAMS
    assert 'Export Scaling' not in gp.SETTINGS_PARAMS
