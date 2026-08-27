"""LineResonator macro vs the exact microwave answer (spec 6.5).

The expanded comb's S11, computed by the full autograph pipeline, is compared
against cmtline_core.s11_lab_exact (ABCD: open-ended line behind a Z0 source;
natural units, no connector Lc=0 — connector cases are Phase 2).

Measured convergence (max in-band |S11_macro - S11_ABCD|, w in
[0.3 pi, 6.7 pi], Z0 = 50/65 natural, i.e. gamma/FSR ~= 0.83) that pins the
fixed-N threshold below:

    N= 10: 1.112e+00     (tail attribution |chi - chi_tailcorr|: 1.112e+00)
    N= 20: 5.366e-01     (                                       5.366e-01)
    N= 40: 2.675e-01     (                                       2.675e-01)
    N= 80: 1.340e-01     (                                       1.340e-01)
    N=160: 6.712e-02     (                                       6.712e-02)

~1/N. The residual at fixed N is the TRUNCATED COMB TAIL, not a defect of
the hub assembly: the tail attribution column (the shift the analytic
digamma tail closure would add back, |s11_graph_chi - s11_graph_chi_tailcorr|
at the same N) matches the macro-vs-ABCD error to three digits at every N.
"""

import numpy as np
import pytest

from graphulator import autograph
from tests import cmtline_core

FSR = 150.0
ZTX = 65.0
Z0 = 50.0
Z0_NAT = Z0 / ZTX

W_NAT = np.linspace(0.3 * np.pi, 6.7 * np.pi, 400)
N_LADDER = (10, 20, 40, 80)
N80_THRESHOLD = 0.15  # measured 1.340e-01 at N=80; pinned with headroom


def macro_s11(N, alpha_uniform=0.0):
    line = autograph.LineResonator(line_id='TL', label='TL', FSR=FSR,
                                   Ztx=ZTX, f_max=N * FSR, port_end='xL',
                                   Z0_port=Z0, alpha_uniform=alpha_uniform)
    assert line.N == N
    f_phys = autograph.line_natural_frequency_to_physical(W_NAT, FSR)
    extractor = autograph.GraphExtractor()
    extractor.extract_graph_data(
        nodes=[], edges=[], scattering_assignments={},
        frequency_settings={'start': float(f_phys[0]),
                            'stop': float(f_phys[-1]),
                            'points': len(f_phys)},
        line_resonators=[line],
    )
    gsm = autograph.GraphScatteringMatrix(extractor, f_phys)
    return gsm.S[:, 0, 0]


@pytest.fixture(scope="module")
def errors_by_N():
    s11_exact = cmtline_core.s11_lab_exact(W_NAT, Z0_NAT)
    return {N: np.max(np.abs(macro_s11(N) - s11_exact)) for N in N_LADDER}


def test_in_band_error_strictly_decreasing(errors_by_N):
    errs = [errors_by_N[N] for N in N_LADDER]
    assert all(a > b for a, b in zip(errs, errs[1:])), errs


def test_error_at_N80_below_pinned_threshold(errors_by_N):
    assert errors_by_N[80] <= N80_THRESHOLD, errors_by_N


def test_residual_attributed_to_truncated_tail(errors_by_N):
    """|s11_graph_chi - s11_graph_chi_tailcorr| at the same N upper-bound-
    order-matches the macro-vs-ABCD error (loose factor: within 2x)."""
    for N in N_LADDER:
        poles, kap, gam = cmtline_core.comb_poles_K(N, Z0_NAT)
        tail = np.max(np.abs(
            cmtline_core.s11_graph_chi(W_NAT, poles, kap)
            - cmtline_core.s11_graph_chi_tailcorr(W_NAT, poles, kap, N, gam)))
        assert errors_by_N[N] <= 2.0 * tail
        assert errors_by_N[N] >= 0.5 * tail


def test_macro_s11_is_unitary_without_loss():
    """|S11| = 1 to machine precision for the lossless one-port comb at any
    N — the hub assembly never leaks or gains (contrast: the diagonal
    approximation errs at the 0.1-1 level here, see test_hub_identity)."""
    s11 = macro_s11(20)
    assert np.max(np.abs(np.abs(s11) - 1.0)) <= 1e-12
