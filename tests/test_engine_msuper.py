"""Step 4, milestone 1: the M_super engine on lumped documents.

Gate (docs/design/step4_msuper_m1.md): for every lumped shipped .pgraph,
``engine.solve(doc)`` equals the legacy engine, ``compute_job`` over
``compile_jobs(doc)``, bit for bit (``np.array_equal``). The two must also
agree on the components, the root of each, which components have no result
(missing parameters), and the port order. The same holds after edits the
files have not seen. Qt-free.
"""
import glob
import json
import os
import subprocess
import sys

import numpy as np
import pytest

from graphulator import engine
from graphulator import model as M
from graphulator.model.legacy_job import compile_jobs, compute_job
from graphulator.model.migrate import from_legacy, legacy_node_id

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = sorted(glob.glob(os.path.join(ROOT, "examples", "**", "*.pgraph"), recursive=True)
               + glob.glob(os.path.join(ROOT, "src", "graphulator", "examples", "**", "*.pgraph"),
                           recursive=True))
PG = os.path.join(ROOT, "examples", "pgraphs")
SCENES = os.path.join(ROOT, "examples", "test_scenes")


def _is_lumped(doc):
    try:
        engine.compile_document(doc)
        return True
    except engine.NotLumpedError:
        return False


DOCS = {os.path.relpath(f, ROOT): f for f in FILES}
LUMPED = [k for k, f in DOCS.items() if _is_lumped(M.load(f))]
NOT_LUMPED = [k for k in DOCS if k not in LUMPED]


def _port_ref(doc, plane_id):
    """Plane id -> the legacy port ref (B_ext node id, or 'port:<id>')."""
    pl = doc.by_id("planes")[plane_id]
    node = pl.extras.get("legacy_B_ext_node")
    return node if node is not None else f"port:{plane_id[len('port'):]}"


def assert_matches_legacy(doc, f=None):
    jobs = compile_jobs(doc, f_root_s=f)
    legacy = [compute_job(j) for j in jobs]
    new = engine.solve(doc, f)
    assert len(new) == len(legacy), "component count"
    for r, l, j in zip(new, legacy, jobs):
        assert legacy_node_id(r.root) == j["root_node_id"], "root"
        assert (r.S is None) == (l is None), "missing-parameter verdict"
        if l is None:
            continue
        assert [_port_ref(doc, p) for p in r.ports] == l["port_ids"], "port order"
        assert r.port_labels == [l["port_dict"][ref]["label"] for ref in l["port_ids"]]
        assert np.array_equal(r.S, l["S"]), (
            f"S differs: max |dS| = {np.max(np.abs(r.S - l['S'])):.3e}")
    return new


# ---------------------------------------------------------------------------
# the gate: every lumped shipped file
# ---------------------------------------------------------------------------

def test_lumped_set():
    assert len(LUMPED) == 54 and len(NOT_LUMPED) == 14


@pytest.mark.parametrize("key", LUMPED)
def test_shipped_bit_for_bit(key):
    assert_matches_legacy(M.load(DOCS[key]))


@pytest.mark.parametrize("key", NOT_LUMPED)
def test_non_lumped_refused(key):
    with pytest.raises(engine.NotLumpedError, match="milestone 2"):
        engine.solve(M.load(DOCS[key]))


# ---------------------------------------------------------------------------
# edits the files have not seen
# ---------------------------------------------------------------------------

def _load(name):
    """A shipped file by basename (examples/ first, then the packaged ones)."""
    return M.load(next(f for f in FILES if os.path.basename(f) == name))


@pytest.mark.parametrize("root", ["n4", "n6"])
def test_teufelator_roots(root):
    doc = _load("TEUFELATOR.pgraph")
    doc.solve.root = root
    (r,) = assert_matches_legacy(doc)
    assert r.root == root
    assert r.msuper.root_conj == doc.by_id("modes")[root].conj


def test_custom_grid():
    assert_matches_legacy(_load("DTWPA_8MODE.pgraph"), np.linspace(5.5, 6.5, 37))


def test_edited_values():
    doc = _load("4MODE_ISOLATOR.pgraph")
    doc.modes[1].freq += 0.013
    doc.modes[2].B_int = 0.021
    doc.pumped[0].rate *= 1.7
    doc.pumped[1].phase = 33.0
    doc.couplings[0].rate = 0.077
    assert_matches_legacy(doc)


def _delete_mode(doc, mid):
    doc.modes = [m for m in doc.modes if m.id != mid]
    dead = {e.id for e in doc.couplings + doc.pumped if mid in (e.a, e.b)}
    doc.couplings = [c for c in doc.couplings if c.id not in dead]
    doc.pumped = [p for p in doc.pumped if p.id not in dead]
    gone_planes = {a.plane for a in doc.attachments if a.mode == mid and a.id.startswith("bext")}
    doc.attachments = [a for a in doc.attachments if a.mode != mid]
    doc.planes = [p for p in doc.planes if p.id not in gone_planes]
    dr = doc.drawing
    dr.order["nodes"] = [n for n in dr.order["nodes"] if f"n{n}" != mid]
    dr.order["edges"] = [e for e in dr.order["edges"]
                         if e not in dead and mid not in (dr.edges[e].get("_ends") or [])]
    dr.nodes.pop(mid, None)


def test_deleted_mode_splits_components():
    doc = _load("5MODE_CHEBY.pgraph")
    _delete_mode(doc, "n2")                  # chain 0-1-2-3-4 -> {0,1} and {3,4}
    res = assert_matches_legacy(doc)
    assert len(res) == 2


def test_loss_port():
    with open(os.path.join(SCENES, "PORT_2NODES_STACK.pgraph")) as fh:
        d = json.load(fh)
    d["ports"].append({"port_id": 1, "label": "L", "monitored": False, "pos": [0, 0],
                       "attachments": [{"node_id": 1, "rate": 0.05, "sign": 1}]})
    doc = from_legacy(d)
    (r,) = assert_matches_legacy(doc)
    assert [c.monitored for c in r.msuper.channels] == [True, False]
    assert r.S.shape[1:] == (1, 1)


def test_fpja_reroot_pins_legacy_tree():
    """FPJA_PRA at root B: the tree changes and the stale A-B value (0.0)
    becomes an input, exactly as in legacy (design note F1; fixed at C1)."""
    doc = _load("FPJA_PRA.pgraph")
    (r0,) = assert_matches_legacy(doc)
    assert r0.msuper.frames.offsets["n1"] == 1.601
    doc.solve.root = "n1"
    (r1,) = assert_matches_legacy(doc)
    assert r1.msuper.frames.offsets["n0"] == 0.0


def test_stale_chord_values_reported():
    for name, edge in (("FPJA_PRA.pgraph", "e0_1"), ("DTWPA_2_WIDE.pgraph", "e13_10")):
        (r,) = engine.solve(_load(name))
        notes = [i.msg for i in r.issues if i.level == "info"]
        assert any(f"edge {edge} is a chord" in n for n in notes), notes


def test_sectors_are_integer_vectors():
    """nu_k = m_k . f_tones over the nonzero tones, root at sector 0
    (DELTA_AMP_WIDE: two nonzero tones, mixed sectors such as (1, -1))."""
    doc = _load("DELTA_AMP_WIDE.pgraph")
    (r,) = engine.solve(doc)
    tones = {t.id: t.f for t in doc.tones}
    f = [tones[t] for t in r.msuper.tones]
    for row in r.msuper.rows:
        assert row.nu == round(float(sum(k * x for k, x in zip(row.sector, f))), 12)
    assert len(f) == 2 and all(x != 0 for x in f)
    assert dict((row.mode, row.sector) for row in r.msuper.rows)[r.root] == (0, 0)
    assert (1, -1) in {row.sector for row in r.msuper.rows}


def test_missing_tree_fp_gives_no_result():
    """A Coupling (f_p never entered) can only be a chord: on a tree edge the
    component has no result, as in legacy."""
    doc = _load("AMP_BA.pgraph")
    p = doc.pumped[0]
    doc.pumped = []
    doc.couplings.append(M.Coupling(id=p.id, a=p.a, b=p.b, rate=p.rate, phase=p.phase))
    (r,) = assert_matches_legacy(doc)
    assert r.S is None
    assert any("f_p on tree edge" in i.msg for i in r.issues)


def test_parallel_edges_summed():
    """Two edges on one pair add (legacy kept only the last; no shipped file
    has any). The extra beta lands on (earlier, later) whatever its drawn
    direction."""
    doc = _load("Delta_Amp2.pgraph")
    c = doc.couplings[0]
    (r0,) = engine.solve(doc)
    doc.couplings.append(M.Coupling(id="extra", a=c.b, b=c.a, rate=0.02, phase=10.0))
    (r1,) = engine.solve(doc)
    assert any("parallel edges" in i.msg for i in r1.issues)
    ids = [x.mode for x in r1.msuper.rows]
    j, k = sorted((ids.index(c.a), ids.index(c.b)))
    d = engine.M_stack(r1.msuper, [6.0])[0] - engine.M_stack(r0.msuper, [6.0])[0]
    extra = 0.01 * np.exp(1j * np.pi / 18)
    assert np.isclose(d[j, k], extra) and np.isclose(d[k, j], np.conj(extra))


def test_no_qt_import():
    code = ("import sys; from graphulator import engine, model; "
            "d = model.load(sys.argv[1]); engine.solve(d); "
            "assert not [m for m in sys.modules if m.startswith(('PySide6', 'PyQt'))]")
    subprocess.run([sys.executable, "-c", code, os.path.join(PG, "AMP_BA.pgraph")],
                   check=True, cwd=ROOT)
