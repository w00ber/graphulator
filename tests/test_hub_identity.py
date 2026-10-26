"""Input-output consistency identities for hub-based external dissipation.

These re-establish, inside the repo and through the production assembly code,
the results the hub redesign rests on (companion doc: "Why diagonal damping
breaks, stated as a theorem"):

    S = -1 + i K^dagger M^-1 K,   M(w) = w*1 - Omega + (i/2) Gamma_tot
    S^dagger S = 1 - (M^-1 K)^dagger Gamma_int (M^-1 K),
    Gamma_int = Gamma_tot - K K^dagger

- Unitarity (lossless)  <=>  Gamma_int = 0
- Passivity             <=>  Gamma_int >= 0 (PSD)
- Writing dissipation on the diagonal while K is dense makes Gamma_int
  indefinite -> spurious |S| > 1 (the pre-hub model's failure mode; kept
  here as an asserted counterexample so the reason for the redesign stays
  executable).
"""

import numpy as np
import pytest

from tests.hub_matrix_helpers import (build_static_extractor, hub_from_column,
                                      random_symmetric)
from graphulator import autograph

N_MODES = 5
OMEGA_SWEEP = np.linspace(-6.0, 6.0, 121)


@pytest.fixture(scope="module")
def dense_two_port():
    """N=5 random real-symmetric Omega, dense random K with 2 port channels,
    built through GraphExtractor/GraphScatteringMatrix."""
    rng = np.random.default_rng(20260827)
    Omega = random_symmetric(rng, N_MODES, scale=2.0)
    K_cols = rng.standard_normal((N_MODES, 2)) * 0.7
    hubs = [hub_from_column('P0', K_cols[:, 0]),
            hub_from_column('P1', K_cols[:, 1])]
    extractor = build_static_extractor(Omega, hubs=hubs)
    gsm = autograph.GraphScatteringMatrix(extractor, OMEGA_SWEEP)
    return gsm, Omega, K_cols


def test_identity_stS(dense_two_port):
    """(a) S^dagger S = 1 - (M^-1 K)^dagger Gamma_int (M^-1 K) at every w."""
    gsm, _, _ = dense_two_port
    K = gsm.K_full  # ports only here (no loss hubs)
    assert K.shape == (N_MODES, 2)

    Minv = np.linalg.inv(gsm.M)
    MK = Minv @ K
    Gamma_tot = -1j * (gsm.M - np.conj(np.transpose(gsm.M, (0, 2, 1))))
    Gamma_int = Gamma_tot - (K @ K.conj().T)[None, :, :]

    lhs = np.conj(np.transpose(gsm.S, (0, 2, 1))) @ gsm.S
    rhs = np.eye(2) - np.conj(np.transpose(MK, (0, 2, 1))) @ Gamma_int @ MK
    assert np.max(np.abs(lhs - rhs)) <= 1e-14


def test_lossless_unitarity(dense_two_port):
    """(b) Gamma_tot = K K^dagger (B_int = 0, no loss hubs) => S unitary."""
    gsm, _, _ = dense_two_port
    StS = np.conj(np.transpose(gsm.S, (0, 2, 1))) @ gsm.S
    eigs = np.linalg.eigvalsh(StS)
    assert np.max(np.abs(eigs - 1.0)) <= 1e-13


def test_passivity_with_loss_hub():
    """(c) Gamma_tot = K K^dagger + W W^dagger (an unmonitored loss hub)
    => max eig(S^dagger S) <= 1: no spurious gain, ever."""
    rng = np.random.default_rng(4257)
    Omega = random_symmetric(rng, N_MODES, scale=2.0)
    K_cols = rng.standard_normal((N_MODES, 2)) * 0.7
    W = rng.standard_normal(N_MODES) * 0.5
    hubs = [hub_from_column('P0', K_cols[:, 0]),
            hub_from_column('P1', K_cols[:, 1]),
            hub_from_column('L0', W, monitored=False)]
    extractor = build_static_extractor(Omega, hubs=hubs)
    gsm = autograph.GraphScatteringMatrix(extractor, OMEGA_SWEEP)

    StS = np.conj(np.transpose(gsm.S, (0, 2, 1))) @ gsm.S
    eigs = np.linalg.eigvalsh(StS)
    assert np.max(eigs) <= 1.0 + 1e-13


def test_diagonal_damping_counterexample(dense_two_port):
    """(d) The pre-hub model: Gamma_tot = diag(K K^dagger) with dense K.

    Keep this assertion direction — it documents WHY the old model is wrong:
    forcing the damping diagonal against a non-diagonal K K^dagger makes
    Gamma_int = diag(KK^d) - KK^d indefinite (it is traceless and nonzero),
    and the scattering matrix shows spurious gain, max eig(S^dagger S) > 1.
    Built with numpy on purpose: the refactored assembly can no longer
    express this inconsistent combination.
    """
    _, Omega, K = dense_two_port
    diag_damping = np.diag(np.diag(K @ K.T))

    max_eig = 0.0
    for w in OMEGA_SWEEP:
        M = w * np.eye(N_MODES) - Omega + 0.5j * diag_damping
        S = 1j * (K.T @ np.linalg.solve(M, K)) - np.eye(2)
        max_eig = max(max_eig, np.linalg.eigvalsh(S.conj().T @ S).max())

    assert max_eig > 1.0 + 1e-6, (
        "diagonal-damping counterexample unexpectedly passive; "
        "the test graph no longer demonstrates the defect"
    )
