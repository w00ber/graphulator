"""Make external command-line tools discoverable to the bundled macOS app.

A GUI app launched from Finder (double-clicking the ``.app`` icon) inherits
only launchd's minimal ``PATH`` -- ``/usr/bin:/bin:/usr/sbin:/sbin`` -- which
omits the directories a login shell picks up via ``/etc/paths.d`` (notably
``/Library/TeX/texbin``, where MacTeX's ``latex``/``dvipng`` live, and the
Homebrew prefixes where Ghostscript lives). As a result, enabling LaTeX mode
(``text.usetex=True``) makes matplotlib shell out to ``latex``, fail to find
it, and silently fall back to the built-in mathtext (serif) renderer -- but
only when the app was double-clicked, not when launched via ``open`` from a
terminal (which inherits the shell's fuller ``PATH``).

Prepending the standard install locations at startup makes LaTeX mode behave
the same however the app is launched. This is a no-op off macOS.
"""

from __future__ import annotations

import os
import sys

# Common macOS locations for latex / dvipng / gs that are absent from
# launchd's default PATH but present for a login shell.
_MAC_TOOL_DIRS = (
    "/Library/TeX/texbin",  # MacTeX / BasicTeX (canonical, via /etc/paths.d/TeX)
    "/usr/texbin",          # older MacTeX layout
    "/opt/homebrew/bin",    # Homebrew (Apple Silicon) -- also Ghostscript
    "/usr/local/bin",       # Homebrew (Intel) / Ghostscript
    "/opt/local/bin",       # MacPorts
)


def ensure_external_tools_on_path() -> None:
    """Prepend known macOS tool directories to ``os.environ['PATH']``.

    Only directories that exist and are not already on ``PATH`` are added, so
    the result stays free of duplicates and phantom entries. No-op unless
    running on macOS.
    """
    if sys.platform != "darwin":
        return

    path = os.environ.get("PATH", "")
    entries = path.split(os.pathsep) if path else []
    present = set(entries)
    missing = [d for d in _MAC_TOOL_DIRS if d not in present and os.path.isdir(d)]
    if missing:
        os.environ["PATH"] = os.pathsep.join(missing + entries)
