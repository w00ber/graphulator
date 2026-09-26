"""Edge line widths come from one table, and it reaches down below 'Thin'.

Dense graphs need edges thinner than the old thinnest setting: at 1.0 a
50-edge fan is a solid band. Two levels were added below 'Thin', and the
levels now live in `config.EDGE_LINEWIDTH_OPTIONS` -- every widget that
offers them (the add-edge dialog, the single and multi properties panels, the
right-click width menu) reads that table, so a level added there shows up in
all of them and nowhere has its own private copy to drift.

Headless (offscreen Qt).
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")


@pytest.fixture()
def win(tmp_path):
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    import graphulator.graphulator_qt as gq

    w = gq.Graphulator()
    w.last_graph_path = tmp_path / "last.graph"
    w.recent_files_path = tmp_path / "recent"
    return w


@pytest.fixture()
def para(tmp_path):
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    import graphulator.graphulator_para as gp

    w = gp.Graphulator()
    w.last_graph_path = tmp_path / "last.pgraph"
    w.recent_files_path = tmp_path / "recent"
    return w


def add_node(w, label, pos):
    node = {'node_id': w.node_id_counter, 'label': label, 'pos': pos,
            'color': '#6699ff', 'color_key': 'BLUE', 'node_size_mult': 1.0,
            'label_size_mult': 1.0, 'conj': False,
            'nodelabelnudge': (0.0, 0.0)}
    w.nodes.append(node)
    w.node_id_counter += 1
    return node


def add_edge(w, a, b, **props):
    edge = {'from_node': a, 'to_node': b, 'from_node_id': a['node_id'],
            'to_node_id': b['node_id'], 'label1': '', 'label2': '',
            'linewidth_mult': 1.5, 'label_size_mult': 1.4,
            'label_offset_mult': 1.0, 'style': 'single', 'direction': 'both',
            'is_self_loop': False, 'flip_labels': False, 'looptheta': 30}
    edge.update(props)
    w.edges.append(edge)
    return edge


# ---------------------------------------------------------------------------
# the table
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("module", ['graphulator_config',
                                    'graphulator_para_config'])
def test_two_levels_sit_below_thin(module):
    import importlib

    config = importlib.import_module(f'graphulator.{module}')
    levels = config.EDGE_LINEWIDTH_OPTIONS
    assert list(levels)[:3] == ['XX-Thin', 'X-Thin', 'Thin']
    assert levels['XX-Thin'] < levels['X-Thin'] < levels['Thin']
    # thinnest first, all the way up
    assert list(levels.values()) == sorted(levels.values())
    assert config.DEFAULT_EDGE_LINEWIDTH_NAME in levels


# ---------------------------------------------------------------------------
# the widgets that offer it
# ---------------------------------------------------------------------------

def test_the_add_edge_dialog_offers_every_level(win):
    import graphulator.graphulator_qt as gq
    from graphulator import graphulator_config as config

    dialog = gq.EdgeInputDialog('A', 'B')
    items = [dialog.lw_combo.itemText(i)
             for i in range(dialog.lw_combo.count())]
    assert items == list(config.EDGE_LINEWIDTH_OPTIONS)

    dialog.lw_combo.setCurrentText('XX-Thin')
    dialog.use_labels_checkbox.setChecked(False)
    dialog.accept()
    assert dialog.get_result()['linewidth_mult'] == pytest.approx(
        config.EDGE_LINEWIDTH_OPTIONS['XX-Thin'])


def test_the_properties_panel_applies_a_thinner_level(win):
    from graphulator import graphulator_config as config

    a, b = add_node(win, 'A', (0.0, 0.0)), add_node(win, 'B', (4.0, 0.0))
    edge = add_edge(win, a, b)
    win.selected_edges = [edge]
    win._update_properties_panel()

    panel = win.properties_panel
    items = [panel.linewidth_combo.itemText(i)
             for i in range(panel.linewidth_combo.count())]
    assert items == list(config.EDGE_LINEWIDTH_OPTIONS)

    panel.linewidth_combo.setCurrentText('X-Thin')
    assert edge['linewidth_mult'] == pytest.approx(
        config.EDGE_LINEWIDTH_OPTIONS['X-Thin'])


def test_a_multi_selection_applies_a_thinner_level(win):
    from PySide6.QtWidgets import QComboBox
    from graphulator import graphulator_config as config

    nodes = [add_node(win, f'N{i}', (3.0 * i, 0.0)) for i in range(3)]
    edges = [add_edge(win, nodes[0], nodes[1]),
             add_edge(win, nodes[1], nodes[2])]
    win.selected_edges = edges
    win._update_properties_panel()

    panel = win.properties_panel
    levels = list(config.EDGE_LINEWIDTH_OPTIONS)
    combo = next(c for c in panel.findChildren(QComboBox)
                 if [c.itemText(i) for i in range(c.count())][-len(levels):]
                 == levels)
    combo.setCurrentText('XX-Thin')
    combo.activated.emit(combo.currentIndex())   # the panel commits on user pick
    for edge in edges:
        assert edge['linewidth_mult'] == pytest.approx(
            config.EDGE_LINEWIDTH_OPTIONS['XX-Thin'])


def test_para_offers_the_thinner_levels_too(para):
    from graphulator import graphulator_para_config as config

    a, b = add_node(para, 'A', (0.0, 0.0)), add_node(para, 'B', (4.0, 0.0))
    edge = add_edge(para, a, b)
    para.selected_edges = [edge]
    para._update_properties_panel()

    panel = para.properties_panel
    items = [panel.linewidth_combo.itemText(i)
             for i in range(panel.linewidth_combo.count())]
    assert items == list(config.EDGE_LINEWIDTH_OPTIONS)

    panel.linewidth_combo.setCurrentText('XX-Thin')
    assert edge['linewidth_mult'] == pytest.approx(
        config.EDGE_LINEWIDTH_OPTIONS['XX-Thin'])


def test_a_thin_edge_reaches_the_exported_code(win):
    """A level nothing can draw or export is not a level."""
    from PySide6.QtWidgets import QApplication
    from graphulator import graphulator_config as config

    a, b = add_node(win, 'A', (0.0, 0.0)), add_node(win, 'B', (4.0, 0.0))
    thin = add_edge(win, a, b,
                    linewidth_mult=config.EDGE_LINEWIDTH_OPTIONS['XX-Thin'])
    thick = add_edge(win, b, a,
                     linewidth_mult=config.EDGE_LINEWIDTH_OPTIONS['X-Thick'])
    win._update_plot()

    QApplication.clipboard().setText('')
    win._export_code()
    code = QApplication.clipboard().text()

    widths = [float(line.split("'lw': ")[1].split(',')[0])
              for line in code.split('\n') if "'lw': " in line]
    assert len(widths) == 2
    ratio = (config.EDGE_LINEWIDTH_OPTIONS['X-Thick']
             / config.EDGE_LINEWIDTH_OPTIONS['XX-Thin'])
    assert max(widths) / min(widths) == pytest.approx(ratio, rel=0.02)
    assert thin['linewidth_mult'] < thick['linewidth_mult']
