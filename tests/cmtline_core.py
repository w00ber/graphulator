"""
Core toolkit, JAA conventions throughout:
  forward FT kernel e^{+i w t}  =>  d/dt -> -i w ; modes rotate e^{-i w t}
  Z_L = -i w L ,  Z_C = +i/(w C) ,  forward propagation phase e^{+i beta z}
Units: v = ell = Ztx = 1  =>  mode spacing dW = pi, w_n = n pi,
       per-length capacitance c = 1/(Ztx v) = 1, C_n = c ell/2 = 1/2 (n>=1), C_0 = 1.
"""
import numpy as np
 
# ---------- exact microwave layer (ABCD, JAA sign convention) ----------
def abcd_line(w, ell=1.0, Ztx=1.0, v=1.0):
    th = w*ell/v
    return np.array([[np.cos(th), -1j*Ztx*np.sin(th)],
                     [-1j*np.sin(th)/Ztx, np.cos(th)]])
 
def abcd_series(Z):
    return np.array([[1.0, Z],[0.0, 1.0]], dtype=complex)
 
def abcd_shunt(Y):
    return np.array([[1.0, 0.0],[Y, 1.0]], dtype=complex)
 
def zin_from_abcd(M, ZL):
    if np.isinf(ZL):
        return M[0,0]/M[1,0]
    return (M[0,0]*ZL + M[0,1])/(M[1,0]*ZL + M[1,1])
 
def s11(Z, Zref):
    return (Z - Zref)/(Z + Zref)
 
# impedances in JAA convention
Z_ind = lambda w, L: -1j*w*L
Z_cap = lambda w, C: 1j/(w*C)
 
# ---------- constructive graph: comb + rank-one hub ----------
def comb_poles_K(N, Z0, Ztx=1.0, v=1.0, ell=1.0, signs=True):
    """poles {0, +-n pi}, couplings kappa = (+-1)^n sqrt(gamma), gamma = 2 (Ztx/Z0)(v/ell)."""
    gam = 2.0*(Ztx/Z0)*(v/ell)
    poles = [0.0]
    kap   = [np.sqrt(gam)]
    for n in range(1, N+1):
        s = (-1)**n if signs else 1.0
        poles += [ n*np.pi*v/ell, -n*np.pi*v/ell]
        kap   += [ s*np.sqrt(gam), s*np.sqrt(gam)]
    return np.array(poles), np.array(kap, dtype=float), gam
 
def s11_graph_chi(w, poles, kap):
    chi = np.sum(kap**2 / (w[:,None] - poles[None,:]), axis=1)
    return (0.5j*chi - 1.0)/(0.5j*chi + 1.0)
 
def s11_graph_matrix(w, poles, kap):
    out = np.empty(len(w), dtype=complex)
    K = kap.astype(complex)
    for i, wi in enumerate(w):
        M = np.diag(wi - poles).astype(complex) + 0.5j*np.outer(K, K)
        out[i] = 1j*K @ np.linalg.solve(M, K) - 1.0
    return out
 
def s11_graph_diagonal_only(w, poles, kap):
    """drop cross-damping: independent Lorentzian modes (the blind alley)."""
    g = kap**2
    return -1.0 + np.sum(1j*g[None,:]/(w[:,None] - poles[None,:] + 0.5j*g[None,:]), axis=1)
 
 
# ---------- analytic tail resummation for truncated comb ----------
from scipy.special import digamma
def chi_tail(w, N, gam, v=1.0, ell=1.0):
    """sum_{n>N} gam*[1/(w-wn)+1/(w+wn)]  (paired => convergent), closed form via digamma."""
    a = w*ell/(np.pi*v)
    return gam*(-1.0/np.pi)*(digamma(N+1+a) - digamma(N+1-a))*(ell/v)*np.pi/np.pi  # units: rates already in v/ell=1
 
def s11_graph_chi_tailcorr(w, poles, kap, N, gam):
    chi = np.sum(kap**2/(w[:,None]-poles[None,:]), axis=1) + chi_tail(w, N, gam)
    return (0.5j*chi - 1.0)/(0.5j*chi + 1.0)
 
# ---------- exact lab-side S11 for [series-L connector + line + open] ----------
def s11_lab_exact(w, Z0, Lc=0.0, Ztx=1.0, ell=1.0, v=1.0):
    out = np.empty(len(w), dtype=complex)
    for i, wi in enumerate(w):
        Zline = zin_from_abcd(abcd_line(wi, ell, Ztx, v), np.inf)  # open far end at device side
        Zin = Z_ind(wi, Lc) + Zline                                # connector at the lab side
        out[i] = s11(Zin, Z0)
    return out
 
# ---------- inverse route: pole-residue identification from S(w) data ----------
from scipy.signal import find_peaks
from scipy.optimize import least_squares
 
def model_S(w, a, b, Rr, Ri, yb, Rb, c0):
    """Blaschke-structured rational model with image-pair symmetry:
       pairs (p, R) <-> (-p*, R*),  p_k = a_k - i b_k,  plus one imaginary-axis pole p_b=-i yb (R_b real)."""
    S = np.full(len(w), c0, dtype=complex)
    for ak, bk, rr, ri in zip(a, b, Rr, Ri):
        p = ak - 1j*bk; R = rr + 1j*ri
        S += 1j*R/(w - p) + 1j*np.conj(R)/(w + np.conj(p))
    S += 1j*Rb/(w + 1j*yb)
    return S
 
def fit_poles_residues(w, S, n_extra_iter=2, broad_seed=10.0):
    # 1) seed poles from group delay
    phi = np.unwrap(np.angle(S)); tau = np.gradient(phi, w)
    pk, props = find_peaks(tau, prominence=0.25*np.median(tau[tau>0]))
    a0 = w[pk]; b0 = 2.0/tau[pk]
    # buffer poles just outside the seeded set to absorb out-of-band tails
    if len(a0):
        dm = np.median(np.diff(a0)) if len(a0) > 1 else np.pi
        a0 = np.concatenate([[a0[0]-dm], a0, [a0[-1]+dm]])
        b0 = np.concatenate([[np.median(b0)], b0, [np.median(b0)]])
    # 2) linear residue solve given poles (build once as least squares over Re/Im)
    def linsolve(a, b, yb):
        cols = []
        for ak, bk in zip(a, b):
            p = ak - 1j*bk
            f1 = 1j/(w-p); f2 = 1j/(w+np.conj(p))     # coeffs: R and conj(R) -> real/imag parts
            cols += [f1+f2, 1j*(f1-f2)]               # multiply by (Rr, Ri)
        cols += [1j/(w+1j*yb), np.ones_like(w)]       # Rb (real), c0 (real)
        Amat = np.array(cols).T
        M = np.vstack([Amat.real, Amat.imag])
        y = np.concatenate([S.real, S.imag])
        x, *_ = np.linalg.lstsq(M, y, rcond=None)
        Rr = x[0:-2:2]; Ri = x[1:-2:2]; Rb = x[-2]; c0 = x[-1]
        return Rr, Ri, Rb, c0
    a, b, yb = a0.copy(), b0.copy(), broad_seed
    Rr, Ri, Rb, c0 = linsolve(a, b, yb)
    # 3) nonlinear refine
    n = len(a)
    def pack(a,b,Rr,Ri,yb,Rb,c0): return np.concatenate([a, np.log(b), Rr, Ri, [np.log(yb), Rb, c0]])
    def unpack(x):
        return (x[:n], np.exp(x[n:2*n]), x[2*n:3*n], x[3*n:4*n], np.exp(x[4*n]), x[4*n+1], x[4*n+2])
    def resid(x):
        Sm = model_S(w, *unpack(x))
        return np.concatenate([(Sm-S).real, (Sm-S).imag])
    x0 = pack(a,b,Rr,Ri,yb,Rb,c0)
    sol = least_squares(resid, x0, method="lm", max_nfev=20000)
    return unpack(sol.x), np.max(np.abs(model_S(w, *unpack(sol.x)) - S))
 
def qnm_exact(seeds, Z0, Lc=0.0, Ztx=1.0, ell=1.0, v=1.0, iters=60):
    """complex roots of Gamma_L(w) e^{2i w ell/v} = 1 by Newton, Z_end = Z0 - i w Lc."""
    roots = []
    for s in seeds:
        z = complex(s, -0.3)
        f = lambda z: ((Z0 - 1j*z*Lc - Ztx)/(Z0 - 1j*z*Lc + Ztx))*np.exp(2j*z*ell/v) - 1.0
        for _ in range(iters):
            h = 1e-7
            z = z - f(z)/((f(z+h)-f(z-h))/(2*h))
        roots.append(z)
    return np.array(roots)
 
# ---------- device + line circuit state-space (flux/charge variables) ----------
def line_arrays(N, ell=1.0, Ztx=1.0, v=1.0, tail=True):
    c = 1.0/(Ztx*v)
    Cn = np.full(N+1, c*ell/2.0); Cn[0] = c*ell
    wn = np.arange(N+1)*np.pi*v/ell
    invLn = wn**2 * Cn                       # 1/L_n ; n=0 -> 0
    e = np.ones(N+1)                         # u_n(0)
    f = np.array([(-1)**n for n in range(N+1)], dtype=float)  # u_n(ell)
    if tail:
        # close the truncation: two aux tanks (even/odd parity), L = tail inductance,
        # resonance from 2nd-moment matching  wx^2 = L_x / sum_{tail} L_n/w_n^2
        from scipy.special import polygamma
        l_per = Ztx/v
        ns = np.arange(N+1, N+4001)          # numerically sum far tail (converges fast) + analytic remainder
        Ln_t = 2*l_per*ell/(ns*np.pi)**2
        Mn_t = Ln_t/((ns*np.pi*v/ell)**2)
        rem1 = (2*l_per*ell/np.pi**2)*polygamma(1, ns[-1]+1)
        for par in (0, 1):                   # even, odd
            m = (ns % 2) == par
            Lx = Ln_t[m].sum() + rem1/2.0
            Mx = Mn_t[m].sum()
            wx2 = Lx/Mx
            Cn = np.append(Cn, 1.0/(wx2*Lx))
            invLn = np.append(invLn, 1.0/Lx)
            e = np.append(e, 1.0)
            f = np.append(f, 1.0 if par == 0 else -1.0)
    return Cn, invLn, e, f
 
def build_galvanic(N, LJ, Cd, Rd=np.inf, ell=1.0, Ztx=1.0, v=1.0):
    Cn, invLn, e, f = line_arrays(N, ell, Ztx, v)
    Cm = np.diag(Cn) + Cd*np.outer(e, e)
    Km = np.diag(invLn) + (1.0/LJ)*np.outer(e, e)
    Rm = (0.0 if np.isinf(Rd) else 1.0/Rd)*np.outer(e, e)
    P  = np.outer(e, e)/LJ                   # pump pattern: modulates 1/LJ at the shared node
    return Cm, Km, Rm, P, f
 
def build_capacitive(N, LJ, Cd, Cc, Rd=np.inf, ell=1.0, Ztx=1.0, v=1.0):
    Cn, invLn, e, f = line_arrays(N, ell, Ztx, v)
    nl = len(Cn); M = nl+1
    Cm = np.zeros((M, M)); Km = np.zeros((M, M)); Rm = np.zeros((M, M))
    Cm[:nl,:nl] = np.diag(Cn) + Cc*np.outer(e, e)
    Cm[:nl, nl] = -Cc*e; Cm[nl, :nl] = -Cc*e
    Cm[nl, nl]  = Cd + Cc
    Km[:nl,:nl] = np.diag(invLn); Km[nl, nl] = 1.0/LJ
    if not np.isinf(Rd): Rm[nl, nl] = 1.0/Rd
    P = np.zeros((M, M)); P[nl, nl] = 1.0/LJ
    fv = np.concatenate([f, [0.0]])
    return Cm, Km, Rm, P, fv
 
def zsys_port(w, Cm, Km, Rm, f):
    """impedance seen at the lab node (load resistor excluded)."""
    out = np.empty(len(w), dtype=complex)
    for i, wi in enumerate(w):
        A = Km - wi**2*Cm - 1j*wi*Rm
        out[i] = -1j*wi * (f @ np.linalg.solve(A, f))
    return out
 
# ---------- pumped harmonic balance (signal/idler conversion matrix) ----------
def hb_signal_idler(ws, wp, eps, Cm, Km, Rm_int, P, f, Z0):
    """returns S_ss, S_is at each ws; port Thevenin source behind Z0 at the lab node."""
    Rport = np.outer(f, f)/Z0
    Rtot = Rm_int + Rport
    Sss = np.empty(len(ws), dtype=complex); Sis = np.empty(len(ws), dtype=complex)
    n = Cm.shape[0]
    for i, w1 in enumerate(ws):
        w2 = wp - w1
        Z1 = Km - w1**2*Cm - 1j*w1*Rtot
        Z2 = np.conj(Km - w2**2*Cm - 1j*w2*Rtot)      # conjugated idler balance
        B  = 0.5*eps*P
        big = np.block([[Z1, B],[B, Z2]])
        Vs = 1.0                                       # Thevenin amplitude at signal
        rhs = np.concatenate([f*Vs/Z0, np.zeros(n)])
        x = np.linalg.solve(big, rhs)
        ps, pib = x[:n], x[n:]
        Vinc = Vs/2.0
        Vl_s = -1j*w1*(f @ ps)
        Vl_i = +1j*w2*(f @ pib)                        # conj of idler voltage amplitude
        Sss[i] = (Vl_s - Vinc)/Vinc
        Sis[i] = Vl_i/Vinc
    return Sss, Sis
 
 
# ---------- a-basis display transform (explicit block inverse; drops n=0) ----------
def a_basis_A(Cm, Km, Rm):
    M = Cm.shape[0]
    Ci = np.linalg.inv(Cm)
    A = np.block([[np.zeros((M,M)), Ci],[-Km, -Rm@Ci]])
    Kdg = np.diag(Km).copy(); Cdg = np.diag(Cm).copy()
    keep = np.where(Kdg > 0)[0]                      # drop free (n=0) mode
    Z = np.sqrt(1.0/(Kdg[keep]*Cdg[keep]))
    m = len(keep)
    T   = np.zeros((2*m, 2*M), complex)
    Tin = np.zeros((2*M, 2*m), complex)
    for r, k in enumerate(keep):
        T[2*r, k]   = 1/np.sqrt(2*Z[r]);  T[2*r, M+k]   =  1j*np.sqrt(Z[r]/2)
        T[2*r+1, k] = 1/np.sqrt(2*Z[r]);  T[2*r+1, M+k] = -1j*np.sqrt(Z[r]/2)
        Tin[k, 2*r] = np.sqrt(Z[r]/2);    Tin[k, 2*r+1] =  np.sqrt(Z[r]/2)
        Tin[M+k, 2*r] = -1j/np.sqrt(2*Z[r]); Tin[M+k, 2*r+1] = +1j/np.sqrt(2*Z[r])
    return T @ A @ Tin, keep
 
# ---------- generalized port: frequency-dependent termination Y_L(w) ----------
def zsys_port_YL(w, Cm, Km, Rm, f):
    return zsys_port(w, Cm, Km, Rm, f)   # alias; impedance excludes the port branch by construction
 
def hb_signal_idler_YL(ws, wp, eps, Cm, Km, Rm_int, P, f, YL, Z0):
    """port branch = Thevenin V_s behind [Z0 + connector], total branch admittance YL(w);
       waves referenced at the Z0 plane."""
    Sss = np.empty(len(ws), dtype=complex); Sis = np.empty(len(ws), dtype=complex)
    n = Cm.shape[0]
    for i, w1 in enumerate(ws):
        w2 = wp - w1
        Y1, Y2 = YL(w1), YL(w2)
        Z1 = Km - w1**2*Cm - 1j*w1*(Rm_int + Y1*np.outer(f, f))
        Z2 = np.conj(Km - w2**2*Cm - 1j*w2*(Rm_int + Y2*np.outer(f, f)))
        B  = 0.5*eps*P
        big = np.block([[Z1, B],[B, Z2]])
        Vs = 1.0
        rhs = np.concatenate([f*Y1*Vs, np.zeros(n)])
        x = np.linalg.solve(big, rhs)
        ps, pib = x[:n], x[n:]
        Vl_s = -1j*w1*(f @ ps)                       # line-end voltage, signal
        Vl_i = +1j*w2*(f @ pib)                      # conj idler amplitude
        Vp_s = Vs - Z0*Y1*(Vs - Vl_s)                # node at the Z0 reference plane
        Vp_i = -Z0*np.conj(Y2)*(0.0 - Vl_i)
        Vinc = Vs/2.0
        Sss[i] = (Vp_s - Vinc)/Vinc
        Sis[i] = Vp_i/Vinc
    return Sss, Sis