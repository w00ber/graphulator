"""Physical documents as an exact circuit network over frequency sectors
(step 4, milestones 2a and 2b; design note docs/design/step4_msuper_m2.md).

Scope:
- M2a: line blocks (uniform, stepped, uniform loss), L/C/R blocks, port
  planes with Z0, element pumps (a modulated 1/L at a plane), one pump
  tone, sector windows.
- M2b: the lumped modes as one CMT block per component, an impedance-type
  multiport on the planes they attach to (decision D2); line poles promoted
  to mode rows (kept poles), with S invariant.
- M2c: capacitive taps as circuit elements: the coupling capacitor C_c is
  a C block in Sigma_0 and the tank attaches to its own node in the
  impedance (Foster I) form, gamma = 1/(2 pi Z_ref C_d) (model/taps.py).
  Each lumped mode carries its -f image pole by default on physical
  documents (solve.images; CMTBlock.M_rows), which makes a tank exact.
- Refused: inductive taps, and lumped modes together with element pumps
  (later: their sector images are the physical workflow's generate step).

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

CMT block (D2, D3). The modes of one milestone-1 component, seen from the
planes they attach to, are the multiport z = (i/2) K^dag M_iso^{-1} K in
units of the document reference impedance Z_ref (``units.z_ref``, default
50 ohm): every attachment rate is a leak rate into Z_ref. It is solved
bordered, never inverting M_iso: with j_p = sqrt(Z_ref) I_p (the current
into the block at plane p),

    M_iso a - K j = 0,        V_p / sqrt(Z_ref) - (i/2) (K^dag a)_p = 0,

and I_p joins the plane's KCL like any other element (D1). A lumped
document is then the reflection of its own z on Z_ref terminations; that is
an identity (Woodbury), gated against milestone 1 on every lumped file. A
port without Z0 is terminated in Z_ref, a matched R is Z_ref.

Kept poles. A line pole n promoted to a mode row splits the line's
open-circuit impedance exactly, Z = Z_rem + sum_n R_n / (f - p_n) with
p_n = f_n - i B_n / 2 and R_n = (i / (4 pi C_n)) u_n u_n^T (twice that for
the DC pole, which has no -f partner); u_n are the mode's end amplitudes and
C_n its mass (autograph.LineResonator; a load block of the line is absorbed
into it, so the poles are the loaded ones). The line's two ABCD rows become

    V - sum_n R_n a_n - Z_rem I_in = 0,     (f - p_n) a_n - u_n . I_in = 0,

with Z_rem = Z - sum_n R_n / (f - p_n), evaluated as the mean over a small
circle around f (Z_rem is analytic there, so the mean is exact and avoids
the cancellation). That form is used only near a kept pole: Z_rem still has
the poles that are not kept (the -f_n partners above all), and next to them
impedance rows lose digits. Elsewhere the line keeps its pole-free ABCD rows,
written on its own voltage V_l = V - sum_n R_n a_n + sum_n R_n I_in / (f - p_n),
which is regular away from the kept poles. The two forms are the same
equations. S does not depend on which poles are kept (gate 3); the rows are
the representation the M_super tab and, later, mode-level couplings need.
They are built only when asked for (``promote=True``).
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..model.pump_depth import anchor_depth
from ..model.schema import Document
from ..model.taps import TapError, freq_scale, resolve_taps
from ..model.validate import Issue
from .kernel import diagonal, f_axis, k_matrices, static_part
from .msuper import MSuper, compile_document

M2B = ("step 4, milestone 2b: lines, L/C/R blocks, ports, element pumps, and "
       "lumped modes attached directly to planes")


class NotSupportedError(ValueError):
    """The document needs a milestone the engine does not have yet."""


# ---------------------------------------------------------------------------
# compiled network
# ---------------------------------------------------------------------------

@dataclass
class KeptPole:
    """One promoted line pole: a mode row (f - p) a = u . I_in."""
    n: int
    f0: float
    B: float
    u: Tuple[float, float]              # amplitude at (x0, xL), 1 at the open end
    C: float                            # mode mass C_n (C_line for DC)

    @property
    def p(self) -> complex:
        return self.f0 - 0.5j * self.B

    @property
    def c(self) -> complex:
        """Residue scale: R = c u u^T (i/(4 pi C), doubled for DC)."""
        return 1j * (2.0 if self.n == 0 else 1.0) / (4 * np.pi * self.C)

    def residue(self) -> np.ndarray:
        u = np.asarray(self.u)
        return self.c * np.outer(u, u)


@dataclass
class LineEl:
    id: str
    x0: Optional[int]                   # plane index, None = ground
    xL: Optional[int]
    FSR: float
    alpha: float                        # one-way attenuation alpha*ell [Np]
    sections: Tuple[Tuple[float, float], ...]   # (Z, frac) from x0 to xL
    load: Optional[Tuple[str, float]] = None    # absorbed shunt L: (end, 1/L)
    poles: List[KeptPole] = field(default_factory=list)


@dataclass
class CMTBlock:
    """The lumped modes of one milestone-1 component, as a multiport on the
    planes of its channels (one column of K per plane)."""
    ms: MSuper
    planes: List[int]
    K: np.ndarray                       # (N, P) complex
    Zr: float
    images: bool = False                # add each mode's -f partner (reality completion)

    @property
    def n(self) -> int:
        """Rows of the block: N, or 2N with the image rows."""
        return len(self.ms.rows) * (2 if self.images else 1)

    @property
    def K_rows(self) -> np.ndarray:
        """K over the block's rows: [K; conj K] with the images."""
        return np.vstack([self.K, np.conj(self.K)]) if self.images else self.K

    def M_rows(self, f) -> np.ndarray:
        """(n_f, n, n): M_iso, and with the images blockdiag(M_iso, 2f - conj M_iso).

        The image block is f + conj(H) for M_iso = f - H: its z is
        conj(z_main(-f)), so z(-f) = conj z(f) holds for the sum (a real
        network). For one mode it is the exact Foster pair of a parallel
        tank, (i/2) gamma [1/(f - f0) + 1/(f + f0)]. Drawn mode-mode edges
        get their conjugates among the images and no counter-rotating
        cross terms (those are the RWA checker's level 2)."""
        M = self.M_iso(f)
        if not self.images:
            return M
        N = M.shape[1]
        fa = np.asarray(f, dtype=float).reshape(-1)
        out = np.zeros((M.shape[0], 2 * N, 2 * N), dtype=complex)
        out[:, :N, :N] = M
        img = -np.conj(M)
        idx = np.arange(N)
        img[:, idx, idx] += 2 * fa[:, None]
        out[:, N:, N:] = img
        return out

    def M_iso(self, f) -> np.ndarray:
        """(n_f, N, N): M without the port loading (i/2) K K^dag."""
        n = len(self.ms.rows)
        static = static_part(self.ms, np.zeros((n, 0), dtype=complex))
        diag = diagonal(self.ms, f_axis(self.ms, np.asarray(f, dtype=float)))
        out = np.empty((len(diag), n, n), dtype=complex)
        out[...] = static
        idx = np.arange(n)
        out[:, idx, idx] += diag
        return out


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
    cmt: List[CMTBlock] = field(default_factory=list)
    complete: bool = True               # False: a CMT block lacks parameters
    issues: List[Issue] = field(default_factory=list)

    def layout(self) -> Dict[str, object]:
        """Offsets of each unknown group inside one sector."""
        o = len(self.planes)
        lines = o
        o += 2 * len(self.lines)
        flux = o
        o += len(self.flux)
        poles = []
        for ln in self.lines:
            poles.append(o)
            o += len(ln.poles)
        cmt = []
        for b in self.cmt:
            cmt.append((o, o + b.n))                  # (a rows, block currents)
            o += b.n + len(b.planes)
        return {"lines": lines, "flux": flux, "poles": poles, "cmt": cmt, "n": o}

    @property
    def n_sector(self) -> int:
        """Unknowns per sector."""
        return self.layout()["n"]


# ---------------------------------------------------------------------------
# reading the document
# ---------------------------------------------------------------------------

def _has_modes(doc: Document) -> bool:
    return bool(doc.modes) or bool(doc.attachments) or bool(doc.couplings) or any(
        p.kind == "coupling" for p in doc.pumped)


def classify(doc: Document) -> str:
    """'lumped' (milestone 1: engine.solve keeps it bit for bit with legacy)
    or 'network' (milestone 2); raises NotSupportedError naming the
    milestone a document needs."""
    physical = [b for b in doc.blocks
                if not (b.type == "R" and b.params.get("R") == "matched")]
    element_pumps = [p for p in doc.pumped if p.kind == "element"]
    if not physical and not element_pumps:
        return "lumped"
    if _has_modes(doc):
        inductive = [a.id for a in doc.attachments if a.element not in (None, "C")]
        if inductive:
            raise NotSupportedError(
                "Inductive taps (attachments " + ", ".join(inductive) + ") are not in "
                "milestone 2c: their exact form is derived but not checked numerically.")
        if element_pumps:
            raise NotSupportedError(
                "Lumped modes together with element pumps come after milestone 2 "
                "(their sector images are the physical workflow's generate "
                "step); the engine has " + M2B + ".")
    return "network"


def z_ref(doc: Document) -> float:
    """The document reference impedance (decision D3; units.z_ref, default 50)."""
    return float(doc.units.get("z_ref", 50.0))


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


def _line_poles(doc: Document, blk, spec, absorbed) -> List[KeptPole]:
    """The kept poles of a line (with its absorbed load), from
    solve.kept_poles: {'f_max': F} keeps DC (when the line has one) and every
    pole with 0 < f_n <= F; a list keeps those indices (0 = DC)."""
    from ..model.pump_depth import _line_resonator
    p = blk.params
    if absorbed is not None and float(p.get("alpha_uniform", 0.0)) != 0.0:
        raise NotSupportedError(
            f"line {blk.id}: kept poles of a lossy loaded line (its poles are "
            "not at f_n - i B/2 exactly)")
    res = _line_resonator(doc, blk)
    if absorbed is None:
        res.load = None
    alpha = float(p.get("alpha_uniform", 0.0))
    B = 2.0 * alpha * res.FSR / np.pi
    if isinstance(spec, dict):
        F = float(spec.get("f_max", 0.0))
        ns = [] if res._skip_dc else [0]
        n = 1
        while res.mode_freq(n) <= F:
            ns.append(n)
            n += 1
    else:
        ns = sorted(int(x) for x in spec)
    out = []
    for n in ns:
        if n == 0:
            if res._skip_dc:
                raise NotSupportedError(f"line {blk.id}: an inductive load leaves no DC pole")
            out.append(KeptPole(0, 0.0, B, (1.0, 1.0), res.C_line))
        else:
            out.append(KeptPole(n, res.mode_freq(n), B,
                                (res.mode_profile(n, "x0"), res.mode_profile(n, "xL")),
                                res.mode_mass(n)))
    return out


def _cmt_blocks(doc: Document, physical: bool) -> List[MSuper]:
    """The milestone-1 components of the document's lumped part."""
    if not _has_modes(doc):
        return []
    sub = copy.deepcopy(doc)
    sub.blocks = [b for b in sub.blocks if b.type == "R" and b.params.get("R") == "matched"]
    sub.pumped = [p for p in sub.pumped if p.kind == "coupling"]
    mss = compile_document(sub)
    if physical:
        for ms in mss:
            off = [r.mode for r in ms.rows if r.conj or (r.nu not in (None, 0.0))]
            if off or ms.root_conj:
                raise NotSupportedError(
                    "lumped modes outside sector 0 (conjugated, or pumped away from "
                    f"the root: {', '.join(off) or ms.root}) on a document with "
                    "lines or blocks come after milestone 2; the engine has " + M2B + ".")
    return mss


def compile_network(doc: Document, promote: bool = False) -> List[Network]:
    """A Document -> one Network per connected component with ports.

    Physical documents are what engine.solve sends here; lumped ones are
    accepted too (the M2 path for gate 4). promote=True builds the kept
    poles of solve.kept_poles as mode rows."""
    physical = classify(doc) == "network"
    try:
        doc, tap_issues, tap_incomplete = resolve_taps(doc)
    except TapError as e:
        raise NotSupportedError(str(e)) from e
    images = physical if doc.solve.images is None else bool(doc.solve.images)
    planes = [p.id for p in doc.planes]
    pidx = {p: i for i, p in enumerate(planes)}
    Zr = z_ref(doc)

    def node(pid):
        return None if pid is None else pidx[pid]

    nonzero = [t for t in doc.tones if t.f != 0]
    used = {p.tone for p in doc.pumped if p.kind == "element"}
    if any(t.f == 0 for t in doc.tones if t.id in used):
        raise NotSupportedError("an element pump on a 0 Hz tone")
    if len({t.id for t in nonzero} & used) > 1:
        raise NotSupportedError("more than one pump tone (a 2-D sector window) "
                                "is not in milestone 2")

    loads = {b.extras.get("load_of"): b for b in doc.blocks
             if b.type == "L" and "load_of" in b.extras}
    lines, lumped, pumps, issues = [], [], [], []
    absorbed_ids = set()
    for b in doc.blocks:
        if b.type == "line":
            p = b.params
            secs = p.get("sections")
            if secs:
                tot = sum(float(s["frac"]) for s in secs)
                sec = tuple((float(s["Z"]), float(s["frac"]) / tot) for s in secs)
            else:
                sec = ((float(p["Ztx"]), 1.0),)
            ln = LineEl(b.id, node(b.terminals.get("x0")), node(b.terminals.get("xL")),
                        float(p["FSR"]), float(p.get("alpha_uniform", 0.0)), sec)
            spec = doc.solve.kept_poles.get(b.id)
            if promote and spec:
                ld = loads.get(b.id)
                absorbed = None
                if ld is not None and ld.terminals.get("b") is None:
                    end = next(e for e in ("x0", "xL")
                               if b.terminals.get(e) == ld.terminals.get("a"))
                    absorbed = (end, 2 * np.pi * float(ld.params["f_Z"]) / float(p["Ztx"]))
                    absorbed_ids.add(ld.id)
                ln.load = absorbed
                ln.poles = _line_poles(doc, b, spec, absorbed)
            lines.append(ln)
    for b in doc.blocks:
        if b.type == "line" or b.id in absorbed_ids:
            continue
        if b.type in ("L", "C"):
            if b.type in b.params:
                # an element value in henries / farads -> document units
                # (omega = 2 pi f with f in the document's unit; L stored as 1/L)
                x = float(b.params[b.type]) * freq_scale(doc)
                val = 1.0 / x if b.type == "L" else x
            elif "f_Z" in b.params:
                Zb, fz = _ref_impedance(doc, b), float(b.params["f_Z"])
                # L = Zb / (2 pi f_Z), C = 1 / (2 pi f_Z Zb)
                val = 2 * np.pi * fz / Zb if b.type == "L" else 1.0 / (2 * np.pi * fz * Zb)
            else:
                raise NotSupportedError(f"block {b.id} ({b.type}): needs {b.type} or f_Z")
            lumped.append(LumpedEl(b.id, b.type, node(b.terminals.get("a")),
                                   node(b.terminals.get("b")), val))
        elif b.type == "R":
            R = b.params.get("R")
            if R == "matched":
                R = Zr
            if not isinstance(R, (int, float)):
                raise NotSupportedError(f"block {b.id}: R = {R!r}")
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

    cmts = []
    for ms in _cmt_blocks(doc, physical):
        if not ms.channels:
            continue
        _, K_full = k_matrices(ms)
        chans = [c for c in ms.channels if c.monitored] + [c for c in ms.channels
                                                            if not c.monitored]
        cmts.append(CMTBlock(ms, [pidx[c.plane] for c in chans], K_full, Zr, images))

    ports = [PortEl(pidx[pl.id], pl.id, pl.label, float(pl.Z0) if pl.Z0 is not None else Zr)
             for pl in doc.planes if pl.kind == "port"]

    # components: planes joined by blocks and CMT blocks (ground is not a node)
    parent = list(range(len(planes)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def join(a, b):
        if a is not None and b is not None:
            parent[find(a)] = find(b)

    used_planes = set()
    for ln in lines:
        join(ln.x0, ln.xL)
        used_planes |= {ln.x0, ln.xL}
    for el in lumped:
        join(el.a, el.b)
        used_planes |= {el.a, el.b}
    for cb in cmts:
        for q in cb.planes[1:]:
            join(cb.planes[0], q)
        used_planes |= set(cb.planes)
    groups: Dict[int, List[int]] = {}
    for i in range(len(planes)):
        groups.setdefault(find(i), []).append(i)

    out = []
    for g in groups.values():
        gs = set(g)
        gports = [p for p in ports if p.plane in gs]
        if not gports or not (gs & used_planes):
            continue
        loc = {old: new for new, old in enumerate(g)}

        def lo(x):
            return None if x is None else loc[x]

        glines = [LineEl(ln.id, lo(ln.x0), lo(ln.xL), ln.FSR, ln.alpha, ln.sections,
                         ln.load, ln.poles)
                  for ln in lines if (ln.x0 in gs or ln.xL in gs)]
        glump = [LumpedEl(el.id, el.kind, lo(el.a), lo(el.b), el.value)
                 for el in lumped if (el.a in gs or el.b in gs)]
        gpumps = [PumpEl(pu.id, loc[pu.plane], pu.delta, pu.phase, pu.f_p, pu.anchor)
                  for pu in pumps if pu.plane in gs]
        gcmt = [CMTBlock(cb.ms, [loc[q] for q in cb.planes], cb.K, cb.Zr, cb.images)
                for cb in cmts if cb.planes[0] in gs]
        flux = sorted({x for el in glump if el.kind == "L" for x in (el.a, el.b)
                       if x is not None} | {pu.plane for pu in gpumps})
        gissues = [i for i in issues if any(i.path == pu.id for pu in gpumps)]
        gmodes = {r.mode for cb in gcmt for r in cb.ms.rows}
        gissues += [i for i in tap_issues
                    if i.path.split("/", 1)[-1] in gmodes or i.path.split("/", 1)[-1] in tap_incomplete]
        for cb in gcmt:
            gissues += cb.ms.issues
        out.append(Network(
            index=len(out), planes=[planes[i] for i in g], lines=glines, lumped=glump,
            pumps=gpumps, ports=[PortEl(loc[p.plane], p.id, p.label, p.Z0) for p in gports],
            flux=flux, f_p=(gpumps[0].f_p if gpumps else None), cmt=gcmt,
            complete=all(cb.ms.complete for cb in gcmt) and not tap_incomplete,
            issues=gissues))
    out.sort(key=lambda n: min(planes.index(n.planes[p.plane]) for p in n.ports))
    for i, n in enumerate(out):
        n.index = i
    return out


# ---------------------------------------------------------------------------
# assembly and solve
# ---------------------------------------------------------------------------

def line_abcd(ln: LineEl, f: np.ndarray):
    """ABCD of the line from x0 to xL at (real or complex) linear frequency f:
    the cascade of [[cos t, -i Z sin t], [-i sin t / Z, cos t]] over the
    sections, t = (pi f / FSR + i alpha) frac (e^{-i omega t} convention:
    the loss puts the poles at n FSR - i alpha FSR / pi). An absorbed load
    (kept poles only) is a shunt [[1, 0], [Y_L, 1]] at its end."""
    f = np.asarray(f)
    theta = np.pi * f / ln.FSR + 1j * ln.alpha
    A = np.ones_like(theta, dtype=complex)
    B = np.zeros_like(theta, dtype=complex)
    C = np.zeros_like(theta, dtype=complex)
    D = np.ones_like(theta, dtype=complex)
    for Z, frac in ln.sections:
        t = theta * frac
        c, s = np.cos(t), np.sin(t)
        a, b, cc, d = c, -1j * Z * s, -1j * s / Z, c
        A, B, C, D = A * a + B * cc, A * b + B * d, C * a + D * cc, C * b + D * d
    if ln.load is not None:
        end, invL = ln.load
        Y = 1j * invL / (2 * np.pi * f)             # 1 / (-i omega L)
        if end == "x0":
            A, B, C, D = A, B, C + Y * A, D + Y * B
        else:
            A, B, C, D = A + B * Y, B, C + D * Y, D
    return A, B, C, D


def line_z(ln: LineEl, f) -> np.ndarray:
    """Open-circuit impedance matrix (n_f, 2, 2), currents into both
    terminals: Z = (1/C) [[A, 1], [1, D]]."""
    A, _, C, D = line_abcd(ln, f)
    Z = np.empty(np.shape(A) + (2, 2), dtype=complex)
    Z[..., 0, 0] = A / C
    Z[..., 0, 1] = Z[..., 1, 0] = 1.0 / C
    Z[..., 1, 1] = D / C
    return Z


#: the circle (in units of FSR) on which Z_rem is averaged near a kept pole
POLE_RADIUS = 0.02
POLE_POINTS = 16


def z_rem(ln: LineEl, f) -> np.ndarray:
    """Z minus the kept poles, (n_f, 2, 2). Within POLE_RADIUS FSR / 2 of a
    kept pole it is the mean over a circle of radius POLE_RADIUS FSR around
    f: exact for a function analytic in the disc (the trapezoid rule on a
    circle converges geometrically), and far enough from the pole that the
    subtraction keeps its digits."""
    f = np.asarray(f, dtype=float)

    def direct(z):
        Zm = line_z(ln, z)
        for kp in ln.poles:
            Zm = Zm - kp.residue() / (z - kp.p)[..., None, None]
        return Zm

    if not ln.poles:
        return line_z(ln, f)
    r = POLE_RADIUS * ln.FSR
    near = np.zeros(len(f), bool)
    for kp in ln.poles:
        near |= np.abs(f - kp.p) < r / 2
    out = np.empty((len(f), 2, 2), dtype=complex)
    if np.any(~near):
        out[~near] = direct(f[~near])
    if np.any(near):
        ring = r * np.exp(2j * np.pi * np.arange(POLE_POINTS) / POLE_POINTS)
        pts = f[near][:, None] + ring[None, :]
        out[near] = direct(pts).mean(axis=1)
    return out


def _assemble(net: Network, f: np.ndarray, sectors: Sequence[int]):
    """(A, rhs): A (n_f, n, n), rhs (n_f, n, P) for one block of frequencies."""
    nf = len(f)
    lay = net.layout()
    fidx = {p: i for i, p in enumerate(net.flux)}
    n1 = lay["n"]
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
        I1 = lambda k: o + lay["lines"] + 2 * k                # noqa: E731
        I2 = lambda k: o + lay["lines"] + 2 * k + 1            # noqa: E731
        PH = lambda p: o + lay["flux"] + fidx[p]               # noqa: E731
        fm = f + m * f_p
        wm = 2 * np.pi * fm
        # ports
        for q, pt in enumerate(net.ports):
            A[:, V(pt.plane), V(pt.plane)] += 1.0 / pt.Z0
            if m == 0:
                rhs[:, V(pt.plane), q] = 2.0 / np.sqrt(pt.Z0)
        # lines: KCL takes +I1 at x0 and -I2 at xL (I2 flows out at xL)
        for k, ln in enumerate(net.lines):
            if ln.x0 is not None:
                A[:, V(ln.x0), I1(k)] += 1.0
            if ln.xL is not None:
                A[:, V(ln.xL), I2(k)] -= 1.0
            r1, r2 = I1(k), I2(k)            # constitutive rows reuse the current indices
            if not ln.poles:
                a_, b_, c_, d_ = line_abcd(ln, fm)
                if ln.x0 is not None:
                    A[:, r1, V(ln.x0)] += 1.0
                if ln.xL is not None:
                    A[:, r1, V(ln.xL)] -= a_
                A[:, r1, I2(k)] -= b_
                A[:, r2, I1(k)] += 1.0
                if ln.xL is not None:
                    A[:, r2, V(ln.xL)] -= c_
                A[:, r2, I2(k)] -= d_
                continue
            # kept poles. Near one (|f - p| < r/2): V - sum R a - Z_rem I_in = 0
            # with I_in = (I1, -I2). Elsewhere: the ABCD rows on the line's own
            # voltage V_l = V - sum R a + sum R I_in / (f - p), which has no
            # pole there (Z_rem keeps the poles that are not kept).
            near = np.zeros(nf, bool)
            for kp in ln.poles:
                near |= np.abs(fm - kp.p) < POLE_RADIUS * ln.FSR / 2
            terms = (ln.x0, ln.xL)
            ra = [o + lay["poles"][k] + j for j in range(len(ln.poles))]

            def vl(t):
                """V_l at terminal t as {column: coefficient (n_f,)}."""
                c = {}
                if terms[t] is not None:
                    c[V(terms[t])] = np.ones(nf, complex)
                for j, kp in enumerate(ln.poles):
                    c[ra[j]] = c.get(ra[j], 0) - kp.c * kp.u[t] * np.ones(nf)
                    w = kp.c * kp.u[t] / (fm - kp.p)
                    c[I1(k)] = c.get(I1(k), 0) + w * kp.u[0]
                    c[I2(k)] = c.get(I2(k), 0) - w * kp.u[1]
                return c

            def put(row, coeffs, mask):
                for col, v in coeffs.items():
                    v = np.broadcast_to(v, (nf,))
                    A[mask, row, col] += v[mask]

            far = ~near
            if np.any(far):
                with np.errstate(divide="ignore", invalid="ignore"):
                    a_, b_, c_, d_ = line_abcd(ln, fm)
                    v0, v1 = vl(0), vl(1)
                row1 = dict(v0)
                for col, v in v1.items():
                    row1[col] = row1.get(col, 0) - a_ * v
                row1[I2(k)] = row1.get(I2(k), 0) - b_
                row2 = {I1(k): np.ones(nf, complex)}
                for col, v in v1.items():
                    row2[col] = row2.get(col, 0) - c_ * v
                row2[I2(k)] = row2.get(I2(k), 0) - d_
                put(r1, row1, far)
                put(r2, row2, far)
            if np.any(near):
                Zr = z_rem(ln, fm[near])
                full = np.zeros((nf, 2, 2), complex)
                full[near] = Zr
                for row, t in ((r1, 0), (r2, 1)):
                    c = {I1(k): -full[:, t, 0], I2(k): full[:, t, 1]}
                    if terms[t] is not None:
                        c[V(terms[t])] = np.ones(nf)
                    for j, kp in enumerate(ln.poles):
                        c[ra[j]] = -kp.c * kp.u[t] * np.ones(nf)
                    put(row, c, near)
            for j, kp in enumerate(ln.poles):
                A[:, ra[j], ra[j]] = fm - kp.p
                A[:, ra[j], I1(k)] -= kp.u[0]
                A[:, ra[j], I2(k)] += kp.u[1]
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
                    A[:, V(pu.plane), oc + lay["flux"] + fidx[pu.plane]] += 0.5 * pu.delta * ph
        # CMT blocks (sector 0 only; refused elsewhere at compile time):
        # M_iso a - K j = 0, V/sqrt(Zr) - (i/2) K^dag a = 0, j = sqrt(Zr) I
        for (oa, oi), cb in zip(lay["cmt"], net.cmt):
            ra = o + oa + np.arange(cb.n)
            A[:, ra[:, None], ra[None, :]] = cb.M_rows(fm)
            Kr = cb.K_rows
            sq = np.sqrt(cb.Zr)
            for c, pl in enumerate(cb.planes):
                ri = o + oi + c
                A[:, ra, ri] = -Kr[:, c] * sq
                A[:, ri, V(pl)] = 1.0 / sq
                A[:, ri, ra] = -0.5j * np.conj(Kr[:, c])
                A[:, V(pl), ri] += 1.0
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


def solve_network(doc: Document, f=None, promote: bool = False) -> List[NetworkResult]:
    """S per component over the grid f (default: the document's sweep), in
    the window doc.solve.sectors. promote=True carries solve.kept_poles as
    mode rows (S is the same; see the module docstring). A component whose
    CMT block lacks parameters has S = None, as in milestone 1."""
    if f is None:
        from ..model.legacy_job import sweep_grid
        f = sweep_grid(doc)
    f = np.asarray(f, dtype=float)
    st = doc.solve
    out = []
    for net in compile_network(doc, promote=promote):
        issues = list(net.issues)
        history = []
        converged = True
        if not net.complete:
            out.append(NetworkResult(
                index=net.index, S=None, S_sectors={}, sectors=[0], f=f, f_p=net.f_p,
                ports=[p.id for p in net.ports], port_labels=[p.label for p in net.ports],
                network=net, issues=issues))
            continue
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
