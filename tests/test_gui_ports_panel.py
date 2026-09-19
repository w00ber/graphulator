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
    # and the comb note says so (flush deleteLater()'d labels from table
    # rebuilds first, so only the live notes are inspected)
    from PySide6.QtWidgets import QLabel
    from PySide6.QtCore import QCoreApplication, QEvent

    def live_notes():
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        return [w.text() for w in panel.ports_param_widget.findChildren(QLabel)
                if 'N = ' in w.text()]

    notes = live_notes()
    assert notes and all('raw truncated comb' in n for n in notes), notes
    panel.tail_closure_check.setChecked(True)
    notes = live_notes()
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


def test_glyph_only_graph_saves_its_sweep_window(para, tmp_path):
    """A pumped line has no GUI edges, so its spanning tree is empty; the
    scattering section (sweep window, injection choice) must still be saved
    -- it used to be gated on a non-empty tree and was silently dropped."""
    import json
    win, line = _pumped_scene(para)
    panel = win.properties_panel
    panel.freq_center_spin.setValue(4.25)
    panel.freq_span_spin.setValue(2.5)
    panel.freq_points_spin.setValue(333)
    path = tmp_path / "amp.pgraph"
    assert win._save_graph_to_file(str(path))
    data = json.loads(path.read_text())
    assert data['scattering']['frequency'] == {'center': 4.25, 'span': 2.5,
                                               'points': 333}


def test_ports_panel_appears_on_entering_scattering_mode(para, monkeypatch):
    """The REAL flow: open a glyph-only scene, press Ctrl+R. Nothing else.
    The Nodes table's early 'no nodes' return used to skip the Ports & Lines
    sync entirely, so the pane stayed hidden and empty (splitter [h, 0])."""
    from PySide6.QtWidgets import QApplication, QMessageBox
    gp, win, config = para
    monkeypatch.setattr(QMessageBox, 'warning',
                        staticmethod(lambda *a, **k: pytest.fail(str(a[1:]))))
    monkeypatch.setattr(QMessageBox, 'information',
                        staticmethod(lambda *a, **k: None))
    win.resize(1600, 1100)
    win.show()
    QApplication.processEvents()
    win._load_example(SCENES / "LINE_PUMPED_AMP_AND_CONV.pgraph")
    QApplication.processEvents()
    win._enter_scattering_mode()                 # Ctrl+R, and nothing more
    QApplication.processEvents()

    panel = win.properties_panel
    assert panel.ports_param_layout.count() > 0, "Ports & Lines never built"
    assert panel.ports_frame.isVisibleTo(panel)
    splitter = panel.ports_frame.parent()
    assert splitter.sizes()[-1] > 0, splitter.sizes()
    # and the pump controls are there without any node in the graph
    assert not win.nodes
    assert any('Pump frequency' in s.toolTip() for s in _spins(panel))


def test_pump_partner_label_explains_the_pair(para):
    """The reference pair is a DEFINITION point for the rate, not a
    selector; the label must say which pair, at what frequencies, and how
    far it is from the pump's resonance condition."""
    from graphulator.para_features.explicit_ports import describe_pump_pair
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = True
    win._apply_explicit_ports_mode()
    line = win.add_line_resonator(label='TL1', pos=(0.0, 2.0), FSR=0.5,
                                  Ztx=65.0, f_max=9.0, port_end='xL')
    win.set_line_pump(line, 'x0', f_p=4.5, rate=0.05, n_ref=4,
                      twin_pos=(0.0, -2.0))
    text = win.pump_pair_description(line)
    assert 'm = 5' in text and 'amplification' in text and 'on resonance' in text
    assert '2 + 2.5' in text.replace('\N{MINUS SIGN}', '-')
    # a pump below the reference mode names the CONVERSION partner
    line['pump']['f_p'] = 1.0
    text = win.pump_pair_description(line)
    assert 'conversion' in text and 'm = 2' in text        # 2.0 - 1.0 = 1.0
    # degenerate case
    assert 'degenerate' in describe_pump_pair(3, 3, 1.5, 1.5, 3.0)


def test_pump_row_labels_units_and_shows_the_modulation_depth(para):
    """Every pump box says what it is in. The brackets were dropped from
    [mau]/[au] to buy horizontal space, but the units themselves stay."""
    from PySide6.QtWidgets import QLabel
    win, line = _pumped_scene(para)
    panel = win.properties_panel
    texts = [w.text() for w in panel.ports_param_widget.findChildren(QLabel)]
    assert 'mau' in texts, texts            # the rate
    assert 'au' in texts                    # f_p
    assert '\N{DEGREE SIGN}' in texts      # the phase
    eps, symbol = win.pump_modulation_fraction(line)
    assert any(symbol in t and '%' in t for t in texts), texts


def test_pump_section_fits_without_horizontal_scrolling(para):
    """The pane must follow the splitter so the plot can keep half the
    window. One wide strip of header + four spinboxes + the full pair
    description pushed the minimum past 1400 px and forced a horizontal
    scrollbar; the three-row split has to stay well inside a half-window
    pane."""
    from PySide6.QtWidgets import QApplication
    win, line = _pumped_scene(para)
    win.resize(1800, 1100)
    win.show()
    QApplication.processEvents()
    panel = win.properties_panel
    need = panel.ports_param_widget.minimumSizeHint().width()
    assert need <= 700, need
    # and the wrapped description really does wrap rather than widen
    from PySide6.QtWidgets import QLabel
    desc = panel._pump_partner_label
    assert isinstance(desc, QLabel) and desc.wordWrap()
    assert desc.minimumSizeHint().width() < 400, desc.minimumSizeHint().width()


def test_alpha_is_reported_and_flagged_past_its_limit(para):
    from PySide6.QtWidgets import QLabel
    from graphulator.para_features.explicit_ports import PUMP_ALPHA_LIMIT
    win, line = _pumped_scene(para)
    panel = win.properties_panel

    alpha, over = win.pump_alpha(line)
    assert not over and alpha < PUMP_ALPHA_LIMIT
    assert '\N{GREEK SMALL LETTER ALPHA} =' in panel._pump_modulation_label.text()
    assert panel._pump_rate_spin.styleSheet() == ''

    # drive it past the limit: the label turns dark red and the rate box
    # takes a translucent red wash
    res = win.line_resonator_for(line)
    n_ref, m_ref = win._pump_reference_pair(line)
    over_rate = 2.5 * np.sqrt(res.mode_freq(n_ref) * res.mode_freq(m_ref))
    panel._pump_rate_spin.setValue(over_rate * 1000.0)
    alpha, over = win.pump_alpha(line)
    assert over and alpha >= PUMP_ALPHA_LIMIT
    text = panel._pump_modulation_label.text()
    assert '\N{WARNING SIGN}' in text and 'unphysical' in text
    assert '8b0000' in panel._pump_modulation_label.styleSheet()
    assert 'rgba(200, 0, 0, 0.25)' in panel._pump_rate_spin.styleSheet()

    # and it clears again when brought back under
    panel._pump_rate_spin.setValue(50.0)
    assert panel._pump_rate_spin.styleSheet() == ''


def test_line_attenuation_is_labelled_alpha_loss(para):
    """Two different alphas in adjacent rows would be misread."""
    from PySide6.QtWidgets import QLabel
    win, line = _pumped_scene(para)
    panel = win.properties_panel
    texts = [w.text() for w in panel.ports_param_widget.findChildren(QLabel)]
    assert '\N{GREEK SMALL LETTER ALPHA}_loss' in texts, texts
