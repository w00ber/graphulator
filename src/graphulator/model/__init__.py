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

import json
from pathlib import Path
from typing import Any, Dict, Union

from .migrate import MigrationError, from_legacy, to_legacy
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
           "Sweep", "Tone", "from_dict", "from_legacy", "load", "save", "to_legacy",
           "validate"]


def from_dict(d: Dict[str, Any]) -> Document:
    """Any supported pgraph dict -> Document."""
    if str(d.get("version")) == VERSION:
        return Document.from_dict(d)
    return from_legacy(d)


def load(path: Union[str, Path]) -> Document:
    with open(path, encoding="utf-8") as fh:
        return from_dict(json.load(fh))


def save(doc: Document, path: Union[str, Path]) -> None:
    d = doc.to_dict()
    d["version"] = VERSION
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=2)
