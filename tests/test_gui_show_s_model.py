"""Layer 0 step 3, slice 2: the GUI's Show S compiles from the model.

``Graphulator._sparams_jobs`` snapshots the live state as a Document and
compiles it with ``model.legacy_job.compile_jobs``. The oracle is the old
live-widget builder ``_build_sparams_job``, which is still in the GUI as the
fallback. Gate: on every shipped file (opened as File > Open does) and after
a set of live edits that a file has not seen yet, the two give the same jobs
field by field and bit-identical S.
"""
import contextlib
import io
import logging
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")

from tests.test_model_legacy_job import FILES, IDS, PG, _norm, _run, _same_result  # noqa: E402

_WIN = {}


@pytest.fixture()
def win():
    """One window for the module (opening a file resets all state)."""
    try:
        from PySide6.QtWidgets import QApplication
        _app = QApplication.instance() or QApplication([])
        import graphulator.graphulator_para as gp
    except ImportError as exc:
        pytest.skip(f"GUI stack unavailable: {exc}")
    if "w" not in _WIN:
        try:
            _WIN["w"] = gp.Graphulator()
        except Exception as exc:
            pytest.skip(f"Could not create main window: {exc}")
    return _WIN["w"]


def _open(win, path):
    import json
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    with contextlib.redirect_stdout(io.StringIO()):
        win._deserialize_graph(win._state_dict_from_file(data))
        if not win.scattering_mode:
            win._enter_scattering_mode()


def _grid(win):
    p = win.properties_panel
    c, s = p.freq_center_spin.value(), p.freq_span_spin.value()
    return np.linspace(c - s / 2, c + s / 2, int(p.freq_points_spin.value()))


def _live_jobs(win, f):
    comps = win.scattering_components
    todo = comps if len(comps) > 1 else [None]
    jobs = [win._build_sparams_job(c, f, f[0], f[-1], len(f), multi_component=len(todo) > 1)
            for c in todo]
    return [j for j in jobs if j is not None]


def _assert_same(win, compute=True):
    f = _grid(win)
    with contextlib.redirect_stdout(io.StringIO()):
        live = _live_jobs(win, f)
        ours = win._sparams_jobs(f)
    assert len(ours) == len(live)
    for a, b in zip(live, ours):
        assert _norm(b) == _norm(a)
    if compute:
        logging.disable(logging.WARNING)
        try:
            for a, b in zip(live, ours):
                ra, rb = _run(a), _run(b)
                assert (ra == rb) if isinstance(ra, tuple) else _same_result(ra, rb)
        finally:
            logging.disable(logging.NOTSET)
    return ours


@pytest.mark.parametrize("path", FILES, ids=IDS)
def test_show_s_model_path_equals_live(win, path):
    _open(win, path)
    _assert_same(win)


def test_compile_failure_falls_back_to_live(win, monkeypatch, caplog):
    import graphulator.graphulator_para as gp
    _open(win, os.path.join(PG, "5MODE_CHEBY.pgraph"))

    def boom(*a, **k):
        raise RuntimeError("no")
    monkeypatch.setattr(gp, "compile_jobs", boom)
    f = _grid(win)
    with caplog.at_level(logging.ERROR):
        jobs = win._sparams_jobs(f)
    assert [_norm(j) for j in jobs] == [_norm(j) for j in _live_jobs(win, f)]
    assert "Model compile failed" in caplog.text


# ---------------------------------------------------------------------------
# live edits the file has not seen
# ---------------------------------------------------------------------------

def test_edited_mode_frequency_and_rate(win):
    _open(win, os.path.join(PG, "5MODE_CHEBY.pgraph"))
    sa = win.scattering_assignments
    nid = win.nodes[0]["node_id"]
    sa[nid]["freq"] = sa[nid]["freq"] + 0.0123
    edge = next(e for e in win.edges if not e["is_self_loop"])
    key = (edge["from_node_id"], edge["to_node_id"])
    sa[key]["rate"] = sa[key]["rate"] * 1.37
    (job,) = _assert_same(win)
    node = next(n for n in job["nodes"] if n["node_id"] == nid)
    assert node["freq"] == sa[nid]["freq"]


def test_unsaved_sweep(win):
    _open(win, os.path.join(PG, "5MODE_CHEBY.pgraph"))
    p = win.properties_panel
    p.freq_center_spin.setValue(6.05)
    p.freq_span_spin.setValue(0.37)
    p.freq_points_spin.setValue(123)
    (job,) = _assert_same(win)
    assert len(job["f_root_s"]) == 123 and job["freq_start"] == 6.05 - 0.37 / 2


def test_injection_combo_choice(win):
    _open(win, os.path.join(PG, "TEUFELATOR.pgraph"))
    combo = win.properties_panel.injection_node_combo
    assert combo.currentData() == 6
    combo.setCurrentIndex(combo.findData(4))
    (job,) = _assert_same(win)
    assert job["root_node_id"] == 4


def test_line_fmax_and_tail_closure(win):
    _open(win, os.path.join(PG, "TL_3_PUMPED_TERMINATION_AMPLIFIER.pgraph"))
    line = next(l for l in win.line_resonators if not l.get("conj"))
    line["f_max"] = 1.5 * line["f_max"]
    win._sync_all_twins()
    win.line_tail_closure = False
    (job,) = _assert_same(win)
    assert job["tail_closure"] is False
    assert {l["f_max"] for l in job["line_resonators"]} == {line["f_max"]}


def test_structural_edit_reruns_components(win):
    """Deleting a node goes through _invalidate_scattering_data, which
    recomputes the GUI's components and drops stale B_ext; the model path
    recomputes them from the snapshot."""
    _open(win, os.path.join(PG, "TL_5_TWO_LINES_ONE_PORT.pgraph"))
    _assert_same(win)
    _open(win, os.path.join(PG, "5MODE_CHEBY.pgraph"))
    win.selected_nodes = [win.nodes[-1]]
    win.selected_edges = []
    with contextlib.redirect_stdout(io.StringIO()):
        win._delete_selected_nodes()
    _assert_same(win)


def test_truncation_check_runs_through_the_model(win, monkeypatch):
    import graphulator.graphulator_para as gp
    _open(win, os.path.join(PG, "TL_1_OPEN_LINE_ON_A_PORT.pgraph"))
    seen = []
    real = gp.compile_jobs

    def spy(doc, **kw):
        seen.append({b: kp["f_max"] for b, kp in doc.solve.kept_poles.items()})
        return real(doc, **kw)
    monkeypatch.setattr(gp, "compile_jobs", spy)
    with contextlib.redirect_stdout(io.StringIO()):
        win.properties_panel._check_truncation()
    assert len(seen) == 2
    (a,), (b,) = (list(s.values()) for s in seen)
    assert b == 2 * a
