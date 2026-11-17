"""Layer 0 step 2: compile a Document into today's S-parameter jobs (no Qt).

``compile_jobs(doc)`` returns exactly the list of job dicts the GUI's Show-S
path builds (``Graphulator._compute_and_plot_sparams`` ->
``_build_sparams_job``) for the same file, and ``compute_job(job)`` is the
worker function that turns one into S (it was
``graphulator_para._compute_sparams_job``, which is now an alias of it). The
gate is tests/test_model_legacy_job.py: S is bit-identical to the live GUI
on every shipped example.

This is the LEGACY compiler. It goes through ``to_legacy(doc)`` and then
re-does, without Qt, what the GUI does to a loaded file before it builds a
job: the loader's normalization (``_deserialize_graph`` and
``_deserialize_ports_and_lines``), twin sync, the connected-component split,
the injection-root rule, and the macro synthesis of hubs, tap edges and pump
buses. It exists so that the GUI, code export and ``extract_from_pgraph``
can read the model before the M_super engine does, and it stays afterwards
as that engine's regression oracle. It deliberately reproduces the GUI's
quirks; they are listed in the design note (step 2), not fixed here.

The pure leaves the GUI and this compiler share (``line_payload``,
``port_hub_payload``, the pump anchor) live here, and
``para_features.explicit_ports`` imports them, so the two paths cannot drift
in the physics; what the gate tests is the translation around them.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np

from .. import graphulator_para_config as _cfg  # Qt-free; read live, as the GUI does
from ..autograph import (
    GraphExtractor,
    GraphScatteringMatrix,
    LineResonator,
    compute_hub_bridge_links,
    pgraph_port_to_hub,
)
from .migrate import legacy_node_id, to_legacy
from .quantize import spin as _spin
from .schema import Document

logger = logging.getLogger(__name__)

DEFAULT_END_COUPLING = {'x0': 'capacitive', 'xL': 'capacitive'}


# ---------------------------------------------------------------------------
# shared physics leaves (imported by para_features.explicit_ports)
# ---------------------------------------------------------------------------

#: Physics fields a pumped line's conjugate twin mirrors from its primary.
#: The twin is the SAME physical line seen in the idler sector, so it owns
#: only its layout (pos, angle, style) and its own end connections. (load
#: and sections are mirrored explicitly by sync_twin, as deep copies.)
TWIN_MIRRORED_KEYS = ('FSR', 'Ztx', 'f_max', 'Z0_port', 'alpha_uniform')


def line_extractor_id(line):
    """Stable extractor line_id for a GUI line resonator."""
    return f"line:{line['line_id']}"


def port_hub_payload(port):
    """GUI port -> extractor hub dict (kappa = sign * sqrt(rate)).

    Same conversion as autograph.pgraph_port_to_hub -- the GUI dict and the
    .pgraph 'ports' entry share one schema, so the programmatic
    extract_from_pgraph route and the live GUI route stay in lockstep.
    """
    return pgraph_port_to_hub(port)


def line_payload(line):
    """GUI line dict -> extractor LineResonator kwargs dict."""
    return {
        'line_id': line_extractor_id(line),
        'label': line['label'],
        'FSR': float(line['FSR']),
        'Ztx': float(line['Ztx']),
        'f_max': float(line['f_max']),
        # port_end is deprecated: termination comes from line['ends'], which
        # the GUI merges into the connected port's hub column. Emitting None
        # keeps LineResonator from generating an implicit hub of its own.
        'port_end': None,
        'Z0_port': float(line.get('Z0_port', 50.0)),
        'alpha_uniform': float(line.get('alpha_uniform', 0.0)),
        'conj': bool(line.get('conj', False)),
        # a shunt reactance at one end; None keeps the open-open comb
        'load': (dict(line['load']) if line.get('load') else None),
        # impedance steps along the line; None is the uniform line at Ztx
        'sections': ([dict(sec) for sec in line['sections']]
                     if line.get('sections') else None),
    }


def end_conns(line, end):
    """Connection list at one end (normalizes legacy None/dict forms)."""
    raw = (line.get('ends') or {}).get(end)
    if not raw:
        return []
    return [raw] if isinstance(raw, dict) else list(raw)


def clamp_mode(resonator, n, label, what):
    """Keep a stored reference mode inside the comb.

    f_max and the end load both move N, and neither edit can reach back
    into the taps and pumps that named a mode. Clamping keeps drawing and
    extraction working; the warning says why the number moved.
    """
    n = int(n)
    if 1 <= n <= resonator.N:
        return n
    logger.warning(
        "%s on line %r references mode %d, outside the %d-mode comb; "
        "clamping. Raise f_max or re-enter the reference mode.",
        what, label, n, resonator.N)
    return int(min(max(n, 1), resonator.N))


def pump_partners(resonator, n_ref, f_p):
    """Every resonant partner of mode n under ONE pump, by family.

    In the two-cluster picture with the twin in the frame f - f_p, its +m
    member sits at f_p - f_m and its -m member at f_p + f_m; in the frame
    f + f_p the -m member sits at f_m - f_p. So a single pump frequency
    satisfies THREE conditions, not one:

        f_n + f_m = f_p     amplification   (two-mode squeezing)
        f_m - f_n = f_p     up-conversion   (always has a target)
        f_n - f_m = f_p     down-conversion (only when f_n > f_p)

    Reporting only the first -- which the panel used to do -- hides the
    conversion processes that the same pump drives regardless, and those
    are exactly what is missed when someone means to amplify (sec. 7.6).

    Returns [{'family', 'm', 'f_m', 'target', 'detune', 'in_comb'}], the
    entries whose target frequency is positive, ordered as above.
    """
    f_n = resonator.mode_freq(n_ref)
    out = []
    for family, target in (('amplification', f_p - f_n),
                           ('up-conversion', f_n + f_p),
                           ('down-conversion', f_n - f_p)):
        if target <= 0:
            continue                    # no such pairing for this n and f_p
        m = resonator.nearest_harmonic(target)
        f_m = resonator.mode_freq(m)
        out.append({'family': family, 'm': int(m), 'f_m': float(f_m),
                    'target': float(target), 'detune': float(f_m - target),
                    'in_comb': abs(f_m - target) <= 1e-9})
    return out


def pump_anchor(line):
    """(n_ref, m_ref, family): the pair a line pump's rate is defined at.

    See ExplicitPortsMixin._pump_anchor (which calls this) for the physics.
    """
    pump = line['pump']
    resonator = LineResonator(**line_payload(line))
    n_ref = clamp_mode(resonator, pump.get('n_ref', 1), line['label'], 'pump')
    f_p = float(pump['f_p'])
    partners = pump_partners(resonator, n_ref, f_p)
    if not partners:                        # cannot happen: f_n + f_p > 0
        return (n_ref, resonator.nearest_harmonic(
            f_p - resonator.mode_freq(n_ref)), 'amplification')
    rank = {'amplification': 0, 'down-conversion': 1, 'up-conversion': 2}
    best = min(partners, key=lambda p: (abs(p['detune']), rank[p['family']]))
    return n_ref, int(best['m']), best['family']


def pump_frame_rule(family):
    """Twin drive frame for the anchored family: 'sector' (omega - f_p) or
    'sector+' (omega + f_p). See autograph's frame accumulation."""
    return 'sector+' if family == 'up-conversion' else 'sector'


# ---------------------------------------------------------------------------
# the loaded-file state the GUI builds jobs from
# ---------------------------------------------------------------------------

class _State:
    """Physics-relevant slice of a loaded Graphulator window."""

    def __init__(self):
        self.nodes: List[Dict[str, Any]] = []
        self.edges: List[Dict[str, Any]] = []
        self.ports: List[Dict[str, Any]] = []
        self.line_resonators: List[Dict[str, Any]] = []
        self.scattering_assignments: Dict[Any, Dict[str, Any]] = {}
        self.port_id_counter = 0

    # -- lookups the GUI mixin provides --------------------------------------
    def line_twin(self, line):
        pump = line.get('pump')
        if not pump:
            return None
        return next((l for l in self.line_resonators
                     if l['line_id'] == pump.get('twin_id')), None)

    def line_end_ports(self, line, end):
        out = []
        for conn in end_conns(line, end):
            if conn.get('kind') != 'port':
                continue
            port = next((p for p in self.ports
                         if p['port_id'] == conn['port_id']), None)
            if port is not None:
                out.append(port)
        return out

    def line_tap_node_ids(self, line):
        ids = set()
        for end in ('x0', 'xL'):
            ids.update(c['node_id'] for c in end_conns(line, end)
                       if c.get('kind') == 'node')
        return ids

    def port_adjacency_pairs(self):
        pairs = []
        for port in self.ports:
            ids = [a['node_id'] for a in port['attachments']]
            pairs.extend((ids[0], other) for other in ids[1:])
        return pairs

    def sync_twin(self, line):
        twin = self.line_twin(line)
        if twin is None:
            return
        for key in TWIN_MIRRORED_KEYS:
            twin[key] = line[key]
        twin['load'] = (dict(line['load']) if line.get('load') else None)
        twin['sections'] = ([dict(sec) for sec in line['sections']]
                            if line.get('sections') else None)
        twin['end_coupling'] = dict(line.get('end_coupling')
                                    or DEFAULT_END_COUPLING)
        twin['label'] = f"{line['label']}*"
        twin['conj'] = True
        twin['twin_of'] = line['line_id']

    def sync_all_twins(self):
        for line in self.line_resonators:
            if line.get('pump'):
                self.sync_twin(line)


def _load_state(data: Dict[str, Any]) -> _State:
    """Mirror _deserialize_graph + _deserialize_ports_and_lines (physics only)."""
    st = _State()
    sa = st.scattering_assignments

    node_ids = set()
    for nd in data.get('nodes', []):
        node = {'node_id': nd['node_id'], 'label': nd['label'],
                'pos': tuple(nd['pos']), 'conj': nd.get('conj', False)}
        st.nodes.append(node)
        node_ids.add(nd['node_id'])
        if 'freq' in nd or 'B_int' in nd or 'B_ext' in nd:
            entry = sa.setdefault(nd['node_id'], {})
            for k in ('freq', 'B_int', 'B_ext'):
                if k in nd:
                    entry[k] = nd[k]

    for ed in data.get('edges', []):
        if ed['from_node_id'] not in node_ids or ed['to_node_id'] not in node_ids:
            continue
        st.edges.append({'from_node_id': ed['from_node_id'],
                         'to_node_id': ed['to_node_id'],
                         'is_self_loop': ed['is_self_loop']})
        if 'f_p' in ed or 'rate' in ed or 'phase' in ed:
            entry = sa.setdefault((ed['from_node_id'], ed['to_node_id']), {})
            for k in ('f_p', 'rate', 'phase'):
                if k in ed:
                    entry[k] = ed[k]

    max_port_id = -1
    for pd in data.get('ports', []):
        atts = []
        for a in pd.get('attachments', []):
            if a['node_id'] not in node_ids:
                continue
            atts.append({'node_id': a['node_id'],
                         'rate': float(a.get('rate', 0.1)),
                         'sign': 1 if a.get('sign', 1) >= 0 else -1})
        port = {'port_id': int(pd['port_id']),
                'label': pd.get('label', f"P{pd['port_id']}"),
                'monitored': bool(pd.get('monitored', True)),
                'attachments': atts}
        st.ports.append(port)
        max_port_id = max(max_port_id, port['port_id'])
    st.port_id_counter = max_port_id + 1

    for ld in data.get('line_resonators', []):
        line = {
            'line_id': int(ld['line_id']),
            'label': ld.get('label', f"TL{ld['line_id']}"),
            'FSR': float(ld['FSR']),
            'Ztx': float(ld['Ztx']),
            'f_max': float(ld['f_max']),
            'ends': {e: [dict(c) for c in end_conns(ld, e)] for e in ('x0', 'xL')},
            'end_coupling': dict(ld.get('end_coupling') or DEFAULT_END_COUPLING),
            'port_end': ld.get('port_end'),
            'Z0_port': float(ld.get('Z0_port', 50.0)),
            'alpha_uniform': float(ld.get('alpha_uniform', 0.0)),
            'load': (dict(ld['load']) if ld.get('load') else None),
            'sections': ([dict(s) for s in ld['sections']]
                         if ld.get('sections') else None),
            'pump': (dict(ld['pump']) if ld.get('pump') else None),
            'conj': bool(ld.get('conj', False)),
            'twin_of': ld.get('twin_of'),
        }
        if line.get('sections'):
            try:
                canon = LineResonator(**line_payload(line)).sections
                line['sections'] = [dict(s) for s in canon]
            except ValueError as exc:
                logger.warning("Dropping invalid sections on line %r: %s",
                               line['label'], exc)
                line['sections'] = None
        st.line_resonators.append(line)

    known_line_ids = {l['line_id'] for l in st.line_resonators}
    for line in list(st.line_resonators):
        pump = line.get('pump')
        if pump and pump.get('twin_id') not in known_line_ids:
            line['pump'] = None
        if line.get('twin_of') is not None and line['twin_of'] not in known_line_ids:
            st.line_resonators.remove(line)
    st.sync_all_twins()

    known_port_ids = {p['port_id'] for p in st.ports}
    for line in st.line_resonators:
        ends = line['ends']
        for end in ('x0', 'xL'):
            ends[end] = [
                c for c in ends.get(end, [])
                if (c.get('kind') == 'node' and c.get('node_id') in node_ids)
                or (c.get('kind') != 'node' and c.get('port_id') in known_port_ids)]
        legacy_end = line.get('port_end')
        if legacy_end in ('x0', 'xL') and not any(ends.values()):
            # the loader materializes the implied port as a real glyph
            port = {'port_id': st.port_id_counter, 'label': line['label'],
                    'monitored': True, 'attachments': []}
            st.ports.append(port)
            st.port_id_counter += 1
            ends[legacy_end].append({'kind': 'port', 'port_id': port['port_id']})
    return st


# ---------------------------------------------------------------------------
# components, root, and the job (mirrors graphulator_para)
# ---------------------------------------------------------------------------

def _find_components(st: _State) -> List[Dict[str, Any]]:
    """Mirror Graphulator._find_connected_components."""
    if not st.nodes and not st.line_resonators:
        return []
    adjacency = {n['node_id']: set() for n in st.nodes}
    for e in st.edges:
        if e.get('is_self_loop', False):
            continue
        a, b = e['from_node_id'], e['to_node_id']
        if a in adjacency and b in adjacency:
            adjacency[a].add(b)
            adjacency[b].add(a)
    for a, b in st.port_adjacency_pairs():
        if a in adjacency and b in adjacency:
            adjacency[a].add(b)
            adjacency[b].add(a)

    visited, components = set(), []
    for node in st.nodes:
        nid = node['node_id']
        if nid in visited:
            continue
        comp, queue = set(), [nid]
        while queue:
            cur = queue.pop(0)
            if cur in visited:
                continue
            visited.add(cur)
            comp.add(cur)
            for nb in adjacency.get(cur, []):
                if nb not in visited:
                    queue.append(nb)
        components.append(comp)

    result = []
    for idx, ids in enumerate(components):
        comp_nodes = [n for n in st.nodes if n['node_id'] in ids]
        comp_edges = []
        for e in st.edges:
            if e.get('is_self_loop', False):
                if e['from_node_id'] in ids:
                    comp_edges.append(e)
            elif e['from_node_id'] in ids and e['to_node_id'] in ids:
                comp_edges.append(e)
        port_node_ids = set()
        for e in comp_edges:
            if e.get('is_self_loop', False):
                port_node_ids.add(e['from_node_id'])
        for port in st.ports:
            if not port.get('monitored', True):
                continue
            for att in port['attachments']:
                if att['node_id'] in ids:
                    port_node_ids.add(att['node_id'])
        result.append({'node_ids': ids, 'nodes': comp_nodes, 'edges': comp_edges,
                       'port_node_ids': port_node_ids, 'index': idx})
    result.sort(key=lambda c: len(c['node_ids']), reverse=True)

    for line in st.line_resonators:
        if line.get('twin_of') is not None:
            continue
        unit = [line]
        twin = st.line_twin(line)
        if twin is not None:
            unit.append(twin)
        partner = set()
        for member in unit:
            partner |= set(st.line_tap_node_ids(member))
            for end in ('x0', 'xL'):
                for port in st.line_end_ports(member, end):
                    partner.update(a['node_id'] for a in port['attachments'])
        host = None
        if partner:
            hosts = [c for c in result if c['node_ids'] & partner]
            if hosts:
                host = hosts[0]
                for other in hosts[1:]:
                    host['node_ids'] |= other['node_ids']
                    host['nodes'].extend(other['nodes'])
                    host['edges'].extend(other['edges'])
                    host['port_node_ids'] |= other['port_node_ids']
                    host.setdefault('line_ids', []).extend(other.get('line_ids', []))
                    result.remove(other)
        if host is not None:
            host.setdefault('line_ids', []).extend(m['line_id'] for m in unit)
        else:
            result.append({'node_ids': set(), 'nodes': [], 'edges': [],
                           'port_node_ids': set(), 'index': len(result),
                           'line_ids': [m['line_id'] for m in unit],
                           'line_label': line['label']})
    for idx, comp in enumerate(result):
        comp['index'] = idx
    return result


def _injection_node_id(st: _State, components, saved=None) -> Optional[int]:
    """What the injection combo holds once scattering mode is entered: the
    document's saved root (solve.root) if it is a port node of the shown
    component, else the first port node (node order) of it (decision Q1)."""
    current = components[0] if len(components) == 1 else None
    if current is not None:
        nodes, port_ids = current['nodes'], current['port_node_ids']
    else:
        nodes = st.nodes
        port_ids = {e['from_node_id'] for e in st.edges if e.get('is_self_loop', False)}
        for port in st.ports:
            if port.get('monitored', True):
                port_ids.update(a['node_id'] for a in port['attachments'])
    shown = [n['node_id'] for n in nodes if n['node_id'] in port_ids]
    if saved is not None and saved in shown:
        return saved
    return shown[0] if shown else None


def _default_root_node_id(st: _State):
    for port in st.ports:
        if port.get('monitored', True) and port['attachments']:
            return port['attachments'][0]['node_id']
    for node in st.nodes:
        nid = node['node_id']
        has_loop = any(e.get('is_self_loop', False) and e['from_node_id'] == nid
                       and e['to_node_id'] == nid for e in st.edges)
        if has_loop and nid in st.scattering_assignments:
            B_ext = st.scattering_assignments[nid].get('B_ext', None)
            if B_ext is not None and B_ext > 0:
                return nid
    return st.nodes[0]['node_id'] if st.nodes else 0


def _hubs_payload(st: _State, node_ids=None, line_ids=None):
    line_terms = {}
    for line in st.line_resonators:
        if line_ids is not None and line['line_id'] not in line_ids:
            continue
        for end in ('x0', 'xL'):
            for conn in end_conns(line, end):
                if conn.get('kind') == 'port':
                    line_terms.setdefault(conn['port_id'], []).append((line, end))
    payload = []
    for port in st.ports:
        atts = port['attachments']
        terms = line_terms.get(port['port_id'], [])
        if node_ids is not None and atts and not all(a['node_id'] in node_ids for a in atts):
            continue
        if not atts and not terms:
            continue
        hub = port_hub_payload(port)
        for line, end in terms:
            res = LineResonator(**line_payload(line))
            hub['attachments'].extend(res.end_couplings(end))
            hub.setdefault('tails', []).append({'line': res.to_dict(), 'end': end})
        payload.append(hub)
    return payload


def _lines_payload(st: _State, line_ids=None):
    st.sync_all_twins()
    return [line_payload(l) for l in st.line_resonators
            if line_ids is None or l['line_id'] in line_ids]


def _tap_edges(st: _State, line_ids=None, node_ids=None):
    out = []
    for line in st.line_resonators:
        if line_ids is not None and line['line_id'] not in line_ids:
            continue
        res = LineResonator(**line_payload(line))
        couplings = line.get('end_coupling') or DEFAULT_END_COUPLING
        for end in ('x0', 'xL'):
            coupling = couplings.get(end, 'capacitive')
            for conn in end_conns(line, end):
                if conn.get('kind') != 'node':
                    continue
                nid = conn['node_id']
                if node_ids is not None and nid not in node_ids:
                    continue
                rate = float(conn.get('rate', 0.0))
                flip = conn.get('sign', 1) < 0
                n_ref = clamp_mode(res, conn.get('n_ref', 1), line['label'], 'tap')
                for comb_id, weight, phase in res.tap_couplings(end, n_ref, coupling):
                    if flip:
                        phase = (phase + 180.0) % 360.0
                    out.append(({'from_node_id': nid, 'to_node_id': comb_id,
                                 'is_self_loop': False},
                                {'f_p': 0.0, 'rate': rate * weight, 'phase': phase}))
    return out


def _pump_edges(st: _State, line_ids=None):
    out = []
    for line in st.line_resonators:
        pump = line.get('pump')
        if not pump:
            continue
        if line_ids is not None and line['line_id'] not in line_ids:
            continue
        twin = st.line_twin(line)
        if twin is None:
            continue
        st.sync_twin(line)
        end = pump['end']
        n_ref, m_ref, family = pump_anchor(line)
        frame_rule = pump_frame_rule(family)
        coupling = pump.get('coupling', 'inductive')
        sig = LineResonator(**line_payload(line)).tap_couplings(end, n_ref, coupling)
        idl = LineResonator(**line_payload(twin)).tap_couplings(end, m_ref, coupling)
        rate = float(pump['rate'])
        phase0 = float(pump.get('phase', 0.0))
        f_p = float(pump['f_p'])
        for sid, wn, phn in sig:
            for tid, wm, phm in idl:
                out.append(({'from_node_id': sid, 'to_node_id': tid,
                             'is_self_loop': False},
                            {'f_p': f_p, 'rate': rate * wn * wm,
                             'phase': (phase0 + phn + phm) % 360.0,
                             'frame_rule': frame_rule}))
    return out


def _build_job(st: _State, component, injection_id, f_root_s, freq_start,
               freq_stop, freq_points, multi_component, tail_closure):
    """Mirror Graphulator._build_sparams_job."""
    if component is not None:
        nodes_to_use, edges_to_use = component['nodes'], component['edges']
        comp_name = f"Component {component['index']}"
        comp_node_ids = component['node_ids']
        comp_line_ids = component.get('line_ids', [])
    else:
        nodes_to_use, edges_to_use = st.nodes, st.edges
        comp_name = "full graph"
        comp_node_ids = comp_line_ids = None
    hubs = _hubs_payload(st, node_ids=comp_node_ids, line_ids=comp_line_ids)
    lines = _lines_payload(st, line_ids=comp_line_ids)
    if not nodes_to_use and not lines:
        return None

    sa = st.scattering_assignments
    root = None
    gui_node_ids = {n['node_id'] for n in nodes_to_use}
    if component is None:
        root = injection_id
    if root is None and hubs:
        root = next((a[0] for h in hubs if h['monitored']
                     for a in h['attachments'] if a[0] in gui_node_ids), None)
    if root is None and component is not None and component['port_node_ids']:
        root = next(iter(component['port_node_ids']))
    if root is None and component is None:
        root = _default_root_node_id(st)
    if root is None and nodes_to_use:
        root = nodes_to_use[0]['node_id']

    nodes = []
    for node in nodes_to_use:
        nd = {'node_id': node['node_id'], 'label': node['label'],
              'pos': node['pos'], 'conj': node.get('conj', False)}
        p = sa.get(node['node_id'])
        for k in ('freq', 'B_int', 'B_ext'):
            nd[k] = p.get(k, None) if p is not None else None
        nodes.append(nd)
    edges = []
    for edge in edges_to_use:
        ed = {'from_node_id': edge['from_node_id'], 'to_node_id': edge['to_node_id'],
              'is_self_loop': edge['is_self_loop']}
        p = sa.get((edge['from_node_id'], edge['to_node_id']))
        for k in ('f_p', 'rate', 'phase'):
            ed[k] = p.get(k, None) if p is not None else None
        edges.append(ed)

    job_sa = {}
    for nd in nodes:
        if nd['node_id'] in sa:
            job_sa[id(nd)] = dict(sa[nd['node_id']])
    for ed in edges:
        key = (ed['from_node_id'], ed['to_node_id'])
        if key in sa:
            job_sa[id(ed)] = dict(sa[key])
    for tap_edge, tap_params in (_tap_edges(st, line_ids=comp_line_ids, node_ids=comp_node_ids)
                                 + _pump_edges(st, line_ids=comp_line_ids)):
        edges.append(tap_edge)
        job_sa[id(tap_edge)] = tap_params

    return {
        'comp_name': comp_name,
        'component_index': component['index'] if component else 0,
        'component_label': (f"C{component['index'] + 1}"
                            if component and multi_component else ""),
        'root_node_id': root,
        'nodes': nodes,
        'edges': edges,
        'scattering_assignments': job_sa,
        'hubs': hubs,
        'line_resonators': lines,
        'f_root_s': f_root_s,
        'freq_start': freq_start,
        'freq_stop': freq_stop,
        'freq_points': freq_points,
        'tail_closure': bool(tail_closure),
    }


def sweep_grid(doc: Document) -> np.ndarray:
    """The document's sweep as the GUI grid (linspace over center +- span/2).

    The file stores whatever the spin boxes last held, often with stepping
    residue (center 5.9999999999999964); the GUI rounds that to the boxes'
    display decimals and clamps it to their ranges on load, and the plot is
    computed from the rounded value. So does this (quirk Q2 in the design
    note), so that a file reproduces the plot its author saw. Rounding is
    QDoubleSpinBox's (ties away from zero, model.quantize), not Python's.
    """
    sw = doc.sweep
    if sw is None:
        c, s, n = _cfg.FREQ_CENTER_DEFAULT, _cfg.FREQ_SPAN_DEFAULT, _cfg.FREQ_POINTS_DEFAULT
    else:   # start/stop files were converted to center/span at migration
        c, s, n = sw.center, sw.span, sw.points
    c = _spin(c, _cfg.FREQ_CENTER_MIN, _cfg.FREQ_CENTER_MAX, _cfg.FREQ_CENTER_DECIMALS)
    s = _spin(s, _cfg.FREQ_SPAN_MIN, _cfg.FREQ_SPAN_MAX, _cfg.FREQ_SPAN_DECIMALS)
    n = int(_spin(n, _cfg.FREQ_POINTS_MIN, _cfg.FREQ_POINTS_MAX, _cfg.FREQ_POINTS_DECIMALS))
    return np.linspace(c - s / 2, c + s / 2, n)


def compile_jobs(doc: Document, f_root_s=None, tail_closure=None) -> List[Dict[str, Any]]:
    """Document -> the job list the GUI's Show S builds for it.

    f_root_s: the sweep grid (default: the document's sweep, sweep_grid()).
    tail_closure: default doc.solve.tail_closure, else the app default (on).
    """
    if f_root_s is None:
        f_root_s = sweep_grid(doc)
    f_root_s = np.asarray(f_root_s)
    if tail_closure is None:
        tail_closure = True if doc.solve.tail_closure is None else doc.solve.tail_closure
    st = _load_state(to_legacy(doc))
    components = _find_components(st)
    injection = _injection_node_id(st, components, legacy_node_id(doc.solve.root))
    todo = components if len(components) > 1 else [None]
    start, stop, n = f_root_s[0], f_root_s[-1], len(f_root_s)
    jobs = []
    for comp in todo:
        job = _build_job(st, comp, injection, f_root_s, start, stop, n,
                         multi_component=len(todo) > 1, tail_closure=tail_closure)
        if job is not None:
            jobs.append(job)
    return jobs


# ---------------------------------------------------------------------------
# the worker (was graphulator_para._compute_sparams_job)
# ---------------------------------------------------------------------------

def compute_job(job):
    """Compute S-parameters for one self-contained component job.

    Pure computation over the plain data packaged by
    Graphulator._build_sparams_job (or compile_jobs) -- no GUI access, safe
    to run on a worker thread.

    Returns:
        dict with S-parameter results, or None if the component is invalid
        (e.g. missing parameter assignments).
    """
    comp_name = job['comp_name']
    nodes = job['nodes']
    edges = job['edges']
    root_node_id = job['root_node_id']
    f_root_s = job['f_root_s']
    hubs = job.get('hubs') or []
    line_resonators = job.get('line_resonators') or []

    extractor = GraphExtractor()

    if nodes and not line_resonators:
        # Compute spanning tree for this component. (With line macros in
        # the job the comb-mode ids exist only after the extractor's
        # expansion pre-pass -- tap edges reference them -- so the extractor
        # computes the tree itself over the expanded graph.)
        gui_nodes = [{'node_id': node['node_id']} for node in nodes]
        gui_edges = [
            {
                'from_node_id': edge['from_node_id'],
                'to_node_id': edge['to_node_id'],
                'is_self_loop': edge['is_self_loop']
            }
            for edge in edges
        ]

        # Zero-offset bridge links across shared hubs (see
        # autograph.compute_hub_bridge_links): the tree must reach
        # hub-bridged subgraphs so their pump-frame accumulation survives
        link_pairs = compute_hub_bridge_links(
            [n['node_id'] for n in nodes],
            [(e['from_node_id'], e['to_node_id'])
             for e in gui_edges if not e['is_self_loop']],
            [[a[0] for a in h['attachments']] for h in hubs])
        gui_edges = gui_edges + [
            {'from_node_id': a, 'to_node_id': b, 'is_self_loop': False}
            for a, b in link_pairs]

        tree_edges_nested, chord_edges_list, is_connected = extractor.compute_spanning_tree(
            gui_nodes, gui_edges, root_node_id
        )

        # Convert to list format for extractor
        tree_edges_list = []
        for branch in tree_edges_nested:
            for from_id, to_id in branch:
                tree_edges_list.append([from_id, to_id])
    else:
        # Line-macro-only job: no GUI nodes; the extractor's expansion
        # pre-pass supplies the comb nodes and its root rule picks the root
        tree_edges_list = None
        chord_edges_list = None
        root_node_id = None

    extractor.extract_graph_data(
        nodes=nodes,
        edges=edges,
        scattering_assignments=job['scattering_assignments'],
        frequency_settings={'start': job['freq_start'], 'stop': job['freq_stop'],
                            'points': job['freq_points']},
        root_node_id=root_node_id,
        precomputed_tree_edges=tree_edges_list,
        precomputed_chord_edges=chord_edges_list,
        hubs=hubs,
        line_resonators=line_resonators
    )

    # Validate all required parameters are assigned before computing
    missing = extractor.validate_scattering_assignments()
    missing_items = (missing.get('missing_nodes', [])
                     + missing.get('missing_edges', [])
                     + missing.get('missing_hubs', []))
    if missing_items:
        detail = "\n".join(f"  - {item}" for item in missing_items)
        logger.info(f"  {comp_name}: Missing scattering parameters:\n{detail}")
        return None

    # Check if injection node is conjugated
    root_node = next((n for n in nodes if n['node_id'] == root_node_id), None)
    f_calc = f_root_s
    if root_node and root_node.get('conj', False):
        f_calc = -f_root_s
        logger.info(f"  {comp_name}: Injection node is conjugated - using negative frequencies")

    # Compute S-matrix (the comb tail closure is on unless the job says
    # otherwise -- see autograph.GraphScatteringMatrix._build_tail_closure)
    scattering_calc = GraphScatteringMatrix(
        extractor, f_calc, tail_closure=job.get('tail_closure', True))

    logger.info(f"  {comp_name}: {scattering_calc.num_ports} ports computed")

    # Build enriched port_dict with labels for checkbox/plot code, keyed by
    # the channel refs in port_ids (hub_id for explicit hubs, node_id for
    # legacy auto-wrapped ports). Port label = hub label (legacy: node label).
    conj_by_node = {n['node_id']: n.get('conj', False) for n in nodes}
    enriched_port_dict = {}
    for hub, ref in zip(scattering_calc.port_hubs, scattering_calc.port_ids):
        if 'legacy_node_id' in hub:
            B_ext = hub['legacy_B_ext']
            conj = conj_by_node.get(hub['legacy_node_id'], False)
        else:
            B_ext = sum(mag ** 2 for _, mag, _ in hub['attachments'])
            # all attachments share one sector (Phase-1 gate)
            first = hub['attachments'][0][0] if hub['attachments'] else None
            conj = conj_by_node.get(first, False)
        enriched_port_dict[ref] = {'B_ext': B_ext, 'label': hub['label'],
                                   'conj': conj}

    return {
        'S': scattering_calc.S,
        'SdB': scattering_calc.SdB,
        'port_dict': enriched_port_dict,
        'drive_signals': scattering_calc.drive_signals,
        'port_ids': list(scattering_calc.port_ids),
        'component_index': job['component_index'],
        'component_label': job['component_label'],
    }
