"""The sweep is assembled a frequency block at a time.

M over a whole sweep is (n_freq, N, N). On a pumped comb that is ~1 GB
(N = 270, 801 points) and simply allocating and first-touching it cost more
than every other stage of the calculation put together -- while each
frequency's system is independent and never needed the others. So the S
path goes block by block and M itself is built on demand.

These pin the structure, not a wall clock: that the blocked assembly agrees
with the whole-sweep one exactly, and that nothing on the S path
materializes the stack.
"""

import numpy as np
import pytest

from graphulator import autograph
from tests.hub_matrix_helpers import build_static_extractor, hub_from_column, random_symmetric

N_MODES = 6
SWEEP = np.linspace(-4.0, 4.0, 37)


@pytest.fixture(scope="module")
def gsm():
    rng = np.random.default_rng(20260919)
    Omega = random_symmetric(rng, N_MODES, scale=2.0)
    cols = rng.standard_normal((N_MODES, 2)) * 0.7
    hubs = [hub_from_column('P0', cols[:, 0]),
            hub_from_column('P1', cols[:, 1])]
    extractor = build_static_extractor(Omega, hubs=hubs)
    return autograph.GraphScatteringMatrix(extractor, SWEEP)


def test_S_path_never_materializes_the_stack(gsm):
    """Construction computes S without ever assembling the (n_freq, N, N)
    array -- the cache stays empty until something asks for .M."""
    assert gsm.S.shape == (len(SWEEP), 2, 2)
    assert getattr(gsm, '_M_full', None) is None


def test_blocks_tile_the_sweep_exactly(gsm):
    blocks = gsm._freq_blocks()
    assert blocks[0][0] == 0 and blocks[-1][1] == len(SWEEP)
    for (_, hi), (lo, _) in zip(blocks, blocks[1:]):
        assert hi == lo                       # contiguous, no gaps or overlap
    assert sum(hi - lo for lo, hi in blocks) == len(SWEEP)


def test_block_assembly_equals_the_whole_sweep(gsm):
    """Bit-for-bit: the block is the same terms in the same order."""
    M = gsm.M                                  # assembles + caches the stack
    assert M.shape == (len(SWEEP), N_MODES, N_MODES)
    for lo, hi in [(0, 1), (0, len(SWEEP)), (3, 11), (len(SWEEP) - 2, len(SWEEP))]:
        assert np.array_equal(gsm.M_block(lo, hi), M[lo:hi]), (lo, hi)


def test_S_matches_a_direct_per_frequency_solve(gsm):
    """Against the textbook expression, one frequency at a time."""
    M = gsm.M
    K = gsm.K
    for i in (0, 7, len(SWEEP) - 1):
        ref = 1j * (K.conj().T @ np.linalg.solve(M[i], K)) - np.eye(2)
        assert np.max(np.abs(gsm.S[i] - ref)) < 1e-12, i


def test_det_M_is_computed_on_demand(gsm):
    """det_M is a diagnostic, not part of the S path: it costs two more
    O(n_freq N^3) factorizations and is not paid for unless asked."""
    fresh = autograph.GraphScatteringMatrix(gsm.extractor, SWEEP)
    assert getattr(fresh, '_det_M', None) is None
    assert fresh.det_M.shape == (len(SWEEP),)
    assert fresh.det_M_dB.shape == (len(SWEEP),)
    ref = np.array([np.linalg.det(fresh.M[i]) for i in range(len(SWEEP))])
    assert np.allclose(fresh.det_M, ref, rtol=1e-10)
