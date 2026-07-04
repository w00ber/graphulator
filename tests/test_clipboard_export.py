"""Tests for clipboard/PDF export opacity handling.

matplotlib encodes a patch's ``alpha`` as SVG ``opacity``, but PyMuPDF's
SVG->PDF conversion drops it, so a dimmed conjugated node (or any other
semi-transparent art) rendered fully opaque in the preferred PDF clipboard
flavour. ``clipboard_export`` now bakes the opacity into the fill/stroke color
over white before conversion. These tests pin that behavior. Qt-free (Agg).
"""

import matplotlib

matplotlib.use("Agg")

import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402

from graphulator import clipboard_export as ce  # noqa: E402

fitz = pytest.importorskip("fitz")  # PyMuPDF; the declared SVG->PDF backend


def test_blend_over_white_half():
    # indianred #cd5c5c at 0.5 over white -> #e6aeae
    assert ce._blend_over_white("#cd5c5c", 0.5) == "#e6aeae"
    # alpha 1.0 is a no-op
    assert ce._blend_over_white("#cd5c5c", 1.0) == "#cd5c5c"


def test_bake_folds_fill_opacity_and_drops_key():
    svg = b'<path style="fill: #cd5c5c; opacity: 0.5"/>'
    out = ce._bake_svg_opacity(svg).decode()
    assert "#e6aeae" in out
    assert "opacity" not in out


def test_bake_folds_stroke_opacity():
    svg = b'<path style="fill: none; opacity: 0.5; stroke: #4682b4; stroke-width: 3"/>'
    out = ce._bake_svg_opacity(svg).decode()
    # steelblue #4682b4 at 0.5 over white
    assert ce._blend_over_white("#4682b4", 0.5) in out
    assert "opacity" not in out
    assert "fill: none" in out  # fill left alone


def test_bake_is_noop_without_opacity():
    svg = b'<path style="fill: #cd5c5c; stroke: none"/>'
    assert ce._bake_svg_opacity(svg) == svg


def test_bake_skips_non_hex_color():
    # A non-#rrggbb fill is left untouched rather than mangled
    svg = b'<path style="fill: url(#grad); opacity: 0.5"/>'
    out = ce._bake_svg_opacity(svg).decode()
    assert "url(#grad)" in out


def _center_rgb_from_pdf(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(4, 4), alpha=False)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
    return arr[pix.h // 2, pix.w // 2][:3]


def test_pdf_export_preserves_dimmed_transparency():
    """End-to-end: a dimmed (alpha=0.5) node exports as its blended-over-white
    color in the PDF flavour, not the solid color (the bug reproduction)."""
    fig, ax = plt.subplots(figsize=(2, 2))
    ax.add_patch(mpatches.Circle((0.5, 0.5), 0.45, facecolor="indianred",
                                 edgecolor="none", alpha=0.5))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    pdf_bytes, _svg, _png = ce.render_figure_formats(fig)
    r, g, b = _center_rgb_from_pdf(pdf_bytes)
    plt.close(fig)

    # Solid indianred is (205, 92, 92); half-over-white is ~(230, 174, 174).
    # The green channel cleanly separates the two (92 vs 174).
    assert g > 140, f"dimmed node exported opaque: center RGB=({r},{g},{b})"


def test_pdf_export_keeps_solid_node_solid():
    fig, ax = plt.subplots(figsize=(2, 2))
    ax.add_patch(mpatches.Circle((0.5, 0.5), 0.45, facecolor="indianred",
                                 edgecolor="none"))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    pdf_bytes, _svg, _png = ce.render_figure_formats(fig)
    r, g, b = _center_rgb_from_pdf(pdf_bytes)
    plt.close(fig)

    # Stays solid indianred (~205, 92, 92): green channel near 92, not blended.
    assert g < 130, f"solid node unexpectedly lightened: center RGB=({r},{g},{b})"


def test_svg_flavour_keeps_true_alpha():
    """The SVG clipboard flavour is untouched (true alpha survives there)."""
    fig, ax = plt.subplots(figsize=(2, 2))
    ax.add_patch(mpatches.Circle((0.5, 0.5), 0.45, facecolor="indianred",
                                 edgecolor="none", alpha=0.5))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    _pdf, svg_bytes, _png = ce.render_figure_formats(fig)
    plt.close(fig)
    assert b"opacity: 0.5" in svg_bytes
