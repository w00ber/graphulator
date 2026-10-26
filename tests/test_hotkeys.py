"""Every Graphulator hotkey is pressed, and must do something.

Why this file exists: the app registers its keys in two places -- QShortcut
objects built in `_create_shortcuts`, and QAction objects in the menu bar.
When the same sequence is claimed by both, Qt logs "Ambiguous shortcut
overload" and dispatches NEITHER, so the key goes silently dead while the
menu item still works when clicked. That is invisible to any test that
calls the handler directly, and it is how `P`, `Shift+P`, `L` and `E` broke
the day the Insert menu was added -- and how `Ctrl+N`, `Ctrl+O`, `Ctrl+S`,
`Ctrl+Shift+S`, `Ctrl+Shift+E` and `Ctrl+Q` had been broken long before
that, unnoticed.

So the gate here is behavioural: synthesize the real key event and assert an
observable consequence. EXPECTED covers every registered sequence, and
test_every_registered_key_is_covered fails if a new key is added without an
entry -- so a key can neither be added untested nor go quietly dead.

Destructive or blocking handlers (file dialogs, quit, clear-all) are
replaced on the class BEFORE the window is built, so the shortcut connects
to the recording stub; those entries assert the stub was called.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

#: Handlers replaced before construction: they would open a modal dialog,
#: close the window, or throw away the scene.
STUBBED = [
    '_new_graph', '_open_graph', '_save_graph', '_save_graph_as',
    '_export_code', '_copy_graph_to_clipboard',
    '_copy_graph_to_clipboard_vector', '_open_settings', '_clear_nodes',
    '_toggle_latex_mode', 'close',
]


@pytest.fixture()
def win(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    import graphulator.graphulator_qt as gq

    calls = []
    for name in STUBBED:
        monkeypatch.setattr(gq.Graphulator, name,
                            (lambda n: lambda self, *a, **k: calls.append(n))(name),
                            raising=False)

    w = gq.Graphulator()
    w.last_graph_path = tmp_path / "last.graph"
    w.recent_files_path = tmp_path / "recent"
    w.calls = calls
    w.show()
    QApplication.processEvents()
    return w


# ---------------------------------------------------------------------------
# scene helpers
# ---------------------------------------------------------------------------

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
            'to_node_id': b['node_id'], 'label1': 'g', 'label2': '',
            'linewidth_mult': 1.5, 'label_size_mult': 1.4,
            'label_offset_mult': 1.0, 'style': 'loopy', 'direction': 'both',
            'is_self_loop': False, 'flip_labels': False, 'looptheta': 30,
            'arrowstyle': 'open', 'arrowscale': 1.0}
    edge.update(props)
    w.edges.append(edge)
    return edge


def scene(w):
    """Two nodes, an edge, a self-loop, a port and a txline."""
    a = add_node(w, 'A', (0.0, 0.0))
    b = add_node(w, 'B', (5.0, 0.0))
    edge = add_edge(w, a, b)
    loop = add_edge(w, a, a, is_self_loop=True, selfloopangle=90,
                    selfloopscale=1.0, arrowlengthsc=1.0, flip=False,
                    angle_pinned=False, selflooplabelnudge=(0.0, 0.0))
    port = w.add_port(label='P1', pos=(-6.0, 0.0))
    txline = w.add_txline(label='TL1', pos=(0.0, -6.0))
    return {'a': a, 'b': b, 'edge': edge, 'loop': loop, 'port': port,
            'txline': txline}


def sel_none(w, s):
    w.selected_nodes, w.selected_edges = [], []
    w._clear_glyph_selection()


def sel_node(w, s):
    sel_none(w, s)
    w.selected_nodes = [s['a']]


def sel_nodes(w, s):
    sel_none(w, s)
    w.selected_nodes = [s['a'], s['b']]


def sel_edge(w, s):
    sel_none(w, s)
    w.selected_edges = [s['edge']]


def sel_loop(w, s):
    sel_none(w, s)
    w.selected_edges = [s['loop']]


def sel_glyph(w, s):
    sel_none(w, s)
    w.selected_txlines = [s['txline']]


def mode(w, s, name):
    w.placement_mode = name


# ---------------------------------------------------------------------------
# what each key must do
# ---------------------------------------------------------------------------
# sequence -> (key name, modifiers, setup(w, s), check(w, s) -> comparable)
# The check runs before and after the press; the values must differ.

def _placement(w, s):
    return w.placement_mode


def _view(w, s):
    return (w.base_xlim, w.base_ylim, w.zoom_level)


def _calls(w, s):
    return list(w.calls)


def _nodes(w, s):
    return [tuple(n['pos']) for n in w.nodes], len(w.nodes)


def _selection(w, s):
    return len(w.selected_nodes), len(w.selected_edges)


EXPECTED = {
    # --- placement modes ---
    'G':            ('G', '', sel_none, _placement),
    'Shift+G':      ('G', 'shift', sel_none, _placement),
    'Ctrl+G':       ('G', 'ctrl', sel_none, _placement),
    'E':            ('E', '', sel_none, _placement),
    'Ctrl+E':       ('E', 'ctrl', sel_none, _placement),
    'C':            ('C', '', sel_none, _placement),
    'P':            ('P', '', sel_none, _placement),
    'Shift+P':      ('P', 'shift', sel_none, _placement),
    'L':            ('L', '', sel_none, _placement),
    'Esc':          ('Escape', '', lambda w, s: mode(w, s, 'single'),
                     _placement),
    # --- grid and view ---
    'R':            ('R', '', sel_none, lambda w, s: w.grid_rotation),
    'T':            ('T', '', sel_none, lambda w, s: w.grid_type),
    'A':            ('A', '', sel_none, _view),
    '+':            ('Plus', '', sel_none, _view),
    '=':            ('Equal', '', sel_none, _view),
    '-':            ('Minus', '', sel_none, _view),
    '?':            ('Question', '', sel_none,
                     lambda w, s: getattr(w, '_shortcut_overlay_on', False)),
    # --- panning (nothing selected) ---
    'Up':           ('Up', '', sel_none, _view),
    'Down':         ('Down', '', sel_none, _view),
    'Left':         ('Left', '', sel_none, _view),
    'Right':        ('Right', '', sel_none, _view),
    # --- label nudge (node selected) ---
    'Shift+Up':     ('Up', 'shift', sel_node,
                     lambda w, s: s['a']['nodelabelnudge']),
    'Shift+Down':   ('Down', 'shift', sel_node,
                     lambda w, s: s['a']['nodelabelnudge']),
    'Shift+Left':   ('Left', 'shift', sel_node,
                     lambda w, s: s['a']['nodelabelnudge']),
    'Shift+Right':  ('Right', 'shift', sel_node,
                     lambda w, s: s['a']['nodelabelnudge']),
    # --- self-loop / edge parameter keys ---
    'Ctrl+Up':      ('Up', 'ctrl', sel_loop,
                     lambda w, s: s['loop']['selfloopscale']),
    'Ctrl+Down':    ('Down', 'ctrl', sel_loop,
                     lambda w, s: s['loop']['selfloopscale']),
    'Ctrl+Left':    ('Left', 'ctrl', sel_edge,
                     lambda w, s: s['edge']['looptheta']),
    'Ctrl+Right':   ('Right', 'ctrl', sel_edge,
                     lambda w, s: s['edge']['looptheta']),
    'F':            ('F', '', sel_edge,
                     lambda w, s: s['edge']['flip_labels']),
    'Shift+F':      ('F', 'shift', sel_edge,
                     lambda w, s: w.edge_rotation_mode),
    # --- rotation ---
    'Ctrl+R':       ('R', 'ctrl', sel_nodes, _nodes),
    'Ctrl+Shift+R': ('R', 'ctrlshift', sel_nodes, _nodes),
    # --- selection, clipboard, undo ---
    'Ctrl+A':       ('A', 'ctrl', sel_none, _selection),
    'Ctrl+C':       ('C', 'ctrl', sel_nodes,
                     lambda w, s: len(w.clipboard['nodes'])),
    'Ctrl+X':       ('X', 'ctrl', sel_nodes, _nodes),
    'Ctrl+V':       ('V', 'ctrl',
                     lambda w, s: (sel_nodes(w, s), w._copy_nodes()), _nodes),
    'Ctrl+Z':       ('Z', 'ctrl',
                     lambda w, s: (sel_node(w, s), w._delete_selected_nodes()),
                     _nodes),
    'Ctrl+Shift+Z': ('Z', 'ctrlshift',
                     lambda w, s: (sel_node(w, s),
                                   w._delete_selected_nodes(), w._undo()),
                     _nodes),
    'Ctrl+Y':       ('Y', 'ctrl',
                     lambda w, s: (sel_node(w, s),
                                   w._delete_selected_nodes(), w._undo()),
                     _nodes),
    # --- deletion ---
    'D':            ('D', '', sel_node, _nodes),
    'Del':          ('Delete', '', sel_node, _nodes),
    'Backspace':    ('Backspace', '', sel_node, _nodes),
    # --- stubbed handlers: assert the shortcut reached them ---
    'Ctrl+N':               ('N', 'ctrl', sel_none, _calls),
    'Ctrl+O':               ('O', 'ctrl', sel_none, _calls),
    'Ctrl+S':               ('S', 'ctrl', sel_none, _calls),
    'Ctrl+Shift+S':         ('S', 'ctrlshift', sel_none, _calls),
    'Ctrl+Shift+E':         ('E', 'ctrlshift', sel_none, _calls),
    'Ctrl+Shift+I':         ('I', 'ctrlshift', sel_none, _calls),
    'Ctrl+Shift+J':         ('J', 'ctrlshift', sel_none, _calls),
    'Ctrl+Q':               ('Q', 'ctrl', sel_none, _calls),
    'Ctrl+L':               ('L', 'ctrl', sel_none, _calls),
    'Ctrl+,':               ('Comma', 'ctrl', sel_none, _calls),
    'Ctrl+Shift+Del':       ('Delete', 'ctrlshift', sel_none, _calls),
    'Ctrl+Shift+Backspace': ('Backspace', 'ctrlshift', sel_none, _calls),
}


def registered_sequences(w):
    """Every key sequence the window claims, however it was registered."""
    from PySide6.QtGui import QAction, QShortcut
    seqs = set()
    for sc in w.findChildren(QShortcut):
        if sc.key().toString():
            seqs.add(sc.key().toString())
    for act in w.findChildren(QAction):
        for seq in act.shortcuts():
            if seq.toString():
                seqs.add(seq.toString())
    return seqs


def test_every_registered_key_is_covered(win):
    """No key may be added without a press-test for it."""
    missing = registered_sequences(win) - set(EXPECTED)
    assert not missing, f"registered but never pressed in a test: {sorted(missing)}"


def test_every_expected_key_is_registered(win):
    """...and none of the table's keys has quietly disappeared."""
    stale = set(EXPECTED) - registered_sequences(win)
    assert not stale, f"expected but not registered: {sorted(stale)}"


@pytest.mark.parametrize("sequence", sorted(EXPECTED))
def test_hotkey_does_something(win, sequence):
    from PySide6.QtCore import Qt, qInstallMessageHandler
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    key_name, mod_name, setup, check = EXPECTED[sequence]
    mods = {'': Qt.NoModifier,
            'shift': Qt.ShiftModifier,
            'ctrl': Qt.ControlModifier,
            'ctrlshift': Qt.ControlModifier | Qt.ShiftModifier}[mod_name]

    s = scene(win)
    setup(win, s)
    win._update_plot()
    QApplication.processEvents()

    warnings = []
    qInstallMessageHandler(lambda mode, ctx, text: warnings.append(text))
    try:
        before = check(win, s)
        QTest.keyClick(win, getattr(Qt, f'Key_{key_name}'), mods)
        QApplication.processEvents()
        after = check(win, s)
    finally:
        qInstallMessageHandler(None)

    ambiguous = [t for t in warnings if 'Ambiguous' in t]
    assert not ambiguous, (
        f"{sequence} is claimed by two owners, so Qt dispatched neither: "
        f"{ambiguous}")
    assert after != before, f"{sequence} was pressed and nothing happened"
