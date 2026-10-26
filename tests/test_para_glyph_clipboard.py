"""Paragraphulator: ports, lines and their links on the clipboard.

Copy/cut/paste used to carry only nodes, edges and constraint groups, so a
selected sub-circuit came back as bare modes with its ports, lines and
wiring silently dropped. These cover the group round trip, the "both ends
must travel" rule links share with edges, the derived conjugate twin, and
the placement memory that makes a run of glyphs come out consistent.
Headless (offscreen Qt + Agg).
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    # QtWebEngine refuses to sandbox as root (CI containers)
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")


@pytest.fixture()
def para(tmp_path):
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    import graphulator.graphulator_para as gp

    w = gp.Graphulator()
    w.last_graph_path = tmp_path / "last.pgraph"
    w.recent_files_path = tmp_path / "recent"
    return w


def add_node(para, label, pos, freq=5.0):
    node = {'node_id': para.node_id_counter, 'label': label, 'pos': pos,
            'color': '#6699ff', 'color_key': 'BLUE', 'node_size_mult': 1.0,
            'label_size_mult': 1.0, 'conj': False,
            'nodelabelnudge': (0.0, 0.0)}
    para.nodes.append(node)
    para.scattering_assignments[node['node_id']] = {'freq': freq,
                                                    'B_int': 0.0}
    para.node_id_counter += 1
    return node


def wired_scene(para):
    """One mode, one port attached to it, one line tapping it."""
    a = add_node(para, 'A', (0.0, 0.0))
    port = para.add_port(label='P1', pos=(-4.0, 0.0))
    port['color'] = 'indianred'
    port['w_mult'] = 1.4
    att = para.add_port_attachment(port, a, rate=0.25, sign=-1)
    att['color'] = 'teal'
    line = para.add_line_resonator(label='TL1', pos=(0.0, -8.0),
                                   port_end=None, w_mult=1.6)
    conn = para.connect_line_end_to_node(line, 'xL', a, rate=0.125)
    return a, port, att, line, conn


def select_all_of(para, nodes=(), ports=(), lines=()):
    para.selected_nodes[:] = list(nodes)
    para.selected_edges.clear()
    para.selected_ports = list(ports)
    para.selected_lines = list(lines)


# ---------------------------------------------------------------------------
# copy
# ---------------------------------------------------------------------------

def test_copy_carries_ports_lines_and_their_links(para):
    a, port, att, line, conn = wired_scene(para)
    select_all_of(para, [a], [port], [line])
    para._copy_nodes()

    assert len(para.clipboard['ports']) == 1
    assert len(para.clipboard['lines']) == 1
    assert len(para.clipboard['ports'][0]['attachments']) == 1
    assert len(para.clipboard['lines'][0]['ends']['xL']) == 1


def test_the_clipboard_holds_copies_not_the_live_objects(para):
    a, port, att, line, conn = wired_scene(para)
    select_all_of(para, [a], [port], [line])
    para._copy_nodes()

    clip_att = para.clipboard['ports'][0]['attachments'][0]
    assert clip_att is not att
    clip_att['rate'] = 999.0
    assert att['rate'] == pytest.approx(0.25)


def test_a_link_whose_mode_was_not_copied_is_dropped(para):
    """Same rule as an edge: a link travels only when BOTH ends do."""
    a, port, att, line, conn = wired_scene(para)
    select_all_of(para, [], [port], [line])     # the mode stays behind
    para._copy_nodes()

    assert para.clipboard['ports'][0]['attachments'] == []
    assert para.clipboard['lines'][0]['ends']['xL'] == []


def test_copy_with_only_a_glyph_selected_is_not_nothing(para):
    port = para.add_port(label='P1', pos=(-4.0, 0.0))
    select_all_of(para, [], [port], [])
    para._copy_nodes()

    assert len(para.clipboard['ports']) == 1


# ---------------------------------------------------------------------------
# paste
# ---------------------------------------------------------------------------

def test_paste_relinks_the_copy_to_itself(para):
    """The copy must link to the pasted mode, not quietly share the
    original's."""
    a, port, att, line, conn = wired_scene(para)
    select_all_of(para, [a], [port], [line])
    para._copy_nodes()
    para._paste_nodes()

    new_node = para.selected_nodes[0]
    new_port = para.selected_ports[0]
    new_line = para.selected_lines[0]
    assert new_node is not a and new_port is not port and new_line is not line
    assert new_port['port_id'] != port['port_id']
    assert new_line['line_id'] != line['line_id']

    assert new_port['attachments'][0]['node_id'] == new_node['node_id']
    assert new_line['ends']['xL'][0]['node_id'] == new_node['node_id']
    # and the original is untouched
    assert port['attachments'][0]['node_id'] == a['node_id']
    assert line['ends']['xL'][0]['node_id'] == a['node_id']


def test_paste_keeps_glyph_and_link_styling(para):
    a, port, att, line, conn = wired_scene(para)
    select_all_of(para, [a], [port], [line])
    para._copy_nodes()
    para._paste_nodes()

    new_port = para.selected_ports[0]
    assert new_port['color'] == 'indianred'
    assert new_port['w_mult'] == pytest.approx(1.4)
    assert para.selected_lines[0]['w_mult'] == pytest.approx(1.6)
    new_att = new_port['attachments'][0]
    assert new_att['color'] == 'teal'
    assert new_att['rate'] == pytest.approx(0.25)
    assert new_att['sign'] == -1


def test_paste_keeps_the_line_physics(para):
    a, port, att, line, conn = wired_scene(para)
    line['FSR'], line['Ztx'], line['f_max'] = 2.5, 42.0, 12.0
    select_all_of(para, [a], [], [line])
    para._copy_nodes()
    para._paste_nodes()

    new_line = para.selected_lines[0]
    assert (new_line['FSR'], new_line['Ztx'], new_line['f_max']) == \
        (2.5, 42.0, 12.0)
    assert new_line['ends']['xL'][0]['rate'] == pytest.approx(0.125)


def test_smart_paste_auto_increments_glyph_labels(para):
    port = para.add_port(label='P1', pos=(-4.0, 0.0))
    line = para.add_line_resonator(label='TL1', pos=(0.0, -8.0),
                                   port_end=None)
    select_all_of(para, [], [port], [line])
    para._copy_nodes()
    para._paste_nodes()

    assert para.selected_ports[0]['label'] == 'P2'
    assert para.selected_lines[0]['label'] == 'TL2'


def test_raw_paste_keeps_the_original_glyph_labels(para):
    port = para.add_port(label='P1', pos=(-4.0, 0.0))
    select_all_of(para, [], [port], [])
    para._copy_nodes()
    para._paste_nodes_raw()

    assert para.selected_ports[0]['label'] == 'P1'


def test_paste_offsets_a_glyph_only_copy(para):
    """A glyph-only copy has no node centroid; without the glyph positions
    it would paste exactly on top of the original."""
    port = para.add_port(label='P1', pos=(-8.0, 0.0))
    select_all_of(para, [], [port], [])
    para._copy_nodes()
    para._paste_nodes()

    assert len(para.ports) == 2
    assert para.selected_ports[0]['pos'] != port['pos']


def test_pasting_an_empty_clipboard_does_nothing(para):
    para.clipboard = {}
    para._paste_nodes()
    assert para.ports == [] and para.line_resonators == []


# ---------------------------------------------------------------------------
# cut
# ---------------------------------------------------------------------------

def test_cut_removes_the_glyphs_and_keeps_them_on_the_clipboard(para):
    a, port, att, line, conn = wired_scene(para)
    select_all_of(para, [a], [port], [line])
    para._cut_nodes()

    assert para.ports == [] and para.line_resonators == []
    assert para.nodes == []
    assert len(para.clipboard['ports']) == 1
    assert len(para.clipboard['lines']) == 1
    # the links were still live when the clipboard was built
    assert len(para.clipboard['ports'][0]['attachments']) == 1
    assert len(para.clipboard['lines'][0]['ends']['xL']) == 1


def test_cut_then_paste_restores_the_whole_group(para):
    a, port, att, line, conn = wired_scene(para)
    select_all_of(para, [a], [port], [line])
    para._cut_nodes()
    para._paste_nodes()

    assert len(para.ports) == 1 and len(para.line_resonators) == 1
    new_port, new_node = para.selected_ports[0], para.selected_nodes[0]
    assert new_port['attachments'][0]['node_id'] == new_node['node_id']


def test_cutting_a_mode_clears_the_links_that_pointed_at_it(para):
    """A link left pointing at a cut node still reaches the extractor."""
    a, port, att, line, conn = wired_scene(para)
    select_all_of(para, [a], [], [])          # only the mode is cut
    para._cut_nodes()

    assert port['attachments'] == []
    assert para._end_conns(line, 'xL') == []


# ---------------------------------------------------------------------------
# the conjugate twin is derived, not copied
# ---------------------------------------------------------------------------

def test_a_pumped_line_pastes_with_its_own_twin(para):
    line = para.add_line_resonator(label='TL1', pos=(0.0, 0.0),
                                   port_end=None, FSR=1.0, f_max=6.0)
    twin = para.set_line_pump(line, 'xL', f_p=4.0, rate=0.05)
    assert twin is not None
    n_lines = len(para.line_resonators)

    select_all_of(para, [], list(para.ports), [line, twin])
    para._copy_nodes()
    # the twin and its mirror ports are derived -- they must not be carried
    assert len(para.clipboard['lines']) == 1
    para._paste_nodes()

    new_line = para.selected_lines[0]
    assert new_line['pump'] is not None
    new_twin = para.line_twin(new_line)
    assert new_twin is not None and new_twin is not twin
    # one primary + one regenerated twin on top of the originals
    assert len(para.line_resonators) == n_lines + 2
    # the original's pump still points at the original's twin
    assert line['pump']['twin_id'] == twin['line_id']
