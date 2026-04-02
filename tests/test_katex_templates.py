"""Tests for the KaTeX HTML template functions."""

import pytest

from graphulator.para_rendering.katex_templates import (
    render_matrix_html,
    render_basis_html,
    render_placeholder_html,
)


class TestRenderPlaceholderHtml:
    """Tests for render_placeholder_html."""

    def test_basic_message(self):
        """Generates valid HTML with the given message."""
        html = render_placeholder_html("Hello world")
        assert "Hello world" in html
        assert "<!DOCTYPE html>" in html
        assert "<body" in html

    def test_custom_color(self):
        """Respects custom color parameter."""
        html = render_placeholder_html("Error!", color="red")
        assert "red" in html
        assert "Error!" in html

    def test_default_color(self):
        """Default color is gray (#666)."""
        html = render_placeholder_html("test")
        assert "#666" in html

    def test_html_in_message(self):
        """HTML tags in the message are preserved."""
        html = render_placeholder_html("Line 1<br>Line 2")
        assert "Line 1<br>Line 2" in html


class TestRenderMatrixHtml:
    """Tests for render_matrix_html."""

    def test_basic_rendering(self):
        """Generates complete HTML with KaTeX rendering."""
        html = render_matrix_html(
            r"\begin{bmatrix} a & b \\ c & d \end{bmatrix}",
            "<script>katex</script>",
            "<script>menu</script>",
            label_prefix="M"
        )
        assert "<!DOCTYPE html>" in html
        assert "katex" in html
        assert "matrix-container" in html
        assert "matrix-content" in html
        assert "renderMathInElement" in html

    def test_custom_label_prefix(self):
        """Label prefix appears in the output."""
        html = render_matrix_html(
            "x",
            "",
            "",
            label_prefix=r"M_{\text{Kron}}"
        )
        assert "Kron" in html

    def test_latex_escaped_in_attribute(self):
        """LaTeX content is HTML-escaped in data-latex attribute."""
        html = render_matrix_html(
            'a "quoted" & <special>',
            "",
            "",
        )
        assert 'data-latex="' in html
        assert "&amp;" in html  # & should be escaped

    def test_arrow_key_panning(self):
        """Arrow key panning JavaScript is included."""
        html = render_matrix_html("x", "", "")
        assert "ArrowUp" in html
        assert "ArrowDown" in html
        assert "ArrowLeft" in html
        assert "ArrowRight" in html


class TestRenderBasisHtml:
    """Tests for render_basis_html."""

    def test_basic_rendering(self):
        """Generates complete HTML for basis vector."""
        html = render_basis_html(
            r"\begin{bmatrix} a \\ b \end{bmatrix}",
            "<script>katex</script>",
            "<script>menu</script>"
        )
        assert "<!DOCTYPE html>" in html
        assert "basis-content" in html
        assert "renderMathInElement" in html

    def test_latex_content_included(self):
        """LaTeX string is included in the output."""
        latex = r"\begin{bmatrix} x \\ y \end{bmatrix}"
        html = render_basis_html(latex, "", "")
        assert "bmatrix" in html
