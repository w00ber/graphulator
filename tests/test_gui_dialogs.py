"""Every dialog in the explicit-ports module actually CONSTRUCTS.

Why this file exists: 77e4cf7 deleted the shared helpers
`_add_appearance_rows` / `_appearance_result` (and `_color_button` /
`_mult_spin` under them) while leaving their call sites in
PortInputDialog and LineInputDialog. From that commit on, placing a port
or a transmission line raised

    NameError: name '_add_appearance_rows' is not defined

and the whole suite stayed green, because nothing ever built a dialog --
the tests drive the model through win.add_port / win.add_line_resonator,
which bypass the UI entirely. A NameError in a widget constructor is
exactly the class of break unit tests miss and a user hits on the first
click, so each dialog is instantiated here and read back.

These are construction and round-trip gates, not interaction tests: no
exec(), no event loop. They would have caught the above.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")

from graphulator.autograph import LineResonator  # noqa: E402
from graphulator.para_features import explicit_ports as ep  # noqa: E402
from tests.test_gui_hubs import para  # noqa: E402,F401


def test_shared_dialog_helpers_exist():
    """The helpers the dialogs call are module-level and callable. Pinned
    by name: the call sites outlived the definitions once already."""
    for name in ('_color_button', '_mult_spin', '_add_appearance_rows',
                 '_appearance_result'):
        assert callable(getattr(ep, name, None)), name


def test_port_dialog_builds_and_round_trips(para):
    gp, win, config = para
    fresh = ep.PortInputDialog(default_label='P7', parent=None)
    out = fresh.get_result()
    assert out['label'] == 'P7' and out['monitored'] is True
    for key in ('w_mult', 'h_mult', 'linewidth', 'color', 'fill'):
        assert key in out, key

    port = {'label': 'Pa', 'monitored': False, 'w_mult': 1.3, 'h_mult': 0.8,
            'linewidth': 3.0, 'color': 'indianred', 'fill': 'white',
            'angle': 90.0, 'angle_pinned': True}
    edit = ep.PortInputDialog(default_label='Pa', monitored=False,
                              editing=True, port=port)
    got = edit.get_result()
    assert got['label'] == 'Pa' and got['monitored'] is False
    assert got['w_mult'] == pytest.approx(1.3)
    assert got['h_mult'] == pytest.approx(0.8)
    assert got['linewidth'] == pytest.approx(3.0)


@pytest.mark.parametrize('sections', [
    None,
    [{'Z': 47.3, 'frac': 2 / 3}, {'Z': 51.4, 'frac': 1 / 3}],
])
def test_line_dialog_builds_and_round_trips(sections):
    """The reported break: placing a line opened this dialog."""
    fresh = ep.LineInputDialog(default_label='TL3')
    out = fresh.get_result()
    assert out['label'] == 'TL3'
    assert out['sections'] is None                 # uniform by default
    for key in ('FSR', 'Ztx', 'f_max', 'load', 'Z0_port', 'alpha_uniform',
                'end_coupling', 'w_mult', 'h_mult', 'linewidth', 'color',
                'fill'):
        assert key in out, key

    line = {'label': 'TL', 'FSR': 1.25, 'Ztx': 65.0, 'f_max': 8.0,
            'Z0_port': 50.0, 'alpha_uniform': 0.0, 'port_end': 'xL',
            'end_coupling': {'x0': 'inductive', 'xL': 'capacitive'},
            'load': {'end': 'x0', 'type': 'inductive', 'f_Z': 3.0},
            'sections': sections, 'w_mult': 1.0, 'h_mult': 1.0,
            'linewidth': 1.6, 'color': 'black', 'fill': '#cccccc'}
    edit = ep.LineInputDialog(line=line)
    got = edit.get_result()
    assert got['FSR'] == pytest.approx(1.25)
    assert got['Ztx'] == pytest.approx(65.0)
    assert got['load'] == line['load']
    if sections is None:
        assert got['sections'] is None
    else:                       # text round-trip: exact to the printed digits
        assert [x['Z'] for x in got['sections']] == [x['Z'] for x in sections]
        for a, b in zip(got['sections'], sections):
            assert a['frac'] == pytest.approx(b['frac'], abs=1e-11)
    assert got['end_coupling'] == line['end_coupling']
    # the live preview ran without raising and says something useful
    assert edit.load_status.text()
    # and the target-resonance solver works through the dialog
    edit.target_spin.setValue(2.0)
    edit.target_mode_spin.setValue(1)
    edit._solve_fsr()
    probe = LineResonator(line_id='p', FSR=edit.fsr_spin.value(), Ztx=65.0,
                          f_max=8.0, load=line['load'], sections=sections)
    assert probe.mode_freq(1) == pytest.approx(2.0, rel=1e-9)


def test_tap_dialog_builds_and_round_trips():
    d = ep.TapInputDialog(line_label='TL', node_label='a', end='x0',
                          coupling='capacitive', N=12, n_nearest=3,
                          rate_mau=75.0, sign=-1)
    out = d.get_result()
    assert out['rate'] == pytest.approx(0.075)       # mau -> a.u.
    assert out['sign'] == -1 and out['n_ref'] == 3


def test_pump_dialog_builds_and_round_trips():
    res = LineResonator(line_id='TL', label='TL', FSR=1.5, Ztx=65.0,
                        f_max=9.0, port_end='xL')
    d = ep.PumpInputDialog(line_label='TL', resonator=res, end='x0',
                           f_p=9.0, rate_mau=50.0, phase=30.0, n_ref=3)
    out = d.get_result()
    assert out['f_p'] == pytest.approx(9.0)
    assert out['rate'] == pytest.approx(0.050)       # mau -> a.u.
    assert out['phase'] == pytest.approx(30.0)
    assert out['n_ref'] == 3
    assert out['coupling'] == 'inductive'
    assert out['FSR'] == pytest.approx(1.5)


def test_attachment_dialog_builds_and_round_trips():
    d = ep.AttachmentEditDialog(port_label='P1', node_label='a',
                                rate_mau=120.0, sign=1)
    out = d.get_result()
    assert out['rate_mau'] == pytest.approx(120.0) and out['sign'] == 1
    # (this one really does report mau; the others convert -- pinned so the
    # inconsistency is visible rather than tripping the next caller)


def test_every_dialog_class_is_covered():
    """If a dialog is added to the module, it gets a gate here too."""
    import inspect

    from PySide6.QtWidgets import QDialog
    classes = {name for name, obj in vars(ep).items()
               if inspect.isclass(obj) and issubclass(obj, QDialog)
               and obj.__module__ == ep.__name__}
    assert classes == {'PortInputDialog', 'LineInputDialog', 'TapInputDialog',
                       'PumpInputDialog', 'AttachmentEditDialog'}, classes


# ---------------------------------------------------------------------------
# the click path from the traceback, end to end
# ---------------------------------------------------------------------------

class _Click:
    """The attributes the placement handlers read off a matplotlib event."""

    def __init__(self, win, x=1.0, y=2.0):
        self.xdata, self.ydata = x, y
        self.inaxes = win.canvas.ax
        self.button = 1


@pytest.fixture()
def auto_accept(monkeypatch):
    """Accept the modal dialogs so placement completes without an event loop."""
    from PySide6.QtWidgets import QDialog
    for cls in (ep.LineInputDialog, ep.PortInputDialog):
        monkeypatch.setattr(cls, 'exec', lambda self: QDialog.Accepted)


def test_placing_a_line_and_a_port_runs_end_to_end(para, auto_accept):
    """_on_click_line_placement -> LineInputDialog(...) is exactly the frame
    that raised NameError for the user. Drive it, don't just import it."""
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = True
    win._apply_explicit_ports_mode()

    win.placement_mode = 'line'
    win._on_click_line_placement(_Click(win))
    assert len(win.line_resonators) == 1
    line = win.line_resonators[0]
    assert line['label'] == 'TL1' and line['sections'] is None

    n_ports = len(win.ports)
    win.placement_mode = 'port'
    win._on_click_port_placement(_Click(win, 4.0, 2.0))
    assert len(win.ports) == n_ports + 1

    win._update_plot()                      # the glyphs draw too


def test_placing_a_line_then_editing_it_keeps_it_valid(para, auto_accept):
    """The edit path shares the dialog; a break there is the same class of
    bug, just one click later."""
    gp, win, config = para
    config.EXPLICIT_PORTS_MODE = True
    win._apply_explicit_ports_mode()
    win.placement_mode = 'line'
    win._on_click_line_placement(_Click(win))
    line = win.line_resonators[0]
    before = dict(line)
    win._edit_line(line)                    # dialog accepted by the fixture
    assert line['FSR'] == pytest.approx(before['FSR'])
    assert line['Ztx'] == pytest.approx(before['Ztx'])
    assert line['sections'] == before['sections']
    LineResonator(**ep.line_payload(line))  # still a valid macro


# ---------------------------------------------------------------------------
# the scattering-parameter dialogs (double-click a node / edge)
# ---------------------------------------------------------------------------
#
# Same coverage hole as the placement dialogs, found by pyflakes rather than
# by a user: _edit_scattering_node_parameters referenced an undefined
# `original_node` inside its self-loop check, and both dialogs passed
# `original_node` / `original_edge` to the row-scroller on accept. Three
# live NameErrors, invisible to a suite that never opened them.


def _two_node_graph(win):
    from tests.test_gui_hubs import add_node
    a = add_node(win, 0, 'a', -2.0, freq=5.0)
    b = add_node(win, 1, 'b', 2.0, freq=6.0)
    edge = {'from_node_id': 0, 'to_node_id': 1, 'from_node': a,
            'to_node': b, 'is_self_loop': False, 'linewidth_mult': 1.0,
            'selfloopangle': 30.0, 'selfloopscale': 1.0, 'flip': False,
            'angle_pinned': False}
    win.edges.append(edge)
    win.scattering_assignments[(0, 1)] = {'f_p': 0.0, 'rate': 0.05,
                                          'phase': 0.0}
    return a, b, edge


def _self_loop(win, node):
    loop = {'from_node_id': node['node_id'], 'to_node_id': node['node_id'],
            'from_node': node, 'to_node': node, 'is_self_loop': True,
            'linewidth_mult': 1.0, 'selfloopangle': 30.0,
            'selfloopscale': 1.0, 'flip': False, 'angle_pinned': False}
    win.edges.append(loop)
    return loop


@pytest.fixture()
def reject_dialogs(monkeypatch):
    """Open the dialogs but decline, so the constructor path runs without
    committing edits (the accept branch is exercised separately)."""
    from PySide6.QtWidgets import QDialog
    monkeypatch.setattr(QDialog, 'exec', lambda self: QDialog.Rejected)


@pytest.fixture()
def accept_dialogs(monkeypatch):
    from PySide6.QtWidgets import QDialog
    monkeypatch.setattr(QDialog, 'exec',
                        lambda self: QDialog.DialogCode.Accepted)


def test_scattering_node_dialog_opens(para, reject_dialogs):
    gp, win, config = para
    a, _, _ = _two_node_graph(win)
    win._edit_scattering_node_parameters(a)       # raised NameError


def test_scattering_node_dialog_finds_a_self_loop(para, reject_dialogs):
    """The check must match on the stable node_id against the ORIGINAL
    edges: a scattering-graph node is a copy, so comparing dicts would
    silently report 'no self-loop' and hide the B_ext field."""
    gp, win, config = para
    a, _, _ = _two_node_graph(win)
    _self_loop(win, a)
    win._original_edges_for_lookup = list(win.edges)
    copy_of_a = dict(a)                            # what the scattering graph holds
    copy_of_a['pos'] = (99.0, 99.0)                # ... and it is NOT the same dict
    win._edit_scattering_node_parameters(copy_of_a)
    assert any(e.get('is_self_loop') and e['from_node_id'] == a['node_id']
               for e in win._original_edges_for_lookup)


def test_scattering_edge_dialog_opens(para, reject_dialogs):
    gp, win, config = para
    _, _, edge = _two_node_graph(win)
    win._edit_scattering_edge_parameters(edge)


def test_scattering_dialogs_commit_and_scroll(para, accept_dialogs):
    """The accept branch calls _scroll_to_node_row / _scroll_to_edge_row --
    both were handed undefined names."""
    gp, win, config = para
    a, _, edge = _two_node_graph(win)
    win._edit_scattering_node_parameters(a)
    assert 'freq' in win.scattering_assignments[0]
    win._edit_scattering_edge_parameters(edge)
    key = next(k for k in win.scattering_assignments if isinstance(k, tuple))
    assert 'rate' in win.scattering_assignments[key]


def test_no_undefined_names_in_the_package():
    """The sweep, kept executable. pyflakes' undefined-name check is exactly
    the NameError-at-runtime class that cost three bugs here; run it over
    the shipped package so the next one fails in CI, not on a click."""
    pyflakes = pytest.importorskip("pyflakes.api")
    import io
    import pathlib

    from pyflakes.reporter import Reporter

    root = pathlib.Path(__file__).resolve().parent.parent / 'src' / 'graphulator'
    out, err = io.StringIO(), io.StringIO()
    reporter = Reporter(out, err)
    for path in sorted(root.rglob('*.py')):
        pyflakes.checkPath(str(path), reporter)
    undefined = [ln for ln in out.getvalue().splitlines()
                 if 'undefined name' in ln]
    assert not undefined, "\n".join(undefined)
