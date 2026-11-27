"""MSuper + sweep grid -> M and S.

The arithmetic repeats autograph.GraphScatteringMatrix operation by operation
(same dtypes, same order, same frequency blocking), so that milestone 1 can
be gated bit for bit against the legacy engine. It is written separately on
purpose: the gate then checks the arithmetic as well as the translation, and
milestone 2 adds a frequency-dependent Sigma_0 step that legacy does not have.
"""
from __future__ import annotations

from typing import Tuple

import numpy as np

from .msuper import MSuper


def f_axis(ms: MSuper, f) -> np.ndarray:
    """The sweep as the root sees it: negated when the root is conjugated."""
    f = np.asarray(f)
    return -f if ms.root_conj else f


def k_matrices(ms: MSuper) -> Tuple[np.ndarray, np.ndarray]:
    """(K, K_full): K over the ports (real when every weight is), K_full over
    ports then loss channels (complex), rows in row order."""
    n = len(ms.rows)

    def columns(chans):
        cols = np.zeros(shape=(n, len(chans)), dtype=complex)
        for col, ch in enumerate(chans):
            for row, w in ch.weights:
                cols[row, col] += w
        return cols

    K_ports = columns(ms.ports)
    K_loss = columns([c for c in ms.channels if not c.monitored])
    K_full = np.column_stack([K_ports, K_loss])
    K = K_ports.real.copy() if np.all(K_ports.imag == 0) else K_ports
    return K, K_full


def static_part(ms: MSuper, K_full: np.ndarray) -> np.ndarray:
    """The frequency-independent part: couplings + (i/2) K_full K_full^dag."""
    n = len(ms.rows)
    static = np.zeros((n, n), dtype=complex)
    if ms.couplings:
        lo = np.asarray([c[0] for c in ms.couplings])
        hi = np.asarray([c[1] for c in ms.couplings])
        beta = np.asarray([c[2] for c in ms.couplings], dtype=complex)
        sector = np.array([r.conj for r in ms.rows], dtype=bool)
        sgn = np.where(sector[lo] == sector[hi], 1.0, -1.0)
        if len(set(zip(lo.tolist(), hi.tolist()))) == len(lo):
            static[lo, hi] = beta
            static[hi, lo] = sgn * np.conj(beta)
        else:                                 # parallel edges: summed
            np.add.at(static, (lo, hi), beta)
            np.add.at(static, (hi, lo), sgn * np.conj(beta))
    if K_full.size:
        gram = K_full @ K_full.conj().T
        static += 0.5j * gram
    return static


def diagonal(ms: MSuper, f_calc: np.ndarray) -> np.ndarray:
    """(n_f, N): (f + nu_k) -+ f_k + i B_int,k / 2 per row."""
    diag = np.empty((len(f_calc), len(ms.rows)), dtype=complex)
    for idx, r in enumerate(ms.rows):
        f_drive = f_calc + r.nu if r.nu is not None else f_calc
        sign = 1.0 if r.conj else -1.0
        diag[:, idx] = f_drive + sign * r.f0 + r.B_int * 1j / 2
    return diag


def freq_blocks(n_f: int, n: int):
    step = max(1, int(2 ** 22 // max(n ** 2, 1)))
    return [(a, min(a + step, n_f)) for a in range(0, n_f, step)]


def m_block(static, diag, lo, hi):
    block = np.empty((hi - lo,) + static.shape, dtype=complex)
    block[...] = static
    idx = np.arange(static.shape[0])
    block[:, idx, idx] += diag[lo:hi]
    return block


def M_stack(ms: MSuper, f) -> np.ndarray:
    """The full (n_f, N, N) M over the sweep, for inspection."""
    f_calc = f_axis(ms, f)
    _, K_full = k_matrices(ms)
    return m_block(static_part(ms, K_full), diagonal(ms, f_calc), 0, len(f_calc))


def scattering(ms: MSuper, f) -> np.ndarray:
    """S = -1 + i K^dag M^-1 K over the ports, shape (n_f, P, P)."""
    f_calc = f_axis(ms, f)
    K, K_full = k_matrices(ms)
    static = static_part(ms, K_full)
    diag = diagonal(ms, f_calc)
    n_chan = K.shape[1]
    S = np.empty((len(f_calc), n_chan, n_chan), dtype=complex)
    for lo, hi in freq_blocks(len(f_calc), len(ms.rows)):
        rhs = np.broadcast_to(K, (hi - lo,) + K.shape)
        MinvK = np.linalg.solve(m_block(static, diag, lo, hi), rhs)
        S[lo:hi] = 1j * (K.conj().T @ MinvK) - np.eye(n_chan)
    return S
