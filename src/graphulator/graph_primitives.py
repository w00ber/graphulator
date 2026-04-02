'''
GRAPH PRIMITIVES LIBRARY
FEB2020, AUG2021
JAA

Library for drawing graphs. Build up the primitives (loops, arrows, bubbles).
'''
import matplotlib.path as mpath
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib import rcParams

from numpy import pi,cos,sin,angle,real,asarray,sqrt,arctan2,abs,diff,linspace

import os
import warnings

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
    # print(bz)

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
def looparrow(ax=None,
              vstartend=[[-1,0],[0,1]],
              R=[2,2],
              theta=[90+34,90-34],
              lw=3.0,
              arrowlength=0.4, # define as None to remove the arrow
              arrowthetatweak=0, # tweak the angle of the arrow. Useful with low loopiness.
              color='black',
              alpha=1.0,
              debug=False):
    '''
    Draw the whole loopy arrow.
    '''

    _,thetaarrow = drawloop(ax=ax,v=vstartend,R=R,theta=theta ,lw=lw,color=color,alpha=alpha,debug=debug)

    if arrowlength:
        arrowhead(ax=ax,v=vstartend[1],length=arrowlength,lw=lw*0.8,theta=thetaarrow+arrowthetatweak,openang=60,color=color,alpha=alpha,debug=debug)

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
    # print(v)

    if flip:
        theta = theta[::-1]
        v = v[::-1]

    looparrow(ax=ax,
              vstartend=v,
              theta=theta,
              arrowlength=arrowlength,
              lw=lw,
              R=[loopR,loopR],
              color=color,
              alpha=alpha,
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

    if nodealpha == None:
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

    # print(f'DEBUG:{drawselfloop=}')
    if drawselfloop is True:
        # Scale self-loop linewidth proportionally to node radius only
        # Use R=2.0 as reference (typical default node radius)
        reference_R = 2.0
        scaled_selflooplw = selflooplw * (R / reference_R)

        selfloop(ax=ax,R=R*1.2,loopR=R*LOOPYSCALE,
                    nodecent=nodecent,baseangle=selfloopangle,dtheta=-34,
                    color=selfloopcolor,arrowlength=R/2*2.25/4*arrowlengthsc,
                    flip=flipselfloop,
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
            print(f"FONT DEBUG: R={R:.2f}, points_per_data_unit={points_per_data_unit:.2f}, scaled_nodelabelsize={scaled_nodelabelsize:.2f}")

        # Format label with bold sans-serif, handling subscripts/superscripts
        # In LaTeX mode with sfmath, use \mathbf{...} (sfmath makes it sans-serif)
        # In MathText mode, use \mathbf{\mathsf{...}} explicitly
        import re

        # Choose font command based on rendering mode
        if use_latex:
            # LaTeX with sfmath: just use \mathbf (sfmath provides sans-serif)
            def apply_font(text):
                return r'\mathbf{' + text + '}'
        else:
            # MathText/STIX: use both \mathbf and \mathsf
            def apply_font(text):
                return r'\mathbf{\mathsf{' + text + '}}'

        # Split on _ and ^ while keeping the delimiters
        # This regex splits but keeps the _ and ^ characters
        parts = re.split(r'([_^])', nodelabel)

        formatted_parts = []
        i = 0
        while i < len(parts):
            if parts[i] in ['_', '^']:
                # This is a sub/superscript operator
                formatted_parts.append(parts[i])
                i += 1
                if i < len(parts):
                    # Next part is the sub/superscript content
                    # Apply font to the content
                    content = parts[i]
                    if content.startswith('{') and content.endswith('}'):
                        # Already has braces, apply font to inner content
                        inner = content[1:-1]
                        formatted_parts.append('{' + apply_font(inner) + '}')
                    else:
                        # Single character, wrap it
                        formatted_parts.append(apply_font(content))
                    i += 1
            elif parts[i]:  # Non-empty part
                # Regular text, apply font
                formatted_parts.append(apply_font(parts[i]))
                i += 1
            else:
                i += 1

        formatted_label = ''.join(formatted_parts)

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
            # print(f'{nodelabelsize=}')
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
    # # print(f'{figwidth=}')
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
        debug = False
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
                    **loopkwargs
                    )
        elif whichedges in ['backward','back']:
            looparrow(ax,
                    vstartend = voffsetendptsBACK,
                    R = [loopiness,loopiness],
                    theta = thetaoffsetanglesBACK,
                    **loopkwargs)

        elif whichedges in ['both','all']:
            looparrow(ax,
                    vstartend = voffsetendptsFORE,
                    R = [loopiness,loopiness],
                    theta = thetaoffsetanglesFORE,
                    **loopkwargs
                    )
            looparrow(ax,
                    vstartend = voffsetendptsBACK,
                    R = [loopiness,loopiness],
                    theta = thetaoffsetanglesBACK,
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
            # print('DEBUG: BUTTZ')
            singleloopkwargs['lw'] = 3.5*scaled_lw

        looparrow(ax,
                    vstartend = voffsetendpts,
                    R = [0,0], # single line so no loopiness
                    theta = thetaoffsetangles,
                    arrowlength = None, # no arrow
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
        looparrow(ax,
                vstartend = voffsetendpts,
                R = [0,0], # single line so no loopiness
                theta = thetaoffsetangles,
                arrowlength = None, # no arrow
                **doubleloopkwargs
                )            

        # draw the thin line ----------------------------------------------
        # modify the linewidth and change the color
        doubleloopkwargs['lw'] = doubleloopkwargs.pop('lw')*0.33
        doubleloopkwargs['color'] = 'white'
        
        # print(f'DEBUG: {doubleloopkwargs=}')
        voffsetendpts = [(n[0] + .98*RR * cos(pi/180*th), n[1] + .98*RR * sin(pi/180*th)) 
                            for n,RR,th in zip(nodexy,Rtot,thetaoffsetangles)]
        
        looparrow(ax,
                vstartend = voffsetendpts,
                R = [0,0], # single line so no loopiness
                theta = thetaoffsetangles,
                arrowlength = None, # no arrow
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

        # print(f'DEBUG: label = {label} vlength = {vlength} th = {th}')
        voffsetmid = (nodexy[0][0] + vlength/2 * cos(th), nodexy[0][1] + vlength/2 * sin(th))
        labelvecpos = (labeloffset * cos(th+pi/2),labeloffset * sin(th+pi/2))
        labelvecneg = (labeloffset * cos(th-pi/2),labeloffset * sin(th-pi/2))

        # forward label
        if label[0] is not None:
            labelvecpos = [voffsetmid[0] + labelvecpos[0],voffsetmid[1] + labelvecpos[1]]
            bbox_props_0 = None
            if labelbgcolor[0] is not None:
                bbox_props_0 = dict(boxstyle='round,pad=0.1', facecolor=labelbgcolor[0], edgecolor='none', alpha=1.0)
            ax.annotate(label[0],xy=labelvecpos,
                        ha='center',va='center',
                        fontsize=scaled_labelfontsize,color=labelcolor,rotation=labeltheta,bbox=bbox_props_0)
        if label[1] is not None:
            labelvecneg = [voffsetmid[0] + labelvecneg[0],voffsetmid[1] + labelvecneg[1]]
            bbox_props_1 = None
            if labelbgcolor[1] is not None:
                bbox_props_1 = dict(boxstyle='round,pad=0.1', facecolor=labelbgcolor[1], edgecolor='none', alpha=1.0)
            ax.annotate(label[1],xy=labelvecneg,
                        ha='center',va='center',
                        fontsize=scaled_labelfontsize,color=labelcolor,rotation=labeltheta,bbox=bbox_props_1)


    if debug:
        for nodecent,nR in zip(nodexy,nodeR):
            print(f'DEBUG:EDGE():{nodecent=},{nR=}')
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

            # print(f'DEBUG: selflooplabel = {nodedict["selflooplabel"]}')
    
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
                error_msg = f"Ambiguous node labels detected:\n"
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
            # print(f'DEBUG: nodelabel = {node["nodelabel"]}')  
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
                    print('Node removed.')

        # still need to audit the edge list to remove any edges that connect to this node
        # removeedge(self, nodelist = [])

        self.nodes = nodelist_tmp
        

    def removeedge(self, nodelist):
        # do we just remove edges connecting to a particular node? or do we remove particular edges that connect two particular nodes?
        # NOT QUITE CORRECT self.edges = [edge for edge in self.edges if edge['startend'] != edge['startend']]
        # Scan through the edge list and remove any edges that connect to any of the nodes in the list
        pass

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
            _, self.ax = plt.subplots(figsize=(figsize,figsize));
            # Set the x and y limits of the axes
            # self.ax.set_xlim(-xylim/2,xylim/2);self.ax.set_ylim(-xylim/2,xylim/2)
            # print(f'DEBUG: {self.ax.get_xlim()=}')
            # self._setminmaxnodecoords(overfrac=overfrac,debug=debug)
            self._axisequalizer(overfrac=overfrac,debug=debug)
            # print(f'DEBUG (after _setminmaxnodecoords()): {self.ax.get_xlim()=}')
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
                print(f'DEBUG: {ed=}')
                print(f'DEBUG: edge from {ed["fromnode"]} to {ed["tonode"]}')

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
            print(f'{idx}: {node["nodelabel"]}: {node["nodecent"]};\t\tconj = {node["conj"]}')

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
            print(f'DEBUG: {self.nodes=}')


        if len(self.nodes) > 1: 
            # Get the minimum and maximum x and y coordinates of the nodes
            minx = min([node['nodecent'][0] for node in self.nodes])
            maxx = max([node['nodecent'][0] for node in self.nodes])
            miny = min([node['nodecent'][1] for node in self.nodes])
            maxy = max([node['nodecent'][1] for node in self.nodes])

            # # Print the minimum and maximum coordinates of the nodes
            # print(f'DEBUG: minx={minx}, maxx={maxx}, miny={miny}, maxy={maxy}')

            # Set the x and y limits of the axes
            dx = (maxx - minx) * overfrac/2
            dy = (maxy - miny) * overfrac/2
            # self.ax.set_xlim(minx-dx,maxx+dx)
            # self.ax.set_ylim(miny-dy,maxy+dy)

            span  = max(dx,dy,*[2*node['R'] for node in self.nodes])
            self.ax.set_xlim(minx-span/2,maxx+span/2)
            self.ax.set_ylim(miny-span/2,maxy+span/2)

            # print(f'DEBUG: {span=}')
            # print(f'DEBUG: {self.ax.get_xlim()=}')
            # print(f'DEBUG: {self.ax.get_ylim()=}')

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

        maxx = max([node['nodecent'][0] for node in self.nodes])
        minx = min([node['nodecent'][0] for node in self.nodes])
        maxy = max([node['nodecent'][1] for node in self.nodes])
        miny = min([node['nodecent'][1] for node in self.nodes])

        maxnodeR = max([node['R'] for node in self.nodes])

        # print(f'DEBUG: {maxx=},{minx=},{maxy=},{miny=}')
        # print(f'DEBUG: {maxnodeR=}')

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

        # print(f'DEBUG: {betteroverscalefrac=}')
        # print(f'DEBUG: {spanx=},{spany=}')

        self.ax.set_xlim(centerx-spanx/2,centerx+spanx/2)
        self.ax.set_ylim(centery-spany/2,centery+spany/2)

        self.ax.set_aspect('equal')

        if debug:
            print(f'DEBUGGGG: {centerx=},{centery=}')
            print(f'DEBUGGGG: {self.ax.get_xlim()=}')
            print(f'DEBUGGGG: {self.ax.get_ylim()=}')


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

    if ax == None and plot == True:
        _,ax = plt.subplots()
        ax.set_xlim(-10*D,10*D);ax.set_ylim(-10*D,10*D)

    elif ax == None and plot == False:
        figwidth = 6
        xylim = [10*D]
    else:
        figwidth = plt.gcf().get_figwidth()
        xylim = abs(diff(plt.gca().get_xlim()))

    # print(f"DEBUG: {plt.gca().get_xlim()}")

    NODESCALING = dict(
        R = D/2,
        # nodelabelsize = fontscale * 28 / xylim[0] * 8 * figwidth * .3,  # legacy, not used anymore
        fontscale = fontscale  # Pass through to plotnode() for new auto-scaling
    )

    # print(f"DEBUG: {NODESCALING['nodelabelsize']=}")

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
        ax.set_xlim(-xylim/2,xylim/2);ax.set_ylim(-xylim/2,xylim/2)
        plt.tight_layout()


    # print(f'DEBUG: {kwargs=}')

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