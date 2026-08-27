"""Golden regression gate for the hub-based dissipation refactor.

The artifacts under tests/golden/ were captured by tests/capture_golden.py on
the PRE-refactor code (main @ eb6fa69). The refactored assembly must
reproduce them: legacy per-node B_ext graphs auto-wrap into single-attachment
hubs whose Gram (i/2) K K^dagger lands on the same diagonal entries the old
code wrote directly.

Tolerance note (why not bit-identity): the old code added B_ext to the
diagonal and sqrt(B_ext) to K independently; the new code squares the stored
kappa = sqrt(B_ext), and sqrt(x)**2 == x is not exact in floating point
(e.g. sqrt(0.3)**2 = 0.3 - 1 ulp). That costs ~1 ulp (~6e-17) on M's
diagonal, which M^-1 amplifies near resonance to ~1e-15 on S in the worst
golden graph. M and K are asserted at rtol=1e-15/atol=1e-18; S at
rtol=1e-14/atol=1e-16 to admit exactly that documented amplification and
nothing more.
"""

import pickle
from pathlib import Path

import numpy as np
import pytest

from graphulator import autograph
from tests.capture_golden import build_all, FREQ_GRID

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


@pytest.fixture(scope="module")
def extractors():
    return build_all()


def load_artifact(name):
    with open(GOLDEN_DIR / f"{name}.pkl", 'rb') as fh:
        return pickle.load(fh)


GOLDEN_NAMES = sorted(p.stem for p in GOLDEN_DIR.glob("*.pkl"))


def test_golden_set_is_complete():
    assert len(GOLDEN_NAMES) == 6


@pytest.mark.parametrize("name", GOLDEN_NAMES)
def test_golden_regression(name, extractors):
    art = load_artifact(name)
    gsm = autograph.GraphScatteringMatrix(extractors[name], FREQ_GRID)

    np.testing.assert_allclose(gsm.M, art['M'], rtol=1e-15, atol=1e-18)
    np.testing.assert_allclose(gsm.K, art['K'], rtol=1e-15, atol=1e-18)
    # See module docstring: 1-ulp sqrt round-trip through M^-1
    np.testing.assert_allclose(gsm.S, art['S'], rtol=1e-14, atol=1e-16)
    np.testing.assert_allclose(gsm.det_M, art['det_M'], rtol=1e-12, atol=0)

    assert gsm.K.dtype == art['K'].dtype  # legacy float64 preserved
    assert gsm.num_ports == art['num_ports']
    assert gsm.port_ids == art['port_ids']
    assert gsm.port_dict == art['port_dict']
    assert {pid: gsm._get_port_label(pid) for pid in gsm.port_ids} \
        == art['port_labels']
    assert extractors[name].graph_data['basis_order'] == art['basis_order']
    assert extractors[name].graph_data['root_node_id'] == art['root_node_id']


@pytest.mark.parametrize("name", GOLDEN_NAMES)
def test_golden_k_full_consistency(name, extractors):
    """The new K_full view of a legacy graph is the old K exactly, with no
    loss columns, and M's anti-Hermitian part equals B_int + K K^dagger."""
    gsm = autograph.GraphScatteringMatrix(extractors[name], FREQ_GRID)
    assert gsm.K_loss.shape == (gsm.num_modes, 0)
    np.testing.assert_array_equal(gsm.K_full.real, gsm.K)
    np.testing.assert_array_equal(gsm.K_full.imag, np.zeros_like(gsm.K))
