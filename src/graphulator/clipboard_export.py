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

On macOS we write directly to the native ``NSPasteboard`` (via pyobjc) when it is
available, because that lets us tag each representation with the exact Uniform
Type Identifier (``com.adobe.pdf``, ``public.svg-image``, ``public.png``) that
other applications look for. If pyobjc is not installed we fall back to Qt's
:class:`~PySide6.QtGui.QClipboard`, which always provides the PNG raster path and
attempts the vector flavours too.
"""

import io
import logging
import sys

import matplotlib

logger = logging.getLogger(__name__)


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


def _copy_macos_native(pdf_bytes, svg_bytes, png_bytes):
    """Write all representations to the native macOS pasteboard.

    Returns the list of UTIs placed on success, or ``None`` if pyobjc is not
    available (so the caller can fall back to Qt).
    """
    try:
        from AppKit import NSData, NSPasteboard, NSPasteboardItem
    except Exception:  # pyobjc not installed
        return None

    item = NSPasteboardItem.alloc().init()
    placed = []
    # Order matters: list the richest/most-preferred flavour first so apps that
    # iterate types pick the vector PDF before the raster PNG.
    for uti, data in (
        ("com.adobe.pdf", pdf_bytes),
        ("public.svg-image", svg_bytes),
        ("public.png", png_bytes),
    ):
        ns_data = NSData.dataWithBytes_length_(data, len(data))
        if item.setData_forType_(ns_data, uti):
            placed.append(uti)

    pasteboard = NSPasteboard.generalPasteboard()
    pasteboard.clearContents()
    if not pasteboard.writeObjects_([item]):
        return None
    return placed


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
        NSPasteboard) or ``"qt"``, and ``formats`` lists the clipboard
        types/UTIs that were placed.
    """
    pdf_bytes, svg_bytes, png_bytes = render_figure_formats(fig, png_dpi=png_dpi)

    if sys.platform == "darwin":
        placed = _copy_macos_native(pdf_bytes, svg_bytes, png_bytes)
        if placed:
            logger.info("Copied graph to clipboard (native macOS): %s", ", ".join(placed))
            return "native", placed
        logger.debug("Native macOS pasteboard unavailable; falling back to Qt clipboard")

    placed = _copy_qt(pdf_bytes, svg_bytes, png_bytes)
    logger.info("Copied graph to clipboard (Qt): %s", ", ".join(placed))
    return "qt", placed
