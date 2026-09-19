"""Mode-frequency overlay on the S-parameter plot.

Reading a mode index off the plot is how you pick the pump's reference
pair, so the markers have to land where that mode actually RESONATES on
the displayed axis -- which is not f_n in general: every channel is read
in its own drive frame, and a pumped line's conjugate twin is read at
f_p - f. The overlay inverts the frame from the sweep's own drive_signals
rather than re-deriving it per topology.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")

from tests.test_gui_hubs import para                            # noqa: E402,F401


def _plot(win, f_start, f_stop, points=201):
    """Compute S through the worker's job route and draw the plot."""
    from graphulator.graphulator_para import _compute_sparams_job
    from PySide6.QtWidgets import QApplication
    f = np.linspace(f_start, f_stop, points)
    if not win.scattering_mode:
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
    QApplication.processEvents()
    return f


def _terminated_line(para, **kw):
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = True
    win._apply_explicit_ports_mode()
    win.resize(1400, 900)
    win.show()
    line = win.add_line_resonator(label='TL1', pos=(0.0, 0.0), FSR=1.5,
                                  Ztx=65.0, f_max=9.0, port_end='xL', **kw)
    return win, line


def test_overlay_is_off_until_toggled(para):
    win, line = _terminated_line(para)
    _plot(win, 0.5, 10.0)
    assert win._mode_markers == []
    win.sparams_mark_modes.setChecked(True)
    win._on_sparams_mark_modes_toggled()
    assert win._mode_markers


def test_markers_sit_on_the_mode_frequencies(para):
    win, line = _terminated_line(para)
    win.sparams_mark_modes.setChecked(True)
    _plot(win, 0.5, 10.0)
    res = win.line_resonator_for(line)
    got = {m['n']: m['x'] for m in win._mode_markers}
    # every mode inside the window is marked, at its own frequency
    for n in range(1, res.N + 1):
        f_n = res.mode_freq(n)
        if 0.5 <= f_n <= 10.0:
            assert abs(got[n] - f_n) < 1e-9, (n, got.get(n), f_n)
    # and nothing beyond the comb cutoff
    assert max(got) <= res.N
    assert sum(m['is_cutoff'] for m in win._mode_markers) <= 1


def test_loaded_line_marks_the_dispersed_modes(para):
    """The whole point of marking rather than computing n*FSR by eye."""
    win, line = _terminated_line(
        para, load={'end': 'x0', 'type': 'inductive', 'f_Z': 3.0})
    win.sparams_mark_modes.setChecked(True)
    _plot(win, 0.2, 10.0)
    res = win.line_resonator_for(line)
    got = {m['n']: m['x'] for m in win._mode_markers}
    assert got, "no markers drawn for a loaded line"
    for n, x in got.items():
        assert abs(x - res.mode_freq(n)) < 1e-9
    # they are NOT at n*FSR -- that is why the overlay exists
    assert any(abs(x - n * res.FSR) > 0.05 for n, x in got.items())


def test_twin_markers_are_translated_into_the_displayed_frame(para):
    """A pumped line's twin is read at f_p - f, so its mode m lands at
    f_p - f_m on the plotted axis, not at f_m."""
    win, line = _terminated_line(para)
    win.set_line_pump(line, 'x0', f_p=9.0, rate=0.05, n_ref=3,
                      twin_pos=(0.0, -5.0))
    win.sparams_mark_modes.setChecked(True)
    _plot(win, 0.5, 9.0)
    res = win.line_resonator_for(line)
    twin_marks = {m['n']: m['x'] for m in win._mode_markers if m['conj']}
    sig_marks = {m['n']: m['x'] for m in win._mode_markers if not m['conj']}
    assert twin_marks and sig_marks
    for n, x in sig_marks.items():
        assert abs(x - res.mode_freq(n)) < 1e-9
    for m, x in twin_marks.items():
        assert abs(x - (9.0 - res.mode_freq(m))) < 1e-9, (m, x)


def test_hover_reports_line_index_and_frequency(para):
    import matplotlib.backend_bases as bb
    win, line = _terminated_line(para)
    win.sparams_mark_modes.setChecked(True)
    _plot(win, 0.5, 10.0)
    ax = win.sparams_canvas.ax
    target = next(m for m in win._mode_markers if m['n'] == 3)
    px, py = ax.transData.transform((target['x'],
                                     np.mean(ax.get_ylim())))
    event = bb.MouseEvent('motion_notify_event', win.sparams_canvas, px, py)
    win._on_mode_marker_hover(event)
    ann = win._mode_marker_annotation
    assert ann is not None and ann.get_visible()
    assert 'TL1' in ann.get_text() and 'mode 3' in ann.get_text()

    # away from any marker the tip goes away again
    far_x = 0.5 * (target['x'] + ax.get_xlim()[1])
    px2, _ = ax.transData.transform((far_x, np.mean(ax.get_ylim())))
    if abs(px2 - px) > 20:
        win._on_mode_marker_hover(
            bb.MouseEvent('motion_notify_event', win.sparams_canvas, px2, py))
        assert not win._mode_marker_annotation.get_visible()


def test_overlay_survives_an_invalid_line(para):
    """A line whose parameters are momentarily invalid must not break the
    plot -- the panel lets you type through such states."""
    win, line = _terminated_line(para)
    win.sparams_mark_modes.setChecked(True)
    _plot(win, 0.5, 10.0)
    line['FSR'] = 0.0                      # invalid; LineResonator raises
    win._plot_sparams()                    # must not raise
    assert win._mode_markers == []


def test_toggle_persists_through_save_and_load(para, tmp_path):
    import json
    win, line = _terminated_line(para)
    win.sparams_mark_modes.setChecked(True)
    _plot(win, 0.5, 10.0)
    path = tmp_path / "marks.pgraph"
    assert win._save_graph_to_file(str(path))
    data = json.loads(path.read_text())
    assert data['scattering']['sparams_plot']['mark_modes'] is True
