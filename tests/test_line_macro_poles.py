"""Complex pole structure of the expanded line comb vs exact QNMs (spec 6.6).

The w-independent pole pencil of the expanded graph, A = diag(poles)
- (i/2) kappa kappa^T (recovered from the assembled M), approximates the
exact quasinormal modes of the loaded line (roots of
Gamma_L(w) e^{2iw} = 1, cmtline_core.qnm_exact).

Observed convergence of the first four QNMs (max |pencil - exact|, natural
units, Z0 = 50/65), which sets the pinned tolerance below:

    N=10: [0.096, 0.241, 0.378, 0.499]
    N=20: [0.047, 0.121, 0.196, 0.269]
    N=40: [0.023, 0.060, 0.099, 0.137]
    N=80: [0.012, 0.030, 0.049, 0.069]

~1/N, consistent with the truncated-tail attribution in
test_line_macro_vs_abcd.py.
"""

import numpy as np
import pytest

from graphulator import autograph
from tests import cmtline_core

FSR = 150.0
ZTX = 65.0
Z0 = 50.0


def pencil_eigs_natural(N):
    """Pole pencil of the EXPANDED autograph graph, mapped back to natural
    units: M(f) = f*1 - A  =>  A = -M(0), and A_nat = A_phys * pi/FSR."""
    line = autograph.LineResonator(line_id='TL', label='TL', FSR=FSR,
                                   Ztx=ZTX, f_max=N * FSR, port_end='xL',
                                   Z0_port=Z0)
    assert line.N == N
    extractor = autograph.GraphExtractor()
    extractor.extract_graph_data(
        nodes=[], edges=[], scattering_assignments={},
        frequency_settings={'start': 0.0, 'stop': 1.0, 'points': 1},
        line_resonators=[line],
    )
    gsm = autograph.GraphScatteringMatrix(extractor, np.array([0.0]))
    A_phys = -gsm.M[0]
    return np.linalg.eigvals(A_phys * (np.pi / FSR))


@pytest.mark.parametrize("N,tol", [(20, 0.30), (80, 0.08)])
def test_pencil_matches_exact_qnms(N, tol):
    ev = pencil_eigs_natural(N)
    approx = np.sort_complex(ev[ev.real > 0.5])[:4]
    exact = cmtline_core.qnm_exact(approx, Z0 / ZTX)
    err = np.abs(approx - exact)
    assert np.max(err) <= tol
    # decaying poles sit in the lower half plane (JAA convention)
    assert np.all(approx.imag < 0)


def test_pencil_error_decreases_with_N():
    errs = []
    for N in (10, 20, 40, 80):
        ev = pencil_eigs_natural(N)
        approx = np.sort_complex(ev[ev.real > 0.5])[:4]
        exact = cmtline_core.qnm_exact(approx, Z0 / ZTX)
        errs.append(np.max(np.abs(approx - exact)))
    assert all(a > b for a, b in zip(errs, errs[1:]))
