"""pgraph 2.0 / 3.0  <->  4.0 Document (pure dict <-> dataclass, no GUI).

``from_legacy(d)`` turns a 2.0/3.0 file dict into a Document.
``to_legacy(doc)`` writes it back as the 2.0/3.0 dict today's GUI serializer
would produce. The pair is lossless on every shipped example (tests/
test_model_roundtrip.py), modulo two normalizations the GUI loader already
applies: a key whose value is None is the same as an absent key, and a line
end's connection list is in list form.

Mapping (design note, "Migration map"):
- node              -> Mode n<id> (+ drawing.nodes); B_ext > 0 -> port Plane
                       bext<id> + Attachment bext<id> (legacy hub auto-wrap)
- edge with f_p     -> Pumped(kind='coupling') + Tone;  edge with a rate or a
                       non-self-loop edge -> Coupling;  self-loop without
                       physics -> drawing only
- port              -> Plane port<id> (+ Attachments port<id>.a<i>); an
                       unmonitored port (loss hub) -> internal Plane + matched
                       R Block
- primary line      -> Block line<id> (type 'line'); each end is the port Plane
                       it terminates on, or an internal Plane line<id>.<end>;
                       taps -> Attachment(element 'C'|'L', legacy_anchor n_ref);
                       load -> Block line<id>.load (type 'L'|'C');
                       pump -> Pumped(kind='element') + Tone; f_max ->
                       solve.kept_poles
- twin line + its   -> drawing.sector_views (sector -1); dropped from physics
  port glyph
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List

from .pump_depth import fill_depths, legacy_rate
from .quantize import quantize_sweep
from .snap import snap_document
from .schema import (Attachment, Block, Coupling, Document, Drawing, Mode,
                     Plane, Pumped, SectorView, SolveSettings, Sweep, Tone)


class MigrationError(ValueError):
    pass


NODE_PHYS = ("node_id", "label", "freq", "B_int", "B_ext", "conj")
EDGE_PHYS = ("from_node_id", "to_node_id", "f_p", "rate", "phase", "from_to")
PORT_PHYS = ("label", "monitored", "attachments")
ATT_STYLE = ("color", "linewidth_mult", "label", "label_size_mult")
LINE_STYLE = ("line_id", "pos", "angle", "w_mult", "h_mult", "linewidth", "color", "fill")
LINE_PARAMS = ("FSR", "Ztx", "alpha_uniform", "sections", "f_ref", "end_coupling")
# physics a twin mirrors from its primary (GUI _sync_all_twins)
TWIN_SYNC = ("FSR", "Ztx", "f_max", "end_coupling", "Z0_port", "alpha_uniform",
             "load", "sections", "f_ref")
SCATTER_KNOWN = ("frequency", "sparams_plot", "injection_node_id", "tail_closure")
TOP_KNOWN = ("version", "format", "metadata", "view", "nodes", "edges",
             "code_properties", "notes", "scattering", "ports", "line_resonators")
ENDS = ("x0", "xL")


def end_conns(line: Dict[str, Any], end: str) -> List[Dict[str, Any]]:
    """Connection list at one end (legacy None / dict / list forms)."""
    raw = (line.get("ends") or {}).get(end)
    if not raw:
        return []
    return [raw] if isinstance(raw, dict) else list(raw)


def _mid(nid):
    return f"n{nid}"


def legacy_node_id(mode_id):
    """Inverse of _mid: 'n6' -> 6 (None -> None)."""
    if mode_id is None:
        return None
    return int(mode_id[1:]) if mode_id[1:].lstrip("-").isdigit() else mode_id[1:]


def _eid(e):
    return f"e{e['from_node_id']}_{e['to_node_id']}"


# ---------------------------------------------------------------------------
# 2.0 / 3.0 -> 4.0
# ---------------------------------------------------------------------------

def from_legacy(d: Dict[str, Any]) -> Document:
    d = copy.deepcopy(d)
    ver = str(d.get("version", "2.0"))
    if d.get("format", "pgraph") != "pgraph" or ver not in ("2.0", "3.0"):
        raise MigrationError(f"not a pgraph 2.0/3.0 dict (format={d.get('format')!r}, version={ver!r})")

    doc = Document()
    doc.meta = dict(d.get("metadata") or {})
    doc.meta["migrated_from"] = ver
    dr = doc.drawing = Drawing(view=dict(d.get("view") or {}))
    dr.order = {"nodes": [], "edges": [], "ports": [], "lines": []}
    doc.code = d.get("code_properties") or {}
    doc.notes = d.get("notes") or ""
    doc.extras = {k: v for k, v in d.items() if k not in TOP_KNOWN}
    if "notes" not in d:
        doc.extras["_notes_absent"] = True

    tones: Dict[float, str] = {}

    def tone_for(f):
        if f not in tones:
            tones[f] = f"tone{len(tones)}"
            doc.tones.append(Tone(id=tones[f], f=f))
        return tones[f]

    # -- nodes ----------------------------------------------------------------
    for n in d.get("nodes", []):
        mid = _mid(n["node_id"])
        m = Mode(id=mid, label=n.get("label", ""), freq=n.get("freq"),
                 B_int=n.get("B_int"), conj=bool(n.get("conj", False)))
        if "conj" not in n:
            m.extras["_conj_absent"] = True
        dr.nodes[mid] = {k: v for k, v in n.items() if k not in NODE_PHYS or k == "node_id"}
        dr.order["nodes"].append(n["node_id"])
        bext = n.get("B_ext")
        if bext is not None and bext > 0:
            pid = f"bext{n['node_id']}"
            doc.planes.append(Plane(id=pid, label=m.label, kind="port",
                                    extras={"legacy_B_ext_node": n["node_id"]}))
            doc.attachments.append(Attachment(id=pid, mode=mid, plane=pid, rate=float(bext)))
        elif "B_ext" in n:
            m.extras["B_ext"] = bext
        doc.modes.append(m)

    # -- edges ----------------------------------------------------------------
    for e in d.get("edges", []):
        eid = _eid(e)
        if eid in dr.edges:
            raise MigrationError(f"duplicate edge {eid}")
        a, b = _mid(e["from_node_id"]), _mid(e["to_node_id"])
        style = {k: v for k, v in e.items() if k not in EDGE_PHYS}
        dr.order["edges"].append(eid)
        if e.get("f_p") is not None:
            doc.pumped.append(Pumped(id=eid, kind="coupling", tone=tone_for(e["f_p"]),
                                     a=a, b=b, rate=e.get("rate"), phase=e.get("phase")))
        elif e.get("is_self_loop") and e.get("rate") is None:
            style["_ends"] = [a, b]          # drawing only (B_ext marker loop)
        else:
            doc.couplings.append(Coupling(id=eid, a=a, b=b, rate=e.get("rate"),
                                          phase=e.get("phase")))
        dr.edges[eid] = style

    # -- lines: classify twins and their port glyphs first -------------------
    lines = d.get("line_resonators", []) or []
    by_lid = {l["line_id"]: l for l in lines}
    primaries = [l for l in lines if l.get("twin_of") is None]
    twins = [l for l in lines if l.get("twin_of") is not None]
    prim_port_refs = {c["port_id"] for l in primaries for e in ENDS
                      for c in end_conns(l, e) if c.get("kind") == "port"}
    ports = d.get("ports", []) or []
    twin_port: Dict[Any, tuple] = {}      # port_id -> (twin line, end)
    for t in twins:
        if t["twin_of"] not in by_lid:
            raise MigrationError(f"twin {t.get('label')!r} of missing line {t['twin_of']}")
        for e in ENDS:
            for c in end_conns(t, e):
                if c.get("kind") == "port":
                    twin_port[c["port_id"]] = (t, e)
    for p in ports:
        if p["port_id"] in twin_port and (p.get("attachments") or p["port_id"] in prim_port_refs):
            twin_port.pop(p["port_id"])   # a real port that a twin also touches

    # -- ports ----------------------------------------------------------------
    port_plane: Dict[Any, str] = {}
    for p in ports:
        dr.order["ports"].append(p["port_id"])
        if p["port_id"] in twin_port:
            continue                       # becomes a sector view below
        plid = f"port{p['port_id']}"
        port_plane[p["port_id"]] = plid
        monitored = bool(p.get("monitored", True))
        pl = Plane(id=plid, label=p.get("label", ""), kind="port" if monitored else "internal")
        doc.planes.append(pl)
        dr.ports[plid] = {k: v for k, v in p.items() if k not in PORT_PHYS}
        if not monitored:
            doc.blocks.append(Block(id=f"rterm{p['port_id']}", type="R",
                                    params={"R": "matched"}, terminals={"a": plid},
                                    extras={"legacy_loss_port": p["port_id"]}))
        for i, a in enumerate(p.get("attachments", [])):
            aid = f"{plid}.a{i}"
            extra = {k: v for k, v in a.items()
                     if k not in ("node_id", "rate", "sign") + ATT_STYLE}
            doc.attachments.append(Attachment(
                id=aid, mode=_mid(a["node_id"]), plane=plid, rate=float(a["rate"]),
                phase_deg=0.0 if a.get("sign", 1) >= 0 else 180.0, extras=extra))
            sty = {k: a[k] for k in ATT_STYLE if k in a}
            if sty:
                dr.attachments[aid] = sty

    # -- primary lines --------------------------------------------------------
    block_end_plane: Dict[str, Dict[str, str]] = {}
    for l in lines:
        dr.order["lines"].append(l["line_id"])
    for l in primaries:
        bid = f"line{l['line_id']}"
        blk = Block(id=bid, type="line", label=l.get("label", ""))
        blk.params = {k: l[k] for k in LINE_PARAMS if k in l}
        known = set(LINE_STYLE) | set(LINE_PARAMS) | {
            "label", "ends", "f_max", "Z0_port", "load", "pump", "conj", "twin_of", "port_end"}
        blk.extras = {k: v for k, v in l.items() if k not in known}
        blk.extras["port_end"] = l.get("port_end")
        if l.get("conj"):
            blk.extras["conj"] = l["conj"]
        dr.blocks[bid] = {k: l[k] for k in LINE_STYLE if k in l}
        order = {}
        planes_at = {}
        for e in ENDS:
            conns = end_conns(l, e)
            pports = [c["port_id"] for c in conns if c.get("kind") == "port"]
            if len(pports) > 1:
                raise MigrationError(f"line {blk.label!r} end {e}: {len(pports)} ports on one end")
            if pports:
                if pports[0] not in port_plane:
                    raise MigrationError(f"line {blk.label!r} end {e}: unknown port {pports[0]}")
                plid = port_plane[pports[0]]
            else:
                plid = f"{bid}.{e}"
                doc.planes.append(Plane(id=plid, label=f"{blk.label}.{e}", kind="internal"))
            planes_at[e] = plid
            blk.terminals[e] = plid
            order[e] = []
            coupling = (l.get("end_coupling") or {}).get(e, "capacitive")
            for i, c in enumerate(conns):
                if c.get("kind") == "port":
                    order[e].append(["port", c["port_id"]])
                    continue
                aid = f"{bid}.{e}.t{i}"
                doc.attachments.append(Attachment(
                    id=aid, mode=_mid(c["node_id"]), plane=plid, rate=float(c["rate"]),
                    phase_deg=0.0 if c.get("sign", 1) >= 0 else 180.0,
                    element="C" if coupling == "capacitive" else "L",
                    legacy_anchor={"n_ref": c.get("n_ref")},
                    extras={k: v for k, v in c.items()
                            if k not in ("kind", "node_id", "rate", "sign", "n_ref")}))
                order[e].append(["tap", aid])
        dr.blocks[bid]["_ends_order"] = order
        block_end_plane[bid] = planes_at

        # Z0 lives on the port plane; disagreeing / port-less lines keep an override
        z0 = l.get("Z0_port")
        port_terms = [planes_at[e] for e in ENDS if planes_at[e] in port_plane.values()]
        if port_terms:
            pl = next(p for p in doc.planes if p.id == port_terms[0])
            if pl.Z0 is None:
                pl.Z0 = z0
            elif pl.Z0 != z0:
                blk.extras["Z0_port"] = z0
        elif "Z0_port" in l:
            blk.extras["Z0_port"] = z0

        if "f_max" in l:
            doc.solve.kept_poles[bid] = {"f_max": l["f_max"]}
        load = l.get("load")
        if load:
            ltype = {"inductive": "L", "capacitive": "C"}.get(load.get("type"), load.get("type"))
            doc.blocks.append(Block(
                id=f"{bid}.load", type=ltype, params={"f_Z": load.get("f_Z")},
                terminals={"a": planes_at[load["end"]]},
                extras={"load_of": bid, **{k: v for k, v in load.items()
                                           if k not in ("end", "type", "f_Z")}}))
        elif "load" in l:
            blk.extras["load"] = load
        pump = l.get("pump")
        if pump:
            pe = pump["end"]
            doc.pumped.append(Pumped(
                id=f"{bid}.pump", kind="element", tone=tone_for(pump["f_p"]),
                phase=pump.get("phase"), plane=planes_at[pe],
                block=(f"{bid}.load" if load and load.get("end") == pe else None),
                param="1/L" if pump.get("coupling", "inductive") == "inductive" else "C",
                legacy_anchor={"line": bid, "end": pe, "rate": pump.get("rate"),
                               "n_ref": pump.get("n_ref"), "coupling": pump.get("coupling")},
                extras={k: v for k, v in pump.items()
                        if k not in ("end", "f_p", "rate", "phase", "n_ref", "coupling", "twin_id")}))
        elif "pump" in l:
            blk.extras["pump"] = pump
        doc.blocks.append(blk)

    # -- twins -> sector views ------------------------------------------------
    for t in twins:
        prim = by_lid[t["twin_of"]]
        bid = f"line{prim['line_id']}"
        glyph = {k: v for k, v in t.items()
                 if not (k in TWIN_SYNC and k in prim and prim[k] == v)}
        dr.sector_views.append(SectorView(of=bid, sector=-1, glyph=glyph))
        for e in ENDS:
            for c in end_conns(t, e):
                if c.get("kind") == "port" and c["port_id"] in twin_port:
                    p = next(pp for pp in ports if pp["port_id"] == c["port_id"])
                    dr.sector_views.append(SectorView(
                        of=block_end_plane[bid][e], sector=-1, glyph=copy.deepcopy(p)))

    # -- scattering section -----------------------------------------------------
    sc = d.get("scattering")
    if sc is not None:
        fr = sc.get("frequency")
        if fr:
            if "center" in fr:
                c, s_ = fr["center"], fr["span"]
                extra = {k: v for k, v in fr.items() if k not in ("center", "span", "points")}
            else:      # oldest files: start/stop -> center/span, as the GUI loader does
                c, s_ = (fr["start"] + fr["stop"]) / 2, fr["stop"] - fr["start"]
                extra = {k: v for k, v in fr.items() if k not in ("start", "stop", "points")}
            c, s_, n = quantize_sweep(c, s_, fr["points"])          # decision Q2
            doc.sweep = Sweep(center=c, span=s_, points=n, extras=extra)
        dr.sparams_plot = sc.get("sparams_plot")
        if "injection_node_id" in sc:                               # decision Q1
            root = sc["injection_node_id"]
            doc.solve.root = None if root is None else _mid(root)
        else:
            doc.solve.extras["_no_root_key"] = True
        if sc.get("tail_closure") is not None:                      # decision Q3
            doc.solve.tail_closure = bool(sc["tail_closure"])
        doc.solve.legacy_frames = {k: v for k, v in sc.items() if k not in SCATTER_KNOWN}
    return fill_depths(snap_document(doc))      # decisions Q2 (option A), D4


# ---------------------------------------------------------------------------
# 4.0 -> 2.0 / 3.0 (today's GUI serializer layout)
# ---------------------------------------------------------------------------

def to_legacy(doc: Document) -> Dict[str, Any]:
    doc = copy.deepcopy(doc)
    dr = doc.drawing
    modes = doc.by_id("modes")
    planes = doc.by_id("planes")
    tones = {t.id: t.f for t in doc.tones}
    nid = {mid: dr.nodes[mid]["node_id"] for mid in dr.nodes}

    out: Dict[str, Any] = {}
    out["format"] = "pgraph"
    meta = dict(doc.meta)
    migrated = meta.pop("migrated_from", None)
    out["metadata"] = meta
    out["view"] = dr.view

    # nodes
    bext = {a.mode: a for a in doc.attachments if a.id.startswith("bext")}
    nodes_by_legacy = {}
    for m in doc.modes:
        n = dict(dr.nodes.get(m.id, {"node_id": m.id}))
        n["label"] = m.label
        if not m.extras.get("_conj_absent"):
            n["conj"] = m.conj
        if m.freq is not None:
            n["freq"] = m.freq
        if m.B_int is not None:
            n["B_int"] = m.B_int
        if m.id in bext:
            n["B_ext"] = bext[m.id].rate
        n.update({k: v for k, v in m.extras.items() if not k.startswith("_")})
        nodes_by_legacy[n["node_id"]] = n
    out["nodes"] = [nodes_by_legacy[i] for i in dr.order.get("nodes", list(nodes_by_legacy))]

    # edges
    phys = {o.id: o for o in doc.couplings}
    phys.update({p.id: p for p in doc.pumped if p.kind == "coupling"})
    edges = []
    for eid in dr.order.get("edges", list(dr.edges)):
        sty = dict(dr.edges[eid])
        ends = sty.pop("_ends", None)
        o = phys.get(eid)
        a, b = (o.a, o.b) if o is not None else ends
        e = dict(sty)
        e["from_node_id"], e["to_node_id"] = nid[a], nid[b]
        la, lb = modes[a].label, modes[b].label
        e["from_to"] = f"{la} (self-loop)" if e.get("is_self_loop") else f"{la} <-> {lb}"
        if isinstance(o, Pumped):
            e["f_p"] = tones[o.tone]
        if o is not None:
            if o.rate is not None:
                e["rate"] = o.rate
            if o.phase is not None:
                e["phase"] = o.phase
            e.update(o.extras)
        edges.append(e)
    out["edges"] = edges
    out["code_properties"] = doc.code

    # ports (real planes and twin sector-view glyphs)
    legacy_ports = {}
    for pl in doc.planes:
        if pl.id not in dr.ports:
            continue
        p = dict(dr.ports[pl.id])
        p["label"] = pl.label
        p["monitored"] = pl.kind == "port"
        atts = []
        for a in doc.attachments:
            if a.plane == pl.id and a.element is None and not a.id.startswith("bext"):
                ad = {"node_id": nid[a.mode], "rate": a.rate,
                      "sign": 1 if a.phase_deg == 0.0 else -1}
                ad.update(dr.attachments.get(a.id, {}))
                ad.update(a.extras)
                atts.append(ad)
        p["attachments"] = atts
        legacy_ports[p["port_id"]] = p
    for sv in dr.sector_views:
        if "port_id" in sv.glyph:
            legacy_ports[sv.glyph["port_id"]] = dict(sv.glyph)

    # lines
    legacy_lines = {}
    loads = {b.extras.get("load_of"): b for b in doc.blocks if "load_of" in b.extras}
    pumps = {p.legacy_anchor["line"]: p for p in doc.pumped if p.kind == "element"}
    att_by_id = doc.by_id("attachments")
    twin_of_block = {sv.of: sv for sv in dr.sector_views if "line_id" in sv.glyph}
    for blk in doc.blocks:
        if blk.type != "line":
            continue
        sty = dict(dr.blocks[blk.id])
        order = sty.pop("_ends_order")
        l = dict(sty)
        l["label"] = blk.label
        l.update(blk.params)
        if blk.id in doc.solve.kept_poles:
            l["f_max"] = doc.solve.kept_poles[blk.id]["f_max"]
        ends = {}
        for e in ENDS:
            conns = []
            for kind, ref in order[e]:
                if kind == "port":
                    conns.append({"kind": "port", "port_id": ref})
                else:
                    a = att_by_id[ref]
                    c = {"kind": "node", "node_id": nid[a.mode], "rate": a.rate,
                         "sign": 1 if a.phase_deg == 0.0 else -1,
                         "n_ref": a.legacy_anchor.get("n_ref")}
                    c.update(a.extras)
                    conns.append(c)
            ends[e] = conns
        l["ends"] = ends
        z0 = None
        for e in ENDS:
            pl = planes[blk.terminals[e]]
            if pl.id in dr.ports and pl.Z0 is not None:
                z0 = pl.Z0
                break
        if z0 is not None:
            l["Z0_port"] = z0
        ld = loads.get(blk.id)
        if ld is not None:
            end = next(e for e in ENDS if blk.terminals[e] == ld.terminals["a"])
            l["load"] = {"end": end, "type": {"L": "inductive", "C": "capacitive"}.get(ld.type, ld.type),
                         "f_Z": ld.params["f_Z"],
                         **{k: v for k, v in ld.extras.items() if k != "load_of"}}
        pu = pumps.get(blk.id)
        if pu is not None:
            an = pu.legacy_anchor
            l["pump"] = {"end": an["end"], "f_p": tones[pu.tone], "rate": legacy_rate(doc, pu),
                         "phase": pu.phase, "n_ref": an["n_ref"], "coupling": an["coupling"],
                         **pu.extras}
            if blk.id in twin_of_block:
                l["pump"]["twin_id"] = twin_of_block[blk.id].glyph["line_id"]
        l["conj"] = False
        l["twin_of"] = None
        l.update(blk.extras)
        legacy_lines[l["line_id"]] = l
    for sv in dr.sector_views:
        if "line_id" in sv.glyph:
            prim = legacy_lines[next(dr.blocks[b]["line_id"] for b in dr.blocks if b == sv.of)]
            t = {k: copy.deepcopy(prim[k]) for k in TWIN_SYNC if k in prim}
            t.update(copy.deepcopy(sv.glyph))
            legacy_lines[t["line_id"]] = t

    if legacy_ports:
        out["ports"] = [legacy_ports[i] for i in dr.order.get("ports", list(legacy_ports))]
    if legacy_lines:
        out["line_resonators"] = [legacy_lines[i] for i in dr.order.get("lines", list(legacy_lines))]

    # scattering
    sv = doc.solve
    if (sv.legacy_frames is not None or doc.sweep is not None
            or sv.root is not None or sv.tail_closure is not None):
        sc = dict(sv.legacy_frames or {})
        if not sv.extras.get("_no_root_key", False):
            sc["injection_node_id"] = legacy_node_id(sv.root)
        if sv.tail_closure is not None:
            sc["tail_closure"] = bool(sv.tail_closure)
        if doc.sweep is not None:
            c, s_, n = quantize_sweep(doc.sweep.center, doc.sweep.span, doc.sweep.points)
            sc["frequency"] = {"center": c, "span": s_, "points": n, **doc.sweep.extras}
        if dr.sparams_plot is not None:
            sc["sparams_plot"] = dr.sparams_plot
        out["scattering"] = sc

    extras = dict(doc.extras)
    if not extras.pop("_notes_absent", False):
        out["notes"] = doc.notes
    out.update(extras)
    out["version"] = migrated or ("3.0" if (legacy_ports or legacy_lines) else "2.0")
    return out
