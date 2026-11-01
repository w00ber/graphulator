"""Copy a matplotlib figure to the system clipboard for pasting into other apps.

The goal is high-fidelity *vector* paste into presentation/design tools
(Keynote, PowerPoint, Adobe Illustrator). To maximise compatibility we put
several representations of the same graph on the clipboard at once and let each
target application pick the richest format it understands:

* **PDF** -- the most widely supported vector clipboard format on macOS. Keynote,
  PowerPoint and Illustrator all paste ``com.adobe.pdf`` as crisp vector art.
* **SVG** -- preferred by Illustrator and other SVG-aware editors.
* **PNG** (high resolution) -- a universal raster fallback so *something* always
  pastes, even into apps that ignore the vector flavours.

On macOS the native ``NSPasteboard`` is the only way to tag each representation
with the exact Uniform Type Identifier (``com.adobe.pdf``, ``public.svg-image``,
``public.png``) that other applications look for. All flavours go onto a single
``NSPasteboardItem`` written with ``-writeObjects:`` -- the modern API, which
some editors' Cmd+V path requires and which bumps the pasteboard's
``changeCount`` once per copy instead of twice. We reach the pasteboard through
a chain of fallbacks, ordered most- to least- robust, mirroring the approach
that ships in the sibling *Diagrammer* app:

1. **ctypes** -- call the Objective-C runtime (``libobjc.dylib``) directly. This
   ships with every macOS install, so it needs **no third-party packages** and
   works inside a frozen (PyInstaller) bundle that has no ``pyobjc``.
2. **PyObjC** -- if ``AppKit`` happens to be importable in this interpreter.
3. **subprocess** -- shell out to the system ``/usr/bin/python3``, which ships
   with PyObjC on macOS, and write the pasteboard from there.
4. **Qt** -- :class:`~PySide6.QtGui.QClipboard` as a last resort (and the only
   path used on Linux/Windows). It always provides the PNG raster path and
   attempts the vector flavours too, but other apps honour them less reliably.

Crucially, the native vector paste no longer *depends* on ``pyobjc`` being
installed -- the ctypes path covers the common case on its own.
"""

import io
import logging
import re
import sys

import matplotlib

logger = logging.getLogger(__name__)

# Uniform Type Identifiers, richest/most-preferred vector flavour first so apps
# that iterate the available types pick the vector PDF before the raster PNG.
_PDF_UTI = "com.adobe.pdf"
_SVG_UTI = "public.svg-image"
_SVG_ALIAS_UTI = "com.adobe.svg"
_PNG_UTI = "public.png"
_TEXT_UTI = "public.utf8-plain-text"

# Advertise the SVG under Adobe's private UTI as well as the public one. Some
# vector editors recognise only ``com.adobe.svg`` when deciding whether the
# pasteboard holds vector artwork -- notably on the Cmd+V path, which can be
# gated on a narrower type list than Edit > Paste. Costs nothing: it is the
# same bytes under a second name, and consumers that want the public UTI still
# find it first.
INCLUDE_SVG_ALIAS = True

# Also advertise the SVG source as plain text, last, after the artwork.
#
# This is what makes Cmd+V work in VectorCraft, established by diffing a
# working clipboard against a failing one on the same machine: a Diagrammer
# copy (pastes) and a Graphulator copy (did not) were identical but for this
# one flavour. VectorCraft's binary lists `text/plain` among the types its
# paste path reads, so that is the flavour it takes the SVG from. Illustrator
# advertises the SVG as text too.
#
# The cost is real and visible: pasting into a *plain-text* target -- BBEdit,
# a terminal, a code editor -- now yields SVG source instead of nothing.
# Rich-text and image consumers are unaffected; they ask for their own flavour
# and never see this one. Set to False to drop it.
INCLUDE_SVG_AS_TEXT = True

# MIME-style pasteboard type names, advertised *in addition to* the UTIs above
# with the same bytes behind them.
#
# Not every macOS app reads the pasteboard by UTI. Some ask for the MIME name
# instead -- cross-platform apps especially, whose clipboard layer was written
# against GTK/Qt (where ``image/svg+xml`` is the standard SVG flavour) and
# ported to macOS unchanged. VectorCraft is one: its binary names
# ``image/svg+xml``, ``application/pdf`` and ``application/postscript``, and
# does *not* name ``public.svg-image`` anywhere.
#
# Like the DOCTYPE strip, this is defensive rather than load-bearing: what
# actually fixed VectorCraft's Cmd+V was INCLUDE_SVG_AS_TEXT, and Diagrammer
# pastes into it with no MIME names at all. Kept because it costs two extra
# flavours of bytes we already have, and because an app that reads by MIME
# name is otherwise unreachable.
#
# These cannot go on the NSPasteboardItem: AppKit rejects a type string that is
# not a valid UTI ("'image/svg+xml' is not a valid UTI string"). They are added
# at the *pasteboard* level instead, after the item is written -- see
# :func:`_add_mime_aliases_pyobjc`. macOS stores them as dynamic UTIs
# (``dyn.ah62d4rv4gu80w5pbq7ww8650q6z1u5pq`` is ``image/svg+xml``), and an app
# asking for the MIME name resolves to the same dynamic UTI and finds the data.
INCLUDE_MIME_ALIASES = True

_MIME_SVG = "image/svg+xml"
_MIME_PDF = "application/pdf"

# Clipboard method used for the most recent copy (for diagnostics).
# One of: "native (ctypes)", "native (PyObjC)", "subprocess (...)", "qt".
last_clipboard_method: str = ""


def _pasteboard_flavours(pdf_bytes, svg_bytes, png_bytes):
    """Build the ``(UTI, payload)`` list to place on the macOS pasteboard.

    Ordered richest-first -- which is what Illustrator does, and what an app
    that walks an item's types in order expects. Empty payloads are dropped, so
    a caller that suppressed the PNG (or a failed SVG render) simply yields
    fewer flavours. The plain-text flavour, when enabled, goes last so nothing
    scanning in order prefers the source over the artwork.

    Returns
    -------
    list[tuple[str, bytes]]
    """
    flavours = []
    if pdf_bytes:
        flavours.append((_PDF_UTI, bytes(pdf_bytes)))
    if svg_bytes:
        flavours.append((_SVG_UTI, bytes(svg_bytes)))
        if INCLUDE_SVG_ALIAS:
            flavours.append((_SVG_ALIAS_UTI, bytes(svg_bytes)))
    if png_bytes:
        flavours.append((_PNG_UTI, bytes(png_bytes)))
    if svg_bytes and INCLUDE_SVG_AS_TEXT:
        flavours.append((_TEXT_UTI, bytes(svg_bytes)))
    return flavours


def _mime_aliases(pdf_bytes, svg_bytes):
    """The ``(MIME name, payload)`` list to add at the pasteboard level.

    Same bytes as the matching UTI flavours, under the names a MIME-oriented
    clipboard layer looks for. Empty when :data:`INCLUDE_MIME_ALIASES` is off,
    and empty entries are dropped as in :func:`_pasteboard_flavours`.

    SVG first: an app that prefers vector should find the SVG before the PDF,
    and both are vector, so this only orders two good answers.

    Returns
    -------
    list[tuple[str, bytes]]
    """
    if not INCLUDE_MIME_ALIASES:
        return []
    aliases = []
    if svg_bytes:
        aliases.append((_MIME_SVG, bytes(svg_bytes)))
    if pdf_bytes:
        aliases.append((_MIME_PDF, bytes(pdf_bytes)))
    return aliases


def content_bbox_inches(fig, pad_frac: float = 0.03):
    """Bounding box (in inches) tightly enclosing ``fig``'s drawn content.

    matplotlib's ``bbox_inches="tight"`` does *not* crop to the graph when the
    axes fills the whole figure with ``axis("off")`` -- it returns roughly the
    full figure, so a pasted graph carries a huge empty margin. This walks the
    real artists (patches, lines, collections **and text labels**) and unions
    their rendered extents instead. Because text extents are included, labels
    are never clipped -- the box grows to contain them.

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        The figure to measure. It must have been drawn at least once (or have a
        usable Agg canvas) so glyph extents are available.
    pad_frac : float, default=0.03
        Padding added on every side, as a fraction of the larger content
        dimension, so strokes/descenders get a little breathing room.

    Returns
    -------
    matplotlib.transforms.Bbox or None
        The crop box in inches, or ``None`` if no content was found or no
        renderer is available (callers should then fall back to ``"tight"``).
    """
    from matplotlib.transforms import Bbox

    # A renderer with current glyph metrics is required for text extents.
    fig.canvas.draw()
    try:
        renderer = fig.canvas.get_renderer()
    except AttributeError:
        return None

    bboxes = []
    for ax in fig.get_axes():
        # The axes background patch, spines and (hidden) axis artists span the
        # whole figure -- exactly the thing we are trying to crop away.
        skip = {ax.patch, ax.xaxis, ax.yaxis, *ax.spines.values()}
        for artist in ax.get_children():
            if artist in skip or not artist.get_visible():
                continue
            try:
                bb = artist.get_window_extent(renderer)
            except Exception:
                continue
            if bb is None or bb.width <= 0 or bb.height <= 0:
                continue
            bboxes.append(bb)

    if not bboxes:
        return None

    bbox = Bbox.union(bboxes)
    pad = pad_frac * max(bbox.width, bbox.height)
    bbox = bbox.padded(pad)
    return bbox.transformed(fig.dpi_scale_trans.inverted())


def render_figure_formats(fig, png_dpi: int = 300, bbox=None):
    """Render ``fig`` to PDF, SVG and PNG byte strings.

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        The figure to render.
    png_dpi : int, default=300
        Resolution for the raster (PNG) fallback.
    bbox : matplotlib.transforms.Bbox or ``"tight"``, optional
        Crop box to save with. Callers that have already measured the
        figure pass theirs so it is not measured (and drawn) twice; left
        out, it is computed here.

    Returns
    -------
    tuple[bytes, bytes, bytes]
        ``(pdf_bytes, svg_bytes, png_bytes)``.
    """
    # Crop tightly to the graph (labels included) rather than the full figure,
    # so it pastes without a huge empty margin. Fall back to matplotlib's
    # "tight" if the content box can't be computed.
    if bbox is None:
        bbox = content_bbox_inches(fig)
    bbox_arg = bbox if bbox is not None else "tight"

    # Render SVG glyphs as embedded vector outlines (svg.fonttype="path") so the
    # paste is self-contained -- no Computer Modern / LaTeX fonts required on the
    # machine that opens it, the way LaTeXit exports outlined text. transparent=
    # True drops matplotlib's white figure-background rectangle, so the paste has
    # no full-page rectangle object to delete (and no opaque backing).
    svg_buffer = io.BytesIO()
    original_svg_fonttype = matplotlib.rcParams.get("svg.fonttype", "path")
    matplotlib.rcParams["svg.fonttype"] = "path"
    try:
        fig.savefig(svg_buffer, format="svg", bbox_inches=bbox_arg, transparent=True)
    finally:
        matplotlib.rcParams["svg.fonttype"] = original_svg_fonttype
    # Drop matplotlib's DOCTYPE: some SVG importers reject the whole document
    # over it. See :func:`_strip_svg_doctype`.
    svg_bytes = _strip_svg_doctype(svg_buffer.getvalue())

    # Derive the PDF from the *outlined* SVG so its text is outlines too. This
    # matters for paste targets (notably Illustrator) that prefer the PDF
    # flavour and would otherwise import matplotlib's font-based PDF as live
    # text needing Computer Modern installed. Fall back to matplotlib's
    # font-embedded PDF if no SVG->PDF converter is available.
    pdf_bytes = svg_bytes_to_pdf(svg_bytes)
    if pdf_bytes is None:
        pdf_buffer = io.BytesIO()
        original_fonttype = matplotlib.rcParams.get("pdf.fonttype", 42)
        matplotlib.rcParams["pdf.fonttype"] = 42
        try:
            fig.savefig(pdf_buffer, format="pdf", bbox_inches=bbox_arg, transparent=True)
        finally:
            matplotlib.rcParams["pdf.fonttype"] = original_fonttype
        pdf_bytes = pdf_buffer.getvalue()

    png_buffer = io.BytesIO()
    fig.savefig(png_buffer, format="png", dpi=png_dpi, bbox_inches=bbox_arg, transparent=True)

    return pdf_bytes, svg_bytes, png_buffer.getvalue()


def _strip_svg_doctype(svg_bytes):
    """Remove the ``<!DOCTYPE svg ...>`` declaration from *svg_bytes*.

    matplotlib emits a DTD declaration on every SVG:

    .. code-block:: xml

        <!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN"
          "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">

    It is valid SVG 1.1, but nothing legitimate reads it: the DTD it points
    at is never fetched and SVG 1.1 does not require the declaration. Qt's
    ``QSvgGenerator`` and Illustrator both omit it.

    Dropping it is defensive rather than load-bearing. The Rust SVG stack
    (``roxmltree`` -> ``usvg`` -> ``resvg``) that a growing number of editors
    are built on refuses a document with a DTD unless the caller opts in with
    ``allow_dtd``, failing with ``XML with DTD detected``. VectorCraft is
    built on that stack and *does* opt in -- it opens a matplotlib SVG with
    the declaration intact -- so this was not the Cmd+V bug (that was the
    missing ``public.utf8-plain-text`` flavour; see
    :data:`INCLUDE_SVG_AS_TEXT`). An editor on the same stack that did not
    opt in would reject our SVG outright, so the declaration is dropped for
    every consumer rather than waiting to meet one.

    The optional internal subset (``<!DOCTYPE svg [ ... ]>``) is handled too,
    since a ``>`` can appear inside it and a naive ``<!DOCTYPE[^>]*>`` would
    truncate mid-declaration and leave broken markup behind.
    """
    return re.sub(
        rb"<!DOCTYPE\s+[^>\[]*(?:\[[^\]]*\]\s*)?>\s*",
        b"",
        svg_bytes,
        count=1,
    )


def _blend_over_white(hex_color, alpha):
    """Composite ``#rrggbb`` at ``alpha`` over a white background -> ``#rrggbb``."""
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    br = round(r * alpha + 255 * (1 - alpha))
    bg = round(g * alpha + 255 * (1 - alpha))
    bb = round(b * alpha + 255 * (1 - alpha))
    return f"#{br:02x}{bg:02x}{bb:02x}"


def _bake_svg_opacity(svg_bytes):
    """Fold element ``opacity`` into solid ``fill``/``stroke`` colors.

    matplotlib encodes a patch's ``alpha`` as ``opacity`` (and occasionally
    ``fill-opacity`` / ``stroke-opacity``) in the element's ``style="..."``.
    PyMuPDF's SVG->PDF conversion silently drops those, so semi-transparent
    art (e.g. a dimmed conjugated node, or Paragraphulator's scattering-mode
    dimming) renders fully opaque in the PDF clipboard/export flavour. We
    pre-composite the opacity into the fill/stroke color over white -- matching
    the white canvas the user sees -- so the color survives any converter.

    Only ``style`` attributes that actually carry an opacity < 1 are touched;
    everything else (and any color that isn't a plain ``#rrggbb``) is left
    byte-identical, so there is no regression for opaque graphs.
    """

    def bake_style(match):
        style = match.group(1)
        props = {}
        for decl in style.split(";"):
            if ":" in decl:
                k, v = decl.split(":", 1)
                props[k.strip()] = v.strip()

        try:
            opacity = float(props.get("opacity", 1))
            fill_op = float(props.get("fill-opacity", 1)) * opacity
            stroke_op = float(props.get("stroke-opacity", 1)) * opacity
        except ValueError:
            return match.group(0)

        if fill_op >= 1 and stroke_op >= 1:
            return match.group(0)  # nothing transparent -> leave untouched

        hex_re = re.compile(r"^#[0-9a-fA-F]{6}$")
        fill = props.get("fill")
        stroke = props.get("stroke")
        if fill_op < 1 and fill and hex_re.match(fill):
            props["fill"] = _blend_over_white(fill, fill_op)
        if stroke_op < 1 and stroke and hex_re.match(stroke):
            props["stroke"] = _blend_over_white(stroke, stroke_op)

        # Opacity is now baked into the colors; neutralize the opacity keys so
        # the converter can't drop (or double-apply) them.
        for k in ("opacity", "fill-opacity", "stroke-opacity"):
            props.pop(k, None)

        new_style = "; ".join(f"{k}: {v}" for k, v in props.items())
        return f'style="{new_style}"'

    text = svg_bytes.decode("utf-8")
    baked = re.sub(r'style="([^"]*)"', bake_style, text)
    return baked.encode("utf-8")


def svg_bytes_to_pdf(svg_bytes):
    """Convert outlined-SVG bytes to PDF bytes, preserving vector outlines.

    Tries, in order of preference, converters that keep glyph *paths* as paths
    (so the PDF needs no fonts): PyMuPDF (pure-Python, the declared dependency),
    then cairosvg, then the ``rsvg-convert`` CLI. Returns the PDF bytes, or
    ``None`` if none are available so the caller can fall back to matplotlib's
    own (font-embedded) PDF output.

    Element opacity is first baked into the fill/stroke colors (over white)
    because PyMuPDF drops SVG ``opacity`` during conversion; see
    :func:`_bake_svg_opacity`.
    """
    svg_bytes = _bake_svg_opacity(svg_bytes)

    # 1. PyMuPDF / fitz -- pure Python, no native CLI needed.
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(stream=svg_bytes, filetype="svg")
        pdf = doc.convert_to_pdf()
        if pdf:
            return bytes(pdf)
    except Exception:
        logger.debug("PyMuPDF SVG->PDF unavailable/failed", exc_info=True)

    # 2. cairosvg -- Python binding over libcairo.
    try:
        import cairosvg

        pdf = cairosvg.svg2pdf(bytestring=svg_bytes)
        if pdf:
            return pdf
    except Exception:
        logger.debug("cairosvg SVG->PDF unavailable/failed", exc_info=True)

    # 3. rsvg-convert CLI -- last resort where it happens to be installed.
    try:
        import shutil
        import subprocess

        exe = shutil.which("rsvg-convert")
        if exe:
            result = subprocess.run(
                [exe, "-f", "pdf"], input=svg_bytes,
                capture_output=True, timeout=15,
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout
    except Exception:
        logger.debug("rsvg-convert SVG->PDF failed", exc_info=True)

    logger.debug("No SVG->PDF converter available; using matplotlib PDF")
    return None


# ----------------------------------------------------------------------
# macOS: ctypes (no dependencies)
# ----------------------------------------------------------------------

def _copy_macos_ctypes(flavours, mime_aliases=()):
    """Write *flavours* to the macOS pasteboard via the ObjC runtime.

    Uses ctypes to call ``libobjc.dylib`` directly -- works on every macOS
    install without any third-party packages, which is what the frozen
    PyInstaller bundles rely on to get native vector paste without shipping
    ``pyobjc``.

    Every flavour goes onto a single ``NSPasteboardItem`` written through
    ``-writeObjects:`` rather than the pre-10.6 ``declareTypes:owner:`` pair.
    Two reasons: it is the API modern AppKit readers expect, and the legacy
    pair bumps the pasteboard's ``changeCount`` *twice* per copy (once for
    ``clearContents``, again for ``declareTypes:``), so apps that poll
    ``changeCount`` to decide whether to re-read the clipboard see a phantom
    second change.

    *mime_aliases* are added afterwards at the pasteboard level, because
    ``NSPasteboardItem`` refuses a type string that is not a valid UTI.

    Returns the list of types actually placed. Raises on failure so the caller
    can fall through to the next method.
    """
    import ctypes
    import ctypes.util

    if not flavours:
        raise RuntimeError("Nothing to place on the pasteboard")

    objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))

    objc.objc_getClass.restype = ctypes.c_void_p
    objc.objc_getClass.argtypes = [ctypes.c_char_p]
    objc.sel_registerName.restype = ctypes.c_void_p
    objc.sel_registerName.argtypes = [ctypes.c_char_p]

    msg = objc.objc_msgSend
    msg.restype = ctypes.c_void_p
    msg.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

    def cls(name: str) -> ctypes.c_void_p:
        return objc.objc_getClass(name.encode())

    def sel(name: str) -> ctypes.c_void_p:
        return objc.sel_registerName(name.encode())

    def send(obj, selector, *args):
        return msg(obj, selector, *args)

    def make_nsdata(raw: bytes) -> ctypes.c_void_p:
        NSData = cls("NSData")
        buf = ctypes.create_string_buffer(raw)
        fn = ctypes.cast(msg, ctypes.CFUNCTYPE(
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_void_p, ctypes.c_uint64,
        ))
        return fn(NSData, sel("dataWithBytes:length:"), buf, len(raw))

    def make_nsstring(s: str) -> ctypes.c_void_p:
        NSString = cls("NSString")
        buf = ctypes.create_string_buffer(s.encode("utf-8"))
        fn = ctypes.cast(msg, ctypes.CFUNCTYPE(
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_void_p, ctypes.c_uint64,
        ))
        return fn(NSString, sel("stringWithUTF8String:"), buf, 0)

    def make_nsarray(items: list) -> ctypes.c_void_p:
        NSArray = cls("NSArray")
        arr_type = ctypes.c_void_p * len(items)
        c_arr = arr_type(*items)
        fn = ctypes.cast(msg, ctypes.CFUNCTYPE(
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p), ctypes.c_uint64,
        ))
        return fn(NSArray, sel("arrayWithObjects:count:"), c_arr, len(items))

    # One item carrying every flavour. Several items would read as several
    # copied objects, which is not what a single graph is.
    NSPasteboardItem = cls("NSPasteboardItem")
    item = send(send(NSPasteboardItem, sel("alloc")), sel("init"))
    if not item:
        raise RuntimeError("Failed to allocate NSPasteboardItem")

    # Unlike the pasteboard-level call, ``setData:forType:`` on an *item*
    # rejects a string that is not a valid UTI -- so a BOOL of false here is
    # the signal that a flavour name is wrong, not that the data was bad.
    fn_set = ctypes.cast(msg, ctypes.CFUNCTYPE(
        ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p,
    ))

    placed = []
    for uti, data in flavours:
        if fn_set(item, sel("setData:forType:"),
                  make_nsdata(data), make_nsstring(uti)):
            placed.append(uti)
        else:
            logger.warning("NSPasteboardItem rejected flavour %r", uti)

    if not placed:
        raise RuntimeError("NSPasteboardItem accepted nothing")

    NSPasteboard = cls("NSPasteboard")
    pb = send(NSPasteboard, sel("generalPasteboard"))
    if not pb:
        raise RuntimeError("Failed to get NSPasteboard")

    send(pb, sel("clearContents"))

    fn_write = ctypes.cast(msg, ctypes.CFUNCTYPE(
        ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
    ))
    if not fn_write(pb, sel("writeObjects:"), make_nsarray([item])):
        raise RuntimeError("NSPasteboard writeObjects: failed")

    send(item, sel("release"))

    # The MIME names go on at the pasteboard level, after the item. addTypes:
    # extends what is already there rather than replacing it, so this does not
    # cost a second changeCount bump (measured: still +1 per copy).
    if mime_aliases:
        fn_add = ctypes.cast(msg, ctypes.CFUNCTYPE(
            ctypes.c_int64, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_void_p, ctypes.c_void_p,
        ))
        name_objs = [(name, make_nsstring(name)) for name, _ in mime_aliases]
        fn_add(pb, sel("addTypes:owner:"),
               make_nsarray([obj for _, obj in name_objs]), None)

        fn_set_pb = ctypes.cast(msg, ctypes.CFUNCTYPE(
            ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_void_p, ctypes.c_void_p,
        ))
        for (name, data), (_, name_obj) in zip(mime_aliases, name_objs):
            if fn_set_pb(pb, sel("setData:forType:"),
                         make_nsdata(data), name_obj):
                placed.append(name)
            else:
                logger.warning("NSPasteboard rejected MIME alias %r", name)

    return placed


# ----------------------------------------------------------------------
# macOS: PyObjC
# ----------------------------------------------------------------------

def _copy_macos_pyobjc(flavours, mime_aliases=()):
    """Write *flavours* to the macOS pasteboard via AppKit (PyObjC).

    Same single-``NSPasteboardItem`` / ``writeObjects:`` shape as
    :func:`_copy_macos_ctypes`, with *mime_aliases* added at the pasteboard
    level afterwards; see there for why. Raises ImportError if PyObjC is not
    available. Returns the list of types placed.
    """
    from AppKit import NSPasteboard, NSPasteboardItem

    if not flavours:
        raise RuntimeError("Nothing to place on the pasteboard")

    item = NSPasteboardItem.alloc().init()
    placed = []
    for uti, data in flavours:
        if item.setData_forType_(data, uti):
            placed.append(uti)
        else:
            logger.warning("NSPasteboardItem rejected flavour %r", uti)

    if not placed:
        raise RuntimeError("NSPasteboardItem accepted nothing")

    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    if not pb.writeObjects_([item]):
        raise RuntimeError("NSPasteboard writeObjects: failed")

    placed += _add_mime_aliases_pyobjc(pb, mime_aliases)
    return placed


def _add_mime_aliases_pyobjc(pb, mime_aliases):
    """Add *mime_aliases* to *pb* at the pasteboard level. Returns those added.

    Split out because this is the one piece the item-based API cannot express:
    ``NSPasteboardItem.setData:forType:`` rejects anything that is not a valid
    UTI, while the older pasteboard-level pair accepts an arbitrary type name.
    ``addTypes:owner:`` appends to the item already written, so the copy still
    costs a single ``changeCount`` bump.
    """
    if not mime_aliases:
        return []

    pb.addTypes_owner_([name for name, _ in mime_aliases], None)
    added = []
    for name, data in mime_aliases:
        if pb.setData_forType_(data, name):
            added.append(name)
        else:
            logger.warning("NSPasteboard rejected MIME alias %r", name)
    return added


# ----------------------------------------------------------------------
# macOS: subprocess (system python3 usually ships with PyObjC)
# ----------------------------------------------------------------------

# Injected with ``str.format``, so any literal brace added here must be
# doubled. There are none; keep it that way.
_PASTEBOARD_SCRIPT = '''\
from AppKit import NSPasteboard, NSPasteboardItem

flavours = {flavours}
mime_aliases = {mime_aliases}

item = NSPasteboardItem.alloc().init()
placed = []
for uti, path in flavours:
    with open(path, "rb") as f:
        data = f.read()
    if item.setData_forType_(data, uti):
        placed.append(uti)

if not placed:
    raise SystemExit("NSPasteboardItem accepted nothing")

pb = NSPasteboard.generalPasteboard()
pb.clearContents()
if not pb.writeObjects_([item]):
    raise SystemExit("writeObjects: failed")

if mime_aliases:
    pb.addTypes_owner_([name for name, _ in mime_aliases], None)
    for name, path in mime_aliases:
        with open(path, "rb") as f:
            pb.setData_forType_(f.read(), name)
'''


def _copy_macos_subprocess(flavours, mime_aliases=()):
    """Fallback: write *flavours* to the macOS pasteboard via a subprocess.

    Tries several Python interpreters that may have AppKit available; each
    payload is handed over as a temp file. *mime_aliases* are added at the
    pasteboard level in the child, as in the other two writers. Returns
    ``(method, placed)`` on success or ``(None, [])`` on failure.
    """
    import os
    import shutil
    import subprocess
    import tempfile

    if not flavours:
        return None, []

    tmp_paths = []

    def spill(payload):
        fd, path = tempfile.mkstemp(suffix=".bin")
        os.close(fd)
        tmp_paths.append(path)
        with open(path, "wb") as f:
            f.write(bytes(payload))
        return path

    try:
        pairs = [(uti, spill(data)) for uti, data in flavours]
        alias_pairs = [(name, spill(data)) for name, data in mime_aliases]

        script = _PASTEBOARD_SCRIPT.format(flavours=repr(pairs),
                                           mime_aliases=repr(alias_pairs))
        placed = [name for name, _ in pairs + alias_pairs]

        candidates = ["/usr/bin/python3"]
        for name in ("python3", "python"):
            found = shutil.which(name)
            if found and found not in candidates:
                candidates.append(found)

        for python in candidates:
            try:
                result = subprocess.run(
                    [python, "-c", script],
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    return f"subprocess ({python})", placed
            except (OSError, subprocess.SubprocessError) as exc:
                logger.debug("Subprocess clipboard via %s failed: %s", python, exc)
                continue
        return None, []
    except Exception:
        logger.debug("Subprocess clipboard fallback failed entirely", exc_info=True)
        return None, []
    finally:
        for path in tmp_paths:
            try:
                os.unlink(path)
            except OSError:
                pass


# ----------------------------------------------------------------------
# Qt fallback (Linux / Windows, or macOS last resort)
# ----------------------------------------------------------------------

def _copy_qt(pdf_bytes, svg_bytes, png_bytes):
    """Write all representations to the clipboard via Qt's QClipboard.

    Returns the list of MIME types placed on the clipboard.
    """
    from PySide6.QtCore import QByteArray, QMimeData
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication

    mime = QMimeData()
    placed = []

    # Raster fallback first -- this is what guarantees a paste everywhere.
    image = QImage.fromData(QByteArray(png_bytes), "PNG")
    if not image.isNull():
        mime.setImageData(image)
        placed.append("image/png")

    mime.setData("application/pdf", QByteArray(pdf_bytes))
    placed.append("application/pdf")
    mime.setData("image/svg+xml", QByteArray(svg_bytes))
    placed.append("image/svg+xml")

    QApplication.clipboard().setMimeData(mime)
    return placed


def copy_figure_to_clipboard(fig, png_dpi: int = 300, include_png: bool = True,
                             bbox=None):
    """Copy ``fig`` to the system clipboard as PDF + SVG (+ PNG).

    On macOS the data is placed on the native ``NSPasteboard`` with the proper
    Uniform Type Identifiers so that Illustrator, Keynote and PowerPoint receive
    editable vector data.  The pasteboard is reached without requiring
    ``pyobjc`` (ctypes path); PyObjC, a subprocess, and Qt are tried in turn if
    the preceding method is unavailable.

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        The figure to copy.
    png_dpi : int, default=300
        Resolution for the raster (PNG) fallback.
    bbox : matplotlib.transforms.Bbox or ``"tight"``, optional
        Crop box to save with; measured from ``fig`` when left out.
    include_png : bool, default=True
        When ``True`` a high-resolution PNG flavour is placed alongside the
        vector ones as a universal raster fallback. When ``False`` the PNG is
        omitted so vector-aware apps that *prefer* a raster flavour when offered
        one (notably Keynote/PowerPoint, which rasterise the PNG instead of the
        PDF) are forced to take the vector PDF/SVG. The trade-off: apps that
        can only paste a raster will paste nothing.

    Returns
    -------
    tuple[str, list[str]]
        ``(backend, formats)`` where ``backend`` is ``"native"`` (macOS
        NSPasteboard via ctypes/PyObjC), ``"subprocess"`` or ``"qt"``, and
        ``formats`` lists the clipboard types/UTIs that were placed.
    """
    global last_clipboard_method

    pdf_bytes, svg_bytes, png_bytes = render_figure_formats(fig,
                                                            png_dpi=png_dpi,
                                                            bbox=bbox)
    # Omitting the PNG payload makes every downstream copy path (which all skip
    # empty payloads) drop the raster flavour.
    if not include_png:
        png_bytes = b""

    if sys.platform == "darwin":
        flavours = _pasteboard_flavours(pdf_bytes, svg_bytes, png_bytes)
        aliases = _mime_aliases(pdf_bytes, svg_bytes)

        # 1) ctypes -- always available on macOS, no dependencies.
        try:
            placed = _copy_macos_ctypes(flavours, aliases)
            last_clipboard_method = "native (ctypes)"
            logger.info("Copied graph to clipboard (native ctypes): %s", ", ".join(placed))
            return "native", placed
        except Exception:
            logger.debug("ctypes clipboard method failed, trying next", exc_info=True)

        # 2) PyObjC -- if AppKit is importable in this interpreter.
        try:
            placed = _copy_macos_pyobjc(flavours, aliases)
            last_clipboard_method = "native (PyObjC)"
            logger.info("Copied graph to clipboard (native PyObjC): %s", ", ".join(placed))
            return "native", placed
        except Exception:
            logger.debug("PyObjC clipboard method failed, trying next", exc_info=True)

        # 3) subprocess -- system Python usually ships with PyObjC.
        method, placed = _copy_macos_subprocess(flavours, aliases)
        if method:
            last_clipboard_method = method
            logger.info("Copied graph to clipboard (%s): %s", method, ", ".join(placed))
            return "subprocess", placed

        logger.debug("Native macOS pasteboard unavailable; falling back to Qt clipboard")

    placed = _copy_qt(pdf_bytes, svg_bytes, png_bytes)
    last_clipboard_method = "qt"
    logger.info("Copied graph to clipboard (Qt): %s", ", ".join(placed))
    return "qt", placed
