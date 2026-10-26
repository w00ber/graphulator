"""Configured defaults for ports, lines/txlines and their wires.

"How do I set the default properties of a port and a port-node wire?" used
to have no answer but editing module constants: the Settings dialog had no
tab for them, nothing read a config value at creation time, and
Paragraphulator did not even remember the last glyph placed. These cover
the new Port & Wire Defaults surface in both apps, the draw-time wire
default (so changing it restyles unoverridden wires), and the placement
memory. Headless (offscreen Qt + Agg).
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
    """Graphulator, with its config restored after the test."""
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    import graphulator.graphulator_qt as gq
    from graphulator import graphulator_config as config

    w = gq.Graphulator()
    w.last_graph_path = tmp_path / "last.graph"
    w.recent_files_path = tmp_path / "recent"
    saved = {k: getattr(config, k) for k in dir(config)
             if k.startswith(('DEFAULT_PORT', 'DEFAULT_TXLINE',
                              'DEFAULT_WIRE', 'GLYPH_ROTATION'))}
    yield w, config
    for key, value in saved.items():
        setattr(config, key, value)


@pytest.fixture()
def para(tmp_path):
    """Paragraphulator, with its config restored after the test."""
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    import graphulator.graphulator_para as gp
    from graphulator import graphulator_para_config as config

    w = gp.Graphulator()
    w.last_graph_path = tmp_path / "last.pgraph"
    w.recent_files_path = tmp_path / "recent"
    saved = {k: getattr(config, k) for k in dir(config)
             if k.startswith(('DEFAULT_PORT', 'DEFAULT_LINE',
                              'DEFAULT_WIRE', 'DEFAULT_ATTACHMENT',
                              'DEFAULT_TAP', 'GLYPH_ROTATION'))}
    yield w, config
    for key, value in saved.items():
        setattr(config, key, value)


def add_node(w, label, pos):
    node = {'node_id': w.node_id_counter, 'label': label, 'pos': pos,
            'color': '#6699ff', 'color_key': 'BLUE', 'node_size_mult': 1.0,
            'label_size_mult': 1.0, 'conj': False,
            'nodelabelnudge': (0.0, 0.0)}
    w.nodes.append(node)
    w.node_id_counter += 1
    return node


# ---------------------------------------------------------------------------
# the settings surface exists in both apps
# ---------------------------------------------------------------------------

def test_both_settings_tabs_expose_the_fixed_port_geometry():
    """The nose depth and the lead length are user options now: they used
    to be module constants, and the nose silently scaled with the body."""
    from graphulator import graphulator_config as qt_config
    from graphulator import graphulator_para as gp
    from graphulator import graphulator_para_config as para_config

    wanted = {'DEFAULT_PORT_APEX_DEPTH', 'DEFAULT_PORT_LEAD_LENGTH'}
    for table, module in ((qt_config.SETTINGS_PARAMS, qt_config),
                          (gp.SETTINGS_PARAMS, para_config)):
        names = {row[0] for row in table['Port & Wire Defaults']}
        assert wanted <= names
        assert all(hasattr(module, name) for name in wanted)
    # both are read at draw time, so a change restyles the open graph
    assert wanted <= set(qt_config.LIVE_PARAMS)
    assert wanted <= set(gp.LIVE_PARAMS)


def test_graphulator_settings_has_a_port_and_wire_tab():
    from graphulator import graphulator_config as config
    rows = config.SETTINGS_PARAMS['Port & Wire Defaults']
    names = {row[0] for row in rows}
    assert {'DEFAULT_PORT_LINEWIDTH', 'DEFAULT_PORT_FILL',
            'DEFAULT_WIRE_COLOR', 'DEFAULT_WIRE_LINEWIDTH_MULT',
            'DEFAULT_WIRE_LINESTYLE'} <= names
    # every row must name a parameter the config module actually has, or
    # the dialog builds a widget bound to nothing
    assert all(hasattr(config, row[0]) for row in rows)


def test_para_settings_has_a_port_and_wire_tab():
    from graphulator import graphulator_para as gp
    from graphulator import graphulator_para_config as config
    rows = gp.SETTINGS_PARAMS['Port & Wire Defaults']
    names = {row[0] for row in rows}
    assert {'DEFAULT_PORT_LINEWIDTH', 'DEFAULT_PORT_FILL',
            'DEFAULT_WIRE_COLOR', 'DEFAULT_ATTACHMENT_RATE',
            'DEFAULT_TAP_RATE'} <= names
    assert all(hasattr(config, row[0]) for row in rows)


# ---------------------------------------------------------------------------
# Graphulator: a new glyph / wire reads them
# ---------------------------------------------------------------------------

def test_a_new_port_takes_the_configured_appearance(win):
    w, config = win
    config.DEFAULT_PORT_LINEWIDTH = 3.5
    config.DEFAULT_PORT_COLOR = '#112233'
    config.DEFAULT_PORT_FILL = '#aabbcc'
    port = w.add_port()
    assert port['linewidth'] == pytest.approx(3.5)
    assert (port['color'], port['fill']) == ('#112233', '#aabbcc')


def test_an_explicit_argument_still_beats_the_default(win):
    w, config = win
    config.DEFAULT_PORT_FILL = '#aabbcc'
    assert w.add_port(fill='red')['fill'] == 'red'


def test_a_new_txline_takes_the_configured_appearance(win):
    w, config = win
    config.DEFAULT_TXLINE_LINEWIDTH = 0.75
    config.DEFAULT_TXLINE_FILL = '#654321'
    cx = w.add_txline()
    assert cx['linewidth'] == pytest.approx(0.75)
    assert cx['fill'] == '#654321'


def test_auto_orient_off_by_default_pins_a_new_port(win):
    w, config = win
    config.DEFAULT_PORT_AUTO_ORIENT = False
    assert w.add_port()['angle_pinned'] is True
    config.DEFAULT_PORT_AUTO_ORIENT = True
    assert w.add_port()['angle_pinned'] is False


def test_a_new_wire_takes_the_configured_width_and_style(win):
    w, config = win
    config.DEFAULT_WIRE_LINEWIDTH_MULT = 2.5
    config.DEFAULT_WIRE_LINESTYLE = ':'
    node = add_node(w, 'A', (0.0, 0.0))
    conn = w.connect_port_to_node(w.add_port(), node)
    assert conn['linewidth_mult'] == pytest.approx(2.5)
    assert conn['linestyle'] == ':'


def test_the_wire_color_default_is_read_at_draw_time(win):
    """An unset color must follow the setting, so changing it restyles
    every wire that has no override of its own."""
    w, config = win
    node = add_node(w, 'A', (0.0, 0.0))
    conn = w.connect_port_to_node(w.add_port(), node)
    assert conn['color'] is None

    config.DEFAULT_WIRE_COLOR = 'magenta'
    assert w.wire_style(conn)[0] == 'magenta'
    # an explicit override still wins
    conn['color'] = 'teal'
    assert w.wire_style(conn)[0] == 'teal'


def test_a_configured_wire_color_survives_the_code_export(win):
    """The exported script calls the primitives directly and knows nothing
    about this session's settings, so a wire riding on a configured default
    has to be written out explicitly."""
    w, config = win
    config.DEFAULT_WIRE_COLOR = '#ff00ff'
    node = add_node(w, 'A', (0.0, 0.0))
    port = w.add_port(pos=(-4.0, 0.0))
    conn = w.connect_port_to_node(port, node)
    args, _per_wire = w._export_wire_style_args(conn)
    assert ('color', repr('#ff00ff')) in args


def test_changing_the_defaults_resets_the_placement_memory(win):
    """Otherwise the next glyph inherits the last one placed and the
    changed setting never shows up."""
    w, _config = win
    import graphulator.graphulator_qt as gq
    w.last_port_props = {'color': 'red'}
    w.last_txline_props = {'color': 'red'}
    gq.sync_dialog_defaults_from_config(w)
    assert w.last_port_props is None and w.last_txline_props is None


# ---------------------------------------------------------------------------
# Paragraphulator: a new glyph / link / wire reads them
# ---------------------------------------------------------------------------

def test_a_new_para_port_takes_the_configured_appearance(para):
    w, config = para
    config.DEFAULT_PORT_LINEWIDTH = 3.5
    config.DEFAULT_PORT_COLOR = '#112233'
    config.DEFAULT_PORT_FILL = '#aabbcc'
    port = w.add_port()
    assert port['linewidth'] == pytest.approx(3.5)
    assert (port['color'], port['fill']) == ('#112233', '#aabbcc')


def test_a_new_para_port_can_default_to_a_loss_hub(para):
    w, config = para
    config.DEFAULT_PORT_MONITORED = False
    assert w.add_port()['monitored'] is False
    # an explicit argument still wins
    assert w.add_port(monitored=True)['monitored'] is True


def test_a_new_line_takes_the_configured_appearance(para):
    w, config = para
    config.DEFAULT_LINE_LINEWIDTH = 0.75
    config.DEFAULT_LINE_FILL = '#654321'
    line = w.add_line_resonator(port_end=None)
    assert line['linewidth'] == pytest.approx(0.75)
    assert line['fill'] == '#654321'


def test_a_new_attachment_takes_the_configured_rate(para):
    w, config = para
    config.DEFAULT_ATTACHMENT_RATE = 250.0
    node = add_node(w, 'A', (0.0, 0.0))
    att = w.add_port_attachment(w.add_port(), node)
    assert att['rate'] == pytest.approx(0.25)


def test_a_new_tap_takes_the_configured_rate(para):
    w, config = para
    config.DEFAULT_TAP_RATE = 50.0
    node = add_node(w, 'A', (0.0, 0.0))
    w.scattering_assignments[node['node_id']] = {'freq': 5.0, 'B_int': 0.0}
    line = w.add_line_resonator(port_end=None, FSR=1.0, f_max=8.0)
    conn = w.connect_line_end_to_node(line, 'xL', node)
    assert conn['rate'] == pytest.approx(0.05)


def test_the_para_wire_color_defaults_track_the_sign(para):
    w, config = para
    config.DEFAULT_WIRE_COLOR = 'navy'
    config.DEFAULT_WIRE_COLOR_INVERTED = 'crimson'
    config.DEFAULT_WIRE_COLOR_TAP = 'olive'
    assert w.wire_default_color('port', 1) == 'navy'
    assert w.wire_default_color('port', -1) == 'crimson'
    assert w.wire_default_color('tap') == 'olive'
    # and an unset color on a link follows them
    assert w.wire_style({'sign': -1})[0] == 'crimson'
    assert w.wire_style({'sign': 1, 'color': 'teal'})[0] == 'teal'


def test_the_para_wire_width_default_is_read_at_draw_time(para):
    w, config = para
    config.DEFAULT_WIRE_LINEWIDTH_MULT = 3.0
    wide = w.wire_style({})[1]
    config.DEFAULT_WIRE_LINEWIDTH_MULT = 1.0
    assert wide > w.wire_style({})[1]


# ---------------------------------------------------------------------------
# Paragraphulator: the placement memory
# ---------------------------------------------------------------------------

class FakePortDialog:
    """Records how it was seeded and returns a canned result."""
    seen = None
    result = None

    def __init__(self, default_label='P1', monitored=True, parent=None,
                 editing=False, port=None):
        FakePortDialog.seen = dict(port or {})
        self._monitored = monitored

    def exec(self):
        from PySide6.QtWidgets import QDialog
        return QDialog.Accepted

    def get_result(self):
        result = {'label': 'P1', 'monitored': self._monitored,
                  'auto_orient': True}
        result.update(FakePortDialog.result or {})
        return result


def place_port(para_win, monkeypatch, **result):
    from graphulator.para_features import explicit_ports as ep
    FakePortDialog.result = result
    monkeypatch.setattr(ep, 'PortInputDialog', FakePortDialog)
    para_win.placement_mode = 'port'
    para_win._on_click_port_placement(
        types.SimpleNamespace(xdata=0.0, ydata=0.0, button=1))
    return para_win.ports[-1]


def test_a_fresh_port_dialog_is_seeded_from_the_config(para, monkeypatch):
    w, config = para
    config.DEFAULT_PORT_FILL = '#aabbcc'
    place_port(w, monkeypatch)
    assert FakePortDialog.seen['fill'] == '#aabbcc'


def test_the_next_port_is_seeded_from_the_last_one_placed(para, monkeypatch):
    w, _config = para
    place_port(w, monkeypatch, fill='#123456', linewidth=4.0)
    assert w.last_port_props['fill'] == '#123456'
    # the label and the port/hub choice are deliberately not remembered:
    # one auto-increments, the other has its own action
    assert 'label' not in w.last_port_props
    assert 'monitored' not in w.last_port_props

    place_port(w, monkeypatch)
    assert FakePortDialog.seen['fill'] == '#123456'
    assert FakePortDialog.seen['linewidth'] == pytest.approx(4.0)


def test_placing_a_loss_hub_still_overrides_the_default(para, monkeypatch):
    w, config = para
    config.DEFAULT_PORT_MONITORED = True
    w._place_loss_hub_next = True
    hub = place_port(w, monkeypatch)
    assert hub['monitored'] is False
    # and the flag is consumed, so the next one is an ordinary port again
    assert w._place_loss_hub_next is False


def test_a_line_placement_dialog_is_not_an_edit_dialog(para):
    """Seeding a PLACEMENT dialog from the memory must not retitle it or
    hide the "terminate end with port" row."""
    from graphulator.para_features.explicit_ports import LineInputDialog
    dialog = LineInputDialog(default_label='TL7', parent=para[0],
                             defaults={'FSR': 2.5, 'Ztx': 42.0})
    assert dialog.windowTitle() == "Place Transmission Line"
    assert dialog.port_end_combo is not None
    assert dialog.fsr_spin.value() == pytest.approx(2.5)
    assert dialog.ztx_spin.value() == pytest.approx(42.0)
