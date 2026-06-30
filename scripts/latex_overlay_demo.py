"""
PROTOTYPE demo for the Qt SVG label overlay (rearchitecture experiment).

Run interactively::

    python scripts/latex_overlay_demo.py

* Scroll to zoom, click-drag to pan.
* matplotlib draws only the node circles + edges; every LaTeX label is painted
  by the Qt SVG overlay, decoupled from matplotlib's render loop.  Labels are
  rendered once and only repositioned/rescaled on pan/zoom -- no LaTeX recompile,
  crisp at any zoom.

The bottom of this file also exposes ``render_proof_frames()`` used to generate
before/after PNGs headlessly for verification.
"""

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMainWindow

from graphulator.para_ui.canvas import MplCanvas
from graphulator.para_rendering.label_overlay import LatexLabelOverlay

# A small demo graph: node positions, labels, and edge label midpoints.
NODES = [
    {'pos': (-5, 0), 'label': r'$\mathbf{A}$', 'color': 'cornflowerblue'},
    {'pos': (5, 0), 'label': r'$\mathbf{B}_{1}$', 'color': 'cornflowerblue'},
    {'pos': (0, 6), 'label': r'$\mathbf{C}$', 'color': 'mediumseagreen'},
]
EDGES = [
    ((-5, 0), (5, 0), r'$\beta_{AB}$'),
    ((-5, 0), (0, 6), r'$\kappa_{AC}$'),
    ((5, 0), (0, 6), r'$\gamma_{BC}$'),
]
NODE_RADIUS = 1.2


def build_scene(canvas, usetex=False):
    """Draw the matplotlib part (circles + edges) and return overlay labels."""
    ax = canvas.ax
    ax.clear()
    ax.set_xlim(-10, 10)
    ax.set_ylim(-8, 12)
    ax.set_aspect('equal')
    ax.axis('off')

    for (p, q, _lbl) in EDGES:
        ax.plot([p[0], q[0]], [p[1], q[1]], '-', color='0.4', lw=2, zorder=1)
    import matplotlib.patches as patches
    for n in NODES:
        ax.add_patch(patches.Circle(n['pos'], NODE_RADIUS, facecolor=n['color'],
                                    edgecolor='none', zorder=2))

    labels = []
    for n in NODES:
        labels.append({'x': n['pos'][0], 'y': n['pos'][1], 'text': n['label'],
                       'height_data': NODE_RADIUS * 0.8, 'color': 'white'})
    for (p, q, lbl) in EDGES:
        mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
        labels.append({'x': mx, 'y': my + 0.6, 'text': lbl,
                       'height_data': NODE_RADIUS * 0.7, 'color': 'black'})
    return labels


class DemoWindow(QMainWindow):
    def __init__(self, usetex=False):
        super().__init__()
        self.setWindowTitle("LaTeX SVG overlay prototype")
        self.canvas = MplCanvas(width=8, height=8, dpi=100)
        self.setCentralWidget(self.canvas)
        self.overlay = LatexLabelOverlay(self.canvas, self.canvas.ax, usetex=usetex)
        self.overlay.set_labels(build_scene(self.canvas, usetex=usetex))
        self.canvas.draw_idle()

        self._pan_start = None
        self.canvas.scroll_signal.connect(self._on_scroll)
        self.canvas.click_signal.connect(self._on_click)
        self.canvas.motion_signal.connect(self._on_motion)
        self.canvas.release_signal.connect(lambda e: setattr(self, '_pan_start', None))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.overlay.setGeometry(self.canvas.rect())

    def _on_scroll(self, event):
        ax = self.canvas.ax
        scale = 0.83 if event.button == 'up' else 1.2
        x, y = event.xdata, event.ydata
        if x is None:
            return
        for get, setlim in ((ax.get_xlim, ax.set_xlim), (ax.get_ylim, ax.set_ylim)):
            lo, hi = get()
            c = x if get is ax.get_xlim else y
            setlim(c + (lo - c) * scale, c + (hi - c) * scale)
        self.canvas.draw_idle()      # cheap: no labels in matplotlib
        self.overlay.update()

    def _on_click(self, event):
        if event.xdata is not None:
            self._pan_start = (event.xdata, event.ydata)

    def _on_motion(self, event):
        if self._pan_start is None or event.xdata is None:
            return
        ax = self.canvas.ax
        dx = event.xdata - self._pan_start[0]
        dy = event.ydata - self._pan_start[1]
        x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
        ax.set_xlim(x0 - dx, x1 - dx); ax.set_ylim(y0 - dy, y1 - dy)
        self.canvas.draw_idle()
        self.overlay.update()


def render_proof_frames(out_dir, usetex=False):
    """Headless: render the composite (canvas + overlay) at several zoom levels."""
    import os
    app = QApplication.instance() or QApplication(sys.argv)
    win = DemoWindow(usetex=usetex)
    win.resize(700, 700)
    win.show()
    app.processEvents()
    ax = win.canvas.ax
    paths = []
    for tag, (xl, yl) in {
        'full': ((-10, 10), (-8, 12)),
        'zoom2x': ((-5, 5), (-1, 9)),
        'zoom6x': ((-2.2, 2.2), (4.2, 8.0)),  # zoom into node C
    }.items():
        ax.set_xlim(*xl); ax.set_ylim(*yl)
        win.canvas.draw(); app.processEvents()
        pix = win.grab()  # composite canvas + overlay
        p = os.path.join(out_dir, f"overlay_{tag}.png")
        pix.save(p); paths.append(p)
    print("SVG builds (should equal number of unique labels):", win.overlay.builds)
    print("frames:", paths)
    return paths


if __name__ == '__main__':
    if '--proof' in sys.argv:
        idx = sys.argv.index('--proof')
        out = sys.argv[idx + 1] if len(sys.argv) > idx + 1 else '.'
        render_proof_frames(out, usetex='--latex' in sys.argv)
    else:
        app = QApplication(sys.argv)
        win = DemoWindow(usetex='--latex' in sys.argv)
        win.resize(800, 800)
        win.show()
        sys.exit(app.exec())
