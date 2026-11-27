# Step 4, milestone 2: embedding circuits and sector windows (design, for review)

*Status: proposal 18 Nov 2026; decisions 19 Nov; M2a built 19 Nov (last section). **[decide]** items need JA's
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

## Decisions (JA, 19 Nov 2026)

Figure: `m2_D1_shared_port.png`. It shows the three readings of "several
things on one port".

- **D1, shared points: side by side (A in the figure).** Real circuit
  elements (lines, loads) that meet at a point are in parallel: one node,
  and their admittances add.
  - The modes attached at a point form one block, internally in Foster I
    form (C in the figure). That block sits on the node like any other
    element.
  - The legacy hub's series reading (B) is dropped for lines.
  - TL_5 and PORT_SHARED_2LINES change. TL_5's notes must be rewritten,
    and the test that pins its two-job split goes.
- **D2, modes attach as an impedance:** z = (i/2) K^T M_iso^{-1} K is the
  graph's z-matrix.
  - A lone mode looks like an admittance, y proportional to M_iso,jj; modes
    sharing a point add as impedances.
  - The code solves the combined system and never inverts M_iso alone.
- **D3, rates are enough, all quoted against one reference impedance.**
  - A mode can attach to several lines with different Z_tx, so the
    document has a single reference impedance Z_ref. Every impedance is
    scaled to it, and every attachment rate means "the leak rate into
    Z_ref".
  - No coupling-element values are needed. The coupling type
    (capacitive/inductive) still sets how the coupling varies with
    frequency.
  - Open detail (mine): when a port's own Z0 differs from Z_ref, the
    engine accounts for the mismatch. Lumped documents have no port Z0, so
    milestone 1 is unaffected.
  - Proposed home: `units.z_ref`, default 50 ohm. A schema addition.
  - Still owed: converting legacy n_ref-anchored tap rates into this
    convention, gated against `cmtline_core`.
- **D4, the depth is the stored quantity (physical workflow only).**
  - The model stores the modulation depth delta(1/L).
  - A rate the user types on a reference pair is converted to a depth
    through the transfer function; the engine flags a rate it cannot
    reach.
  - Editing FSR, the load and so on keeps the depth, and the displayed
    rate follows.
  - Migration converts the legacy {rate, n_ref} anchor to a depth once the
    conversion is gated (M2a), and the anchor is kept as provenance. This
    replaces layer-0 decision 3's "hold the anchor" for pumps.
  - Abstract pumped edges keep their drawn rate.
- **D5, sectors:** the user steps the window up or down by hand, and
  "auto" grows it until the answer converges, as proposed.
- **D6, trace labels use S_jk order (k scatters into j); no "S" in labels:**
  - `P1:0`: P1 reflection, same sector;
  - `P1:(-1,0)`: P1 in at sector 0, out at sector -1;
  - `(P1,P2):0`: P2 into P1, same sector;
  - `(P1,P2):(-1,0)`: P2 sector 0 into P1 sector -1.

  Traces are toggled by choosing ports and sectors. Photon flux is the
  default, with a toggle to power.
- **D7:** pin e^{-i omega t}; fix the preamble of
  `pumped_line_termination.md`.

## M2a as built (19 Nov 2026)

`src/graphulator/engine/network.py` (Qt-free). `engine.solve(doc)` routes:
- lumped documents go to milestone 1, unchanged;
- physical documents (lines, L/C/R blocks, ports, element pumps, no modes)
  go to the network, returning `NetworkResult`;
- documents with modes and lines are refused with `NotSupportedError`,
  naming 2b (CMT block on port planes: PORT_SHARED_2LINES) or 2c (taps:
  TL_2, LINE_TAP_2NODES, NODE_2LINES_TAP).

**Formulation, as implemented.** It is a modified nodal analysis per
sector, chosen so that every matrix entry is entire in frequency:
- one V per plane (KCL rows);
- per line, (I1, I2) with the two ABCD rows V1 = A V2 + B I2 and
  I1 = C V2 + D I2. A..D are cos/sin of the complex electrical length
  t = (pi f / FSR + i alpha) frac, cascaded over the sections. There is no
  cot/csc, so a line pole (f_m = n FSR) is not a division by zero;
- one flux Phi per plane with an inductor or a pump, with the row
  V + i omega Phi = 0. An inductor draws Phi/L, and the pump draws
  (delta/2) e^{-+i phi} Phi_{m-+1}. A sector landing on DC is therefore
  regular when a static L is present; without one (TL_3: 1/L0 = 0) it is a
  true zero mode, and S is NaN at that point with a warning.
- L and C blocks are read from `f_Z` against their line's Ztx
  (`extras.load_of`): L = Ztx/(2 pi f_Z), C = 1/(2 pi f_Z Ztx). R is
  numeric. `"matched"` R on a physical document is refused.
- Components are planes joined by blocks; only components with a port are
  solved. The order is the first port's plane order.
- `NetworkResult`:
  - `S` is the sector-0 block;
  - `S_sectors[m]` holds out at (p, m), in at (q, 0);
  - `photon(m)` is S sqrt(|f|/|f_m|);
  - `label(p, q, m)` gives the D6 labels;
  - `history` lists (window, metric) for the auto window.

**Depth (D4).** `engine.pump_depth(doc, pumped)` converts the anchor:

    delta = 4 pi rate sqrt(w_n C_n w_m C_m) / |u_n u_m|      (w = 2 pi f, physical units)

- (n, m) is legacy's anchor pair (`clamp_mode`, `pump_partners`, the same
  tie rule as `pump_anchor`).
- u, C, f are LineResonator's loaded/stepped mode quantities.
- TL_3 gives 6 pi^2 rate / Ztx. That is E0's 3 pi^2 rate / FSR times
  2 FSR / Ztx (natural to physical), to 1e-14.
- Not done: storing the depth in the model (see "Open").

**Window (D5).**
- With no pump the window is {0}.
- An explicit [m_lo, m_hi] must contain 0.
- `"auto"` grows {-1..0}, {-2..1}, ... up to `sector_max` sectors and stops
  when the metric drops below `sector_tol`. The metric is the one proposed:
  max |dS| over the smaller window's sectors divided by
  max(max_f max_p ||S_pp^(0)|^2 - 1|, 1e-2). I read "G" as the reflection
  gain: relative for a one-port amplifier, about absolute for a matched
  multiport or for conversion.
- On the cap it warns "not converged", adding "possibly beyond threshold"
  when the peak |S| grew over the last three windows.
- On the shipped files, auto stops at {-3..2} to {-5..4}.

**Gates** (`tests/test_engine_network.py`, 50 tests, all passing):
1. TL_1 against the closed form and against legacy (tail closure on): both
   2e-14. TL_5 in parallel (Y_a + Y_b) against the closed form: 1e-14. A
   two-port stepped line with unequal Z0 against the ABCD S formula; a
   lossy line against complex theta; lossless unpumped |S| = 1.
2. TL_3 against `hb_sectors` at {-1..0}, {-2..1}, {-3..2}, {-4..3} and
   {-6..5}: 4e-14 away from line poles.
   - Within 1e-3 FSR of a pole the oracle's cot/csc loses digits (1.7e-9 at
     f = 6.0000001). That residual is the oracle's.
   - E0's peak table is reproduced to its printed digits (dB and f) at
     rates 0.05, 0.2, 0.8 and 1.6.
3. All 8 pumped files against an HB written in the test. It has its own
   ABCD cascade, its own mode roots (bisection on the real mode
   condition), C_n by Gauss-Legendre and its own anchor rule.
   - Depth agrees to 1e-14. S agrees to at most 2.7e-12 at {-1..0} and
     {-3..2}; the worst case is the Lee nondegenerate amplifier, where
     |S| reaches 7.
   - The test's tolerance is 1e-10 max(1, max|S|).
   - For scale: a 1e-6 change in depth moves S by 1e-8 to 1e-4, so the
     gate discriminates.
4. Manley-Rowe at 1e-12 on all 8 (all are lossless).
5. Kept poles: f_max 14 -> 40 leaves S unchanged (1e-13). The full gate 3
   (promoted poles) belongs to M2b.
6. TL_3 at rate 3.2, capped at 8 sectors: warns "not converged".

**Gate 5, reported** (`misc/msuper_M2a_vs_legacy.py`, `.out`). The
comparison is legacy against M2a in legacy's own two sectors: {-1..0}, or
{0..1} for an up-conversion anchor, since legacy puts that twin at
f + f_p. The first version of the script compared Lee conversion at
{-1..0} and showed an O(1) gap; that was my comparison, not physics.
- **Loaded lines (Lee x3, TL_4, LINE_PUMPED_LOADED).** The gap roughly
  halves each time legacy's f_max doubles (Lee nondegenerate: 0.27, 0.16,
  0.076). That is the dropped pump-tail couplings: legacy pumps comb pairs
  only, and its tail closure covers the port, not the pump.
  - The Lee nondegenerate amplifier peaks at 20.9 dB in two sectors and
    22.3 dB in the converged window.
- **Unloaded lines (TL_3, LINE_PUMPED_TERMINATION,
  LINE_PUMPED_AMP_AND_CONV).** A floor of 2e-3 to 1e-2 does not fall with
  f_max. *(speculation)* It is the DC mode, which legacy's pump never
  couples (tap_couplings drops n = 0). Consistent with that, the residual
  peaks at the sweep edge where the idler frequency is closest to 0. Not
  demonstrated.

**D7.** The preamble of `docs/pumped_line_termination.md` now says
e^{-i omega t}, and so does its section-7 remark.

**JA on the open items (19 Nov):**
- **D4 storage: recompute the rate. Done.**
  - `Pumped.depth` is a schema field (model/pump_depth.py).
  - Migration and loading a 4.0 file without a depth fill it in from the
    anchor. The anchor stays as provenance.
  - `to_legacy` writes the rate recomputed from the depth. When the depth
    is still exactly what the stored anchor rate gives, it writes the stored
    rate verbatim, so unedited files round-trip bit for bit.
  - Editing the line keeps the depth (the S curve moves, the exported rate
    follows); see `test_edit_keeps_the_depth_and_the_rate_follows`.
  - The engine uses `depth`. A hand-built pump with no depth is converted
    from its anchor, with an info issue.
  - Not done yet (GUI slice): the GUI still holds the legacy rate, so an
    FSR edit in the GUI keeps the rate, and the depth is recomputed on save.
    Keeping the depth there belongs with the live-state work.
- **TL_5 (D1):** do it with the Show S switch.
- **Window metric:** JA asked what it meant; explained in chat. Kept as
  built until a reply.
- **Pump phase:** kept as specified (degrees, phi in cos(omega_p t + phi)).

## M2b as built (19 Nov 2026)

**Routing.**
- Physical documents with lumped modes attached directly to planes now go
  to the network. Of the shipped files this adds PORT_SHARED_2LINES.
- Still refused:
  - taps (M2c: TL_2, LINE_TAP_2NODES, NODE_2LINES_TAP);
  - lumped modes together with element pumps;
  - modes outside sector 0 (conjugated, or pumped away from the root) on a
    document with blocks. Both of these are "later" in the build order.
- Lumped documents still go to milestone 1 by default, bit for bit with
  legacy. `solve_network(doc)` also accepts them; that is the M2 path for
  gate 4.

**CMT block (D2, D3).**
- The modes of each milestone-1 component form one block. Its M_iso is
  milestone 1's M without (i/2) K K^dag, so frames, conjugation and pumped
  couplings all carry over unchanged.
- It is stamped bordered, with j = sqrt(Z_ref) I:

      M_iso a - K j = 0,        V / sqrt(Z_ref) - (i/2) K^dag a = 0

  I joins the plane's KCL. M_iso is never inverted.
- Z_ref is read from `units.z_ref` (default 50 ohm; nothing writes it yet).
  Every attachment rate is a leak rate into Z_ref.
- A port without Z0 is terminated in Z_ref, and a matched R is Z_ref. For
  lumped documents this reduces exactly to milestone 1.
- *Physics to check:* a lone mode on a port is y = -2i (f - f0)/(gamma
  Z_ref), i.e. a shunt parallel tank. Away from f0 it is a low impedance
  across the port: the CMT convention's "S = -1 off resonance". So on
  PORT_SHARED_2LINES the two lines are visible only near the mode
  (4.4 GHz); elsewhere the mode's block shorts the port. This follows from
  D1 + D2, but it is the first file where it shows.

**Kept poles (`promote=True`).**
- `solve.kept_poles[line]` is either `{'f_max': F}` (DC when the line has
  it, plus every pole with 0 < f_n <= F) or a list of indices (0 = DC).
- The poles are those of the line together with its load block (absorbed
  into the line element), so they are the loaded ones. Each pole:
  - sits at p_n = f_n - i B/2, with B = 2 alpha FSR / pi;
  - has residue R_n = (i/(4 pi C_n)) u_n u_n^T, twice that for DC
    (autograph.LineResonator's u, C, f).
- Lossy loaded lines are refused: their poles are not at f_n - i B/2
  exactly.
- Rows per pole: (f - p_n) a_n = u_n . I_in. The line's two rows then take
  one of two equivalent forms, chosen point by point:
  - within 0.01 FSR of a kept pole: V - sum R a - Z_rem I_in = 0. Z_rem is
    the mean over a circle of radius 0.02 FSR (16 points), exact because
    Z_rem is analytic there;
  - elsewhere: the pole-free ABCD rows on V_l = V - sum R a +
    sum R I_in/(f - p).
- Why two forms: Z_rem keeps the poles that are not kept. The -f_n partners
  land in sector -1, so the first version, which used impedance rows
  everywhere, lost digits there: 7e-2 at an exact hit on TL_3. The ABCD
  form blows up only at the kept poles, which is exactly where it is not
  used.
- Off by default. S is the same either way, and the plain ABCD rows have no
  poles at all. The rows are the representation a future M_super tab and
  mode-level couplings need.

**Gates** (`tests/test_engine_m2b.py`, 81 tests; all 222 engine tests
pass):
- **Gate 4.** All 54 lumped files through the network match milestone 1 to
  within 1e-13 max(1, max|S|). The median difference is 2e-15. The worst is
  6.6e-12 on DELTA_AMP_WIDE, where |S| = 526 (54 dB), i.e. 1.3e-14
  relative. A loss port (internal plane + matched R) matches to 1e-13.
- **PORT_SHARED_2LINES** against Y_a + Y_b + 1/(Z0 z): 5e-15.
- **Z_ref:** a lone mode reflects as in milestone 1 when Z0 = Z_ref, and as
  the mismatched z/2 when Z0 = 2 Z_ref.
- **Gate 3:**
  - S is invariant when every pole below f_max is promoted, on all 11
    network files and in every sector (the auto windows come out the same).
  - Subsets [0], [3], [1,2,3], [2,5,9] on TL_1 (whose sweep hits pole 3
    exactly) and on TL_3 (all sectors).
  - Tolerance: 1e-11 max(1,|S|)^2. The worst case is 2.7e-12 on Lee
    conversion, beside its barely loaded line mode (port Z0 = 38718 ohm).
    The condition number of the equilibrated system there is 4e3 for both
    forms, so this is rounding at the problem's conditioning; changing the
    circle radius tenfold does not move it. Elsewhere the forms agree to
    1e-15 to 1e-14.
- **Residues and positions** of every kept pole (uniform, loaded, stepped,
  two-line) against a contour integral of the exact impedance: 1e-9. Z_rem
  stays bounded at f_n +- 1e-7 FSR. Uniform loss: the residues hold at
  f_n - i alpha FSR / pi.

## M2c: the D3 derivation (for review, 19 Nov 2026)

Script: `misc/msuper_M2c_tap_physics.py` (`.out`). The circuit is TL_2's
line with its direct port attachment removed, a lossless tank tapped at x0
through Cc, at the legacy rate 0.05 at n_ref = 3.

**What a capacitive tap is, seen from the plane.** Exactly:

    Y_tap = -i w Cs + i w w1^2 Cb / (w^2 - w1^2),   Cs = Cc Cd/(Cc+Cd),  Cb = Cc^2/(Cc+Cd),  w1^2 = 1/(Ld (Cd+Cc))

- That is a shunt capacitor Cs plus a Foster pole pair (+-w1, equal
  residues), i.e. a series-LC branch from the plane to ground. Adding the
  exact Cs to the pole pair reproduces the exact circuit to 1e-12 at every
  device impedance.
- It is admittance-type: open away from resonance. It is the dual of the
  M2b block, which is impedance-type and shorts the plane away from
  resonance. Using the M2b form for this tap is wrong by |dS| = 2.
- The pole pair is fixed by (f1, gamma), with gamma = Z_ref w1^2 Cb / 2 pi
  the leak rate into Z_ref: rates are enough for it, as D3 says.
- Cs is not fixed by (f1, gamma). At fixed gamma, Cc is proportional to
  sqrt(Cd), i.e. it falls with the device impedance Z_d = sqrt(Ld/Cd).
  Dropping Cs costs:

| Z_d [ohm] | 5 | 25 | 125 | 625 | 3125 |
|---|---|---|---|---|---|
| Cs w1 Z_ref | 0.067 | 0.030 | 0.013 | 0.0057 | 0.0024 |
| max dS, pole pair only | 0.27 | 0.12 | 0.053 | 0.023 | 0.0096 |

  The error is first order in the coupling amplitude, ~ sqrt(gamma/f) x
  sqrt(Z_ref/Z_d). It is mostly a broadband phase of the line's response:
  the resonance position agrees with the exact circuit to < 1e-4 GHz at
  every Z_d.
- The counter-rotating partner (pole pair against one RWA pole) changes S
  by 4e-4 here, less than Cs unless Z_d is very high.

**Legacy is not an oracle for taps.** On this circuit its resonance moves
with f_max: 4.3985 GHz at f_max = 9, 4.3933 GHz at f_max = 36. The exact
circuit gives 4.4001 GHz. *(speculation, consistent with this)* The
capacitive profile g_n ~ sqrt(n) makes the comb's dispersive shift sum
g_n^2/(f_d - f_n) grow linearly with N. The oracle has to be the exact
circuit, as the note already said.

**Inductive tap** (cmtline_core's flux coupling, kL in the inverse
inductance matrix): derived, not yet checked numerically. It should be

    y = (i/2) gamma [1/(f - f1) + 1/(f + f1) - 2/f]

That is the same pole pair plus a shunt-inductor term whose size is fixed
by gamma, so no element value is needed.

**Anchor conversion (proposed).** gamma = rate^2 2 pi Z_ref C_n / u_n^2 at
n_ref, which gives legacy's splitting with mode n_ref at resonance.

**Decisions needed (JA):** see the chat of 19 Nov. The questions:
- the tap form;
- Cs: drop it, or store something to make it exact;
- the partner pole;
- direct attachments on physical documents (impedance or admittance type);
- the anchor rule.

## M2c decisions (JA, 26-27 Nov 2026)

The five questions above were asked from this note alone. JA's theory
(CMT-Theory repo; `cmt_msuper_lectures` v38, 23 Nov) had already settled
the form, and the tap reduces to it:

- **Q1, the tap form: impedance (Foster I, "B") everywhere.** A mode
  attaches to a node as a parallel tank; its K entry is sqrt(gamma) with
  gamma = 1/(2 pi Z_ref C), C the mode's own pole residue (its tank
  capacitance), independent of whatever circuit sits between the node and
  the ports.
- **Q2, Cs: no approximation.** The coupling capacitor C_c is a circuit
  element in Sigma_0 between the tank's node and the line end. Cs is not a
  separate quantity: it is what C_c in series with C_d looks like from the
  plane. This overrides D3's "no coupling-element values" for taps.
- **Q3, the partner pole: a user option, with an RWA flag.** On by default
  for physical documents (`solve.images`). See "M2c as built" for the number
  the RWA checker should use.
- **Q4, direct attachments: B,** as M2b already does. Anything physically
  between a mode and a plane (a coupling C or L) is a Sigma_0 element.
- **Q5, legacy anchors.** A tap's rate at n_ref converts to C_c given the
  tank's capacitance. A direct port attachment fixes it; otherwise the file
  is a validation error asking for the LC mode impedance Z_d = sqrt(L/C).
  Nothing is guessed.

## M2c as built (27 Nov 2026)

`model/taps.py` rewrites a document's capacitive taps before the network
is compiled (`resolve_taps`); `engine/network.py` builds C blocks from an
element value and gives each CMT block its image rows.

**The rewrite, per tapped mode** (frequency f1 as drawn, w1 = 2 pi f1):
- The mode as drawn is the tank with every coupling capacitor to ground:
  C_sum = C_d + sum_k C_c,k, L_d = 1 / (w1^2 C_sum).
- Each tap's legacy rate is its coupling to line mode n_ref at resonance
  (weak-coupling capacitance matrix, CMT-Theory `better_derivation.md`
  sec. 7.2):

      rate_k = w1 C_c,k u_k / (2 pi sqrt(C_sum C_n,k))

  u_k and C_n,k are the line's loaded/stepped mode amplitude at the tapped
  end and mode capacitance at n_ref. For one tap this is the M2c anchor
  gamma = rate^2 2 pi Z_ref C_n / u^2 above (gated).
- C_sum from: (1) a direct attachment (the legacy port coupling, rate
  gamma_p): that plane is the tank's node and C_d = 1/(2 pi Z_ref gamma_p),
  then sqrt(C_sum) solves a quadratic; (2) `Mode.extras['Z_d']`, read as the
  impedance of the mode as drawn, Z_d = sqrt(L_d / C_sum), so
  C_sum = 1/(w1 Z_d); (3) otherwise an error (`tap_issues`, also reported by
  `validate`), and the component's S is None.
- The rewritten mode sits at the bare frequency f0 = 1/(2 pi sqrt(L_d C_d)),
  attached to its node (the direct plane, or a new internal plane
  `<mode>.node`) at gamma_d = 1/(2 pi Z_ref C_d). Each tap becomes a C
  block (farads in `params['C']`). The resolved values are kept in
  `Mode.extras['tap_resolved']` of the rewritten copy.
- Inductive taps are refused.

**Images.** `CMTBlock.M_rows` is blockdiag(M_iso, 2f - conj M_iso), with K
rows [K; conj K]. For M_iso = f - H the image block is f + conj(H), so its
z is conj(z_main(-f)) and the sum obeys z(-f) = conj z(f). For one mode
this is the parallel tank's Foster pair, (i/2) gamma [1/(f-f0) + 1/(f+f0)],
exact. Drawn mode-mode edges get their conjugates among the images and no
counter-rotating cross terms (the RWA checker's level 2). Default: on for
physical documents, off for lumped ones (milestone 1 stays bit for bit).

**The RWA-checker number for an embedded mode.** The 1/2Q rule (v38 sec.
3.6) with the physical Q is the wrong yardstick behind Sigma_0. On TL_2's
tap Q = 4.4 GHz / 2 MHz = 2200, yet dropping the image is O(1) wrong at
large Z_d. What sets it is the pull d = f1 - f0 that C_c gives the tank:
deleting the image moves the dressed resonance by d^2/(2 f0) (v38 sec. 3.7,
level attraction with the image). Measured against that prediction to
< 1 % (Z_d 5 to 3125 ohm; gated at 125 and 625 ohm):

| Z_d [ohm] | d [MHz] | d^2/2f0 [MHz] | in linewidths |
|---|---|---|---|
| 5 | -15 | 0.025 | 0.01 |
| 125 | -76 | 0.64 | 0.32 |
| 3125 | -406 | 17.1 | 8.5 |

Proposed level-1 flag: (d^2 / 2 f0) / gamma > eps.

**Gates** (`tests/test_engine_m2c.py`, 20 tests): S against an independent
nodal solve of the physical circuit (line two-ports, series C_c, shunt
tanks) with the element values the rewrite reports: one tap at Z_d 5 to
3125 ohm, TL_2 as shipped (two ports; the direct port fixes C_d), two
modes on one line end, one mode on two lines. All within 1e-10 (the
oracle's own cos/sin near the line poles sets the floor). Also: the anchor
relations, the image-deletion shift, images off for lumped documents, the
missing-Z_d error, inductive taps refused, schema round trip of the
rewritten document.

**Shipped files.** TL_2 solves (its direct port fixes C_d). LINE_TAP_2NODES
and NODE_2LINES_TAP report the missing-Z_d error until Z_d is set;
`tests/test_model_roundtrip.py` expects that error for those two files.

## Show S through the engine (27 Nov 2026)

Show S now solves with `engine.solve` (JA, 27 Nov: wire the engine first).
`engine/gui_payload.py` puts each result in the dict the plot code was
written against (`legacy_job.compute_job`'s): `S`, `SdB`, `port_ids`,
`port_dict`, `drive_signals`, component index and label. Only the
bookkeeping is legacy's.

- **The GUI hook.** `Graphulator._sparams_show_s_jobs` snapshots the live
  state as a Document and hands the worker one engine job for the whole
  document. The worker (`_compute_engine_job`) falls back to the legacy jobs
  when the engine refuses the document (NotSupportedError, TapError) and the
  status bar says so. Action > *Solve S with the Legacy Engine* (or
  `GRAPHULATOR_S_ENGINE=legacy`) switches Show S back to legacy, for
  comparison. The tail-closure check in the Ports panel still runs legacy:
  it is a legacy diagnostic.
- **Channels of a physical document.** Each port in sector 0, then each
  sector view the drawing has of a port (a twin's port). Inputs in a
  nonzero sector are extra right-hand sides of the same solve
  (`solve_window_inputs`), so S over the channels is exact, not a symmetry
  reconstruction.
- **Normalization: photon flux.** `NetworkResult.S_channels` is
  S sqrt(|f_in| / |f_out|), the normalization legacy's CMT S has and the one
  Manley-Rowe conserves. Sector-0 entries are unchanged.
- **The twin's sector is the pump's partner sector, not -1.** Legacy reads
  TL* at f - f_p for an amplification or down-conversion anchor and at
  f + f_p for up-conversion (`legacy_job.pump_frame_rule`). Migration
  stores every twin as sector -1, so `network._twin_sectors` takes the
  sector from the anchor family. *Open (model):* store a twin as "the
  partner sector of pump X" rather than an integer, or fix migration.
- **Gate** (`tests/test_gui_show_s_engine.py`, every shipped file opened in
  the GUI): port refs, labels, conj flags, drive frames and component labels
  equal legacy's wherever both split the same components; lumped S is bit
  for bit; physical S is finite where legacy's is. Plus: the missing-Z_d
  scenes show the error instead of a plot, the legacy switch, the fallback,
  and the worker end to end.

**What moves on screen (physical documents only), against legacy:**

| file | max abs dS | why |
|---|---|---|
| TL_1 | 2e-14 | legacy exact here |
| TL_3, LINE_PUMPED_TERMINATION, TL_4, LINE_PUMPED_LOADED | 1e-3 to 1e-2 | DC mode / dropped pump-tail couplings (gate 5 above) |
| LINE_PUMPED_AMP_AND_CONV | 0.22 | idler 0.5 GHz at the sweep edge, the DC-mode region; engine conserves photons to 5e-15 |
| Lee degenerate / nondegenerate amp | 0.12 / 12 | truncated comb; the nondegenerate gain is 22.3 dB, not 20.9 |
| Lee conversion | 2 | magnitude within 0.1; the off-diagonal sign is opposite (a gauge of the idler amplitude, see below) |
| TL_2 | 0.55 | exact tap (M2c) vs legacy's rate model |
| PORT_SHARED_2LINES, TL_5 | O(1) | one shared port (D1) vs legacy's split |

The conversion off-diagonals (non-conjugate partner sector) come out with
the opposite sign to legacy's; |S| and every diagonal agree. Flipping the
sign of the idler channel's amplitude flips both off-diagonals and nothing
else, so it is a convention, not physics. Left as the engine has it.

## Z_d in the GUI (27 Nov 2026)

The Scattering tab's node table gets a **Z_d [ohm]** column for the modes
that need it: tapped onto a line through a coupling capacitor and not
attached directly to a plane (`Graphulator._modes_needing_z_d`, from
`taps.tap_groups` and `taps._direct` on the model snapshot). Unset, it shows
grey and stores nothing, so the plot keeps the missing-Z_d error (decision
Q5: nothing guessed). The value lives in `scattering_assignments[node]['Z_d']`,
is written as the node's `Z_d` key in 2.0/3.0 dicts, and migrates to
`Mode.extras['Z_d']` (`NODE_PHYS` now includes it, so it is physics, not
drawing). Gates in `tests/test_gui_show_s_engine.py`: both tap scenes solve
(finite, |S| <= 1) once Z_d is typed; Z_d survives a 4.0 save and reload;
TL_2 (direct port) asks for none.

## The RWA flag (27 Nov 2026)

`engine/rwa.py`. After every engine Show S on a physical document with CMT
modes, `rwa_check` solves again with `solve.images` flipped and reports:

- **Measured cost:** max |S_images - S_rwa| over the sweep and every drawn
  channel, with where and which trace. No rule of thumb in between.
- **Predicted, per tapped mode:** the pull d = f_drawn - f_bare and the image
  shift d^2 / (2 f_bare), which explains the measured cost (v38 sec. 3.7).

Flag: |dS| > `RWA_TOL` = 0.01. With images kept it is an info line ("the RWA
would change S by ..."); with the RWA in use it is a warning, and the
Ports & Lines checkbox **keep image poles (no RWA)** shows a warning sign.
The checkbox sets `solve.images` (now carried by the GUI like the sector
settings, so it is saved in the 4.0 file); the last report is its tooltip.
Lumped documents get no report (RWA by construction, milestone 1).

Measured on the shipped scenes (`examples/test_scenes/MSUPER_3_RWA`):
- A tank on a port (TL_2, gamma_p = 0.1, f0 = 4.4): |dS| = 0.0136 at the
  sweep edge, against 1/2Q_ext = 0.011 (sec. 3.6: first order, largest off
  resonance).
- A tapped mode (Z_d 1 to 625 ohm): the measured resonance shift equals
  d^2/2f0 to 1 % (-0.046, -0.231, -1.184 MHz at 25, 125, 625 ohm, linewidth
  0.73 MHz); |dS| 0.0098 to 2.0. On a lossless one-port |dS| ~ 2 sin(2 delta/kappa),
  so a shift of a third of a linewidth already gives |dS| ~ 1.
- The tolerance is a choice (JA to confirm): 0.01 flags TL_2's 1/2Q_ext.
