#!/usr/bin/env python3
"""Bump the project version.

Reads the current version from ``pyproject.toml``, increments the requested
semver component, and writes the new version back to both ``pyproject.toml``
and ``src/graphulator/__init__.py``. Also prepends a new dated stub to
``CHANGELOG.md`` so future release notes have a place to land.

Usage:
    python scripts/bump_version.py {patch|minor|major}

Prints the new version on stdout so the GitHub workflow can capture it.
"""

from __future__ import annotations

import datetime as _dt
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
INIT = ROOT / "src" / "graphulator" / "__init__.py"
CHANGELOG = ROOT / "CHANGELOG.md"


def _current_version() -> tuple[int, int, int]:
    with PYPROJECT.open("rb") as f:
        raw = tomllib.load(f)["project"]["version"]
    parts = raw.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise SystemExit(f"pyproject.toml version is not semver: {raw!r}")
    major, minor, patch = (int(p) for p in parts)
    return major, minor, patch


def _bumped(current: tuple[int, int, int], level: str) -> tuple[int, int, int]:
    major, minor, patch = current
    if level == "major":
        return major + 1, 0, 0
    if level == "minor":
        return major, minor + 1, 0
    if level == "patch":
        return major, minor, patch + 1
    raise SystemExit(f"Unknown bump level: {level!r} (expected patch/minor/major)")


def _write_pyproject(new: str) -> None:
    text = PYPROJECT.read_text()
    updated, n = re.subn(
        r'^version\s*=\s*"[^"]+"',
        f'version = "{new}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if n != 1:
        raise SystemExit("could not locate a `version = \"...\"` line in pyproject.toml")
    PYPROJECT.write_text(updated)


def _write_init(new: str) -> None:
    text = INIT.read_text()
    updated, n = re.subn(
        r'^__version__\s*=\s*"[^"]+"',
        f'__version__ = "{new}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if n != 1:
        raise SystemExit("could not locate `__version__` in src/graphulator/__init__.py")
    INIT.write_text(updated)


def _prepend_changelog(new: str) -> None:
    today = _dt.date.today().isoformat()
    stub = f"## [{new}] - {today}\n### Changed\n- _TODO: describe changes._\n\n"
    if not CHANGELOG.exists():
        CHANGELOG.write_text(f"# Changelog\n\n{stub}")
        return
    text = CHANGELOG.read_text()
    # Insert after the first blank line so "# Changelog" header stays on top.
    marker = "\n\n"
    idx = text.find(marker)
    if idx == -1:
        CHANGELOG.write_text(text + "\n\n" + stub)
    else:
        head = text[: idx + len(marker)]
        tail = text[idx + len(marker) :]
        CHANGELOG.write_text(head + stub + tail)


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in {"patch", "minor", "major"}:
        print("usage: bump_version.py {patch|minor|major}", file=sys.stderr)
        return 2
    level = argv[1]
    current = _current_version()
    new_tuple = _bumped(current, level)
    new = ".".join(str(p) for p in new_tuple)
    _write_pyproject(new)
    _write_init(new)
    _prepend_changelog(new)
    print(new)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
