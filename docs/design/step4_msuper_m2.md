# Step 4, milestone 2: embedding circuits and sector windows (design, for review)

*Status: proposal, 18 Nov 2026. No code yet. **[decide]** items need JA's
call. Numbers come from survey scripts run on the shipped files.
*(speculation)* marks physics I have not tested.*

## Scope

Physical documents, as the 4.0 model already holds them:
- line blocks (uniform, stepped, uniform loss);
- `L`/`C`/`R` blocks at planes (end loads, matched loss terminations);
- port planes with Z0;
- element pumps (`Pumped(kind="element")`, a modulated 1/L at a plane);
- lumped modes attached to planes: directly to a port, or through a tap
  onto a line end;
- sector windows (`solve.sectors`).

The abstract workflow keeps the milestone-1 path unchanged (bit for bit with
legacy).

The 14 non-lumped shipped files, by what they need:

| needs | files |
|---|---|
| lines + ports only | TL_1, TL_5 |
| lines + element pump (+ load, + sections) | TL_3, TL_4, LINE_PUMPED_TERMINATION, LINE_PUMPED_LOADED, LINE_PUMPED_AMP_AND_CONV, 3 x INTERMODE_LEE2013 |
| a lumped mode on a port plane shared with lines | PORT_SHARED_2LINES |
| taps (mode -> line end through C) | TL_2, LINE_TAP_2NODES, NODE_2LINES_TAP |

No shipped file has lumped modes and a pump together.

## What the oracle can and cannot be

Bit for bit against legacy is not available here, and not desirable:
- legacy expands every line into a truncated comb, closes the port tail
  analytically, and keeps two sectors;
- M_super evaluates the lines exactly and opens as many sectors as needed.

The references are:
- **Exact, independent:** closed-form line admittances and ABCD cascades,
  written in the test, not imported from the engine. Also nodal harmonic
  balance: `misc/msuper_E0_tl3_sectors.py`'s `hb_sectors`, cross-checked
  against JA's immsuper.py in `misc/msuper_E0_immsuper_crosscheck.out`.
- **Legacy, where legacy is exact:** unpumped one-port lines with the tail
  closure. TL_1 legacy equals the exact reflection to 4e-15.
- **Legacy, where it is not:** pumped files at window {-1..0}. Differences
  are reported and explained (the DC mode, the dropped pump-tail couplings,
  two sectors), not gated.

## Formulation

**Convention.** Time dependence e^{-i omega t}, decaying poles in the lower
half plane. This is what legacy S actually matches: TL_1 gives
S = (1 - Z0 Y)/(1 + Z0 Y) with Y_open = -i tan(theta)/Z_tx, to 4e-15.
`docs/pumped_line_termination.md` says e^{+i omega t} in its preamble, which
contradicts "poles in the lower half plane"; the note should be corrected
**[decide D7]**.

**Sectors.** Sector m (an integer vector over tones) runs at the lab
frequency omega_m = omega + m . omega_P. A negative omega_m is conjugate
(idler) content. Circuit blocks need no conj flag: a real element obeys
Y(-omega) = conj Y(omega), so evaluating it at omega_m is enough.

**Unknowns per frequency point:**
- one voltage V_{p,m} per (plane, sector);
- one amplitude a_{k,m} per kept (mode, sector) row.

**Sigma_0 rows (KCL at each plane, in each sector):**

    sum_blocks Y_b(omega_m) V_m + V_m / Z0 (ports) + I_pump,m + I_CMT,m = 2 b_in / sqrt(Z0)     (sources only on sector-0 port rows)

- Blocks: line two-ports, exact, built from the same closed forms
  LineResonator already uses for its tail (`input_impedance`, the stepped
  cascade, complex theta for loss); `L`/`C`/`R`; open = nothing.
- **Element pump:** 1/L(t) = 1/L0 + delta cos(omega_P t + phi) at plane p
  couples (p, m) to (p, m +- 1) through
  I_m += (delta/2) e^{-+i phi} (i/omega_{m-+1}) V_{m-+1}. The flux is
  V/(-i omega). This is `hb_sectors` verbatim.
  - With a pure first harmonic in 1/L, the window truncation is the only
    approximation.
  - W3 level 2 (harmonics) adds shifts of +-n at no extra structure.

**Lumped modes: the CMT block as an impedance-type multiport.** All lumped
modes, with their couplings, form one block. Seen from the planes they
attach to, it is a multiport with normalized impedance matrix

    z(omega) = (i/2) K^dag M_iso(omega)^{-1} K

This is the legacy convention, and it is an identity: by Woodbury,

    -1 + i K^dag (M_iso + (i/2) K K^dag)^{-1} K = (z - 1)(z + 1)^{-1}

so a lumped document is the Gamma of its own z on matched ports. Checked
numerically on the 28 lumped components with ports only: median difference
3e-16. The worst point is 7e-7, where M_iso alone has condition number
about 1e8 (a lossless mode on resonance). Hence the implementation never
inverts M_iso; it solves the bordered system:

    [ M_iso      K y_c  ] [a]   [K j]
    [ -(i/2)K^dag   1   ] [v] = [ 0 ]

Here the block is folded into the plane rows, so the current into it is
I_CMT. A physical z needs a reference impedance per plane: Z0 for a port
plane. For an internal plane there is none yet; see D3.

**Physical consequence (what changes from legacy).** Every block on a plane,
the CMT block included, is connected *in parallel* at that node (KCL). The
legacy hub instead adds impedances: every comb mode and node mode on a hub
column sits in *series* with the resistor. The TL_5 notes say so explicitly
("the port sees the two ends in series, Z_a + Z_b"). See D1.

**Kept poles: a representation choice, not an accuracy knob.**
- With no promoted poles, the network is exact.
- Promoting pole n of a line to a mode row (`Mode.origin = line_pole`)
  splits its admittance exactly, Mittag-Leffler style:
  Y_line(omega) = Y_rem(omega) + sum_n (pole terms). The -f_n partner stays
  in Y_rem.
- **S must not depend on `kept_poles`.** That is a gate.
- `f_max` stops being an accuracy setting and becomes a display/generate
  setting: which poles are drawn as modes, and which appear in M_iso and in
  a future M_super tab.

*(speculation)* With all line poles in Sigma_0, a pumped line has **no RWA
at all**: only the window truncates. The RWA enters only through drawn
lumped modes and promoted poles, each of which is one pole of a real
response.

**S.**
- Channels are (port, sector). Each port gets one row per sector; ports
  carry no sector of their own (layer-0 note).
- S_{(p,m),(q,0)} uses power waves normalized to each port's Z0.
- Gain and conversion are also reported in photon flux,
  |S^ph_{m0}|^2 = |S_{m0}|^2 omega/|omega_m|, which is what Manley-Rowe
  conserves.
- The default display is the sector-0 block (comparable with legacy). The
  conversion blocks are available alongside it.

**Size.** At most 4 planes and 16 modes, times 8-16 sectors: under about
300 unknowns per frequency point. A dense solve per point is fine.
Reporting M (the Schur complement onto the mode rows, for the M_super tab)
is a later display feature, and the solve does not need it.

## Legacy anchors the engine must convert

**Pump depth (D4).** Legacy stores {rate, n_ref, coupling} anchored at a
mode pair. The forward conversion is pinned:
- rate = (2 FSR/pi) g_nm, with g_nm = delta u_n u_m / (4 sqrt(omega_n C_n omega_m C_m));
- on a loaded or stepped line, the mode quantities are the loaded ones
  (LineResonator: `mode_profile`, `mode_mass`, `load_participation`);
- TL_3 reduces to delta = 3 pi^2 rate / FSR (E0, natural units).

I propose the engine computes delta at compile time, and the schema keeps
the anchor (step-1 deviation, unchanged). Gate: TL_3 equals E0's
`hb_sectors` at the same windows, to rounding.

**Taps (D3).** A tap couples a lumped mode to a line end through C or L,
with its rate anchored at n_ref. As a plane attachment it needs the
attachment weight and a reference impedance on an internal plane. That is
the "inverse tap profile" left open by layer-0 decision 3.
- *(speculation)* For a capacitive tap the mode couples to V_end. The
  anchor fixes |kappa|^2 times the line's residue at pole n_ref. The
  derivation is a page.
- It must be gated against `tests/cmtline_core` (`a_basis_A`, the oracle
  the tap profile was pinned to), not against legacy alone.
- Until then the three tap files are refused.

## Sector windows (D5)

- Decision 5 (accepted earlier):
  - `"auto"` grows symmetrically from {-1..0}, mirror-symmetric
    (m <-> -1-m), so {-1..0}, {-2..1}, ...;
  - it stops when the change in S over the sweep, relative to (G - 1), is
    below `sector_tol` = 1e-3;
  - it is capped at `sector_max` = 16, with a not-converged warning;
  - an explicit [m_lo, m_hi] overrides.
- E0 shows why the default matters for TL_3: {-1..0} is off by 36 % at
  rate 0.05 and by 10x at rate 0.8. {-4..3} agrees with {-6..5} to 1e-6 up
  to rate 0.4.
- **Open detail:** "relative to (G - 1)" is undefined for pure conversion,
  where G - 1 <= 0. I propose the metric
  max_f max_{p,q} |dS_{pq}| / max(max_f |G - 1|, 1e-2), so conversion
  windows converge on the absolute change. Your call.
- **One tone in milestone 2.** No shipped physical file has two. A
  two-tone window is a 2-D grid, and its growth rule needs its own
  thought.
- **Stability:** E0 sees gain peaks that rise and then fall with rate
  (a pole crossing the real axis). The engine reports "possibly beyond
  threshold" when the window keeps growing |S| without converging. A real
  stability test (det M, Routh-Hurwitz) is later.

## Gates

1. **Exact, unpumped:** TL_1 and TL_5 against independent closed forms
   (1e-12, away from poles). TL_1 also against legacy with the tail closure
   on (the same exact answer).
2. **Pumped:**
   - TL_3 against `hb_sectors` at windows {-1..0} through {-6..5}
     (1e-12);
   - reproduce E0's table of peaks;
   - TL_4, LINE_PUMPED_LOADED and the Lee scenes (loaded, stepped) against
     an independent HB on the test side;
   - Manley-Rowe / photon-flux audit at 1e-12 on lossless documents;
   - S_full unitary on lossless unpumped documents.
3. **Representation:** S is invariant under `kept_poles` (promote 0, 3 or
   all poles below f_max), at 1e-12.
4. **Lumped through the M2 path:** every lumped shipped file equals
   milestone 1 to 1e-13. Not bitwise: the algebra differs. Abstract
   documents still use the milestone-1 path.
5. **Reported, not gated:** pumped files at {-1..0} against legacy, with
   each difference attributed to the DC mode, the pump-tail couplings or
   the window.

## Build order (proposed)

- **M2a:** network only. Lines, loads, ports, element pumps, windows.
  Covers 10 of the 14 files.
- **M2b:** the CMT block as a z-multiport on port planes
  (PORT_SHARED_2LINES), plus kept poles as mode rows.
- **M2c:** taps, after the D3 derivation and its gate.
- **Later:** lumped modes together with element pumps. Their sector images
  are the physical workflow's *generate* step (W2 resonator tag, sector
  glyphs), so they wait for that design.

## Findings to act on

- **Legacy TL_5 shows neither physics.** The example's notes describe one
  shared port (series). But legacy's component split gives the two lines
  **separate jobs**: each trace is one line alone on P (verified to 1e-14).
  - The shipped test `test_two_lines_one_port_is_two_jobs` pins that.
  - The split misses components joined only through a port with no node
    attachments.
- **The model already says "parallel".** Both line terminals name the same
  plane `port0`, a node.
- **The pumped-termination note's time convention** (see D7).

## Questions for JA

- **D1, shared planes:** a plane is a node, and everything on it is in
  parallel (my recommendation: it is what a circuit drawing means, and
  nodal analysis needs no special case). The legacy hub/series meaning
  would become an explicit element if wanted. TL_5's notes would then be
  rewritten, and its plot changes from "two separate lines" to "two lines
  in parallel".
- **D2, the CMT block is an impedance-type multiport,**
  z = (i/2) K^dag M_iso^{-1} K. This is legacy-exact for lumped documents.
  The alternative, admittance type, differs by S -> -S on a lone port
  (a reference-plane choice) but physically on shared planes. I recommend
  the impedance type.
- **D3, taps:** derive the inverse tap profile in M2c, gated against
  cmtline_core; refuse tap files until then. Also: what reference
  impedance should a *new* attachment to an internal plane use? Z_tx of
  the line, a per-plane field, or should such attachments always go
  through an explicit C/L element?
- **D4, pump depth:** compute delta from the anchor in the engine; keep
  the schema as is.
- **D5, windows:** the convergence metric for conversion, one tone only,
  and the threshold warning.
- **D6, S output:** (port, sector) channels; default display of the
  sector-0 block plus the photon-flux conversion blocks.
- **D7:** pin e^{-i omega t} and fix the preamble of
  `pumped_line_termination.md`.
