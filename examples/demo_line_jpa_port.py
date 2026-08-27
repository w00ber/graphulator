"""Demo: a transmission-line standing-wave comb as a one-port LineResonator.

Builds the line macro at standard physical parameters (Z0 = 50 Ohm port,
Ztx = 65 Ohm line, FSR = 150 MHz), prints the units-layer numbers
(gamma/FSR = (2/pi)(Ztx/Z0) ~ 0.8276, gamma ~ 124 MHz), plots |S11| of the
expanded autograph graph against the exact microwave (ABCD) answer, and
asserts the empirically pinned N = 80 in-band error threshold from
tests/test_line_macro_vs_abcd.py.

Run from the repo root:  python examples/demo_line_jpa_port.py
(the reference numerics tests/cmtline_core.py must be importable; the script
adds the tests/ directory to sys.path itself).
"""

import os
import sys

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

import cmtline_core  # the reference oracle (JAA conventions)  # noqa: E402
from graphulator import autograph  # noqa: E402

# ---- standard physical parameters -----------------------------------------
Z0 = 50.0      # Ohm, port termination
ZTX = 65.0     # Ohm, line characteristic impedance
FSR = 150.0    # MHz, free spectral range
N = 80         # comb pairs; f_max = N * FSR
N80_THRESHOLD = 0.15  # pinned in tests/test_line_macro_vs_abcd.py

line = autograph.LineResonator(line_id='TL', label='coax', FSR=FSR, Ztx=ZTX,
                               f_max=N * FSR, port_end='xL', Z0_port=Z0)

print("LineResonator at standard parameters")
print(f"  Z0 = {Z0:g} Ohm, Ztx = {ZTX:g} Ohm, FSR = {FSR:g} MHz, N = {line.N}")
print(f"  gamma       = {line.gamma:.6f} MHz   (expected ~124 MHz)")
print(f"  gamma / FSR = {line.gamma / FSR:.10f}")
print(f"  (2/pi)(Ztx/Z0) = {(2.0 / np.pi) * (ZTX / Z0):.10f}")
assert abs(line.gamma / FSR - (2.0 / np.pi) * (ZTX / Z0)) < 1e-12

# ---- expanded autograph graph vs exact ABCD --------------------------------
w_nat = np.linspace(0.3 * np.pi, 6.7 * np.pi, 800)          # in-band sweep
f_mhz = autograph.line_natural_frequency_to_physical(w_nat, FSR)

extractor = autograph.GraphExtractor()
extractor.extract_graph_data(
    nodes=[], edges=[], scattering_assignments={},
    frequency_settings={'start': float(f_mhz[0]), 'stop': float(f_mhz[-1]),
                        'points': len(f_mhz)},
    line_resonators=[line],
)
gsm = autograph.GraphScatteringMatrix(extractor, f_mhz)
s11_macro = gsm.S[:, 0, 0]

s11_abcd = cmtline_core.s11_lab_exact(w_nat, Z0 / ZTX)      # natural units
err = np.abs(s11_macro - s11_abcd)

print(f"\n|S11| macro vs ABCD over f in [{f_mhz[0]:.1f}, {f_mhz[-1]:.1f}] MHz")
print(f"  modes in comb        : {gsm.num_modes}")
print(f"  max |S11| deviation  : {np.max(np.abs(np.abs(s11_macro) - 1)):.2e} "
      "(lossless unitarity)")
print(f"  max |dS11| vs ABCD   : {err.max():.4f} "
      f"(threshold {N80_THRESHOLD}; residual = truncated comb tail ~ 1/N)")
assert err.max() <= N80_THRESHOLD, "N=80 threshold from test 6.5 violated"
print("  PASS: within the pinned N = 80 threshold")

# ---- plot ------------------------------------------------------------------
import matplotlib  # noqa: E402
if not os.environ.get('DISPLAY') and sys.platform.startswith('linux'):
    matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6), sharex=True,
                               height_ratios=[2, 1])
ax1.plot(f_mhz, np.angle(s11_abcd), 'k-', lw=2, label='ABCD (exact)')
ax1.plot(f_mhz, np.angle(s11_macro), 'r--', lw=1.2,
         label=f'LineResonator comb (N = {N})')
ax1.set_ylabel('arg S11 [rad]')
ax1.legend()
ax1.set_title(f'One-port line: Z0 = {Z0:g} Ω, Ztx = {ZTX:g} Ω, '
              f'FSR = {FSR:g} MHz, γ/FSR = {line.gamma / FSR:.3f}')
ax2.semilogy(f_mhz, err, 'b-', lw=1)
ax2.axhline(N80_THRESHOLD, color='gray', ls=':',
            label=f'pinned threshold {N80_THRESHOLD}')
ax2.set_ylabel('|ΔS11|')
ax2.set_xlabel('frequency [MHz]')
ax2.legend()
fig.tight_layout()

out_png = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'demo_line_jpa_port.png')
fig.savefig(out_png, dpi=150)
print(f"\nplot saved to {out_png}")
if matplotlib.get_backend().lower() != 'agg':
    plt.show()
