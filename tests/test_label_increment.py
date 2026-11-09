"""Tests for label auto-increment, shared by both apps.

The table lives in common_window; both apps' ``_auto_increment_label`` and
Paragraphulator's smart-paste sequencer read from it. The cases that matter
most here are the NEGATIVE subscripts ('A_-2'), which previously matched no
pattern at all and were copied verbatim onto the next node.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from graphulator.common_window import (auto_increment_label,  # noqa: E402
                                       format_subscript_label,
                                       letters_to_number, number_to_letters)


@pytest.mark.parametrize("label,expected", [
    # pure letters
    ('A', 'B'), ('Z', 'AA'), ('AA', 'AB'), ('a', 'b'), ('z', 'aa'),
    # bare subscripts
    ('A_1', 'A_2'), ('A_8', 'A_9'),
    # a two-character subscript gets braces, or only its first character
    # would render lowered
    ('A_9', 'A_{10}'), ('A_{10}', 'A_{11}'),
    # negative subscripts, braced or not -- counting UPWARD through zero
    ('A_-2', 'A_{-1}'), ('A_{-2}', 'A_{-1}'), ('A_-1', 'A_0'),
    ('A_{-10}', 'A_{-9}'),
    # multi-letter prefixes
    ('Mode_2', 'Mode_3'), ('Mode_-1', 'Mode_0'),
    # letter + adjacent number
    ('A0', 'A1'), ('B9', 'B10'), ('A-2', 'A-1'),
    # pure numbers
    ('1', '2'), ('99', '100'), ('-3', '-2'), ('-1', '0'), ('0', '1'),
])
def test_auto_increment(label, expected):
    assert auto_increment_label(label) == expected


@pytest.mark.parametrize("label", ['', 'Q-factor', 'A_B', '  ', 'x_y_1'])
def test_unrecognized_labels_are_returned_unchanged(label):
    assert auto_increment_label(label) == label


def test_incrementing_a_negative_sequence_walks_up_to_zero():
    label = 'A_-3'
    seen = [label]
    for _ in range(4):
        label = auto_increment_label(label)
        seen.append(label)
    assert seen == ['A_-3', 'A_{-2}', 'A_{-1}', 'A_0', 'A_1']


def test_format_subscript_label_braces_only_when_needed():
    assert format_subscript_label('A', 3) == 'A_3'
    assert format_subscript_label('A', 12) == 'A_{12}'
    assert format_subscript_label('A', -1) == 'A_{-1}'


def test_letter_number_round_trip():
    for n in (1, 26, 27, 52, 703):
        assert letters_to_number(number_to_letters(n)) == n
    assert number_to_letters(1) == 'A'
    assert number_to_letters(27) == 'AA'
    assert number_to_letters(2, lowercase=True) == 'b'
    assert letters_to_number('ab') == letters_to_number('AB')


# ---------------------------------------------------------------------------
# both apps' window methods delegate to the shared table
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_graphulator_window_increments_negative_labels(qapp, tmp_path):
    import graphulator.graphulator_qt as gq
    w = gq.Graphulator()
    w.last_graph_path = tmp_path / "last.graph"
    assert w._auto_increment_label('A_-2') == 'A_{-1}'
    assert w._auto_increment_label('A') == 'B'


def test_paragraphulator_window_increments_negative_labels(qapp, tmp_path):
    import graphulator.graphulator_para as gp
    w = gp.Graphulator()
    w.last_graph_path = tmp_path / "last.pgraph"
    assert w._auto_increment_label('A_-2') == 'A_{-1}'
    assert w._auto_increment_label('A') == 'B'


def test_continuous_duplicate_placement_walks_a_negative_series(qapp,
                                                                tmp_path):
    """The reported symptom: in auto-increment placement mode a label like
    'A_-2' was copied to the next node instead of stepping."""
    import graphulator.graphulator_qt as gq
    w = gq.Graphulator()
    w.last_graph_path = tmp_path / "last.graph"
    labels = []
    current = 'A_-2'
    for _ in range(3):
        current = w._auto_increment_label(current)
        labels.append(current)
    assert labels == ['A_{-1}', 'A_0', 'A_1']
    assert len(set(labels)) == 3       # no duplicates


# ---------------------------------------------------------------------------
# Paragraphulator's smart-paste sequencer
# ---------------------------------------------------------------------------

def test_label_pattern_analyzer_classifies_negative_subscripts(qapp):
    from graphulator.graphulator_para import LabelPatternAnalyzer as LA
    assert LA.classify_label('A_-2') == (LA.PATTERN_UNDERSCORE, 'A', -2)
    assert LA.classify_label('A_{-2}') == (LA.PATTERN_UNDERSCORE, 'A', -2)
    assert LA.classify_label('A_{12}') == (LA.PATTERN_UNDERSCORE, 'A', 12)
    assert LA.classify_label('-3') == (LA.PATTERN_PURE_NUMBER, '', -3)


def test_smart_paste_continues_an_all_negative_series(qapp):
    """A series living entirely below zero used to report a max of -1 (the
    sentinel), so the paste jumped to 0 instead of continuing the run."""
    from graphulator.graphulator_para import LabelPatternAnalyzer as LA
    existing = {'A_-5', 'A_-4', 'A_-3'}
    mapping = LA.compute_next_labels(['A_-5'], existing)
    assert mapping['A_-5'] == 'A_{-2}'


def test_smart_paste_still_continues_a_positive_series(qapp):
    from graphulator.graphulator_para import LabelPatternAnalyzer as LA
    mapping = LA.compute_next_labels(['A_1'], {'A_1', 'A_2'})
    assert mapping['A_1'] == 'A_3'


# ---------------------------------------------------------------------------
# continuous placement (Shift+G): one dialog, then a subscripted series
# ---------------------------------------------------------------------------
#
# The reported symptom: the node dialog opened on EVERY click, and its
# default label came from a plain letter counter, so a series started as
# 'A_0' went on 'B', 'C', ... instead of 'A_1', 'A_2'.

class _StubNodeDialog:
    """Stands in for NodeInputDialog: counts how often it opens and accepts
    whatever label it was offered (or the one a test asks it to type)."""

    opened = []
    typed = None

    def __init__(self, default_label='A', default_color='BLUE', parent=None,
                 **_):
        from unittest import mock
        type(self).opened.append(default_label)
        self.label = type(self).typed or default_label
        type(self).typed = None
        for name in ('node_size_combo', 'label_size_combo', 'conj_checkbox',
                     'node_size_slider', 'label_size_slider',
                     'outline_checkbox', 'outline_color_combo',
                     'outline_width_slider', 'outline_alpha_slider'):
            setattr(self, name, mock.MagicMock())

    def exec(self):
        from PySide6.QtWidgets import QDialog
        return QDialog.Accepted

    def get_result(self):
        return {'label': self.label, 'color': '#6699ff', 'color_key': 'BLUE',
                'node_size_mult': 1.0, 'label_size_mult': 1.0, 'conj': False,
                'outline_enabled': False, 'outline_color_key': 'BLACK',
                'outline_color': 'black', 'outline_width': 1.0,
                'outline_alpha': 1.0}


def _left_click(win, x, y):
    import types
    win._on_click(types.SimpleNamespace(xdata=x, ydata=y, button=1,
                                        inaxes=win.canvas.ax, dblclick=False,
                                        key=None))


@pytest.fixture(params=['graphulator_qt', 'graphulator_para'])
def placing_window(request, qapp, tmp_path, monkeypatch):
    import importlib
    module = importlib.import_module(f'graphulator.{request.param}')
    monkeypatch.setattr(module, 'NodeInputDialog', _StubNodeDialog)
    _StubNodeDialog.opened = []
    _StubNodeDialog.typed = None
    w = module.Graphulator()
    w.last_graph_path = tmp_path / 'last'
    w.recent_files_path = tmp_path / 'recent'
    w.nodes.clear()
    w.node_counter = 0
    w.last_node_props = None
    return w


def test_continuous_mode_asks_once_then_continues_the_subscript(
        placing_window):
    w = placing_window
    w._toggle_continuous_mode()
    _StubNodeDialog.typed = 'A_0'
    for i in range(4):
        _left_click(w, 2.0 * i, 0.0)

    assert [n['label'] for n in w.nodes] == ['A_0', 'A_1', 'A_2', 'A_3']
    assert len(_StubNodeDialog.opened) == 1
    assert w.placement_mode == 'continuous'


def test_reentering_continuous_mode_asks_again_and_offers_the_next_label(
        placing_window):
    w = placing_window
    w._toggle_continuous_mode()
    _StubNodeDialog.typed = 'B_8'
    _left_click(w, 0.0, 0.0)
    _left_click(w, 2.0, 0.0)
    w._toggle_continuous_mode()            # off
    w._toggle_continuous_mode()            # on again: a fresh session
    _left_click(w, 4.0, 0.0)

    assert [n['label'] for n in w.nodes] == ['B_8', 'B_9', 'B_{10}']
    assert len(_StubNodeDialog.opened) == 2
    assert _StubNodeDialog.opened[-1] == 'B_{10}'


def test_the_next_label_steps_past_labels_already_in_use(placing_window):
    w = placing_window
    w._toggle_continuous_mode()
    _StubNodeDialog.typed = 'A_0'
    _left_click(w, 0.0, 0.0)
    w.nodes.append(dict(w.nodes[0], node_id=99, label='A_1', pos=(9.0, 9.0)))
    _left_click(w, 2.0, 0.0)

    assert w.nodes[-1]['label'] == 'A_2'


def test_single_placement_offers_the_next_subscript(placing_window):
    w = placing_window
    w.placement_mode = 'single'
    _StubNodeDialog.typed = 'a_{-1}'
    _left_click(w, 0.0, 0.0)
    w.placement_mode = 'single'
    _left_click(w, 2.0, 0.0)

    assert _StubNodeDialog.opened[-1] == 'a_0'


def test_duplicate_mode_on_an_empty_label_continues_the_letter_count(
        placing_window):
    """Ctrl+G with no previous node used to start at 'A' even when an 'A'
    was already on the canvas."""
    w = placing_window
    w.nodes.append({'node_id': 0, 'label': 'A', 'pos': (9.0, 9.0),
                    'color': '#6699ff', 'color_key': 'BLUE',
                    'node_size_mult': 1.0, 'label_size_mult': 1.0,
                    'conj': False})
    w.node_counter = 1
    w._toggle_continuous_duplicate_mode()
    _left_click(w, 0.0, 0.0)

    assert w.nodes[-1]['label'] == 'B'
    assert _StubNodeDialog.opened == []
