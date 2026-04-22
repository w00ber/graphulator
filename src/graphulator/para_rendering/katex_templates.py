"""
KaTeX HTML templates for Graphulator.

Consolidates the duplicated HTML template code used for rendering
matrices, basis vectors, and other mathematical content with KaTeX.
"""

import html as html_module


def render_matrix_html(latex_str: str, katex_header: str, context_menu_js: str,
                       label_prefix: str = "M", container_id: str = "matrix-container",
                       content_id: str = "matrix-content") -> str:
    """Generate HTML for rendering a LaTeX matrix with KaTeX.

    Consolidates the duplicated HTML generation from _update_matrix_display()
    and _update_kron_matrix_display().

    Args:
        latex_str: The LaTeX string to render.
        katex_header: The KaTeX CSS/JS includes HTML.
        context_menu_js: The right-click copy LaTeX context menu JS/CSS.
        label_prefix: Display label before the matrix (e.g. "M", "M_{\\text{Kron}}").
        container_id: HTML id for the scrollable container div.
        content_id: HTML id for the content div.

    Returns:
        Complete HTML string ready for setHtml().
    """
    latex_for_attr = html_module.escape(latex_str, quote=True)

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        {katex_header}
        {context_menu_js}
        <script>
        // Arrow key panning
        document.addEventListener('keydown', (e) => {{
          const container = document.getElementById('{container_id}');
          if (!container) return;

          const step = 50; // pixels to scroll per keypress

          switch(e.key) {{
            case 'ArrowUp':
              container.scrollTop -= step;
              e.preventDefault();
              break;
            case 'ArrowDown':
              container.scrollTop += step;
              e.preventDefault();
              break;
            case 'ArrowLeft':
              container.scrollLeft -= step;
              e.preventDefault();
              break;
            case 'ArrowRight':
              container.scrollLeft += step;
              e.preventDefault();
              break;
          }}
        }});
        </script>
        <style>
            html, body {{
                margin: 0;
                padding: 0;
                width: 100%;
                height: 100%;
                overflow: hidden;
            }}
            body {{
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 10px;
                box-sizing: border-box;
            }}
            #{container_id} {{
                width: 100%;
                height: 100%;
                overflow: auto;
                display: flex;
                justify-content: flex-start;
                align-items: flex-start;
                padding: 10px;
            }}
            #{content_id} {{
                /* Content will be positioned at top-left, allowing proper scrolling */
                margin: auto;  /* Center when smaller than container */
            }}
        </style>
    </head>
    <body>
        <div id="{container_id}">
            <div id="{content_id}" data-latex="{latex_for_attr}">${label_prefix} = \\\\\\\\ {latex_str}$</div>
        </div>
        <script>
            document.addEventListener("DOMContentLoaded", function() {{
                renderMathInElement(document.body, {{
                    delimiters: [
                        {{left: "$$", right: "$$", display: true}},
                        {{left: "$", right: "$", display: false}},
                        {{left: "\\\\(", right: "\\\\)", display: false}},
                        {{left: "\\\\[", right: "\\\\]", display: true}}
                    ],
                    throwOnError: false
                }});
            }});
        </script>
    </body>
    </html>
    """


def render_basis_html(latex_str: str, katex_header: str, context_menu_js: str) -> str:
    """Generate HTML for rendering a basis vector with KaTeX.

    Args:
        latex_str: The LaTeX string to render.
        katex_header: The KaTeX CSS/JS includes HTML.
        context_menu_js: The right-click copy LaTeX context menu JS/CSS.

    Returns:
        Complete HTML string ready for setHtml().
    """
    latex_for_attr = html_module.escape(latex_str, quote=True)

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        {katex_header}
        {context_menu_js}
        <style>
            html, body {{
                margin: 0;
                padding: 0;
                width: 100%;
                height: 100%;
                overflow: auto;
            }}
            body {{
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 20px;
                box-sizing: border-box;
                font-size: 16px;
            }}
            #basis-content {{
                margin: auto;
            }}
        </style>
    </head>
    <body>
        <div id="basis-content" data-latex="{latex_for_attr}">${latex_str}$</div>
        <script>
            renderMathInElement(document.body, {{
                delimiters: [
                    {{left: "$$", right: "$$", display: true}},
                    {{left: "$", right: "$", display: false}}
                ],
                throwOnError: false
            }});
        </script>
    </body>
    </html>
    """


def render_placeholder_html(message: str, color: str = "#666") -> str:
    """Generate simple placeholder HTML for empty states.

    Replaces the duplicated inline HTML for "No nodes yet",
    "Initializing...", error messages, etc.

    Args:
        message: The message to display (can include HTML tags).
        color: Text color (default gray).

    Returns:
        Complete HTML string.
    """
    return f"""
    <!DOCTYPE html>
    <html><body style='margin:0; padding:20px; display:flex; justify-content:center;
    align-items:center; min-height:100vh; font-family:sans-serif; color:{color};
    text-align:center;'>
    <div>{message}</div>
    </body></html>
    """
