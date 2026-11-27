"""Show S through the M_super engine (engine/gui_payload.py).

Show S snapshots the live state as a Document and solves it with
``engine.solve``; ``gui_payload`` puts the result in the shape the plot code
reads (the legacy ``compute_job`` dict). Gates, on every shipped file opened
as File > Open does:

- the channel bookkeeping (port refs, labels, conj flags, drive frames,
  component labels) equals legacy's wherever both split the document into
  the same components;
- lumped documents: S is bit-identical to legacy (milestone 1);
- physical documents: S is the engine's, finite where legacy's is;
- the two tap scenes without Z_d show the missing-Z_d error, not a plot;
- the legacy switch (menu action, or GRAPHULATOR_S_ENGINE=legacy) gives the
  legacy jobs back, and a document the engine refuses falls back to them.
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

from tests.test_gui_show_s_model import _grid, _open, win  # noqa: E402,F401
from tests.test_model_legacy_job import FILES, IDS, PG  # noqa: E402

TAPS_NEED_ZD = ("LINE_TAP_2NODES", "NODE_2LINES_TAP")
# Legacy splits these into separate jobs per line; the engine solves the
# shared port as one network (decision D1).
SPLIT_DIFFERS = ("TL_5_TWO_LINES_ONE_PORT",)


def _solve(win):
    import graphulator.graphulator_para as gp
    f = _grid(win)
    logging.disable(logging.WARNING)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            (job,) = win._sparams_show_s_jobs(f)
            assert job["kind"] == "engine"
            eng = gp._compute_engine_job(job)
            leg = [r for r in (gp._compute_sparams_job(j) for j in win._sparams_jobs(f))
                   if r is not None]
    finally:
        logging.disable(logging.NOTSET)
    return f, eng, leg


def _meta(r):
    return ([(k, r["port_dict"][k]["label"], r["port_dict"][k]["conj"]) for k in r["port_ids"]],
            r["component_index"], r["component_label"])


@pytest.mark.parametrize("path", FILES, ids=IDS)
def test_engine_payload_matches_legacy_bookkeeping(win, path):
    _open(win, path)
    if not win.nodes and not win.line_resonators:
        pytest.skip("empty scene")
    f, eng, leg = _solve(win)
    name = os.path.splitext(os.path.basename(path))[0]
    assert eng["engine"] == "msuper" and eng["fallback"] is None
    res = eng["results"]
    if name in TAPS_NEED_ZD:
        assert res == []
        assert any(lvl == "error" and "Z_d" in msg for lvl, _, msg in eng["issues"])
        return
    if name in SPLIT_DIFFERS:
        assert len(res) == 1 and len(leg) == 2
        return
    assert len(res) == len(leg)
    for e, g in zip(res, leg):
        assert _meta(e) == _meta(g)
        for k in g["port_ids"]:
            if k in g["drive_signals"]:
                assert np.allclose(e["drive_signals"][k], g["drive_signals"][k], rtol=0, atol=1e-9)
        assert e["S"].shape == g["S"].shape
        if "sectors" not in e:                       # lumped: milestone 1
            assert np.array_equal(e["S"], g["S"])
        else:
            assert np.all(np.isfinite(e["S"][np.isfinite(g["S"])]))


def test_lumped_is_bit_for_bit(win):
    _open(win, os.path.join(PG, "AMP_BA.pgraph"))
    _, eng, leg = _solve(win)
    (e,), (g,) = eng["results"], leg
    assert np.array_equal(e["S"], g["S"]) and e["port_ids"] == g["port_ids"] == [0, 1]
    assert e["port_dict"][1]["conj"] is True


def test_twin_channel_is_the_partner_sector(win):
    """TL* is the port read in the pump's partner sector: f - f_p for an
    amplifier, f + f_p for an up-conversion anchor (legacy pump_frame_rule)."""
    _open(win, os.path.join(PG, "TL_3_PUMPED_TERMINATION_AMPLIFIER.pgraph"))
    f, eng, _ = _solve(win)
    (e,) = eng["results"]
    assert [e["port_dict"][k]["label"] for k in e["port_ids"]] == ["TL", "TL*"]
    assert np.allclose(e["drive_signals"]["port:1"], f - 9.0)
    _open(win, os.path.join(os.path.dirname(PG), "test_scenes",
                            "INTERMODE_LEE2013_CONVERSION.pgraph"))
    f, eng, _ = _solve(win)
    (e,) = eng["results"]
    d = e["drive_signals"]["port:1"] - f
    assert np.allclose(d, d[0]) and d[0] > 0


def test_pumped_channels_conserve_photons(win):
    """Lossless pumped line, amplifier: |S_ss|^2 - |S_is|^2 is 1 summed over
    the whole window; the two drawn channels carry nearly all of it."""
    from graphulator import engine
    _open(win, os.path.join(PG, "TL_3_PUMPED_TERMINATION_AMPLIFIER.pgraph"))
    doc = win._model_document()
    (r,) = engine.solve(doc, _grid(win))
    tot = sum(np.sign(r.f_sector(m)) * np.abs(r.photon(m)[:, 0, 0]) ** 2 for m in r.sectors)
    assert np.allclose(tot, 1.0, atol=1e-10)
    S = r.S_channels
    assert np.array_equal(S[:, 0, 0], r.S[:, 0, 0])


def test_legacy_switch(win, monkeypatch):
    _open(win, os.path.join(PG, "TL_3_PUMPED_TERMINATION_AMPLIFIER.pgraph"))
    f = _grid(win)
    with contextlib.redirect_stdout(io.StringIO()):
        win.sparams_legacy_engine = True
        try:
            jobs = win._sparams_show_s_jobs(f)
        finally:
            win.sparams_legacy_engine = False
        assert all(j.get("kind") != "engine" for j in jobs) and jobs
        monkeypatch.setenv("GRAPHULATOR_S_ENGINE", "legacy")
        assert all(j.get("kind") != "engine" for j in win._sparams_show_s_jobs(f))


def test_refused_document_falls_back_to_legacy(win, monkeypatch):
    import graphulator.engine.gui_payload as gpl
    import graphulator.graphulator_para as gp
    from graphulator.engine import NotSupportedError
    _open(win, os.path.join(PG, "TL_3_PUMPED_TERMINATION_AMPLIFIER.pgraph"))

    def refuse(doc, f):
        raise NotSupportedError("Inductive taps are not in milestone 2c.")
    monkeypatch.setattr(gpl, "solve_for_gui", refuse)
    f = _grid(win)
    with contextlib.redirect_stdout(io.StringIO()):
        (job,) = win._sparams_show_s_jobs(f)
        out = gp._compute_engine_job(job)
    assert out["engine"] == "legacy" and "Inductive" in out["fallback"]
    assert len(out["results"]) == 1 and out["results"][0]["port_ids"] == ["port:0", "port:1"]


def test_worker_end_to_end(win):
    """The worker thread's run() with an engine job emits the plot payload."""
    import graphulator.graphulator_para as gp
    _open(win, os.path.join(PG, "TL_3_PUMPED_TERMINATION_AMPLIFIER.pgraph"))
    f = _grid(win)
    got = []
    with contextlib.redirect_stdout(io.StringIO()):
        w = gp.SParamsWorker(7, win._sparams_show_s_jobs(f), f)
        w.finished_ok.connect(lambda g, p: got.append((g, p)))
        w.run()
    ((gen, payload),) = got
    assert gen == 7 and payload["engine"] == "msuper"
    assert payload["results"][0]["S"].shape == (len(f), 2, 2)
    with contextlib.redirect_stdout(io.StringIO()):
        win._on_sparams_finished(win._sparams_generation, payload)
    assert win.sparams_data["port_ids"] == ["port:0", "port:1"]
    assert win.sparams_engine_used == "msuper"
