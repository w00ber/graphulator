"""The M_super engine (Qt-free).

- Milestone 1 (docs/design/step4_msuper_m1.md): lumped documents, solved
  exactly as drawn; the legacy engine (model/legacy_job) is its oracle,
  bit for bit.
- Milestone 2a (docs/design/step4_msuper_m2.md): physical documents (lines,
  L/C/R blocks, ports, element pumps) as an exact network over a sector
  window (engine/network.py).

    from graphulator import engine
    results = engine.solve(doc)          # one result per component
    systems = engine.compile_document(doc)     # lumped only
    nets = engine.compile_network(doc)         # physical only
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from ..model.schema import Document
from ..model.validate import Issue
from .kernel import M_stack, scattering
from .msuper import Channel, MSuper, NotLumpedError, Row, compile_document
from .network import Network, NetworkResult, NotSupportedError, classify, compile_network, pump_depth, solve_network

__all__ = ["ComponentResult", "Channel", "MSuper", "Network", "NetworkResult",
           "NotLumpedError", "NotSupportedError", "Row", "M_stack", "classify",
           "compile_document", "compile_network", "pump_depth", "scattering",
           "solve", "solve_network"]


@dataclass
class ComponentResult:
    index: int
    S: Optional[np.ndarray]          # None when parameters are missing
    ports: List[str]                 # plane ids, in S order
    port_labels: List[str]
    root: str
    msuper: MSuper
    issues: List[Issue] = field(default_factory=list)


def solve(doc: Document, f=None):
    """S per component over the grid f (default: the document's sweep).

    Lumped documents give ComponentResult (milestone 1), physical ones
    NetworkResult (milestone 2a). Raises NotSupportedError for documents
    that need a later milestone (lumped modes with lines: 2b, taps: 2c)."""
    if classify(doc) == "network":
        return solve_network(doc, f)
    if f is None:
        from ..model.legacy_job import sweep_grid
        f = sweep_grid(doc)
    out = []
    for ms in compile_document(doc):
        S = scattering(ms, f) if ms.complete else None
        out.append(ComponentResult(ms.index, S, [c.plane for c in ms.ports],
                                   [c.label for c in ms.ports], ms.root, ms, ms.issues))
    return out
