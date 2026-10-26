"""Shared helpers for the hub identity/dilation tests.

Builds "static" graphs through the real GraphExtractor/GraphScatteringMatrix
API such that M(w) = w*1 - Omega + (i/2)Gamma_tot with a caller-chosen real
symmetric Omega:

- every node is normal-sector (conj=False) with freq = Omega[j, j],
- every off-diagonal Omega[j, k] != 0 becomes an edge with f_p = 0,
  rate = 2*|Omega[j, k]| and phase 0/180 (beta = rate/2 * e^{i phase} equals
  the real signed Omega entry; all pump offsets vanish so f_drive = w),
- dissipation enters only through hubs (and optional B_int).

This exercises the production assembly code end to end rather than
re-implementing it with numpy.
"""

import numpy as np

from graphulator import autograph


def build_static_extractor(Omega, hubs=None, B_int=0.0, freq_settings=None):
    """Build a GraphExtractor for M(w) = w - Omega + (i/2)(B_int + Gram).

    Parameters
    ----------
    Omega : (N, N) real symmetric ndarray
        Target Hermitian part: diagonal -> node freqs, off-diagonal -> edges.
    hubs : list of dicts/DissipationHub, optional
        Explicit hubs, attachments referencing node ids 0..N-1.
    B_int : float or (N,) array
        Per-node internal loss (uniform diagonal damping).
    """
    Omega = np.asarray(Omega)
    N = Omega.shape[0]
    B_int = np.broadcast_to(np.asarray(B_int, dtype=float), (N,))

    nodes = [
        {'node_id': j, 'label': f'm{j}', 'pos': (float(j), 0.0),
         'conj': False}
        for j in range(N)
    ]
    edges = []
    for j in range(N):
        for k in range(j + 1, N):
            if Omega[j, k] != 0.0:
                edges.append({
                    'from_node_id': j, 'to_node_id': k,
                    'is_self_loop': False,
                    'f_p': 0.0,
                    'rate': 2.0 * abs(Omega[j, k]),
                    'phase': 0.0 if Omega[j, k] > 0 else 180.0,
                })

    assignments = {}
    for j, node in enumerate(nodes):
        assignments[id(node)] = {'freq': float(Omega[j, j]),
                                 'B_int': float(B_int[j]), 'B_ext': None}
    for edge in edges:
        assignments[id(edge)] = {'f_p': edge['f_p'], 'rate': edge['rate'],
                                 'phase': edge['phase']}

    extractor = autograph.GraphExtractor()
    extractor.extract_graph_data(
        nodes=nodes, edges=edges,
        scattering_assignments=assignments,
        frequency_settings=freq_settings or {'start': -6.0, 'stop': 6.0,
                                             'points': 121},
        root_node_id=0,
        hubs=hubs,
    )
    return extractor


def hub_from_column(hub_id, column, monitored=True, label=None):
    """Make a hub dict whose attachment vector equals `column` (real signed)."""
    attachments = [(j, float(w)) for j, w in enumerate(column) if w != 0.0]
    return {'hub_id': hub_id, 'label': label or str(hub_id),
            'attachments': attachments, 'monitored': monitored}


def random_symmetric(rng, N, scale=1.0):
    A = rng.standard_normal((N, N)) * scale
    return (A + A.T) / 2.0
