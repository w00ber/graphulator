"""Tests for the macOS pasteboard flavour list and how it reaches the writers.

A picky vector editor's Cmd+V path turned out to be sensitive to the *shape*
of the pasteboard, not just its contents: which UTIs are advertised, in what
order, and whether they arrive via the modern ``writeObjects:`` API or the
pre-10.6 ``declareTypes:owner:`` pair. These tests pin the flavour list and
the plumbing that hands it to each writer.

Nothing here touches the real pasteboard. The macOS writers are monkeypatched
and we assert on the ``(uti, payload)`` list they were handed -- writing to
NSPasteboard (or Qt's clipboard) from a test clobbers the developer's
clipboard and, worse, leaks into any later test that reads it back. Qt-free
(Agg).
"""

import ast
import xml.etree.ElementTree as ET

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

from graphulator import clipboard_export as ce  # noqa: E402

PDF = b"%PDF-fake"
SVG = b"<svg/>"
PNG = b"\x89PNG-fake"


def _utis(flavours):
    return [uti for uti, _ in flavours]


# ----------------------------------------------------------------------
# The flavour list itself
# ----------------------------------------------------------------------

def test_default_flavours_are_richest_first():
    """PDF, SVG (+ Adobe alias), raster PNG, then the SVG source as text.

    Pinned against the module defaults rather than a monkeypatched pair,
    because the *shipping* set is what a paste target sees. It matches the
    one flavour-for-flavour comparison that actually resolved this: a
    Diagrammer copy (pastes into VectorCraft) against a Graphulator copy
    (did not), identical but for the text flavour.
    """
    flavours = ce._pasteboard_flavours(PDF, SVG, PNG)
    assert _utis(flavours) == [
        "com.adobe.pdf",
        "public.svg-image",
        "com.adobe.svg",
        "public.png",
        "public.utf8-plain-text",
    ]
    assert dict(flavours)["com.adobe.svg"] == SVG


def test_svg_source_ships_as_plain_text():
    """The flavour VectorCraft's paste path reads. Do not drop it casually.

    Turning INCLUDE_SVG_AS_TEXT off is what made Cmd+V fail in VectorCraft;
    see the constant's comment for the trade-off it buys.
    """
    assert ce.INCLUDE_SVG_AS_TEXT is True
    flavours = ce._pasteboard_flavours(PDF, SVG, PNG)
    assert flavours[-1] == ("public.utf8-plain-text", SVG)


def test_alias_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(ce, "INCLUDE_SVG_ALIAS", False)
    monkeypatch.setattr(ce, "INCLUDE_SVG_AS_TEXT", False)
    assert _utis(ce._pasteboard_flavours(PDF, SVG, PNG)) == [
        "com.adobe.pdf", "public.svg-image", "public.png",
    ]


def test_text_flavour_goes_last(monkeypatch):
    """An app walking the types in order must see the artwork before source."""
    monkeypatch.setattr(ce, "INCLUDE_SVG_ALIAS", True)
    monkeypatch.setattr(ce, "INCLUDE_SVG_AS_TEXT", True)
    flavours = ce._pasteboard_flavours(PDF, SVG, PNG)
    assert _utis(flavours)[-1] == "public.utf8-plain-text"
    assert dict(flavours)["public.utf8-plain-text"] == SVG


def test_empty_svg_drops_every_svg_flavour(monkeypatch):
    """A failed SVG render must not promise data it cannot deliver."""
    monkeypatch.setattr(ce, "INCLUDE_SVG_ALIAS", True)
    monkeypatch.setattr(ce, "INCLUDE_SVG_AS_TEXT", True)
    assert _utis(ce._pasteboard_flavours(PDF, b"", PNG)) == [
        "com.adobe.pdf", "public.png",
    ]


def test_empty_png_drops_the_raster_flavour(monkeypatch):
    monkeypatch.setattr(ce, "INCLUDE_SVG_ALIAS", False)
    monkeypatch.setattr(ce, "INCLUDE_SVG_AS_TEXT", False)
    assert _utis(ce._pasteboard_flavours(PDF, SVG, b"")) == [
        "com.adobe.pdf", "public.svg-image",
    ]


def test_no_payloads_yields_no_flavours():
    assert ce._pasteboard_flavours(b"", b"", b"") == []


def test_payloads_are_plain_bytes():
    """memoryview/bytearray payloads are normalised; ObjC needs real bytes."""
    flavours = ce._pasteboard_flavours(bytearray(PDF), b"", b"")
    assert flavours == [("com.adobe.pdf", PDF)]
    assert isinstance(flavours[0][1], bytes)


# ----------------------------------------------------------------------
# The MIME-name aliases
# ----------------------------------------------------------------------

def test_mime_aliases_are_svg_then_pdf(monkeypatch):
    """SVG first so a vector-preferring reader meets the SVG before the PDF."""
    monkeypatch.setattr(ce, "INCLUDE_MIME_ALIASES", True)
    assert ce._mime_aliases(PDF, SVG) == [
        ("image/svg+xml", SVG),
        ("application/pdf", PDF),
    ]


def test_mime_aliases_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(ce, "INCLUDE_MIME_ALIASES", False)
    assert ce._mime_aliases(PDF, SVG) == []


def test_mime_aliases_skip_missing_payloads(monkeypatch):
    monkeypatch.setattr(ce, "INCLUDE_MIME_ALIASES", True)
    assert ce._mime_aliases(PDF, b"") == [("application/pdf", PDF)]
    assert ce._mime_aliases(b"", SVG) == [("image/svg+xml", SVG)]
    assert ce._mime_aliases(b"", b"") == []


def test_mime_names_are_deliberately_not_utis():
    """These must not be moved onto the item: AppKit rejects non-UTI names.

    If someone "tidies" these into _pasteboard_flavours, the item-level
    setData:forType: refuses them and the aliases silently vanish. Pinning the
    shape here so that refactor fails loudly instead.
    """
    uti_names = _utis(ce._pasteboard_flavours(PDF, SVG, PNG))
    for name, _payload in ce._mime_aliases(PDF, SVG):
        assert "/" in name, f"{name} looks like a UTI, not a MIME name"
        assert name not in uti_names


# ----------------------------------------------------------------------
# How the list reaches the writers
# ----------------------------------------------------------------------

def _tiny_figure():
    fig, ax = plt.subplots(figsize=(1, 1))
    ax.plot([0, 1], [0, 1])
    return fig


def test_copy_passes_flavours_and_aliases_to_the_ctypes_writer(monkeypatch):
    """The ctypes path is tried first and gets both lists, nothing else."""
    monkeypatch.setattr(ce.sys, "platform", "darwin")
    monkeypatch.setattr(ce, "INCLUDE_SVG_ALIAS", True)
    monkeypatch.setattr(ce, "INCLUDE_SVG_AS_TEXT", True)
    monkeypatch.setattr(ce, "INCLUDE_MIME_ALIASES", True)

    seen = {}

    def fake_ctypes(flavours, mime_aliases=()):
        seen["flavours"] = flavours
        seen["aliases"] = mime_aliases
        return _utis(flavours) + _utis(mime_aliases)

    monkeypatch.setattr(ce, "_copy_macos_ctypes", fake_ctypes)
    monkeypatch.setattr(ce, "_copy_macos_pyobjc", _unreachable)
    monkeypatch.setattr(ce, "_copy_macos_subprocess", _unreachable)
    monkeypatch.setattr(ce, "_copy_qt", _unreachable)

    fig = _tiny_figure()
    try:
        backend, placed = ce.copy_figure_to_clipboard(fig, png_dpi=36)
    finally:
        plt.close(fig)

    assert backend == "native"
    assert placed == [
        "com.adobe.pdf", "public.svg-image", "com.adobe.svg", "public.png",
        "public.utf8-plain-text", "image/svg+xml", "application/pdf",
    ]
    assert all(payload for _name, payload in seen["flavours"])
    assert all(payload for _name, payload in seen["aliases"])


def test_mime_aliases_carry_the_same_bytes_as_their_utis(monkeypatch):
    """An alias that disagreed with its UTI would paste two different graphs."""
    monkeypatch.setattr(ce.sys, "platform", "darwin")
    monkeypatch.setattr(ce, "INCLUDE_MIME_ALIASES", True)

    seen = {}

    def fake_ctypes(flavours, mime_aliases=()):
        seen.update(flavours=dict(flavours), aliases=dict(mime_aliases))
        return []

    monkeypatch.setattr(ce, "_copy_macos_ctypes", fake_ctypes)
    monkeypatch.setattr(ce, "_copy_qt", _unreachable)

    fig = _tiny_figure()
    try:
        ce.copy_figure_to_clipboard(fig, png_dpi=36)
    finally:
        plt.close(fig)

    assert seen["aliases"]["image/svg+xml"] == seen["flavours"]["public.svg-image"]
    assert seen["aliases"]["application/pdf"] == seen["flavours"]["com.adobe.pdf"]


def test_include_png_false_drops_the_png_flavour(monkeypatch):
    monkeypatch.setattr(ce.sys, "platform", "darwin")
    monkeypatch.setattr(ce, "_copy_macos_ctypes",
                        lambda flavours, mime_aliases=(): _utis(flavours))
    monkeypatch.setattr(ce, "_copy_qt", _unreachable)

    fig = _tiny_figure()
    try:
        _backend, placed = ce.copy_figure_to_clipboard(fig, include_png=False)
    finally:
        plt.close(fig)

    assert "public.png" not in placed


def test_pyobjc_is_tried_when_ctypes_fails(monkeypatch):
    monkeypatch.setattr(ce.sys, "platform", "darwin")

    def boom(flavours, mime_aliases=()):
        raise RuntimeError("no objc here")

    monkeypatch.setattr(ce, "_copy_macos_ctypes", boom)
    monkeypatch.setattr(ce, "_copy_macos_pyobjc",
                        lambda flavours, mime_aliases=(): _utis(flavours))
    monkeypatch.setattr(ce, "_copy_macos_subprocess", _unreachable)
    monkeypatch.setattr(ce, "_copy_qt", _unreachable)

    fig = _tiny_figure()
    try:
        backend, placed = ce.copy_figure_to_clipboard(fig, png_dpi=36)
    finally:
        plt.close(fig)

    assert backend == "native"
    assert ce.last_clipboard_method == "native (PyObjC)"
    assert "com.adobe.pdf" in placed


def _unreachable(*args, **kwargs):
    raise AssertionError("later clipboard fallback should not have been reached")


# ----------------------------------------------------------------------
# The subprocess script
# ----------------------------------------------------------------------

def test_pasteboard_script_formats_into_valid_python():
    """The script is injected with str.format, so a stray brace breaks it.

    Any literal ``{`` or ``}`` added to _PASTEBOARD_SCRIPT must be doubled;
    this catches the one that was not.
    """
    pairs = [("com.adobe.pdf", "/tmp/a.bin"), ("public.svg-image", "/tmp/b.bin")]
    aliases = [("image/svg+xml", "/tmp/c.bin")]
    script = ce._PASTEBOARD_SCRIPT.format(flavours=repr(pairs),
                                          mime_aliases=repr(aliases))
    ast.parse(script)
    assert "writeObjects_" in script
    assert "addTypes_owner_" in script
    assert "declareTypes" not in script


def test_subprocess_writer_reports_nothing_for_an_empty_list():
    assert ce._copy_macos_subprocess([], []) == (None, [])


# ----------------------------------------------------------------------
# The SVG payload itself
# ----------------------------------------------------------------------

def test_rendered_svg_carries_no_doctype():
    """matplotlib emits a DOCTYPE; we strip it before anyone sees the SVG.

    Defensive, not load-bearing: the Rust SVG stack (roxmltree -> usvg ->
    resvg) rejects a document with a DTD unless the caller opts in, failing
    with "XML with DTD detected". VectorCraft opts in and was never bothered
    by it, but an editor on the same stack that did not would refuse our SVG
    outright.
    """
    fig = _tiny_figure()
    try:
        _pdf, svg, _png = ce.render_figure_formats(fig, png_dpi=36)
    finally:
        plt.close(fig)

    assert b"DOCTYPE" not in svg
    assert b"svg11.dtd" not in svg
    assert svg.lstrip().startswith(b"<?xml")
    ET.fromstring(svg)  # still well-formed, and still an svg document


def test_strip_doctype_leaves_a_clean_document():
    src = (b'<?xml version="1.0" encoding="utf-8" standalone="no"?>\n'
           b'<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN"\n'
           b'  "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">\n'
           b'<svg xmlns="http://www.w3.org/2000/svg"/>')
    out = ce._strip_svg_doctype(src)
    assert b"DOCTYPE" not in out
    assert out == (b'<?xml version="1.0" encoding="utf-8" standalone="no"?>\n'
                   b'<svg xmlns="http://www.w3.org/2000/svg"/>')


def test_strip_doctype_handles_an_internal_subset():
    """A '>' inside the internal subset must not truncate the declaration."""
    src = b'<!DOCTYPE svg [\n<!ENTITY gt_in_here "b>c">\n]>\n<svg/>'
    assert ce._strip_svg_doctype(src) == b"<svg/>"


def test_strip_doctype_is_a_noop_without_one():
    src = b'<?xml version="1.0"?>\n<svg><!-- DOCTYPE in a comment --></svg>'
    assert ce._strip_svg_doctype(src) == src
