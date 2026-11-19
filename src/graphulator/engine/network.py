"""Physical documents as an exact circuit network over frequency sectors
(step 4, milestone 2a; design note docs/design/step4_msuper_m2.md).

Scope (M2a): line blocks (uniform, stepped, uniform loss), L/C/R blocks,
port planes with Z0, element pumps (a modulated 1/L at a plane), one pump
tone, sector windows. Lumped modes on such documents (shared ports, taps)
are milestones 2b/2c and are refused here.

Convention: time dependence e^{-i omega t}, decaying poles in the lower half
plane (decision D7), omega = 2 pi f with f in the document's frequency unit.
Sector m runs at f_m = f + m f_p; a negative f_m is conjugate (idler)
content. A real element obeys Y(-omega) = conj Y(omega), so every block is
simply evaluated at f_m and needs no conjugation flag.

Unknowns per sector m (a modified nodal analysis whose rows are entire in
frequency, so a line pole, f = n FSR, or a sector landing on DC is not a
division by zero):
- V_p for every plane p (KCL row each);
- (I1, I2) for every line: the current into its x0 terminal and out of its
  xL terminal, with the two ABCD rows V1 = A V2 + B I2, I1 = C V2 + D I2
  (A..D are cos/sin of the complex electrical length: no poles);
- Phi_p, the node flux, for every plane carrying an inductor or a pump, with
  the row V_p + i omega_m Phi_p = 0. Inductors draw Phi/L and the pump draws
  (delta/2) e^{-+i phi} Phi_{m-+1}: 1/L(t) = 1/L0 + delta cos(omega_p t + phi).

KCL at a port plane adds V/Z0 and the Norton source 2 a / sqrt(Z0) (sector 0
only); the outgoing power wave is b = V / sqrt(Z0) - a [sector 0], V / sqrt(Z0)
[other sectors]. Elements meeting at a plane are in parallel (decision D1).

The pump's depth delta is the stored ``Pumped.depth`` (decision D4). A pump
without one (a document built by hand) is converted from its legacy
{rate, n_ref} anchor (model/pump_depth.py, gated in
tests/test_engine_network.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..model.pump_depth import anchor_depth
from ..model.schema import Document
from ..model.validate import Issue

M2A = ("step 4, milestone 2a: lines, L/C/R blocks, ports and element pumps")


class NotSupportedError(ValueError):
    """The document needs a milestone the engine does not have yet."""


# ---------------------------------------------------------------------------
# compiled network
# ---------------------------------------------------------------------------

@dataclass
class LineEl:
    id: str
    x0: Optional[int]                   # plane index, None = ground
    xL: Optional[int]
    FSR: float
    alpha: float                        # one-way attenuation alpha*ell [Np]
    sections: Tuple[Tuple[float, float], ...]   # (Z, frac) from x0 to xL


@dataclass
class LumpedEl:
    id: str
    kind: str                           # 'L', 'C', 'R'
    a: Optional[int]
    b: Optional[int]
    value: float                        # L: 1/L; C: C; R: 1/R  (omega = 2 pi f units)


@dataclass
class PumpEl:
    id: str
    plane: int
    delta: float                        # depth of 1/L(t)
    phase: float                        # rad
    f_p: float
    anchor: Dict[str, object] = field(default_factory=dict)


@dataclass
class PortEl:
    plane: int
    id: str
    label: str
    Z0: float


@dataclass
class Network:
    """One connected component of a physical document."""
    index: int
    planes: List[str]                   # plane ids, row order
    lines: List[LineEl]
    lumped: List[LumpedEl]
    pumps: List[PumpEl]
    ports: List[PortEl]
    flux: List[int]                     # planes with a flux unknown
    f_p: Optional[float]                # the pump tone (None: unpumped)
    issues: List[Issue] = field(default_factory=list)

    @property
    def n_sector(self) -> int:
        """Unknowns per sector."""
        return len(self.planes) + 2 * len(self.lines) + len(self.flux)


# ---------------------------------------------------------------------------
# reading the document
# ---------------------------------------------------------------------------

def _has_modes(doc: Document) -> bool:
    return bool(doc.modes) or bool(doc.attachments) or bool(doc.couplings) or any(
        p.kind == "coupling" for p in doc.pumped)


def classify(doc: Document) -> str:
    """'lumped' (milestone 1), 'network' (milestone 2a), or raise
    NotSupportedError naming the milestone the document needs."""
    physical = [b for b in doc.blocks
                if not (b.type == "R" and b.params.get("R") == "matched")]
    element_pumps = [p for p in doc.pumped if p.kind == "element"]
    if not physical and not element_pumps:
        return "lumped"
    if _has_modes(doc):
        taps = [a.id for a in doc.attachments if a.element is not None]
        if taps:
            raise NotSupportedError(
                "Lumped modes tapped onto lines (attachments " + ", ".join(taps)
                + ") come in step 4, milestone 2c (taps, after the D3 "
                "derivation); the engine has " + M2A + ".")
        raise NotSupportedError(
            "Lumped modes on a document with lines or blocks (the CMT block "
            "as a z-multiport on port planes) come in step 4, milestone 2b; "
            "the engine has " + M2A + ".")
    return "network"


def pump_depth(doc: Document, pumped) -> Tuple[float, Dict[str, object]]:
    """delta(1/L) of an element pump from its legacy {rate, n_ref} anchor
    (model.pump_depth.anchor_depth): (delta, info about the anchor pair)."""
    return anchor_depth(doc, pumped)


def _ref_impedance(doc: Document, b) -> float:
    """The impedance an L/C block's f_Z is quoted against (its line's Ztx)."""
    lid = b.extras.get("load_of")
    if lid is None:
        raise NotSupportedError(
            f"block {b.id} ({b.type}): f_Z without a line to refer it to "
            "(a document reference impedance, D3, is not in the schema yet)")
    return float(doc.by_id("blocks")[lid].params["Ztx"])


def compile_network(doc: Document) -> List[Network]:
    """A physical Document -> one Network per connected component with ports."""
    if classify(doc) != "network":
        raise NotSupportedError("not a physical document (use the milestone-1 path)")
    planes = [p.id for p in doc.planes]
    pidx = {p: i for i, p in enumerate(planes)}

    def node(pid):
        return None if pid is None else pidx[pid]

    nonzero = [t for t in doc.tones if t.f != 0]
    used = {p.tone for p in doc.pumped}
    if any(t.f == 0 for t in doc.tones if t.id in used):
        raise NotSupportedError("an element pump on a 0 Hz tone")
    if len({t.id for t in nonzero} & used) > 1:
        raise NotSupportedError("more than one pump tone (a 2-D sector window) "
                                "is not in milestone 2a")

    lines, lumped, pumps, issues = [], [], [], []
    for b in doc.blocks:
        if b.type == "line":
            p = b.params
            secs = p.get("sections")
            if secs:
                tot = sum(float(s["frac"]) for s in secs)
                sec = tuple((float(s["Z"]), float(s["frac"]) / tot) for s in secs)
            else:
                sec = ((float(p["Ztx"]), 1.0),)
            lines.append(LineEl(b.id, node(b.terminals.get("x0")), node(b.terminals.get("xL")),
                                float(p["FSR"]), float(p.get("alpha_uniform", 0.0)), sec))
        elif b.type in ("L", "C"):
            if "f_Z" not in b.params:
                raise NotSupportedError(f"block {b.id} ({b.type}): only f_Z is supported")
            Zr, fz = _ref_impedance(doc, b), float(b.params["f_Z"])
            # L = Zr / (2 pi f_Z), C = 1 / (2 pi f_Z Zr)
            val = 2 * np.pi * fz / Zr if b.type == "L" else 1.0 / (2 * np.pi * fz * Zr)
            lumped.append(LumpedEl(b.id, b.type, node(b.terminals.get("a")),
                                   node(b.terminals.get("b")), val))
        elif b.type == "R":
            R = b.params.get("R")
            if not isinstance(R, (int, float)):
                raise NotSupportedError(f"block {b.id}: R = {R!r} on a physical document")
            lumped.append(LumpedEl(b.id, "R", node(b.terminals.get("a")),
                                   node(b.terminals.get("b")), 1.0 / float(R)))
        else:
            raise NotSupportedError(f"block {b.id}: type {b.type!r}")

    tones = doc.by_id("tones")
    for p in doc.pumped:
        if p.kind != "element":
            continue
        if p.depth is not None:
            delta, info = float(p.depth), {}
        else:
            try:
                delta, info = anchor_depth(doc, p)
            except ValueError as e:
                raise NotSupportedError(str(e)) from e
            issues.append(Issue("info", p.id,
                                f"no stored depth: delta(1/L) = {delta:.12g} from the "
                                f"legacy anchor (rate {p.legacy_anchor.get('rate')} at "
                                f"pair ({info['n_ref']}, {info['m_ref']}), {info['family']})"))
        if p.param != "1/L":
            raise NotSupportedError(f"pump {p.id}: only a modulated 1/L is supported")
        pumps.append(PumpEl(p.id, pidx[p.plane], delta, np.deg2rad(p.phase or 0.0),
                            tones[p.tone].f, info))

    ports = []
    for pl in doc.planes:
        if pl.kind == "port":
            if pl.Z0 is None:
                raise NotSupportedError(f"port {pl.id} has no Z0")
            ports.append(PortEl(pidx[pl.id], pl.id, pl.label, float(pl.Z0)))

    # components: planes joined by blocks (ground is not a node)
    parent = list(range(len(planes)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def join(a, b):
        if a is not None and b is not None:
            parent[find(a)] = find(b)

    for ln in lines:
        join(ln.x0, ln.xL)
    for el in lumped:
        join(el.a, el.b)
    groups: Dict[int, List[int]] = {}
    for i in range(len(planes)):
        groups.setdefault(find(i), []).append(i)

    out = []
    for g in groups.values():
        gs = set(g)
        gports = [p for p in ports if p.plane in gs]
        if not gports:
            continue
        loc = {old: new for new, old in enumerate(g)}

        def lo(x):
            return None if x is None else loc[x]

        glines = [LineEl(ln.id, lo(ln.x0), lo(ln.xL), ln.FSR, ln.alpha, ln.sections)
                  for ln in lines if (ln.x0 in gs or ln.xL in gs)]
        glump = [LumpedEl(el.id, el.kind, lo(el.a), lo(el.b), el.value)
                 for el in lumped if (el.a in gs or el.b in gs)]
        gpumps = [PumpEl(pu.id, loc[pu.plane], pu.delta, pu.phase, pu.f_p, pu.anchor)
                  for pu in pumps if pu.plane in gs]
        flux = sorted({x for el in glump if el.kind == "L" for x in (el.a, el.b)
                       if x is not None} | {pu.plane for pu in gpumps})
        out.append(Network(
            index=len(out), planes=[planes[i] for i in g], lines=glines, lumped=glump,
            pumps=gpumps, ports=[PortEl(loc[p.plane], p.id, p.label, p.Z0) for p in gports],
            flux=flux, f_p=(gpumps[0].f_p if gpumps else None),
            issues=[i for i in issues if any(i.path == pu.id for pu in gpumps)]))
    out.sort(key=lambda n: min(planes.index(n.planes[p.plane]) for p in n.ports))
    for i, n in enumerate(out):
        n.index = i
    return out


# ---------------------------------------------------------------------------
# assembly and solve
# ---------------------------------------------------------------------------

def line_abcd(ln: LineEl, f: np.ndarray):
    """ABCD of the line from x0 to xL at linear frequency f (array):
    the cascade of [[cos t, -i Z sin t], [-i sin t / Z, cos t]] over the
    sections, t = (pi f / FSR + i alpha) frac (e^{-i omega t} convention:
    the loss puts the poles at n FSR - i alpha FSR / pi)."""
    theta = np.pi * np.asarray(f, dtype=float) / ln.FSR + 1j * ln.alpha
    A = np.ones_like(theta)
    B = np.zeros_like(theta)
    C = np.zeros_like(theta)
    D = np.ones_like(theta)
    for Z, frac in ln.sections:
        t = theta * frac
        c, s = np.cos(t), np.sin(t)
        a, b, cc, d = c, -1j * Z * s, -1j * s / Z, c
        A, B, C, D = A * a + B * cc, A * b + B * d, C * a + D * cc, C * b + D * d
    return A, B, C, D


def _assemble(net: Network, f: np.ndarray, sectors: Sequence[int]):
    """(A, rhs): A (n_f, n, n), rhs (n_f, n, P) for one block of frequencies."""
    nf = len(f)
    np_ = len(net.planes)
    nl = len(net.lines)
    fidx = {p: i for i, p in enumerate(net.flux)}
    n1 = net.n_sector
    K = len(sectors)
    n = K * n1
    P = len(net.ports)
    A = np.zeros((nf, n, n), dtype=complex)
    rhs = np.zeros((nf, n, P), dtype=complex)
    sidx = {m: s for s, m in enumerate(sectors)}
    f_p = net.f_p or 0.0

    for s, m in enumerate(sectors):
        o = s * n1
        V = lambda p: o + p                                   # noqa: E731
        I1 = lambda k: o + np_ + 2 * k                         # noqa: E731
        I2 = lambda k: o + np_ + 2 * k + 1                     # noqa: E731
        PH = lambda p: o + np_ + 2 * nl + fidx[p]              # noqa: E731
        fm = f + m * f_p
        wm = 2 * np.pi * fm
        # ports
        for q, pt in enumerate(net.ports):
            A[:, V(pt.plane), V(pt.plane)] += 1.0 / pt.Z0
            if m == 0:
                rhs[:, V(pt.plane), q] = 2.0 / np.sqrt(pt.Z0)
        # lines
        for k, ln in enumerate(net.lines):
            a_, b_, c_, d_ = line_abcd(ln, fm)
            if ln.x0 is not None:
                A[:, V(ln.x0), I1(k)] += 1.0
            if ln.xL is not None:
                A[:, V(ln.xL), I2(k)] -= 1.0
            r1, r2 = I1(k), I2(k)            # constitutive rows reuse the current indices
            if ln.x0 is not None:
                A[:, r1, V(ln.x0)] += 1.0
            if ln.xL is not None:
                A[:, r1, V(ln.xL)] -= a_
            A[:, r1, I2(k)] -= b_
            A[:, r2, I1(k)] += 1.0
            if ln.xL is not None:
                A[:, r2, V(ln.xL)] -= c_
            A[:, r2, I2(k)] -= d_
        # lumped
        for el in net.lumped:
            ends = [(el.a, 1.0), (el.b, -1.0)]
            for x, sx in ends:
                if x is None:
                    continue
                for y, sy in ends:
                    if y is None:
                        continue
                    if el.kind == "L":
                        A[:, V(x), PH(y)] += sx * sy * el.value
                    elif el.kind == "C":
                        A[:, V(x), V(y)] += sx * sy * (-1j * wm * el.value)
                    else:
                        A[:, V(x), V(y)] += sx * sy * el.value
        # flux rows: V + i omega Phi = 0
        for p in net.flux:
            A[:, PH(p), V(p)] = 1.0
            A[:, PH(p), PH(p)] = 1j * wm
        # pumps: I_m += (delta/2) e^{-i phi} Phi_{m-1} + (delta/2) e^{+i phi} Phi_{m+1}
        for pu in net.pumps:
            for dm, ph in ((-1, np.exp(-1j * pu.phase)), (+1, np.exp(1j * pu.phase))):
                if m + dm in sidx:
                    oc = sidx[m + dm] * n1
                    A[:, V(pu.plane), oc + np_ + 2 * nl + fidx[pu.plane]] += 0.5 * pu.delta * ph
    return A, rhs


def _blocks(nf, n):
    step = max(1, int(2 ** 22 // max(n ** 2, 1)))
    return [(a, min(a + step, nf)) for a in range(0, nf, step)]


def solve_window(net: Network, f, sectors: Sequence[int]):
    """S over one window: dict m -> (n_f, P, P), out at (p, m), in at (q, 0),
    power waves normalized to each port's Z0. NaN where the circuit itself
    is singular (e.g. a lossless DC zero mode hit exactly)."""
    f = np.asarray(f, dtype=float)
    sectors = list(sectors)
    if 0 not in sectors:
        raise ValueError("the sector window must contain 0")
    n1 = net.n_sector
    P = len(net.ports)
    out = {m: np.empty((len(f), P, P), dtype=complex) for m in sectors}
    singular = 0
    for lo, hi in _blocks(len(f), len(sectors) * n1):
        A, rhs = _assemble(net, f[lo:hi], sectors)
        try:
            X = np.linalg.solve(A, rhs)
        except np.linalg.LinAlgError:
            X = np.empty_like(rhs)
            for i in range(hi - lo):
                try:
                    X[i] = np.linalg.solve(A[i], rhs[i])
                except np.linalg.LinAlgError:
                    X[i] = np.nan
                    singular += 1
        for s, m in enumerate(sectors):
            for p, pt in enumerate(net.ports):
                b = X[:, s * n1 + pt.plane, :] / np.sqrt(pt.Z0)
                if m == 0:
                    b[:, p] -= 1.0
                out[m][lo:hi, p, :] = b
    return out, singular


def window_metric(S_new, S_old) -> float:
    """max_f max_{m,p,q} |dS| over the old window's sectors, divided by
    max(max_f max_p ||S_pp^(0)|^2 - 1|, 1e-2): relative to the excess gain
    for an amplifier, absolute for conversion (design note D5, open detail)."""
    num = max(float(np.nanmax(np.abs(S_new[m] - S_old[m]))) for m in S_old)
    S0 = S_new[0]
    diag = np.abs(np.diagonal(S0, axis1=1, axis2=2)) ** 2
    den = max(float(np.nanmax(np.abs(diag - 1.0))), 1e-2)
    return num / den


def auto_windows(sector_max: int):
    """{-1..0}, {-2..1}, ...: mirror-symmetric (m <-> -1-m), up to sector_max sectors."""
    k = 1
    while 2 * k <= max(sector_max, 2):
        yield list(range(-k, k))
        k += 1


@dataclass
class NetworkResult:
    """S of one component over the sweep.

    S: the sector-0 block (n_f, P, P), comparable with legacy and milestone 1.
    S_sectors: m -> (n_f, P, P), out at (port p, sector m), in at (q, 0).
    """
    index: int
    S: np.ndarray
    S_sectors: Dict[int, np.ndarray]
    sectors: List[int]
    f: np.ndarray
    f_p: Optional[float]
    ports: List[str]
    port_labels: List[str]
    network: Network
    converged: bool = True
    history: List[Tuple[List[int], float]] = field(default_factory=list)
    issues: List[Issue] = field(default_factory=list)

    def f_sector(self, m: int) -> np.ndarray:
        return self.f + m * (self.f_p or 0.0)

    def photon(self, m: int) -> np.ndarray:
        """S in photon-flux normalization, S sqrt(|f| / |f_m|): what
        Manley-Rowe conserves (sum_{p,m} sgn(f_m) |S^ph|^2 = 1, lossless)."""
        with np.errstate(divide="ignore", invalid="ignore"):
            r = np.sqrt(np.abs(self.f) / np.abs(self.f_sector(m)))
        return self.S_sectors[m] * r[:, None, None]

    def label(self, p: int, q: int, m: int = 0) -> str:
        """Trace label in S_jk order (k scatters into j), decision D6:
        'P1:0', 'P1:(-1,0)', '(P1,P2):0', '(P1,P2):(-1,0)'."""
        a, b = self.port_labels[p], self.port_labels[q]
        who = a if p == q else f"({a},{b})"
        return f"{who}:0" if m == 0 else f"{who}:({m},0)"


def solve_network(doc: Document, f=None) -> List[NetworkResult]:
    """S per component of a physical document over the grid f (default: the
    document's sweep), in the window doc.solve.sectors."""
    if f is None:
        from ..model.legacy_job import sweep_grid
        f = sweep_grid(doc)
    f = np.asarray(f, dtype=float)
    st = doc.solve
    out = []
    for net in compile_network(doc):
        issues = list(net.issues)
        history = []
        converged = True
        if not net.pumps:
            window = [0]
            S, sing = solve_window(net, f, window)
        elif st.sectors != "auto":
            lo, hi = int(st.sectors[0]), int(st.sectors[1])
            window = list(range(lo, hi + 1))
            S, sing = solve_window(net, f, window)
        else:
            S_old, peaks = None, []
            for window in auto_windows(int(st.sector_max)):
                S, sing = solve_window(net, f, window)
                peaks.append(float(np.nanmax(np.abs(S[0]))))
                if S_old is not None:
                    d = window_metric(S, S_old)
                    history.append((list(window), d))
                    if d < st.sector_tol:
                        break
                S_old = S
            converged = bool(history) and history[-1][1] < st.sector_tol
            if not converged and history:
                grow = len(peaks) >= 3 and all(b > a for a, b in zip(peaks[-3:], peaks[-2:]))
                issues.append(Issue(
                    "warning", f"component{net.index}",
                    f"sector window not converged at {len(window)} sectors "
                    f"(last change {history[-1][1]:.2e} > tol {st.sector_tol:g})"
                    + ("; |S| keeps growing with the window: possibly beyond "
                       "threshold" if grow else "")))
        if sing:
            issues.append(Issue("warning", f"component{net.index}",
                                f"{sing} frequency points are singular (a lossless "
                                "pole hit exactly); S is NaN there"))
        out.append(NetworkResult(
            index=net.index, S=S[0], S_sectors=S, sectors=list(window), f=f,
            f_p=net.f_p, ports=[p.id for p in net.ports],
            port_labels=[p.label for p in net.ports], network=net,
            converged=converged, history=history, issues=issues))
    return out
