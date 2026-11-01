#!/usr/bin/env python
"""Put one *variant* of the graph pasteboard on the clipboard, to find out
which flavour a picky vector editor's keyboard-paste path actually wants.

Background
----------
Some vector editors (VectorCraft is the known case) gate their **Cmd+V**
path on the pasteboard advertising a type they recognise as vector
artwork, while Edit > Paste and the context menu run a permissive
importer chain that happily takes ``com.adobe.pdf``.  Symptom: menu paste
works, Cmd+V does nothing.

Three candidate ingredients were identified from the sibling Diagrammer
app, which had the identical symptom and is now fixed: the modern
``writeObjects:`` API, a ``com.adobe.svg`` alias, and a
``public.utf8-plain-text`` flavour carrying the SVG source.  Diagrammer
added all three at once, so which one matters is unknown.  This script
separates them.

Unlike the first draft of this script, every variant here drives the
*shipping* code in :mod:`graphulator.clipboard_export` -- the variants
only flip its module constants and, for ``legacy``, swap in the old
``declareTypes:owner:`` writer.  So a variant that pastes is a
configuration that ships, not just one that works in this script.

Usage
-----
Run a variant, click into the target app, press Cmd+V, note whether
anything arrives::

    python scripts/pasteboard_variant.py legacy      # pre-fix behaviour
    python scripts/pasteboard_variant.py modern      # writeObjects:, UTIs only
    python scripts/pasteboard_variant.py alias       # + com.adobe.svg
    python scripts/pasteboard_variant.py mime        # + image/svg+xml  (ships)
    python scripts/pasteboard_variant.py text        # + utf8-plain-text
    python scripts/pasteboard_variant.py eps         # + encapsulated-postscript
    python scripts/pasteboard_variant.py everything  # all of the above
    python scripts/pasteboard_variant.py dump        # just dump the pasteboard
    python scripts/pasteboard_variant.py watch       # dump every copy as it happens

``legacy`` reproduces what shipped originally and **should fail**.  If it
pastes, the problem is elsewhere (a stale build, a different copy command,
app state) and the rest tell you nothing.

``modern`` and ``alias`` have both been tried against VectorCraft and both
failed.  ``mime`` is the one grounded in evidence rather than guesswork:
VectorCraft's binary names ``image/svg+xml``, ``application/pdf`` and
``application/postscript``, and never names ``public.svg-image`` or any
``com.adobe.illustrator.*`` type, so it reads the pasteboard by MIME name.
``mime`` is what the code ships today.

``text`` and ``eps`` remain as fallbacks.  ``everything`` is the "is it
*any* of these" probe.

``dump`` writes nothing; it prints whatever is on the pasteboard now, so
you can copy from another app and diff its flavours against ours.

``watch`` writes nothing either, and is what you want when comparing two
apps: it prints every new pasteboard as it appears, labelled with the app
that was frontmost.  ``dump`` loses the race if anything touches the
clipboard first -- copying the dump command out of a browser is enough --
and a dump full of ``org.chromium.*`` flavours is that race, not a result.

Needs PyObjC (``pip install pyobjc-framework-Cocoa``) for ``dump`` and
for ``legacy``; the shipping writers do not.
"""

from __future__ import annotations

import argparse
import sys

VARIANTS = ("legacy", "modern", "alias", "mime", "text", "eps",
            "everything", "dump", "watch")


def sample_figure():
    """A throwaway graph to copy."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0, 1, 2, 3], [0, 1, 4, 9], marker="o")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    return fig


EPS_UTI = "com.adobe.encapsulated-postscript"


def render_eps(fig):
    """EPS bytes for *fig*, or None if matplotlib cannot produce them.

    Not part of the shipping flavour list -- this is here because EPS is
    the next candidate for an editor that refuses PDF and SVG on its
    keyboard path.  Illustrator advertises EPS on every copy, and an
    importer written against Illustrator may well key on it.
    """
    import io

    import matplotlib

    buf = io.BytesIO()
    original = matplotlib.rcParams.get("ps.fonttype", 3)
    matplotlib.rcParams["ps.fonttype"] = 3  # glyphs as paths, no font needed
    try:
        fig.savefig(buf, format="eps", bbox_inches="tight", transparent=True)
    except Exception as exc:
        print(f"(EPS render failed: {exc})")
        return None
    finally:
        matplotlib.rcParams["ps.fonttype"] = original
    return buf.getvalue()


def with_eps(original_builder, eps_bytes):
    """Wrap clipboard_export._pasteboard_flavours to add EPS after the PDF."""
    def builder(pdf_bytes, svg_bytes, png_bytes):
        flavours = original_builder(pdf_bytes, svg_bytes, png_bytes)
        if not eps_bytes:
            return flavours
        at = 1 if flavours and flavours[0][0] == "com.adobe.pdf" else 0
        return flavours[:at] + [(EPS_UTI, eps_bytes)] + flavours[at:]
    return builder


def write_legacy(flavours, mime_aliases=()):
    """declareTypes:owner: + setData:forType: -- the pre-fix writer.

    Kept only so the bisect has a control.  Note it bumps changeCount
    twice: once for clearContents and again for declareTypes:.
    """
    from AppKit import NSPasteboard

    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    all_types = list(flavours) + list(mime_aliases)
    pb.declareTypes_owner_([name for name, _ in all_types], None)
    placed = []
    for name, data in all_types:
        if pb.setData_forType_(data, name):
            placed.append(name)
    return placed


def dump_pasteboard():
    """Print every item and flavour currently on the general pasteboard."""
    from AppKit import NSPasteboard

    pb = NSPasteboard.generalPasteboard()
    print(f"changeCount: {pb.changeCount()}")
    items = pb.pasteboardItems() or []
    if not items:
        print("(no items)")
    for i, item in enumerate(items):
        print(f"-- item {i} --")
        for t in item.types():
            data = item.dataForType_(t)
            print(f"  {t:<40} {data.length() if data else -1:>9} bytes")
    if len(items) > 1:
        print("\nNote: more than one item. One item carrying every flavour "
              "is what a single copied graph should look like.")


def watch_pasteboard():
    """Print every new pasteboard as it appears, until Ctrl+C.

    ``dump`` has a race that eats measurements: between making the copy in
    the app under test and running the dump, *anything* that touches the
    clipboard wins -- and copying the dump command itself out of a browser
    or chat window is enough to do it.  Watching sidesteps that entirely.
    Start this first, then go make copies; each one is recorded as it
    happens, labelled with whichever app was frontmost at the time.
    """
    import datetime
    import time

    from AppKit import NSPasteboard, NSWorkspace

    pb = NSPasteboard.generalPasteboard()
    workspace = NSWorkspace.sharedWorkspace()
    last = pb.changeCount()

    print(f"watching the pasteboard (changeCount {last}); Ctrl+C to stop")
    print("go make a copy in the app under test\n", flush=True)

    try:
        while True:
            time.sleep(0.25)
            count = pb.changeCount()
            if count == last:
                continue
            last = count

            app = workspace.frontmostApplication()
            who = app.localizedName() if app else "?"
            stamp = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"-- {stamp}  changeCount {count}  frontmost: {who} --")

            items = pb.pasteboardItems() or []
            if not items:
                print("   (no items)")
            for i, item in enumerate(items):
                if len(items) > 1:
                    print(f"   item {i}:")
                for t in item.types():
                    data = item.dataForType_(t)
                    size = data.length() if data else -1
                    print(f"   {t:<45} {size:>9} bytes")
            print(flush=True)
    except KeyboardInterrupt:
        print("\nstopped")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("variant", choices=VARIANTS)
    args = parser.parse_args()

    if sys.platform != "darwin":
        raise SystemExit("NSPasteboard is macOS-only")

    if args.variant == "dump":
        dump_pasteboard()
        return

    if args.variant == "watch":
        watch_pasteboard()
        return

    from AppKit import NSPasteboard

    from graphulator import clipboard_export as ce

    # Each variant is one configuration of the shipping module.
    later = ("alias", "mime", "text", "eps", "everything")
    ce.INCLUDE_SVG_ALIAS = args.variant in later
    ce.INCLUDE_MIME_ALIASES = args.variant in ("mime", "text", "eps", "everything")
    ce.INCLUDE_SVG_AS_TEXT = args.variant in ("text", "everything")
    if args.variant == "legacy":
        ce._copy_macos_ctypes = write_legacy
        ce._copy_macos_pyobjc = write_legacy

    import matplotlib.pyplot as plt

    fig = sample_figure()
    try:
        if args.variant in ("eps", "everything"):
            ce._pasteboard_flavours = with_eps(ce._pasteboard_flavours,
                                               render_eps(fig))
        backend, placed = ce.copy_figure_to_clipboard(fig)
    finally:
        plt.close(fig)

    api = ("declareTypes:owner: + setData:forType:" if args.variant == "legacy"
           else "writeObjects: (one NSPasteboardItem)")
    pb = NSPasteboard.generalPasteboard()
    print(f"variant    : {args.variant}")
    print(f"api        : {api}")
    print(f"backend    : {backend} via {ce.last_clipboard_method}")
    print(f"changeCount: {pb.changeCount()}")
    print("flavours   :")
    for uti in placed:
        print(f"  {uti}")
    print("\nNow click into the target app and press Cmd+V.")


if __name__ == "__main__":
    main()
