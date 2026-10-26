"""Physical-units layer for the LineResonator macro (handoff spec 6.7).

Standard parameters: Z0 = 50 Ohm, Ztx = 65 Ohm, FSR = 150 MHz. The macro's
gamma must agree with comb_poles_K under the unit mapping, and independently
with the arithmetic gamma/FSR = (2/pi)(Ztx/Z0) ~= 0.8276 (gamma ~= 124 MHz).
"""

import numpy as np

from graphulator import autograph
from tests import cmtline_core

Z0 = 50.0
ZTX = 65.0
FSR = 150.0  # MHz


def make_line(**kw):
    defaults = dict(line_id='TL', FSR=FSR, Ztx=ZTX, f_max=1200.0,
                    port_end='xL', Z0_port=Z0)
    defaults.update(kw)
    return autograph.LineResonator(**defaults)


def test_gamma_matches_reference_under_mapping():
    line = make_line()
    _, _, gam_nat = cmtline_core.comb_poles_K(line.N, Z0 / ZTX)
    assert line.gamma == autograph.line_natural_frequency_to_physical(
        gam_nat, FSR)


def test_gamma_over_fsr_arithmetic():
    """Independent arithmetic check: gamma/FSR = (2/pi)(Ztx/Z0) ~ 0.8276."""
    line = make_line()
    assert abs(line.gamma / FSR - (2.0 / np.pi) * (ZTX / Z0)) <= 1e-12
    assert abs(line.gamma / FSR - 0.8276057040778558) <= 1e-12
    # gamma ~= 124 MHz at the standard parameters
    assert abs(line.gamma - 124.14085561167837) <= 1e-9


def test_frequency_and_coupling_scalings_consistent():
    """rate scaling = FSR/pi; coupling scaling = sqrt(FSR/pi); so the mapped
    kappa**2 equals the mapped gamma (channel budget preserved)."""
    line = make_line(port_end='x0')
    freqs, kappas, gamma_phys, N = line.expand_arrays()
    # each coupling entry: kappa_n^2 == gamma (all-plus at x0)
    np.testing.assert_allclose(kappas ** 2, gamma_phys, rtol=1e-14)
    # pole spacing is the FSR (in-ulp): compare successive positive poles
    pos = np.sort(freqs[freqs > 0])
    np.testing.assert_allclose(np.diff(pos), FSR, rtol=1e-13)


def test_alpha_uniform_maps_to_per_mode_B_int():
    """B_int = (2/pi) * alpha * FSR (uniform per-mode loss; the physics
    behind the factor is verified against lossy ABCD in test_uniform_loss)."""
    alpha = 0.02
    line = make_line(alpha_uniform=alpha)
    expected = (2.0 / np.pi) * alpha * FSR
    assert abs(line.B_int_per_mode - expected) <= 1e-12
    nodes, _ = line.expand()
    assert all(abs(n['B_int'] - expected) <= 1e-12 for n in nodes)
