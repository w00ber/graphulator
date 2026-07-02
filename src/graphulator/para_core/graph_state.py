"""Full-fidelity graph state snapshots for undo/redo.

Both Graphulator and Paragraphulator keep their graph as plain node/edge
dicts, where each edge holds direct references to its endpoint node dicts
(``edge['from_node'] is node``). Earlier undo implementations copied an
explicit allow-list of fields, which silently dropped any field added to
the schema later (loop theta, label background colors, outline styling,
numeric properties, ...). Snapshotting with a single :func:`copy.deepcopy`
copies every field, and the deepcopy memo preserves the edge-to-node
aliasing, so no reconnection logic is needed on restore.
"""

import copy


def capture_graph_state(nodes, edges, extra=None):
    """Deep-copy the full graph state for the undo/redo stacks.

    Args:
        nodes: List of node dicts.
        edges: List of edge dicts (may reference node dicts from ``nodes``;
            the aliasing is preserved in the copy).
        extra: Optional dict of additional state to snapshot alongside the
            graph (e.g. scattering assignments). Merged into the snapshot
            at the top level.

    Returns:
        dict: A fully independent snapshot with at least 'nodes' and
        'edges' keys, plus any keys from ``extra``.
    """
    state = {'nodes': nodes, 'edges': edges}
    if extra:
        state.update(extra)
    return copy.deepcopy(state)
