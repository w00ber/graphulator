"""Residue snapping in the legacy (2.0/3.0) layout, for the gates.

An independent statement of decision Q2 option A, written against the legacy
field names. The model does the same on Document fields (model/snap.py), so
comparing the two checks the model's field list, not just snap() itself.
"""
import copy

from graphulator.model import PRECISION as P
from graphulator.model.quantize import snap

NODE = {"freq": P["mode.freq"], "B_int": P["mode.B_int"], "B_ext": P["attachment.rate"]}
EDGE = {"rate": P["coupling.rate"], "phase": P["phase"], "f_p": P["tone.f"]}
LINE = {"FSR": P["line.FSR"], "Ztx": P["line.Ztx"], "f_max": P["line.f_max"],
        "Z0_port": P["Z0"], "f_ref": P["line.f_ref"]}
PUMP = {"f_p": P["tone.f"], "rate": P["pump.rate"], "phase": P["phase"]}


def _apply(obj, table):
    for k, d in table.items():
        if obj.get(k) is not None:
            obj[k] = snap(obj[k], d)


def snap_legacy(d):
    d = copy.deepcopy(d)
    for n in d.get("nodes", []):
        _apply(n, NODE)
    for e in d.get("edges", []):
        _apply(e, EDGE)
    for p in d.get("ports", []) or []:
        for a in p.get("attachments", []):
            _apply(a, {"rate": P["attachment.rate"]})
    for l in d.get("line_resonators", []) or []:
        _apply(l, LINE)
        for s in l.get("sections") or []:
            _apply(s, {"Z": P["line.section_Z"]})
        if l.get("load"):
            _apply(l["load"], {"f_Z": P["load.f_Z"]})
        if l.get("pump"):
            _apply(l["pump"], PUMP)
        for end in ("x0", "xL"):
            raw = (l.get("ends") or {}).get(end) or []
            for c in ([raw] if isinstance(raw, dict) else raw):
                if c.get("kind") == "node":
                    _apply(c, {"rate": P["attachment.rate"]})
    # assignments the GUI keeps per node/edge id mirror the node/edge fields
    return d
