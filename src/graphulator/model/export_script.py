"""Layer 0 step 3, slice 3: the scattering-code export, rendered from the model.

``scattering_script(doc, ...)`` returns the Python script that the GUI's
"Export to .py" / "Export to Paste Buffer" buttons write. It is rendered
from ``compile_jobs(doc)``, the same job list Show S solves, and the script's
``solve()`` repeats ``compute_job`` step by step through the public autograph
API (spanning tree with hub bridge links, the conjugate-root frequency flip,
the comb tail closure). So the exported script computes Show S's S, bit for
bit (tests/test_model_export_script.py); it no longer has its own reading of
the GUI state.

Numbers are written with ``repr`` (exact round trip), not rounded: a rounded
literal is a different circuit. Constraint groups become shared variables,
used only for members whose value equals the group's exactly.

No Qt is imported here.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from .legacy_job import compile_jobs
from .migrate import to_legacy
from .schema import Document

#: constraint-group parameter -> variable-name prefix in the script
_VAR_PREFIX = {'freq': 'omega0', 'B_int': 'gamma_int', 'B_ext': 'gamma_ext',
               'f_p': 'omegaP', 'rate': 'gP', 'phase': 'phiP'}
#: parameters the GUI stores in milli-units in a constraint group's value
_MILLI = ('B_int', 'B_ext', 'rate')

_COLORS = ('indianred', 'cornflowerblue', 'darkseagreen', 'sandybrown',
           'mediumpurple', 'mediumaquamarine', 'gray')

# compute_job, written out against the public API. Kept in step with
# model.legacy_job.compute_job by the bit-identical gate.
_SOLVE = '''
def solve(nodes, edges, assignments, hubs, line_resonators, root_node_id,
          frequencies, tail_closure=True):
    """One connected component -> GraphScatteringMatrix (None if a
    parameter is unassigned). Same steps as the GUI's Show S."""
    extractor = GraphExtractor()
    if nodes and not line_resonators:
        # spanning tree over the drawn graph, with zero-offset bridge links
        # across shared ports so hub-bridged subgraphs stay in one frame
        tree_nodes = [{'node_id': n['node_id']} for n in nodes]
        tree_edges = [{'from_node_id': e['from_node_id'], 'to_node_id': e['to_node_id'],
                       'is_self_loop': e['is_self_loop']} for e in edges]
        links = compute_hub_bridge_links(
            [n['node_id'] for n in nodes],
            [(e['from_node_id'], e['to_node_id']) for e in tree_edges
             if not e['is_self_loop']],
            [[a[0] for a in h['attachments']] for h in hubs])
        tree_edges += [{'from_node_id': a, 'to_node_id': b, 'is_self_loop': False}
                       for a, b in links]
        branches, chords, _ = extractor.compute_spanning_tree(
            tree_nodes, tree_edges, root_node_id)
        tree = [[a, b] for branch in branches for a, b in branch]
    else:
        # with line macros the comb modes exist only after the extractor's
        # expansion pre-pass, so it builds the tree (and picks the root)
        tree = chords = root_node_id = None
    extractor.extract_graph_data(
        nodes=nodes, edges=edges, scattering_assignments=assignments,
        frequency_settings={'start': frequencies[0], 'stop': frequencies[-1],
                            'points': len(frequencies)},
        root_node_id=root_node_id, precomputed_tree_edges=tree,
        precomputed_chord_edges=chords, hubs=hubs, line_resonators=line_resonators)
    missing = extractor.validate_scattering_assignments()
    if any(missing.get(k) for k in ('missing_nodes', 'missing_edges', 'missing_hubs')):
        print("Missing scattering parameters:", missing)
        return None
    # a conjugated injection node sees the sweep as negative frequencies
    root = next((n for n in nodes if n['node_id'] == root_node_id), None)
    f = -frequencies if root is not None and root.get('conj', False) else frequencies
    return GraphScatteringMatrix(extractor, f, tail_closure=tail_closure)
'''


def _join(entries: Sequence[str], open_: str, close: str) -> str:
    """Bracketed multi-line literal. An entry may carry a trailing comment
    after a TAB; the separating comma goes before it."""
    if not entries:
        return open_ + close
    rows = []
    for i, e in enumerate(entries):
        code, _, comment = e.partition("\t")
        sep = "," if i < len(entries) - 1 else ""
        rows.append(f"{code}{sep}  # {comment}" if comment else code + sep)
    return open_ + "\n" + "\n".join(rows) + "\n" + close


def _num(x) -> str:
    """Exact literal for a number (repr round-trips a float)."""
    if isinstance(x, float) and not math.isfinite(x):
        return f"float({str(x)!r})"
    return repr(x)


def _constraints(legacy: Dict[str, Any]):
    """(variable definitions, {(obj_type, obj_label, param): (var, value)})."""
    groups = ((legacy.get('scattering') or {}).get('constraint_groups')) or {}
    defs, lookup = [], {}
    for gid, g in groups.items():
        members = list(g.get('members') or [])
        if len(members) < 2:
            continue
        param = g['param_name']
        value = g['value'] / 1000 if param in _MILLI else g['value']
        var = f"{_VAR_PREFIX.get(param, param)}_group{gid}"
        shown = ", ".join(members[:5]) + (f", ... (+{len(members) - 5} more)"
                                         if len(members) > 5 else "")
        defs.append(f"{var} = {_num(value)}  # constrained {param}: {shown}")
        for m in members:
            lookup[(g['obj_type'], m, param)] = (var, value)
    return defs, lookup


def _port_labels(job) -> List[str]:
    """Channel labels in K-column order: monitored hubs, then legacy B_ext
    nodes (node walk order), conjugate-sector channels marked '*'."""
    conj = {n['node_id']: n.get('conj', False) for n in job['nodes']}
    out = []
    for h in job['hubs']:
        if h['monitored']:
            first = h['attachments'][0][0] if h['attachments'] else None
            out.append(h['label'] + ('*' if conj.get(first, False) else ''))
    for n in job['nodes']:
        b = n.get('B_ext')
        if b is not None and b > 0:
            out.append(n['label'] + ('*' if n.get('conj', False) else ''))
    return out


def _component_block(job, prefix: str, lookup) -> Tuple[str, Dict[str, str]]:
    """Literal data for one job. Returns (code, variable names)."""
    sa = job['scattering_assignments']
    v = {k: f"{prefix}{k}" for k in ('nodes', 'edges', 'assignments', 'hubs',
                                     'line_resonators')}
    node_ids = {n['node_id'] for n in job['nodes']}
    label = {n['node_id']: n['label'] + ('*' if n.get('conj', False) else '')
             for n in job['nodes']}

    def params(d, obj_type, obj_label):
        items = []
        for k, x in d.items():
            hit = lookup.get((obj_type, obj_label, k))
            if hit is not None and hit[1] == x:
                items.append(f"{k!r}: {hit[0]}")
            else:
                items.append(f"{k!r}: {_num(x) if isinstance(x, (int, float)) else repr(x)}")
        return "{" + ", ".join(items) + "}"

    nodes, edges, assigns = [], [], []
    for i, n in enumerate(job['nodes']):
        nodes.append("    " + repr(n))
        if id(n) in sa:
            assigns.append(f"    id({v['nodes']}[{i}]): "
                           f"{params(sa[id(n)], 'node', n['label'])}\tnode {n['label']}")
    for i, e in enumerate(job['edges']):
        edges.append("    " + repr(e))
        if id(e) not in sa:
            continue
        a, b = e['from_node_id'], e['to_node_id']
        if a in node_ids and b in node_ids:
            el = f"{label[a]}→{label[b]}"
            assigns.append(f"    id({v['edges']}[{i}]): {params(sa[id(e)], 'edge', el)}\t{el}")
        else:   # synthesized by the line macros: a tap onto a comb mode, or a pump bus
            assigns.append(f"    id({v['edges']}[{i}]): {params(sa[id(e)], None, None)}"
                           "\tline tap / pump bus")
    hubs = ["    " + repr(h) for h in job['hubs']]
    lines = ["    LineResonator(" + ", ".join(f"{k}={x!r}" for k, x in ln.items()) + ")"
             for ln in job['line_resonators']]
    code = "\n\n".join([
        f"{v['nodes']} = {_join(nodes, '[', ']')}",
        f"{v['edges']} = {_join(edges, '[', ']')}",
        "# parameters keyed by object id (the GraphExtractor API)\n"
        f"{v['assignments']} = {_join(assigns, '{', '}')}",
        "# ports / loss hubs: attachments are (node_id, weight_mag, weight_phase_deg),\n"
        "# weight in sqrt(rate) units\n"
        f"{v['hubs']} = {_join(hubs, '[', ']')}",
        "# transmission-line macros (expand to standing-wave combs at extraction)\n"
        f"{v['line_resonators']} = {_join(lines, '[', ']')}",
    ])
    return code, v


def _solve_call(v, job, target: str) -> str:
    return (f"{target} = solve({v['nodes']}, {v['edges']}, {v['assignments']}, "
            f"{v['hubs']}, {v['line_resonators']},\n"
            f"    root_node_id={job['root_node_id']!r}, frequencies=frequencies, "
            f"tail_closure={bool(job['tail_closure'])!r})")


def scattering_script(doc: Document, f_root_s=None, tail_closure=None,
                      traces: Optional[Iterable[Tuple[int, int, int]]] = None,
                      source: Optional[str] = None) -> Optional[str]:
    """The exported scattering script for `doc`.

    f_root_s, tail_closure: as compile_jobs (the GUI passes its spin-box grid
    and its tail-closure switch). traces: (component_index, j, k) to plot;
    None plots every S_jk of the first component. source: a path for the
    header comment. Returns None if nothing compiles.
    """
    jobs = compile_jobs(doc, f_root_s=f_root_s, tail_closure=tail_closure)
    if not jobs:
        return None
    f = np.asarray(jobs[0]['f_root_s'])
    defs, lookup = _constraints(to_legacy(doc))
    multi = len(jobs) > 1
    labels = {j['component_index']: _port_labels(j) for j in jobs}

    if traces is None:
        first = jobs[0]['component_index']
        n = len(labels[first])
        traces = [(first, j, k) for k in range(n) for j in range(n)]
    trace_lines = []
    for c, (ci, j, k) in enumerate(traces):
        lab = labels.get(ci, [])
        jl, kl = (lab[j], lab[k]) if j < len(lab) and k < len(lab) else (str(j), str(k))
        target = f"gsm_components[{ci}]" if multi else "gsm"
        tag = f"C{ci + 1}: " if multi else ""
        trace_lines.append(f"{target}.add_trace({j}, {k}, color={_COLORS[c % len(_COLORS)]!r}, "
                           f"linestyle='-', linewidth=2.0)  # {tag}S_{jl}{kl}")
    traces_code = "\n".join(trace_lines) or (
        "# No traces selected" + ("" if multi else
                                  " - use gsm.add_trace(j, k) to add S-parameters"))

    header = '"""\nScattering calculation code exported from Graphulator'
    if source:
        header += f"\nExported from: {source}"
    if multi:
        header += (f"\n\nNOTE: Graph contains {len(jobs)} disconnected components. "
                   "Each component has its own GSM with local port indices.")
    header += '\n"""'
    common = "\n".join([
        header, "",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "import seaborn as sns",
        "from graphulator.autograph import (GraphExtractor, GraphScatteringMatrix, "
        "LineResonator,",
        "                                   compute_hub_bridge_links)",
        "",
        "# Set plot style (uncomment/modify to customize appearance)",
        "# sns.set_theme(style='whitegrid', context='talk', font_scale=1.0)",
        _SOLVE,
        "# Frequency sweep",
        f"frequencies = np.linspace({_num(float(f[0]))}, {_num(float(f[-1]))}, {len(f)})",
    ])
    if defs:
        common += "\n\n# Constrained parameters (shared variables)\n" + "\n".join(defs)

    if not multi:
        (job,) = jobs
        data, v = _component_block(job, "", lookup)
        ports = ", ".join(f"{i}: {lab}" for i, lab in enumerate(labels[job['component_index']]))
        return f'''{common}

# Graph structure
{data}

# Compute S-matrix (port indices: {ports})
{_solve_call(v, job, "scattering_matrix")}
if scattering_matrix is not None:
    print(f"Computed S-matrix: {{scattering_matrix.num_ports}} ports, "
          f"{{len(frequencies)}} frequency points")

# ============================================================================
# Plot S-parameters
# ============================================================================
gsm = scattering_matrix
gsm.clear_traces()
{traces_code}

fig, ax = gsm.plot_SdB()
plt.show()
'''

    blocks = []
    for job in jobs:
        ci = job['component_index']
        data, v = _component_block(job, f"comp{ci}_", lookup)
        names = [n['label'] for n in job['nodes']] + [ln['label'] for ln in job['line_resonators']]
        blocks.append(f'''# ----------------------------------------------------------------------
# Component {ci}: {', '.join(names)}
# ----------------------------------------------------------------------
{data}

{_solve_call(v, job, f"gsm_components[{ci}]")}
if gsm_components[{ci}] is not None:
    print(f"Component {ci}: {{gsm_components[{ci}].num_ports}} port(s)")
''')
    nl = "\n"
    return f'''{common}

# ============================================================================
# One GSM per connected component
# ============================================================================
gsm_components = {{}}

{nl.join(blocks)}
# ============================================================================
# Add traces to each component's GSM
# ============================================================================
for gsm in gsm_components.values():
    if gsm is not None:
        gsm.clear_traces()

{traces_code}

# ============================================================================
# Plot all components together
# ============================================================================
fig, ax = plt.subplots(figsize=(10, 6))

for comp_idx, gsm in gsm_components.items():
    if gsm is not None and gsm._plot_traces:  # only components with traces
        gsm.plot_SdB(ax=ax)

ax.set_xlabel('Frequency')
ax.set_ylabel('|S| (dB)')
ax.legend()
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()
'''
