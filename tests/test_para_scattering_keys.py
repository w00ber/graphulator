"""App-level tests: scattering assignments use stable keys and survive
save/load and undo.

These require a working Qt platform (they instantiate the Paragraphulator
main window). They skip automatically in environments where the GUI can't
start; run them under a display or `xvfb-run` to include them.
"""

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    # QtWebEngine refuses to sandbox as root (CI containers)
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")

PGRAPH = os.path.join(os.path.dirname(__file__), os.pardir,
                      "misc", "PGRAPH_TESTS", "CIRC_FULL_SCATT.pgraph")


@pytest.fixture(scope="module")
def para_window():
    try:
        from PySide6.QtWidgets import QApplication
        import graphulator.graphulator_para as gp
    except ImportError as exc:
        pytest.skip(f"GUI stack unavailable: {exc}")
    app = QApplication.instance() or QApplication([])
    try:
        win = gp.Graphulator()
    except Exception as exc:  # e.g. no usable Qt platform plugin
        pytest.skip(f"Could not create main window: {exc}")
    win._open_graph_file(os.path.abspath(PGRAPH))
    return gp, win


def test_assignments_use_stable_keys(para_window):
    gp, win = para_window
    assert win.scattering_assignments
    node_keys = {gp._node_key(n) for n in win.nodes}
    edge_keys = {gp._edge_key(e) for e in win.edges}
    for key in win.scattering_assignments:
        assert isinstance(key, (int, tuple))
        assert key in node_keys or key in edge_keys


def test_assignments_survive_serialize_round_trip(para_window):
    gp, win = para_window
    before = {k: dict(v) for k, v in win.scattering_assignments.items()}

    data = json.loads(json.dumps(win._serialize_graph()))  # simulate disk
    win._deserialize_graph(data)
    after = win.scattering_assignments

    assert set(after) == set(before)
    port_keys = {gp._node_key(e['from_node'])
                 for e in win.edges if e.get('is_self_loop')}
    for key, params in before.items():
        restored = dict(after[key])
        expected = dict(params)
        # the serializer intentionally nulls B_ext for non-port nodes
        if isinstance(key, int) and key not in port_keys:
            restored.pop('B_ext', None)
            expected.pop('B_ext', None)
        assert restored == expected


def test_assignments_survive_undo(para_window):
    gp, win = para_window
    node = win.nodes[0]
    key = gp._node_key(node)
    assert key in win.scattering_assignments
    before = dict(win.scattering_assignments[key])

    win._save_state()
    node['pos'] = (123.0, 456.0)
    del win.scattering_assignments[key]

    win._undo()
    assert dict(win.scattering_assignments[key]) == before

    win._redo()
    assert key not in win.scattering_assignments
    win._undo()  # leave the fixture in a sane state
