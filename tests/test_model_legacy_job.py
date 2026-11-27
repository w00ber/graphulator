"""Layer 0 step 2: the Qt-free legacy compiler (model -> today's S jobs).

Gate 2 (design note, build order step 2): for every shipped .pgraph,
``compile_jobs(load(path))`` builds the SAME job list the GUI's Show S path
builds after opening that file in a fresh window, and the resulting S is
bit-identical (``np.array_equal``, not allclose). Job equality is checked
field by field first, so a failure names the field that drifted rather than
just a number.

The GUI half needs PySide6 and skips without it; the Qt-free half (every
document compiles and computes, the sweep rounding, solve settings reaching
the job) always runs.
"""
import contextlib
import copy
import glob
import io
import json
import logging
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")

from graphulator import model as M  # noqa: E402
from graphulator.model.legacy_job import compile_jobs, compute_job, sweep_grid  # noqa: E402
from tests.snap_helpers import snap_legacy  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _file_version(path):
    import json as _json
    with open(path, encoding="utf-8") as fh:
        return str(_json.load(fh).get("version"))


FILES = sorted(glob.glob(os.path.join(ROOT, "examples", "**", "*.pgraph"), recursive=True)
               + glob.glob(os.path.join(ROOT, "src", "graphulator", "examples", "**", "*.pgraph"),
                           recursive=True))
# The legacy-format (2.0/3.0) shipped files: what these migration gates are
# about. 4.0 scenes (saved by the app, e.g. MSUPER_3_RWA/R3c) are covered by
# tests/test_gui_show_s_engine.py.
FILES = [f for f in FILES if _file_version(f) in ("2.0", "3.0")]
IDS = [os.path.relpath(f, ROOT) for f in FILES]
PG = os.path.join(ROOT, "examples", "pgraphs")


def _norm(job):
    """A job with its id()-keyed assignments re-keyed by position, so two
    jobs built from different dict objects compare with ==."""
    j = dict(job)
    sa = j.pop("scattering_assignments")
    j["node_sa"] = [sa.get(id(n)) for n in j["nodes"]]
    j["edge_sa"] = [sa.get(id(e)) for e in j["edges"]]
    assert len(sa) == sum(x is not None for x in j["node_sa"] + j["edge_sa"])
    j["f_root_s"] = np.asarray(j["f_root_s"]).tolist()
    j["freq_start"], j["freq_stop"] = float(j["freq_start"]), float(j["freq_stop"])
    return j


def _same_result(a, b):
    if a is None or b is None:
        return a is None and b is None
    return (np.array_equal(a["S"], b["S"]) and a["port_ids"] == b["port_ids"]
            and a["port_dict"] == b["port_dict"]
            and (a["component_index"], a["component_label"])
            == (b["component_index"], b["component_label"]))


def _run(job):
    try:
        return compute_job(job)
    except Exception as exc:             # the GUI worker logs and skips these
        return ("error", type(exc).__name__, str(exc))


# ---------------------------------------------------------------------------
# Qt-free
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", FILES, ids=IDS)
def test_every_document_compiles(path):
    jobs = compile_jobs(M.load(path))
    assert jobs
    for job in jobs:
        res = _run(job)
        assert not isinstance(res, tuple), res      # no shipped file raises
        if res is not None:
            assert np.all(np.isfinite(res["S"]))


def test_compiler_imports_no_qt():
    import subprocess
    import sys
    code = ("import sys, graphulator.model.legacy_job as L; "
            "sys.exit(any(m.startswith('PySide6') for m in sys.modules))")
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0


def test_pumped_line_compiles_to_comb_twin_and_bus():
    (job,) = compile_jobs(M.load(os.path.join(PG, "TL_3_PUMPED_TERMINATION_AMPLIFIER.pgraph")))
    # the twin is drawing-only in the model, but the legacy engine needs it
    # back as a conj line macro carrying the primary's physics
    tl, twin = job["line_resonators"]
    assert (tl["label"], tl["conj"]) == ("TL", False)
    assert (twin["label"], twin["conj"]) == ("TL*", True)
    assert {k: twin[k] for k in ("FSR", "Ztx", "f_max")} == \
        {k: tl[k] for k in ("FSR", "Ztx", "f_max")}
    sa = job["scattering_assignments"]
    bus = [sa[id(e)] for e in job["edges"] if id(e) in sa and sa[id(e)].get("f_p")]
    assert bus and all(p["f_p"] == 9.0 and p["frame_rule"] == "sector" for p in bus)
    assert [h["label"] for h in job["hubs"]] == ["TL", "TL*"]   # one column per sector


def test_two_lines_one_port_is_two_jobs():
    jobs = compile_jobs(M.load(os.path.join(PG, "TL_5_TWO_LINES_ONE_PORT.pgraph")))
    assert [j["component_label"] for j in jobs] == ["C1", "C2"]


def test_sweep_rounds_like_the_spin_boxes():
    doc = M.load(os.path.join(PG, "5MODE_CHEBY.pgraph"))
    assert (doc.sweep.center, doc.sweep.span) == (6.0, 0.4)      # quantized at migration
    f = sweep_grid(doc)
    assert (f[0], f[-1], len(f)) == (5.8, 6.2, 801)
    assert np.array_equal(f, np.linspace(6.0 - 0.4 / 2, 6.0 + 0.4 / 2, 801))
    # residue set by a script is still rounded the spin-box way (ties away
    # from zero), and the center is clamped to the box's range
    doc.sweep.center, doc.sweep.span = 6.125, 0.125
    f = sweep_grid(doc)
    assert np.array_equal(f, np.linspace(6.13 - 0.13 / 2, 6.13 + 0.13 / 2, 801))
    doc.sweep.center = -1.0
    assert sweep_grid(doc)[400] == 0.0


def test_saved_root_is_used():
    doc = M.load(os.path.join(PG, "TEUFELATOR.pgraph"))
    assert [j["root_node_id"] for j in compile_jobs(doc)] == [6]       # decision Q1
    doc.solve.root = "n999"                                           # not a port node
    assert [j["root_node_id"] for j in compile_jobs(doc)] == [4]       # first port node
    doc.solve.root = None
    assert [j["root_node_id"] for j in compile_jobs(doc)] == [4]


def test_solve_tail_closure_reaches_the_job():
    doc = M.load(os.path.join(PG, "TL_3_PUMPED_TERMINATION_AMPLIFIER.pgraph"))
    assert compile_jobs(doc)[0]["tail_closure"] is True       # None = app default
    doc.solve.tail_closure = False
    assert compile_jobs(doc)[0]["tail_closure"] is False
    assert compile_jobs(doc, tail_closure=True)[0]["tail_closure"] is True


def test_compiler_does_not_mutate_the_document():
    doc = M.load(os.path.join(PG, "TL_3_PUMPED_TERMINATION_AMPLIFIER.pgraph"))
    before = copy.deepcopy(doc.to_dict())
    compile_jobs(doc)
    assert doc.to_dict() == before


# ---------------------------------------------------------------------------
# the gate: bit-identical to the live GUI
# ---------------------------------------------------------------------------

@pytest.fixture()
def fresh_window():
    try:
        from PySide6.QtWidgets import QApplication
        _app = QApplication.instance() or QApplication([])
        import graphulator.graphulator_para as gp
    except ImportError as exc:
        pytest.skip(f"GUI stack unavailable: {exc}")

    def make():
        # no close()/deleteLater() at teardown, as in test_gui_hubs: tearing
        # a window down mid-session crashes QtWebEngine at interpreter exit
        try:
            return gp.Graphulator()
        except Exception as exc:
            pytest.skip(f"Could not create main window: {exc}")
    return make


def _gui_jobs(win, path, tail_closure=None):
    """Open `path` as File > Open does, then build jobs as Show S does."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    with contextlib.redirect_stdout(io.StringIO()):
        # the file as the model reads it: floating-point residue in
        # user-entered numbers snapped (decision Q2 option A), stated
        # independently in tests/snap_helpers.py
        win._deserialize_graph(snap_legacy(data))
        if not win.scattering_mode:
            win._enter_scattering_mode()      # what Show S does when needed
        if tail_closure is not None:
            win.line_tail_closure = tail_closure
        p = win.properties_panel
        c, s = p.freq_center_spin.value(), p.freq_span_spin.value()
        n = int(p.freq_points_spin.value())
        f = np.linspace(c - s / 2, c + s / 2, n)
        comps = win.scattering_components
        todo = comps if len(comps) > 1 else [None]
        jobs = [win._build_sparams_job(comp, f, c - s / 2, c + s / 2, n,
                                       multi_component=len(todo) > 1)
                for comp in todo]
    return f, [j for j in jobs if j is not None]


@pytest.mark.parametrize("path", FILES, ids=IDS)
def test_gate_bit_identical_to_gui(path, fresh_window):
    f_gui, gui = _gui_jobs(fresh_window(), path)
    doc = M.load(path)
    # the document's own sweep IS the GUI's (after spin-box rounding)
    assert np.array_equal(sweep_grid(doc), f_gui)
    ours = compile_jobs(doc)
    assert len(ours) == len(gui)
    for a, b in zip(gui, ours):
        assert _norm(b) == _norm(a)
    logging.disable(logging.WARNING)
    try:
        for a, b in zip(gui, ours):
            ra, rb = _run(a), _run(b)
            assert (ra == rb) if isinstance(ra, tuple) else _same_result(ra, rb)
    finally:
        logging.disable(logging.NOTSET)


def test_gate_tail_closure_off(fresh_window):
    path = os.path.join(PG, "TL_3_PUMPED_TERMINATION_AMPLIFIER.pgraph")
    _, gui = _gui_jobs(fresh_window(), path, tail_closure=False)
    doc = M.load(path)
    doc.solve.tail_closure = False
    (b,) = compile_jobs(doc)
    (a,) = gui
    assert _norm(b) == _norm(a) and a["tail_closure"] is False
    assert _same_result(compute_job(a), compute_job(b))


def test_gate_teufelator_root_restored(fresh_window):
    _, (job,) = _gui_jobs(fresh_window(), os.path.join(PG, "TEUFELATOR.pgraph"))
    assert job["root_node_id"] == 6


def test_gate_root_does_not_depend_on_the_previous_file(fresh_window):
    """The root used to depend on what was open before (stale combo)."""
    win = fresh_window()
    for first in ("DTWPA_8MODE.pgraph", "TEUFELATOR.pgraph", "5MODE_CHEBY.pgraph"):
        _gui_jobs(win, os.path.join(PG, first))
        for path in ("TEUFELATOR.pgraph", "DTWPA_8MODE.pgraph", "DTWPA_MINIMAL2.pgraph"):
            _, gui = _gui_jobs(win, os.path.join(PG, path))
            ours = compile_jobs(M.load(os.path.join(PG, path)))
            assert [_norm(j) for j in gui] == [_norm(j) for j in ours], (first, path)


def test_gate_tail_closure_saved_and_restored(fresh_window):
    path = os.path.join(PG, "TL_3_PUMPED_TERMINATION_AMPLIFIER.pgraph")
    win = fresh_window()
    _gui_jobs(win, path, tail_closure=False)
    with contextlib.redirect_stdout(io.StringIO()):
        saved = win._serialize_graph()
    assert saved["scattering"]["tail_closure"] is False
    doc = M.from_dict(json.loads(json.dumps(saved)))
    assert doc.solve.tail_closure is False
    with contextlib.redirect_stdout(io.StringIO()):
        win._deserialize_graph(json.loads(json.dumps(saved)))
    assert win.line_tail_closure is False
    # and the next file without the key goes back to the app default
    _gui_jobs(win, os.path.join(PG, "TL_1_OPEN_LINE_ON_A_PORT.pgraph"))
    assert win.line_tail_closure is True
