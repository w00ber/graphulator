# Graphulator Quick Start Guide

## Installation

```bash
cd <package_path>/graphulator
pip install -e .
```

## Launch

```bash
graphulator
```

## Basic Usage

### 1. Create Nodes
- Press `g` to enter node placement mode
- Click to place a node
- Edit label, color, and size in the properties panel

### 2. Create Edges
- Press `e` to enter edge mode
- Click first node, then second node
- Configure edge style, labels, and direction in the dialog

### 3. Add Self-Loops
- Select a node
- In properties panel: enable "Draw Self-Loop"
- Adjust angle and scale as needed

### 4. Navigate
- **Zoom**: Mouse wheel or `+`/`-` keys
- **Pan**: Arrow keys (or drag with mouse)
- **Auto-fit**: Press `a` to fit all nodes in view

### 5. Save/Load
- **Save**: `Ctrl+S` or File → Save
- **Load**: `Ctrl+O` or File → Open
- **Examples**: File → Examples → bowtie/circulator/FC_AB

### 6. Export
- **Code**: `Ctrl+Shift+E` (generates Python code)
- **Graphics**: Right-click → Export to PDF/SVG

## Keyboard Shortcuts

### Modes
- `g` - Place single node
- `Shift+G` - Continuous node placement
- `Ctrl+G` - Auto-increment node labels
- `e` - Place single edge
- `Ctrl+E` - Continuous edge placement
- `Esc` - Exit mode / Clear selection

### View
- `a` - Auto-fit view
- `+/-` - Zoom in/out
- `Arrow keys` - Pan view
- `r` - Rotate grid
- `t` - Toggle grid type

### Editing (with selection)
- `Arrow keys` - Pan view OR adjust node/edge properties
- `Shift+Arrow` - Nudge labels
- `Ctrl+Arrow` - Adjust self-loop parameters / edge theta

### Selection
- Click - Select
- `Shift+Click` - Multi-select
- `Ctrl+A` - Select all
- `Esc` - Clear selection

### File Operations
- `Ctrl+N` - New graph
- `Ctrl+O` - Open
- `Ctrl+S` - Save
- `Ctrl+Shift+S` - Save As
- `Ctrl+Shift+E` - Export code
- `Ctrl+L` - Toggle LaTeX rendering

### Clipboard
- `Ctrl+C` - Copy
- `Ctrl+X` - Cut
- `Ctrl+V` - Paste
- `Ctrl+Z` - Undo
- `d` or `Delete` - Delete selection

## Python API Quick Reference

```python
import matplotlib.pyplot as plt
import graphulator.graph_primitives as gp
import graphulator.graphulator_config as config

# Create graph
graph = gp.GraphCircuit()

# Add nodes
graph.addnode(label='A', xy=(-5, 0),
              nodecolor=config.MYCOLORS['RED'],
              R=2.0,           # radius
              fontscale=1.0,   # label size
              drawselfloop=True,
              selflooplabel=r'$\Delta_A$',
              selfloopangle=180)

# Add edges
graph.addedge(fromnode='A', tonode='B',
              label=[r'$\beta_{BA}$', r'$\beta_{AB}$'],
              style='loopy',      # 'loopy', 'single', 'double'
              whichedges='both',  # 'both', 'forward', 'backward'
              theta=30)           # curvature angle

# Draw
graph.draw(figsize=8, overfrac=0.2)
plt.axis('off')
plt.savefig('graph.pdf', bbox_inches='tight')
plt.show()
```

## Common Tasks

### Create Triangle Graph
```python
graph = gp.GraphCircuit()
graph.addnode(label='A', xy=(-5, 0), nodecolor=config.MYCOLORS['RED'])
graph.addnode(label='B', xy=(5, 0), nodecolor=config.MYCOLORS['BLUE'])
graph.addnode(label='C', xy=(0, -7), nodecolor=config.MYCOLORS['GREEN'])
graph.addedge(fromnode='A', tonode='B', style='loopy')
graph.addedge(fromnode='B', tonode='C', style='loopy')
graph.addedge(fromnode='C', tonode='A', style='loopy')
graph.draw(figsize=8)
plt.show()
```

### Customize Node
- Double-click node to edit
- Or use properties panel (right side)
- Adjust: size, label, color, self-loop

### Adjust Edge
- Double-click edge to edit
- Or use properties panel when edge selected
- Adjust: style, labels, linewidth, theta

### Export Options
1. **PDF/SVG**: Right-click canvas → Export
2. **Python Code**: `Ctrl+Shift+E`
3. **Programmatic**: `plt.savefig('out.pdf')`

## Tips

- Use **grid** for alignment (show with UI checkbox)
- Use **Shift+G** for quickly placing multiple nodes
- Use **Ctrl+Arrow** to fine-tune self-loop angles
- Use **Shift+Arrow** to nudge labels into position
- Use **Auto-increment mode** (`Ctrl+G`) for sequential labels
- Check **Examples** menu for inspiration

## Troubleshooting

**GUI won't launch**: Check installation with `python -c "import graphulator"`

**Examples not showing**: Reinstall with `pip install -e .`

**Import errors**: Install dependencies: `pip install PySide6 matplotlib numpy`

**Command not found**: Use `python -m graphulator` instead

## Learn More

- **README.md**: Full documentation
- **Tutorial**: `jupyter notebook examples/notebooks/graphulator_tutorial.ipynb`
- **Examples**: File → Examples in GUI

---

**Happy Graphing!** 📊
