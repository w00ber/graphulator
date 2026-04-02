"""
Web view widgets for paragraphulator.

This module contains the ZoomableWebView class for displaying KaTeX-rendered content.
"""

from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QTimer, QEvent, Qt
from PySide6.QtWidgets import QMenu, QWidget
from PySide6.QtGui import QAction
from PySide6.QtWebEngineCore import QWebEnginePage


class ZoomableWebView(QWebEngineView):
    """QWebEngineView with keyboard zoom support

    Keyboard shortcuts (when Matrix/Basis view has focus):
    - Cmd+Plus (or Cmd+=): Zoom in
    - Cmd+Minus: Zoom out
    - Cmd+0: Reset zoom to default

    Trackpad pinch-to-zoom also works via Chromium's built-in support.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # Set default zoom slightly larger for better readability
        self.setZoomFactor(1.25)
        self.default_zoom = 1.25
        # LaTeX content for copy functionality
        self._latex_content = None
        # Install event filter on child widgets to catch right-clicks
        # QWebEngineView's mouse events go to an internal child widget
        QTimer.singleShot(0, self._install_event_filter_on_children)

    def _install_event_filter_on_children(self):
        """Install event filter on the internal widget that receives mouse events"""
        for child in self.findChildren(QWidget):
            child.installEventFilter(self)
        if self.focusProxy():
            self.focusProxy().installEventFilter(self)

    def eventFilter(self, obj, event):
        """Filter events to catch right-clicks before web engine handles them"""
        if event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.RightButton:
                self._show_custom_context_menu(event.globalPosition().toPoint())
                return True
        return super().eventFilter(obj, event)

    def setLatexContent(self, latex_str):
        """Set the LaTeX content that can be copied via context menu"""
        self._latex_content = latex_str

    def _show_custom_context_menu(self, global_pos):
        """Show custom context menu with Copy LaTeX option"""
        menu = QMenu(self)

        # Add Copy LaTeX option if we have content
        if self._latex_content:
            copy_latex_action = QAction("Copy LaTeX", self)
            copy_latex_action.triggered.connect(self._copy_latex_to_clipboard)
            menu.addAction(copy_latex_action)
            menu.addSeparator()

        # Add standard web view actions
        menu.addAction(self.pageAction(QWebEnginePage.WebAction.Copy))
        menu.addAction(self.pageAction(QWebEnginePage.WebAction.SelectAll))

        menu.exec(global_pos)

    def _copy_latex_to_clipboard(self):
        """Copy the LaTeX content to clipboard using Qt"""
        from PySide6.QtWidgets import QApplication
        if self._latex_content:
            QApplication.clipboard().setText(self._latex_content)

    def zoom_in(self):
        """Zoom in by 25%"""
        current = self.zoomFactor()
        new_zoom = current * 1.25  # Removed cap to allow unlimited zoom
        self.setZoomFactor(new_zoom)
        print(f"[ZoomableWebView] Zoom IN: {new_zoom:.2f}x")

    def zoom_out(self):
        """Zoom out by 25%"""
        current = self.zoomFactor()
        new_zoom = max(current / 1.25, 0.1)  # Lowered minimum to 0.1x
        self.setZoomFactor(new_zoom)
        print(f"[ZoomableWebView] Zoom OUT: {new_zoom:.2f}x")

    def reset_zoom(self):
        """Reset zoom to default"""
        self.setZoomFactor(self.default_zoom)
        print(f"[ZoomableWebView] Zoom RESET to {self.default_zoom:.2f}x")
