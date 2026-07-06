"""Floating, context-sensitive keyboard-shortcut hint panel.

An optional cheat-sheet that lowers the learning curve for the keyboard-driven
workflow: it shows a curated set of the shortcuts relevant to the current
selection (nothing / node / coupling edge / self-loop) in a chosen corner of
the canvas.

The panel is a plain Qt widget parented to the matplotlib canvas widget, so it
is layered *over* the plot but is never part of the figure -- it can't appear
in PNG/SVG/PDF exports or clipboard copies (those are rendered from the figure,
not from Qt children). It repositions itself when the canvas resizes and never
takes focus, so it never interferes with typing or single-key shortcuts.

The widget is content-agnostic: each app feeds it ``(keys, label)`` rows for the
current context via :meth:`ShortcutOverlay.set_rows`. Key resolution differs per
app (Paragraphulator reads its remappable ShortcutManager; Graphulator uses a
static table), which is why the content lives in the apps, not here.
"""

import logging

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)

# Corner keyword -> (anchor to the right?, anchor to the bottom?)
_CORNERS = {
    "top-left": (False, False),
    "top-right": (True, False),
    "bottom-left": (False, True),
    "bottom-right": (True, True),
}

_MARGIN = 12  # px inset from the canvas edge


class ShortcutOverlay(QWidget):
    """A small translucent panel of context-relevant shortcut hints."""

    def __init__(self, canvas):
        super().__init__(canvas)
        self._canvas = canvas
        self._corner = "top-right"
        self.setObjectName("shortcutOverlay")
        # Never steal focus (matches the canvas), so single-key shortcuts and
        # text fields keep working while it is visible.
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(0)
        self._label = QLabel(self)
        self._label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self._label)

        # objectName-scoped stylesheet so it doesn't bleed onto child labels of
        # other widgets; translucent so the graph shows through faintly.
        self.setStyleSheet(
            "#shortcutOverlay {"
            "  background-color: rgba(250, 250, 250, 235);"
            "  border: 1px solid rgba(0, 0, 0, 40);"
            "  border-radius: 8px;"
            "}"
        )
        # Reposition whenever the canvas resizes.
        canvas.installEventFilter(self)
        self.hide()

    # ---- public API ---------------------------------------------------

    def set_corner(self, corner):
        """Set the anchor corner ('top-left'|'top-right'|'bottom-left'|'bottom-right')."""
        if corner in _CORNERS:
            self._corner = corner
            self._reposition()

    def set_rows(self, title, rows):
        """Populate with a context title and ``[(keys, label), ...]`` rows.

        Hides the panel when there are no rows.
        """
        if not rows:
            self.hide()
            return
        body = "".join(
            "<tr>"
            f"<td style='padding:1px 10px 1px 0; white-space:nowrap;'>"
            f"<span style='font-family:monospace; font-weight:bold;'>{keys}</span></td>"
            f"<td style='padding:1px 0;'>{label}</td>"
            "</tr>"
            for keys, label in rows
        )
        html = (
            f"<div style='font-weight:bold; padding-bottom:4px;'>{title}</div>"
            f"<table style='border-collapse:collapse;'>{body}</table>"
        )
        self._label.setText(html)
        self.adjustSize()
        self._reposition()

    # ---- internals ----------------------------------------------------

    def _reposition(self):
        parent = self.parentWidget()
        if parent is None:
            return
        right, bottom = _CORNERS.get(self._corner, (True, False))
        pw, ph = parent.width(), parent.height()
        w, h = self.width(), self.height()
        x = pw - w - _MARGIN if right else _MARGIN
        y = ph - h - _MARGIN if bottom else _MARGIN
        self.move(max(_MARGIN, x), max(_MARGIN, y))

    def eventFilter(self, obj, event):
        if obj is self._canvas and event.type() == QEvent.Type.Resize:
            self._reposition()
        return super().eventFilter(obj, event)

    def showEvent(self, event):
        super().showEvent(event)
        self._reposition()
        self.raise_()
