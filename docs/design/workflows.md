# Abstract and physical workflows (design note, for review)

*Status: discussion record, 18 Nov 2026 (JA and Claude). Captures the
discussion that grew out of question L3 of the Layer-0 live-state design
pass (`layer0_document_model.md`). Items marked **[decided]** are JA's
calls. **[open]** items need a decision before the step that depends on
them. Physics remarks marked *(proposal)* are Claude's suggestions and have
not been tested.*

## The two workflows

1. **Abstract.** You draw a graph to see what network topologies do. The
   graph *is* the equations. You apply the RWA yourself by choosing which
   modes to draw, which to conjugate, and which pumped edges (f_p) to add.
   Embedding circuits (lines, stubs, ...) are not available here: Sigma_0
   holds only the ports, so M = M_iso plus the port loading.
2. **Physical.** You describe physical resonances, ports (some shared),
   embedding circuits, and modulated elements. The pump scales pair rates
   from one reference pairing beta, and later from a transfer function. The
   app applies the RWA and generates the extra modes (sector images), wired
   with the usual single/double-edge and conjugation conventions. You
   arrange them on the canvas.

Both workflows can show M_iso and M. M is more interesting with an embedding
circuit, because the reduction M = M_super / Sigma_0 adds loading terms.
How much of that is broken out at each level is a later discussion.

## Structure: physical compiles to abstract **[decided in principle]**

```
physical document --generate--> abstract graph --compile--> M_super --Schur(Sigma_0)--> M, M_iso
```

"The graph is the graph." A physical document never solves anything the
abstract graph cannot express. It *generates* an abstract graph, and the
canvas shows that graph. The Layer-0 schema already separates the two:
- `Mode.origin`: `lumped` (drawn) vs generated (`line_pole`, sector images);
- `Pumped(kind="coupling")` (abstract pumped edge) vs `Pumped(kind="element")`
  (physical modulated element);
- drawing keyed by physics ids.

The existing pumped line is the first instance of the physical pump: its
`pump.rate` at `n_ref` is beta, and the mode-profile scaling to other pairs
plays the role of the transfer function.

## Ownership and the workflow flag **[decided]**

- A document is marked **physical** or **abstract**. In a physical
  document, additions to the graph are constrained by the physical model.
  Generated objects are read-only and are regenerated from their sources.
  Their canvas positions survive regeneration because their ids are
  deterministic, built from the origin (e.g. `line0.n3.s-1`).
- A physical document **with no embedding circuit** can be switched to
  abstract. Its generated objects are frozen into ordinary drawn modes. The
  switch is **one-way**, and the user gets a warning.
- **The interface must show the workflow plainly:** a label near the top
  or in the title bar, possibly a light/dark theme per workflow (which theme
  goes with which workflow is set in Settings).
- Saving over a physical document with an abstract one (same name) warns.
- **W1, file naming [decided]:** one format with a `workflow` field;
  `.pgraph` for both (an optional `.pmgraph` dialog convention only, never
  the source of truth). **Guardrails** on a physical -> abstract
  conversion:
  - The conversion never overwrites the physical file silently. The default
    action is Save As with a derived name (e.g. `name_abstract.pgraph`).
    Overwriting needs an explicit confirmation that says the physical
    description will be lost.
  - The converted document records where it came from
    (`meta.converted_from`: path and content hash of the physical source).
    The app can then say "this was generated from X". Conversion stays
    one-way.

## RWA checking (the "RWA nanny")

**Where it lives.** It is a Qt-free validation check: `validate(doc)`
issues, or a sibling `model/rwa.py`. Its views are a warning box in the
scattering-assignment panel and a button that opens a modeless window. The
window lists the modes, by resonator, that may need attention, and you can
keep editing the canvas while it is open. The threshold eps has a default
and is settable in Settings **[decided]**.

**Level 1: cheap estimate** *(proposal)*.
- For each drawn coupling g, look at the terms the drawing implicitly drops:
  for a static edge, the counter-rotating a.b term near w_a + w_b; for a
  pumped edge, the other mixing products. Each oscillates at some Omega in
  the frame of the drawn sectors.
- To second order, a dropped term shifts frequencies by about g^2 / Omega
  (Bloch-Siegert-like). For S-parameters, the useful comparison is that
  shift against the linewidth kappa: flag when g^2 / (Omega * kappa) > eps.

**Limitation (JA).** The abstract graph cannot say that several modes
belong to *one* physical resonator. Example: one modulated LC tank with a
small pump frequency (w_P << gamma_0) has sector images at w, w +- w_P, ...
of the *same* resonance. A graph today has no way to express that, so
level 1 cannot reason about it in the abstract workflow. The physical
workflow makes it natural: one resonance, plus a sector window that
generates the images.
- **W2, "same resonator" tag [decided: yes].** Modes get an optional
  `resonator` tag (resonator id plus sector index m) that marks drawn nodes
  as sector images of one physical resonator.
  - Ways to set it: the node parameters panel (a "Resonator" field), the
    right-click menu on a selection ("Mark as one resonator..."), and/or a
    grouping column in the S-parameter assignment panel.
  - What the tag enables:
    - the nanny can reason about images (e.g. w_P << gamma_0);
    - a consistency check that freq_m = w_0 + m * w_P;
    - optionally, frequencies auto-filled from (w_0, m, f_p), through the
      constraint-group mechanism (members by id, decision L4).

**Level 2: exact check** *(proposal)*.
- Complete each drawn edge to its non-RWA form, g(t)(a + a^dag)(b + b^dag),
  solve through M_super with the sector window opened, and compare S with
  the as-drawn solve. This reuses the sector-convergence machinery
  (layer-0 decision 5).
- **Coupling type [decided].** The completion depends on the bilinear
  coupling type (x-x, p-p, x-p), mainly through signs of loop phases
  (summed pump phases around graph cycles). The type is part of each
  pairwise coupling's description and defaults to **x-x**.
- **Cost [decided].** The check must finish in under about 1 minute. If a
  run is expected to take longer, warn before starting. The non-RWA basis
  can get large. The check matters for validating the app and also for
  validating more complicated experiments.

## Canvas conventions for hidden modes **[decided in outline]**

- A modulated termination couples modes hidden inside the embedding
  circuit. Those modes are shown or hidden with a **toggle**, and the
  element gets a **decoration** saying it has hidden modes.
- Coupled chains can be huge: a dispersionless pumped line couples
  everything to everything. Showing them is **truncated to a maximum**,
  with a warning.
- Sectors are drawn as **one stacked-line glyph for the positive sectors
  and one for the negative / counter-rotating sectors**. The glyph looks
  like a few lines piled on top of each other, labelled with its sector
  range, e.g. `{0:2:8}` or `{-5:2:-1}`. In the schema this is one
  `drawing.sector_views` entry per sector range rather than per sector.
- Transmission lines and other embedding circuits belong to the
  **physical workflow only**.

## Physical-workflow pump model (later phase) **[W3: proposed depth, JA to confirm]**

Proposed stopping point: levels 1-2 below are in, level 3 is out.

1. **Linear.** w_k(phi_dc + dphi cos w_P t) ~ w_k + w_k' dphi cos w_P t
   gives the pair rates g_jk at w_P. This is today's pumped-line anchor,
   generalized.
2. **Harmonics and the static shift.** Use the full transfer function
   (user-supplied w_k(phi) or L(phi), with the SQUID form
   L_J0 / |cos(pi phi / phi_0)| built in). Its Fourier series in w_P gives:
   - the depth at n w_P. In M_super a harmonic of one tone is just a
     coupling between sectors m and m + n, so this is cheap;
   - the n = 0 term, a pump-induced static shift of every w_k (order
     dphi^2). It must be included, or the resonances sit in the wrong
     place at large dphi.
3. **Out of scope (the real rabbit holes):**
   - calibrating applied pump power to dphi (the pump's own circuit and
     port);
   - pump depletion;
   - signal-power nonlinearity (Kerr). The model stays linear in the
     signal;
   - participations p_j for arbitrary embedding networks beyond what pole
     residues give (lines already have them).

Notes from the discussion:

- **Inputs.** Modulated elements with a transfer function, e.g. w_k(phi) or
  w_k^2(phi), with phi(t) = phi_dc + dphi cos(w_P t).
- **Harmonics.** Expanding w_k(phi(t)) in harmonics of w_P gives the
  harmonic content. Start with the linear approximation; harmonics come from
  the transfer function.
- **Pair rates.** A shared modulated element gives
  g_jk ~ sqrt(w_j w_k) p_j p_k with participations p *(proposal, the usual
  energy-participation scaling)*. They are expressed relative to one
  reference pairing beta, to stay abstract.
- **No graph at all.** Modulating a bare inductor needs no pole under
  M_super. The modulated element sits in Sigma_0, and the sector expansion
  couples its rows. Modelling it as a very high-frequency pole (a junction
  plasma frequency) is the approximation one would make without M_super.
- **Embedding circuits with their own resonances** (embedded line or stub
  resonators) need effective coupling rates to the poles seen from M_iso,
  looking into the embedding circuit (the input immittance toward the
  ports).
- This workflow needs a **pedagogical tutorial**: tool tips and a
  structured walk-through.

## Effect on the build plan

1. **Step 4, milestone 1 (next):** the abstract workflow through M_super.
   Lumped graphs and ports only, **solved exactly as drawn** (the user's
   RWA). No automatic sector expansion; non-RWA only through the nanny
   **[decided]**. Gate: bit-for-bit against the legacy engine on every
   lumped shipped file.
2. **Before step 4 milestone 2** (embedding circuits, element pumps, sector
   windows) **and before live-state slice C2** (twin -> sector views):
   settle W1-W3 and the generate step's design.
3. Live-state slices C1, C3 and C4 are unaffected and follow the L1 order.
