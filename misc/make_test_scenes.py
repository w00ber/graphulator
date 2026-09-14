"""Regenerate the canonical explicit-ports test scenes (File -> Test).

Headless: builds each scene through the live GUI API and saves it with the
app's own serializer, so the files always match the current .pgraph format.

    QT_QPA_PLATFORM=offscreen python misc/make_test_scenes.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if hasattr(os, "geteuid") and os.geteuid() == 0:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
OUT_DIR = os.path.join(ROOT, "examples", "test_scenes")

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

import graphulator.graphulator_para as gp                    # noqa: E402
from graphulator import graphulator_para_config as config    # noqa: E402


def fresh_window():
    config.EXPLICIT_PORTS_MODE = True
    win = gp.Graphulator()
    win._apply_explicit_ports_mode()
    return win


def add_node(win, node_id, label, pos, freq, B_int=0.0):
    node = {'node_id': node_id, 'label': label,
            'pos': (float(pos[0]), float(pos[1])),
            'color': 'cornflowerblue', 'color_key': 'BLUE',
            'node_size_mult': 1.0, 'label_size_mult': 1.0, 'conj': False}
    win.nodes.append(node)
    win.node_id_counter = max(win.node_id_counter, node_id + 1)
    win.scattering_assignments[node_id] = {'freq': freq, 'B_int': B_int}
    return node


def save(win, name):
    path = os.path.join(OUT_DIR, f"{name}.pgraph")
    assert win._save_graph_to_file(path), name
    print(f"  wrote {os.path.relpath(path, ROOT)}")


def scene_port_1node():
    win = fresh_window()
    a = add_node(win, 0, 'a', (-3.0, 0.0), freq=5.0)
    p = win.add_port(label='P1', pos=(1.5, 0.0))
    win.add_port_attachment(p, a['node_id'], rate=0.2, sign=1)
    save(win, "PORT_1NODE")


def scene_port_2nodes_stack():
    win = fresh_window()
    a = add_node(win, 0, 'a', (-3.0, 1.5), freq=5.0)
    b = add_node(win, 1, 'b', (-3.0, -1.5), freq=6.0)
    p = win.add_port(label='P1', pos=(1.5, 0.0))
    win.add_port_attachment(p, a['node_id'], rate=0.2, sign=1)
    win.add_port_attachment(p, b['node_id'], rate=0.2, sign=-1)
    save(win, "PORT_2NODES_STACK")


def scene_port_3nodes_arc():
    win = fresh_window()
    freqs = (4.5, 5.0, 5.5)
    pts = ((-3.5, 2.5), (-4.5, 0.0), (-3.5, -2.5))
    p = win.add_port(label='P1', pos=(1.5, 0.0))
    for k, (pos, f) in enumerate(zip(pts, freqs)):
        n = add_node(win, k, chr(ord('a') + k), pos, freq=f)
        win.add_port_attachment(p, n['node_id'], rate=0.15,
                                sign=1 if k % 2 == 0 else -1)
    save(win, "PORT_3NODES_ARC")


def scene_port_3nodes_surround():
    # nodes on three sides of the port: stresses the collimated exit and
    # the wrap-around wire to the node BEHIND the lead direction
    win = fresh_window()
    freqs = (4.5, 5.0, 5.5)
    pts = ((-4.0, 0.0), (1.0, 3.5), (1.0, -3.5))
    p = win.add_port(label='P1', pos=(1.0, 0.0))
    for k, (pos, f) in enumerate(zip(pts, freqs)):
        n = add_node(win, k, chr(ord('a') + k), pos, freq=f)
        win.add_port_attachment(p, n['node_id'], rate=0.15, sign=1)
    save(win, "PORT_3NODES_SURROUND")


def scene_port_shared_2lines():
    # one physical resistor shared by two lines AND a device mode
    win = fresh_window()
    a = add_node(win, 0, 'a', (0.0, 3.5), freq=4.4)
    p = win.add_port(label='P1', pos=(0.0, 0.0))
    tl1 = win.add_line_resonator(label='TL1', pos=(-7.0, 0.0), FSR=1.5,
                                 Ztx=65.0, f_max=6.0, port_end=None)
    tl2 = win.add_line_resonator(label='TL2', pos=(7.0, 0.0), FSR=2.0,
                                 Ztx=65.0, f_max=8.0, port_end=None)
    win.connect_line_end_to_port(tl1, 'xL', p)
    win.connect_line_end_to_port(tl2, 'x0', p)
    win.add_port_attachment(p, a['node_id'], rate=0.2, sign=1)
    save(win, "PORT_SHARED_2LINES")


def scene_line_tap_2nodes():
    win = fresh_window()
    a = add_node(win, 0, 'a', (-8.0, 2.8), freq=4.4)
    b = add_node(win, 1, 'b', (-8.0, -2.8), freq=2.9)
    tl = win.add_line_resonator(label='TL1', pos=(0.0, 0.0), FSR=1.5,
                                Ztx=65.0, f_max=6.0, port_end='xL')
    win.connect_line_end_to_node(tl, 'x0', a, rate=0.03)
    win.connect_line_end_to_node(tl, 'x0', b, rate=0.02)
    save(win, "LINE_TAP_2NODES")


def scene_node_2lines_tap():
    win = fresh_window()
    a = add_node(win, 0, 'a', (0.0, 0.0), freq=4.4)
    tl1 = win.add_line_resonator(label='TL1', pos=(-7.5, 2.0), FSR=1.5,
                                 Ztx=65.0, f_max=6.0, port_end='x0')
    tl2 = win.add_line_resonator(label='TL2', pos=(7.5, -2.0), FSR=2.0,
                                 Ztx=65.0, f_max=8.0, port_end='xL')
    win.connect_line_end_to_node(tl1, 'xL', a, rate=0.03)
    win.connect_line_end_to_node(tl2, 'x0', a, rate=0.03)
    save(win, "NODE_2LINES_TAP")


if __name__ == '__main__':
    os.makedirs(OUT_DIR, exist_ok=True)
    print("Generating test scenes:")
    scene_port_1node()
    scene_port_2nodes_stack()
    scene_port_3nodes_arc()
    scene_port_3nodes_surround()
    scene_port_shared_2lines()
    scene_line_tap_2nodes()
    scene_node_2lines_tap()
    print("done.")
