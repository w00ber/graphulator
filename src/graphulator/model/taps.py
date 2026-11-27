"""Capacitive taps as circuit elements (step 4, milestone 2c; decisions of
27 Nov 2026 in docs/design/step4_msuper_m2.md, "M2c as built").

A legacy tap couples a lumped mode (a tank) to a line end through a fixed
coupling capacitor C_c, with a rate anchored at line harmonic n_ref. In the
M_super formulation the coupling capacitor is a circuit element in Sigma_0
and the tank attaches to its own node in the impedance (Foster I) form, with
the attachment rate fixed by the tank's own capacitance alone:

    gamma_d = 1 / (2 pi Z_ref C_d)                  (cyclic, document units)

``resolve_taps`` rewrites a document that way. For a mode with taps k:

- The mode as drawn (frequency f1) is the tank with every coupling
  capacitor taken to ground: C_sum = C_d + sum_k C_c,k and
  L_d = 1 / (w1^2 C_sum), w1 = 2 pi f1.
- Each tap's legacy rate is the coupling to line mode n_ref at resonance
  (the weak-coupling capacitance-matrix result, CMT-Theory
  better_derivation.md sec. 7.2):

      rate_k = w1 C_c,k u_k / (2 pi sqrt(C_sum C_n,k))

  with u_k, C_n,k the line's (loaded, stepped) mode amplitude at the tapped
  end and mode capacitance at n_ref. For one tap this is the M2c anchor
  gamma = rate^2 2 pi Z_ref C_n / u^2 of the design note.
- C_sum comes from, in order:
  1. a direct attachment of the mode to a plane (the legacy port coupling,
     rate gamma_p): that plane is the tank's node and C_d = 1/(2 pi Z_ref gamma_p).
     Then sqrt(C_sum) = (A + sqrt(A^2 + 4 C_d)) / 2 with A = sum_k a_k,
     C_c,k = a_k sqrt(C_sum);
  2. the mode's LC impedance Z_d = sqrt(L_d / C_sum) (``Mode.extras['Z_d']``,
     ohms), the impedance of the mode as drawn: C_sum = 1 / (w1 Z_d);
  3. otherwise the document is incomplete: an error asks for Z_d (decision
     Q5: nothing is guessed).
- The rewritten mode sits at the bare tank frequency f0 = 1/(2 pi sqrt(L_d C_d)),
  attached to its node with gamma_d; each tap becomes a C block of C_c,k
  between the node and the line end. A mode without a direct attachment
  gets a new internal plane ``<mode>.node``.

Capacitances are in the document's units (ohm and its frequency unit: nF
for GHz). A C block stores farads in ``params['C']``.

Inductive taps are refused: their exact form is derived but not checked.
"""
from __future__ import annotations

import copy
import math
from typing import Dict, List, Optional, Tuple

from .schema import Attachment, Block, Document, Plane
from .validate import Issue

FREQ_SCALE = {"Hz": 1.0, "kHz": 1e3, "MHz": 1e6, "GHz": 1e9, "THz": 1e12}


class TapError(ValueError):
    """A tap the engine cannot represent (inductive, or an ambiguous node)."""


def freq_scale(doc: Document) -> float:
    """Hz per document frequency unit (GHz -> 1e9)."""
    return FREQ_SCALE[doc.units.get("frequency", "GHz")]


def z_ref(doc: Document) -> float:
    return float(doc.units.get("z_ref", 50.0))


def tap_groups(doc: Document) -> Dict[str, List[Attachment]]:
    """mode id -> its tap attachments (element set)."""
    out: Dict[str, List[Attachment]] = {}
    for a in doc.attachments:
        if a.element is not None:
            out.setdefault(a.mode, []).append(a)
    return out


def _direct(doc: Document, mode: str) -> List[Attachment]:
    return [a for a in doc.attachments if a.mode == mode and a.element is None]


def _line_at(doc: Document, plane: str) -> Tuple[Block, str]:
    for b in doc.blocks:
        if b.type == "line":
            for end in ("x0", "xL"):
                if b.terminals.get(end) == plane:
                    return b, end
    raise TapError(f"tap onto plane {plane!r}: no line end there")


def tap_issues(doc: Document) -> List[Issue]:
    """Errors for taps whose mode impedance nothing fixes (decision Q5)."""
    out = []
    for mode, taps in tap_groups(doc).items():
        if _direct(doc, mode):
            continue
        m = doc.by_id("modes").get(mode)
        if m is None:
            continue
        zd = m.extras.get("Z_d")
        if not (isinstance(zd, (int, float)) and zd > 0):
            out.append(Issue(
                "error", f"modes/{mode}",
                f"mode {m.label or mode} is tapped onto a line through a coupling "
                "capacitor, and nothing fixes its LC mode impedance. Set Z_d = "
                "sqrt(L/C) of the mode as drawn (ohms); the coupling capacitor "
                "follows from Z_d and the tap rate."))
    return out


def resolve_taps(doc: Document) -> Tuple[Document, List[Issue], List[str]]:
    """(rewritten copy, issues, modes left incomplete). A document without
    taps comes back unchanged (the same object)."""
    groups = tap_groups(doc)
    if not groups:
        return doc, [], []
    from .pump_depth import _line_resonator
    out = copy.deepcopy(doc)
    modes = out.by_id("modes")
    planes = out.by_id("planes")
    Zr = z_ref(out)
    scale = freq_scale(out)
    issues: List[Issue] = []
    incomplete: List[str] = []
    taps_by_mode = tap_groups(out)
    for mode_id in groups:
        taps = taps_by_mode[mode_id]
        m = modes[mode_id]
        for a in taps:
            if a.element != "C":
                raise TapError(
                    f"tap {a.id}: inductive taps are not in milestone 2c (their "
                    "exact form is derived but not checked numerically)")
        if m.freq is None:
            incomplete.append(mode_id)
            continue
        w1 = 2 * math.pi * float(m.freq)
        # a_k: C_c,k = a_k sqrt(C_sum)
        a_k = []
        for a in taps:
            blk, end = _line_at(out, a.plane)
            res = _line_resonator(out, blk)
            n = int((a.legacy_anchor or {}).get("n_ref") or 1)
            u = float(res.mode_profile(n, end))
            Cn = float(res.mode_mass(n))
            if u == 0.0:
                raise TapError(f"tap {a.id}: line mode {n} has no amplitude at {end}")
            a_k.append(2 * math.pi * float(a.rate) * math.sqrt(Cn) / (w1 * abs(u)))
        A = sum(a_k)
        direct = [x for x in out.attachments if x.mode == mode_id and x.element is None]
        zd = m.extras.get("Z_d")
        if direct:
            if len(direct) > 1:
                raise TapError(
                    f"mode {mode_id}: tapped onto a line and attached directly to "
                    "more than one plane; which plane is the tank's node is ambiguous")
            node = direct[0].plane
            C_d = 1.0 / (2 * math.pi * Zr * float(direct[0].rate))
            sC = 0.5 * (A + math.sqrt(A * A + 4 * C_d))
            C_sum = sC * sC
            if isinstance(zd, (int, float)):
                issues.append(Issue(
                    "warning", f"modes/{mode_id}",
                    f"Z_d = {zd} ignored: the direct attachment {direct[0].id} "
                    "already fixes the tank capacitance"))
        elif isinstance(zd, (int, float)) and zd > 0:
            C_sum = 1.0 / (w1 * float(zd))
            C_d = C_sum - A * math.sqrt(C_sum)
            if not C_d > 0:
                raise TapError(
                    f"mode {mode_id}: Z_d = {zd} ohm is too high for its tap rates "
                    "(the coupling capacitors would exceed the tank capacitance)")
            node = f"{mode_id}.node"
            if node not in planes:
                pl = Plane(id=node, label=f"{m.label or mode_id} node", kind="internal")
                out.planes.append(pl)
                planes[node] = pl
        else:
            incomplete.append(mode_id)
            continue
        Cc = [ak * math.sqrt(C_sum) for ak in a_k]
        L_d = 1.0 / (w1 * w1 * C_sum)
        f0 = 1.0 / (2 * math.pi * math.sqrt(L_d * C_d))
        gamma_d = 1.0 / (2 * math.pi * Zr * C_d)
        m.extras["tap_resolved"] = {"f_drawn": m.freq, "C_d": C_d, "L_d": L_d,
                                    "C_c": dict(zip([a.id for a in taps], Cc))}
        m.freq = f0
        if direct:
            direct[0].rate = gamma_d
        else:
            out.attachments.append(Attachment(id=f"{mode_id}.node", mode=mode_id,
                                              plane=node, rate=gamma_d))
        for a, c in zip(taps, Cc):
            out.blocks.append(Block(id=f"{a.id}.Cc", type="C",
                                    params={"C": c / scale},
                                    terminals={"a": node, "b": a.plane},
                                    label="C_c", extras={"tap_of": a.id}))
        out.attachments = [x for x in out.attachments if x not in taps]
        issues.append(Issue(
            "info", f"modes/{mode_id}",
            f"taps of {m.label or mode_id} solved as coupling capacitors "
            + ", ".join(f"{c / scale * 1e15:.4g} fF" for c in Cc)
            + f"; tank C_d = {C_d / scale * 1e12:.4g} pF, bare frequency {f0:.6g}"))
    for mid in incomplete:
        issues += [i for i in tap_issues(doc) if i.path == f"modes/{mid}"]
    return out, issues, incomplete


def tank_of(doc: Document, mode: str) -> Optional[Dict[str, float]]:
    """The resolved tank (C_d, L_d, C_c by tap) of a tapped mode, or None."""
    d, _, _ = resolve_taps(doc)
    m = d.by_id("modes").get(mode)
    return None if m is None else m.extras.get("tap_resolved")
