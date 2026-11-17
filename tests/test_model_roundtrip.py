"""Layer 0 document model: migration and round-trip gates (no Qt).

Gate 1 (design note, build order step 1): every shipped .pgraph loads,
migrates to 4.0, saves and reloads to an equal Document.
Gate 1b: the migration loses nothing -- 4.0 -> legacy reproduces the original
2.0/3.0 dict EXACTLY (every key, value and list order), the only
canonicalization being a line end's connections in list form (the GUI
loader's own normalization of the oldest files) and dropping the edge
'from_to' display string, which the GUI regenerates from node labels on every
save (some shipped files carry a stale one from before a relabel).
"""
import copy
import glob
import json
import os

import pytest

from graphulator import model as M
from graphulator.model.migrate import end_conns

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = sorted(glob.glob(os.path.join(ROOT, "examples", "**", "*.pgraph"), recursive=True)
               + glob.glob(os.path.join(ROOT, "src", "graphulator", "examples", "**", "*.pgraph"),
                           recursive=True))
IDS = [os.path.relpath(f, ROOT) for f in FILES]


def _raw(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _canon_legacy(d):
    d = copy.deepcopy(d)
    for l in d.get("line_resonators", []) or []:
        l["ends"] = {e: end_conns(l, e) for e in ("x0", "xL")}
    for e in d.get("edges", []):
        e.pop("from_to", None)
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
