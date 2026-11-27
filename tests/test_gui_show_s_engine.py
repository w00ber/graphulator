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

TAPS_NEED_ZD = ("LINE_TAP_2NODES", "NODE_2LINES_TAP", "ZD_a_TAP_NEEDS_Z_D")
# Legacy splits these into separate jobs per line; the engine solves the
# shared port as one network (decision D1).
SPLIT_DIFFERS = ("TL_5_TWO_LINES_ONE_PORT", "S1e_SHARED_PORT")
# The engine refuses these (inductive taps); Show S falls back to legacy.
REFUSED = ("S1f_INDUCTIVE_TAP_FALLBACK",)


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
    if name in REFUSED:
        assert eng["engine"] == "legacy" and "Inductive" in eng["fallback"]
        assert [_meta(r) for r in eng["results"]] == [_meta(r) for r in leg]
        return
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


# ---------------------------------------------------------------------------
# Z_d: the LC impedance a tapped mode needs (model/taps.py, decision Q5)
# ---------------------------------------------------------------------------

SCENES = os.path.join(os.path.dirname(PG), "test_scenes")


def _zd_spins(win):
    from PySide6.QtWidgets import QDoubleSpinBox
    lay = win.properties_panel.nodes_param_layout
    out = {}
    for i in range(lay.count()):
        w = lay.itemAt(i).widget()
        if isinstance(w, QDoubleSpinBox) and w.property("param_name") == "Z_d":
            out[w.property("node_id")] = w
    return out


@pytest.mark.parametrize("name", TAPS_NEED_ZD)
def test_z_d_field_makes_the_tap_scene_solve(win, name):
    import glob
    (path,) = glob.glob(os.path.join(SCENES, "**", name + ".pgraph"), recursive=True)
    _open(win, path)
    need = win._modes_needing_z_d()
    assert need
    with contextlib.redirect_stdout(io.StringIO()):
        win.properties_panel._update_scattering_node_table()
    spins = _zd_spins(win)
    assert set(spins) == need
    for nid, w in spins.items():
        assert w.property("user_assigned") is False
        w.setValue(125.0)                          # what a user typing does
    assert all(win.scattering_assignments[n]["Z_d"] == 125.0 for n in need)
    _, eng, _ = _solve(win)
    assert eng["results"] and not [i for i in eng["issues"] if i[0] == "error"]
    S = eng["results"][0]["S"]
    assert np.all(np.isfinite(S))
    # passive, lossless network: |S| <= 1
    assert np.nanmax(np.abs(S)) <= 1 + 1e-9


def test_z_d_round_trips_through_save_and_load(win, tmp_path):
    from graphulator import model
    _open(win, os.path.join(SCENES, "LINE_TAP_2NODES.pgraph"))
    nid = sorted(win._modes_needing_z_d())[0]
    win.scattering_assignments.setdefault(nid, {})["Z_d"] = 625.0
    doc = win._model_document()
    assert doc.by_id("modes")[f"n{nid}"].extras["Z_d"] == 625.0
    assert "Z_d" not in doc.drawing.nodes[f"n{nid}"]
    p = tmp_path / "tap.pgraph"
    model.save(doc, p)
    back = model.load(p)
    assert back.by_id("modes")[f"n{nid}"].extras["Z_d"] == 625.0
    import json
    with contextlib.redirect_stdout(io.StringIO()):
        win._deserialize_graph(win._state_dict_from_file(json.loads(p.read_text())))
    assert win.scattering_assignments[nid]["Z_d"] == 625.0


def test_direct_port_needs_no_z_d(win):
    """TL_2's tapped mode also sits on a port, which fixes its C_d."""
    _open(win, os.path.join(PG, "TL_2_MODE_TAPPED_ONTO_A_LINE.pgraph"))
    assert win._modes_needing_z_d() == set()


# ---------------------------------------------------------------------------
# File > Test: campaign subfolders become submenus
# ---------------------------------------------------------------------------

def test_test_menu_has_campaign_submenus(win):
    from pathlib import Path
    win._populate_test_menu()
    menus = {a.menu().title(): a.menu() for a in win.test_menu.actions() if a.menu()}
    assert {"MSUPER_1_SHOW_S", "MSUPER_2_Z_D"} <= set(menus)
    top = [a.text() for a in win.test_menu.actions() if not a.menu() and not a.isSeparator()]
    assert "LINE_TAP_2NODES" in top
    for title, menu in menus.items():
        names = sorted(a.text() for a in menu.actions() if not a.isSeparator())
        files = sorted(p.stem for p in (Path(win._get_test_scenes_dir()) / title).glob("*.pgraph"))
        assert names == files


def test_campaign_scenes_have_notes():
    import glob
    import json
    for f in glob.glob(os.path.join(SCENES, "MSUPER_*", "*.pgraph")):
        with open(f, encoding="utf-8") as fh:
            notes = json.load(fh).get("notes", "")
        assert "**Try" in notes and "**Expect" in notes, f


def test_z_d_scene_loads_with_z_d_and_solves(win):
    _open(win, os.path.join(SCENES, "MSUPER_2_Z_D", "ZD_b_TAP_Z_D_SET.pgraph"))
    assert [v.get("Z_d") for v in win.scattering_assignments.values() if "Z_d" in v] == [125.0]
    _, eng, _ = _solve(win)
    (r,) = eng["results"]
    f = _grid(win)
    phase = np.unwrap(np.angle(r["S"][:, 0, 0]))
    f_res = f[np.argmax(np.abs(np.gradient(phase, f)))]
    assert abs(f_res - 4.4) < 2e-4               # the mode as drawn


# ---------------------------------------------------------------------------
# The RWA flag (engine/rwa.py): image poles on/off, and what deleting costs
# ---------------------------------------------------------------------------

RWA = os.path.join(SCENES, "MSUPER_3_RWA")


def test_rwa_report_predicted_shift_and_cost():
    from graphulator import model
    from graphulator.engine.gui_payload import solve_for_gui
    from graphulator.model.legacy_job import sweep_grid
    doc = model.load(os.path.join(RWA, "R3b_TAP_PULL_SETS_RWA_COST.pgraph"))
    out = solve_for_gui(doc, sweep_grid(doc))
    r = out["rwa"]
    assert r.images and r.matters
    (m,) = r.modes
    assert m.image_shift == pytest.approx(-m.pull ** 2 / (2 * m.f_bare))
    assert m.image_shift * 1e3 == pytest.approx(-0.0457, rel=2e-2)
    assert any(p == "solve.images" and lvl == "info" for lvl, p, _ in out["issues"])
    doc.solve.images = False
    out = solve_for_gui(doc, sweep_grid(doc))
    assert out["rwa"].images is False
    assert any(p == "solve.images" and lvl == "warning" for lvl, p, _ in out["issues"])


def test_rwa_measured_shift_matches_prediction():
    """Deleting the image moves the dressed resonance by d^2/2f0 (sec. 3.7)."""
    from graphulator import engine, model
    from graphulator.engine.rwa import mode_pulls
    doc = model.load(os.path.join(RWA, "R3c_SAVED_WITH_RWA_BREAKS.pgraph"))
    f = np.linspace(4.39, 4.41, 20001)
    res = {}
    for img in (True, False):
        doc.solve.images = img
        (r,) = engine.solve(doc, f)
        g = np.gradient(np.unwrap(np.angle(r.S[:, 0, 0])), f)
        res[img] = f[np.argmax(np.abs(g))]
    (m,) = mode_pulls(doc)
    assert res[True] == pytest.approx(4.4, abs=1e-4)
    assert res[False] - res[True] == pytest.approx(m.image_shift, rel=2e-2)


def test_no_rwa_report_without_modes_or_on_lumped():
    from graphulator import model
    from graphulator.engine.gui_payload import solve_for_gui
    from graphulator.model.legacy_job import sweep_grid
    for p in (os.path.join(PG, "TL_3_PUMPED_TERMINATION_AMPLIFIER.pgraph"),
              os.path.join(SCENES, "MSUPER_1_SHOW_S", "S1a_LUMPED_UNCHANGED.pgraph")):
        doc = model.load(p)
        assert solve_for_gui(doc, sweep_grid(doc))["rwa"] is None


def test_images_checkbox_drives_the_document(win, tmp_path):
    from graphulator import model
    _open(win, os.path.join(RWA, "R3c_SAVED_WITH_RWA_BREAKS.pgraph"))
    panel = win.properties_panel
    panel._update_scattering_ports_table()
    assert panel.images_check.isChecked() is False          # from the file
    assert win._model_document().solve.images is False
    _, eng, _ = _solve(win)
    with contextlib.redirect_stdout(io.StringIO()):
        win._on_sparams_finished(win._sparams_generation,
                                 {**eng, "f_root_s": _grid(win)})
    assert panel.images_check.text().startswith("⚠")
    assert "RWA in use" in panel.images_check.toolTip()
    panel.images_check.setChecked(True)
    assert win._model_document().solve.images is True
    p = tmp_path / "rwa.pgraph"
    model.save(win._model_document(), p)
    assert model.load(p).solve.images is True
    _, eng, _ = _solve(win)
    with contextlib.redirect_stdout(io.StringIO()):
        win._on_sparams_finished(win._sparams_generation,
                                 {**eng, "f_root_s": _grid(win)})
    assert not panel.images_check.text().startswith("⚠")
