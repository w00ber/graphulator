"""Layer 0 step 3, slice 1: Paragraphulator file I/O goes through the model.

Open: any pgraph (2.0/3.0/4.0) -> model.from_dict -> to_legacy -> the GUI
loader. Save: the GUI state -> model.from_legacy -> a 4.0 file.
File > Save Legacy 3.0 Copy writes the old layout for older builds.

Gates, for every shipped file:
- opening through the model leaves the GUI in the same state as opening the
  raw file did (same _serialize_graph(), same Show S jobs);
- a GUI save is a valid 4.0 file, and reopening it reproduces that state;
- 4.0-only settings (sector window, units) survive Open -> Save in the GUI.
"""
import contextlib
import copy
import glob
import io
import json
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")

from graphulator import model as M  # noqa: E402
from tests.snap_helpers import snap_legacy  # noqa: E402


def _norm(job):
    """A job with its id()-keyed assignments re-keyed by position (as in
    test_model_legacy_job), so jobs from different dicts compare with ==."""
    j = dict(job)
    sa = j.pop("scattering_assignments")
    j["node_sa"] = [sa.get(id(n)) for n in j["nodes"]]
    j["edge_sa"] = [sa.get(id(e)) for e in j["edges"]]
    j["f_root_s"] = np.asarray(j["f_root_s"]).tolist()
    j["freq_start"], j["freq_stop"] = float(j["freq_start"]), float(j["freq_stop"])
    return j

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = sorted(glob.glob(os.path.join(ROOT, "examples", "**", "*.pgraph"), recursive=True)
               + glob.glob(os.path.join(ROOT, "src", "graphulator", "examples", "**", "*.pgraph"),
                           recursive=True))
IDS = [os.path.relpath(f, ROOT) for f in FILES]
PG = os.path.join(ROOT, "examples", "pgraphs")


@pytest.fixture()
def window():
    try:
        from PySide6.QtWidgets import QApplication
        _app = QApplication.instance() or QApplication([])
        import graphulator.graphulator_para as gp
    except ImportError as exc:
        pytest.skip(f"GUI stack unavailable: {exc}")
    try:
        return gp.Graphulator()       # not closed: see test_model_legacy_job
    except Exception as exc:
        pytest.skip(f"Could not create main window: {exc}")


def _raw(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _quiet(fn, *a):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a)


def _state(win):
    """What the GUI holds, as its serializer writes it, minus the thumbnail
    (a rendering of that state, not part of it)."""
    d = _quiet(win._serialize_graph)
    d.pop("svg", None)
    d.pop("kron_svg", None)
    for k in ("created", "modified"):          # the serializer's clock
        (d.get("metadata") or {}).pop(k, None)
    return json.loads(json.dumps(d))


def _jobs(win):
    with contextlib.redirect_stdout(io.StringIO()):
        if not win.scattering_mode:
            win._enter_scattering_mode()
        p = win.properties_panel
        c, s = p.freq_center_spin.value(), p.freq_span_spin.value()
        n = int(p.freq_points_spin.value())
        f = np.linspace(c - s / 2, c + s / 2, n)
        comps = win.scattering_components
        todo = comps if len(comps) > 1 else [None]
        jobs = [win._build_sparams_job(comp, f, c - s / 2, c + s / 2, n,
                                       multi_component=len(todo) > 1) for comp in todo]
    return [_norm(j) for j in jobs if j is not None]


def _open(win, data):
    """What File > Open does with a file's dict."""
    _quiet(win._deserialize_graph, win._state_dict_from_file(copy.deepcopy(data)))


@pytest.mark.parametrize("path", FILES, ids=IDS)
def test_open_through_model_is_same_gui_state(path, window):
    raw = _raw(path)
    # The first load into a fresh window sets different view limits from
    # every later one (pre-existing, independent of the model), so warm up.
    # the pre-model path, on the file as the model reads it (residue snapped,
    # decision Q2 option A; tests/snap_helpers.py states it independently)
    _quiet(window._deserialize_graph, snap_legacy(raw))
    _quiet(window._deserialize_graph, snap_legacy(raw))
    state_raw, jobs_raw = _state(window), _jobs(window)
    _open(window, raw)
    assert _state(window) == state_raw
    assert _jobs(window) == jobs_raw


@pytest.mark.parametrize("path", FILES, ids=IDS)
def test_gui_save_is_v4_and_reopens_to_same_state(path, window, tmp_path):
    _open(window, _raw(path))
    _open(window, _raw(path))                                 # warm-up, as above
    legacy = json.loads(json.dumps(_quiet(window._serialize_graph)))
    out = _quiet(window._file_dict_from_state, copy.deepcopy(legacy))
    assert (out["format"], out["version"]) == ("pgraph", "4.0")
    f = tmp_path / "saved.pgraph"
    f.write_text(json.dumps(out))
    errors = [i for i in M.validate(M.load(f)) if i.level == "error"
              and "LC mode impedance" not in i.msg]     # milestone 2c, Q5
    assert not errors, errors
    # Reloading a GUI save does not reproduce the saved view exactly (the
    # loader refits it once; pre-existing, model-independent). So compare
    # with the same reload done without the model.
    _quiet(window._deserialize_graph, copy.deepcopy(legacy))
    want = _state(window)
    _open(window, _raw(f))
    assert _state(window) == want


def test_model_only_settings_survive_open_save(window):
    doc = M.load(os.path.join(PG, "TL_3_PUMPED_TERMINATION_AMPLIFIER.pgraph"))
    doc.solve.sectors, doc.solve.sector_tol, doc.solve.sector_max = [-2, 1], 1e-4, 8
    doc.units = {"frequency": "MHz", "impedance": "ohm"}
    _open(window, M.to_file_dict(doc))
    out = M.from_dict(_quiet(window._file_dict_from_state, _quiet(window._serialize_graph)))
    assert (out.solve.sectors, out.solve.sector_tol, out.solve.sector_max) == ([-2, 1], 1e-4, 8)
    assert out.units["frequency"] == "MHz"
    # and they do not leak into the next document
    _open(window, _raw(os.path.join(PG, "TL_1_OPEN_LINE_ON_A_PORT.pgraph")))
    out = M.from_dict(_quiet(window._file_dict_from_state, _quiet(window._serialize_graph)))
    assert out.solve.sectors == "auto" and out.units["frequency"] == "GHz"


def test_legacy_copy_is_the_old_layout(window, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    path = os.path.join(PG, "5MODE_CHEBY.pgraph")
    _open(window, _raw(path))
    window.current_filepath = path
    target = tmp_path / "old"
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(target), "")))
    assert _quiet(window._save_legacy_copy)
    d = _raw(str(target) + ".pgraph")
    assert d["format"] == "pgraph" and d["version"] in ("2.0", "3.0")
    assert window.current_filepath == path                    # a copy, not a Save As
    assert d["scattering"]["frequency"]["center"] == 6.0      # quantized, like a 4.0 save
    _open(window, d)                                          # and it reads back


def test_graph_files_bypass_the_model(window):
    data = {"version": "1.0", "nodes": [], "edges": []}
    assert window._state_dict_from_file(data) is data
