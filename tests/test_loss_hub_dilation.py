"""Loss-hub dilation invariants: unitary dilation, energy audit, bright/dark.

One monitored port (kappa) plus one unmonitored loss hub (lambda), both with
dense attachments over a random Omega. The dilated S_full treats the loss hub
as a channel; the reduced S keeps its damping inside M but drops the column.
"""

import numpy as np
import pytest

from tests.hub_matrix_helpers import (build_static_extractor, hub_from_column,
                                      random_symmetric)
from graphulator import autograph

N_MODES = 5
OMEGA_SWEEP = np.linspace(-6.0, 6.0, 121)


@pytest.fixture(scope="module")
def port_plus_loss():
    rng = np.random.default_rng(90125)
    Omega = random_symmetric(rng, N_MODES, scale=2.0)
    kappa = rng.standard_normal(N_MODES) * 0.8
    lam = rng.standard_normal(N_MODES) * 0.6
    hubs = [hub_from_column('P0', kappa),
            hub_from_column('L0', lam, monitored=False)]
    extractor = build_static_extractor(Omega, hubs=hubs)  # B_int = 0
    gsm = autograph.GraphScatteringMatrix(extractor, OMEGA_SWEEP)
    return gsm


def test_dilated_unitarity(port_plus_loss):
    """(a) With B_int = 0 every damping channel is in K_full, so S_full is
    exactly unitary — the built-in self-test for lossy models."""
    S_full = port_plus_loss.S_full
    n_chan = S_full.shape[-1]
    assert n_chan == 2
    StS = np.conj(np.transpose(S_full, (0, 2, 1))) @ S_full
    assert np.max(np.abs(StS - np.eye(n_chan))) <= 1e-13


def test_reduced_equals_dilated_port_block(port_plus_loss):
    """(b) Reduced S (loss inside M, absent from S) equals the dilated port
    block. Same M^-1 solve feeds both, so this is tight."""
    gsm = port_plus_loss
    block = gsm.S_full[:, :gsm.num_ports, :gsm.num_ports]
    assert np.max(np.abs(gsm.S - block)) <= 1e-15


def test_energy_audit(port_plus_loss):
    """(c) Missing port power equals the flux into the loss channel:
    1 - |S11|^2 = |S_full[loss, port]|^2 at every frequency."""
    gsm = port_plus_loss
    s11 = gsm.S[:, 0, 0]
    loss_flux = np.abs(gsm.S_full[:, 1, 0]) ** 2
    audit = np.abs(1.0 - np.abs(s11) ** 2 - loss_flux)
    assert np.max(audit) <= 1e-13
    # .absorption is the same audit, exposed as API
    assert np.max(np.abs(gsm.absorption[:, 0] - loss_flux)) <= 1e-13


def test_bright_dark_pole_structure():
    """(d) A rank-one absorber on a degenerate comb damps exactly one bright
    collective mode and leaves N-1 dark; diagonalizing the same budget damps
    everything a little. Same trace, different physics."""
    w0 = 3.0
    Omega = w0 * np.eye(N_MODES)

    # unit-budget dense loss hub: sum lambda_n^2 = 1
    lam = np.ones(N_MODES) / np.sqrt(N_MODES)
    extractor = build_static_extractor(
        Omega, hubs=[hub_from_column('L0', lam, monitored=False)])
    gsm = autograph.GraphScatteringMatrix(extractor, np.array([0.0]))

    # M(w) = w*1 - A with A = Omega - (i/2) lambda lambda^dagger,
    # so at the w = 0 grid point the pole pencil is A = -M(0)
    A = -gsm.M[0]
    poles = np.linalg.eigvals(A)
    im = np.sort(poles.imag)

    # exactly one bright pole at Im = -1/2, N-1 dark at Im = 0
    assert abs(im[0] + 0.5) <= 1e-12
    assert np.max(np.abs(im[1:])) <= 1e-12

    # diagonal comparison: same budget written per-node damps every mode
    A_diag = Omega - 0.5j * np.diag(lam ** 2)
    im_diag = np.linalg.eigvals(A_diag).imag
    assert np.min(np.abs(im_diag)) > 0.0
    # trace (total damping budget) is identical in both allocations
    assert abs(np.sum(im_diag) - np.sum(poles.imag)) <= 1e-12
