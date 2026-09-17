"""The S-parameter plot's frequency axis for hub-port channels.

A channel is either a legacy port node or an explicit hub; the plot's
per-port frequency rows used to look every channel up in ``self.nodes``,
so a graph whose only channels were hub ports (a terminated line, a pumped
line and its twin) hid the x tick labels and drew nothing in their place.
"""

import os
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")

from tests.test_gui_hubs import para, add_node                  # noqa: E402,F401

HERE = os.path.dirname(__file__)
SCENES = os.path.join(HERE, os.pardir, "examples", "test_scenes")


def _load_scene(win, name, monkeypatch):
    """Load a bundled scene; a load error must FAIL the test, not block it
    behind a modal message box on the offscreen platform."""
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, 'warning',
                        staticmethod(lambda *a, **k: pytest.fail(str(a[1:]))))
    monkeypatch.setattr(QMessageBox, 'information',
                        staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, 'question',
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    win._load_example(Path(SCENES) / name)      # takes a Path (uses .stem)


def _show_all_traces(win, f_start, f_stop, points=41):
    """Compute S through the worker's job route and plot every trace."""
    from graphulator.graphulator_para import _compute_sparams_job
    f = np.linspace(f_start, f_stop, points)
    win._enter_scattering_mode()
    job = win._build_sparams_job(None, f, f_start, f_stop, points)
    assert job is not None
    result = _compute_sparams_job(job)
    assert result is not None
    win._sparams_generation += 1
    win._on_sparams_finished(win._sparams_generation,
                             {'results': [result], 'f_root_s': f})
    for cb in win.sparams_checkboxes.values():
        cb.setChecked(True)
    win._plot_sparams()
    return win.sparams_canvas.ax


def _frequency_labels(ax):
    """(visible x tick labels, per-port frequency-row texts).

    The rows are drawn as free texts: the numbers on the x-axis transform,
    the 'Port ...' captions on the axes transform.
    """
    ticks = [t.label1.get_text() for t in ax.xaxis.get_major_ticks()
             if t.label1.get_visible() and t.label1.get_text()]
    rows = [t.get_text() for t in ax.texts if t.get_text().strip()]
    return ticks, rows


def test_hub_port_channels_keep_their_frequency_axis(para, monkeypatch):
    gp, win, config = para
    _load_scene(win, "LINE_PUMPED_TERMINATION.pgraph", monkeypatch)
    assert win.ports and win.line_resonators and not win.nodes
    ax = _show_all_traces(win, 3.0, 9.0)
    ticks, rows = _frequency_labels(ax)
    # off-diagonal traces between the signal port and its conjugate twin's
    # sit in two frames, so the axis is replaced by one row per frame --
    # and those rows must actually be there
    assert rows, (ticks, rows)
    numbers = [r for r in rows if r.lstrip('\N{MINUS SIGN}-').replace('.', '').isdigit()]
    assert len(numbers) >= 4, rows
    assert any('TL1' in t for t in rows), rows


def test_single_hub_port_keeps_plain_tick_labels(para, monkeypatch):
    gp, win, config = para
    _load_scene(win, "PORT_SHARED_2LINES.pgraph", monkeypatch)
    ax = _show_all_traces(win, 3.0, 6.0)
    ticks, rows = _frequency_labels(ax)
    assert ticks or rows, "x axis has neither tick labels nor frequency rows"


def test_hub_channels_carry_a_drive_frame():
    """autograph: an explicit hub's channel inherits the frame of the modes
    it damps, as a legacy port node always did."""
    from graphulator import autograph
    nodes = [{'node_id': 0, 'label': 'a', 'pos': (0, 0), 'conj': False,
              'freq': 5.0, 'B_int': 0.0, 'B_ext': None},
             {'node_id': 1, 'label': 'b', 'pos': (1, 0), 'conj': True,
              'freq': 6.0, 'B_int': 0.0, 'B_ext': None}]
    edges = [{'from_node_id': 0, 'to_node_id': 1, 'is_self_loop': False}]
    # the extractor keys assignments by the OBJECT ids of the dicts it is
    # handed (the GUI's convention), not by node_id
    assign = {id(nodes[0]): {'freq': 5.0, 'B_int': 0.0},
              id(nodes[1]): {'freq': 6.0, 'B_int': 0.0},
              id(edges[0]): {'f_p': 11.0, 'rate': 0.1, 'phase': 0.0}}
    f = np.linspace(4.0, 6.0, 5)
    ext = autograph.GraphExtractor()
    ext.extract_graph_data(
        nodes=nodes, edges=edges, scattering_assignments=assign,
        frequency_settings={'start': 4.0, 'stop': 6.0, 'points': 5},
        root_node_id=0,
        hubs=[{'hub_id': 'P', 'label': 'P', 'monitored': True,
               'attachments': [(0, 0.3, 0.0)]},
              {'hub_id': 'Q', 'label': 'Q', 'monitored': True,
               'attachments': [(1, 0.3, 0.0)]}])
    gsm = autograph.GraphScatteringMatrix(ext, f)
    assert 'P' in gsm.drive_signals and 'Q' in gsm.drive_signals
    np.testing.assert_allclose(gsm.drive_signals['P'], gsm.drive_signals[0])
    np.testing.assert_allclose(gsm.drive_signals['Q'], gsm.drive_signals[1])
