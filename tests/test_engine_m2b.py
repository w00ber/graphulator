"""Step 4, milestone 2b: the CMT block as a z-multiport; kept poles as rows.

Gates (docs/design/step4_msuper_m2.md):
- 4: every lumped shipped file through the M2 path equals milestone 1. The
  two are the same physics by an identity (Woodbury: a lumped document is
  the reflection of its own z on Z_ref terminations), computed by different
  algebra (bordered system vs M^-1), so the gate is to rounding:
  1e-13 max(1, max|S|), relative because the gain files reach |S| = 526.
- PORT_SHARED_2LINES (D1, D2): two lines and a mode in parallel on one port,
  against the closed form Y = Y_a + Y_b + 1 / (Z0 z), z = (i/2) gamma / (f - f0)
  (plus (i/2) gamma / (f + f0) with the M2c image poles).
- 3: S does not depend on the kept poles (none, a few, all below f_max),
  through pole hits and in every sector; the kept poles' residues are the
  line's own (an independent contour integral of the exact impedance), so the
  remainder is analytic at them.
"""
import glob
import os

import numpy as np
import pytest

from graphulator import engine
from graphulator import model as M
from graphulator.engine.network import compile_network, line_z, solve_network, z_rem

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALL = sorted(glob.glob(os.path.join(ROOT, "examples", "**", "*.pgraph"), recursive=True)
             + glob.glob(os.path.join(ROOT, "src", "graphulator", "examples", "**", "*.pgraph"),
                         recursive=True))
FILES = {os.path.basename(f): f for f in ALL}


def _kind(path):
    try:
        return engine.classify(M.load(path))
    except engine.NotSupportedError:
        return "refused"


KINDS = {os.path.relpath(f, ROOT): _kind(f) for f in ALL}
LUMPED = [k for k, v in KINDS.items() if v == "lumped"]
NETWORK = [k for k, v in KINDS.items() if v == "network"]


def load(name):
    return M.load(FILES[name])


def test_counts():
    # the three tap scenes joined the network set in milestone 2c; the
    # validation campaigns (examples/test_scenes/MSUPER_*) add 1 lumped and
    # 10 network scenes, and one the engine refuses on purpose (inductive tap)
    assert len(LUMPED) == 55 and len(NETWORK) == 24
    assert [os.path.basename(k) for k, v in KINDS.items() if v == "refused"] == [
        "S1f_INDUCTIVE_TAP_FALLBACK.pgraph"]


# ---------------------------------------------------------------------------
# gate 4: lumped files through the network = milestone 1
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", LUMPED)
def test_lumped_through_network_equals_m1(key):
    doc = M.load(os.path.join(ROOT, key))
    m1 = engine.solve(doc)
    m2 = solve_network(doc)
    for r1 in m1:
        if not r1.ports:                     # nothing to scatter into (DTWPA_4x)
            assert not [r for r in m2 if r.S is not None and not r.ports]
            continue
        (r2,) = [r for r in m2 if set(r1.ports) <= set(r.ports)]
        assert (r2.S is None) == (r1.S is None)
        if r1.S is None:
            continue
        assert set(r2.ports) == set(r1.ports)
        idx = [r2.ports.index(p) for p in r1.ports]
        S2 = r2.S[:, idx][:, :, idx]
        assert np.max(np.abs(S2 - r1.S)) < 1e-13 * max(1.0, np.max(np.abs(r1.S)))


def test_loss_port_is_a_matched_resistor():
    import json

    from graphulator.model.migrate import from_legacy
    with open(os.path.join(ROOT, "examples", "test_scenes", "PORT_2NODES_STACK.pgraph")) as fh:
        d = json.load(fh)
    d["ports"].append({"port_id": 1, "label": "L", "monitored": False, "pos": [0, 0],
                       "attachments": [{"node_id": 1, "rate": 0.05, "sign": 1}]})
    doc = from_legacy(d)
    (r1,) = engine.solve(doc)
    (r2,) = solve_network(doc)
    assert r2.ports == r1.ports
    assert np.max(np.abs(r2.S - r1.S)) < 1e-13


# ---------------------------------------------------------------------------
# D1/D2 on a physical file
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("images", [False, True])
def test_port_shared_2lines_closed_form(images):
    """With images (the M2c default on physical documents) the lone mode is
    its exact Foster pair; without, the RWA pole of M2b."""
    doc = load("PORT_SHARED_2LINES.pgraph")
    doc.solve.images = images
    (r,) = engine.solve(doc)
    f = r.f
    Y = -1j * np.tan(np.pi * f / 1.5) / 65 - 1j * np.tan(np.pi * f / 2.0) / 65
    z = 0.5j * 0.2 / (f - 4.4)                      # the lone mode: B_int 0, rate 0.2
    if images:
        z = z + 0.5j * 0.2 / (f + 4.4)
    Y = Y + 1 / (50 * z)
    S = (1 - 50 * Y) / (1 + 50 * Y)
    assert np.max(np.abs(r.S[:, 0, 0] - S)) < 1e-12
    (net,) = r.network,
    assert len(net.cmt) == 1 and net.cmt[0].Zr == 50.0 and net.cmt[0].images == images


def test_rates_are_quoted_against_z_ref():
    """D3: a rate is the leak rate into Z_ref. A lone mode on a port whose Z0
    equals Z_ref reflects as in milestone 1 whatever Z_ref is; with
    Z0 != Z_ref the port sees the same z through a mismatch."""
    doc = load("PORT_SHARED_2LINES.pgraph")
    doc.blocks = []
    f = np.linspace(4.0, 4.8, 81) + 1.234e-7        # off f0 (the closed form divides by f - f0)
    (r50,) = solve_network(doc, f)
    gamma = 0.2
    S_cmt = (0.5j * gamma - (f - 4.4)) / (0.5j * gamma + (f - 4.4))
    assert np.max(np.abs(r50.S[:, 0, 0] - S_cmt)) < 1e-13
    doc.units["z_ref"] = 25.0                       # Z0 = 50 = 2 Z_ref
    (r25,) = solve_network(doc, f)
    z = 0.5 * (0.5j * gamma / (f - 4.4))            # z in units of Z0
    assert np.max(np.abs(r25.S[:, 0, 0] - (z - 1) / (z + 1))) < 1e-13


def test_modes_with_element_pumps_refused():
    doc = load("TL_3_PUMPED_TERMINATION_AMPLIFIER.pgraph")
    doc.modes.append(M.Mode("n9", "x", 4.0, 0.0))
    doc.attachments.append(M.Attachment("a9", "n9", "port0", 0.1))
    with pytest.raises(engine.NotSupportedError, match="element pumps"):
        engine.solve(doc)


def test_mode_outside_sector_zero_refused():
    doc = load("PORT_SHARED_2LINES.pgraph")
    doc.modes[0].conj = True
    with pytest.raises(engine.NotSupportedError, match="outside sector 0"):
        engine.solve(doc)


# ---------------------------------------------------------------------------
# gate 3: kept poles
# ---------------------------------------------------------------------------

def _invariant(doc, f=None):
    """Both forms are exact; they round differently. Next to a high-Q line
    mode the system's condition number reaches ~4e3 (Lee conversion, its
    port at 38718 ohm barely loads the mode), so the two agree to ~eps cond
    = 1e-12 there and to ~1e-15 elsewhere; near a gain pole the rounding
    grows like |S|^2."""
    (r0,) = solve_network(doc, f)
    (r1,) = solve_network(doc, r0.f, promote=True)
    assert r1.sectors == r0.sectors
    scale = max(1.0, np.nanmax(np.abs(r0.S))) ** 2
    for m in r0.S_sectors:
        assert np.max(np.abs(r1.S_sectors[m] - r0.S_sectors[m])) < 1e-11 * scale
    return r1


def _zd_missing(doc):
    from graphulator.model.taps import tap_issues
    return [i.path.split("/", 1)[1] for i in tap_issues(doc)]


@pytest.mark.parametrize("key", NETWORK)
def test_kept_poles_below_f_max_leave_s_unchanged(key):
    doc = M.load(os.path.join(ROOT, key))
    for mode in _zd_missing(doc):
        doc.by_id("modes")[mode].extras["Z_d"] = 50.0   # any Z_d completes the tank
    r = _invariant(doc)
    assert sum(len(ln.poles) for ln in r.network.lines) > 0


@pytest.mark.parametrize("spec", [[0], [3], [1, 2, 3], [2, 5, 9]])
def test_kept_pole_subsets(spec):
    """Promote 1, 3 or scattered poles, on a sweep that hits n FSR exactly
    (f = 4.5 is pole 3 of TL_1's line) and in every sector of TL_3."""
    for name in ("TL_1_OPEN_LINE_ON_A_PORT.pgraph", "TL_3_PUMPED_TERMINATION_AMPLIFIER.pgraph"):
        doc = load(name)
        doc.solve.kept_poles["line0"] = list(spec)
        r = _invariant(doc)
        assert [kp.n for kp in r.network.lines[0].poles] == spec


def _residue(ln, p, r=1e-3):
    """(1 / 2 pi i) contour integral of the exact Z around p, radius r."""
    phi = 2 * np.pi * np.arange(64) / 64
    z = p + r * ln.FSR * np.exp(1j * phi)
    Z = line_z(ln, z)
    return np.mean(Z * (r * ln.FSR * np.exp(1j * phi))[:, None, None], axis=0)


@pytest.mark.parametrize("name", ["TL_1_OPEN_LINE_ON_A_PORT.pgraph",
                                  "TL_4_INDUCTIVELY_LOADED_LINE.pgraph",
                                  "INTERMODE_LEE2013_CONVERSION.pgraph",
                                  "TL_5_TWO_LINES_ONE_PORT.pgraph"])
def test_kept_poles_are_the_lines_own(name):
    """Residue and position of every kept pole (uniform, loaded, stepped)
    against the exact impedance: the contour integral equals R_n, and Z_rem
    stays bounded at the pole (it would grow like 1/(f - p) otherwise)."""
    for net in compile_network(load(name), promote=True):
        for ln in net.lines:
            for kp in ln.poles:
                R = _residue(ln, kp.p)
                assert np.max(np.abs(R - kp.residue())) < 1e-9 * np.max(np.abs(R))
                near = kp.f0 + ln.FSR * np.array([-1e-7, 1e-7, -1e-4, 1e-4])
                Zr = z_rem(ln, near)
                assert np.max(np.abs(Zr[:2])) < 10 * np.max(np.abs(Zr[2:])) + 1e-9


def test_lossy_line_kept_poles():
    """Uniform loss: the poles sit at f_n - i alpha FSR / pi exactly."""
    doc = M.Document()
    doc.planes = [M.Plane("p1", "P1", "port", 50.0), M.Plane("p2", "P2", "port", 30.0)]
    doc.blocks = [M.Block("ln", "line", {"FSR": 1.3, "Ztx": 60.0, "alpha_uniform": 0.01},
                          {"x0": "p1", "xL": "p2"})]
    doc.solve.kept_poles["ln"] = {"f_max": 4.0}
    r = _invariant(doc, np.linspace(0.0, 5.2, 521))
    (net,) = compile_network(doc, promote=True)
    for kp in net.lines[0].poles:
        assert np.max(np.abs(_residue(net.lines[0], kp.p) - kp.residue())) < 1e-9 * abs(kp.c)
    assert r.S.shape == (521, 2, 2)


def test_lossy_loaded_promotion_refused():
    doc = load("TL_4_INDUCTIVELY_LOADED_LINE.pgraph")
    doc.by_id("blocks")["line0"].params["alpha_uniform"] = 0.01
    with pytest.raises(engine.NotSupportedError, match="lossy loaded"):
        solve_network(doc, promote=True)
