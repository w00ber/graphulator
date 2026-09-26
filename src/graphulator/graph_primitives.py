'''
GRAPH PRIMITIVES LIBRARY
FEB2020, AUG2021
JAA

Library for drawing graphs. Build up the primitives (loops, arrows, bubbles).

-------------------------------------------------------------------------------
REVISION NOTES
-------------------------------------------------------------------------------
The original library -- the node/self-loop/edge vocabulary, the bezier
`drawloop`/`looparrow`/`selfloop` machinery, `plotnode`, `edge`, `prettynode`
and the `GraphCircuit` container -- was written by J. Aumentado (JAA) in
Feb 2020 and Aug 2021 and is his work.

Everything dated below is a joint revision: JAA specifying the behaviour and
the diagrammatic conventions, Claude (Anthropic) doing the refactoring and
implementation under review. Dates are the dates of the change, not of
release.

  2026-04-21  Packaged for public release as part of `graphulator` 0.9.0.
              `GraphCircuit` gained node_id support so graphs may carry
              duplicate node labels (`allow_duplicate_labels`), with
              `addedge(fromnode_id=, tonode_id=)` and an ambiguity error
              that names the colliding ids.
  2026-06-30  Label sizes became resolution-independent: every text size is
              derived from the live points-per-data-unit of the axes, so
              node/self-loop/edge labels keep their proportions at any
              figure size or axis extent, and the `fontscale`-family
              arguments became pure multipliers.
  2026-07-02  Each edge curve and its arrowhead are emitted as ONE compound
              matplotlib Path in a single PathPatch, so an SVG export keeps
              them together as a single editable group. Added the `filled`
              and `stealth` arrowhead styles alongside the original `open`
              two-stroke head, with a per-edge `arrowscale`.
  2026-07-03  Restored flush (butt) endcaps on the `single`/`double` edge
              styles, which the compound-path rewrite had rounded.
  2026-09-22  Added the schematic glyph vocabulary shared with the GUI apps:
              `port` (home-plate pentagon + lead), `txline` (slender
              cylinder with a closed cap, an open mouth and end stubs), and
              `wire` -- the cubic-bezier routing that leaves a port
              colinear with its lead and lands on its target along the
              target's own normal. `GraphCircuit` gained `addport`,
              `addtxline` and `addwire`, port auto-orientation, and
              extent bookkeeping so the new glyphs are never clipped.
              Factored the bold sans-serif math label formatting out of
              `plotnode` into `mathboldlabel`, which the new glyphs share.
-------------------------------------------------------------------------------
'''
import logging
import os
import re
import warnings

import matplotlib.lines as mlines
import matplotlib.patches as mpatches
import matplotlib.path as mpath
import matplotlib.pyplot as plt
import matplotlib.transforms as mtransforms
from matplotlib import rcParams
from numpy import abs, angle, arctan2, asarray, cos, diff, linspace, pi, real, sin, sqrt

logger = logging.getLogger(__name__)

#------------------------------------------------------------------------------
ORIGSFFONTLIST = rcParams['font.sans-serif']

#------------------------------------------------------------------------------
# Use MathText instead of LaTeX for much faster rendering
# STIX fonts provide a similar appearance to LaTeX
plt.rc('text', usetex=False)
rcParams['mathtext.fontset'] = 'stix'
rcParams['font.family'] = 'STIXGeneral'

# Old LaTeX rendering (very slow):
# plt.rc('text',usetex=True)
# rcParams['text.latex.preamble'] = '\\usepackage{{amsmath}}\n\\DeclareMathAlphabet{\\mathbfsf}{\\encodingdefault}{\\sfdefault}{bx}{n}'


#------------------------------------------------------------------------------
# TEXT ------------------------------------------------------------------------
#------------------------------------------------------------------------------

def mathboldlabel(text, use_latex=False):
    """Format `text` as bold sans-serif math, honoring `_`/`^` groups.

    Returned WITHOUT the enclosing ``$``, so callers can append decorations
    (the conjugation star, say) before entering math mode.

    MathText has no sans-serif bold alias, so each run is wrapped in
    ``\\mathbf{\\mathsf{...}}``; under LaTeX the `sfmath` package already
    makes the math font sans-serif, so ``\\mathbf{...}`` is enough. Sub- and
    superscript groups are wrapped individually, otherwise the font command
    swallows the script operator and the whole label renders at one size.
    """
    if use_latex:
        def apply_font(t):
            return r'\mathbf{' + t + '}'
    else:
        def apply_font(t):
            return r'\mathbf{\mathsf{' + t + '}}'

    parts = re.split(r'([_^])', str(text))
    out = []
    i = 0
    while i < len(parts):
        if parts[i] in ('_', '^'):
            out.append(parts[i])
            i += 1
            if i < len(parts):
                content = parts[i]
                if content.startswith('{') and content.endswith('}'):
                    out.append('{' + apply_font(content[1:-1]) + '}')
                else:
                    out.append(apply_font(content))
                i += 1
        elif parts[i]:
            out.append(apply_font(parts[i]))
            i += 1
        else:
            i += 1
    return ''.join(out)


#------------------------------------------------------------------------------
# PRIMITIVES ------------------------------------------------------------------
#------------------------------------------------------------------------------

def drawloop(ax=None,v=[[4,0],[6,0.0]],R=[4,4],theta=[120,60],lw=2,color='black',alpha=1.0,debug=False):

    '''
    This draws a loopy arrow.

    v:          vector of start/end points
    R:          length of bezier vectors
    theta:      bezier angles
    lw:         linewidth
    alpha:      transparency (0.0 to 1.0)

    RETURNS:
    vend:      end point of the arrow
    theta:     angle of the arrow
    '''
    # dx=0.05
    # v = [[0.5-dx,0],[.5+dx,0.1]]
    # R = [0.4,0.4] # bezier vector lengths
    # theta = [90+30,90-30] # in degrees

    bz = [[vv[0]+RR/2*cos(pi*tht/180),vv[1]+RR/2*sin(pi*tht/180)] for vv,RR,tht in zip(v,R,theta)]

    if not ax:
        fig, ax = plt.subplots()

    Path = mpath.Path
    pp1 = mpatches.PathPatch(
        Path([v[0], bz[0], bz[1], v[1]],
             [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4]),
        fc="none", transform=ax.transData,lw=lw,color=color,alpha=alpha)

    

    ax.add_patch(pp1)       
    
    # plt.axis('square')
    
    

    if debug:
        [plt.plot([vv[0],bbz[0]],[vv[1],bbz[1]],'-',lw=1,color='red') for vv,bbz in zip(v,bz)]
        [plt.plot(vv[0],vv[1],'ro') for vv in v]
        # plt.grid(True)
        ax.grid(True)

    
    # return the end point and the bezier theta so we can plant an arrow on it.
    vend = v[1]
    theta = 180-theta[1]
    return vend,theta



def arrowhead(ax=None,v=[0,0],theta=0,openang=90,lw=2,length=4,color='k',alpha=1.0,debug=False):
    '''
    Draw just the pointy end at point v [x,y list], along angle theta [degrees], with opening angle openang [degrees],
        linewidth lw, and length (projection cosine along direction).
    '''
    if ax is None:
        ax = plt.gca()

    v1 = v

    theta0 = theta+openang/2
    theta2 = theta-openang/2
    L = length/cos(openang/2*pi/180)
#     L = length
    v0 = asarray(v1)+[-L*cos(theta0*pi/180),L*sin(theta0*pi/180)]
    v2 = asarray(v1)+[-L*cos(theta2*pi/180),L*sin(theta2*pi/180)]

    varr = [v0,v1,v2]
    xarr = [vv[0] for vv in varr]
    yarr = [vv[1] for vv in varr]

    ax.plot(xarr,yarr,lw=lw,color=color,alpha=alpha)
    if debug is True:
        plt.grid('on')
        plt.axis('square')
        # plt.xlim([-10,10])
        # plt.ylim([-10,10])

# def node(R=2,lw=2,color='lightsalmon',linecolor='black',linetype='-',
#          label='$\mathsf{A}$',labelcolor='white'):
#     '''
#     Draw a standard node.
#     '''




#- UTILITIES -------------------------------------------------------------------------------------------
def angled(v):
    '''
    Return the angle of a vector v in degrees.
    '''
    vv = (v[1][0]-v[0][0]) + 1j*(v[1][1]-v[0][1])
    return real(angle(vv))*180/pi

#- LESS PRIMITIVE --------------------------------------------------------------------------------------
def _arrowhead_pts(tip, theta, openang, length):
    '''
    Barb points of an arrowhead at `tip` along angle `theta` (degrees).

    Exactly the legacy arrowhead() convention: barbs at
    tip + (-L*cos(theta±openang/2), +L*sin(theta±openang/2)) with
    L = length/cos(openang/2), so `length` is the projection along the
    arrow direction.
    '''
    L = length / cos(openang / 2 * pi / 180)
    th0 = theta + openang / 2
    th2 = theta - openang / 2
    v0 = (tip[0] - L * cos(th0 * pi / 180), tip[1] + L * sin(th0 * pi / 180))
    v2 = (tip[0] - L * cos(th2 * pi / 180), tip[1] + L * sin(th2 * pi / 180))
    return v0, v2


def looparrow(ax=None,
              vstartend=[[-1,0],[0,1]],
              R=[2,2],
              theta=[90+34,90-34],
              lw=3.0,
              arrowlength=0.4, # define as None to remove the arrow
              arrowthetatweak=0, # tweak the angle of the arrow. Useful with low loopiness.
              color='black',
              alpha=1.0,
              arrowstyle='open',   # 'open' | 'filled' | 'stealth'
              arrowscale=1.0,      # relative arrowhead scaling
              arrowopenang=60.0,   # arrowhead opening angle (degrees)
              gid=None,            # SVG group id for the whole edge
              capstyle='round',    # 'round' for arrowhead strokes; 'butt' for flush line ends
              debug=False):
    '''
    Draw the whole loopy arrow: curve plus arrowhead as ONE compound
    Path in a single PathPatch, so vector exports (SVG) keep each edge
    and its arrowhead together as one group.

    Returns the PathPatch.
    '''
    v = vstartend
    bz = [[vv[0] + RR / 2 * cos(pi * tht / 180), vv[1] + RR / 2 * sin(pi * tht / 180)]
          for vv, RR, tht in zip(v, R, theta)]

    Path = mpath.Path
    verts = [v[0], bz[0], bz[1], v[1]]
    codes = [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4]

    filled = bool(arrowlength) and arrowstyle in ('filled', 'stealth')
    if filled:
        # Retrace the Bezier backward so the open curve subpath has zero
        # net winding: matplotlib implicitly closes open subpaths when
        # filling, which would otherwise fill the lens between the curve
        # and its chord. Forward+reverse cancels under both nonzero and
        # even-odd fill rules, and the stroke still renders in one paint
        # op so alpha < 1 does not double-composite.
        verts += [bz[1], bz[0], v[0]]
        codes += [Path.CURVE4] * 3

    if arrowlength:
        # drawloop's end tangent convention: 180 - theta[1]
        th = (180 - theta[1]) + arrowthetatweak
        length = arrowlength * arrowscale
        tip = tuple(v[1])
        v0, v2 = _arrowhead_pts(tip, th, arrowopenang, length)
        if arrowstyle == 'filled':
            # Closed triangle
            verts += [v0, tip, v2, v0]
            codes += [Path.MOVETO, Path.LINETO, Path.LINETO, Path.CLOSEPOLY]
        elif arrowstyle == 'stealth':
            # Swept-back head: concave quad (back point closer to the tip
            # than the barb depth)
            back = 0.45 * length
            vb = (tip[0] - back * cos(th * pi / 180), tip[1] + back * sin(th * pi / 180))
            verts += [tip, v0, vb, v2, tip]
            codes += [Path.MOVETO, Path.LINETO, Path.LINETO, Path.LINETO, Path.CLOSEPOLY]
        else:
            # 'open': the legacy stroked V
            verts += [v0, tip, v2]
            codes += [Path.MOVETO, Path.LINETO, Path.LINETO]

    pp = mpatches.PathPatch(mpath.Path(verts, codes),
                            facecolor=(color if filled else 'none'),
                            edgecolor=color, lw=lw, alpha=alpha,
                            capstyle=capstyle, joinstyle='miter')
    if gid:
        pp.set_gid(gid)

    if ax is None:
        _, ax = plt.subplots()
    ax.add_patch(pp)

    if debug:
        [plt.plot([vv[0], bbz[0]], [vv[1], bbz[1]], '-', lw=1, color='red')
         for vv, bbz in zip(v, bz)]
        [plt.plot(vv[0], vv[1], 'ro') for vv in v]
        ax.grid(True)

    return pp

def selfloop(ax=None,
             baseangle=90,
             dtheta=34,
             nodecent=[0,0],
             R=1,
             loopR=24,
             arrowlength=1.5,
             color='black',
             lw=3,
             flip=False,
             alpha=1.0,
             arrowstyle='open',
             arrowscale=1.0,
             arrowopenang=60.0,
             gid=None,
             debug=False):
    ''''
    Draw self-loop.
    '''
    # baseangle=90
    # dtheta = 34
    # vcent = [0,0]


    R2 = [R,R]
    theta = [baseangle+dtheta,baseangle-dtheta]
    v = [[RR*cos(th*pi/180)+nodecent[0],RR*sin(th*pi/180)+nodecent[1]] for RR,th in zip(R2,theta)]

    if flip:
        theta = theta[::-1]
        v = v[::-1]

    return looparrow(ax=ax,
              vstartend=v,
              theta=theta,
              arrowlength=arrowlength,
              lw=lw,
              R=[loopR,loopR],
              color=color,
              alpha=alpha,
              arrowstyle=arrowstyle,
              arrowscale=arrowscale,
              arrowopenang=arrowopenang,
              gid=gid,
              debug=debug)


def plotnode(ax = None,
            R = 2,
            selfloopangle = 0,
            nodecent = [0,0],
            nodecolor = 'cornflowerblue',
            nodeoutlinecolor = 'black',
            nodealpha=None,
            nodeoutlinealpha=1.0,
            nodelw = 2.5,
            nodelabel = 'A',
            nodelabelcolor = 'white',
            nodelabelbgcolor = None,  # Background color for node label (None = no background)
            # nodelabelsize = 28,
            nodelabelnudge = (0,0),
            conj = False,
            selfloopscale = 1.,
            selfloopcolor = 'black',
            selflooplabel =r'$\Delta_A$',
            selflooplabelscale = 1.0,
            selflooplabelbgcolor = None,  # Background color for self-loop label (None = no background)
            selflooplw = 2.5,
            arrowlengthsc = 1,
            arrowstyle = 'open',  # 'open' | 'filled' | 'stealth' self-loop arrowhead
            drawlabels = True,
            drawselfloop = True,
            selflooplabelnudge = (0,0), # hacky way to nudge the labels into the center
            flipselfloop = False,
            fontscale = 1.0,  # multiplier for auto-scaled font size
            use_latex = False,  # if True, use LaTeX-specific formatting for conjugation
            debug = False):

    SELFLOOPLABELSCALE = selflooplabelscale
    # SELFLOOPLABELSCALE = 0.8
    LOOPYSCALE = 6*selfloopscale

    Ranchor = 3.2*R

    if nodealpha is None:
        nodealpha = 1

    if conj is True:
        nodealpha *= 0.5  # More transparent for conjugated nodes

    # to make selfloopangle positive if it's not already
    while selfloopangle<0:
        selfloopangle = selfloopangle + 360

    if not ax:
        fig, ax = plt.subplots()

    if nodealpha:
        circle = plt.Circle(nodecent, R,
                            facecolor=nodecolor,alpha=nodealpha)
        ax.add_patch(circle)

        if nodeoutlinecolor:
            ring = plt.Circle(nodecent,R,
                            facecolor='none',  # No fill, just outline
                            edgecolor=nodeoutlinecolor,
                            linewidth=nodelw,
                            alpha=nodeoutlinealpha)
            ax.add_patch(ring)
    else:
        # Create edge color with alpha if needed
        if nodeoutlinecolor and nodeoutlinealpha < 1.0:
            import matplotlib.colors as mcolors
            # Convert color to RGBA with specified alpha
            edge_rgba = mcolors.to_rgba(nodeoutlinecolor, alpha=nodeoutlinealpha)
            circle = plt.Circle(nodecent, R,
                                facecolor=nodecolor,
                                edgecolor=edge_rgba,
                                linewidth=nodelw)
        else:
            circle = plt.Circle(nodecent, R,
                                facecolor=nodecolor,
                                edgecolor=nodeoutlinecolor,
                                linewidth=nodelw)
        ax.add_patch(circle)

    selflooplabelanchor = [nodecent[0] + 1.05*Ranchor*cos(selfloopangle*pi/180), nodecent[1] + 1.05*Ranchor*sin(selfloopangle*pi/180)]

    # Calculate points_per_data_unit for font scaling only (not linewidths)
    if ax is not None:
        fig = ax.get_figure()
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        fig_width_inches = fig.get_figwidth()
        fig_height_inches = fig.get_figheight()
        fig_width_points = fig_width_inches * 72
        fig_height_points = fig_height_inches * 72
        data_width = xlim[1] - xlim[0]
        data_height = ylim[1] - ylim[0]
        points_per_data_unit_x = fig_width_points / data_width
        points_per_data_unit_y = fig_height_points / data_height
        points_per_data_unit = min(points_per_data_unit_x, points_per_data_unit_y)
    else:
        points_per_data_unit = 43.0

    if drawselfloop is True:
        # Scale self-loop linewidth proportionally to node radius only
        # Use R=2.0 as reference (typical default node radius)
        reference_R = 2.0
        scaled_selflooplw = selflooplw * (R / reference_R)

        selfloop(ax=ax,R=R*1.2,loopR=R*LOOPYSCALE,
                    nodecent=nodecent,baseangle=selfloopangle,dtheta=-34,
                    color=selfloopcolor,arrowlength=R/2*2.25/4*arrowlengthsc,
                    flip=flipselfloop,
                    arrowstyle=arrowstyle,
                    lw=scaled_selflooplw,debug=debug)
    
    

    if drawlabels is True:
        # Calculate dynamic points_per_data_unit to keep labels proportional to node circles
        # This is REQUIRED for correct scaling - fonts are in points, circles are in data units
        if ax is not None:
            fig = ax.get_figure()
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            fig_width_inches = fig.get_figwidth()
            fig_height_inches = fig.get_figheight()
            fig_width_points = fig_width_inches * 72
            fig_height_points = fig_height_inches * 72
            data_width = xlim[1] - xlim[0]
            data_height = ylim[1] - ylim[0]
            points_per_data_unit_x = fig_width_points / data_width
            points_per_data_unit_y = fig_height_points / data_height
            points_per_data_unit = min(points_per_data_unit_x, points_per_data_unit_y)
        else:
            points_per_data_unit = 43.0  # fallback

        conj_scale = 0.9 if conj else 1.0

        # Scale font size proportional to node radius AND current scale
        scaled_nodelabelsize = R * 2 * points_per_data_unit * 0.45 * fontscale * conj_scale

        # Self-loop label size: use reference radius so it doesn't scale with node size
        # This keeps self-loop labels consistent regardless of individual node sizing
        reference_R = 2.0  # typical default node radius
        scaled_selflooplabelsize = reference_R * 2 * points_per_data_unit * 0.45 * conj_scale

        if debug:
            logger.debug(f"FONT: R={R:.2f}, points_per_data_unit={points_per_data_unit:.2f}, scaled_nodelabelsize={scaled_nodelabelsize:.2f}")

        # Bold sans-serif math, with _/^ handling (see mathboldlabel)
        formatted_label = mathboldlabel(nodelabel, use_latex=use_latex)

        if conj is False:
            nodelabelbfsf = rf"${formatted_label}$"
        else:
            # Choose conjugation marker based on rendering mode
            if use_latex:
                # LaTeX with sfmath: mathbf gives bold sans-serif
                # Use \raisebox to lift the asterisk for better vertical alignment
                # Need to re-enter math mode inside \raisebox
                nodelabelbfsf = rf"${formatted_label}\raisebox{{0.15ex}}{{$\mathbf{{*}}$}}$"
            else:
                # MathText/STIX: use star symbol
                nodelabelbfsf = rf"${formatted_label}\!\star$"

        # turns out that the main thing you need to do is scale the plot limits to the figure size

        # No vertical offset needed for inline conjugation marker
        vertical_offset = 0.0

        # Small horizontal offset for LaTeX rendering to match MathText positioning
        # LaTeX text tends to render slightly left of MathText
        horizontal_offset = 0.02 * R if use_latex else 0.0

        offsetxy = [nodecent[0]+nodelabelnudge[0]+horizontal_offset, nodecent[1]+nodelabelnudge[1]+vertical_offset]

        # Create bbox dict for label background if specified
        bbox_props = None
        if nodelabelbgcolor is not None:
            bbox_props = dict(boxstyle='round,pad=0.1', facecolor=nodelabelbgcolor, edgecolor='none', alpha=1.0)

        ax.annotate(nodelabelbfsf,xy=offsetxy,
               ha='center',va='center',
               fontsize=scaled_nodelabelsize,color=nodelabelcolor,
               bbox=bbox_props)
        # DEBUG
        # ax.plot(offsetxy[0],offsetxy[1],'ko')

        if drawselfloop is True:
            if 135<selfloopangle%360<215:
                ha = 'right'
                va = 'center'
            elif (0<=selfloopangle%360<45)|(315<selfloopangle<=360):
                ha = 'left'
                va = 'center'
            elif (45<=selfloopangle%360<=135):
                ha = 'center'
                va = 'bottom'

            elif (215<=selfloopangle%360<=315):
                ha = 'center'
                va = 'top'

            offsetxy_label = [selflooplabelanchor[0]+selflooplabelnudge[0],selflooplabelanchor[1]+selflooplabelnudge[1]]
            # Use scaled_selflooplabelsize (based on reference radius, not actual node size)

            # Create bbox dict for self-loop label background if specified
            selfloop_bbox_props = None
            if selflooplabelbgcolor is not None:
                selfloop_bbox_props = dict(boxstyle='round,pad=0.1', facecolor=selflooplabelbgcolor, edgecolor='none', alpha=1.0)

            ax.annotate(selflooplabel,xy=offsetxy_label,
                    ha=ha,va=va,
                    size=scaled_selflooplabelsize*SELFLOOPLABELSCALE,color=selfloopcolor,
                    bbox=selfloop_bbox_props)

    # plt.axis('equal')

    # NEED TO ensure that the limits are scaled to match the rendered figure size
    # figwidth = plt.gcf().get_figwidth()
    # plt.ylim(-figwidth,figwidth)

    if debug is True:
        plt.plot(selflooplabelanchor[0],selflooplabelanchor[1],'r.')
    else:
        plt.axis('off')
        
    # node = {'nodecent':nodecent,'nodelabel':nodelabel,
    #         'selfloopangle':selfloopangle, 'selflooplabel':selflooplabel,
    #         'selflooplabelanchor':selflooplabelanchor}

    # return node


def edge(ax = None,
        nodexy = [(-4,-2),(4,4)],
        nodeR = [2,2],
        offsetradius_delta = 0.25,
        theta = 30,
        loopiness = None,
        label = [None,None], # string or None
        labeloffset = 2,
        labelfontsize = 30,
        labelcolor = 'black',
        labeltheta = 0,
        labelbgcolor = [None, None],  # Background colors for labels [label1, label2]
        style = 'loopy',  # 'loopy' or 'single' or 'double'
        whichedges = 'both',
        lw = 1.5,
        loopkwargs = {},
        reverse = False,
        gid = None,          # SVG group id base; direction suffixes are added
        debug = False,
        label_cache = None,  # optional LabelPathCache for fast cached-glyph labels
        usetex = False,      # forwarded to the cache (LaTeX vs mathtext)
        ):
    '''Draw a connecting edge between nodes.
    '''
    if reverse:
        nodexy = nodexy[::-1]
        nodeR = nodeR[::-1]

    # calc absolute angle of the vector connecting the two nodes
    theta12 = angled(nodexy)
    # print(f'{theta12=}') # DEBUG
    Rtot = [R+offsetradius_delta for R in nodeR]

    # Scale edge linewidth proportionally to average node radius only
    # Use R=2.0 as reference (typical default node radius)
    reference_R = 2.0
    avg_node_R = sum(nodeR) / len(nodeR)
    scaled_lw = lw * (avg_node_R / reference_R)

    if loopiness is None:
        # set default loopiness
        d = sqrt((nodexy[1][0]-nodexy[0][0])**2 + (nodexy[1][1]-nodexy[0][1])**2)
        loopiness = 4.5/12*d


    # loopkwargs['lw'] = lw
    loopkwargs['arrowthetatweak'] = -8



    if style == 'loopy':
        # Compute the start and end points based on the node radii and specified 
        # exit/entry theta angles (degrees)

        # angles of the exit and return arrows (wrt to the 1st and 2nd nodes)
        thetaoffsetanglesFORE = (theta12 + theta, theta12 + 180 - theta)
        thetaoffsetanglesBACK = (theta12 + 180 + theta, theta12 - theta)

        voffsetendptsFORE = [(n[0] + RR * cos(pi/180*th), n[1] + RR * sin(pi/180*th)) 
                            for n,RR,th in zip(nodexy,Rtot,thetaoffsetanglesFORE)]
        
        voffsetendptsBACK = [(n[0] + RR * cos(pi/180*th), n[1] + RR * sin(pi/180*th))
                            for n,RR,th in zip(nodexy[::-1],Rtot,thetaoffsetanglesBACK)]

        if whichedges in ['forward','fore']:
            looparrow(ax,
                    vstartend = voffsetendptsFORE,
                    R = [loopiness,loopiness],
                    theta = thetaoffsetanglesFORE,
                    gid = gid,
                    **loopkwargs
                    )
        elif whichedges in ['backward','back']:
            looparrow(ax,
                    vstartend = voffsetendptsBACK,
                    R = [loopiness,loopiness],
                    theta = thetaoffsetanglesBACK,
                    gid = gid,
                    **loopkwargs)

        elif whichedges in ['both','all']:
            looparrow(ax,
                    vstartend = voffsetendptsFORE,
                    R = [loopiness,loopiness],
                    theta = thetaoffsetanglesFORE,
                    gid = f'{gid}_fore' if gid else None,
                    **loopkwargs
                    )
            looparrow(ax,
                    vstartend = voffsetendptsBACK,
                    R = [loopiness,loopiness],
                    theta = thetaoffsetanglesBACK,
                    gid = f'{gid}_back' if gid else None,
                    **loopkwargs)
            
    elif style == 'single':
        # ax.set_title('single!')
        # single line style
        thetaoffsetangles = (theta12, theta12 + 180)
        voffsetendpts = [(n[0] + RR * cos(pi/180*th), n[1] + RR * sin(pi/180*th))
                            for n,RR,th in zip(nodexy,Rtot,thetaoffsetangles)]

        singleloopkwargs = loopkwargs.copy()
        singleloopkwargs.pop('arrowlength', None)  # Remove arrowlength if present

        if 'lw' not in singleloopkwargs:
            singleloopkwargs['lw'] = 3.5*scaled_lw

        looparrow(ax,
                    vstartend = voffsetendpts,
                    R = [0,0], # single line so no loopiness
                    theta = thetaoffsetangles,
                    arrowlength = None, # no arrow
                    gid = gid,
                    capstyle = 'butt', # flush line ends (legacy appearance)
                    **singleloopkwargs
                    )

    elif style == 'double':
        # ax.set_title('double!')
        # double line style
        thetaoffsetangles = (theta12, theta12 + 180)
        voffsetendpts = [(n[0] + RR * cos(pi/180*th), n[1] + RR * sin(pi/180*th))
                            for n,RR,th in zip(nodexy,Rtot,thetaoffsetangles)]

        # kludge to get double line by overlaying a skinnier white line in the middle
        doubleloopkwargs = loopkwargs.copy()
        doubleloopkwargs.pop('arrowlength', None)  # Remove arrowlength if present
        if 'lw' not in doubleloopkwargs:
            doubleloopkwargs['lw'] = 7*scaled_lw


        # draw the fat line ----------------------------------------------
        # Both passes need flush 'butt' ends: the white overlay runs slightly
        # past the fat stroke and cuts its ends open, so the pair reads as two
        # parallel rails. Round caps would bulge the fat stroke past the white.
        looparrow(ax,
                vstartend = voffsetendpts,
                R = [0,0], # single line so no loopiness
                theta = thetaoffsetangles,
                arrowlength = None, # no arrow
                gid = gid,
                capstyle = 'butt',
                **doubleloopkwargs
                )

        # draw the thin line ----------------------------------------------
        # modify the linewidth and change the color
        doubleloopkwargs['lw'] = doubleloopkwargs.pop('lw')*0.33
        doubleloopkwargs['color'] = 'white'

        voffsetendpts = [(n[0] + .98*RR * cos(pi/180*th), n[1] + .98*RR * sin(pi/180*th))
                            for n,RR,th in zip(nodexy,Rtot,thetaoffsetangles)]

        looparrow(ax,
                vstartend = voffsetendpts,
                R = [0,0], # single line so no loopiness
                theta = thetaoffsetangles,
                arrowlength = None, # no arrow
                gid = f'{gid}_inner' if gid else None,
                capstyle = 'butt',
                **doubleloopkwargs
                )

    if label:
        # Calculate dynamic points_per_data_unit to keep labels proportional to node circles
        if ax is not None:
            fig = ax.get_figure()
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            fig_width_inches = fig.get_figwidth()
            fig_height_inches = fig.get_figheight()
            fig_width_points = fig_width_inches * 72
            fig_height_points = fig_height_inches * 72
            data_width = xlim[1] - xlim[0]
            data_height = ylim[1] - ylim[0]
            points_per_data_unit_x = fig_width_points / data_width
            points_per_data_unit_y = fig_height_points / data_height
            points_per_data_unit = min(points_per_data_unit_x, points_per_data_unit_y)
        else:
            points_per_data_unit = 43.0  # fallback

        # Calculate base edge label size - use average node radius as reference
        # avg_node_R already calculated above
        # Base size proportional to node size, similar to node labels
        base_edge_label_size = avg_node_R * 2 * points_per_data_unit * 0.35

        # labelfontsize now works as a multiplier (like fontscale for nodes)
        scaled_labelfontsize = base_edge_label_size * labelfontsize / 30.0  # 30 was the old default

        # calculate the midpoint of the edge
        # voffsetmid = [(n[0] + RR * cos(pi/180*th), n[1] + RR * sin(pi/180*th))
        #                     for n,RR,th in zip(nodexy,Rtot,[theta12,theta12+180])]

        # v12 = (voffsetendpts[1][0] - voffsetendpts[0][0], voffsetendpts[1][1] - voffsetendpts[0][1])
        v12 = (nodexy[1][0] - nodexy[0][0], nodexy[1][1] - nodexy[0][1])
        vlength = sqrt(v12[0]**2 + v12[1]**2)
        th = arctan2(v12[1],v12[0])

        voffsetmid = (nodexy[0][0] + vlength/2 * cos(th), nodexy[0][1] + vlength/2 * sin(th))
        labelvecpos = (labeloffset * cos(th+pi/2),labeloffset * sin(th+pi/2))
        labelvecneg = (labeloffset * cos(th-pi/2),labeloffset * sin(th-pi/2))

        # forward label
        if label[0] is not None:
            labelvecpos = [voffsetmid[0] + labelvecpos[0],voffsetmid[1] + labelvecpos[1]]
            if label_cache is not None:
                label_cache.draw(ax, label[0], labelvecpos[0], labelvecpos[1],
                                 fontsize_points=scaled_labelfontsize,
                                 points_per_data_unit=points_per_data_unit,
                                 color=labelcolor, rotation=labeltheta,
                                 ha='center', va='center', usetex=usetex,
                                 zorder=20, bgcolor=labelbgcolor[0])
            else:
                bbox_props_0 = None
                if labelbgcolor[0] is not None:
                    bbox_props_0 = dict(boxstyle='round,pad=0.1', facecolor=labelbgcolor[0], edgecolor='none', alpha=1.0)
                ax.annotate(label[0],xy=labelvecpos,
                            ha='center',va='center',
                            fontsize=scaled_labelfontsize,color=labelcolor,rotation=labeltheta,bbox=bbox_props_0)
        if label[1] is not None:
            labelvecneg = [voffsetmid[0] + labelvecneg[0],voffsetmid[1] + labelvecneg[1]]
            if label_cache is not None:
                label_cache.draw(ax, label[1], labelvecneg[0], labelvecneg[1],
                                 fontsize_points=scaled_labelfontsize,
                                 points_per_data_unit=points_per_data_unit,
                                 color=labelcolor, rotation=labeltheta,
                                 ha='center', va='center', usetex=usetex,
                                 zorder=20, bgcolor=labelbgcolor[1])
            else:
                bbox_props_1 = None
                if labelbgcolor[1] is not None:
                    bbox_props_1 = dict(boxstyle='round,pad=0.1', facecolor=labelbgcolor[1], edgecolor='none', alpha=1.0)
                ax.annotate(label[1],xy=labelvecneg,
                            ha='center',va='center',
                            fontsize=scaled_labelfontsize,color=labelcolor,rotation=labeltheta,bbox=bbox_props_1)


    if debug:
        for nodecent,nR in zip(nodexy,nodeR):
            logger.debug(f'EDGE(): {nodecent=}, {nR=}')
            circle = plt.Circle(nodecent, nR, 
                                facecolor='darkred',alpha=0.6)    
            ax.add_patch(circle)
            # ax.axis('on')
    else:
        ax.axis('off')
    
    # ax.axis('square')
    

################################################################################
# GRAPH CIRCUIT CLASS ##########################################################
################################################################################
'''
GRAPH CIRCUIT CLASS

This class defines a graph circuit, defined by a set of node definitions and defined edges. 
These nodes are defined as a list of dictionaries, each with the following keys:
    
        nodecent:       [x,y] center of the node
        nodelabel:      label of the node      
        selfloopangle:  angle of the self-loop (with default to automatic if not specified)
        selflooplabel:  label of the self-loop (if any)
        
The edges are defined as a list of dictionaries, each with the following keys:

        startend:       [node1label,node2label] the nodes that are coupled by this edge. 
                        node1label and node2label are the string labels of the nodes given in the list.
        loopiness:      the loopiness of the edge


'''

#------------------------------------------------------------------------------
# SCHEMATIC GLYPHS -------------------------------------------------------------
#------------------------------------------------------------------------------
# The glyph vocabulary the GUI apps draw on the canvas, so an exported script
# reproduces what was on screen. All proportions are in units of the reference
# node radius R, and every glyph takes `length`/`height` multipliers -- the
# same two numbers the apps bind to the arrow keys.
#
# A PORT is a home-plate pentagon (square back, flat top and bottom,
# tapered nose) with a straight lead off the apex: it is where a wire enters
# or leaves the drawing. A TXLINE is a slender cylinder drawn in perspective --
# closed rounded cap on the left, open elliptical mouth on the right -- with a
# stub at each end. Wires leave a lead COLINEAR with it, so a fan of wires out
# of one port collimates through its lead before spreading.

PORT_BODY_W = 1.5      # pentagon straight-body width (x R)
PORT_BODY_H = 1.35     # pentagon height
PORT_APEX_W = 0.55     # tapered nose beyond the body
PORT_LW = 2.0          # default stroke

#: Where a wire anchors INSIDE the port body, as a fraction of the
#: half-width. A port has no lead of its own: its wires start at a point
#: buried in the filled body and run out through the apex, so the visible
#: wire begins exactly at the point of the pentagon. Anchoring at the apex
#: itself would leave the stroke's end cap sticking out past the vertex
#: with nothing to cover it -- the polygon has zero width there -- which
#: reads as a stray nub against the background.
PORT_WIRE_INSET = 1.0

TXLINE_BODY_W = 2.7          # cylinder half-length
TXLINE_BODY_H = 0.28         # cylinder half-height
TXLINE_LEAD_LEN = 0.55       # stub at each end
TXLINE_LW = 1.6

# Wires are BLACK by default: a wire is ordinary circuit ink, the same
# weight of statement as an edge, and a gray default quietly read as
# 'secondary'. Per-wire color / width / style overrides are in the panel.
WIRE_COLOR = 'black'
WIRE_LW = 1.4

GLYPH_LABEL_FILL = 0.90    # fraction of the body width a label may occupy
GLYPH_LABEL_ADVANCE = 0.60 # mean glyph advance / font size (bold sans)
GLYPH_LABEL_SCALE = 0.35   # matches the apps' PLOT_NODE_LABEL_FONT_SCALE


def rotatepoint(x, y, cx, cy, angle_deg):
    """Rotate (x, y) about (cx, cy) by `angle_deg` degrees CCW."""
    if not angle_deg:
        return (x, y)
    th = angle_deg * pi / 180.0
    dx, dy = x - cx, y - cy
    return (cx + dx * cos(th) - dy * sin(th),
            cy + dx * sin(th) + dy * cos(th))


def pointsperdataunit(ax):
    """Points per data unit of `ax` -- the factor that keeps text sized in
    points proportional to geometry sized in data units."""
    if ax is None:
        return 43.0  # same fallback plotnode uses
    fig = ax.get_figure()
    xlim, ylim = ax.get_xlim(), ax.get_ylim()
    if xlim[1] == xlim[0] or ylim[1] == ylim[0]:
        return 43.0
    return min(fig.get_figwidth() * 72 / (xlim[1] - xlim[0]),
               fig.get_figheight() * 72 / (ylim[1] - ylim[0]))


def readableangle(angle_deg):
    """`angle_deg` folded into the readable half-turn.

    A label rides its glyph so it stays inside the body, but text that ends
    up upside down is worse than text merely mirrored about the glyph axis --
    so past a quarter turn it flips, the usual schematic convention.
    """
    angle = float(angle_deg) % 360.0
    if 90.0 < angle <= 270.0:
        angle -= 180.0
    return angle


def _glyphlabel(ax, text, x, y, fontsize, color='black', rotation=0.0,
                use_latex=False, zorder=12):
    """Draw a glyph label in the node-label style (bold sans-serif math)."""
    if not text or not str(text).strip():
        return None
    body = mathboldlabel(text, use_latex=use_latex)
    return ax.text(x, y, rf"${body}$", ha='center', va='center',
                   rotation=rotation, rotation_mode='anchor',
                   fontsize=max(float(fontsize), 1.0), color=color,
                   zorder=zorder)


def portgeometry(xy=(0, 0), R=2.0, length=1.0, height=1.0):
    """(x, y, w, h, apex_x) of a port, UNROTATED.

    `w`/`h` are the full width/height of the straight part of the body and
    `apex_x` is the nose tip. A caller rotates these about (x, y) by the
    glyph angle.
    """
    x, y = xy
    w = PORT_BODY_W * R * length
    h = PORT_BODY_H * R * height
    apex_x = x + w / 2 + PORT_APEX_W * R * length
    return x, y, w, h, apex_x


def portapex(xy=(0, 0), R=2.0, angle=0.0, length=1.0, height=1.0):
    """((x, y), (tx, ty)): the point of the pentagon and the outward unit
    tangent there -- where a wire VISIBLY leaves the port."""
    x, y, _, _, apex_x = portgeometry(xy, R, length, height)
    th = angle * pi / 180.0
    return (rotatepoint(apex_x, y, x, y, angle), (cos(th), sin(th)))


def portwirestart(xy=(0, 0), R=2.0, angle=0.0, length=1.0, height=1.0):
    """((x, y), (tx, ty)): where a wire ANCHORS on a port.

    Buried inside the filled body, on the glyph axis, so the stroke's end
    cap is hidden under the polygon and the wire appears to start at the
    apex (see PORT_WIRE_INSET). The tangent is the glyph axis, so the wire
    runs straight out through the point of the pentagon.
    """
    x, y, w, _, _ = portgeometry(xy, R, length, height)
    th = angle * pi / 180.0
    anchor_x = x + PORT_WIRE_INSET * w / 2
    return (rotatepoint(anchor_x, y, x, y, angle), (cos(th), sin(th)))


def txlinegeometry(xy=(0, 0), R=2.0, length=1.0, height=1.0):
    """(x, y, w, h, rx) of a txline, UNROTATED: half-length, half-height and
    the end-cap ellipse half-depth (tied to h so the perspective survives
    stretching)."""
    x, y = xy
    w = TXLINE_BODY_W * R * length
    h = TXLINE_BODY_H * R * height
    return x, y, w, h, 0.5 * h


def txlineendpoints(xy=(0, 0), R=2.0, angle=0.0, length=1.0, height=1.0):
    """{'x0': ((x, y), (tx, ty)), 'xL': ...}: the two stub tips of a txline
    with the outward unit tangent at each."""
    x, y, w, h, rx = txlinegeometry(xy, R, length, height)
    th = angle * pi / 180.0
    axis = (cos(th), sin(th))
    x0 = x - w - rx - TXLINE_LEAD_LEN * R
    xL = x + w + rx + TXLINE_LEAD_LEN * R
    return {'x0': (rotatepoint(x0, y, x, y, angle), (-axis[0], -axis[1])),
            'xL': (rotatepoint(xL, y, x, y, angle), axis)}


def nodewireend(nodecent, R, toward):
    """((x, y), (tx, ty)) where a wire meets a node circle.

    The wire enters radially -- normal to the circle's tangent -- on the side
    facing `toward` (the emitting lead tip), so it never cuts the disc.
    """
    cx, cy = nodecent
    ux, uy = toward[0] - cx, toward[1] - cy
    norm = sqrt(ux * ux + uy * uy)
    if norm < 1e-12:
        ux, uy = 1.0, 0.0
    else:
        ux, uy = ux / norm, uy / norm
    return ((cx + R * ux, cy + R * uy), (-ux, -uy))


def wirepoints(p0, t0, p1, t1, R=2.0, samples=33):
    """Sampled cubic-bezier wire from p0 (leaving along unit tangent t0) to
    p1 (arriving travelling along unit tangent t1).

    The node-editor routing style: one smooth rounded curve, no rectilinear
    jogs, colinear with each port's lead at the ends. The control-point
    reach is a fraction of the span, clamped so very short wires do not loop
    and very long ones do not balloon.
    """
    p0 = asarray(p0, dtype=float)
    p1 = asarray(p1, dtype=float)
    t0 = asarray(t0, dtype=float)
    t1 = asarray(t1, dtype=float)
    d = float(sqrt(((p1 - p0) ** 2).sum()))
    c = min(max(0.45 * d, 0.9 * R), 4.0 * R)
    c0 = p0 + c * t0
    c1 = p1 - c * t1
    ts = linspace(0.0, 1.0, samples)[:, None]
    return ((1 - ts) ** 3 * p0 + 3 * (1 - ts) ** 2 * ts * c0
            + 3 * (1 - ts) * ts ** 2 * c1 + ts ** 3 * p1)


def wire(ax=None, p0=(0, 0), t0=(1, 0), p1=(1, 0), t1=(1, 0), R=2.0,
         color=WIRE_COLOR, lw=None, linestyle='-', alpha=0.9,
         label=None, labelscale=1.0, labelcolor=None, use_latex=False,
         zorder=4, samples=33):
    """Draw one routed wire; returns its sampled points."""
    if ax is None:
        _, ax = plt.subplots()
    lw = WIRE_LW if lw is None else lw
    pts = wirepoints(p0, t0, p1, t1, R=R, samples=samples)
    ax.add_line(mlines.Line2D(pts[:, 0], pts[:, 1], color=color, linewidth=lw,
                              linestyle=linestyle, alpha=alpha, zorder=zorder,
                              solid_capstyle='round'))
    if label:
        ppdu = pointsperdataunit(ax)
        mx, my = pts[len(pts) // 2]
        fontsize = 0.55 * R * ppdu * GLYPH_LABEL_SCALE * 1.45 * labelscale
        lc = labelcolor or color
        ax.text(mx, my, rf"${mathboldlabel(label, use_latex=use_latex)}$",
                ha='center', va='center', zorder=zorder + 1,
                fontsize=max(fontsize, 1.0), color=lc,
                bbox=dict(boxstyle='round,pad=0.18', fc='white', ec=lc,
                          lw=0.6))
    return pts


def port(ax=None, xy=(0, 0), angle=0.0, R=2.0, length=1.0, height=1.0,
             label='', color='black', fill='white', labelcolor='black',
             lw=None, hatch=None, linestyle='-', labelscale=1.0,
             labelnudge=(0, 0), drawlabel=True, use_latex=False,
             use_zorder=11, debug=False):
    """Draw a port glyph: a home-plate pentagon, and nothing else.

    The port has no lead of its own. A wire drawn to it anchors inside the
    body (`portwirestart`) and emerges through the point of the pentagon,
    so the line leaving a port is the CONNECTION's own stroke -- one line,
    one width -- rather than a glyph-owned stub that has to be kept in
    visual agreement with whatever attaches to it.

    Returns ``{'apex': (x, y), 'tangent': (tx, ty), 'angle': angle}``.
    """
    if ax is None:
        _, ax = plt.subplots()
    lw = PORT_LW if lw is None else lw
    x, y, w, h, apex_x = portgeometry(xy, R, length, height)

    def rot(px, py):
        return rotatepoint(px, py, x, y, angle)

    verts = [rot(x - w / 2, y - h / 2),
             rot(x + w / 2, y - h / 2),
             rot(apex_x, y),
             rot(x + w / 2, y + h / 2),
             rot(x - w / 2, y + h / 2)]
    ax.add_patch(mpatches.Polygon(
        verts, closed=True, facecolor=fill, edgecolor=color, linewidth=lw,
        linestyle=linestyle, joinstyle='miter', hatch=hatch,
        zorder=use_zorder))

    if drawlabel and label:
        ppdu = pointsperdataunit(ax)
        # sized off the body height, then capped so a long label shrinks to
        # fit the STRAIGHT part of the body rather than spilling over the nose
        fontsize = h * GLYPH_LABEL_SCALE * 1.45 * ppdu * labelscale
        n_chars = max(len(str(label)), 1)
        fontsize = min(fontsize, GLYPH_LABEL_FILL * w * ppdu
                       / (GLYPH_LABEL_ADVANCE * n_chars))
        cx, cy = rot(x + labelnudge[0], y + labelnudge[1])
        _glyphlabel(ax, label, cx, cy, fontsize, color=labelcolor,
                    rotation=readableangle(angle), use_latex=use_latex,
                    zorder=use_zorder + 1)

    apex, tangent = portapex(xy, R, angle, length, height)
    if debug:
        ax.plot([apex[0]], [apex[1]], 'r.')

    return {'apex': apex, 'tangent': tangent, 'angle': angle}


def txline(ax=None, xy=(0, 0), angle=0.0, R=2.0, length=1.0, height=1.0,
         label='', color='black', fill='#cccccc', labelcolor='black',
         lw=None, labelscale=1.0, labelnudge=(0, 0), drawlabel=True,
         drawendmarks=True, endmarks=(), use_latex=False, use_zorder=10,
         debug=False):
    """Draw a txline glyph (slender cylinder, closed cap, open mouth, stubs).

    `endmarks` names the ends drawn as FILLED dots (i.e. the terminated
    ones); the others are hollow. Returns ``{'ends': {'x0': ((x, y),
    (tx, ty)), 'xL': ...}}``.
    """
    if ax is None:
        _, ax = plt.subplots()
    lw = TXLINE_LW if lw is None else lw
    x, y, w, h, rx = txlinegeometry(xy, R, length, height)
    # draw axis-aligned, then rotate every artist about the glyph center
    glyph_tf = (mtransforms.Affine2D().rotate_deg_around(x, y, angle)
                + ax.transData)

    ax.add_patch(mpatches.Rectangle(
        (x - w, y - h), 2 * w, 2 * h, facecolor=fill, edgecolor='none',
        zorder=use_zorder, transform=glyph_tf))
    ax.add_patch(mpatches.Ellipse(
        (x - w, y), 2 * rx, 2 * h, facecolor=fill, edgecolor='none',
        zorder=use_zorder, transform=glyph_tf))
    ax.add_patch(mpatches.Arc(
        (x - w, y), 2 * rx, 2 * h, theta1=90, theta2=270, edgecolor=color,
        linewidth=lw, zorder=use_zorder + 1, transform=glyph_tf))
    ax.add_patch(mpatches.Ellipse(
        (x + w, y), 2 * rx, 2 * h, facecolor='white', edgecolor=color,
        linewidth=lw, zorder=use_zorder + 1, transform=glyph_tf))
    for yy in (y - h, y + h):
        ax.add_line(mlines.Line2D([x - w, x + w], [yy, yy], color=color,
                                  linewidth=lw, zorder=use_zorder + 1,
                                  transform=glyph_tf))
    # closed (left) cap: the stub leaves the outside of the rounded cap,
    # which is the physical outer surface of the line
    ax.add_line(mlines.Line2D(
        [x - w - rx - TXLINE_LEAD_LEN * R, x - w - rx], [y, y], color=color,
        linewidth=lw, zorder=use_zorder + 1, transform=glyph_tf))
    # open (right) mouth: the conductor comes out of the BORE, so its stub
    # runs from the CENTER of the mouth ellipse and is drawn in FRONT of it,
    # with a round cap so it reads as a wire end rather than a cut edge.
    # From the rim it looked stuck to the outside of the mouth.
    ax.add_line(mlines.Line2D(
        [x + w, x + w + rx + TXLINE_LEAD_LEN * R], [y, y], color=color,
        linewidth=lw, solid_capstyle='round', zorder=use_zorder + 1.4,
        transform=glyph_tf))

    ends = txlineendpoints(xy, R, angle, length, height)
    if drawendmarks:
        for name, (pt, _) in ends.items():
            filled = name in (endmarks or ())
            mark = 'black' if filled else 'darkgray'
            ax.add_patch(mpatches.Circle(
                pt, 0.12 * R, facecolor=(mark if filled else 'white'),
                edgecolor=mark, linewidth=1.6, zorder=use_zorder + 1.5))

    if drawlabel and label:
        ppdu = pointsperdataunit(ax)
        n_chars = max(len(str(label)), 1)
        if 2 * h >= 0.85 * R:
            # Inside the body, sized to the body HEIGHT so stretching the
            # line grows its label with it. (This used to be capped at
            # 1.1 R, which pinned the label to a fixed size the moment the
            # body was stretched at all -- and made `labelscale` look inert,
            # because it was scaling an already-tiny base.)
            tx, ty = x, y
            fontsize = 2 * h * ppdu * GLYPH_LABEL_SCALE * 1.6 * labelscale
            # ...but never wider than the body it sits in
            fontsize = min(fontsize, GLYPH_LABEL_FILL * 2 * w * ppdu
                           / (GLYPH_LABEL_ADVANCE * n_chars))
        else:
            # too thin to hold text: float it just above, where nothing
            # clips it, at a size tied to the node scale
            tx, ty = x, y + h + 0.45 * R
            fontsize = 0.9 * R * ppdu * GLYPH_LABEL_SCALE * 1.6 * labelscale
        tx, ty = rotatepoint(tx + labelnudge[0], ty + labelnudge[1], x, y,
                             angle)
        _glyphlabel(ax, label, tx, ty, fontsize,
                    color=labelcolor, rotation=readableangle(angle),
                    use_latex=use_latex, zorder=use_zorder + 2)

    if debug:
        for pt, _ in ends.values():
            ax.plot([pt[0]], [pt[1]], 'r.')

    return {'ends': ends, 'angle': angle}


class GraphCircuit:
    def __init__(self, nodes=None, edges=None, allow_duplicate_labels=False, use_latex=False):
        """Initialize a GraphCircuit object.

        Parameters
        ----------
        nodes : list of dicts, optional
            Node definitions. Each dictionary should have the following keys:
            'nodecent', 'nodelabel', 'selfloopangle', 'selflooplabel'.
        edges : list of dicts, optional
            Edge definitions. Each dictionary should have the following keys:
            'startend', 'loopiness'.
        ax : matplotlib axes, optional
            Axes to draw the graph on. If not provided, a new figure is created.
        allow_duplicate_labels : bool, optional
            If True, allow nodes with duplicate labels. Default is False.
        use_latex : bool, optional
            If True, use LaTeX rendering (slow but high quality). Default is False (uses MathText/STIX).

        """
        self.nodes = nodes or []
        self.edges = edges or []
        # Schematic glyphs and their routed wiring (see the SCHEMATIC GLYPHS
        # section above). These are drawing-only: they carry no graph
        # semantics, so nothing else in the container needs to know about
        # them beyond drawing them and sizing the axes to fit.
        self.ports = []
        self.txlines = []
        self.wires = []
        self.allow_duplicate_labels = allow_duplicate_labels
        self.use_latex = use_latex

        # GLOBAL node and edge preferences
        self.nodeprefs = {
            'R': 2,
            # 'nodecolor': 'cornflowerblue',
            'nodeoutlinecolor': 'white',
            # 'nodealpha': None,
            # 'selfloopcolor': 'black',
            'nodelabelcolor': 'white',
            # 'nodelabelsize': 28,
            'nodelw': 2.5,
            'arrowlengthsc': 1,
            'drawlabels': True,
            # 'drawselfloop': True,
            'conj': False,
            'selflooplabel':r'$\Delta_A$',
            'selflooplabelnudge': (0, 0),
            'selflooplw': 2.5,
            'nodelabelnudge': (0, 0),
        }
        self.edgeprefs = {
            'arrowlength': 0.4,
            'arrowthetatweak': -8,
            'lw': 1.5, # do we want this?
            'color': 'black'
            }
        self.glyphprefs = {
            'R': None,          # None -> fall back to nodeprefs['R']
            'color': 'black',
            'labelcolor': 'black',
            'length': 1.0,
            'height': 1.0,
            'labelscale': 1.0,
            'labelnudge': (0, 0),
            }

    def __repr__(self):
        """Return a string representation of the graph showing nodes and edges in table format."""
        lines = []
        lines.append(f"GraphCircuit(allow_duplicate_labels={self.allow_duplicate_labels})")
        lines.append("")

        # Nodes table
        if self.nodes:
            lines.append(f"Nodes ({len(self.nodes)}):")
            lines.append("-" * 70)
            if self.allow_duplicate_labels and any(n.get('node_id') is not None for n in self.nodes):
                lines.append(f"{'ID':<5} {'Label':<15} {'Position':<20} {'Conj':<6}")
                lines.append("-" * 70)
                for node in self.nodes:
                    node_id = node.get('node_id', 'N/A')
                    label = node.get('nodelabel', '?')
                    pos = node.get('nodecent', (0, 0))
                    conj = node.get('conj', False)
                    lines.append(f"{node_id!s:<5} {label:<15} ({pos[0]:>6.2f}, {pos[1]:>6.2f})     {str(conj):<6}")
            else:
                lines.append(f"{'Label':<15} {'Position':<20} {'Conj':<6}")
                lines.append("-" * 70)
                for node in self.nodes:
                    label = node.get('nodelabel', '?')
                    pos = node.get('nodecent', (0, 0))
                    conj = node.get('conj', False)
                    lines.append(f"{label:<15} ({pos[0]:>6.2f}, {pos[1]:>6.2f})     {str(conj):<6}")
        else:
            lines.append("Nodes: (none)")

        lines.append("")

        # Edges table
        if self.edges:
            lines.append(f"Edges ({len(self.edges)}):")
            lines.append("-" * 70)
            lines.append(f"{'From':<15} {'To':<15} {'Style':<10} {'Direction':<10}")
            lines.append("-" * 70)
            for edge in self.edges:
                from_node = edge.get('fromnode', '?')
                to_node = edge.get('tonode', '?')
                style = edge.get('style', '?')
                direction = edge.get('whichedges', '?')
                lines.append(f"{from_node:<15} {to_node:<15} {style:<10} {direction:<10}")
        else:
            lines.append("Edges: (none)")

        return "\n".join(lines)

    def addnode(self, **nodedict):
        """Add a node to the graph.

        Parameters
        ----------
        nodedict : dict
            Node definition. Should have the following keys:
            'label', 'xy'

            optional:
            'node_id' (int): Unique identifier for the node. If not provided and allow_duplicate_labels=True,
                            an auto-incrementing ID will be assigned.
            'selfloopangle', 'selflooplabel', 'conj', 'selfloopcolor', 'nodelabelcolor', 'nodelabelsize', 'arrowlengthsc', 'nodelw', 'selflooplw', 'drawlabels', 'drawselfloop', 'selflooplabelnudge', 'nodelabelnudge'

            Note that 'drawselfloop' = False|None will suppress drawing the self-loop and its label.

        Example:
            g = gp.GraphCircuit()

            g.nodeprefs['nodelabelsize'] = 24
            g.nodeprefs['selflooplw'] = 2
            g.addnode(label='A',xy=[0,0])
            g.addnode(label='B',xy=[5,5])
            g.addnode(label='C',xy=[10,10],conj=True,nodealpha=1.2)
            g.addnode(label='D',xy=[15,0],selfloopangle=90)

            # With duplicate labels, use node_id:
            g.addnode(label='A',xy=[0,0],node_id=0)
            g.addnode(label='A',xy=[5,5],node_id=1)

            g.draw(overfrac=.3)

        """

        # rename the key from label to nodelabel
        nodedict['nodelabel'] = nodedict.pop('label')
        nodedict['nodecent'] = nodedict.pop('xy')

        # Handle node_id
        if 'node_id' in nodedict:
            nodedict['node_id'] = nodedict.pop('node_id')
        elif self.allow_duplicate_labels:
            # Auto-assign node_id if duplicate labels are allowed
            if not hasattr(self, '_node_id_counter'):
                self._node_id_counter = 0
            nodedict['node_id'] = self._node_id_counter
            self._node_id_counter += 1
        else:
            nodedict['node_id'] = None

        # rename color to nodecolor if provided
        if 'color' in nodedict:
            nodedict['nodecolor'] = nodedict.pop('color')


        # there's probably a better way to do this, but we want to populate the nodedict with some defaults and override them as specified by the user
        for k,v in self.nodeprefs.items():
            if k not in nodedict:
                if k == 'selflooplabel':
                    # warnings.warn('WARNING: selflooplabel not specified. Setting it to the nodelabel.')
                    # we'll just set it to None if it was't specified by the user and we'll automatically set it to the nodelabel
                    nodedict['selflooplabel'] = None
                else:
                    nodedict[k] = v

        # check if the node label already exists. If so, then we'll just append a number to it as a kludge and notify the user.
        if not self.allow_duplicate_labels and nodedict['nodelabel'] in [node['nodelabel'] for node in self.nodes]:
            warnings.warn('Node label already exists. Please use a unique label.')
        else:
            self.nodes.append(nodedict)

        # autolabel the self-loops if not specified by the user
        # if 'selflooplabel' was not specified then we'll set it to the nodelabel
        if nodedict['selflooplabel'] is None:
            if nodedict['conj'] is False:
                nodedict['selflooplabel'] = rf'$\Delta_{{{nodedict["nodelabel"]}}}$'
            else:
                nodedict['selflooplabel'] = rf'${{-}}\Delta_{{{nodedict["nodelabel"]}}}^*$'

    
    def addprettynode(self, 
                    mode = 'A',    # str in ['A','B','C','D','E']
                    sub = '',      # subscript for the label
                    xy = (0,0),    # location   
                    loopangle = 0, # angle of the self-loop 
                    conj = False,  # conjugation state
                    D = 1,        # diameter of the node
                    fontscale = 1, # scale the font size
                    **kwargs
                    ):
        """Add pretty node to graph.
        This uses PRETTYNODE which is a wrapper around the standard node function.
        It's a little more user-friendly and generates a mode representations with a nice set of 
        defaults.
        """
        # check if the node label already exists. If it does then we just notify the user and do nothing.
        modestr = f'{mode}{sub}'
        if not self.allow_duplicate_labels and modestr in [node['nodelabel'] for node in self.nodes]:
            warnings.warn('Node label already exists. Please use a unique label.')
            # and then do nothing
        else:
            nodedict = prettynode(mode=mode,sub=sub,xy=xy,loopangle=loopangle,conj=conj,D=D,fontscale=fontscale,
                                  **kwargs,
                                  )
            self.nodes.append(nodedict)

    # ---- schematic glyphs ---------------------------------------------------

    def _glyphR(self, R=None):
        """Reference radius for a glyph: explicit, else the glyph default,
        else the node default -- so glyphs stay proportional to the nodes."""
        if R is not None:
            return R
        if self.glyphprefs.get('R') is not None:
            return self.glyphprefs['R']
        return self.nodeprefs['R']

    def addport(self, label='', xy=(0, 0), angle=0.0, autoorient=False,
                    port_id=None, **kwargs):
        """Add a port glyph (home-plate pentagon + lead).

        Parameters
        ----------
        label : str
            Drawn inside the straight part of the body.
        xy : (float, float)
            Glyph center.
        angle : float
            Degrees CCW; the lead points along it.
        autoorient : bool
            When True the lead aims at the centroid of whatever this
            port is wired to, and `angle` is ignored (this is the
            "auto-orient" toggle the GUI exposes). A port with no wires
            falls back to `angle`.
        port_id : int, optional
            Explicit id; auto-assigned when omitted. Wires may reference a
            port by id or by label.
        **kwargs
            `R`, `length`, `height`, `color`, `fill`, `labelcolor`, `lw`,
            `hatch`, `labelscale`, `labelnudge`, `drawlabel`.

        Example
        -------
        g.addport(label='P1', xy=(-8, 0), autoorient=True)
        g.addwire(start=('port', 'P1'), end=('node', 'A'))
        """
        term = dict(self.glyphprefs)
        term.pop('R', None)
        term.update(kwargs)
        term['label'] = label
        term['xy'] = tuple(xy)
        term['angle'] = float(angle)
        term['autoorient'] = bool(autoorient)
        term['R'] = self._glyphR(kwargs.get('R'))
        if port_id is None:
            port_id = len(self.ports)
        term['port_id'] = port_id
        self.ports.append(term)
        return term

    def addtxline(self, label='', xy=(0, 0), angle=0.0, txline_id=None, **kwargs):
        """Add a txline glyph (slender cylinder with a closed cap and an open
        mouth). `length`/`height` stretch it; see `addport` for the
        shared keyword arguments.

        Example
        -------
        g.addtxline(label='TL1', xy=(0, 0), angle=0, length=1.4, height=1.0)
        g.addwire(start=('txline', 'TL1', 'xL'), end=('node', 'B'))
        """
        cx = dict(self.glyphprefs)
        cx.pop('R', None)
        cx.setdefault('fill', '#cccccc')
        cx.update(kwargs)
        cx['label'] = label
        cx['xy'] = tuple(xy)
        cx['angle'] = float(angle)
        cx['R'] = self._glyphR(kwargs.get('R'))
        if txline_id is None:
            txline_id = len(self.txlines)
        cx['txline_id'] = txline_id
        self.txlines.append(cx)
        return cx

    def addwire(self, start, end, **kwargs):
        """Wire two anchors together with one smooth routed curve.

        `start` and `end` are anchor specs:

            ('node', 'A')            -- by node label
            ('node', 3)              -- by node_id (an int means id)
            ('port', 'P1')       -- by port label or id
            ('txline', 'TL1', 'xL')    -- a txline END ('x0' or 'xL')

        **kwargs: `color`, `lw`, `linestyle`, `alpha`, `label`,
        `labelscale`, `labelcolor`.
        """
        w = dict(kwargs)
        w['start'] = tuple(start)
        w['end'] = tuple(end)
        self.wires.append(w)
        return w

    def _findport(self, key):
        for term in self.ports:
            if isinstance(key, int) and not isinstance(key, bool):
                if term['port_id'] == key:
                    return term
            elif term['label'] == key:
                return term
        raise ValueError(f"No port matching {key!r}")

    def _findtxline(self, key):
        for cx in self.txlines:
            if isinstance(key, int) and not isinstance(key, bool):
                if cx['txline_id'] == key:
                    return cx
            elif cx['label'] == key:
                return cx
        raise ValueError(f"No txline matching {key!r}")

    def _findnode(self, key):
        for node in self.nodes:
            if isinstance(key, int) and not isinstance(key, bool):
                if node.get('node_id') == key:
                    return node
            elif node['nodelabel'] == key:
                return node
        raise ValueError(f"No node matching {key!r}")

    def _anchorpos(self, spec):
        """Bare position of an anchor, used to aim auto-orienting ports
        BEFORE any angle is known (so the two never depend on each other)."""
        kind = spec[0]
        if kind == 'node':
            return tuple(self._findnode(spec[1])['nodecent'])
        if kind == 'port':
            return tuple(self._findport(spec[1])['xy'])
        if kind == 'txline':
            cx = self._findtxline(spec[1])
            end = spec[2] if len(spec) > 2 else 'xL'
            return txlineendpoints(cx['xy'], cx['R'], cx['angle'],
                                 cx['length'], cx['height'])[end][0]
        raise ValueError(f"Unknown wire anchor kind {kind!r}")

    def _portangle(self, term):
        """Drawing angle of a port: its own when pinned or unwired, else
        aimed at the CENTROID of everything it is wired to (a cluster
        therefore pulls proportionally, which a mean of unit directions
        would not)."""
        if not term.get('autoorient'):
            return term['angle']
        targets = []
        for w in self.wires:
            for near, far in ((w['start'], w['end']), (w['end'], w['start'])):
                if near[0] == 'port':
                    try:
                        if self._findport(near[1]) is term:
                            targets.append(self._anchorpos(far))
                    except ValueError:
                        pass
        if not targets:
            return term['angle']
        px, py = term['xy']
        cx = sum(t[0] for t in targets) / len(targets)
        cy = sum(t[1] for t in targets) / len(targets)
        vx, vy = cx - px, cy - py
        if abs(vx) < 1e-12 and abs(vy) < 1e-12:
            return term['angle']
        return float(arctan2(vy, vx) * 180 / pi)

    def _wireanchor(self, spec, toward=None):
        """((x, y), (tx, ty)) where a wire attaches, and the unit tangent
        there. `toward` is the OTHER end's point, needed to pick the side of
        a node circle."""
        kind = spec[0]
        if kind == 'node':
            node = self._findnode(spec[1])
            R = node.get('R') or self.nodeprefs['R']
            return nodewireend(node['nodecent'], R,
                               toward if toward is not None
                               else node['nodecent'])
        if kind == 'port':
            term = self._findport(spec[1])
            return portwirestart(term['xy'], term['R'],
                                 self._portangle(term),
                                 term['length'], term['height'])
        if kind == 'txline':
            cx = self._findtxline(spec[1])
            end = spec[2] if len(spec) > 2 else 'xL'
            return txlineendpoints(cx['xy'], cx['R'], cx['angle'],
                                 cx['length'], cx['height'])[end]
        raise ValueError(f"Unknown wire anchor kind {kind!r}")

    def _terminatedtxlineends(self, cx):
        """The end names of `cx` that a wire actually lands on -- drawn as
        filled dots, the rest hollow."""
        marks = set()
        for w in self.wires:
            for spec in (w['start'], w['end']):
                if spec[0] != 'txline':
                    continue
                try:
                    if self._findtxline(spec[1]) is cx:
                        marks.add(spec[2] if len(spec) > 2 else 'xL')
                except ValueError:
                    pass
        return tuple(marks)

    def _drawglyphs(self, debug=False):
        """Draw txlines, ports and their wiring onto self.ax."""
        for cx in self.txlines:
            txline(ax=self.ax, xy=cx['xy'], angle=cx['angle'], R=cx['R'],
                 length=cx['length'], height=cx['height'],
                 label=cx['label'], color=cx['color'],
                 fill=cx.get('fill', '#cccccc'),
                 labelcolor=cx['labelcolor'], lw=cx.get('lw'),
                 labelscale=cx['labelscale'], labelnudge=cx['labelnudge'],
                 drawlabel=cx.get('drawlabel', True),
                 endmarks=self._terminatedtxlineends(cx),
                 use_latex=self.use_latex, debug=debug)

        for term in self.ports:
            port(ax=self.ax, xy=term['xy'],
                     angle=self._portangle(term), R=term['R'],
                     length=term['length'], height=term['height'],
                     label=term['label'], color=term['color'],
                     fill=term.get('fill', 'white'),
                     labelcolor=term['labelcolor'], lw=term.get('lw'),
                     hatch=term.get('hatch'),
                     labelscale=term['labelscale'],
                     labelnudge=term['labelnudge'],
                     drawlabel=term.get('drawlabel', True),
                     use_latex=self.use_latex, debug=debug)

        for w in self.wires:
            # resolve the far end first: a node needs to know which side it
            # is being approached from before it can offer an attach point
            p_far = self._anchorpos(w['end'])
            p0, t0 = self._wireanchor(w['start'], toward=p_far)
            p1, t1 = self._wireanchor(w['end'], toward=p0)
            if w['end'][0] in ('port', 'txline'):
                # arrive travelling INTO the lead, not out of it
                t1 = (-t1[0], -t1[1])
            wire(ax=self.ax, p0=p0, t0=t0, p1=p1, t1=t1,
                 R=self._glyphR(), color=w.get('color', WIRE_COLOR),
                 lw=w.get('lw'), linestyle=w.get('linestyle', '-'),
                 alpha=w.get('alpha', 0.9), label=w.get('label'),
                 labelscale=w.get('labelscale', 1.0),
                 labelcolor=w.get('labelcolor'), use_latex=self.use_latex)

    def _glyphextentpoints(self):
        """Extreme points of every glyph, so _axisequalizer can size the
        axes to include them (a txline is long enough to leave the frame that
        the nodes alone would set)."""
        pts = []
        for term in self.ports:
            x, y, w, h, apex_x = portgeometry(
                term['xy'], term['R'], term['length'], term['height'])
            angle = self._portangle(term)
            for px, py in ((x - w / 2, y - h / 2), (x - w / 2, y + h / 2),
                           (apex_x, y - h / 2), (apex_x, y + h / 2)):
                pts.append(rotatepoint(px, py, x, y, angle))
        for cx in self.txlines:
            x, y, w, h, rx = txlinegeometry(cx['xy'], cx['R'], cx['length'],
                                          cx['height'])
            half_w = w + rx + TXLINE_LEAD_LEN * cx['R']
            half_h = max(h, 0.45 * cx['R'] + 0.9 * cx['R'])  # label floats above
            for px, py in ((x - half_w, y - half_h), (x - half_w, y + half_h),
                           (x + half_w, y - half_h), (x + half_w, y + half_h)):
                pts.append(rotatepoint(px, py, x, y, cx['angle']))
        return pts

    def _getnodecoords(self, nodelabel1=None, nodelabel2=None, nodeid1=None, nodeid2=None):
        """
        Get the coordinates of the labeled nodes.

        Parameters
        ----------
        nodelabel1 : str, optional
            Label of the first node.
        nodelabel2 : str, optional
            Label of the second node.
        nodeid1 : int, optional
            ID of the first node (takes precedence over label).
        nodeid2 : int, optional
            ID of the second node (takes precedence over label).

        Returns
        -------
        v1, v2 : 2-tuple of 2-tuples
            Coordinates of the two nodes.
        """
        v1 = None
        v2 = None

        # Use node_id if provided (unambiguous), otherwise use label
        for node in self.nodes:
            if nodeid1 is not None and node.get('node_id') == nodeid1:
                v1 = node['nodecent']
            elif nodeid1 is None and node['nodelabel'] == nodelabel1:
                v1 = node['nodecent']

            if nodeid2 is not None and node.get('node_id') == nodeid2:
                v2 = node['nodecent']
            elif nodeid2 is None and node['nodelabel'] == nodelabel2:
                v2 = node['nodecent']

        return v1, v2
    
    def _getnodeR(self, nodelabel=None, nodeid=None):
        """Get the radius of a node by label or ID."""
        for node in self.nodes:
            if nodeid is not None and node.get('node_id') == nodeid:
                if node['R'] is not None:
                    return node['R']
                else:
                    return self.nodeprefs['R']
            elif nodeid is None and node['nodelabel'] == nodelabel:
                if node['R'] is not None:
                    return node['R']
                else:
                    return self.nodeprefs['R']
    
    def addedge(self, fromnode=None, tonode=None,
                fromnode_id=None, tonode_id=None,
                style='loopy',
                labelfontsize = 16,
                **edgekwargs):
        """Add an edge to the graph.

        Parameters
        ----------
        fromnode : str, optional
            Label of the source node. Required if fromnode_id not provided.
        tonode : str, optional
            Label of the target node. Required if tonode_id not provided.
        fromnode_id : int, optional
            Node ID of the source node. Use this when node labels are ambiguous.
        tonode_id : int, optional
            Node ID of the target node. Use this when node labels are ambiguous.
        style : str, optional
            Edge style: 'loopy', 'single', or 'double'. Default is 'loopy'.
        labelfontsize : int, optional
            Font size for edge labels. Default is 16.
        **edgekwargs : dict
            Additional edge parameters (loopiness, arrowstyle, lw, color, etc.)

        Notes
        -----
        - If node labels are unique, use fromnode/tonode parameters
        - If node labels are duplicated, use fromnode_id/tonode_id parameters
        - If fromnode/tonode are ambiguous, an error will be raised with node_id information

        Example
        -------
        # With unique labels:
        g.addedge(fromnode='A', tonode='B')

        # With duplicate labels, use node_id:
        g.addedge(fromnode_id=0, tonode_id=1)

        """

        # Determine which nodes to connect
        if fromnode_id is not None and tonode_id is not None:
            # Use node IDs (explicit, unambiguous)
            from_nodes = [n for n in self.nodes if n.get('node_id') == fromnode_id]
            to_nodes = [n for n in self.nodes if n.get('node_id') == tonode_id]

            if not from_nodes:
                raise ValueError(f"No node found with node_id={fromnode_id}")
            if not to_nodes:
                raise ValueError(f"No node found with node_id={tonode_id}")

            fromnode = from_nodes[0]['nodelabel']
            tonode = to_nodes[0]['nodelabel']

        elif fromnode is not None and tonode is not None:
            # Use node labels - check for ambiguity
            from_nodes = [n for n in self.nodes if n['nodelabel'] == fromnode]
            to_nodes = [n for n in self.nodes if n['nodelabel'] == tonode]

            if len(from_nodes) == 0:
                raise ValueError(f"No node found with label '{fromnode}'")
            if len(to_nodes) == 0:
                raise ValueError(f"No node found with label '{tonode}'")

            if len(from_nodes) > 1 or len(to_nodes) > 1:
                error_msg = "Ambiguous node labels detected:\n"
                if len(from_nodes) > 1:
                    from_ids = [n['node_id'] for n in from_nodes]
                    error_msg += f"  - Label '{fromnode}' matches {len(from_nodes)} nodes with node_ids: {from_ids}\n"
                if len(to_nodes) > 1:
                    to_ids = [n['node_id'] for n in to_nodes]
                    error_msg += f"  - Label '{tonode}' matches {len(to_nodes)} nodes with node_ids: {to_ids}\n"
                error_msg += "Please use fromnode_id and tonode_id parameters to specify which nodes to connect."
                raise ValueError(error_msg)
        else:
            raise ValueError("Must provide either (fromnode, tonode) or (fromnode_id, tonode_id)")

        edgedict = dict(
            fromnode = fromnode,
            tonode = tonode,
            style = style,
            labelfontsize = labelfontsize,
            **edgekwargs
        )

        # Store node_ids if they were specified (for correct rendering with duplicate labels)
        if fromnode_id is not None:
            edgedict['fromnode_id'] = fromnode_id
        if tonode_id is not None:
            edgedict['tonode_id'] = tonode_id

        self.edges.append(edgedict)



    def removenode(self, nodelabel, conj=False):
        # self.nodes = [node for node in self.nodes if node['nodelabel'] != nodelabel]
        nodelist_tmp = []

        for node in self.nodes:
            if node['nodelabel'] != nodelabel:
                # need to get the matching conjugation state
                # if node['conj'] != conj:
                #    self.nodes.append(node)
                nodelist_tmp.append(node)
            else:
                if node['conj'] != conj:
                    warnings.warn('Node not removed because the conjugation state does not match. Did you mean to remove the conjugated version?')
                    nodelist_tmp.append(node)
                else:
                    logger.debug('Node removed.')

        # still need to audit the edge list to remove any edges that connect to this node
        # removeedge(self, nodelist = [])

        self.nodes = nodelist_tmp
        

    def removeedge(self, nodelist):
        """Remove edges connected to any node in the given list.

        Filters the edge list to remove edges where either endpoint
        is one of the nodes being removed.
        """
        if not nodelist:
            return
        node_labels = {n['label'] for n in nodelist}
        self.edges = [
            edge for edge in self.edges
            if edge['startend'][0] not in node_labels
            and edge['startend'][1] not in node_labels
        ]

    def draw(self, ax=None, figsize = 8, overfrac=0.25, debug=False)->None:
        """
        Draw the graph.

        Parameters
        ----------
        ax : matplotlib axes, optional
            Axes to draw the graph on. If not provided, a new figure is created.
        overfrac : float, optional
            Fraction of the maximum extent to add to the maximum and minimum
            coordinates of the nodes. The default is 0.1. Increase if you have big 
            self-loops that are getting cut off.
        debug : bool, optional
            Whether to print debug messages. The default is False.

        Returns
        -------
        None
        """

        # Configure matplotlib rendering based on use_latex setting
        if self.use_latex:
            plt.rc('text', usetex=True)
            # Load packages for bold sans-serif math fonts
            rcParams['text.latex.preamble'] = r'\usepackage{amsmath}\usepackage{sfmath}\renewcommand{\familydefault}{\sfdefault}'
            # Note: LaTeX rendering is much slower but supports full LaTeX features
        else:
            plt.rc('text', usetex=False)
            rcParams['mathtext.fontset'] = 'stix'
            rcParams['font.family'] = 'STIXGeneral'

        if ax is None:
            _, self.ax = plt.subplots(figsize=(figsize,figsize))
            # Set the x and y limits of the axes
            # self.ax.set_xlim(-xylim/2,xylim/2);self.ax.set_ylim(-xylim/2,xylim/2)
            # self._setminmaxnodecoords(overfrac=overfrac,debug=debug)
            self._axisequalizer(overfrac=overfrac,debug=debug)
        else:
            self.ax = ax


        # Draw the nodes
        for node in self.nodes:
            # plotnode(ax=self.ax,**node,**self.nodeprefs,debug=debug)
            # plotnode(ax=self.ax, **node, debug=debug)
            # 090924: WILL REVAMP THIS TO USE PRETTYNODES.
            # This means that the dictionary we pass will be a little more restricted
            # and prettynode() will handle the rest of the details, including the autoscaling from
            # the figure scaling and axis limits.

            # Filter out node_id before passing to plotnode (it's only for internal tracking)
            node_kwargs = {k: v for k, v in node.items() if k != 'node_id'}
            plotnode(ax=self.ax, **node_kwargs, use_latex=self.use_latex, debug=debug)
        


        # Draw the edges
        for ed in self.edges:
            if debug:
                logger.debug(f'{ed=}')
                logger.debug(f'edge from {ed["fromnode"]} to {ed["tonode"]}')

            # Use node_ids if available (for duplicate labels), otherwise use labels
            from_id = ed.get('fromnode_id')
            to_id = ed.get('tonode_id')

            ed_kwargs = self._strippededgekwargs(ed)
            edge(ax=self.ax,
                 nodexy=self._getnodecoords(
                     nodelabel1=ed['fromnode'], nodelabel2=ed['tonode'],
                     nodeid1=from_id, nodeid2=to_id
                 ),
                 nodeR=[
                     self._getnodeR(nodelabel=ed['fromnode'], nodeid=from_id),
                     self._getnodeR(nodelabel=ed['tonode'], nodeid=to_id)
                 ],
                 style=ed['style'],
                 debug=debug,
                 **ed_kwargs
                )

        # Draw the schematic glyphs (ports, txlines) and their wiring
        self._drawglyphs(debug=debug)

        # Make sure the axes are tight
        plt.tight_layout()
        # plt.axis('equal')
        # self._axisequalizer()



    def save(self,fname,**kwargs):
        # let's attempt a mod to eliminate the useless figure and bounding boxes from the SVG:

        self.ax.set_position([0, 0, 1, 1])
        self.ax.patch.set_alpha(0.)
        plt.gcf().patch.set_alpha(0.)


        # make directory if it doesn't exist
        os.makedirs(os.path.dirname(fname), exist_ok=True)
        # plt.savefig(fname,**kwargs)
        plt.savefig(fname, bbox_inches=0, transparent=True, **kwargs)
        plt.gcf().savefig(fname, bbox_inches=0, transparent=True, **kwargs)

    def listnodes(self)->None:
        """
        List just the nodes and the corresponding coordinates.

        Returns
        -------
        None
        """
        for idx,node in enumerate(self.nodes):
            logger.debug('%d: %s: %s;\t\tconj = %s', idx, node["nodelabel"], node["nodecent"], node["conj"])

    def _setminmaxnodecoords(self, overfrac=0.1, debug=False)->None:
        """
        Get the minimum and maximum coordinates of the nodes.

        This function is a helper function for the `draw` method. It is called by
        `draw` to set the x and y limits of the axes based on the positions of the
        nodes.

        Parameters
        ----------
        overfrac : float, optional
            Fraction of the maximum extent to add to the maximum and minimum
            coordinates of the nodes. The default is 0.1.

        Returns
        -------
        None
        """

        if debug:
            logger.debug(f'{self.nodes=}')


        if len(self.nodes) > 1: 
            # Get the minimum and maximum x and y coordinates of the nodes
            minx = min([node['nodecent'][0] for node in self.nodes])
            maxx = max([node['nodecent'][0] for node in self.nodes])
            miny = min([node['nodecent'][1] for node in self.nodes])
            maxy = max([node['nodecent'][1] for node in self.nodes])

            # # Print the minimum and maximum coordinates of the nodes

            # Set the x and y limits of the axes
            dx = (maxx - minx) * overfrac/2
            dy = (maxy - miny) * overfrac/2
            # self.ax.set_xlim(minx-dx,maxx+dx)
            # self.ax.set_ylim(miny-dy,maxy+dy)

            span  = max(dx,dy,*[2*node['R'] for node in self.nodes])
            self.ax.set_xlim(minx-span/2,maxx+span/2)
            self.ax.set_ylim(miny-span/2,maxy+span/2)


            if debug:
                # show the axis boundaries
                plt.axis('on')
        else:
            pass

    def _strippededgekwargs(self, ed):
        # return {k:v for k,v in ed.items() if k in self.edgeprefs}
        # pass

        stripped_kwargs = {}
        for k,v in ed.items():
            # Filter out internal keys that shouldn't be passed to edge() function
            if k not in ['fromnode','tonode','style','fromnode_id','tonode_id']:
                stripped_kwargs[k] = v

        return stripped_kwargs
    
    def _axisequalizer(self,overfrac = 0.2, debug=False):
        """
        # Make the axes equal in scaling.
        Size the graph to accommodate the node positions.
        """

        # Get the x and y limits of the axes
        # xlim = self.ax.get_xlim()
        # ylim = self.ax.get_ylim()

        # Get the maximum extent of the x and y limits
        # maxextent = max(abs(xlim[0]),abs(xlim[1]),abs(ylim[0]),abs(ylim[1]))

        # # Set the x and y limits to be equal
        # self.ax.set_xlim(-maxextent/2,maxextent/2)
        # self.ax.set_ylim(-maxextent/2,maxextent/2)

        # # Make the aspect ratio of the axes equal
        # self.ax.set_aspect('equal')

        # Glyph corners join the node centers, so a long txline or a port
        # lead can never fall outside the frame the nodes alone would set.
        xs = [node['nodecent'][0] for node in self.nodes]
        ys = [node['nodecent'][1] for node in self.nodes]
        for px, py in self._glyphextentpoints():
            xs.append(px)
            ys.append(py)
        if not xs:
            return

        maxx, minx = max(xs), min(xs)
        maxy, miny = max(ys), min(ys)

        maxnodeR = max([node['R'] for node in self.nodes], default=None)
        if maxnodeR is None:
            maxnodeR = self._glyphR()


        centerx,centery = (maxx+minx)/2,(maxy+miny)/2

        # Get the maximum extent of the x and y limits
        # maxextent = max(abs(maxx-minx),abs(maxy-miny))*OVERSIZE_SCALING

        # self.ax.set_xlim(centerx-maxextent/2,centerx+maxextent/2)
        # self.ax.set_ylim(centery-maxextent/2,centery+maxextent/2)
        # betteroverscalefrac = min(abs(maxx-minx),abs(maxy-miny))\
        #                         * OVERSIZE_SCALING\
        #                         /min(max(abs(maxx-minx),maxnodeR),max(abs(maxy-miny),maxnodeR))


        # Calculate actual extent needed including self-loops and labels
        # Be more conservative - self-loop typically extends to about R*3.5 from center
        # (not the full R*7.2 theoretical maximum)
        max_element_extension = maxnodeR  # Start with just the node radius

        for node in self.nodes:
            R = node.get('R', self.nodeprefs.get('R', 2.0))
            # Check if this node has a self-loop
            if node.get('drawselfloop', self.nodeprefs.get('drawselfloop', True)):
                selfloopscale = node.get('selfloopscale', 1.0)
                # Self-loop + label extends to approximately R*3.5 empirically
                # (actual geometry is complex, but this gives a good tight fit)
                selfloop_extent = R * (2.5 + selfloopscale)
                max_element_extension = max(max_element_extension, selfloop_extent)

        # overfrac=0.0 gives tight fit with just the elements
        # overfrac=0.2 adds 20% extra space
        total_buffer = max_element_extension * (1 + overfrac)

        spanx = abs(maxx-minx) + total_buffer*2
        spany = abs(maxy-miny) + total_buffer*2


        self.ax.set_xlim(centerx-spanx/2,centerx+spanx/2)
        self.ax.set_ylim(centery-spany/2,centery+spany/2)

        self.ax.set_aspect('equal')

        if debug:
            logger.debug(f'{centerx=}, {centery=}')
            logger.debug(f'{self.ax.get_xlim()=}')
            logger.debug(f'{self.ax.get_ylim()=}')


#********************************************************************************
#********************************************************************************
# PRETTY/SIMPLIFIED WRAPPERS ****************************************************
#********************************************************************************
#********************************************************************************
def prettynode(
        ax = None,
        mode = 'A',     # str in ['A','B','C','D','E'] 
        xy = (0,0),     # location
        loopangle = 0,  # self-loop angle
        sub  = '',      # None|str decorates the mode label above
        conj = False,   # conjugated?
        D = 1,          # node diameter (relative scaling)
        fontscale = 1,  # font sizing (relative scaling)
        plot = False,
        **kwargs
        ):      # any other PLOTNODE parameters

    """
    This just returns a dict that we feed to the GraphCircuit.addnode() method.
    plot = True will plot the node on a given axis for debugging.
    """    

    if ax is None and plot:
        _,ax = plt.subplots()
        ax.set_xlim(-10*D,10*D)
        ax.set_ylim(-10*D,10*D)

    elif ax is None and not plot:
        xylim = [10*D]
    else:
        xylim = abs(diff(plt.gca().get_xlim()))


    NODESCALING = dict(
        R = D/2,
        # nodelabelsize = fontscale * 28 / xylim[0] * 8 * figwidth * .3,  # legacy, not used anymore
        fontscale = fontscale  # Pass through to plotnode() for new auto-scaling
    )


    MODELABELS = ['A','B','C',
                  'D','E','F']
    MODECOLORS = [
        'indianred','cornflowerblue','darkseagreen',
        'sandybrown','cadetblue','mediumaquamarine'
        ]
    # MODELABELCOLORSCONJ = [
    #     'firebrick','cornflowerblue','darkseagreen',
    #     'orange','cadetblue','forestgreen'
    # ]

    # I'm on a plane and can't google how to get the index of 
    # a particular list item so doing this the ghetto way
    
    NODEPREFS = {}

    for idx,item in enumerate(MODELABELS):
        if mode == item:
            NODEPREFS['nodecolor'] = MODECOLORS[idx]
            NODEPREFS['nodecent'] = xy
            NODEPREFS['selfloopangle'] = loopangle

            if not conj:
                NODEPREFS['nodelabel'] = mode+sub
                NODEPREFS['nodeoutlinecolor'] = None
                NODEPREFS['selflooplabel'] = rf'$\Delta_{{{mode+sub}}}$'
            else:    
                NODEPREFS['nodelabel'] = mode+sub+'*'
                NODEPREFS['nodealpha'] = 0.3
                # NODEPREFS['nodeoutlinecolor'] = MODECOLORS[idx]
                NODEPREFS['nodeoutlinecolor'] = None
                NODEPREFS['nodelabelcolor'] = MODECOLORS[idx]
                # NODEPREFS['nodelabelnudge'] = (0.2,-0.1)
                NODEPREFS['selflooplabel'] = rf'$-\Delta_{{{mode+sub}}}^*$'
 
    if plot:
        plotnode(ax=ax,**NODEPREFS,**NODESCALING,**kwargs)
        ax.set_xlim(-xylim/2,xylim/2)
        ax.set_ylim(-xylim/2,xylim/2)
        plt.tight_layout()



    ALLNODEPREFS = {**NODEPREFS,**NODESCALING,**kwargs}

    return ALLNODEPREFS
    
def rotategraphcircuit(g,theta):
    """
    Rotate the graph circuit by a specified angle.
    """
    for node in g.nodes:
        node['nodecent'] = rotate2d(node['nodecent'],theta)
        if node['selfloopangle'] is not None:
            node['selfloopangle'] += theta

    for edge in g.edges:
        if 'labeltheta' in edge.keys():
            edge['labeltheta'] += theta


def rotate2d(v,theta):
    """
    Rotate a 2D vector by a specified angle.
    """
    x,y = v
    xnew = x*cos(pi/180*theta) - y*sin(pi/180*theta)
    ynew = x*sin(pi/180*theta) + y*cos(pi/180*theta)

    return (xnew,ynew)

def xycoordsOnCircle(n,R,theta0=0):
    """
    Generate n xy coordinates on a circle of radius R.
    """
    thetas = linspace(theta0,theta0+360,n,endpoint=False)

    return [(R*cos(pi/180*th),R*sin(pi/180*th)) for th in thetas], thetas


def shiftxygraphcircuit(g,xy = (1,0)):
    """Shifts the placement of a graph. Helpful when cobbling different graphs.

    Args:
        g (GraphCircuit)
        xy (tuple, optional): Delta xy tuple (dx,dy). Defaults to (1,0).
    """
    for node in g.nodes:
        node['nodecent'] = (node['nodecent'][0] + xy[0], node['nodecent'][1] + xy[1])

    return g


def fliplrgraphcircuit(g):
    """Flips the graph across the y-axis (i.e., left-right swap)

    Args:
        g (GraphCircuit)
    """

    for node in g.nodes:
        node['nodecent'] = (-node['nodecent'][0],node['nodecent'][1])
        node['selfloopangle'] = -node['selfloopangle'] + 180

    for edge in g.edges:
        # edge['labeltheta'] = -edge['labeltheta'] + 180
        edge['labeltheta'] = -edge['labeltheta']

def flipudgraphcircuit(g):
    """Flips the graph across the x-axis (i.e., up-down swap)

    Args:
        g (GraphCircuit)
    """

    for node in g.nodes:
        node['nodecent'] = (node['nodecent'][0],-node['nodecent'][1])
        node['selfloopangle'] = -node['selfloopangle']

    for edge in g.edges:
        # edge['labeltheta'] = -edge['labeltheta'] + 180
        edge['labeltheta'] = -edge['labeltheta']