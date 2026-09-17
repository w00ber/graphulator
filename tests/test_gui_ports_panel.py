"""The Ports & Lines panel as the place a glyph-only graph is tuned from.

A pumped line and its twin have no graph node, so the Nodes and Edges
tables are empty; everything tunable -- the line's FSR/Ztx/f_max/Z0/alpha,
its end load's f_Z, the pump's f_p/rate/phase/n_ref -- must be live in
Ports & Lines, which now spans the full width under Nodes | Edges.
"""

import os
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")

from tests.test_gui_hubs import para                            # noqa: E402,F401

SCENES = Path(__file__).resolve().parent.parent / "examples" / "test_scenes"


def _pumped_scene(para, load=None):
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = True
    win._apply_explicit_ports_mode()
    kw = {'load': load} if load else {}
    line = win.add_line_resonator(label='TL1', pos=(0.0, 2.0), FSR=1.5,
                                  Ztx=65.0, f_max=6.0, port_end='xL', **kw)
    win.set_line_pump(line, 'x0', f_p=9.0, rate=0.05, n_ref=3,
                      twin_pos=(0.0, -2.0))
    win._enter_scattering_mode()
    win.properties_panel._update_scattering_ports_table()
    return win, line


def _spins(panel):
    from PySide6.QtWidgets import QDoubleSpinBox
    return panel.ports_param_widget.findChildren(QDoubleSpinBox)


def _spin_with_tip(panel, fragment):
    return next(s for s in _spins(panel) if fragment in s.toolTip())


def test_glyph_only_graph_is_tunable_from_ports_and_lines(para):
    win, line = _pumped_scene(para)
    panel = win.properties_panel
    assert not win.nodes
    # the panel is visible and full-width (a sibling of Nodes|Edges, not
    # a child of the Nodes column)
    assert panel.ports_frame.isVisibleTo(panel)
    assert panel.ports_frame.parent() is not None
    assert 'nodes' not in type(panel.ports_frame.parent()).__name__.lower()

    fsr = _spin_with_tip(panel, "Free spectral range")
    fsr.setValue(2.0)
    assert line['FSR'] == 2.0
    twin = win.line_twin(line)
    win._gui_lines_payload()
    assert twin['FSR'] == 2.0                     # mirrored onto the twin

    fp = _spin_with_tip(panel, "Pump frequency")
    fp.setValue(7.5)
    assert line['pump']['f_p'] == 7.5
    rate = _spin_with_tip(panel, "Parametric coupling")
    rate.setValue(80.0)
    assert abs(line['pump']['rate'] - 0.08) < 1e-12
    phase = _spin_with_tip(panel, "Pump phase")
    phase.setValue(45.0)
    assert line['pump']['phase'] == 45.0


def test_invalid_line_edit_is_refused_not_applied(para):
    win, line = _pumped_scene(para)
    panel = win.properties_panel
    fmax = _spin_with_tip(panel, "Comb extent")
    fmax.setValue(0.5)                            # < FSR on an unloaded line
    assert line['f_max'] == 6.0


def test_load_fz_is_live_in_the_panel(para):
    load = {'end': 'x0', 'type': 'inductive', 'f_Z': 3.0}
    win, line = _pumped_scene(para, load=load)
    panel = win.properties_panel
    fz = _spin_with_tip(panel, "f_Z [a.u.]")
    fz.setValue(4.0)
    assert line['load']['f_Z'] == 4.0
    assert win.line_twin(line)['load']['f_Z'] == 4.0


def test_placeholder_points_at_ports_and_lines(para):
    from PySide6.QtWidgets import QLabel
    from PySide6.QtCore import QCoreApplication, QEvent
    win, line = _pumped_scene(para)
    panel = win.properties_panel
    panel._update_scattering_node_table()
    # the table rebuild deleteLater()s the old labels; flush those so only
    # the live ones are inspected
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    texts = [w.text() for w in panel.nodes_param_widget.findChildren(QLabel)]
    assert any('Ports' in t and 'Lines' in t for t in texts), texts
    assert not any('Enter Scattering mode' in t for t in texts), texts


def test_tail_closure_toggle_reaches_the_job(para):
    win, line = _pumped_scene(para)
    panel = win.properties_panel
    assert win.line_tail_closure is True
    f = np.linspace(3.0, 9.0, 11)
    assert win._build_sparams_job(None, f, 3.0, 9.0, 11)['tail_closure'] is True
    panel.tail_closure_check.setChecked(False)
    assert win.line_tail_closure is False
    assert win._build_sparams_job(None, f, 3.0, 9.0, 11)['tail_closure'] is False
    # and the comb note says so
    from PySide6.QtWidgets import QLabel
    notes = [w.text() for w in panel.ports_param_widget.findChildren(QLabel)
             if 'N = ' in w.text()]
    assert notes and all('raw truncated comb' in n for n in notes), notes
    panel.tail_closure_check.setChecked(True)
    notes = [w.text() for w in panel.ports_param_widget.findChildren(QLabel)
             if 'N = ' in w.text()]
    assert notes and all('closed analytically' in n for n in notes), notes


def test_truncation_check_reports_a_number(para):
    win, line = _pumped_scene(para)
    panel = win.properties_panel
    panel.freq_center_spin.setValue(4.5)
    panel.freq_span_spin.setValue(3.0)
    panel.freq_points_spin.setValue(41)
    panel._check_truncation()
    assert panel._truncation_result is not None
    assert np.isfinite(panel._truncation_result)
    # the check must leave the graph exactly as it found it
    assert line['f_max'] == 6.0 and win.line_twin(line)['f_max'] == 6.0
    assert "|\N{GREEK CAPITAL LETTER DELTA}S|" in panel.truncation_check_button.text()


def test_truncation_check_is_small_for_a_terminated_line_with_closure(para):
    """A plain terminated line: the closure makes the port loading exact,
    so doubling f_max must change S by (numerically) nothing."""
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = True
    win._apply_explicit_ports_mode()
    win.add_line_resonator(label='TL1', pos=(0.0, 0.0), FSR=1.5, Ztx=65.0,
                           f_max=6.0, port_end='xL')
    win._enter_scattering_mode()
    panel = win.properties_panel
    panel._update_scattering_ports_table()
    panel.freq_center_spin.setValue(4.5)
    panel.freq_span_spin.setValue(3.0)
    panel.freq_points_spin.setValue(41)
    panel._check_truncation()
    assert panel._truncation_result < 1e-10, panel._truncation_result
    # ...and is NOT small with the raw comb: the check measures the truth
    panel.tail_closure_check.setChecked(False)
    panel._check_truncation()
    assert panel._truncation_result > 1e-2, panel._truncation_result
