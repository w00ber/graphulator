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
``public.png``) that other applications look for. We reach the pasteboard
through a chain of fallbacks, ordered most- to least- robust, mirroring the
approach that ships in the sibling *Diagrammer* app:

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
import sys

import matplotlib

logger = logging.getLogger(__name__)

# Uniform Type Identifiers, richest/most-preferred vector flavour first so apps
# that iterate the available types pick the vector PDF before the raster PNG.
_PDF_UTI = "com.adobe.pdf"
_SVG_UTI = "public.svg-image"
_PNG_UTI = "public.png"

# Clipboard method used for the most recent copy (for diagnostics).
# One of: "native (ctypes)", "native (PyObjC)", "subprocess (...)", "qt".
last_clipboard_method: str = ""


def render_figure_formats(fig, png_dpi: int = 300):
    """Render ``fig`` to PDF, SVG and PNG byte strings.

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        The figure to render.
    png_dpi : int, default=300
        Resolution for the raster (PNG) fallback.

    Returns
    -------
    tuple[bytes, bytes, bytes]
        ``(pdf_bytes, svg_bytes, png_bytes)``.
    """
    # Embed TrueType fonts in the PDF (fonttype 42) so text stays sharp and
    # selectable when pasted, matching the app's "Export PDF" behaviour.
    pdf_buffer = io.BytesIO()
    original_fonttype = matplotlib.rcParams.get("pdf.fonttype", 42)
    matplotlib.rcParams["pdf.fonttype"] = 42
    try:
        fig.savefig(pdf_buffer, format="pdf", bbox_inches="tight")
    finally:
        matplotlib.rcParams["pdf.fonttype"] = original_fonttype

    svg_buffer = io.BytesIO()
    fig.savefig(svg_buffer, format="svg", bbox_inches="tight")

    png_buffer = io.BytesIO()
    fig.savefig(png_buffer, format="png", dpi=png_dpi, bbox_inches="tight")

    return pdf_buffer.getvalue(), svg_buffer.getvalue(), png_buffer.getvalue()


# ----------------------------------------------------------------------
# macOS: ctypes (no dependencies)
# ----------------------------------------------------------------------

def _copy_macos_ctypes(pdf_bytes, svg_bytes, png_bytes):
    """Write all representations to the macOS pasteboard via the ObjC runtime.

    Uses ctypes to call ``libobjc.dylib`` directly -- works on every macOS
    install without any third-party packages.  Returns the list of UTIs
    actually placed.  Raises on failure so the caller can fall through.
    """
    import ctypes
    import ctypes.util

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

    # Build the flavour list (UTI string, data) skipping any empty payloads.
    flavours = [
        (_PDF_UTI, pdf_bytes),
        (_SVG_UTI, svg_bytes),
        (_PNG_UTI, png_bytes),
    ]
    flavours = [(uti, data) for uti, data in flavours if data]
    if not flavours:
        raise RuntimeError("Nothing to place on the pasteboard")

    # Create each NSString type once; reuse for declareTypes and setData.
    type_objs = [(uti, make_nsstring(uti)) for uti, _ in flavours]
    ns_types = make_nsarray([obj for _, obj in type_objs])

    NSPasteboard = cls("NSPasteboard")
    pb = send(NSPasteboard, sel("generalPasteboard"))
    if not pb:
        raise RuntimeError("Failed to get NSPasteboard")

    send(pb, sel("clearContents"))

    fn_declare = ctypes.cast(msg, ctypes.CFUNCTYPE(
        ctypes.c_int64, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p,
    ))
    fn_declare(pb, sel("declareTypes:owner:"), ns_types, None)

    fn_set = ctypes.cast(msg, ctypes.CFUNCTYPE(
        ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p,
    ))

    placed = []
    for (uti, data), (_, type_obj) in zip(flavours, type_objs):
        ns_data = make_nsdata(data)
        if fn_set(pb, sel("setData:forType:"), ns_data, type_obj):
            placed.append(uti)

    if not placed:
        raise RuntimeError("setData:forType: placed nothing on the pasteboard")
    return placed


# ----------------------------------------------------------------------
# macOS: PyObjC
# ----------------------------------------------------------------------

def _copy_macos_pyobjc(pdf_bytes, svg_bytes, png_bytes):
    """Write all representations to the macOS pasteboard via AppKit (PyObjC).

    Raises ImportError if PyObjC is not available.  Returns the list of UTIs
    placed.
    """
    from AppKit import NSPasteboard

    flavours = [
        (_PDF_UTI, pdf_bytes),
        (_SVG_UTI, svg_bytes),
        (_PNG_UTI, png_bytes),
    ]
    flavours = [(uti, data) for uti, data in flavours if data]
    if not flavours:
        raise RuntimeError("Nothing to place on the pasteboard")

    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.declareTypes_owner_([uti for uti, _ in flavours], None)

    placed = []
    for uti, data in flavours:
        if pb.setData_forType_(data, uti):
            placed.append(uti)

    if not placed:
        raise RuntimeError("setData:forType: placed nothing on the pasteboard")
    return placed


# ----------------------------------------------------------------------
# macOS: subprocess (system python3 usually ships with PyObjC)
# ----------------------------------------------------------------------

_PASTEBOARD_SCRIPT = '''\
from AppKit import NSPasteboard

flavours = []
for uti, path in (
    ("com.adobe.pdf", {pdf_path!r}),
    ("public.svg-image", {svg_path!r}),
    ("public.png", {png_path!r}),
):
    if not path:
        continue
    with open(path, "rb") as f:
        flavours.append((uti, f.read()))

pb = NSPasteboard.generalPasteboard()
pb.clearContents()
pb.declareTypes_owner_([uti for uti, _ in flavours], None)
for uti, data in flavours:
    pb.setData_forType_(data, uti)
'''


def _copy_macos_subprocess(pdf_bytes, svg_bytes, png_bytes):
    """Fallback: write the flavours to the macOS pasteboard via a subprocess.

    Tries several Python interpreters that may have AppKit available.
    Returns ``(method, placed)`` on success or ``(None, [])`` on failure.
    """
    import os
    import shutil
    import subprocess
    import tempfile

    tmp_paths = {}
    placed = []
    for key, uti, data in (
        ("pdf_path", _PDF_UTI, pdf_bytes),
        ("svg_path", _SVG_UTI, svg_bytes),
        ("png_path", _PNG_UTI, png_bytes),
    ):
        if not data:
            tmp_paths[key] = ""
            continue
        suffix = "." + key.split("_")[0]
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        with open(path, "wb") as f:
            f.write(bytes(data))
        tmp_paths[key] = path
        placed.append(uti)

    try:
        script = _PASTEBOARD_SCRIPT.format(**tmp_paths)

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
        for path in tmp_paths.values():
            if path:
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


def copy_figure_to_clipboard(fig, png_dpi: int = 300):
    """Copy ``fig`` to the system clipboard as PDF + SVG + PNG.

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

    Returns
    -------
    tuple[str, list[str]]
        ``(backend, formats)`` where ``backend`` is ``"native"`` (macOS
        NSPasteboard via ctypes/PyObjC), ``"subprocess"`` or ``"qt"``, and
        ``formats`` lists the clipboard types/UTIs that were placed.
    """
    global last_clipboard_method

    pdf_bytes, svg_bytes, png_bytes = render_figure_formats(fig, png_dpi=png_dpi)

    if sys.platform == "darwin":
        # 1) ctypes -- always available on macOS, no dependencies.
        try:
            placed = _copy_macos_ctypes(pdf_bytes, svg_bytes, png_bytes)
            last_clipboard_method = "native (ctypes)"
            logger.info("Copied graph to clipboard (native ctypes): %s", ", ".join(placed))
            return "native", placed
        except Exception:
            logger.debug("ctypes clipboard method failed, trying next", exc_info=True)

        # 2) PyObjC -- if AppKit is importable in this interpreter.
        try:
            placed = _copy_macos_pyobjc(pdf_bytes, svg_bytes, png_bytes)
            last_clipboard_method = "native (PyObjC)"
            logger.info("Copied graph to clipboard (native PyObjC): %s", ", ".join(placed))
            return "native", placed
        except Exception:
            logger.debug("PyObjC clipboard method failed, trying next", exc_info=True)

        # 3) subprocess -- system Python usually ships with PyObjC.
        method, placed = _copy_macos_subprocess(pdf_bytes, svg_bytes, png_bytes)
        if method:
            last_clipboard_method = method
            logger.info("Copied graph to clipboard (%s): %s", method, ", ".join(placed))
            return "subprocess", placed

        logger.debug("Native macOS pasteboard unavailable; falling back to Qt clipboard")

    placed = _copy_qt(pdf_bytes, svg_bytes, png_bytes)
    last_clipboard_method = "qt"
    logger.info("Copied graph to clipboard (Qt): %s", ", ".join(placed))
    return "qt", placed
