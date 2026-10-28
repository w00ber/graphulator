"""The exported script has to draw what the canvas drew.

Three places it did not, all surfaced by the in-app code preview putting
the two pictures side by side:

* wires routed with the wrong reference radius, so a port's fan ran as one
  long straight stub and split in a tight S against the nodes instead of
  spreading as it leaves the port,
* glyph labels ignoring the export's label rescale, so tuning
  NODELABELSCALE moved the modes and left the ports behind,
* LaTeX mode being a flag the loader set without telling matplotlib, so a
  graph saved with LaTeX on reopened in a serif MathText face.

Headless (offscreen Qt + Agg).
"""

import os
import re

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    # QtWebEngine refuses to sandbox as root (CI containers)
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")


@pytest.fixture()
def win(tmp_path):
    """Graphulator: a port fanned out to two modes, as in the report."""
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    import graphulator.graphulator_qt as gq

    w = gq.Graphulator()
    w.last_graph_path = tmp_path / "last.graph"
    w.recent_files_path = tmp_path / "recent"
    return w


def add_node(w, label, pos, conj=False):
    node = {'node_id': w.node_id_counter, 'label': label, 'pos': pos,
            'color': '#c0504d', 'color_key': 'RED', 'node_size_mult': 1.0,
            'label_size_mult': 1.0, 'conj': conj,
            'nodelabelnudge': (0.0, 0.0)}
    w.nodes.append(node)
    w.node_id_counter += 1
    return node


def fan_scene(w):
    """One port wired to a mode and its conjugate."""
    a = add_node(w, 'A', (0.0, 1.0))
    a_star = add_node(w, 'A', (0.0, -1.0), conj=True)
    port = w.add_port(label='P_1', pos=(-3.5, 0.0))
    w.connect_port_to_node(port, a)
    w.connect_port_to_node(port, a_star)
    return port, a, a_star


def rebuilt_circuit(w, compact=False):
    """The GraphCircuit the exported script builds, without drawing it."""
    import matplotlib.pyplot as plt
    from graphulator import code_export

    code = code_export.build_code(w, compact=compact)
    namespace = {'__name__': '__export_fidelity_test__'}
    real_show, plt.show = plt.show, lambda *a, **k: None
    try:
        exec(compile(code.replace('graph.draw(', '#graph.draw('),
                     '<generated>', 'exec'), namespace)
    finally:
        plt.show = real_show
    return namespace['graph'], code


def circuit_wire_points(graph, wire):
    from graphulator.graph_primitives import wirepoints

    p_far = graph._anchorpos(wire['end'])
    p0, t0 = graph._wireanchor(wire['start'], toward=p_far)
    p1, t1 = graph._wireanchor(wire['end'], toward=p0)
    if wire['end'][0] in ('port', 'txline'):
        t1 = (-t1[0], -t1[1])
    return wirepoints(p0, t0, p1, t1, R=graph._wireR(wire),
                      lead0=graph._wirelead(wire['start']),
                      lead1=graph._wirelead(wire['end']))


# ---------------------------------------------------------------------------
# wire routing
# ---------------------------------------------------------------------------

def test_the_exported_wires_trace_the_canvas_wires(win):
    """Point for point, allowing only for the export recentring."""
    from graphulator import code_export

    port, _a, _a_star = fan_scene(win)
    canvas = [np.asarray(win._wire_for(port, conn))
              for conn in port['connections']]
    graph, _code = rebuilt_circuit(win)

    # code_export recentres the drawing on its own centroid
    ctx = code_export.Context(win)
    shift = np.array([ctx.x_center, ctx.y_center])

    assert len(graph.wires) == len(canvas)
    for drawn, wire in zip(canvas, graph.wires):
        exported = circuit_wire_points(graph, wire)
        assert np.abs(exported - (drawn - shift)).max() < 1e-9


def test_a_wire_is_routed_at_the_radius_of_what_it_joins(win):
    """Not GraphCircuit's graph-wide node default, which is 2 while an
    exported scene's objects are all R=0.6: that lifted the bezier clamp
    and straightened the stub out."""
    fan_scene(win)
    graph, _code = rebuilt_circuit(win)
    assert graph._glyphR() != win.node_radius      # the old, wrong value
    for wire in graph.wires:
        assert graph._wireR(wire) == pytest.approx(win.node_radius)


def test_the_fan_spreads_earlier_than_it_did(win):
    """The symptom, stated as geometry: at the graph-wide radius the clamp
    is lifted, so both wires stay together far longer before splitting."""
    from graphulator.graph_primitives import wirepoints

    port, _a, _a_star = fan_scene(win)
    graph, _code = rebuilt_circuit(win)

    def midpoint_gap(radius):
        """Vertical separation of the two wires halfway along."""
        ys = []
        for wire in graph.wires:
            p_far = graph._anchorpos(wire['end'])
            p0, t0 = graph._wireanchor(wire['start'], toward=p_far)
            p1, t1 = graph._wireanchor(wire['end'], toward=p0)
            pts = wirepoints(p0, t0, p1, t1, R=radius,
                             lead0=graph._wirelead(wire['start']),
                             lead1=graph._wirelead(wire['end']))
            ys.append(pts[len(pts) // 2][1])
        return abs(ys[0] - ys[1])

    was = midpoint_gap(graph._glyphR())         # the old, graph-wide radius
    now = midpoint_gap(graph._wireR(graph.wires[0]))
    assert now > was * 1.5, (now, was)


def test_a_wire_to_an_unknown_anchor_falls_back_instead_of_raising():
    """_wireR has to survive a half-built graph (it is called while the
    script is still adding objects in some orders)."""
    from graphulator import graph_primitives as gp

    graph = gp.GraphCircuit(allow_duplicate_labels=True)
    wire = {'start': ('port', 99), 'end': ('node', 99)}
    assert graph._wireR(wire) == graph._glyphR()


# ---------------------------------------------------------------------------
# glyph labels follow the export's label rescale
# ---------------------------------------------------------------------------

def labelscales(code):
    """{'port': value, 'txline': value} as written into the script."""
    found = {}
    for line in code.splitlines():
        if 'addport' not in line and 'addtxline' not in line:
            continue
        match = re.search(r"labelscale=([\d.]+)", line)
        key = 'port' if 'addport' in line else 'txline'
        found[key] = float(match.group(1)) if match else None
    return found


def test_glyph_labels_follow_the_node_label_rescale(win):
    from graphulator import code_export

    port, _a, _a_star = fan_scene(win)
    win.add_txline(label='TL1', pos=(0.0, -4.0))

    win.export_rescale['NODELABELSCALE'] = 0.5
    assert labelscales(code_export.build_code(win)) == {'port': 0.5,
                                                        'txline': 0.5}
    win.export_rescale['NODELABELSCALE'] = 2.0
    assert labelscales(code_export.build_code(win)) == {'port': 2.0,
                                                        'txline': 2.0}


def test_at_the_default_rescale_nothing_is_written(win):
    """1.0 is the primitive default, so it stays out of the script."""
    from graphulator import code_export

    fan_scene(win)
    win.add_txline(label='TL1', pos=(0.0, -4.0))
    win.export_rescale['NODELABELSCALE'] = 1.0
    assert labelscales(code_export.build_code(win)) == {'port': None,
                                                        'txline': None}


def test_a_glyphs_own_label_multiplier_composes_with_the_rescale(win):
    from graphulator import code_export

    port, _a, _a_star = fan_scene(win)
    port['label_size_mult'] = 1.5
    win.export_rescale['NODELABELSCALE'] = 2.0
    assert labelscales(code_export.build_code(win))['port'] == 3.0


def test_the_rescale_reaches_the_grouped_export_too(win):
    from graphulator import code_export

    fan_scene(win)
    win.export_rescale['NODELABELSCALE'] = 0.5
    code = code_export.build_code(win, compact=True)
    assert "'labelscale': 0.500" in code or 'labelscale=0.500' in code


def test_the_exported_script_still_runs_with_a_rescale(win):
    """The scaled value has to be something addport accepts."""
    from graphulator.code_preview import preview_png_bytes

    fan_scene(win)
    win.add_txline(label='TL1', pos=(0.0, -4.0))
    win.export_rescale['NODELABELSCALE'] = 0.4
    png, error = preview_png_bytes(win)
    assert error is None, error
    assert png.startswith(b'\x89PNG')


# ---------------------------------------------------------------------------
# LaTeX mode is global matplotlib state, not just a flag
# ---------------------------------------------------------------------------

@pytest.fixture()
def quiet_latex_warning(monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, 'warning',
                        staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, 'information',
                        staticmethod(lambda *a, **k: None))


@pytest.fixture()
def restore_rcparams():
    import matplotlib

    keys = ('text.usetex', 'text.latex.preamble', 'mathtext.fontset',
            'font.family')
    saved = {k: matplotlib.rcParams[k] for k in keys}
    yield
    matplotlib.rcParams.update(saved)


def test_opening_a_latex_graph_puts_matplotlib_in_latex_mode(
        win, tmp_path, quiet_latex_warning, restore_rcparams):
    import matplotlib

    add_node(win, 'A_1', (0.0, 0.0))
    win._toggle_latex_mode()
    assert win.use_latex is True
    path = tmp_path / "latexy.graph"
    win._save_graph_to_file(str(path))

    # a window that is in MathText mode, as a fresh launch would be
    reopened = type(win)()
    reopened.last_graph_path = tmp_path / "last2.graph"
    reopened.recent_files_path = tmp_path / "recent2"
    matplotlib.rcParams['text.usetex'] = False
    matplotlib.rcParams['font.family'] = 'STIXGeneral'

    reopened._open_graph_file(str(path))
    assert reopened.use_latex is True
    assert matplotlib.rcParams['text.usetex'] is True
    assert 'sfmath' in matplotlib.rcParams['text.latex.preamble']


def test_opening_a_mathtext_graph_puts_matplotlib_back(
        win, tmp_path, quiet_latex_warning, restore_rcparams):
    import matplotlib

    add_node(win, 'A_1', (0.0, 0.0))
    path = tmp_path / "plain.graph"
    win._save_graph_to_file(str(path))
    assert win.use_latex is False

    matplotlib.rcParams['text.usetex'] = True
    win._open_graph_file(str(path))
    assert matplotlib.rcParams['text.usetex'] is False
    assert matplotlib.rcParams['text.latex.preamble'] == ''


def test_applying_the_mode_drops_the_glyph_cache(win, quiet_latex_warning,
                                                 restore_rcparams):
    """Cached glyph paths were rendered under the old preamble."""
    cleared = []
    win._label_cache.clear = lambda: cleared.append(True)
    win.use_latex = True
    win._apply_latex_mode(warn=False)
    assert cleared


def test_the_toggle_still_works(win, quiet_latex_warning, restore_rcparams):
    import matplotlib

    add_node(win, 'A_1', (0.0, 0.0))
    before = win.use_latex
    win._toggle_latex_mode()
    assert win.use_latex is not before
    assert matplotlib.rcParams['text.usetex'] is win.use_latex
    win._toggle_latex_mode()
    assert win.use_latex is before
    assert matplotlib.rcParams['text.usetex'] is before
