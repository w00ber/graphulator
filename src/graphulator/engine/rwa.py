"""How much the rotating-wave approximation costs on a physical document.

The RWA is the deletion of each mode's -f image node (cmt_msuper_lectures
v38, sec. 3.6). The engine keeps the images by default on physical
documents (``solve.images``), which makes a parallel tank exact. This
module answers "would deleting them matter here?" two ways:

- **Measured.** Solve again with the images flipped and take
  max |S_with - S_without| over the sweep and every drawn channel. That is
  the cost of the RWA *in this window*: no linewidth, Q or rule of thumb in
  between (for one tank on a port it reproduces the 1/2Q_ext law of sec. 3.6
  over a window of +-10 linewidths).
- **Predicted, per tapped mode.** A tap's coupling capacitor pulls the bare
  tank f0 to the drawn f1 by d = f1 - f0. The image sits 2 f0 away and repels
  the dressed resonance by about d^2 / (2 f0) (level attraction with the
  image, sec. 3.7). That number explains *why* the measured cost is what it
  is; on a tapped tank the physical Q badly underestimates it (design note,
  "M2c as built").

The check runs only where there are CMT modes on a physical document;
lumped documents are RWA by construction (milestone 1).
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from ..model.schema import Document

#: |dS| above this is reported (warning with the RWA, info without).
RWA_TOL = 1e-2


@dataclass
class ModePull:
    mode: str
    label: str
    f_drawn: float
    f_bare: float

    @property
    def pull(self) -> float:
        return self.f_drawn - self.f_bare

    @property
    def image_shift(self) -> float:
        """The dressed resonance's move when the image is deleted, ~d^2/(2 f0)
        (towards lower frequency: the image repels it)."""
        return -self.pull ** 2 / (2.0 * self.f_bare)


@dataclass
class RWAReport:
    images: bool                    # what the shown solution used
    max_dS: float                   # max |S_images - S_rwa| over the sweep
    at_f: Optional[float]           # where
    trace: str                      # which channel pair (out <- in)
    modes: List[ModePull] = field(default_factory=list)
    unit: str = "GHz"

    @property
    def matters(self) -> bool:
        return self.max_dS > RWA_TOL

    def summary(self) -> str:
        where = f" ({self.trace} at f = {self.at_f:.6g})" if self.at_f is not None else ""
        sub = {"GHz": "MHz", "MHz": "kHz", "kHz": "Hz"}.get(self.unit)
        k = 1e3 if sub else 1.0
        u = sub or self.unit
        pulls = "; ".join(
            f"{m.label}: pull d = {m.pull * k:+.3g} {u}, predicted image shift "
            f"d\u00b2/2f0 = {m.image_shift * k:+.3g} {u}"
            for m in self.modes)
        pulls = f" [{pulls}]" if pulls else ""
        if self.images:
            return (f"RWA check: deleting the image poles would change S by up to "
                    f"{self.max_dS:.3g}{where}{pulls}")
        return (f"RWA in use (image poles deleted): S is off by up to "
                f"{self.max_dS:.3g}{where}{pulls}")


def _has_modes(doc: Document) -> bool:
    return bool(doc.modes) and any(a.mode for a in doc.attachments)


def mode_pulls(doc: Document) -> List[ModePull]:
    """Drawn vs bare frequency of every tapped mode (model/taps.py)."""
    from ..model.taps import TapError, resolve_taps
    try:
        rd, _, _ = resolve_taps(doc)
    except TapError:
        return []
    out = []
    for m in rd.modes:
        tr = m.extras.get("tap_resolved")
        if tr and m.freq:
            out.append(ModePull(m.id, m.label or m.id, float(tr["f_drawn"]), float(m.freq)))
    return out


def rwa_check(doc: Document, f, results) -> Optional[RWAReport]:
    """The RWA report for engine.solve(doc, f) -> results, or None when the
    document has no CMT modes on a physical network (nothing to delete)."""
    from .network import classify, solve_network
    if classify(doc) != "network" or not _has_modes(doc):
        return None
    shown = [r for r in results if getattr(r, "S_channels", None) is not None]
    if not shown:
        return None
    images = True if doc.solve.images is None else bool(doc.solve.images)
    other = copy.deepcopy(doc)
    other.solve.images = not images
    alt = {r.index: r for r in solve_network(other, f)}
    f = np.asarray(f, dtype=float)
    best, at, trace = 0.0, None, ""
    for r in shown:
        a = alt.get(r.index)
        if a is None or a.S_channels is None or a.S_channels.shape != r.S_channels.shape:
            continue
        d = np.abs(r.S_channels - a.S_channels)
        if not np.isfinite(d).any():
            continue
        k = np.unravel_index(np.nanargmax(d), d.shape)
        if d[k] > best:
            best = float(d[k])
            at = float(f[k[0]])
            trace = f"{r.channels[k[1]][2]} \N{LEFTWARDS ARROW} {r.channels[k[2]][2]}"
    return RWAReport(images=images, max_dS=best, at_f=at, trace=trace,
                     modes=mode_pulls(doc), unit=doc.units.get("frequency", "GHz"))
