"""Layer 0: Qt-free document model (docs/design/layer0_document_model.md).

    doc = load(path)          # accepts pgraph 2.0 / 3.0 / 4.0
    save(doc, path)           # always writes 4.0
    issues = validate(doc)
    legacy = to_legacy(doc)   # the 2.0/3.0 dict today's GUI reads

    from graphulator.model.legacy_job import compile_jobs, compute_job
    results = [compute_job(j) for j in compile_jobs(doc)]   # = the GUI's Show S
(legacy_job is not imported here: it pulls in the numerics, the schema does not.)
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, Union

from .migrate import MigrationError, from_legacy, to_legacy
from .pump_depth import fill_depths
from .quantize import quantize_sweep
from .snap import PRECISION, snap_document
from .schema import (
    VERSION,
    Attachment,
    Block,
    Coupling,
    Document,
    Drawing,
    Mode,
    Plane,
    Pumped,
    SectorView,
    SolveSettings,
    Sweep,
    Tone,
)
from .validate import Issue, validate

__all__ = ["Attachment", "Block", "Coupling", "Document", "Drawing", "Issue",
           "MigrationError", "Mode", "Plane", "Pumped", "SectorView", "SolveSettings",
           "PRECISION", "Sweep", "Tone", "VERSION", "from_dict", "from_legacy", "load", "save",
           "snap_document", "to_file_dict", "to_legacy",
           "validate"]


def from_dict(d: Dict[str, Any]) -> Document:
    """Any supported pgraph dict -> Document."""
    if str(d.get("version")) == VERSION:
        return fill_depths(snap_document(Document.from_dict(d)))   # decisions Q2, D4
    return from_legacy(d)                               # snaps too


def load(path: Union[str, Path]) -> Document:
    with open(path, encoding="utf-8") as fh:
        return from_dict(json.load(fh))


def to_file_dict(doc: Document) -> Dict[str, Any]:
    """`doc` as the JSON dict a 4.0 file holds. User-entered numbers are
    stored quantized to their widget's precision (decision Q2); `doc` itself
    is not modified."""
    d = snap_document(copy.deepcopy(doc)).to_dict()
    d["version"] = VERSION
    if d.get("sweep") is not None:
        sw = d["sweep"]
        sw["center"], sw["span"], sw["points"] = quantize_sweep(sw["center"], sw["span"],
                                                                sw["points"])
    return d


def save(doc: Document, path: Union[str, Path]) -> None:
    """Write `doc` as a 4.0 file (see to_file_dict)."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(to_file_dict(doc), fh, indent=2)
