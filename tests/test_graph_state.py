"""Tests for para_core.graph_state — full-fidelity undo/redo snapshots.

The old undo implementation copied an allow-list of fields, silently
dropping anything added to the schema later (looptheta, label background
colors, outline styling, ...). These tests pin the new behavior: every
field survives, and edge -> node dict aliasing is preserved.
"""

from graphulator.para_core.graph_state import capture_graph_state


def make_fixture():
    """A graph exercising every known node/edge field, including the ones
    the old allow-list undo used to drop."""
    node_a = {
        'node_id': 0, 'label': 'A', 'pos': (0.0, 0.0),
        'color': 'indianred', 'color_key': 'RED',
        'node_size_mult': 1.5, 'label_size_mult': 0.8,
        'conj': True, 'nodelabelnudge': (0.1, -0.2),
        # fields the old undo dropped:
        'outline_enabled': True, 'outline_color': 'black',
        'outline_color_key': 'BLACK', 'outline_width': 2.0,
        'outline_alpha': 0.7,
        'numeric_properties': {'Q': 1e4}, 'code_properties': 'x = 1',
    }
    node_b = {
        'node_id': 1, 'label': 'B', 'pos': (2.0, 0.0),
        'color': 'cornflowerblue', 'color_key': 'BLUE',
        'node_size_mult': 1.0, 'label_size_mult': 1.0,
        'conj': False, 'nodelabelnudge': (0.0, 0.0),
    }
    edge = {
        'from_node': node_a, 'to_node': node_b,
        'from_node_id': 0, 'to_node_id': 1,
        'label1': 'g', 'label2': 'g*',
        'linewidth_mult': 2.0, 'label_size_mult': 1.1,
        'label_offset_mult': 1.3, 'style': 'loopy', 'direction': 'both',
        'flip_labels': True, 'label_rotation_offset': 15,
        'is_self_loop': False,
        # fields the old undo dropped:
        'looptheta': 75,
        'label1_bgcolor': 'white', 'label2_bgcolor': None,
        'numeric_properties': {'rate': 0.5},
    }
    self_loop = {
        'from_node': node_a, 'to_node': node_a,
        'from_node_id': 0, 'to_node_id': 0,
        'label1': 'k', 'label2': '',
        'linewidth_mult': 1.0, 'label_size_mult': 1.0,
        'label_offset_mult': 1.0, 'style': 'single', 'direction': 'forward',
        'flip_labels': False, 'label_rotation_offset': 0,
        'is_self_loop': True,
        'selfloopangle': 45, 'selfloopscale': 1.2, 'arrowlengthsc': 0.9,
        'flip': True, 'angle_pinned': True,
        # fields the old undo dropped:
        'selflooplabelnudge': (0.3, 0.4), 'label_bgcolor': 'yellow',
    }
    return [node_a, node_b], [edge, self_loop]


def test_snapshot_preserves_every_field():
    nodes, edges = make_fixture()
    snap = capture_graph_state(nodes, edges)
    assert snap['nodes'] == nodes
    assert snap['edges'] == edges


def test_snapshot_is_independent_of_live_state():
    nodes, edges = make_fixture()
    snap = capture_graph_state(nodes, edges)
    original = capture_graph_state(nodes, edges)  # second copy for comparison

    # Mutate the live graph in every category the old undo used to lose
    nodes[0]['pos'] = (99.0, 99.0)
    nodes[0]['outline_width'] = 5.0
    nodes[0]['numeric_properties']['Q'] = 0
    edges[0]['looptheta'] = 30
    edges[0]['label1_bgcolor'] = 'red'
    edges[1]['selflooplabelnudge'] = (0.0, 0.0)

    assert snap['nodes'] == original['nodes']
    assert snap['edges'] == original['edges']


def test_snapshot_preserves_edge_node_aliasing():
    nodes, edges = make_fixture()
    snap = capture_graph_state(nodes, edges)

    # edge['from_node'] must reference the copied node dict, not a second copy
    assert snap['edges'][0]['from_node'] is snap['nodes'][0]
    assert snap['edges'][0]['to_node'] is snap['nodes'][1]
    assert snap['edges'][1]['from_node'] is snap['nodes'][0]
    assert snap['edges'][1]['to_node'] is snap['nodes'][0]
    # ... and not the live dicts
    assert snap['nodes'][0] is not nodes[0]


def test_extra_state_is_snapshotted():
    """Paragraphulator snapshots scattering state alongside the graph.
    Stable keys (node_id ints, (from, to) tuples) must survive deepcopy."""
    nodes, edges = make_fixture()
    assignments = {
        0: {'freq': 6.0, 'B_int': 0.001, 'B_ext': 0.02},
        (0, 1): {'f_p': 2.0, 'rate': 0.5, 'phase': 90.0},
    }
    groups = {1: {'param_name': 'freq', 'obj_type': 'node',
                  'members': ['A', 'B'], 'value': 6.0}}
    snap = capture_graph_state(nodes, edges, extra={
        'scattering_assignments': assignments,
        'scattering_constraint_groups': groups,
        'next_constraint_group_id': 2,
    })

    assignments[0]['freq'] = -1.0
    groups[1]['members'].append('C')

    assert snap['scattering_assignments'][0]['freq'] == 6.0
    assert snap['scattering_assignments'][(0, 1)]['phase'] == 90.0
    assert snap['scattering_constraint_groups'][1]['members'] == ['A', 'B']
    assert snap['next_constraint_group_id'] == 2
