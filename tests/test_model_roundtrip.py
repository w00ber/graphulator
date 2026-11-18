"""Layer 0 document model: migration and round-trip gates (no Qt).

Gate 1 (design note, build order step 1): every shipped .pgraph loads,
migrates to 4.0, saves and reloads to an equal Document.
Gate 1b: the migration loses nothing -- 4.0 -> legacy reproduces the original
2.0/3.0 dict EXACTLY (every key, value and list order), the only
canonicalization being a line end's connections in list form (the GUI
loader's own normalization of the oldest files) and dropping the edge
'from_to' display string, which the GUI regenerates from node labels on every
save (some shipped files carry a stale one from before a relabel), and the
sweep, which is stored as its spin boxes hold it (decision Q2: center/span
quantized to the display precision; the oldest start/stop form becomes
center/span, as the GUI loader converts it).
"""
import copy
import glob
import json
import os

import pytest

from graphulator import model as M
from graphulator.model.migrate import end_conns
from graphulator.model.quantize import quantize, quantize_sweep
from tests.snap_helpers import snap_legacy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = sorted(glob.glob(os.path.join(ROOT, "examples", "**", "*.pgraph"), recursive=True)
               + glob.glob(os.path.join(ROOT, "src", "graphulator", "examples", "**", "*.pgraph"),
                           recursive=True))
IDS = [os.path.relpath(f, ROOT) for f in FILES]


def _raw(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _canon_legacy(d):
    d = snap_legacy(d)                   # Q2 option A: residue is snapped
    for l in d.get("line_resonators", []) or []:
        l["ends"] = {e: end_conns(l, e) for e in ("x0", "xL")}
    for e in d.get("edges", []):
        e.pop("from_to", None)
    fr = (d.get("scattering") or {}).get("frequency")
    if fr:
        if "center" in fr:
            c, s = fr.pop("center"), fr.pop("span")
        else:
            a, b = fr.pop("start"), fr.pop("stop")
            c, s = (a + b) / 2, b - a
        fr["center"], fr["span"], fr["points"] = quantize_sweep(c, s, fr["points"])
    return d


def test_examples_found():
    assert len(FILES) >= 60


@pytest.mark.parametrize("path", FILES, ids=IDS)
def test_migrates_without_errors(path):
    doc = M.load(path)
    errors = [i for i in M.validate(doc) if i.level == "error"]
    assert not errors, errors


@pytest.mark.parametrize("path", FILES, ids=IDS)
def test_legacy_roundtrip_is_lossless(path):
    raw = _raw(path)
    back = M.to_legacy(M.from_legacy(raw))
    assert _canon_legacy(back) == _canon_legacy(raw)


@pytest.mark.parametrize("path", FILES, ids=IDS)
def test_v4_save_load_roundtrip(path, tmp_path):
    doc = M.load(path)
    out = tmp_path / "doc.pgraph"
    M.save(doc, out)
    again = M.load(out)
    assert again == doc
    assert again.to_dict() == doc.to_dict()
    # and a second hop through 4.0 still reproduces the legacy dict
    assert _canon_legacy(M.to_legacy(again)) == _canon_legacy(_raw(path))


def test_saved_file_is_v4(tmp_path):
    doc = M.load(os.path.join(ROOT, "examples", "pgraphs", "TL_1_OPEN_LINE_ON_A_PORT.pgraph"))
    M.save(doc, tmp_path / "x.pgraph")
    d = _raw(tmp_path / "x.pgraph")
    assert (d["format"], d["version"]) == ("pgraph", "4.0")


# ---------------------------------------------------------------------------
# what the physics looks like after migration
# ---------------------------------------------------------------------------

def test_twin_becomes_a_sector_view_not_physics():
    doc = M.load(os.path.join(ROOT, "examples", "pgraphs", "TL_3_PUMPED_TERMINATION_AMPLIFIER.pgraph"))
    lines = [b for b in doc.blocks if b.type == "line"]
    ports = [p for p in doc.planes if p.kind == "port"]
    assert [b.label for b in lines] == ["TL"]          # TL* is gone from the physics
    assert [p.label for p in ports] == ["TL"] and ports[0].Z0 == 50.0
    assert sorted((sv.of, sv.sector) for sv in doc.drawing.sector_views) == \
        [("line0", -1), ("port0", -1)]
    (pump,) = doc.pumped
    assert (pump.kind, pump.param, pump.plane) == ("element", "1/L", "line0.x0")
    assert doc.by_id("tones")[pump.tone].f == 9.0
    assert pump.legacy_anchor["rate"] == 0.05 and pump.legacy_anchor["n_ref"] == 3
    assert doc.solve.kept_poles == {"line0": {"f_max": 9.0}}
    assert doc.solve.sectors == "auto" and doc.solve.sector_max == 16


def test_tap_keeps_its_legacy_anchor():
    doc = M.load(os.path.join(ROOT, "examples", "pgraphs", "TL_2_MODE_TAPPED_ONTO_A_LINE.pgraph"))
    (tap,) = [a for a in doc.attachments if a.element is not None]
    assert tap.plane == "line0.x0" and tap.element == "C"
    assert tap.rate == 0.05 and tap.legacy_anchor == {"n_ref": 3}


def test_load_and_pump_share_the_loaded_end():
    doc = M.load(os.path.join(ROOT, "examples", "pgraphs", "TL_4_INDUCTIVELY_LOADED_LINE.pgraph"))
    (load,) = [b for b in doc.blocks if b.type == "L"]
    (pump,) = doc.pumped
    assert load.params == {"f_Z": 3.0} and pump.block == load.id
    assert pump.plane == load.terminals["a"]


def test_legacy_B_ext_becomes_port_plane_and_attachment():
    paths = [f for f in FILES if any((n.get("B_ext") or 0) > 0 for n in _raw(f)["nodes"])]
    assert paths
    raw = _raw(paths[0])
    doc = M.from_legacy(raw)
    want = [n for n in raw["nodes"] if (n.get("B_ext") or 0) > 0]
    got = [a for a in doc.attachments if a.id.startswith("bext")]
    assert [a.rate for a in got] == [n["B_ext"] for n in want]
    assert all(doc.by_id("planes")[a.plane].kind == "port" for a in got)


def test_pump_tones_are_deduplicated():
    for path in FILES:
        doc = M.load(path)
        fs = [t.f for t in doc.tones]
        assert len(fs) == len(set(fs)), path


# ---------------------------------------------------------------------------
# validation catches broken documents
# ---------------------------------------------------------------------------

def test_validate_flags_dangling_references():
    doc = M.load(os.path.join(ROOT, "examples", "pgraphs", "TL_2_MODE_TAPPED_ONTO_A_LINE.pgraph"))
    doc.attachments[0].mode = "nope"
    doc.blocks[0].terminals["x0"] = "missing"
    doc.solve.sectors = [1, 3]
    msgs = [(i.level, i.path) for i in M.validate(doc)]
    assert ("error", f"attachments/{doc.attachments[0].id}") in msgs
    assert ("error", "blocks/line0") in msgs
    assert ("error", "solve/sectors") in msgs


def test_validate_warns_on_sweep_hitting_a_line_pole():
    doc = M.load(os.path.join(ROOT, "examples", "pgraphs", "TL_3_PUMPED_TERMINATION_AMPLIFIER.pgraph"))
    # 4.5 +- 1.5 over 801 points lands exactly on f = 3, 4.5, 6 (n = 2, 3, 4)
    warns = [i for i in M.validate(doc) if i.level == "warning" and i.path == "blocks/line0"]
    assert warns and "n = [2, 3, 4]" in warns[0].msg


def test_unknown_keys_survive():
    raw = _raw(os.path.join(ROOT, "examples", "pgraphs", "TL_2_MODE_TAPPED_ONTO_A_LINE.pgraph"))
    raw["future_top_level"] = {"x": 1}
    raw["line_resonators"][0]["future_line_key"] = [1, 2]
    raw["ports"][0]["future_port_key"] = "y"
    back = M.to_legacy(M.from_dict(json.loads(json.dumps(M.from_legacy(raw).to_dict()))))
    assert back["future_top_level"] == {"x": 1}
    assert back["line_resonators"][0]["future_line_key"] == [1, 2]
    assert back["ports"][0]["future_port_key"] == "y"


# ---------------------------------------------------------------------------
# decisions Q1-Q3 (design note): root, quantized sweep, tail closure
# ---------------------------------------------------------------------------

PG = os.path.join(ROOT, "examples", "pgraphs")


def test_quantize_is_spin_box_rounding():
    # ties away from zero on the exact binary value (QDoubleSpinBox), not
    # Python's ties-to-even
    assert quantize(-0.125, 2) == -0.13 and quantize(0.125, 2) == 0.13
    assert quantize(-2.625, 2) == -2.63 and quantize(0.375, 2) == 0.38
    assert quantize(2.675, 2) == 2.67          # the double is 2.67499...
    assert quantize(5.9999999999999964, 2) == 6.0
    assert str(quantize(-0.001, 2)) == "0.0"


def test_migration_stores_the_spin_box_sweep():
    doc = M.load(os.path.join(PG, "5MODE_CHEBY.pgraph"))
    assert (doc.sweep.center, doc.sweep.span, doc.sweep.points) == (6.0, 0.4, 801)


def test_save_quantizes_the_sweep(tmp_path):
    doc = M.load(os.path.join(PG, "5MODE_CHEBY.pgraph"))
    doc.sweep.center, doc.sweep.span = -0.125, 0.2999999999999994
    M.save(doc, tmp_path / "x.pgraph")
    sw = _raw(tmp_path / "x.pgraph")["sweep"]
    assert (sw["center"], sw["span"]) == (-0.13, 0.3)
    assert doc.sweep.center == -0.125             # the in-memory doc is untouched


def test_injection_root_migrates_to_solve():
    doc = M.load(os.path.join(PG, "TEUFELATOR.pgraph"))
    assert doc.solve.root == "n6"
    assert "injection_node_id" not in doc.solve.legacy_frames
    assert M.to_legacy(doc)["scattering"]["injection_node_id"] == 6


def test_stale_root_is_a_warning_not_an_error():
    doc = M.load(os.path.join(PG, "TEUFELATOR.pgraph"))
    doc.solve.root = "n999"
    issues = [(i.level, i.path) for i in M.validate(doc)]
    assert ("warning", "solve/root") in issues
    assert not any(lvl == "error" for lvl, _ in issues)


def test_tail_closure_travels_with_the_file():
    raw = _raw(os.path.join(PG, "TL_3_PUMPED_TERMINATION_AMPLIFIER.pgraph"))
    assert M.from_legacy(raw).solve.tail_closure is None     # old file: app default
    raw["scattering"]["tail_closure"] = False
    doc = M.from_legacy(raw)
    assert doc.solve.tail_closure is False
    assert "tail_closure" not in doc.solve.legacy_frames
    assert M.to_legacy(doc)["scattering"]["tail_closure"] is False


# ---------------------------------------------------------------------------
# decision Q2, option A: snap floating-point residue, keep deliberate digits
# ---------------------------------------------------------------------------

SCENES = os.path.join(ROOT, "examples", "test_scenes")


def test_snap_moves_residue_only():
    from graphulator.model.quantize import snap
    assert snap(14.999999999999996, 4) == 15.0
    assert snap(0.10000000000000003, 5) == 0.1
    assert snap(0.028399999999999998, 5) == 0.0284
    assert snap(3e-18, 3) == 0.0                         # residue around zero
    # deliberate digits finer than the widget are not residue
    assert snap(4.008568771762118, 4) == 4.008568771762118
    assert snap(0.003604911497849718, 6) == 0.003604911497849718
    assert snap(6.0123, 3) == 6.0123
    for x in (None, True, "matched", float("nan")):
        assert snap(x, 3) is x


def test_shipped_residue_is_snapped():
    doc = M.load(os.path.join(PG, "BOGO_AB_AMP.pgraph"))
    assert [t.f for t in doc.tones] == [15.0]
    leg = M.to_legacy(M.load(os.path.join(PG, "FPJA_PRA.pgraph")))
    assert [n["B_ext"] for n in leg["nodes"][:2]] == [0.0284, 0.0283]


def test_script_computed_physics_is_kept():
    """The Lee-2013 scene's numbers are computed to put f_A at 1.840 GHz and
    the pump exactly on f_B - f_A; rounding them to widget precision would
    move f_A by 13.5 kHz. Snapping leaves every one of them alone."""
    path = os.path.join(SCENES, "INTERMODE_LEE2013_CONVERSION.pgraph")
    raw = _raw(path)
    leg = M.to_legacy(M.load(path))
    keys = ("FSR", "Ztx", "f_max", "Z0_port", "load", "pump", "sections")
    for a, b in zip(raw["line_resonators"], leg["line_resonators"]):
        assert {k: a.get(k) for k in keys} == {k: b.get(k) for k in keys}


def test_coinciding_tones_merge():
    raw = _raw(os.path.join(PG, "5MODE_CHEBY.pgraph"))
    pumpable = [e for e in raw["edges"] if not e.get("is_self_loop")][:2]
    pumpable[0]["f_p"], pumpable[1]["f_p"] = 12.0, 11.999999999999998
    doc = M.from_legacy(raw)
    twelve = [t for t in doc.tones if t.f == 12.0]
    assert len(twelve) == 1 and len(doc.tones) == len({t.f for t in doc.tones})
    assert sum(p.tone == twelve[0].id for p in doc.pumped) == 2


def test_4p0_load_and_save_snap(tmp_path):
    doc = M.load(os.path.join(PG, "5MODE_CHEBY.pgraph"))
    doc.modes[0].freq = 6.0000000000000009
    M.save(doc, tmp_path / "a.pgraph")
    assert doc.modes[0].freq == 6.0000000000000009          # in-memory doc untouched
    assert _raw(tmp_path / "a.pgraph")["modes"][0]["freq"] == 6.0
    d = M.to_file_dict(doc)
    d["modes"][0]["freq"] = 6.0000000000000009              # a script-written 4.0 file
    assert M.from_dict(d).modes[0].freq == 6.0


@pytest.mark.parametrize("name", ["AMP_BA", "BOGO_AB_AMP", "DTWPA_MINIMAL2", "FIG15", "FPJA_PRA"])
def test_snapping_moves_S_only_at_roundoff(name, monkeypatch):
    import numpy as np

    import graphulator.model.migrate as mg
    from graphulator.model.legacy_job import compile_jobs, compute_job
    raw = _raw(os.path.join(PG, f"{name}.pgraph"))
    snapped = [compute_job(j) for j in compile_jobs(M.from_legacy(raw))]
    monkeypatch.setattr(mg, "snap_document", lambda d: d)
    unsnapped = [compute_job(j) for j in compile_jobs(M.from_legacy(raw))]
    for a, b in zip(snapped, unsnapped):
        assert np.max(np.abs(a["S"] - b["S"])) < 1e-13      # measured <= 1.5e-15
