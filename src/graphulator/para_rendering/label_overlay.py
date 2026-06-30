"""
PROTOTYPE: Qt SVG overlay for LaTeX labels (rearchitecture experiment).

This is the "bigger rearchitecture" alternative to caching glyph paths inside
matplotlib.  Instead of drawing labels through matplotlib at all, it renders each
unique LaTeX label *once* to an SVG and paints it with Qt's vector renderer
(:class:`QSvgRenderer`) in a transparent widget laid over the matplotlib canvas.

matplotlib keeps drawing the cheap artists (node circles, edges, grid); the
expensive LaTeX is taken entirely out of matplotlib's render loop.  On pan/zoom
the axes limits change and the overlay simply repaints -- mapping each label's
data coordinate through ``ax.transData`` and scaling the cached SVG by the
current pixels-per-data-unit.  No LaTeX is ever re-run, and because the source is
SVG the labels stay crisp at any zoom (true vector, like the matplotlib-path
approach, but rendered natively by Qt).

Status: proof-of-concept.  Demonstrates node-label tracking on pan/zoom.  Known
gaps vs the matplotlib path: edge-label rotation, self-loops, and export still
go through matplotlib (labels would need to be re-added for export).
"""

import io
import logging

from matplotlib.figure import Figure
from PySide6.QtCore import Qt, QByteArray, QRectF
from PySide6.QtGui import QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

# Font size (points) at which each label SVG is generated.  Irrelevant to final
# size (the SVG is scaled at paint time); only sets the SVG's intrinsic aspect.
_SVG_FONTSIZE = 24


class LatexLabelOverlay(QWidget):
    """Transparent overlay that paints cached LaTeX-label SVGs over a canvas.

    Parameters
    ----------
    canvas
        The matplotlib ``FigureCanvasQTAgg`` (e.g. ``MplCanvas``) to overlay.
    ax
        The axes whose ``transData`` maps label data coords to display pixels.
    usetex
        Forwarded to matplotlib when generating the label SVG (LaTeX vs mathtext).
    """

    def __init__(self, canvas, ax, usetex=False, parent=None):
        super().__init__(parent or canvas)
        self.canvas = canvas
        self.ax = ax
        self.usetex = usetex
        self.labels = []                 # list of dicts: x, y, text, height_data, color
        self._svg_cache = {}             # (text, color, usetex) -> (QSvgRenderer, aspect)
        self.builds = 0                  # diagnostic: SVGs generated

        # Click-through, transparent overlay sitting on top of the canvas.
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # Repaint whenever matplotlib redraws (pan/zoom/resize all trigger it).
        try:
            self.canvas.mpl_connect('draw_event', lambda _e: self.update())
        except Exception:
            logger.exception("could not connect draw_event")

        self.setGeometry(self.canvas.rect())
        self.raise_()

    # -- public API ---------------------------------------------------------
    def set_labels(self, labels):
        """Set the labels to display.

        ``labels`` is a list of dicts with keys: ``x``, ``y`` (data coords),
        ``text`` (LaTeX/mathtext string), ``height_data`` (label height in data
        units, so it scales with zoom like a node), and optional ``color``.
        """
        self.labels = labels or []
        self.update()

    def clear_cache(self):
        self._svg_cache.clear()

    # -- internals ----------------------------------------------------------
    def _get_svg(self, text, color):
        key = (text, color, self.usetex)
        ent = self._svg_cache.get(key)
        if ent is not None:
            return ent
        renderer = self._render_svg(text, color, self.usetex)
        if renderer is None and self.usetex:
            renderer = self._render_svg(text, color, False)  # mathtext fallback
        if renderer is not None:
            sz = renderer.defaultSize()
            aspect = (sz.width() / sz.height()) if sz.height() else 1.0
            ent = (renderer, aspect)
        else:
            ent = (None, 1.0)
        self._svg_cache[key] = ent
        return ent

    def _render_svg(self, text, color, usetex):
        try:
            fig = Figure()
            fig.patch.set_alpha(0.0)
            fig.text(0.5, 0.5, text, fontsize=_SVG_FONTSIZE, ha='center',
                     va='center', color=color, usetex=usetex)
            buf = io.BytesIO()
            fig.savefig(buf, format='svg', bbox_inches='tight', transparent=True)
            self.builds += 1
            return QSvgRenderer(QByteArray(buf.getvalue()))
        except Exception:
            logger.exception("SVG render failed for %r (usetex=%s)", text, usetex)
            return None

    def _pixels_per_data_unit(self):
        """Vertical pixels per data unit under the current view transform."""
        p0 = self.ax.transData.transform((0.0, 0.0))
        p1 = self.ax.transData.transform((0.0, 1.0))
        return abs(p1[1] - p0[1])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update()

    def paintEvent(self, event):
        if not self.labels:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        height = self.height()
        ppu = self._pixels_per_data_unit()
        for lab in self.labels:
            renderer, aspect = self._get_svg(lab['text'], lab.get('color', 'black'))
            if renderer is None:
                continue
            # data -> display pixels (matplotlib origin is bottom-left; Qt is top-left)
            dx, dy = self.ax.transData.transform((lab['x'], lab['y']))
            cx, cy = dx, height - dy
            h_px = lab['height_data'] * ppu
            w_px = h_px * aspect
            renderer.render(painter, QRectF(cx - w_px / 2, cy - h_px / 2, w_px, h_px))
        painter.end()
