"""Layer 0 document model: dataclasses only (no Qt, no matplotlib, no numpy).

Design note: docs/design/layer0_document_model.md. The rule is that the
document stores PHYSICAL objects, never their expansion: a line is one Block,
a pump is one Pumped, a conjugate twin is a drawing (``Drawing.sector_views``),
and how many poles/sectors to keep are SolveSettings.

Every object carries ``extras``: keys this build does not model are kept there
and written back, so nothing is lost when an older or newer file passes
through. ``to_dict``/``from_dict`` are plain JSON-ready dicts.

Deviations from the design note (recorded there):
- Attachment stores the legacy ``rate`` (and phase) instead of ``weight =
  sqrt(rate)``, so a migrated file round-trips bit-exactly; ``weight`` is a
  derived property.
- Sweep keeps ``center/span/points`` as the GUI's spin boxes hold them,
  quantized to their display precision (decision Q2; start/stop derived).
- Element pumps store their depth (decision D4, model/pump_depth.py) and
  keep the legacy ``{rate, n_ref}`` anchor as provenance; export recomputes
  the rate from the depth.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, Dict, List, Optional, Union, get_args, get_origin, get_type_hints

FORMAT = "pgraph"
VERSION = "4.0"


# ---------------------------------------------------------------------------
# generic dict <-> dataclass
# ---------------------------------------------------------------------------

def _to_plain(v):
    if is_dataclass(v):
        return {f.name: _to_plain(getattr(v, f.name)) for f in fields(v)}
    if isinstance(v, dict):
        return {k: _to_plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_to_plain(x) for x in v]
    return v


def _from_plain(tp, v):
    if v is None:
        return None
    origin = get_origin(tp)
    if origin is Union:
        args = [a for a in get_args(tp) if a is not type(None)]
        for a in args:
            if is_dataclass(a) and isinstance(v, dict):
                return _from_plain(a, v)
            if get_origin(a) in (list, List) and isinstance(v, list):
                return _from_plain(a, v)
        return v
    if origin in (list, List):
        (a,) = get_args(tp)
        return [_from_plain(a, x) for x in v]
    if origin in (dict, Dict):
        _, a = get_args(tp)
        return {k: _from_plain(a, x) for k, x in v.items()}
    if is_dataclass(tp):
        hints = get_type_hints(tp)
        names = {f.name for f in fields(tp)}
        kw = {k: _from_plain(hints[k], x) for k, x in v.items() if k in names}
        unknown = {k: x for k, x in v.items() if k not in names}
        obj = tp(**kw)
        if unknown and hasattr(obj, "extras"):
            obj.extras.update(unknown)
        return obj
    return v


class _Base:
    def to_dict(self) -> Dict[str, Any]:
        return _to_plain(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]):
        return _from_plain(cls, d)


# ---------------------------------------------------------------------------
# physics
# ---------------------------------------------------------------------------

@dataclass
class Tone(_Base):
    """A pump tone. Sector index m counts multiples of f (vector m when >1 tone)."""
    id: str
    f: float
    label: str = ""
    extras: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Plane(_Base):
    """A terminal pair (single-ended, ground implicit).

    kind 'port' is a scattering channel and carries its own Z0 (None for a
    port that only serves lumped CMT attachments). 'internal' is any other
    circuit node (a line end, a loss termination)."""
    id: str
    label: str
    kind: str = "port"
    Z0: Optional[float] = None
    extras: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Block(_Base):
    """One LTI element. type in {'line','L','C','R', ...}; terminals map
    terminal name -> plane id ('b' omitted = ground)."""
    id: str
    type: str
    params: Dict[str, Any] = field(default_factory=dict)
    terminals: Dict[str, str] = field(default_factory=dict)
    label: str = ""
    extras: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Mode(_Base):
    """A dynamical degree of freedom (a row of M_iso)."""
    id: str
    label: str
    freq: Optional[float] = None
    B_int: Optional[float] = None
    conj: bool = False
    origin: Dict[str, Any] = field(default_factory=lambda: {"kind": "lumped"})
    extras: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Coupling(_Base):
    """Static mode-mode coupling (M_iso off-diagonal). rate None = unassigned."""
    id: str
    a: str
    b: str
    rate: Optional[float] = None
    phase: Optional[float] = None
    extras: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Attachment(_Base):
    """A K entry: mode <-> plane.

    element None: direct CMT external coupling (legacy port attachment or
    B_ext). element 'C'/'L': a tap through a fixed capacitor / mutual onto a
    line-end plane; its rate is anchored at harmonic legacy_anchor['n_ref']."""
    id: str
    mode: str
    plane: str
    rate: float
    phase_deg: float = 0.0
    element: Optional[str] = None
    legacy_anchor: Optional[Dict[str, Any]] = None
    extras: Dict[str, Any] = field(default_factory=dict)

    @property
    def weight(self) -> float:
        return math.sqrt(self.rate)


@dataclass
class Pumped(_Base):
    """A modulated thing. kind 'coupling': a parametric mode-mode edge (a, b,
    rate, phase). kind 'element': a modulated element at a plane (param '1/L'
    or 'C', on top of an optional static block) with depth delta:
    1/L(t) = 1/L0 + delta cos(omega_p t + phase), omega = 2 pi f in the
    document's units. legacy_anchor {line, end, rate, n_ref, coupling} is the
    legacy line pump it came from (provenance; decision D4)."""
    id: str
    kind: str
    tone: str
    phase: Optional[float] = None
    a: Optional[str] = None
    b: Optional[str] = None
    rate: Optional[float] = None
    plane: Optional[str] = None
    block: Optional[str] = None
    param: Optional[str] = None
    depth: Optional[float] = None
    legacy_anchor: Optional[Dict[str, Any]] = None
    extras: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Sweep(_Base):
    center: float
    span: float
    points: int
    extras: Dict[str, Any] = field(default_factory=dict)

    @property
    def start(self) -> float:
        return self.center - self.span / 2

    @property
    def stop(self) -> float:
        return self.center + self.span / 2


@dataclass
class SolveSettings(_Base):
    """sectors: 'auto' (grow symmetrically from {-1..0} until max-sweep |dS|
    relative to (G-1) < sector_tol, capped at sector_max sectors) or an
    explicit [m_lo, m_hi]. kept_poles: block id -> {'f_max': f} | [n, ...].
    tail_closure: the legacy comb engine's tail closure (None = app default,
    on); M_super ignores it (a line's non-promoted part is exact). root: the
    mode id the sweep is injected at (the legacy injection node, which fixes
    the lumped sector frame); used when it is a port mode of the shown
    component, else the first port mode is (decision Q1). legacy_frames: the
    spanning-tree / constraint-group state the legacy engine uses for lumped
    sectors (HANDOFF sec. 6), kept verbatim."""
    sectors: Union[str, List[int]] = "auto"
    sector_tol: float = 1e-3
    sector_max: int = 16
    kept_poles: Dict[str, Any] = field(default_factory=dict)
    tail_closure: Optional[bool] = None
    root: Optional[str] = None
    legacy_frames: Optional[Dict[str, Any]] = None
    extras: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SectorView(_Base):
    """A drawing of a block or plane in a non-zero sector (e.g. the conjugate
    twin TL* of a pumped line = block in sector -1). Pure drawing: 'glyph'
    holds the legacy glyph dict (position, style, legacy ids, end wiring)."""
    of: str
    sector: int
    glyph: Dict[str, Any] = field(default_factory=dict)
    extras: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Drawing(_Base):
    """Everything visual, keyed by physics ids. Style dicts are today's GUI
    keys verbatim, so the GUI round-trips unchanged."""
    view: Dict[str, Any] = field(default_factory=dict)
    nodes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    edges: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    ports: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    blocks: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    attachments: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    sector_views: List[SectorView] = field(default_factory=list)
    sparams_plot: Optional[Dict[str, Any]] = None
    order: Dict[str, List[Any]] = field(default_factory=dict)
    extras: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Document(_Base):
    format: str = FORMAT
    version: str = VERSION
    meta: Dict[str, Any] = field(default_factory=dict)
    units: Dict[str, str] = field(default_factory=lambda: {"frequency": "GHz", "impedance": "ohm"})
    sweep: Optional[Sweep] = None
    tones: List[Tone] = field(default_factory=list)
    planes: List[Plane] = field(default_factory=list)
    blocks: List[Block] = field(default_factory=list)
    modes: List[Mode] = field(default_factory=list)
    couplings: List[Coupling] = field(default_factory=list)
    attachments: List[Attachment] = field(default_factory=list)
    pumped: List[Pumped] = field(default_factory=list)
    solve: SolveSettings = field(default_factory=SolveSettings)
    drawing: Drawing = field(default_factory=Drawing)
    notes: str = ""
    code: Dict[str, Any] = field(default_factory=dict)
    extras: Dict[str, Any] = field(default_factory=dict)

    # -- lookups ------------------------------------------------------------
    def by_id(self, kind: str) -> Dict[str, Any]:
        return {o.id: o for o in getattr(self, kind)}
