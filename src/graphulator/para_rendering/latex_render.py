"""
LaTeX rendering utilities for paragraphulator.

This module contains background workers and utilities for rendering LaTeX.
"""

import io
import traceback

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QPixmap


class MatrixRenderWorker(QThread):
    """Worker thread for rendering LaTeX matrix asynchronously"""

    # Signal emitted when rendering completes (sends QPixmap)
    render_complete = Signal(object)

    def __init__(self, latex_str):
        super().__init__()
        self.latex_str = latex_str

    def run(self):
        """Render the LaTeX to a pixmap in background thread"""
        import matplotlib
        import matplotlib.pyplot as plt
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg

        # Save original settings
        old_usetex = matplotlib.rcParams['text.usetex']
        old_preamble = matplotlib.rcParams.get('text.latex.preamble', '')

        try:
            # Ensure LaTeX rendering is enabled in this thread
            matplotlib.rcParams['text.usetex'] = True
            matplotlib.rcParams['text.latex.preamble'] = r'\usepackage{amsmath}'

            # Create figure with transparent background
            fig = Figure(figsize=(8, max(3, len(self.latex_str) / 50)))
            fig.patch.set_alpha(0.0)  # Transparent figure background

            ax = fig.add_subplot(111)
            ax.axis('off')
            ax.patch.set_alpha(0.0)  # Transparent axes background
            ax.text(0.5, 0.5, f'${self.latex_str}$',
                   fontsize=12, ha='center', va='center')

            # Render to buffer
            canvas = FigureCanvasAgg(fig)
            buf = io.BytesIO()
            canvas.print_figure(buf, format='png', bbox_inches='tight', dpi=150)
            buf.seek(0)

            # Close figure
            plt.close(fig)

            # Convert to QPixmap
            pixmap = QPixmap()
            pixmap.loadFromData(buf.read())

            # Emit the result
            self.render_complete.emit(pixmap)

        except Exception as e:
            # On error, emit None to trigger fallback
            print(f"Matrix render error: {e}")
            traceback.print_exc()
            self.render_complete.emit(None)

        finally:
            # Restore original settings
            matplotlib.rcParams['text.usetex'] = old_usetex
            matplotlib.rcParams['text.latex.preamble'] = old_preamble
