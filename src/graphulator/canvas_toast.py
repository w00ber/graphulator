"""A transient message panel laid over the canvas.

For things the user needs to SEE happen but should not have to go looking
for: an image copied to the paste buffer, say, where the status bar is too
far from where the eye is and too easy to miss, and a modal dialog would be
absurd.

Built the same way as :mod:`shortcut_overlay`: a plain Qt widget parented to
the matplotlib canvas widget, so it is layered *over* the plot but is never
part of the figure. That matters here more than anywhere -- the exports are
rendered from the figure, so a toast announcing an export can never end up
inside the very image it is announcing.

It takes no focus and no mouse events, repositions itself when the canvas
resizes, and hides itself again after a timeout.
"""

import logging

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)

# Corner keyword -> (anchor to the right?, anchor to the bottom?)
_CORNERS = {
    "top-left": (False, False),
    "top-right": (True, False),
    "bottom-left": (False, True),
    "bottom-right": (True, True),
}

_MARGIN = 12    # px inset from the canvas edge
_GAP = 8        # px between the toast and a panel it has to clear

#: How long a flash stays up, in milliseconds, when the caller names nothing.
DEFAULT_DURATION_MS = 2600


class CanvasToast(QWidget):
    """A small translucent panel that appears, says one thing, and leaves."""

    def __init__(self, canvas, corner="top-right", avoid=None):
        """`avoid` is an optional callable returning a sibling widget that
        the toast should sit clear of when both are in the same corner --
        the shortcut overlay, which shares this corner by default."""
        super().__init__(canvas)
        self._canvas = canvas
        self._corner = corner if corner in _CORNERS else "top-right"
        self._avoid = avoid
        self.setObjectName("canvasToast")
        # Never steal focus (matches the canvas), so single-key shortcuts
        # and text fields keep working while it is visible.
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(0)
        self._label = QLabel(self)
        self._label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._label.setTextFormat(Qt.TextFormat.RichText)
        # Pin the text light: the panel background is always dark, so
        # without this the text follows the system palette and turns black
        # (unreadable) under macOS light mode.
        self._label.setStyleSheet("color: #f5f5f5;")
        layout.addWidget(self._label)

        # objectName-scoped so it does not bleed onto other widgets' child
        # labels. Dark, unlike the shortcut overlay: a toast is a a brief
        # notice and reads as one at a glance, rather than as another panel.
        self.setStyleSheet(
            "#canvasToast {"
            "  background-color: rgba(28, 32, 38, 225);"
            "  border: 1px solid rgba(255, 255, 255, 40);"
            "  border-radius: 8px;"
            "}"
        )

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

        canvas.installEventFilter(self)
        self.hide()

    # ---- public API ---------------------------------------------------

    def set_corner(self, corner):
        """Anchor corner ('top-left'|'top-right'|'bottom-left'|'bottom-right')."""
        if corner in _CORNERS:
            self._corner = corner
            self._reposition()

    def flash(self, title, detail=None, msec=None):
        """Show `title` (bold) over an optional dimmer `detail` line.

        Re-flashing restarts the clock rather than queueing, so a run of
        copies in quick succession reads as one message that keeps up.
        """
        html = f"<div style='font-weight:bold;'>{title}</div>"
        if detail:
            html += ("<div style='padding-top:2px; color:#b9c0cc;'>"
                     f"{detail}</div>")
        self._label.setText(html)
        self.adjustSize()
        self._clamp_to_parent()
        self._reposition()
        self.show()
        self.raise_()
        self._timer.start(int(msec if msec is not None
                              else DEFAULT_DURATION_MS))

    # ---- internals ----------------------------------------------------

    def _clamp_to_parent(self):
        """Keep the panel inside the canvas, however long the text is."""
        parent = self.parentWidget()
        if parent is None:
            return
        max_h = max(40, parent.height() - 2 * _MARGIN)
        max_w = max(80, parent.width() - 2 * _MARGIN)
        if self.height() > max_h or self.width() > max_w:
            self.resize(min(self.width(), max_w), min(self.height(), max_h))

    def _avoided_rect(self):
        """Geometry of the sibling panel to clear, if there is one up."""
        if self._avoid is None:
            return None
        try:
            other = self._avoid()
        except Exception:
            logger.debug("Toast avoid() failed", exc_info=True)
            return None
        # isHidden(), not isVisible(): a child of a window that has not
        # been shown yet still reports isVisible() False, and the toast
        # would then stack straight on top of a panel that is about to
        # appear beside it.
        if other is None or other is self or other.isHidden():
            return None
        return other.geometry()

    def _reposition(self):
        parent = self.parentWidget()
        if parent is None:
            return
        right, bottom = _CORNERS.get(self._corner, (True, False))
        pw, ph = parent.width(), parent.height()
        w, h = self.width(), self.height()
        x = pw - w - _MARGIN if right else _MARGIN
        y = ph - h - _MARGIN if bottom else _MARGIN

        # Stack clear of a panel already occupying this corner, so the two
        # never sit on top of each other.
        other = self._avoided_rect()
        if other is not None and other.right() >= x and other.left() <= x + w:
            if bottom:
                y = min(y, other.top() - _GAP - h)
            else:
                y = max(y, other.bottom() + _GAP)
        self.move(max(_MARGIN, x), max(_MARGIN, y))

    def eventFilter(self, obj, event):
        if obj is self._canvas and event.type() == QEvent.Type.Resize:
            self._reposition()
        return super().eventFilter(obj, event)

    def showEvent(self, event):
        super().showEvent(event)
        self._reposition()
        self.raise_()
