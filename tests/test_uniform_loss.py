"""Gate for the LineResonator alpha_uniform parameter (spec 6.8).

Derivation (stated per the no-ansatz rule): a spatially uniform per-length
amplitude attenuation alpha acts on the open-open standing-wave basis as a
multiple of the identity — every mode's traveling-wave components lose
amplitude at the same rate alpha*v, and mode orthogonality keeps the loss
operator diagonal with equal entries. Hence each comb mode acquires the same
amplitude decay rate alpha*v, i.e. an energy rate Gamma_int = 2*alpha in
natural angular units (v = ell = 1), which the unit-mapping layer turns into
per-mode B_int = (2/pi) * alpha_uniform * FSR.

Reference: abcd_line extended with complex propagation angle
th -> th + i*alpha*ell (JAA forward kernel e^{+i beta z}, amplitude decay
e^{-alpha z} => beta_c = beta + i*alpha).

Verification strategy: the raw lossy-macro vs lossy-ABCD error is dominated
by the same truncated-tail residual as the lossless case, so the mapping is
tested on the LOSS-INDUCED CHANGE, d = S11(alpha) - S11(0), macro vs ABCD.
Measured (Z0 = 50/65, in-band sweep):

    alpha=0.02:  |d| ~ 5.1e-02;  |d_macro - d_abcd| = 1.34e-02 (N=40),
                 6.70e-03 (N=80), 3.36e-03 (N=160)

The mapping error vanishes ~1/N alongside the truncation error (relative
error at fixed N equals the lossless truncation ratio), so the residual is
attributable to truncation, not to the B_int mapping. alpha_uniform is
therefore ENABLED, gated by this test.
"""

import numpy as np
import pytest

from graphulator import autograph
from tests import cmtline_core
from tests.test_line_macro_vs_abcd import macro_s11, W_NAT, FSR, Z0_NAT

ALPHA = 0.02  # one-way attenuation alpha*ell in nepers


def s11_lab_lossy(w, Z0, alpha, Ztx=1.0, ell=1.0, v=1.0):
    """ABCD with complex propagation angle (see module docstring)."""
    out = np.empty(len(w), dtype=complex)
    for i, wi in enumerate(w):
        th = wi * ell / v + 1j * alpha * ell
        M = np.array([[np.cos(th), -1j * Ztx * np.sin(th)],
                      [-1j * np.sin(th) / Ztx, np.cos(th)]])
        out[i] = cmtline_core.s11(cmtline_core.zin_from_abcd(M, np.inf), Z0)
    return out


@pytest.fixture(scope="module")
def loss_effect_reference():
    return s11_lab_lossy(W_NAT, Z0_NAT, ALPHA) \
        - cmtline_core.s11_lab_exact(W_NAT, Z0_NAT)


def loss_effect_macro(N):
    return macro_s11(N, alpha_uniform=ALPHA) - macro_s11(N)


def test_loss_effect_matches_abcd_and_converges(loss_effect_reference):
    d_ref = loss_effect_reference
    errs = []
    for N in (20, 40, 80):
        errs.append(np.max(np.abs(loss_effect_macro(N) - d_ref)))
    # strictly decreasing ~1/N and, at N=80, small vs the effect itself
    assert all(a > b for a, b in zip(errs, errs[1:])), errs
    assert errs[-1] <= 0.2 * np.max(np.abs(d_ref)), errs


def test_lossy_macro_absorbs(loss_effect_reference):
    """With alpha on, |S11| < 1 in-band and the absorption is positive where
    the reference says it is (sanity on sign conventions)."""
    s11 = macro_s11(40, alpha_uniform=ALPHA)
    absorption = 1.0 - np.abs(s11) ** 2
    assert np.all(absorption > 0.0)
    ref_absorption = 1.0 - np.abs(
        s11_lab_lossy(W_NAT, Z0_NAT, ALPHA)) ** 2
    # same order of magnitude, in-band average within 35% at N=40
    assert abs(np.mean(absorption) / np.mean(ref_absorption) - 1.0) <= 0.35


def test_b_int_mapping_constant():
    """The enabling constant itself: B_int = (2/pi) alpha FSR."""
    line = autograph.LineResonator(line_id='TL', FSR=FSR, Ztx=65.0,
                                   f_max=10 * FSR, port_end='xL',
                                   Z0_port=50.0, alpha_uniform=ALPHA)
    assert abs(line.B_int_per_mode - (2.0 / np.pi) * ALPHA * FSR) <= 1e-12
