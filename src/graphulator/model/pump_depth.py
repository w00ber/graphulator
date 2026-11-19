"""Element-pump depth <-> the legacy {rate, n_ref} anchor (decision D4).

The model stores the modulation depth delta of 1/L(t) = 1/L0 + delta cos(omega_p t + phi)
(``Pumped.depth``). The legacy line pump stores a rate at a reference mode
pair instead; ``legacy_anchor`` keeps it as provenance. The two are related
by (docs/design/step4_msuper_m2.md, "Depth (D4)"):

    rate = g_nm / pi,   g_nm = delta u_n u_m / (4 sqrt(omega_n C_n omega_m C_m))

with omega = 2 pi f, and u, C, f the line's (loaded, stepped) mode
quantities from autograph.LineResonator at the anchor pair (n, m) the legacy
macro uses: n = n_ref clamped into the comb, m the partner nearest the pump's
target (legacy_job.pump_anchor's rule). In natural units this is
docs/pumped_line_termination.md sec. 6, rate = (2 FSR / pi) g_nat. The
conversion is gated in tests/test_engine_network.py.

- Migration (from_legacy) and loading a 4.0 file without a depth fill it in
  from the anchor (``fill_depths``).
- Export to legacy recomputes the rate from the depth (``legacy_rate``). When
  the depth is still what the stored anchor rate gives, the stored rate is
  written verbatim, so an unedited file round-trips bit for bit.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np

from .schema import Document


def _line_resonator(doc: Document, blk):
    from ..autograph import LineResonator
    p = blk.params
    load = None
    for b in doc.blocks:
        if b.extras.get("load_of") == blk.id:
            end = next(e for e in ("x0", "xL") if blk.terminals.get(e) == b.terminals.get("a"))
            load = {"end": end, "type": {"L": "inductive", "C": "capacitive"}[b.type],
                    "f_Z": b.params["f_Z"]}
    spec = doc.solve.kept_poles.get(blk.id) or {}
    if isinstance(spec, dict):
        f_max = spec.get("f_max", p["FSR"])
    else:                                   # a list of pole indices: no f_max to clamp to
        f_max = float(p["FSR"]) * (max([0] + [int(n) for n in spec]) + 64)
    return LineResonator(line_id=blk.id, FSR=float(p["FSR"]), Ztx=float(p["Ztx"]),
                         f_max=float(f_max), label=blk.label or blk.id,
                         alpha_uniform=float(p.get("alpha_uniform", 0.0)),
                         load=load, sections=p.get("sections"))


def anchor_factor(doc: Document, pumped) -> Tuple[float, Dict[str, Any]]:
    """(F, info) with delta = F * rate at the pump's anchor pair.

    Raises ValueError when there is no anchor, the pump is not a modulated
    1/L, or the anchor pair has no amplitude at the pumped end (no depth
    reaches the rate)."""
    from .legacy_job import clamp_mode, pump_partners
    an = pumped.legacy_anchor or {}
    if an.get("line") is None:
        raise ValueError(f"pump {pumped.id}: no legacy anchor (line, end, n_ref)")
    if (an.get("coupling") or "inductive") != "inductive" or pumped.param != "1/L":
        raise ValueError(f"pump {pumped.id}: only a modulated 1/L is supported")
    res = _line_resonator(doc, doc.by_id("blocks")[an["line"]])
    end = an["end"]
    f_p = doc.by_id("tones")[pumped.tone].f
    n = clamp_mode(res, an.get("n_ref") or 1, res.label, "pump")
    rank = {"amplification": 0, "down-conversion": 1, "up-conversion": 2}
    best = min(pump_partners(res, n, f_p), key=lambda q: (abs(q["detune"]), rank[q["family"]]))
    m = int(best["m"])
    u_n, u_m = res.mode_profile(n, end), res.mode_profile(m, end)
    if u_n == 0.0 or u_m == 0.0:
        raise ValueError(f"pump {pumped.id}: the anchor pair ({n}, {m}) has no "
                         f"amplitude at {end}; no depth reaches a nonzero rate")
    f_n, f_m = res.mode_freq(n), res.mode_freq(m)
    C_n, C_m = res.mode_mass(n), res.mode_mass(m)
    w_n, w_m = 2 * np.pi * f_n, 2 * np.pi * f_m
    F = 4.0 * np.pi * np.sqrt(w_n * C_n * w_m * C_m) / abs(u_n * u_m)
    return float(F), {"n_ref": n, "m_ref": m, "family": best["family"],
                      "u": (u_n, u_m), "C": (C_n, C_m), "f": (f_n, f_m)}


def anchor_depth(doc: Document, pumped) -> Tuple[float, Dict[str, Any]]:
    """delta from the stored anchor rate."""
    rate = (pumped.legacy_anchor or {}).get("rate")
    if rate is None:
        raise ValueError(f"pump {pumped.id}: the legacy anchor has no rate")
    F, info = anchor_factor(doc, pumped)
    return F * float(rate), info


def legacy_rate(doc: Document, pumped) -> float:
    """The anchor rate to export: recomputed from the depth, or the stored
    rate verbatim when the depth is still the one it gives."""
    an = pumped.legacy_anchor or {}
    if pumped.depth is None:
        return an.get("rate")
    try:
        if an.get("rate") is not None and anchor_depth(doc, pumped)[0] == pumped.depth:
            return an["rate"]
        F, _ = anchor_factor(doc, pumped)
    except ValueError:
        return an.get("rate")
    return float(pumped.depth) / F


def fill_depths(doc: Document) -> Document:
    """Set Pumped.depth from the anchor where it is missing (in place).
    A pump whose anchor cannot be converted keeps depth None; the engine
    reports why."""
    for p in doc.pumped:
        if p.kind == "element" and p.depth is None:
            try:
                p.depth = anchor_depth(doc, p)[0]
            except (ValueError, KeyError):
                pass
    return doc
