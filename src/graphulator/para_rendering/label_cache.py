"""
Cached vector glyph-path rendering of math / LaTeX text labels.

The graph canvas used to draw every label with ``ax.text(..., usetex=...)``.
With ``usetex=True`` matplotlib shells out to LaTeX, and because the label font
size is recomputed from the zoom level on *every* frame
(``font_size_points = ... * points_per_data_unit``), matplotlib's usetex cache
(keyed by string + fontsize + dpi) missed on every zoom step and re-invoked
``pdflatex`` for every label, every frame.  That is what made LaTeX mode
sluggish and forced the old fast/slow MathText<->LaTeX debounce hack.

This module renders each unique ``(text, usetex)`` label *once* to a
resolution-independent :class:`matplotlib.path.Path` (via
:class:`matplotlib.textpath.TextPath`) and caches it.  Drawing a label then only
adds a cheap :class:`~matplotlib.patches.PathPatch` with a per-call affine
transform (scale + rotate + translate).  Pan / zoom / rescale change only the
transform, so the (slow) LaTeX / mathtext layout engine is never re-run -- giving
permanent LaTeX-quality labels that stay crisp at any zoom with no toggle.

The cache is engine-agnostic: ``usetex`` is simply forwarded to ``TextPath``.
``usetex=False`` uses matplotlib's built-in mathtext (STIX) engine, which needs
no system LaTeX; ``usetex=True`` uses system LaTeX.  Both produce real vector
paths, so the caching/transform path is identical for both.
"""

import logging

import numpy as np
from matplotlib.font_manager import FontProperties
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.textpath import TextPath
from matplotlib.transforms import Affine2D

logger = logging.getLogger(__name__)

# Reference font size (points) at which paths are built.  The path is scaled at
# draw time, so this only affects internal numeric precision, not output size.
_REF_SIZE = 100.0


class LabelPathCache:
    """Memoizes ``(text, usetex) -> (Path, extents)`` and draws cached labels.

    A single instance is shared across an entire canvas; call :meth:`clear` when
    something global to LaTeX rendering changes (preamble / fontset).  Colors and
    background boxes are applied at *draw* time, so they never invalidate the
    cache.
    """

    def __init__(self):
        # key -> (Path | None, (width, height, x0, y0)) measured at _REF_SIZE
        self._cache = {}
        self._fp = FontProperties()
        self.builds = 0  # diagnostic: number of TextPath compilations performed

    def clear(self):
        self._cache.clear()

    def _get(self, text, usetex):
        key = (text, bool(usetex))
        entry = self._cache.get(key)
        if entry is not None:
            return entry

        path = None
        try:
            path = TextPath((0, 0), text, size=_REF_SIZE, prop=self._fp,
                            usetex=usetex)
            self.builds += 1
        except Exception:
            logger.exception("TextPath failed for %r (usetex=%s); "
                             "falling back to mathtext", text, usetex)
            if usetex:
                try:
                    path = TextPath((0, 0), text, size=_REF_SIZE, prop=self._fp,
                                    usetex=False)
                    self.builds += 1
                except Exception:
                    logger.exception("mathtext fallback also failed for %r", text)
                    path = None

        if path is not None:
            ext = path.get_extents()
            entry = (path, (ext.width, ext.height, ext.x0, ext.y0))
        else:
            entry = (None, (0.0, 0.0, 0.0, 0.0))
        self._cache[key] = entry
        return entry

    @staticmethod
    def _align_offsets(ha, va, w, h, x0, y0):
        """Offsets (in path units) that move the requested anchor to the origin."""
        if ha == 'left':
            ax_off = -x0
        elif ha == 'right':
            ax_off = -(x0 + w)
        else:  # center
            ax_off = -(x0 + w / 2.0)

        if va == 'bottom':
            ay_off = -y0
        elif va == 'top':
            ay_off = -(y0 + h)
        elif va == 'baseline':
            ay_off = 0.0
        else:  # center
            ay_off = -(y0 + h / 2.0)
        return ax_off, ay_off

    def draw(self, ax, text, x, y, fontsize_points, points_per_data_unit,
             color='black', rotation=0.0, ha='center', va='center',
             usetex=False, zorder=11, bgcolor=None, bgpad_frac=0.30, alpha=1.0):
        """Draw ``text`` anchored at data coordinates ``(x, y)``.

        Parameters mirror the relevant ``ax.text`` arguments:

        fontsize_points
            Target font size in points (same meaning as ``ax.text(fontsize=...)``).
        points_per_data_unit
            Current view's points-per-data-unit, used to scale the (point-sized)
            glyph path into data coordinates so it tracks zoom.
        rotation
            Degrees, counter-clockwise, about the anchor.
        bgcolor
            If given, a filled rounded-ish rectangle is drawn behind the text.

        Returns the list of artists added (so callers can track them if needed).
        """
        if not text:
            return []
        path, (w, h, x0, y0) = self._get(text, usetex)
        if path is None or w <= 0 or h <= 0:
            return []

        # points -> data units.  Path is built at _REF_SIZE points.
        scale_data = (fontsize_points / _REF_SIZE) / float(points_per_data_unit)
        ax_off, ay_off = self._align_offsets(ha, va, w, h, x0, y0)

        # translate so anchor -> origin, then rotate, scale to data, place at (x, y).
        trans = (Affine2D()
                 .translate(ax_off, ay_off)
                 .rotate_deg(rotation)
                 .scale(scale_data)
                 .translate(x, y)) + ax.transData

        artists = []
        if bgcolor is not None:
            pad = bgpad_frac * h
            rect = Rectangle((x0 - pad, y0 - pad), w + 2 * pad, h + 2 * pad,
                             facecolor=bgcolor, edgecolor='none', alpha=alpha,
                             zorder=zorder - 0.01)
            rect.set_transform(trans)
            ax.add_patch(rect)
            artists.append(rect)

        patch = PathPatch(path, facecolor=color, edgecolor='none', linewidth=0,
                          antialiased=True, alpha=alpha, zorder=zorder)
        patch.set_transform(trans)
        ax.add_patch(patch)
        artists.append(patch)
        return artists
