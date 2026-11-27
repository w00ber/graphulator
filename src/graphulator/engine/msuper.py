"""Document -> M_super, abstract workflow (step 4, milestone 1).

Design note: docs/design/step4_msuper_m1.md. A lumped document is solved
exactly as drawn: one (mode, sector) row per drawn mode, its sector from
frames.assign_frames, and Sigma_0 holding only the ports, whose Schur
reduction onto the mode rows is the constant (i/2) K K^dag. Per component:

    M_kk(f) = (f + nu_k) -+ f_k + i B_int,k / 2 + (i/2) (K K^dag)_kk      (- unconjugated, + conjugated)
    M_jk    = (g/2) e^{i phi},   M_kj = sigma conj(M_jk)   (j earlier in mode order; sigma = -1 across sectors)
    S       = -1 + i K^dag M^{-1} K

This module reads model objects directly (no to_legacy). The rules that
decide components, root, channel order and frames are the legacy engine's,
restated over the model, because milestone 1 is gated bit for bit against
model/legacy_job (tests/test_engine_msuper.py). Conventions kept from legacy
on purpose (design note, M2-M6): the coupling phase is referred to the
earlier mode in mode order; frame offsets are rounded to 12 decimals; with
several components the saved root is not used. Deviation: parallel edges
between one pair are summed (legacy keeps the last); no shipped file has any.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..autograph import _MIXED_SECTOR_MSG, _hub_signed_weight
from ..model.migrate import legacy_node_id
from ..model.schema import Document
from ..model.validate import Issue
from .frames import EdgeRec, Frames, assign_frames


class NotLumpedError(ValueError):
    """The document has objects milestone 1 does not solve."""


@dataclass(frozen=True)
class Row:
    """One (mode, sector) row of M_super."""
    mode: str
    label: str
    sector: Optional[Tuple[int, ...]]   # None: lone mode, driven at the root frequency
    nu: Optional[float]                 # frame offset round(m . f, 12)
    f0: Optional[float]
    B_int: Optional[float]
    conj: bool


@dataclass
class Channel:
    """A plane after the closed-form Schur reduction: one column of K."""
    plane: str
    label: str
    monitored: bool
    weights: List[Tuple[int, float]]    # (row index, real signed weight)


@dataclass
class MSuper:
    """One connected component of a lumped document."""
    index: int
    rows: List[Row]
    couplings: List[Tuple[int, int, complex]]   # (j, k, beta), j < k in row order
    channels: List[Channel]
    root: str
    root_conj: bool
    tones: List[str]                            # sector axes (nonzero tones)
    frames: Optional[Frames]
    complete: bool
    issues: List[Issue] = field(default_factory=list)

    @property
    def ports(self) -> List[Channel]:
        return [c for c in self.channels if c.monitored]


# ---------------------------------------------------------------------------
# reading the document
# ---------------------------------------------------------------------------

def _refuse_non_lumped(doc: Document):
    why = []
    for b in doc.blocks:
        if not (b.type == "R" and b.params.get("R") == "matched"):
            why.append(f"block {b.id} ({b.type})")
    for p in doc.pumped:
        if p.kind != "coupling":
            why.append(f"pumped element {p.id}")
    for m in doc.modes:
        if (m.origin or {}).get("kind", "lumped") != "lumped":
            why.append(f"mode {m.id} ({m.origin.get('kind')})")
    if why:
        raise NotLumpedError(
            "The M_super engine solves lumped documents only (step 4, "
            "milestone 1); lines, other blocks and element pumps come in "
            "milestone 2. Not lumped: " + ", ".join(why))


def _edge_records(doc: Document, mode_ids) -> List[EdgeRec]:
    """Drawn edges in the legacy edge order (drawing.order['edges'])."""
    tones = doc.by_id("tones")
    by_id: Dict[str, EdgeRec] = {}
    for c in doc.couplings:
        by_id[c.id] = EdgeRec(c.id, c.a, c.b, c.a == c.b, c.rate, c.phase)
    for p in doc.pumped:
        by_id[p.id] = EdgeRec(p.id, p.a, p.b, p.a == p.b, p.rate, p.phase,
                              tone=p.tone, tone_f=tones[p.tone].f)
    out, seen = [], set()
    for eid in doc.drawing.order.get("edges", []):
        if eid in by_id:
            out.append(by_id[eid])
            seen.add(eid)
            continue
        ends = (doc.drawing.edges.get(eid) or {}).get("_ends")
        if ends and ends[0] == ends[1]:            # drawing-only B_ext marker loop
            out.append(EdgeRec(eid, ends[0], ends[1], True, physical=False))
    out += [r for eid, r in by_id.items() if eid not in seen]
    return [r for r in out if r.a in mode_ids and r.b in mode_ids]


def _ports(doc: Document, mode_ids):
    """Explicit planes (legacy 'ports', monitored or loss) and B_ext planes."""
    atts: Dict[str, list] = {}
    for a in doc.attachments:
        atts.setdefault(a.plane, []).append(a)
    explicit, bext = [], {}
    for pl in doc.planes:
        node = pl.extras.get("legacy_B_ext_node")
        if node is not None:
            for a in atts.get(pl.id, []):
                bext[a.mode] = (pl, a.rate)
            continue
        explicit.append((pl, [a for a in atts.get(pl.id, []) if a.mode in mode_ids]))
    return explicit, bext


def _keys(mode_ids):
    """Node keys for the shared tree code: the legacy int ids when every mode
    has one (so the DFS matches the legacy job's), else row positions."""
    keys = {m: legacy_node_id(m) for m in mode_ids}
    if all(isinstance(k, int) for k in keys.values()) and len(set(keys.values())) == len(keys):
        return keys
    return {m: i for i, m in enumerate(mode_ids)}


# ---------------------------------------------------------------------------
# compile
# ---------------------------------------------------------------------------

def compile_document(doc: Document) -> List[MSuper]:
    """A lumped Document -> one MSuper per connected component (legacy order)."""
    _refuse_non_lumped(doc)
    modes = doc.by_id("modes")
    order = [m.id for m in doc.modes]
    if not order:
        return []
    mode_set = set(order)
    keys = _keys(order)
    edges = _edge_records(doc, mode_set)
    explicit, bext = _ports(doc, mode_set)
    nonzero = [t for t in doc.tones if t.f != 0]
    tone_ids, tone_f = [t.id for t in nonzero], [t.f for t in nonzero]

    # components: drawn edges + shared explicit planes, BFS in mode order,
    # largest first (stable)
    adj = {m: set() for m in order}
    for e in edges:
        if not e.self_loop:
            adj[e.a].add(e.b)
            adj[e.b].add(e.a)
    for _, pa in explicit:
        ids = [a.mode for a in pa]
        for other in ids[1:]:
            adj[ids[0]].add(other)
            adj[other].add(ids[0])
    visited, comps = set(), []
    for m in order:
        if m in visited:
            continue
        comp, queue = set(), [m]
        while queue:
            cur = queue.pop(0)
            if cur in visited:
                continue
            visited.add(cur)
            comp.add(cur)
            queue.extend(nb for nb in adj[cur] if nb not in visited)
        comps.append(comp)
    comps.sort(key=len, reverse=True)
    multi = len(comps) > 1

    def port_keys(ids):
        """The legacy port_node_ids set, built in the legacy insertion order
        (its iteration order picks the multi-component root)."""
        s = set()
        for e in edges:
            if e.self_loop and e.a in ids:
                s.add(keys[e.a])
        for pl, pa in explicit:
            if pl.kind == "port":
                s.update(keys[a.mode] for a in pa if a.mode in ids)
        return s

    out = []
    for idx, comp in enumerate(comps if multi else [mode_set]):
        ids = [m for m in order if m in comp]
        hubs = [(pl, pa) for pl, pa in explicit
                if pa and all(a.mode in comp for a in pa)]
        root = _root(doc, keys, ids, comp, hubs, edges, explicit, bext, multi,
                     port_keys(comp))
        out.append(_compile_component(
            doc, idx, ids, modes, keys, [e for e in edges if e.a in comp],
            hubs, bext, root, tone_ids, tone_f))
    return out


def _root(doc, keys, ids, comp, hubs, edges, explicit, bext, multi, pkeys):
    inv = {keys[m]: m for m in ids}
    first_hub = next((a.mode for pl, pa in hubs if pl.kind == "port" for a in pa), None)
    if multi:
        if first_hub is not None:
            return first_hub
        if pkeys:
            return inv[next(iter(pkeys))]
        return ids[0]
    # one component: the saved root if it is a port mode (decision Q1)
    shown = [m for m in ids if keys[m] in pkeys]
    if doc.solve.root in shown:
        return doc.solve.root
    if shown:
        return shown[0]
    if first_hub is not None:
        return first_hub
    # legacy _default_root_node_id
    for pl, pa in explicit:
        if pl.kind == "port" and pa:
            return pa[0].mode
    loops = {e.a for e in edges if e.self_loop}
    for m in ids:
        if m in loops and m in bext and bext[m][1] > 0:
            return m
    return ids[0]


def _compile_component(doc, idx, ids, modes, keys, edges, hubs, bext, root,
                       tone_ids, tone_f) -> MSuper:
    issues: List[Issue] = []
    path = f"component{idx}"

    def missing(what):
        issues.append(Issue("error", path, f"missing {what}"))

    # parameters (legacy validate_scattering_assignments)
    loops = {e.a for e in edges if e.self_loop}
    for m in ids:
        mo = modes[m]
        need = [k for k in ("freq", "B_int") if getattr(mo, k) is None]
        if m in loops and m not in bext and mo.extras.get("B_ext") is None:
            need.append("B_ext")
        if need:
            missing(f"{need} on mode {m} ({mo.label})")
    phys = [e for e in edges if not e.self_loop]
    for e in phys:
        need = [k for k in ("rate", "phase") if getattr(e, k) is None]
        if need:
            missing(f"{need} on edge {e.id}")
    complete = not issues

    frames = None
    if all(modes[m].freq is not None for m in ids):
        frames = assign_frames(ids, keys, modes, edges,
                               [[a.mode for a in pa] for _, pa in hubs],
                               root, tone_ids, tone_f)
        for eid in frames.missing_fp:
            missing(f"f_p on tree edge {eid} (only a chord's pump frequency is derived)")
        issues += [Issue("info", path, n) for n in frames.notes]
        complete = complete and not frames.missing_fp

    row_of = {m: i for i, m in enumerate(ids)}
    rows = [Row(m, modes[m].label,
                frames.sectors.get(m) if frames else None,
                frames.offsets.get(m) if frames else None,
                modes[m].freq, modes[m].B_int, bool(modes[m].conj)) for m in ids]

    # couplings: beta on (earlier, later) in row order (legacy convention, M2)
    couplings = []
    pairs = set()
    for e in phys:
        j, k = row_of[e.a], row_of[e.b]
        if j == k or e.rate is None or e.phase is None:
            continue
        beta = e.rate / 2 * np.exp(1j * e.phase * np.pi / 180)
        lo, hi = min(j, k), max(j, k)
        if (lo, hi) in pairs:
            issues.append(Issue("warning", path,
                                f"parallel edges between {ids[lo]} and {ids[hi]}: summed"))
        pairs.add((lo, hi))
        couplings.append((lo, hi, beta))

    # channels: explicit monitored ports, then B_ext ports in mode order, then loss
    conj = {m: bool(modes[m].conj) for m in ids}
    explicit_ch = []
    for pl, pa in hubs:
        if len({conj[a.mode] for a in pa}) > 1:
            details = ", ".join(f"node {a.mode!r} (conj={conj[a.mode]})" for a in pa)
            raise ValueError(_MIXED_SECTOR_MSG.format(hub_id=pl.id, details=details))
        w = [(row_of[a.mode],
              _hub_signed_weight(pl.id, a.mode, float(np.sqrt(max(float(a.rate), 0.0))),
                                 a.phase_deg)) for a in pa]
        explicit_ch.append(Channel(pl.id, pl.label, pl.kind == "port", w))
    channels = [c for c in explicit_ch if c.monitored]
    for m in ids:
        if m in bext and bext[m][1] is not None and bext[m][1] > 0:
            pl, rate = bext[m]
            channels.append(Channel(pl.id, modes[m].label, True,
                                    [(row_of[m], float(np.sqrt(rate)))]))
    channels += [c for c in explicit_ch if not c.monitored]

    return MSuper(index=idx, rows=rows, couplings=couplings, channels=channels,
                  root=root, root_conj=bool(modes[root].conj), tones=list(tone_ids),
                  frames=frames, complete=complete, issues=issues)
