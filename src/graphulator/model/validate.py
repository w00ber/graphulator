"""validate(doc) -> [Issue]; never raises on user content."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .schema import Document


@dataclass
class Issue:
    level: str      # 'error' | 'warning'
    path: str
    msg: str


def validate(doc: Document) -> List[Issue]:
    out: List[Issue] = []
    err = lambda p, m: out.append(Issue("error", p, m))
    warn = lambda p, m: out.append(Issue("warning", p, m))

    for kind in ("tones", "planes", "blocks", "modes", "couplings", "attachments", "pumped"):
        seen = set()
        for o in getattr(doc, kind):
            if o.id in seen:
                err(f"{kind}/{o.id}", "duplicate id")
            seen.add(o.id)
    modes, planes = doc.by_id("modes"), doc.by_id("planes")
    tones, blocks = doc.by_id("tones"), doc.by_id("blocks")

    for c in doc.couplings:
        for end in (c.a, c.b):
            if end not in modes:
                err(f"couplings/{c.id}", f"unknown mode {end!r}")
        if c.rate is None:
            warn(f"couplings/{c.id}", "no rate assigned")
    for a in doc.attachments:
        if a.mode not in modes:
            err(f"attachments/{a.id}", f"unknown mode {a.mode!r}")
        if a.plane not in planes:
            err(f"attachments/{a.id}", f"unknown plane {a.plane!r}")
        if a.phase_deg not in (0.0, 180.0):
            warn(f"attachments/{a.id}", "phase outside {0, 180}: the legacy engine ignores it")
        if a.element is not None and not (a.legacy_anchor or {}).get("n_ref"):
            err(f"attachments/{a.id}", "tap without a reference harmonic n_ref")
    for b in doc.blocks:
        for t, pid in b.terminals.items():
            if pid not in planes:
                err(f"blocks/{b.id}", f"terminal {t} -> unknown plane {pid!r}")
        if b.type == "line":
            for k in ("FSR", "Ztx"):
                v = b.params.get(k)
                if not (isinstance(v, (int, float)) and v > 0):
                    err(f"blocks/{b.id}", f"{k} must be > 0 (got {v!r})")
    for p in doc.pumped:
        if p.tone not in tones:
            err(f"pumped/{p.id}", f"unknown tone {p.tone!r}")
        if p.kind == "coupling":
            for end in (p.a, p.b):
                if end not in modes:
                    err(f"pumped/{p.id}", f"unknown mode {end!r}")
        elif p.kind == "element":
            if p.plane not in planes:
                err(f"pumped/{p.id}", f"unknown plane {p.plane!r}")
            if p.block is not None and p.block not in blocks:
                err(f"pumped/{p.id}", f"unknown block {p.block!r}")
        else:
            err(f"pumped/{p.id}", f"unknown kind {p.kind!r}")
    for pl in doc.planes:
        if pl.Z0 is not None and not pl.Z0 > 0:
            err(f"planes/{pl.id}", f"Z0 must be > 0 (got {pl.Z0!r})")

    s = doc.solve
    if s.sectors != "auto":
        if not (isinstance(s.sectors, list) and len(s.sectors) == 2 and s.sectors[0] <= 0 <= s.sectors[1]):
            err("solve/sectors", "must be 'auto' or [m_lo, m_hi] with m_lo <= 0 <= m_hi")
        elif doc.pumped and s.sectors[1] - s.sectors[0] + 1 < 2:
            warn("solve/sectors", "a pumped document solved in one sector has no idler")
    if not s.sector_max >= 2:
        err("solve/sector_max", "must be >= 2")

    # a sweep point exactly on a line pole (f = n FSR of an open-open line)
    if doc.sweep is not None and doc.sweep.points > 1:
        df = doc.sweep.span / (doc.sweep.points - 1)
        for b in doc.blocks:
            fsr = b.params.get("FSR") if b.type == "line" else None
            if not fsr or b.params.get("sections"):
                continue
            k = (doc.sweep.start / fsr)
            hits = [n for n in range(int(k), int(doc.sweep.stop / fsr) + 2)
                    if doc.sweep.start <= n * fsr <= doc.sweep.stop
                    and abs(((n * fsr - doc.sweep.start) / df) - round((n * fsr - doc.sweep.start) / df)) < 1e-9]
            if hits:
                warn(f"blocks/{b.id}", f"sweep lands on line pole(s) f = n*FSR, n = {hits[:5]}: nudge the grid")
    return out
