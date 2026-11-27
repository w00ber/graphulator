"""Snap floating-point residue in user-entered numbers (decision Q2, option A).

``snap_document(doc)`` moves every user-entered number of a Document to its
widget-precision value when it is only floating-point residue away from it
(``quantize.snap``): 14.999999999999996 -> 15.0, 0.10000000000000003 -> 0.1.
A number deliberately finer than any widget (a script-computed FSR or pump
frequency) is left alone, and derived numbers (alpha from a loss rate,
section fractions from angles) are not touched at all.

Precision is the finest widget that edits the quantity, in stored units
(milli-unit displays add 3 decimals): see PRECISION. It runs wherever a
Document is made from data (from_legacy, from_dict for 4.0) and on save, so
the GUI (which opens and saves through the model), Show S, the export and
scripts all see the same numbers.
"""
from __future__ import annotations

from typing import Dict

from .quantize import snap
from .schema import Document

#: stored-unit decimals per quantity (finest widget; milli displays + 3)
PRECISION: Dict[str, int] = {
    "mode.freq": 3,          # scattering table / node dialog, 3 decimals
    "mode.B_int": 6,         # table: 3 decimals of milli-units
    "attachment.rate": 5,    # port / B_ext / tap rate: 2 decimals of milli-units
    "coupling.rate": 5,      # edge rate: 2 decimals of milli-units
    "phase": 1,              # edge / pump phase, degrees
    "pump.rate": 6,          # line pump rate: 3 decimals of milli-units
    "tone.f": 4,             # edge f_p (3) / line pump f_p (4)
    "line.FSR": 9,           # lines table carries 9
    "line.Ztx": 2,
    "line.f_ref": 4,
    "line.section_Z": 2,
    "line.f_max": 4,
    "Z0": 2,                 # port plane / line Z0_port
    "load.f_Z": 6,           # load dialog, 6 decimals
}


def snap_document(doc: Document) -> Document:
    """Snap residue in place; returns doc. Tones that become equal merge."""
    P = PRECISION
    for m in doc.modes:
        m.freq = snap(m.freq, P["mode.freq"])
        m.B_int = snap(m.B_int, P["mode.B_int"])
    for a in doc.attachments:
        a.rate = snap(a.rate, P["attachment.rate"])
    for c in doc.couplings:
        c.rate = snap(c.rate, P["coupling.rate"])
        c.phase = snap(c.phase, P["phase"])
    for p in doc.pumped:
        p.phase = snap(p.phase, P["phase"])
        if p.kind == "coupling":
            p.rate = snap(p.rate, P["coupling.rate"])
        if p.legacy_anchor and "rate" in p.legacy_anchor and p.kind == "element":
            p.legacy_anchor["rate"] = snap(p.legacy_anchor["rate"], P["pump.rate"])
    for pl in doc.planes:
        pl.Z0 = snap(pl.Z0, P["Z0"])
    for b in doc.blocks:
        if b.type == "line":
            for k in ("FSR", "Ztx", "f_ref"):
                if k in b.params:
                    b.params[k] = snap(b.params[k], P[f"line.{k}"])
            for sec in b.params.get("sections") or []:
                if isinstance(sec, dict) and "Z" in sec:
                    sec["Z"] = snap(sec["Z"], P["line.section_Z"])
            if "Z0_port" in b.extras:
                b.extras["Z0_port"] = snap(b.extras["Z0_port"], P["Z0"])
        elif "f_Z" in b.params:
            b.params["f_Z"] = snap(b.params["f_Z"], P["load.f_Z"])
    for kp in doc.solve.kept_poles.values():
        if isinstance(kp, dict) and "f_max" in kp:
            kp["f_max"] = snap(kp["f_max"], P["line.f_max"])
    # tones: snap, then merge any that now coincide
    first: Dict[float, str] = {}
    alias: Dict[str, str] = {}
    keep = []
    for t in doc.tones:
        t.f = snap(t.f, P["tone.f"])
        if t.f in first:
            alias[t.id] = first[t.f]
        else:
            first[t.f] = t.id
            keep.append(t)
    if alias:
        doc.tones = keep
        for p in doc.pumped:
            p.tone = alias.get(p.tone, p.tone)
    return doc
