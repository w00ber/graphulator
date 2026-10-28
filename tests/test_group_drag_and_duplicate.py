"""Dragging and Option-duplicating a whole sub-circuit, in both apps.

Two drag machineries used to live side by side: the node drag (delta-based,
NODES ONLY) and the glyph drag (one glyph, straight to the pointer). Clicking
a port shrank the selection to that port and dragged it alone, so a selected
port + edge + node could not be moved as a group at all, and nothing anywhere
copied on Option-drag. Headless (offscreen Qt + Agg).
"""

import os
import types

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    # QtWebEngine refuses to sandbox as root (CI containers)
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")


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


def add_node(w, label, pos):
    node = {'node_id': w.node_id_counter, 'label': label, 'pos': pos,
            'color': '#6699ff', 'color_key': 'BLUE', 'node_size_mult': 1.0,
            'label_size_mult': 1.0, 'conj': False,
            'nodelabelnudge': (0.0, 0.0)}
    w.nodes.append(node)
    w.node_id_counter += 1
    return node


def click(x, y, button=1, ax=None):
    return types.SimpleNamespace(xdata=x, ydata=y, button=button, inaxes=ax)


# ---------------------------------------------------------------------------
# the shared group-drag machinery
# ---------------------------------------------------------------------------

def test_a_group_lists_its_nodes_and_its_glyphs(win):
    a = add_node(win, 'A', (0.0, 0.0))
    port = win.add_port(label='P1', pos=(-6.0, 0.0))
    win.selected_nodes[:] = [a]
    win.selected_ports = [port]
    members = win._group_drag_members()
    assert any(m is a for m in members) and any(m is port for m in members)


def test_a_group_drag_is_rigid(win):
    """One snapped delta for everyone. Snapping each member on its own
    shears a group whose members do not share a grid phase."""
    a = add_node(win, 'A', (0.0, 0.0))
    b = add_node(win, 'B', (0.37, 1.13))      # deliberately off-grid
    win.selected_nodes[:] = [a, b]
    before = b['pos'][0] - a['pos'][0], b['pos'][1] - a['pos'][1]
    win._commit_group_drag(3.3, 2.2)
    after = b['pos'][0] - a['pos'][0], b['pos'][1] - a['pos'][1]
    assert after == pytest.approx(before)


def test_a_group_drag_carries_the_glyphs(win):
    a = add_node(win, 'A', (0.0, 0.0))
    port = win.add_port(label='P1', pos=(-6.0, 0.0))
    win.connect_port_to_node(port, a)
    win.selected_nodes[:] = [a]
    win.selected_ports = [port]
    node_before, port_before = a['pos'], port['pos']

    win._commit_group_drag(4.0, 4.0)
    assert a['pos'] != node_before and port['pos'] != port_before
    moved = (a['pos'][0] - node_before[0], a['pos'][1] - node_before[1])
    assert (port['pos'][0] - port_before[0],
            port['pos'][1] - port_before[1]) == pytest.approx(moved)


def test_a_group_drag_is_one_undo_step(win):
    a = add_node(win, 'A', (0.0, 0.0))
    port = win.add_port(label='P1', pos=(-6.0, 0.0))
    win.selected_nodes[:] = [a]
    win.selected_ports = [port]
    before = len(win.undo_stack)
    win._commit_group_drag(4.0, 4.0)
    assert len(win.undo_stack) == before + 1


def test_a_group_refuses_to_land_on_an_unselected_node(win):
    a = add_node(win, 'A', (0.0, 0.0))
    add_node(win, 'B', (4.0, 0.0))             # not selected, in the way
    win.selected_nodes[:] = [a]
    win.selected_ports = [win.add_port(label='P1', pos=(-6.0, 0.0))]
    message = win._commit_group_drag(4.0, 0.0)
    assert 'occupied' in message
    assert a['pos'] == (0.0, 0.0)


def test_glyphs_may_overlap_during_a_group_drag(win):
    """Only NODES get the occupancy rule: a port sitting on the mode it
    feeds is a legitimate drawing."""
    a = add_node(win, 'A', (0.0, 0.0))
    port = win.add_port(label='P1', pos=(-4.0, 0.0))
    win.add_port(label='P2', pos=(0.0, 0.0))   # unselected, in the way
    win.selected_ports = [port]
    win.selected_nodes[:] = [a]
    assert win._commit_group_drag(-4.0, 0.0) is not None


# ---------------------------------------------------------------------------
# clicking an already-selected object drags the whole group
# ---------------------------------------------------------------------------

def test_clicking_a_selected_port_arms_the_group_not_the_port(win):
    a = add_node(win, 'A', (0.0, 0.0))
    port = win.add_port(label='P1', pos=(-6.0, 0.0))
    win.selected_nodes[:] = [a]
    win.selected_ports = [port]

    assert win._maybe_handle_glyph_click(click(-6.0, 0.0), False, False)
    assert win.drag_pending_group is True
    assert win._glyph_drag_pending is None
    # and the selection survived the click
    assert win.selected_nodes == [a] and win.selected_ports == [port]


def test_clicking_a_lone_port_still_drags_just_it(win):
    port = win.add_port(label='P1', pos=(-6.0, 0.0))
    assert win._maybe_handle_glyph_click(click(-6.0, 0.0), False, False)
    assert win._glyph_drag_pending == ('port', port)
    assert win.drag_pending_group is False


def test_clicking_a_selected_port_arms_the_group_in_para(para):
    a = add_node(para, 'A', (0.0, 0.0))
    port = para.add_port(label='P1', pos=(-6.0, 0.0))
    para.selected_nodes[:] = [a]
    para.selected_ports = [port]

    assert para._maybe_handle_ports_normal_click(click(-6.0, 0.0),
                                                 False, False)
    assert para.drag_pending_group is True
    assert para._glyph_drag_pending is None


def test_a_para_group_drag_carries_the_glyphs(para):
    a = add_node(para, 'A', (0.0, 0.0))
    port = para.add_port(label='P1', pos=(-6.0, 0.0))
    para.add_port_attachment(port, a)
    para.selected_nodes[:] = [a]
    para.selected_ports = [port]
    node_before, port_before = a['pos'], port['pos']

    para._commit_group_drag(4.0, 4.0)
    moved = (a['pos'][0] - node_before[0], a['pos'][1] - node_before[1])
    assert moved != (0.0, 0.0)
    assert (port['pos'][0] - port_before[0],
            port['pos'][1] - port_before[1]) == pytest.approx(moved)


def test_a_kron_drag_leaves_the_glyphs_out(para):
    """The Kron canvas is a different node list and has no glyphs at all."""
    a = add_node(para, 'A', (0.0, 0.0))
    port = para.add_port(label='P1', pos=(-6.0, 0.0))
    para.selected_nodes[:] = [a]
    para.selected_ports = [port]
    kron_nodes = [dict(a)]
    members = para._group_drag_members(nodes=kron_nodes)
    assert not any(m is port for m in members)


# ---------------------------------------------------------------------------
# Option/Alt-drag duplicates instead of moving
# ---------------------------------------------------------------------------

def test_option_drag_leaves_the_original_and_copies_it(win):
    a = add_node(win, 'A', (0.0, 0.0))
    port = win.add_port(label='P1', pos=(-6.0, 0.0))
    win.connect_port_to_node(port, a)
    win.selected_nodes[:] = [a]
    win.selected_ports = [port]
    win._drag_duplicate = True

    message = win._commit_group_drag(0.0, 8.0)
    assert 'Copied' in message
    assert a['pos'] == (0.0, 0.0) and port['pos'] == (-6.0, 0.0)
    assert len(win.nodes) == 2 and len(win.ports) == 2
    # the copy is wired to ITSELF, not sharing the original's node
    new_port = win.selected_ports[0]
    assert new_port is not port
    assert new_port['connections'][0]['node_id'] != a['node_id']


def test_option_drag_does_not_clobber_the_clipboard(win):
    a = add_node(win, 'A', (0.0, 0.0))
    win.selected_nodes[:] = [a]
    win._copy_nodes()
    saved = win.clipboard

    win._drag_duplicate = True
    win.selected_nodes[:] = [a]
    win.selected_ports = [win.add_port(label='P1', pos=(-6.0, 0.0))]
    win._commit_group_drag(0.0, 8.0)
    assert win.clipboard is saved


def test_option_drag_on_the_spot_copies_nothing(win):
    a = add_node(win, 'A', (0.0, 0.0))
    win.selected_nodes[:] = [a]
    win._drag_duplicate = True
    message = win._commit_group_drag(0.0, 0.0)
    assert 'Nothing copied' in message
    assert len(win.nodes) == 1


def test_option_drag_duplicates_in_para(para):
    a = add_node(para, 'A', (0.0, 0.0))
    port = para.add_port(label='P1', pos=(-6.0, 0.0))
    para.add_port_attachment(port, a)
    para.selected_nodes[:] = [a]
    para.selected_ports = [port]
    para._drag_duplicate = True

    message = para._commit_group_drag(0.0, 8.0)
    assert 'Copied' in message
    assert a['pos'] == (0.0, 0.0) and port['pos'] == (-6.0, 0.0)
    assert len(para.nodes) == 2 and len(para.ports) == 2
    new_port = para.selected_ports[0]
    assert new_port['attachments'][0]['node_id'] != a['node_id']


def test_a_plain_drag_still_moves(win):
    a = add_node(win, 'A', (0.0, 0.0))
    win.selected_nodes[:] = [a]
    win.selected_ports = [win.add_port(label='P1', pos=(-6.0, 0.0))]
    win._drag_duplicate = False
    win._commit_group_drag(0.0, 8.0)
    assert len(win.nodes) == 1
    assert a['pos'] != (0.0, 0.0)


# ---------------------------------------------------------------------------
# end to end: click a selected port, drag, release
# ---------------------------------------------------------------------------

def test_dragging_a_selected_port_moves_the_whole_group(win):
    """The reported bug: with a port + node selected, grabbing the port
    moved the port alone and dropped everything else from the selection."""
    a = add_node(win, 'A', (0.0, 0.0))
    port = win.add_port(label='P1', pos=(-6.0, 0.0))
    win.connect_port_to_node(port, a)
    win.selected_nodes[:] = [a]
    win.selected_ports = [port]
    ax = win.canvas.ax

    assert win._maybe_handle_glyph_click(click(-6.0, 0.0), False, False)
    win._on_motion(click(-6.0, 4.0, ax=ax))
    assert win.dragging_group is True
    win._on_release(click(-6.0, 4.0, ax=ax))

    assert a['pos'] != (0.0, 0.0)
    assert port['pos'] != (-6.0, 0.0)
    assert win.dragging_group is False


def test_dragging_a_selected_port_moves_the_group_in_para(para):
    a = add_node(para, 'A', (0.0, 0.0))
    port = para.add_port(label='P1', pos=(-6.0, 0.0))
    para.add_port_attachment(port, a)
    para.selected_nodes[:] = [a]
    para.selected_ports = [port]
    ax = para.canvas.ax

    assert para._maybe_handle_ports_normal_click(click(-6.0, 0.0),
                                                 False, False)
    para._on_motion(click(-6.0, 4.0, ax=ax))
    assert para.dragging_group is True
    para._on_release(click(-6.0, 4.0, ax=ax))

    assert a['pos'] != (0.0, 0.0)
    assert port['pos'] != (-6.0, 0.0)
    assert para.dragging_group is False


# ---------------------------------------------------------------------------
# grabbing the NODE half of the group must keep the glyphs
#
# The glyph hit-test runs before node handling and used to clear the glyph
# selection on any click that missed a glyph -- a click on a node included.
# So the port + node group reached _arm_group_drag_from with its ports
# already gone: grabbing the port moved everything, grabbing the node moved
# the nodes alone, which is what made move / Option-drag-copy / copy-paste
# of a port + wire + node look intermittent.
# ---------------------------------------------------------------------------

def test_clicking_a_selected_node_keeps_the_glyphs_in_the_selection(win):
    a = add_node(win, 'A', (0.0, 0.0))
    port = win.add_port(label='P1', pos=(-6.0, 0.0))
    win.connect_port_to_node(port, a)
    win.selected_nodes[:] = [a]
    win.selected_ports = [port]

    # the click misses every glyph: it is the node that is being grabbed
    assert win._maybe_handle_glyph_click(click(0.0, 0.0), False, False) is False
    assert win.selected_ports == [port]


def test_clicking_an_unselected_node_still_clears_the_glyphs(win):
    add_node(win, 'A', (0.0, 0.0))
    port = win.add_port(label='P1', pos=(-6.0, 0.0))
    win.selected_ports = [port]                 # node NOT selected

    assert win._maybe_handle_glyph_click(click(0.0, 0.0), False, False) is False
    assert win.selected_ports == []


def test_clicking_empty_space_still_clears_the_glyphs(win):
    port = win.add_port(label='P1', pos=(-6.0, 0.0))
    win.selected_ports = [port]
    assert win._maybe_handle_glyph_click(click(9.0, 9.0), False, False) is False
    assert win.selected_ports == []


def test_dragging_a_selected_node_moves_the_whole_group(win):
    a = add_node(win, 'A', (0.0, 0.0))
    port = win.add_port(label='P1', pos=(-6.0, 0.0))
    win.connect_port_to_node(port, a)
    win.selected_nodes[:] = [a]
    win.selected_ports = [port]
    ax = win.canvas.ax

    win._on_click(click(0.0, 0.0, ax=ax))
    assert win.drag_pending_group is True
    win._on_motion(click(0.0, 4.0, ax=ax))
    assert win.dragging_group is True
    win._on_release(click(0.0, 4.0, ax=ax))

    assert a['pos'] != (0.0, 0.0)
    assert port['pos'] != (-6.0, 0.0)


def test_option_dragging_a_selected_node_copies_the_glyphs_too(win):
    a = add_node(win, 'A', (0.0, 0.0))
    port = win.add_port(label='P1', pos=(-6.0, 0.0))
    win.connect_port_to_node(port, a)
    win.selected_nodes[:] = [a]
    win.selected_ports = [port]

    assert win._maybe_handle_glyph_click(click(0.0, 0.0), False, False,
                                         True) is False
    assert win._arm_group_drag_from(a, 0.0, 0.0, True) is True
    message = win._commit_group_drag(0.0, 8.0)

    assert 'Copied' in message
    assert len(win.nodes) == 2 and len(win.ports) == 2
    new_port = win.selected_ports[0]
    assert new_port is not port
    assert new_port['connections'][0]['node_id'] != a['node_id']


def test_copying_after_clicking_a_selected_node_still_carries_the_port(win):
    a = add_node(win, 'A', (0.0, 0.0))
    port = win.add_port(label='P1', pos=(-6.0, 0.0))
    win.connect_port_to_node(port, a)
    win.selected_nodes[:] = [a]
    win.selected_ports = [port]

    win._maybe_handle_glyph_click(click(0.0, 0.0), False, False)
    win._copy_nodes()
    assert len(win.clipboard['ports']) == 1
    assert len(win.clipboard['ports'][0]['connections']) == 1


def test_clicking_a_selected_node_keeps_the_glyphs_in_para(para):
    a = add_node(para, 'A', (0.0, 0.0))
    port = para.add_port(label='P1', pos=(-6.0, 0.0))
    att = para.add_port_attachment(port, a)
    para.selected_nodes[:] = [a]
    para.selected_ports = [port]
    para.selected_attachments = [(port, att)]

    assert para._maybe_handle_ports_normal_click(click(0.0, 0.0),
                                                 False, False) is False
    assert para.selected_ports == [port]
    assert para.selected_attachments == [(port, att)]


def test_clicking_an_unselected_node_still_clears_the_glyphs_in_para(para):
    add_node(para, 'A', (0.0, 0.0))
    port = para.add_port(label='P1', pos=(-6.0, 0.0))
    para.selected_ports = [port]

    assert para._maybe_handle_ports_normal_click(click(0.0, 0.0),
                                                 False, False) is False
    assert para.selected_ports == []


def test_dragging_a_selected_node_moves_the_group_in_para(para):
    a = add_node(para, 'A', (0.0, 0.0))
    port = para.add_port(label='P1', pos=(-6.0, 0.0))
    para.add_port_attachment(port, a)
    para.selected_nodes[:] = [a]
    para.selected_ports = [port]
    ax = para.canvas.ax

    para._on_click_normal_mode(click(0.0, 0.0, ax=ax), False)
    assert para.drag_pending_group is True
    para._on_motion(click(0.0, 4.0, ax=ax))
    assert para.dragging_group is True
    para._on_release(click(0.0, 4.0, ax=ax))

    assert a['pos'] != (0.0, 0.0)
    assert port['pos'] != (-6.0, 0.0)
