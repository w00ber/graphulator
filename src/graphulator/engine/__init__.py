"""The M_super engine (Qt-free). Step 4, milestone 1: lumped documents,
solved exactly as drawn (docs/design/step4_msuper_m1.md).

    from graphulator import engine
    results = engine.solve(doc)          # one ComponentResult per component
    systems = engine.compile_document(doc)

The legacy engine (model/legacy_job) is its regression oracle.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from ..model.schema import Document
from ..model.validate import Issue
from .kernel import M_stack, scattering
from .msuper import Channel, MSuper, NotLumpedError, Row, compile_document

__all__ = ["ComponentResult", "Channel", "MSuper", "NotLumpedError", "Row",
           "M_stack", "compile_document", "scattering", "solve"]


@dataclass
class ComponentResult:
    index: int
    S: Optional[np.ndarray]          # None when parameters are missing
    ports: List[str]                 # plane ids, in S order
    port_labels: List[str]
    root: str
    msuper: MSuper
    issues: List[Issue] = field(default_factory=list)


def solve(doc: Document, f=None) -> List[ComponentResult]:
    """S per component over the grid f (default: the document's sweep)."""
    if f is None:
        from ..model.legacy_job import sweep_grid
        f = sweep_grid(doc)
    out = []
    for ms in compile_document(doc):
        S = scattering(ms, f) if ms.complete else None
        out.append(ComponentResult(ms.index, S, [c.plane for c in ms.ports],
                                   [c.label for c in ms.ports], ms.root, ms, ms.issues))
    return out
