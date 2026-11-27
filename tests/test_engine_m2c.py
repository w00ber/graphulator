"""Step 4, milestone 2c: capacitive taps as C_c in Sigma_0, the tank in the
impedance (Foster I) form at its own node, and the -f image poles.

Oracle: an independent nodal solve of the physical circuit, written here
(lossless line two-ports from cos/sin, shunt tanks, series coupling
capacitors), fed the element values the engine reports for each tank. The
anchor conversion itself is checked against its defining relations.
"""
import copy
import os

import numpy as np
import pytest

from graphulator import engine
from graphulator import model as M
from graphulator.model.taps import resolve_taps, tap_issues

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TL2 = os.path.join(ROOT, "examples", "pgraphs", "TL_2_MODE_TAPPED_ONTO_A_LINE.pgraph")
TAP2 = os.path.join(ROOT, "examples", "test_scenes", "LINE_TAP_2NODES.pgraph")
NODE2 = os.path.join(ROOT, "examples", "test_scenes", "NODE_2LINES_TAP.pgraph")
F = np.linspace(1.0, 7.0, 1201) + 1.234e-3     # off the line poles n FSR (the oracle's sin -> 0)


# ---------------------------------------------------------------------------
# independent circuit solver (e^{-i w t}; GHz, ohm, nF, nH)
# ---------------------------------------------------------------------------

def _circuit_S(f, n_nodes, ports, stamps):
    """ports: [(node, Z0)]; stamps: callables (w, Y) adding admittances."""
    out = np.empty((len(f), len(ports), len(ports)), complex)
    for i, x in enumerate(f):
        w = 2 * np.pi * x
        Y = np.zeros((n_nodes, n_nodes), complex)
        for st in stamps:
            st(x, w, Y)
        for node, Z0 in ports:
            Y[node, node] += 1 / Z0
        for q, (nq, Zq) in enumerate(ports):
            rhs = np.zeros(n_nodes, complex)
            rhs[nq] = 2 / np.sqrt(Zq)
            V = np.linalg.solve(Y, rhs)
            for p, (np_, Zp) in enumerate(ports):
                out[i, p, q] = V[np_] / np.sqrt(Zp) - (p == q)
    return out


def line(a, b, FSR, Z):
    def st(x, w, Y):
        t = np.pi * x / FSR
        B = -1j * Z * np.sin(t)         # ABCD of a lossless line, e^{-i w t}
        Y[a, a] += np.cos(t) / B        # Y = [[D, -1], [-1, A]] / B
        Y[b, b] += np.cos(t) / B
        Y[a, b] -= 1 / B
        Y[b, a] -= 1 / B
    return st


def shunt_tank(a, C, L):
    def st(x, w, Y):
        Y[a, a] += -1j * w * C + 1j / (w * L)
    return st


def series_C(a, b, C):
    def st(x, w, Y):
        y = -1j * w * C
        Y[a, a] += y
        Y[b, b] += y
        Y[a, b] -= y
        Y[b, a] -= y
    return st


def _tank(doc, mode):
    d, _, _ = resolve_taps(doc)
    return d.by_id("modes")[mode].extras["tap_resolved"]


def _with_zd(path, zds, drop_port=None):
    doc = M.load(path)
    if drop_port:
        doc.attachments = [a for a in doc.attachments if a.plane != drop_port]
        doc.planes = [p for p in doc.planes if p.id != drop_port]
        doc.drawing.ports.pop(drop_port, None)
    for m, z in zds.items():
        doc.by_id("modes")[m].extras["Z_d"] = z
    return doc


def _S(doc, f=F):
    (r,) = engine.solve(doc, f)
    return r


# ---------------------------------------------------------------------------
# the anchor
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("Zd", [5.0, 25.0, 125.0, 625.0])
def test_anchor_reproduces_the_rate_and_the_drawn_frequency(Zd):
    """rate = w1 C_c u / (2 pi sqrt(C_sum C_n)) and w1^2 L_d C_sum = 1, with
    Z_d = sqrt(L_d / C_sum)."""
    doc = _with_zd(TL2, {"n0": Zd}, drop_port="port1")
    t = _tank(doc, "n0")
    (Cc,) = t["C_c"].values()
    C_sum = t["C_d"] + Cc
    w1 = 2 * np.pi * 4.4
    Cn = 1 / (4 * 65.0 * 1.5)
    assert w1 ** 2 * t["L_d"] * C_sum == pytest.approx(1, rel=1e-13)
    assert np.sqrt(t["L_d"] / C_sum) == pytest.approx(Zd, rel=1e-13)
    assert w1 * Cc / (2 * np.pi * np.sqrt(C_sum * Cn)) == pytest.approx(0.05, rel=1e-13)


def test_anchor_matches_the_m2c_note_single_tap_form():
    """gamma = rate^2 2 pi Z_ref C_n / u^2 (design note, M2c) is the leak rate
    of the resolved tank into Z_ref: Z_ref w1^2 C_c^2 / (2 pi C_sum)."""
    doc = _with_zd(TL2, {"n0": 25.0}, drop_port="port1")
    t = _tank(doc, "n0")
    (Cc,) = t["C_c"].values()
    C_sum = t["C_d"] + Cc
    w1 = 2 * np.pi * 4.4
    gamma_note = 0.05 ** 2 * 2 * np.pi * 50.0 / (4 * 65.0 * 1.5)
    assert 50.0 * w1 ** 2 * Cc ** 2 / (2 * np.pi * C_sum) == pytest.approx(gamma_note, rel=1e-13)


# ---------------------------------------------------------------------------
# S against the circuit
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("Zd", [5.0, 25.0, 125.0, 625.0, 3125.0])
def test_one_tap_equals_the_circuit(Zd):
    """TL_2 without its direct port: line (x0 <- C_c <- tank), port at xL."""
    doc = _with_zd(TL2, {"n0": Zd}, drop_port="port1")
    t = _tank(doc, "n0")
    (Cc,) = t["C_c"].values()
    # nodes: 0 = xL (port0), 1 = x0, 2 = tank
    want = _circuit_S(F, 3, [(0, 50.0)],
                      [line(1, 0, 1.5, 65.0), series_C(1, 2, Cc), shunt_tank(2, t["C_d"], t["L_d"])])
    r = _S(doc)
    assert r.S is not None
    assert np.max(np.abs(r.S - want)) < 1e-10


def test_tl2_two_ports_equals_the_circuit():
    """TL_2 as shipped: the direct port fixes C_d; the tank's node is port1."""
    doc = M.load(TL2)
    t = _tank(doc, "n0")
    assert 1 / (2 * np.pi * 50.0 * t["C_d"]) == pytest.approx(0.1, rel=1e-13)
    (Cc,) = t["C_c"].values()
    r = _S(doc)
    order = r.ports
    # nodes: 0 = port0 (xL), 1 = port1 (tank), 2 = x0
    node = {"port0": 0, "port1": 1}
    want = _circuit_S(F, 3, [(node[p], 50.0) for p in order],
                      [line(2, 0, 1.5, 65.0), series_C(2, 1, Cc), shunt_tank(1, t["C_d"], t["L_d"])])
    assert np.max(np.abs(r.S - want)) < 1e-10


def test_two_modes_on_one_line_end_equal_the_circuit():
    doc = _with_zd(TAP2, {"n0": 40.0, "n1": 80.0})
    t0, t1 = _tank(doc, "n0"), _tank(doc, "n1")
    (c0,), (c1,) = t0["C_c"].values(), t1["C_c"].values()
    # nodes: 0 = xL (port0), 1 = x0, 2 = tank n0, 3 = tank n1
    want = _circuit_S(F, 4, [(0, 50.0)],
                      [line(1, 0, 1.5, 65.0),
                       series_C(1, 2, c0), shunt_tank(2, t0["C_d"], t0["L_d"]),
                       series_C(1, 3, c1), shunt_tank(3, t1["C_d"], t1["L_d"])])
    assert np.max(np.abs(_S(doc).S - want)) < 1e-10


def test_one_mode_on_two_lines_equals_the_circuit():
    doc = _with_zd(NODE2, {"n0": 40.0})
    t = _tank(doc, "n0")
    cs = t["C_c"]
    ca, cb = cs["line0.xL.t0"], cs["line1.x0.t0"]
    r = _S(doc)
    node = {"port0": 0, "port1": 1}
    # nodes: 0 = port0 (line0.x0), 1 = port1 (line1.xL), 2 = line0.xL, 3 = line1.x0, 4 = tank
    want = _circuit_S(F, 5, [(node[p], 50.0) for p in r.ports],
                      [line(0, 2, 1.5, 65.0), line(3, 1, 2.0, 65.0),
                       series_C(2, 4, ca), series_C(3, 4, cb), shunt_tank(4, t["C_d"], t["L_d"])])
    assert np.max(np.abs(r.S - want)) < 1e-10


# ---------------------------------------------------------------------------
# images, and what dropping them costs
# ---------------------------------------------------------------------------

def test_without_images_the_resonance_moves_by_the_predicted_pull():
    """Deleting the tank's -f0 image shifts the dressed resonance by
    d^2 / (2 f0), d = f1 - f0 the pull C_c gives (v38 sec. 3.6-3.7; the
    RWA-checker number for an embedded mode)."""
    f = np.linspace(4.2, 4.6, 80001) + 1.1e-9
    for Zd in (125.0, 625.0):
        doc = _with_zd(TL2, {"n0": Zd}, drop_port="port1")
        t = _tank(doc, "n0")
        f0 = 1 / (2 * np.pi * np.sqrt(t["L_d"] * t["C_d"]))
        base = copy.deepcopy(doc)
        base.attachments = [a for a in base.attachments if a.element is None]
        base.modes = []
        S0 = _S(base, f).S[:, 0, 0]
        on = _S(doc, f).S[:, 0, 0]
        doc.solve.images = False
        off = _S(doc, f).S[:, 0, 0]
        f_on = f[np.argmax(np.abs(on - S0))]
        f_off = f[np.argmax(np.abs(off - S0))]
        d = f_on - f0
        assert (f_on - f_off) == pytest.approx(d * d / (2 * f0), rel=0.02)


def test_lumped_documents_keep_the_rwa_by_default():
    """Images default off for lumped documents, so milestone 1 is unchanged."""
    path = os.path.join(ROOT, "examples", "test_scenes", "PORT_1NODE.pgraph")
    doc = M.load(path)
    (net,) = engine.compile_network(doc)
    assert not net.cmt[0].images


def test_a_lone_mode_on_a_port_with_images_is_the_exact_tank():
    """PORT_SHARED_2LINES' kind of attachment, alone: the mode with its image
    is the parallel tank C = 1/(2 pi Z_ref gamma), L from f0, on the port."""
    doc = M.load(TL2)
    doc.blocks, doc.attachments = [], [a for a in doc.attachments if a.element is None]
    doc.planes = [p for p in doc.planes if p.id == "port1"]
    doc.planes[0].Z0 = 50.0
    doc.blocks.append(M.schema.Block(id="R", type="R", params={"R": 1e12}, terminals={"a": "port1"}))
    r = _S(doc)
    C = 1 / (2 * np.pi * 50.0 * 0.1)
    L = 1 / ((2 * np.pi * 4.4) ** 2 * C)
    want = _circuit_S(F, 1, [(0, 50.0)], [shunt_tank(0, C, L)])
    assert np.max(np.abs(r.S - want)) < 1e-6           # the 1e12 ohm R is the residual


# ---------------------------------------------------------------------------
# what is asked of the user, and what is refused
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", [TAP2, NODE2])
def test_missing_mode_impedance_is_an_error_not_a_guess(path):
    doc = M.load(path)
    errs = [i for i in M.validate(doc) if i.level == "error"]
    assert errs and all("Z_d" in i.msg for i in errs)
    assert {i.path for i in errs} == {i.path for i in tap_issues(doc)}
    (r,) = engine.solve(doc, F)
    assert r.S is None
    assert any("Z_d" in i.msg for i in r.issues)


def test_inductive_tap_is_refused():
    doc = M.load(TL2)
    for a in doc.attachments:
        if a.element:
            a.element = "L"
    with pytest.raises(engine.NotSupportedError, match="Inductive taps"):
        engine.solve(doc, F)


def test_resolved_document_round_trips_through_the_schema():
    doc = _with_zd(TAP2, {"n0": 40.0, "n1": 80.0})
    d, _, _ = resolve_taps(doc)
    back = M.schema.Document.from_dict(d.to_dict())
    assert np.max(np.abs(_S(back).S - _S(doc).S)) == 0.0
