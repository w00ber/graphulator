"""Resource path resolution that works in dev, pip-installed, and frozen modes.

All bundled assets (icons, fonts, examples, ...) live next to the
``graphulator`` package on disk. ``Path(__file__).parent`` resolves correctly
in both source checkouts and ``pip install``-ed packages, and PyInstaller
rewrites ``__file__`` to point inside the extracted bundle when running from
a frozen build (provided the data is included via ``--add-data`` /
``datas=`` in the spec file). For PyInstaller onefile builds, ``sys._MEIPASS``
points at the temporary extraction directory; we prefer it when present so
the helper keeps working even if ``__file__`` resolution differs across
freezer backends.

Use this helper instead of computing paths manually so that adding standalone
distribution support later is a one-place change.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parent


def resource_path(*parts: str) -> Path:
    """Return an absolute path to a bundled resource inside the package.

    Pass path components relative to the ``graphulator/`` package directory,
    e.g. ``resource_path("assets")`` or
    ``resource_path("assets", "graphulator_ICON.png")``.

    The returned path is not guaranteed to exist — callers should check
    ``.is_file()`` / ``.is_dir()`` as appropriate.
    """
    base = Path(getattr(sys, "_MEIPASS", _PACKAGE_ROOT))
    return base.joinpath(*parts)
