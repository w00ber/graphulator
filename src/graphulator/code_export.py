"""Generated drawing code for a graph, in two shapes.

Both apps' "Export Python Code" lands here: :func:`build_code` walks a main
window's nodes, edges and glyphs and returns a runnable graph_primitives
script. The math that turns GUI multipliers into figure-space linewidths and
font sizes used to live in two near-identical copies, one per app, and they
had already drifted apart (one grew arrowhead options, the other did not).

Two shapes of the same drawing:

``verbose`` writes one call per object with every keyword spelled out. It is
the long-standing format and stays the default, because it is the shape you
read when you want to know exactly what one node is doing.

``compact`` factors the keywords that repeat into named style dicts and
leaves only the geometry in per-style lists::

    NODE_STYLES = {'red': dict(nodecolor=..., R=0.600, ...)}
    NODES = {'red': [('A_0', (0.000, 0.000), 3), ...]}
    for _style, _items in NODES.items():
        for _label, _xy, _node_id in _items:
            graph.addnode(label=_label, xy=_xy, node_id=_node_id,
                          **NODE_STYLES[_style])

That is the shape you edit: change one style dict and every object drawn in
it follows, or drop the lists and generate the geometry in a loop of your
own. A 15-node, 49-edge graph shrinks from ~700 lines to ~100.
"""

import logging
from dataclasses import dataclass, field

import matplotlib.colors as mcolors
import numpy as np

logger = logging.getLogger(__name__)

#: Longest source line the emitted style dicts wrap at.
WRAP = 79


# ---------------------------------------------------------------------------
# colors
# ---------------------------------------------------------------------------

def _same_color(a, b):
    """True when two color spellings name the same color."""
    try:
        return mcolors.to_rgba(a) == mcolors.to_rgba(b)
    except (ValueError, TypeError):
        return False


def palette_key(color, cfg):
    """The MYCOLORS key that names ``color``, or None.

    Compared as colors rather than as strings: the pickers hand back hex and
    the palette holds matplotlib color names, so 'indianred' has to match
    '#cd5c5c'. The GUI's own reverse lookups compared the spellings, which is
    why a picked color never found its key again.
    """
    for key, val in (getattr(cfg, 'MYCOLORS', {}) or {}).items():
        if _same_color(val, color):
            return key
    return None


def color_expr(color, color_key, cfg, fallback='indianred'):
    """``config.MYCOLORS['RED']`` when the key still names this color, else
    the literal color.

    The color pickers hand back hex ('#aab6a8') and only *try* to match it
    against the palette -- by string, so 'indianred' never matches
    '#cd5c5c'. ``color_key`` therefore routinely names a different color
    than ``color``, which is the one the canvas actually draws. Exporting
    the key regardless is what made a graph of hand-picked colors come out
    uniformly 'RED': the drawing was right on screen and monochrome in the
    generated script.
    """
    palette = getattr(cfg, 'MYCOLORS', {}) or {}
    named = palette.get(color_key)
    if color and named is not None and _same_color(named, color):
        return f"config.MYCOLORS['{color_key}']"
    if color:
        return repr(color)
    if named is not None:
        return f"config.MYCOLORS['{color_key}']"
    return repr(fallback)


# ---------------------------------------------------------------------------
# one generated call
# ---------------------------------------------------------------------------

@dataclass
class Call:
    """One ``graph.<func>(...)`` call, split by what its keywords mean.

    ``ident`` is what the object *is* -- its label, position and id -- and
    varies for every object. ``style`` is what it *looks like*; objects that
    share a style tuple are exactly the objects the compact shape groups.
    ``extra`` is per-object settings that are not geometry: labels, nudges,
    self-loop parameters.
    """

    func: str
    ident: list = field(default_factory=list)   # [(name, literal), ...]
    style: tuple = ()                           # hashable, groups look-alikes
    extra: list = field(default_factory=list)
    comment: str = ''        # emitted above the call in the verbose shape
    tag: str = ''            # short name, listed in the compact style comment
    hint: str = ''           # preferred compact style name
    inline: bool = False     # verbose shape keeps it on one line

    @property
    def args(self):
        return list(self.ident) + list(self.style) + list(self.extra)


#: func -> (styles dict name, items dict name, singular, plural)
COMPACT_BLOCKS = {
    'addnode': ('NODE_STYLES', 'NODES', 'node', 'nodes'),
    'addedge': ('EDGE_STYLES', 'EDGES', 'edge', 'edges'),
    'addport': ('PORT_STYLES', 'PORTS', 'port', 'ports'),
    'addtxline': ('TXLINE_STYLES', 'TXLINES', 'txline', 'txlines'),
    'addwire': ('WIRE_STYLES', 'WIRES', 'wire', 'wires'),
}


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

def _kwargs_src(args):
    return ", ".join(f"{k}={v}" for k, v in args)


def _dict_src(args):
    """``dict(a=1, b=2)`` -- the per-object override dict."""
    return "dict(" + _kwargs_src(args) + ")" if args else "{}"


def _wrapped(head, args, tail):
    """``head`` + comma-separated ``args`` + ``tail``, wrapped at WRAP."""
    lines = []
    pad = " " * len(head)
    cur = head
    for i, (k, v) in enumerate(args):
        piece = f"{k}={v}"
        if i < len(args) - 1:
            piece += ","
        if cur.strip() and len(cur) + 1 + len(piece) > WRAP:
            lines.append(cur.rstrip())
            cur = pad + piece
        else:
            cur = (cur + " " + piece) if cur.strip() and not cur.endswith("(") \
                else cur + piece
    lines.append(cur + tail)
    return lines


def render_verbose(calls):
    """One call per object: the long-standing export shape."""
    lines = []
    for call in calls:
        if call.comment:
            lines.append(f"# {call.comment}")
        if call.inline:
            lines.append(f"graph.{call.func}({_kwargs_src(call.args)})")
            continue
        head = f"graph.{call.func}({_kwargs_src(call.ident)},"
        lines.append(head)
        rest = list(call.style) + list(call.extra)
        pad = " " * 13
        for i, (k, v) in enumerate(rest):
            end = ")" if i == len(rest) - 1 else ","
            lines.append(f"{pad}{k}={v}{end}")
        if not rest:                      # nothing but identity
            lines[-1] = head[:-1] + ")"
        lines.append("")
    return lines


def _by_func(calls):
    """[(func, [calls])], in the order the funcs first appear."""
    out = []
    for call in calls:
        if out and out[-1][0] == call.func:
            out[-1][1].append(call)
        else:
            out.append((call.func, [call]))
    return out


def _style_groups(calls):
    """[(style, [calls])], first-seen order."""
    groups = []
    index = {}
    for call in calls:
        key = tuple(call.style)
        if key not in index:
            index[key] = len(groups)
            groups.append((key, []))
        groups[index[key]][1].append(call)
    return groups


def _style_names(groups, singular):
    """Name each style after what it is, and number only the collisions."""
    bases = []
    for _style, members in groups:
        hints = {c.hint for c in members if c.hint}
        bases.append(hints.pop() if len(hints) == 1 else singular)
    counts = {}
    for base in bases:
        counts[base] = counts.get(base, 0) + 1
    seen = {}
    names = []
    for base in bases:
        if counts[base] == 1:
            names.append(base)
        else:
            seen[base] = seen.get(base, 0) + 1
            names.append(f"{base}{seen[base]}")
    return names


def _tag_comment(members, plural):
    """``# 5 nodes: A_0, A_1, ...`` -- what is drawn in this style."""
    tags = [c.tag for c in members if c.tag]
    shown, room = [], 52
    for tag in tags:
        if room - len(tag) < 0:
            shown.append("...")
            break
        shown.append(tag)
        room -= len(tag) + 2
    what = plural if len(members) != 1 else plural[:-1]
    listed = ", ".join(shown)
    return f"# {len(members)} {what}" + (f": {listed}" if listed else "")


def render_compact(calls):
    """Style dicts plus geometry lists plus one loop, per kind of object."""
    lines = []
    for func, group in _by_func(calls):
        if func not in COMPACT_BLOCKS or len(group) < 2:
            lines += render_verbose(group)
            continue
        ident_keys = [k for k, _ in group[0].ident]
        if any([k for k, _ in c.ident] != ident_keys for c in group):
            # some objects addressed by label and some by id: no one loop
            # fits them, so this kind stays explicit
            lines += render_verbose(group)
            continue

        styles_var, items_var, singular, plural = COMPACT_BLOCKS[func]
        groups = _style_groups(group)
        names = _style_names(groups, singular)
        has_extra = any(c.extra for c in group)

        lines.append(f"# {plural.capitalize()} by style. Edit one entry here "
                     f"and every {singular} drawn in it follows.")
        lines.append(f"{styles_var} = {{")
        for name, (style, members) in zip(names, groups):
            lines.append("    " + _tag_comment(members, plural))
            lines += _wrapped(f"    '{name}': dict(", list(style), "),")
        lines.append("}")
        lines.append("")

        fields = ", ".join(ident_keys)
        if has_extra:
            fields += ", overrides"
            lines.append(f"# ({fields}) per style -- overrides is a dict of "
                         f"per-{singular} keywords")
        else:
            lines.append(f"# ({fields}) per style")
        lines.append(f"{items_var} = {{")
        for name, (_style, members) in zip(names, groups):
            lines.append(f"    '{name}': [")
            for call in members:
                vals = [v for _, v in call.ident]
                if has_extra:
                    vals.append(_dict_src(call.extra))
                lines.append(f"        ({', '.join(vals)}),")
            lines.append("    ],")
        lines.append("}")
        lines.append("")

        loop_vars = ", ".join("_" + k for k in ident_keys)
        if has_extra:
            loop_vars += ", _over"
        pieces = [f"{k}=_{k}," for k in ident_keys]
        pieces.append(f"**{styles_var}[_style]" + ("," if has_extra else ")"))
        if has_extra:
            pieces.append("**_over)")
        lines.append(f"for _style, _items in {items_var}.items():")
        lines.append(f"    for {loop_vars} in _items:")
        head = f"        graph.{func}("
        cur, pad = head, " " * len(head)
        for piece in pieces:
            if cur != head and len(cur) + 1 + len(piece) > WRAP:
                lines.append(cur.rstrip())
                cur = pad + piece
            else:
                cur += (" " if cur != head else "") + piece
        lines.append(cur)
        lines.append("")
    return lines


# ---------------------------------------------------------------------------
# scaling context
# ---------------------------------------------------------------------------

class Context:
    """Numbers derived once from the whole graph, needed by every call."""

    def __init__(self, win):
        cfg = getattr(win, 'APP_CONFIG', None)
        self.cfg = cfg
        self.win = win
        (self.x_min, self.x_max,
         self.y_min, self.y_max) = win._calculate_graph_extents()
        self.x_center = (self.x_min + self.x_max) / 2
        self.y_center = (self.y_min + self.y_max) / 2

        # the plot extent the generated script ends up with (10% padding)
        self.span = max(self.x_max - self.x_min,
                        self.y_max - self.y_min) * 1.1

        # *2: the extent runs from -x_extent to +x_extent
        self.points_per_data_unit = (12 * 72) / (self.span * 2)

        # linewidths are in points, so they have to shrink as the graph grows
        # to stay proportional to the circles
        self.lw_extent_scale = 15.0 / self.span
        self.rescale = win.export_rescale

        # Wires and edges address nodes by node_id, and GraphCircuit only
        # keeps the id we pass it. Emit ids whenever labels repeat, and
        # whenever glyphs are present -- a graph something was deleted from
        # has ids that are not 0..N-1, and would wire itself up wrong.
        labels = [n['label'] for n in win.nodes]
        self.use_ids = (len(set(labels)) != len(labels)
                        or bool(getattr(win, '_has_glyphs', False)))

        logger.debug("Graph extent span: %.3f, linewidth scale: %.3f",
                     self.span, self.lw_extent_scale)


# ---------------------------------------------------------------------------
# nodes
# ---------------------------------------------------------------------------

def _math(label):
    """A label the mathtext/LaTeX renderer will accept."""
    return label if label.startswith('$') else f'${label}$'


def node_calls(win, ctx):
    cfg = ctx.cfg
    rescale = ctx.rescale
    selfloops = {e['from_node_id']: e for e in win.edges if e['is_self_loop']}
    calls = []

    for i, node in enumerate(win.nodes):
        label = node['label']
        if not label or not label.strip():
            label = ' '            # empty labels break math parsing
        node_id = node['node_id']
        x, y = node['pos']
        radius = win.node_radius * node.get('node_size_mult', 1.0)
        label_size_mult = node.get('label_size_mult', 1.0) * 0.75
        conj = node.get('conj', False)

        ident = [('label', repr(label)),
                 ('xy', f"({x - ctx.x_center:.3f}, {y - ctx.y_center:.3f})")]
        if ctx.use_ids:
            ident.append(('node_id', str(node_id)))

        color_key = node.get('color_key')
        style = [('nodecolor', color_expr(node.get('color'), color_key, cfg)),
                 ('R', f"{radius:.3f}"),
                 ('fontscale',
                  f"{label_size_mult * rescale['NODELABELSCALE']:.3f}"),
                 ('conj', str(conj))]

        if node.get('outline_enabled', False):
            outline_color = node.get(
                'outline_color',
                getattr(cfg, 'DEFAULT_NODE_OUTLINE_COLOR', 'black'))
            style += [
                ('nodeoutlinecolor',
                 color_expr(outline_color, node.get('outline_color_key'), cfg,
                            fallback='black')),
                ('nodelw', f"{node.get('outline_width', 2.5):.1f}"),
                ('nodeoutlinealpha', f"{node.get('outline_alpha', 1.0):.2f}"),
            ]

        extra = []
        nudge = tuple(node.get('nodelabelnudge', (0.0, 0.0)))
        if abs(nudge[0]) > 0.001 or abs(nudge[1]) > 0.001:
            # the canvas nudges a node label 5% of its font size downward;
            # take that back out so the exported position matches the screen
            conj_scale = getattr(cfg, 'CONJ_LABEL_SCALE', 1.0) if conj else 1.0
            font_points = (radius * 2 * ctx.points_per_data_unit * 0.35
                           * label_size_mult * conj_scale)
            adjust = font_points * 0.05 / ctx.points_per_data_unit
            extra.append(('nodelabelnudge',
                          f"({nudge[0]:.3f}, {nudge[1] - adjust:.3f})"))

        loop = selfloops.get(node_id)
        if loop is None:
            style.append(('drawselfloop', 'False'))
        else:
            extra.append(('drawselfloop', 'True'))
            extra += _selfloop_args(loop, ctx)

        hint = (color_key.lower()
                if color_key and style[0][1].startswith('config.') else '')
        calls.append(Call('addnode', ident=ident, style=tuple(style),
                          extra=extra, tag=label.strip(), hint=hint,
                          comment=f"Node {i + 1}: "
                                  f"{label if label.strip() else '(blank)'}"))
    return calls


def _selfloop_args(loop, ctx):
    """Self-loop keywords, which ride along on the node that carries it."""
    rescale = ctx.rescale
    args = []
    label = loop.get('label1', '')
    if label:
        args.append(('selflooplabel', f"r'{_math(label)}'"))
        label_size_mult = loop.get('label_size_mult', 1.4)
        if abs(label_size_mult - 1.4) > 0.01:
            args.append(('selflooplabelscale',
                         f"{label_size_mult * rescale['SELFLOOP_LABELSCALE']:.3f}"))

    args.append(('selflooplw',
                 f"{2.5 * loop['linewidth_mult'] * rescale['SLLW'] * ctx.lw_extent_scale:.1f}"))

    angle = loop.get('selfloopangle', 0)
    if angle != 0:
        args.append(('selfloopangle', str(angle)))
    scale = loop.get('selfloopscale', 1.0)
    if abs(scale - 1.0) > 0.01:
        args.append(('selfloopscale', f"{scale * rescale['SLSC']:.3f}"))
    arrowlengthsc = loop.get('arrowlengthsc', 1.0)
    if abs(arrowlengthsc - 1.0) > 0.01:
        args.append(('arrowlengthsc', f"{arrowlengthsc:.3f}"))
    arrowstyle = loop.get('arrowstyle', 'open')
    if arrowstyle != 'open':
        args.append(('arrowstyle', repr(arrowstyle)))
    if loop.get('flip', False):
        args.append(('flipselfloop', 'True'))

    # the label nudge carries both the user's fine-tuning and the export
    # distance scale, which moves the label radially along the loop angle
    nudge = tuple(loop.get('selflooplabelnudge', (0.0, 0.0)))
    nudge_scale = rescale.get('SELFLOOP_LABELNUDGE_SCALE', 1.0)
    distance = rescale.get('EXPORT_SELFLOOP_LABEL_DISTANCE', 1.0)
    nx, ny = nudge[0] * nudge_scale, nudge[1] * nudge_scale
    if abs(distance - 1.0) > 0.001:
        radial = (distance - 1.0) * 0.5
        rad = angle * np.pi / 180
        nx += radial * np.cos(rad)
        ny += radial * np.sin(rad)
    if abs(nx) > 0.001 or abs(ny) > 0.001:
        args.append(('selflooplabelnudge', f"({nx:.3f}, {ny:.3f})"))

    bgcolor = loop.get('label_bgcolor', None)
    if bgcolor is not None:
        args.append(('selflooplabelbgcolor', repr(bgcolor)))
    return args


# ---------------------------------------------------------------------------
# edges
# ---------------------------------------------------------------------------

def edge_calls(win, ctx, compact=False):
    """Calls for every edge that is not a self-loop.

    ``compact`` drops the placeholder ``label=[None, None]`` and its rotation
    from unlabeled edges: in the grouped shape they would be noise on every
    row, and an edge with no label has nothing to rotate. The verbose shape
    keeps them, so an edge you want to label later is a one-word edit.
    """
    cfg = ctx.cfg
    rescale = ctx.rescale
    calls = []
    edges = [e for e in win.edges if not e['is_self_loop']]

    for i, edge in enumerate(edges):
        from_node, to_node = edge['from_node'], edge['to_node']
        style_name = edge['style']
        label_size_mult = edge['label_size_mult']
        label_offset_mult = edge.get('label_offset_mult', 1.0)

        # base values for figsize=12
        base_fontsize = getattr(cfg, 'EXPORT_EDGE_LABEL_BASE_FONTSIZE',
                                50 * 0.4)
        scaled_lw = 4 * edge['linewidth_mult'] * ctx.lw_extent_scale
        scaled_fontsize = base_fontsize * label_size_mult
        scaled_offset = 2.3 * label_offset_mult

        # graph_primitives multiplies the linewidth per style, so pre-multiply
        if style_name == 'single':
            scaled_lw *= 3.5 * 0.4
        elif style_name == 'double':
            scaled_lw *= 0.9 * 3.5
        elif style_name == 'loopy':
            scaled_lw *= 0.4

        if ctx.use_ids:
            ident = [('fromnode_id', str(edge['from_node_id'])),
                     ('tonode_id', str(edge['to_node_id']))]
        else:
            ident = [('fromnode', repr(from_node['label'])),
                     ('tonode', repr(to_node['label']))]

        loopkwargs = [f"'lw': {scaled_lw * rescale['EDGELWSCALE']:.1f}",
                      "'arrowlength': 0.4"]
        arrowstyle = edge.get('arrowstyle', 'open')
        arrowscale = edge.get('arrowscale', 1.0)
        if arrowstyle != 'open':
            loopkwargs.append(f"'arrowstyle': '{arrowstyle}'")
        if abs(arrowscale - 1.0) > 0.01:
            loopkwargs.append(f"'arrowscale': {arrowscale:.3f}")

        style = [
            ('labeloffset',
             f"{scaled_offset * rescale['EDGELABELOFFSET']:.1f}"),
            ('labelfontsize',
             f"{scaled_fontsize * rescale['EDGEFONTSCALE']:.0f}"),
            ('style', repr(style_name)),
            ('whichedges', repr(edge['direction'])),
            ('theta', str(edge.get('looptheta', 30))),
            ('loopkwargs', "{" + ", ".join(loopkwargs) + "}"),
        ]

        label1 = edge.get('label1', '')
        label2 = edge.get('label2', '')
        extra = []

        # the labels ride along the edge, so their rotation is geometry
        dx = to_node['pos'][0] - from_node['pos'][0]
        dy = to_node['pos'][1] - from_node['pos'][1]
        labeltheta = np.arctan2(dy, dx) * 180 / np.pi
        if edge.get('flip_labels', False):
            labeltheta += 180
        labeltheta += edge.get('label_rotation_offset', 0)

        if label1 or label2:
            l1 = f"r'{_math(label1)}'" if label1 else 'None'
            l2 = f"r'{_math(label2)}'" if label2 else 'None'
            extra.append(('label', f"[{l1}, {l2}]"))
            extra.append(('labeltheta', f"{labeltheta:.1f}"))

            bg1 = edge.get('label1_bgcolor', None)
            bg2 = edge.get('label2_bgcolor', None)
            if bg1 or bg2:
                extra.append(('labelbgcolor',
                              f"[{repr(bg1) if bg1 else 'None'}, "
                              f"{repr(bg2) if bg2 else 'None'}]"))
        elif not compact:
            # empty placeholders, so labeling this edge by hand later is one
            # word rather than two new keywords
            extra += [('label', '[None, None]'),
                      ('labeltheta', f"{labeltheta:.1f}")]

        calls.append(Call(
            'addedge', ident=ident, style=tuple(style), extra=extra,
            tag=f"{from_node['label']}→{to_node['label']}",
            hint=style_name,
            comment=f"Edge {i + 1}: {from_node['label']} → "
                    f"{to_node['label']}"))
    return calls


# ---------------------------------------------------------------------------
# the whole script
# ---------------------------------------------------------------------------

def build_code(win, compact=False, preserve_ylim=False):
    """The generated script for ``win``, or None when there is nothing to draw.

    ``compact`` groups look-alike objects under named style dicts;
    ``preserve_ylim`` pins the y limits to the window's current view.
    """
    if not win.nodes and not getattr(win, '_has_glyphs', False):
        return None

    ctx = Context(win)
    render = render_compact if compact else render_verbose

    lines = ["#!/usr/bin/env python", '"""',
             "Generated graph code using graph_primitives"]
    if compact:
        lines += ["",
                  "Objects are grouped by style: each entry in a *_STYLES",
                  "dict is one appearance, and the matching list holds the",
                  "geometry drawn in it. Edit a style to restyle every object",
                  "using it, or build the lists programmatically."]
    lines += ['"""', "",
              "import matplotlib.pyplot as plt",
              "import graphulator.graph_primitives as gp",
              "import graphulator.graphulator_config as config",
              "",
              "# Create graph circuit (allow duplicate labels)",
              "# Set use_latex=True for LaTeX rendering, False for MathText "
              "(default)",
              f"graph = gp.GraphCircuit(allow_duplicate_labels=True, "
              f"use_latex={'True' if win.use_latex else 'False'})",
              ""]

    if win.nodes:
        if not compact:
            lines.append("# Add nodes")
        lines += render(node_calls(win, ctx))

    edges = edge_calls(win, ctx, compact=compact)
    if edges:
        if not compact:
            lines.append("# Add edges")
        lines += render(edges)

    # ports, transmission lines and their wiring, drawn by the same
    # graph_primitives calls the canvas uses
    glyphs = (win._glyph_code_calls(ctx.x_center, ctx.y_center)
              if hasattr(win, '_glyph_code_calls') else [])
    if glyphs:
        lines += ["", "# Ports, transmission lines and their wiring"]
        lines += render(glyphs)

    while lines and not lines[-1]:
        lines.pop()
    lines += ["",
              "# Draw the graph",
              "# overfrac adds padding around the graph to ensure all "
              "elements are visible",
              "# Increase overfrac if labels or self-loops are cut off",
              "graph.draw(figsize=12, overfrac=0.2)",
              ""]

    if preserve_ylim:
        # graph.draw() auto-centers on the graph extent; if the user has
        # panned or zoomed away from that, keep what they are looking at
        ylim = win.canvas.ax.get_ylim()
        y_center = (ylim[0] + ylim[1]) / 2
        y_range = ylim[1] - ylim[0]
        if (abs(y_center) > 0.1
                or y_range < (ctx.y_max - ctx.y_min) * 0.8):
            lines += ["# Set explicit y-axis limits (preserving GUI view)",
                      f"plt.ylim({ylim[0]:.2f}, {ylim[1]:.2f})", ""]

    lines += ["plt.axis('off')", "plt.title('')  # Remove title",
              "plt.show()"]
    return "\n".join(lines)
