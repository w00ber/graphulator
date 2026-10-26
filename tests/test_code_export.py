"""The generated drawing code: the colors it names, and its two shapes.

Two things this file gates.

The colors: the pickers hand back hex and only *try* to name it in the
palette, so a node's `color_key` routinely names a different color than the
`color` the canvas draws. The export used to trust the key, so a graph of
hand-picked colors came out uniformly 'RED' -- right on screen, monochrome in
the script.

The shapes: `compact` factors look-alike objects into style dicts and loops
over the geometry. It has to draw the same figure as the explicit shape, or
it is a different graph wearing the same name -- so the test renders both and
compares pixels.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture()
def win(tmp_path):
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    import graphulator.graphulator_qt as gq

    w = gq.Graphulator()
    w.last_graph_path = tmp_path / "last.graph"
    w.recent_files_path = tmp_path / "recent"
    return w


def add_node(w, label, pos, **props):
    node = {'node_id': w.node_id_counter, 'label': label, 'pos': pos,
            'color': '#6699ff', 'color_key': 'BLUE', 'node_size_mult': 1.0,
            'label_size_mult': 1.0, 'conj': False,
            'nodelabelnudge': (0.0, 0.0)}
    node.update(props)
    w.nodes.append(node)
    w.node_id_counter += 1
    w.node_counter += 1
    return node


def add_edge(w, a, b, **props):
    edge = {'from_node': a, 'to_node': b, 'from_node_id': a['node_id'],
            'to_node_id': b['node_id'], 'label1': '', 'label2': '',
            'linewidth_mult': 1.5, 'label_size_mult': 1.4,
            'label_offset_mult': 1.0, 'style': 'double', 'direction': 'both',
            'is_self_loop': False, 'flip_labels': False, 'looptheta': 30,
            'arrowstyle': 'open', 'arrowscale': 1.0}
    edge.update(props)
    w.edges.append(edge)
    return edge


def export(w, compact=False):
    from PySide6.QtWidgets import QApplication
    QApplication.clipboard().setText('')
    w._export_code(compact=compact)
    return QApplication.clipboard().text()


def render(code, path):
    """Run generated code and return the figure it draws, as pixels."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    ns = {'__name__': '__main__'}
    exec(compile(code.replace("plt.show()", f'plt.savefig(r"{path}")'),
                 str(path), 'exec'), ns)
    plt.close('all')
    return ns['graph'], np.asarray(matplotlib.image.imread(path))


# ---------------------------------------------------------------------------
# colors
# ---------------------------------------------------------------------------

def test_a_hand_picked_color_exports_as_that_color(win):
    """The bug: three colors on screen, one color key in the data."""
    for i, color in enumerate(('#aab6a8', '#929ec0', '#cd726c')):
        # color_key stayed 'RED' because the picker could not name the hex
        add_node(win, f'A_{i}', (2.0 * i, 0.0), color=color,
                 color_key='RED')
    win._update_plot()

    code = export(win)
    for color in ('#aab6a8', '#929ec0', '#cd726c'):
        assert f"nodecolor='{color}'" in code
    assert "MYCOLORS['RED']" not in code


def test_a_palette_color_still_exports_by_its_palette_name(win):
    """A node that really is MYCOLORS['RED'] keeps the readable spelling,
    whichever way the color happens to be written down."""
    add_node(win, 'A', (0.0, 0.0), color='indianred', color_key='RED')
    add_node(win, 'B', (4.0, 0.0), color='#CD5C5C', color_key='RED')
    win._update_plot()

    code = export(win)
    assert code.count("nodecolor=config.MYCOLORS['RED']") == 2


def test_palette_key_matches_colors_not_spellings():
    from graphulator import code_export, graphulator_config as config

    assert code_export.palette_key('#cd5c5c', config) == 'RED'
    assert code_export.palette_key('indianred', config) == 'RED'
    assert code_export.palette_key('#123456', config) is None


def test_an_outline_color_survives_a_stale_key_too(win):
    add_node(win, 'A', (0.0, 0.0), outline_enabled=True,
             outline_color='#334455', outline_color_key='BLACK',
             outline_width=3.0, outline_alpha=0.5)
    win._update_plot()

    code = export(win)
    assert "nodeoutlinecolor='#334455'" in code


# ---------------------------------------------------------------------------
# the compact shape
# ---------------------------------------------------------------------------

def scene(win):
    """Two families of nodes, a self-loop, a labeled edge, a wired port."""
    reds = [add_node(win, f'R_{i}', (0.0, 3.0 * i), color='indianred',
                     color_key='RED') for i in range(3)]
    blues = [add_node(win, f'B_{i}', (9.0, 3.0 * i), color='#929ec0',
                      color_key='RED') for i in range(3)]
    for r, b in zip(reds, blues):
        add_edge(win, r, b)
    add_edge(win, reds[0], blues[1], label1='g', label2='',
             label_rotation_offset=5)
    add_edge(win, reds[2], reds[2], is_self_loop=True, label1=r'\kappa',
             selfloopangle=90, selfloopscale=1.0, arrowlengthsc=1.0,
             flip=False, selflooplabelnudge=(0.0, 0.0))
    port = win.add_port(label='P1', pos=(-6.0, 3.0))
    for r in reds:
        win.connect_port_to_node(port, r)
    win._update_plot()
    return reds, blues, port


def test_the_compact_shape_groups_look_alikes(win):
    scene(win)
    code = export(win, compact=True)

    assert 'NODE_STYLES' in code and 'NODES = {' in code
    # two node colors, and the self-loop node is its own style
    assert code.count("': dict(") >= 2
    assert "for _style, _items in NODES.items():" in code
    # the wired port and its five wires are grouped too
    assert 'WIRE_STYLES' in code


def test_the_compact_shape_draws_the_same_figure(win, tmp_path):
    import numpy as np

    scene(win)
    verbose = export(win)
    compact = export(win, compact=True)

    a, pixels_a = render(verbose, tmp_path / 'verbose.png')
    b, pixels_b = render(compact, tmp_path / 'compact.png')

    assert len(a.nodes) == len(b.nodes) == 6
    assert len(a.edges) == len(b.edges)
    assert len(a.wires) == len(b.wires) == 3
    assert np.array_equal(pixels_a, pixels_b)


def test_the_compact_shape_is_the_shorter_one(win):
    for i in range(12):
        add_node(win, f'A_{i}', (2.0 * i, 0.0), color='indianred',
                 color_key='RED')
    for i in range(11):
        add_edge(win, win.nodes[i], win.nodes[i + 1])
    win._update_plot()

    long, short = export(win), export(win, compact=True)
    assert len(short.split('\n')) < len(long.split('\n')) / 2


def test_a_lone_object_stays_an_explicit_call(win):
    """Grouping one node behind three blocks of scaffolding helps nobody."""
    add_node(win, 'A', (0.0, 0.0))
    win._update_plot()

    code = export(win, compact=True)
    assert 'NODE_STYLES' not in code
    assert 'graph.addnode(label=' in code
