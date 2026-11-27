"""Step 4, milestone 2a: physical documents as an exact network over sectors.

Gates (docs/design/step4_msuper_m2.md, "Gates"):
1. exact, unpumped: TL_1 and TL_5 against closed forms; TL_1 against legacy
   with the tail closure on (legacy is exact there);
2. pumped: TL_3 against E0's hb_sectors at windows {-1..0}..{-6..5} and E0's
   peak table; every pumped file against an independent nodal HB written
   here (its own ABCD cascade, its own mode roots, mode masses by quadrature
   and its own anchor -> depth conversion); Manley-Rowe on lossless files;
   unitarity on lossless unpumped networks;
3. (M2a part) S does not depend on kept_poles' f_max while the anchor stays
   in the comb;
plus refusals (2b/2c files), windows, labels, no Qt.

Oracle precision: the oracles evaluate cot/csc admittances, which lose
digits next to a line pole (f_m = n FSR on an unloaded section); the engine
uses pole-free ABCD rows. Comparisons are therefore made away from poles
(|Y| Z < 1e4), and the residual near them is the oracle's.
"""
import glob
import os
import subprocess
import sys

import numpy as np
import pytest

from graphulator import engine
from graphulator import model as M
from graphulator.model.legacy_job import compile_jobs, compute_job

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "misc"))
import msuper_E0_tl3_sectors as E0  # noqa: E402

FILES = {os.path.basename(f): f for f in
         glob.glob(os.path.join(ROOT, "examples", "**", "*.pgraph"), recursive=True)}
NETWORK = ["TL_1_OPEN_LINE_ON_A_PORT.pgraph", "TL_3_PUMPED_TERMINATION_AMPLIFIER.pgraph",
           "TL_4_INDUCTIVELY_LOADED_LINE.pgraph", "TL_5_TWO_LINES_ONE_PORT.pgraph",
           "INTERMODE_LEE2013_CONVERSION.pgraph", "INTERMODE_LEE2013_DEGENERATE_AMP.pgraph",
           "INTERMODE_LEE2013_NONDEGENERATE_AMP.pgraph", "LINE_PUMPED_AMP_AND_CONV.pgraph",
           "LINE_PUMPED_LOADED.pgraph", "LINE_PUMPED_TERMINATION.pgraph"]
PUMPED = [k for k in NETWORK if M.load(FILES[k]).pumped]
# Tap documents were refused until milestone 2c (test_engine_m2c). The two
# without a direct port need the user's Z_d and solve to S = None until then.
TAPPED = {"TL_2_MODE_TAPPED_ONTO_A_LINE.pgraph": True, "LINE_TAP_2NODES.pgraph": False,
          "NODE_2LINES_TAP.pgraph": False}


def load(name):
    return M.load(FILES[name])


# ---------------------------------------------------------------------------
# independent oracle: nodal HB on the circuit read straight off the document
# ---------------------------------------------------------------------------

def abcd(f, FSR, sections, alpha=0.0):
    """ABCD from x0 to xL, e^{-i w t}: [[cos, -iZ sin], [-i sin/Z, cos]]."""
    th = np.pi * f / FSR + 1j * alpha
    T = np.eye(2, dtype=complex)
    for Z, frac in sections:
        t = th * frac
        T = T @ np.array([[np.cos(t), -1j * Z * np.sin(t)], [-1j * np.sin(t) / Z, np.cos(t)]])
    return T


def y_from_abcd(T):
    (A, B), (C, D) = T
    return np.array([[D / B, -1.0 / B], [-1.0 / B, A / B]])


def circuit(doc):
    """The one-line circuit of a shipped M2a file, as plain numbers."""
    (ln,) = [b for b in doc.blocks if b.type == "line"]
    p = ln.params
    secs = p.get("sections")
    sections = ([(s["Z"], s["frac"] / sum(x["frac"] for x in secs)) for s in secs]
                if secs else [(p["Ztx"], 1.0)])
    (port,) = [pl for pl in doc.planes if pl.kind == "port"]
    port_end = next(e for e in ("x0", "xL") if ln.terminals[e] == port.id)
    loads = [b for b in doc.blocks if b.type == "L"]
    load_end, f_Z = None, None
    if loads:
        load_end = next(e for e in ("x0", "xL") if ln.terminals[e] == loads[0].terminals["a"])
        f_Z = loads[0].params["f_Z"]
    pump = doc.pumped[0] if doc.pumped else None
    return dict(FSR=p["FSR"], Ztx=p["Ztx"], alpha=p.get("alpha_uniform", 0.0),
                sections=sections, Z0=port.Z0, port_end=port_end, load_end=load_end,
                f_Z=f_Z, pump=pump, f_p=(doc.by_id("tones")[pump.tone].f if pump else 0.0))


def _abcd_vec(f, FSR, sections):
    th = np.pi * np.asarray(f, float) / FSR
    A, B, C, D = (np.ones_like(th, complex), np.zeros_like(th, complex),
                  np.zeros_like(th, complex), np.ones_like(th, complex))
    for Z, frac in sections:
        t = th * frac
        a, b, cc, d = np.cos(t), -1j * Z * np.sin(t), -1j * np.sin(t) / Z, np.cos(t)
        A, B, C, D = A * a + B * cc, A * b + B * d, C * a + D * cc, C * b + D * d
    return A, B, C, D


def modes(c, f_top):
    """[(f_n, u_n at the pumped end, C_n), n = 1, 2, ...] below f_top, by
    root-finding and quadrature, written independently of LineResonator.

    The open end is the one without the load. From it, (V, I) = (1, 0); the
    far end is open (I = 0) or loaded (V = Z_L I). With T walking from the
    open end the far-end state is T^-1 (1, 0) = (D, -C), so the mode
    condition is C = 0 (open) or D + Z_L C = 0 (L load, Z_L = -i f Ztx / f_Z),
    both real on the real axis. C_n = int c u^2 dx by Gauss-Legendre.
    """
    origin = "x0" if c["load_end"] != "x0" else "xL"
    secs = c["sections"] if origin == "x0" else c["sections"][::-1]

    def cond(f):
        _, _, C, D = _abcd_vec(f, c["FSR"], secs)
        if c["load_end"] is None:
            return (1j * C).real
        return (D + (-1j * f * c["Ztx"] / c["f_Z"]) * C).real

    grid = np.linspace(1e-9, f_top, 200001)
    v = cond(grid)
    out = []
    xg, wg = np.polynomial.legendre.leggauss(60)
    for i in np.nonzero(np.sign(v[:-1]) * np.sign(v[1:]) < 0)[0]:
        lo, hi = grid[i], grid[i + 1]
        slo = np.sign(v[i])
        while True:
            mid = 0.5 * (lo + hi)
            if mid in (lo, hi):
                break
            if np.sign(cond(np.array([mid]))[0]) == slo:
                lo = mid
            else:
                hi = mid
        fn = 0.5 * (lo + hi)
        theta = np.pi * fn / c["FSR"]
        V, I, Cn = 1.0 + 0j, 0j, 0.0
        for Z, frac in secs:      # V(s) = V cos s + i Z I sin s inside a section
            d = theta * frac
            s = 0.5 * d * (xg + 1)
            u = (V * np.cos(s) + 1j * Z * I * np.sin(s)).real
            Cn += 0.5 * d * np.sum(wg * u ** 2) / (2 * Z * c["FSR"] * theta)
            V, I = V * np.cos(d) + 1j * Z * I * np.sin(d), 1j * V * np.sin(d) / Z + I * np.cos(d)
        u_pumped = 1.0 if c["pump"].legacy_anchor["end"] == origin else V.real
        out.append((fn, u_pumped, Cn))
    return out


def depth(c):
    """delta(1/L) from {rate, n_ref}: rate = g / pi with
    g = delta u_n u_m / (4 sqrt(w_n C_n w_m C_m)) at the anchor pair; m is the
    mode nearest the pump's partner target (amplification first on a tie,
    then down-, then up-conversion)."""
    an = c["pump"].legacy_anchor
    n = an["n_ref"]
    ms = modes(c, 4 * c["FSR"] + 2 * c["f_p"] + n * c["FSR"])
    fn, un, Cn = ms[n - 1]
    cand = []
    for rank, target in enumerate((c["f_p"] - fn, fn - c["f_p"], fn + c["f_p"])):
        if target > 0:
            k = min(range(len(ms)), key=lambda j: abs(ms[j][0] - target))
            cand.append((abs(ms[k][0] - target), rank, k + 1))
    m = min(cand)[2]
    fm, um, Cm = ms[m - 1]
    w_n, w_m = 2 * np.pi * fn, 2 * np.pi * fm
    return 4 * np.pi * an["rate"] * np.sqrt(w_n * Cn * w_m * Cm) / abs(un * um), (n, m)


def hb(c, f, window, delta):
    """Nodal HB, voltage unknowns at (x0, xL) per sector; returns
    (S: m -> (n_f,), mask of points away from line poles)."""
    idx = {m: k for k, m in enumerate(window)}
    pe = {"x0": 0, "xL": 1}
    out = {m: np.empty(len(f), complex) for m in window}
    ok = np.ones(len(f), bool)
    pump_node = pe[c["pump"].legacy_anchor["end"]] if c["pump"] else None
    phi = np.deg2rad(c["pump"].phase or 0.0) if c["pump"] else 0.0
    for i, x in enumerate(f):
        A = np.zeros((2 * len(window),) * 2, complex)
        rhs = np.zeros(2 * len(window), complex)
        for m in window:
            fm = x + m * c["f_p"]
            r = 2 * idx[m]
            Y = y_from_abcd(abcd(fm, c["FSR"], c["sections"], c["alpha"]))
            if np.max(np.abs(Y)) * c["Ztx"] > 1e4:
                ok[i] = False
            A[r:r + 2, r:r + 2] += Y
            A[r + pe[c["port_end"]], r + pe[c["port_end"]]] += 1 / c["Z0"]
            if c["load_end"]:
                A[r + pe[c["load_end"]], r + pe[c["load_end"]]] += 1j * c["f_Z"] / (c["Ztx"] * fm)
            if c["pump"]:
                for dm, ph in ((-1, np.exp(-1j * phi)), (1, np.exp(1j * phi))):
                    if m + dm in idx:
                        wk = 2 * np.pi * (x + (m + dm) * c["f_p"])
                        A[r + pump_node, 2 * idx[m + dm] + pump_node] += 0.5 * delta * ph * 1j / wk
        rhs[2 * idx[0] + pe[c["port_end"]]] = 2 / np.sqrt(c["Z0"])
        V = np.linalg.solve(A, rhs)
        for m in window:
            out[m][i] = V[2 * idx[m] + pe[c["port_end"]]] / np.sqrt(c["Z0"]) - (m == 0)
    return out, ok


# ---------------------------------------------------------------------------
# 1. exact, unpumped
# ---------------------------------------------------------------------------

def test_set():
    for k in NETWORK:
        assert engine.classify(load(k)) == "network"
    assert len(PUMPED) == 8


def test_tl1_closed_form_and_legacy():
    doc = load("TL_1_OPEN_LINE_ON_A_PORT.pgraph")
    (r,) = engine.solve(doc)
    f = r.f
    Y = -1j * np.tan(np.pi * f / 1.5) / 65.0             # open line: Z_in = i Ztx cot
    S = (1 - 50 * Y) / (1 + 50 * Y)
    assert np.max(np.abs(r.S[:, 0, 0] - S)) < 1e-12
    (leg,) = [compute_job(j) for j in compile_jobs(doc)]
    assert np.max(np.abs(r.S[:, 0, 0] - leg["S"][:, 0, 0])) < 1e-12
    assert r.sectors == [0] and r.port_labels == ["TL"]


def test_tl5_lines_in_parallel():
    """D1: two lines on one port plane are in parallel, Y = Y_a + Y_b (legacy
    splits them into two jobs; the model and the engine do not)."""
    doc = load("TL_5_TWO_LINES_ONE_PORT.pgraph")
    (r,) = engine.solve(doc)
    f = r.f
    Y = -1j * np.tan(np.pi * f / 1.5) / 65.0 - 1j * np.tan(np.pi * f / 1.0) / 40.0
    S = (1 - 50 * Y) / (1 + 50 * Y)
    ok = (np.abs(Y) * 50 < 1e6)
    assert np.max(np.abs(r.S[ok, 0, 0] - S[ok])) < 1e-12
    assert len(compile_jobs(doc)) == 2        # legacy's split, pinned elsewhere


def _two_port_line(alpha=0.0, sections=None, Z0=(50.0, 50.0)):
    doc = M.Document()
    doc.planes = [M.Plane("p1", "P1", "port", Z0[0]), M.Plane("p2", "P2", "port", Z0[1])]
    params = {"FSR": 1.3, "Ztx": 60.0, "alpha_uniform": alpha}
    if sections:
        params["sections"] = sections
    doc.blocks = [M.Block("ln", "line", params, {"x0": "p1", "xL": "p2"})]
    return doc


def test_two_port_line_abcd_and_unitarity():
    f = np.linspace(0.3, 5.0, 401)
    secs = [{"Z": 40.0, "frac": 1.0}, {"Z": 75.0, "frac": 2.0}]
    doc = _two_port_line(sections=secs, Z0=(50.0, 30.0))
    (r,) = engine.solve(doc, f)
    for i, x in enumerate(f):
        (A, B), (C, D) = abcd(x, 1.3, [(40.0, 1 / 3), (75.0, 2 / 3)])
        Z1, Z2 = 50.0, 30.0
        den = A * Z2 + B + C * Z1 * Z2 + D * Z1
        S11 = (A * Z2 + B - C * Z1 * Z2 - D * Z1) / den
        S21 = 2 * np.sqrt(Z1 * Z2) / den
        S22 = (-A * Z2 + B - C * Z1 * Z2 + D * Z1) / den
        assert abs(r.S[i, 0, 0] - S11) < 1e-12
        assert abs(r.S[i, 1, 0] - S21) < 1e-12 and abs(r.S[i, 0, 1] - S21) < 1e-12
        assert abs(r.S[i, 1, 1] - S22) < 1e-12
    U = np.einsum("fji,fjk->fik", r.S.conj(), r.S)
    assert np.max(np.abs(U - np.eye(2))) < 1e-12
    assert r.label(1, 0) == "(P2,P1):0" and r.label(0, 0) == "P1:0"


def test_uniform_loss_matches_complex_theta_and_dissipates():
    f = np.linspace(0.3, 5.0, 201)
    (r,) = engine.solve(_two_port_line(alpha=0.02), f)
    th = np.pi * f / 1.3 + 0.02j
    S21 = 2 / (2 * np.cos(th) - 1j * (60 / 50 + 50 / 60) * np.sin(th))
    assert np.max(np.abs(r.S[:, 1, 0] - S21)) < 1e-12
    power = np.sum(np.abs(r.S) ** 2, axis=1)
    assert np.all(power < 1)


@pytest.mark.parametrize("name", [k for k in NETWORK if k not in PUMPED])
def test_unpumped_lossless_unitary(name):
    (r,) = engine.solve(load(name))
    assert np.max(np.abs(np.abs(r.S) - 1)) < 1e-12


# ---------------------------------------------------------------------------
# 2. pumped
# ---------------------------------------------------------------------------

def _tl3(rate=None, window=None):
    doc = load("TL_3_PUMPED_TERMINATION_AMPLIFIER.pgraph")
    if rate is not None:                       # the depth is what is stored (D4)
        doc.pumped[0].legacy_anchor["rate"] = rate
        doc.pumped[0].depth = engine.pump_depth(doc, doc.pumped[0])[0]
    if window is not None:
        doc.solve.sectors = list(window)
    return doc


@pytest.mark.parametrize("window", [(-1, 0), (-2, 1), (-3, 2), (-4, 3), (-6, 5)])
def test_tl3_against_e0(window):
    f = np.linspace(3, 6, 301) + 1.234e-7
    (r,) = engine.solve(_tl3(window=window), f)
    ms = list(range(window[0], window[1] + 1))
    assert r.sectors == ms
    ref = E0.hb_sectors(np.pi * f / 1.5, 6 * np.pi, 3 * np.pi ** 2 * 0.05 / 1.5, ms, 50 / 65)
    ok = np.ones(len(f), bool)
    for m in ms:
        x = (f + 9 * m) / 1.5
        ok &= np.abs(x - np.round(x)) > 1e-3
    for m in ms:
        assert np.max(np.abs(r.S_sectors[m][ok, 0, 0] - ref[m][ok])) < 1e-12


def test_tl3_depth_is_e0_conversion():
    delta, info = engine.pump_depth(_tl3(), _tl3().pumped[0])
    # natural delta = 3 pi^2 rate / FSR; physical = natural * 2 FSR / Ztx
    assert np.isclose(delta, 3 * np.pi ** 2 * 0.05 / 1.5 * 2 * 1.5 / 65, rtol=1e-14)
    assert (info["n_ref"], info["m_ref"], info["family"]) == (3, 3, "amplification")


# E0's table (misc/msuper_E0_tl3_sectors.out): peak dB @ f over f in [3, 6]
E0_TABLE = {
    0.05: [(0.08, 5.256), (0.06, 5.266), (0.06, 5.266), (0.06, 5.266), (0.06, 5.266)],
    0.20: [(1.33, 5.256), (0.94, 5.266), (0.94, 5.266), (0.94, 5.266), (0.94, 5.266)],
    0.80: [(20.09, 5.245), (9.35, 5.279), (10.38, 5.263), (10.35, 5.264), (10.35, 5.264)],
    1.60: [(12.10, 4.500), (14.01, 5.659), (34.36, 5.251), (25.40, 5.263), (25.76, 5.259)],
}


@pytest.mark.parametrize("rate", sorted(E0_TABLE))
def test_tl3_e0_peak_table(rate):
    f = np.linspace(3.0, 6.0, 3001) + 1.234e-7
    for (lo, hi), (dB, fpk) in zip([(-1, 0), (-2, 1), (-3, 2), (-4, 3), (-6, 5)],
                                   E0_TABLE[rate]):
        (r,) = engine.solve(_tl3(rate, (lo, hi)), f)
        G = np.abs(r.S[:, 0, 0]) ** 2
        assert round(10 * np.log10(G.max()), 2) == dB
        assert round(f[G.argmax()], 3) == fpk


@pytest.mark.parametrize("name", PUMPED)
def test_pumped_against_independent_hb(name):
    doc = load(name)
    c = circuit(doc)
    delta_ref, pair = depth(c)
    delta, info = engine.pump_depth(doc, doc.pumped[0])
    assert (info["n_ref"], info["m_ref"]) == pair
    assert abs(delta / delta_ref - 1) < 1e-11
    (r0,) = engine.solve(doc)
    f = r0.f[::10] + 1.234e-7
    for window in ([-1, 0], [-3, 2]):
        doc.solve.sectors = [window[0], window[-1]]
        (r,) = engine.solve(doc, f)
        ref, ok = hb(c, f, list(range(window[0], window[-1] + 1)), delta_ref)
        assert ok.sum() > 0.8 * len(f)
        scale = max(1.0, np.max(np.abs(ref[0])))
        for m in ref:
            assert np.max(np.abs(r.S_sectors[m][ok, 0, 0] - ref[m][ok])) < 1e-10 * scale, m


@pytest.mark.parametrize("name", PUMPED)
def test_manley_rowe(name):
    """Lossless and stable: sum_m sgn(f_m) |S^ph_m0|^2 = 1 at every point."""
    doc = load(name)
    (r,) = engine.solve(doc)
    tot = sum(np.sign(r.f_sector(m)) * np.abs(r.photon(m)[:, 0, 0]) ** 2 for m in r.sectors)
    scale = max(np.max(np.abs(r.photon(m))) ** 2 for m in r.sectors)
    assert np.max(np.abs(tot - 1)) < 1e-12 * max(1.0, scale)


@pytest.mark.parametrize("name", PUMPED)
def test_auto_window_converges(name):
    doc = load(name)
    (r,) = engine.solve(doc)
    assert r.converged and r.history[-1][1] < doc.solve.sector_tol
    k = len(r.sectors) // 2
    assert r.sectors == list(range(-k, k))


def test_window_cap_warns_beyond_threshold():
    """TL_3 at rate 3.2 has no converged window within 16 sectors (E0)."""
    doc = _tl3(3.2)
    doc.solve.sector_max = 8
    (r,) = engine.solve(doc, np.linspace(3, 6, 301) + 1.234e-7)
    assert not r.converged and r.sectors == list(range(-4, 4))
    assert any("not converged" in i.msg for i in r.issues)


def test_explicit_window_without_zero_refused():
    doc = _tl3(window=(1, 2))
    with pytest.raises(ValueError, match="contain 0"):
        engine.solve(doc, [4.0])


def test_conversion_label():
    (r,) = engine.solve(_tl3(window=(-1, 0)), [4.0])
    assert r.label(0, 0, -1) == "TL:(-1,0)"


# ---------------------------------------------------------------------------
# D4: the depth is the stored quantity, the legacy rate follows it
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", PUMPED)
def test_migration_stores_the_depth(name):
    doc = load(name)
    p = doc.pumped[0]
    assert p.depth == engine.pump_depth(doc, p)[0]
    assert M.to_legacy(doc) == M.to_legacy(M.from_legacy(M.to_legacy(doc)))
    raw = M.to_legacy(doc)
    (line,) = [ln for ln in raw["line_resonators"] if ln.get("pump")]
    assert line["pump"]["rate"] == p.legacy_anchor["rate"]       # unedited: verbatim


def test_edit_keeps_the_depth_and_the_rate_follows(tmp_path):
    doc = load("LINE_PUMPED_LOADED.pgraph")
    p = doc.pumped[0]
    d0, r0 = p.depth, p.legacy_anchor["rate"]
    (s0,) = engine.solve(doc)
    doc.by_id("blocks")["line0"].params["FSR"] *= 1.01          # edit the line
    assert p.depth == d0
    (s1,) = engine.solve(doc)
    assert not np.allclose(s1.S, s0.S)
    raw = M.to_legacy(doc)
    (line,) = [ln for ln in raw["line_resonators"] if ln.get("pump")]
    assert line["pump"]["rate"] != r0
    back = M.from_legacy(raw)                                    # the GUI's save path
    assert abs(back.pumped[0].depth / d0 - 1) < 1e-14
    M.save(doc, tmp_path / "x.pgraph")
    assert M.load(tmp_path / "x.pgraph").pumped[0].depth == d0


def test_edited_depth_exports_its_rate():
    doc = load("TL_3_PUMPED_TERMINATION_AMPLIFIER.pgraph")
    p = doc.pumped[0]
    p.depth *= 2
    (line,) = [ln for ln in M.to_legacy(doc)["line_resonators"] if ln.get("pump")]
    assert abs(line["pump"]["rate"] / 0.1 - 1) < 1e-14


def test_hand_built_pump_without_depth_uses_the_anchor():
    doc = load("TL_3_PUMPED_TERMINATION_AMPLIFIER.pgraph")
    (r0,) = engine.solve(doc)
    doc.pumped[0].depth = None
    (r1,) = engine.solve(doc)
    assert np.array_equal(r0.S, r1.S)
    assert any("no stored depth" in i.msg for i in r1.issues)


# ---------------------------------------------------------------------------
# 3. representation (the M2a part)
# ---------------------------------------------------------------------------

def test_kept_poles_do_not_change_s():
    doc = load("LINE_PUMPED_LOADED.pgraph")
    (r0,) = engine.solve(doc)
    doc.solve.kept_poles["line0"] = {"f_max": 40.0}
    (r1,) = engine.solve(doc)
    assert r1.sectors == r0.sectors
    assert np.max(np.abs(r1.S - r0.S)) < 1e-13


# ---------------------------------------------------------------------------
# refusals and hygiene
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", sorted(TAPPED))
def test_tap_documents_solve_or_ask_for_z_d(name):
    rs = engine.solve(load(name))
    if TAPPED[name]:
        assert all(r.S is not None for r in rs)
    else:
        assert all(r.S is None for r in rs)
        assert any("LC mode impedance" in i.msg for r in rs for i in r.issues)


def test_no_qt_import():
    code = ("import sys; from graphulator import engine, model; "
            "d = model.load(sys.argv[1]); engine.solve(d); "
            "assert not [m for m in sys.modules if m.startswith(('PySide6', 'PyQt'))]")
    subprocess.run([sys.executable, "-c", code,
                    FILES["TL_3_PUMPED_TERMINATION_AMPLIFIER.pgraph"]], check=True, cwd=ROOT)
