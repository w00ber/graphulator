"""Engine results in the shape the GUI's Show S plot reads (Qt-free).

The plot code (Graphulator._on_sparams_finished and what it calls) was
written against ``model.legacy_job.compute_job``. Each result there is a
dict over *channels*:

- ``S``, ``SdB``: (n_f, C, C), out x in.
- ``port_ids``: one ref per channel, the GUI's id for it: the node id (int)
  of a legacy B_ext port, ``"port:<id>"`` of an explicit port or of a
  twin's port.
- ``port_dict``: ref -> {'label', 'conj', 'B_ext'}.
- ``drive_signals``: ref -> the channel's own frequency axis over the sweep
  (the frame it is read in: f + nu for a lumped mode, f + m f_p for a
  physical port in sector m).
- ``component_index``, ``component_label``.

This module builds that from ``engine.solve``. The physics is the engine's;
only the bookkeeping is legacy's.

- Lumped documents: the channels are MSuper.ports, S is the engine's
  (milestone 1 is bit for bit with legacy, so nothing on screen moves).
- Physical documents: the channels are each port in sector 0 plus each
  sector view the drawing has of a port (a twin's port: TL* is that port
  read in the pump's partner sector). S is NetworkResult.S_channels, photon
  normalized, which is the normalization legacy's CMT S has.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import numpy as np

from ..model.schema import Document


def _plane_ref(doc: Document, plane_id: str):
    """The GUI's id for a plane: a B_ext node id, or 'port:<id>'."""
    pl = next((p for p in doc.planes if p.id == plane_id), None)
    if pl is not None and "legacy_B_ext_node" in pl.extras:
        return pl.extras["legacy_B_ext_node"]
    glyph = doc.drawing.ports.get(plane_id) or {}
    if "port_id" in glyph:
        return f"port:{glyph['port_id']}"
    m = re.fullmatch(r"port(\d+)", plane_id)
    if m:
        return f"port:{int(m.group(1))}"
    return plane_id


def _db(S):
    with np.errstate(divide="ignore"):
        return 20 * np.log10(np.abs(S))


def _label(index: int, multi: bool) -> str:
    return f"C{index + 1}" if multi else ""


def _lumped(doc: Document, r, multi: bool, f) -> Optional[Dict[str, Any]]:
    if r.S is None:
        return None
    ms = r.msuper
    f_calc = -np.asarray(f) if ms.root_conj else np.asarray(f)
    refs, port_dict, drive = [], {}, {}
    for ch in ms.ports:
        ref = _plane_ref(doc, ch.plane)
        row = ms.rows[ch.weights[0][0]] if ch.weights else None
        refs.append(ref)
        port_dict[ref] = {"label": ch.label,
                          "conj": bool(row.conj) if row is not None else False,
                          "B_ext": float(sum(w * w for _, w in ch.weights))}
        nu = row.nu if row is not None else None
        drive[ref] = f_calc + nu if nu is not None else f_calc
    for row in ms.rows:
        m = re.fullmatch(r"n(\d+)", row.mode)
        key = int(m.group(1)) if m else row.mode
        drive.setdefault(key, f_calc + row.nu if row.nu is not None else f_calc)
    return {"S": r.S, "SdB": _db(r.S), "port_dict": port_dict,
            "drive_signals": drive, "port_ids": refs,
            "component_index": r.index, "component_label": _label(r.index, multi)}


def _network(doc: Document, r, multi: bool, f) -> Optional[Dict[str, Any]]:
    if r.S is None or r.S_channels is None:
        return None
    f = np.asarray(f, dtype=float)
    f_p = r.f_p or 0.0
    views = {}
    for v in doc.drawing.sector_views:
        g = v.glyph or {}
        if "port_id" in g and "twin_of" not in g:
            views.setdefault(v.of, []).append(g["port_id"])
    refs, port_dict, drive = [], {}, {}
    used = {}
    for p, m, label in r.channels:
        plane = r.ports[p]
        if m == 0:
            ref = _plane_ref(doc, plane)
        else:
            k = used.get(plane, 0)
            ids = views.get(plane, [])
            ref = f"port:{ids[k]}" if k < len(ids) else f"{plane}:{m}"
            used[plane] = k + 1
        refs.append(ref)
        port_dict[ref] = {"label": label, "conj": False, "B_ext": None}
        drive[ref] = f + m * f_p
    return {"S": r.S_channels, "SdB": _db(r.S_channels), "port_dict": port_dict,
            "drive_signals": drive, "port_ids": refs,
            "component_index": r.index, "component_label": _label(r.index, multi),
            "sectors": list(r.sectors), "converged": r.converged}


def payloads(doc: Document, results, f) -> List[Dict[str, Any]]:
    """engine.solve(doc, f) -> the GUI's per-component result dicts (components
    without S are left out, as legacy leaves out a job that returns None)."""
    multi = len(results) > 1
    out = []
    for r in results:
        build = _network if hasattr(r, "S_channels") else _lumped
        d = build(doc, r, multi, f)
        if d is not None:
            d["issues"] = [(i.level, i.path, i.msg) for i in r.issues]
            out.append(d)
    return out


def solve_for_gui(doc: Document, f) -> Dict[str, Any]:
    """{'results': payloads, 'issues': [(level, path, msg)]} for a document.
    Raises engine.NotSupportedError (or TapError) when the engine cannot
    represent the document; the GUI falls back to legacy then."""
    from . import solve
    results = solve(doc, f)
    issues = [(i.level, i.path, i.msg) for r in results for i in r.issues]
    return {"results": payloads(doc, results, f), "issues": issues}
