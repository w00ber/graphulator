"""Node-tap couplings onto a transmission-line end (harmonic-referenced).

The profile implemented by ``LineResonator.tap_couplings`` is NOT an ansatz:
it is pinned here against the reference's own circuit model. A device mode
tapped onto the open end of the line through a fixed element couples to
comb mode n with

    capacitive tap (fixed Cc):        g_n ~ u_n(end) * sqrt(w_n / C_n)
    inductive tap  (fixed mutual kL): g_n ~ u_n(end) / sqrt(w_n * C_n)

extracted from ``cmtline_core.a_basis_A`` applied to the exact Cm/Km
matrices (the same construction as ``build_capacitive``). For the open-open
comb C_n is n-independent (n >= 1), so relative to a chosen reference
harmonic n_ref the element value cancels and the profile is
(n/n_ref)^(+1/2) or (n/n_ref)^(-1/2). The user's rate is the coupling AT
n_ref, which removes the ambiguity when the tapped mode's frequency is not
on a harmonic.
"""

import numpy as np
import pytest

from graphulator.autograph import LineResonator

from tests import cmtline_core as core


def _abasis_tap_couplings(N, tap='capacitive', ell=1.0, Ztx=65.0, v=1.0):
    """|a-basis| device<->line-mode couplings of a tapped device, exactly.

    Builds the (N+1 line modes + 1 device) Cm/Km matrices for a device
    tapped at x = 0 through a fixed capacitor Cc (or fixed mutual kL) and
    reads the coupling magnitudes off the reference's a-basis generator
    A = T @ [[0, C^-1], [-K, 0]] @ T^-1 (cmtline_core.a_basis_A; it drops
    the free n = 0 mode itself).
    """
    Cn, invLn, e, f = core.line_arrays(N, ell=ell, Ztx=Ztx, v=v, tail=False)
    nl = len(Cn)                    # N+1 line modes (n = 0..N)
    M = nl + 1                      # + device
    Cd, Ld = Cn[1], 1.0 / invLn[2]  # arbitrary device values, order-1 in-band

    Cm = np.zeros((M, M))
    Km = np.zeros((M, M))
    if tap == 'capacitive':
        Cc = 1e-6
        Cm[:nl, :nl] = np.diag(Cn) + Cc * np.outer(e, e)
        Cm[:nl, nl] = -Cc * e
        Cm[nl, :nl] = -Cc * e
        Cm[nl, nl] = Cd + Cc
        Km[:nl, :nl] = np.diag(invLn)
        Km[nl, nl] = 1.0 / Ld
    else:
        kL = 1e-6
        Cm[:nl, :nl] = np.diag(Cn)
        Cm[nl, nl] = Cd
        Km[:nl, :nl] = np.diag(invLn)
        Km[nl, nl] = 1.0 / Ld
        Km[:nl, nl] = -kL * e
        Km[nl, :nl] = -kL * e

    A, keep = core.a_basis_A(Cm, Km, np.zeros_like(Cm))
    dev = list(keep).index(nl)
    return {int(k): abs(A[2 * dev, 2 * r])
            for r, k in enumerate(keep) if k not in (0, nl)}


LINE = dict(line_id=0, label='TL', FSR=1.5, Ztx=65.0, f_max=15.1,
            port_end=None, Z0_port=50.0)   # N = ceil(15.1/1.5) = 11


@pytest.mark.parametrize("coupling,exponent", [('capacitive', 0.5),
                                               ('inductive', -0.5)])
@pytest.mark.parametrize("n_ref", [1, 3, 7])
def test_tap_profile_matches_abasis_reference(coupling, exponent, n_ref):
    """(n/n_ref)^(+-1/2) == the reference circuit's own coupling ratios."""
    N = 10
    g = _abasis_tap_couplings(N, tap=coupling)
    line = LineResonator(**dict(LINE, f_max=N * 1.5 - 0.1))
    assert line.N == N

    weights = {cid: w for cid, w, _ in line.tap_couplings('x0', n_ref,
                                                          coupling)}
    for n in range(1, N + 1):
        ref_ratio = g[n] / g[n_ref]
        w = weights[line.mode_node_id(n)]
        assert w == pytest.approx((n / n_ref) ** exponent, rel=0, abs=0)
        assert w == pytest.approx(ref_ratio, rel=5e-6), \
            f"n={n}: implemented {w} vs reference {ref_ratio}"


def test_tap_profile_reference_is_exact_for_weak_elements():
    """The residual vs the reference vanishes with the element strength
    (it is loading of the comb by the finite Cc, not a profile error)."""
    N = 6
    line = LineResonator(**dict(LINE, f_max=N * 1.5 - 0.1))
    for n in range(2, N + 1):
        exact = np.sqrt(n)
        g6 = _abasis_tap_couplings(N, tap='capacitive')
        err = abs(g6[n] / g6[1] - exact) / exact
        assert err < 1e-5


def test_tap_couplings_contract():
    """Pair structure, signs, DC exclusion, and id mapping."""
    line = LineResonator(**LINE)
    N = line.N

    for end, alternating in (('x0', False), ('xL', True)):
        out = line.tap_couplings(end, 2, 'capacitive')
        # one entry per +-n pair member, n = 1..N; DC never appears
        assert len(out) == 2 * N
        ids = [cid for cid, _, _ in out]
        assert line.mode_node_id(0) not in ids
        for n in range(1, N + 1):
            assert line.mode_node_id(n) in ids
            assert line.mode_node_id(-n) in ids
        by_id = {cid: (w, p) for cid, w, p in out}
        for n in range(1, N + 1):
            w_p, p_p = by_id[line.mode_node_id(n)]
            w_m, p_m = by_id[line.mode_node_id(-n)]
            # the +-n pair carries identical weight and sign
            assert w_p == w_m and p_p == p_m
            expected_phase = 180.0 if (alternating and n % 2 == 1) else 0.0
            assert p_p == expected_phase
            assert w_p == (n / 2) ** 0.5


def test_tap_couplings_normalized_at_n_ref():
    line = LineResonator(**LINE)
    for coupling in LineResonator.TAP_COUPLINGS:
        for n_ref in (1, line.N):
            out = dict((cid, w) for cid, w, _ in
                       line.tap_couplings('x0', n_ref, coupling))
            assert out[line.mode_node_id(n_ref)] == 1.0


def test_nearest_harmonic():
    line = LineResonator(**LINE)          # FSR = 1.5, N = 11
    assert line.nearest_harmonic(4.4) == 3      # 4.4/1.5 = 2.93
    assert line.nearest_harmonic(1.5) == 1
    assert line.nearest_harmonic(2.24) == 1     # 1.49
    assert line.nearest_harmonic(2.26) == 2     # 1.51
    assert line.nearest_harmonic(-4.4) == 3     # magnitude
    assert line.nearest_harmonic(0.1) == 1      # clamped up (never DC)
    assert line.nearest_harmonic(1e6) == line.N  # clamped to the comb


def test_tap_validation():
    line = LineResonator(**LINE)
    with pytest.raises(ValueError, match="coupling"):
        line.tap_couplings('x0', 1, 'galvanic')
    with pytest.raises(ValueError, match="end"):
        line.tap_couplings('middle', 1)
    with pytest.raises(ValueError, match="reference harmonic"):
        line.tap_couplings('x0', 0)
    with pytest.raises(ValueError, match="reference harmonic"):
        line.tap_couplings('x0', line.N + 1)
