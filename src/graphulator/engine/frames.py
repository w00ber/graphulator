"""Frames (sectors) of the drawn modes for the abstract workflow.

Each drawn mode k sits in one sector m_k (integers over the document's
nonzero pump tones): it is driven at f + nu_k with nu_k = m_k . f_tones,
relative to the component's root. The drawing chooses one (mode, sector) row
of M_super per mode; that choice is the user's RWA.

The rule is the legacy one (design note docs/design/step4_msuper_m1.md,
decision M1 option b): a spanning tree is grown from the root, and each tree
edge moves the sector by +-e_t for a pump at tone t (sign: up-conversion when
the child's effective frequency, -f_0 for a conjugated mode, is higher) or
by 0 for a static edge (f_p = 0) or a shared-port bridge. f_p is an input on
tree edges only; a chord's pump frequency is derived from its cycle, and a
value stored on a chord is ignored (reported when it disagrees).

The tree itself is autograph's (``compute_spanning_tree``, with
``compute_hub_bridge_links``), called with the same node keys and edge order
as the legacy job, so the two engines pick the same tree. Which tree that is
depends on the root and the DFS order; making the tree document data is
planned for live-state slice C1.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..autograph import GraphExtractor, _edge_key, compute_hub_bridge_links


@dataclass
class EdgeRec:
    """One drawn edge, in the legacy edge order.

    tone_f: the pump frequency; None for a Coupling (f_p never entered: only
    legal on a chord), 0.0 for a static edge.
    """
    id: str
    a: str
    b: str
    self_loop: bool
    rate: Optional[float] = None
    phase: Optional[float] = None
    tone: Optional[str] = None
    tone_f: Optional[float] = None
    physical: bool = True          # False: drawing-only B_ext marker loop


@dataclass
class Frames:
    sectors: Dict[str, Tuple[int, ...]]        # reached modes only
    offsets: Dict[str, float]                  # round(m . f, 12), reached modes only
    tree: List[Tuple[str, str]]                # oriented (parent, child)
    chords: List[Tuple[str, str]]
    chord_fp: Dict[Tuple[str, str], float]     # derived pump frequency per chord
    missing_fp: List[str] = field(default_factory=list)   # tree edges without f_p
    notes: List[str] = field(default_factory=list)        # stale chord values


def _eff(freq, conj):
    return -freq if conj else freq


def assign_frames(mode_ids: Sequence[str], keys: Dict[str, Any], modes: Dict[str, Any],
                  edges: Sequence[EdgeRec], hub_attachments: Sequence[Sequence[str]],
                  root: str, tone_ids: Sequence[str],
                  tone_f: Sequence[float]) -> Frames:
    """Sectors of one component's modes.

    keys: mode id -> the node key the legacy job uses (its int node id), so
    that the DFS sees the same keys and therefore picks the same tree.
    tone_ids / tone_f: the nonzero tones, defining the sector axes.
    """
    inv = {keys[m]: m for m in mode_ids}
    gui_nodes = [{'node_id': keys[m]} for m in mode_ids]
    gui_edges = [{'from_node_id': keys[e.a], 'to_node_id': keys[e.b],
                  'is_self_loop': e.self_loop} for e in edges]
    links = compute_hub_bridge_links(
        [keys[m] for m in mode_ids],
        [(g['from_node_id'], g['to_node_id']) for g in gui_edges if not g['is_self_loop']],
        [[keys[m] for m in atts] for atts in hub_attachments])
    gui_edges += [{'from_node_id': a, 'to_node_id': b, 'is_self_loop': False}
                  for a, b in links]
    tree_nested, chord_list, _ = GraphExtractor().compute_spanning_tree(
        gui_nodes, gui_edges, keys[root])

    lookup = {}
    for e in edges:                       # last wins, as the legacy edge_lookup
        if not e.self_loop:
            lookup[_edge_key(keys[e.a], keys[e.b])] = e
    link_set = set(links)

    adj: Dict[Any, List[Any]] = {}
    for branch in tree_nested:
        for p, c in branch:
            adj.setdefault(p, []).append(c)
            adj.setdefault(c, []).append(p)

    axis = {t: i for i, t in enumerate(tone_ids)}
    zero = (0,) * len(tone_ids)
    out = Frames(sectors={}, offsets={}, tree=[], chords=[], chord_fp={})
    if adj:                               # a lone mode is not in drive_signals
        out.sectors[root] = zero
    seen = {keys[root]}
    queue = deque([keys[root]])
    while queue:
        p = queue.popleft()
        for c in adj.get(p, []):
            if c in seen:
                continue
            seen.add(c)
            queue.append(c)
            pm, cm = inv[p], inv[c]
            out.tree.append((pm, cm))
            step = zero
            rec = lookup.get(_edge_key(p, c))
            if rec is None:
                assert _edge_key(p, c) in link_set
            elif rec.tone_f is None:
                out.missing_fp.append(rec.id)
            elif rec.tone_f != 0:
                up = (_eff(modes[cm].freq, modes[cm].conj)
                      > _eff(modes[pm].freq, modes[pm].conj))
                v = list(zero)
                v[axis[rec.tone]] = 1 if up else -1
                step = tuple(v)
            out.sectors[cm] = tuple(x + y for x, y in zip(out.sectors[pm], step))

    for m, vec in out.sectors.items():
        out.offsets[m] = round(float(sum(k * f for k, f in zip(vec, tone_f))), 12)

    for a, b in chord_list:
        am, bm = inv[a], inv[b]
        out.chords.append((am, bm))
        derived = round(abs(out.offsets.get(bm, 0.0) - out.offsets.get(am, 0.0)), 12)
        out.chord_fp[(am, bm)] = derived
        rec = lookup.get(_edge_key(a, b))
        if rec is not None and rec.tone_f is not None and rec.tone_f != derived:
            out.notes.append(
                f"edge {rec.id} is a chord: its pump frequency is derived "
                f"from its cycle ({derived}); the stored f_p {rec.tone_f} is ignored")
    return out
