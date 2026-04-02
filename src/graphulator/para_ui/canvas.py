"""
Matplotlib canvas widget for paragraphulator.

This module contains the MplCanvas class for embedding matplotlib in Qt.
"""

from PySide6.QtCore import Signal, Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class MplCanvas(FigureCanvas):
    """Matplotlib canvas for embedding in Qt"""

    # Custom signals
    click_signal = Signal(object)
    release_signal = Signal(object)
    motion_signal = Signal(object)
    scroll_signal = Signal(object)

    def __init__(self, parent=None, width=12, height=12, dpi=100, show_axes=False):
        self.fig = Figure(figsize=(width, height), dpi=dpi)

        if show_axes:
            # For plot canvases - use tight_layout to prevent label cutoff
            self.ax = self.fig.add_subplot(111)
            self.fig.set_tight_layout(True)
        else:
            # For graph canvases - remove all margins, make axes fill entire figure
            self.fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
            self.ax = self.fig.add_subplot(111)
            # Remove any padding around the axes
            self.ax.set_position([0, 0, 1, 1])  # [left, bottom, width, height] in figure coordinates

        super().__init__(self.fig)

        # Prevent canvas from participating in tab focus chain
        # Use NoFocus so Tab key moves between spinboxes, not to canvas
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Connect matplotlib events to Qt signals
        self.mpl_connect('button_press_event', self._on_click)
        self.mpl_connect('button_release_event', self._on_release)
        self.mpl_connect('motion_notify_event', self._on_motion)
        self.mpl_connect('scroll_event', self._on_scroll)

    def _on_click(self, event):
        self.click_signal.emit(event)

    def _on_release(self, event):
        self.release_signal.emit(event)

    def _on_motion(self, event):
        self.motion_signal.emit(event)

    def _on_scroll(self, event):
        self.scroll_signal.emit(event)
