# Graphulator & Paragraphulator
[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Graphulator** is an interactive graph drawing tool designed for creating coupled mode theory diagrams and quantum circuit visualizations. Built with PySide6 and matplotlib, it provides both a powerful GUI application and a flexible Python library for programmatic graph creation.

**Paragraphulator** is an interactive graph calculation tool, specifically for computing scattering in parametric coupled mode systems. It is derived from `Graphulator` but uses a simplified graph language for setting up the calculations.

## Graphulator Features

### Interactive GUI
- **Visual graph editor** with click-to-place nodes and edges
- **Real-time rendering** with matplotlib backend
- **Multiple edge styles**: loopy (curved), single, and double arrows
- **Self-loop support** with customizable angles and labels
- **Node customization**: colors, sizes, labels, and conjugation markers
- **Edge label positioning** with rotation and offset controls
- **Zoom and pan** with mouse wheel and arrow keys
- **Export to PDF/SVG** with scaling presets
- **Save/load graphs** in JSON format
- **Example graphs** included (bowtie, circulator, frequency converters)

### Graph Primitives Library
- **Programmatic graph creation** using `graph_primitives` module
- **LaTeX/MathText support** for mathematical labels
- **Automatic layout** and proportional scaling
- **Customizable styling** for nodes, edges, and labels
- **Jupyter notebook integration**

### Keyboard Shortcuts
- **Node placement**: `g` (single), `Shift+G` (continuous), `Ctrl+G` (auto-increment)
- **Edge creation**: `e` (single), `Ctrl+E` (continuous)
- **Selection**: Click to select, `Shift+Click` for multi-select, `Ctrl+A` for select all
- **Editing**: Arrow keys for pan, `Shift+Arrow` for label nudge, `Ctrl+Arrow` for parameter adjustment
- **File operations**: `Ctrl+N` (new), `Ctrl+O` (open), `Ctrl+S` (save)
- **View**: `a` (auto-fit), `+/-` (zoom), `r` (rotate grid)

## Installation

### From PyPI (when published)
```bash
pip install graphulator
```

### From Source
```bash
git clone https://gitlab.nist.gov/gitlab/aumentad/graphulator.git
cd graphulator
pip install -e .
```

### Development Installation
```bash
pip install -e ".[dev]"
```

## Quick Start

### Launch the GUI
```bash
graphulator
```

Or using Python:
```bash
python -m graphulator
```

### Programmatic Usage

Create a simple graph:

```python
import matplotlib.pyplot as plt
import graphulator.graph_primitives as gp
import graphulator.graphulator_config as config

# Create a graph circuit
graph = gp.GraphCircuit()

# Add nodes
graph.addnode(label='A', xy=(-5, 0), nodecolor=config.MYCOLORS['RED'])
graph.addnode(label='B', xy=(5, 0), nodecolor=config.MYCOLORS['BLUE'])

# Add edge
graph.addedge(fromnode='A', tonode='B',
              label=[r'$\\beta_{BA}$', r'$\\beta_{AB}$'],
              style='loopy')

# Draw
graph.draw(figsize=8, overfrac=0.2)
plt.axis('off')
plt.show()
```

Add self-loops:

```python
graph.addnode(label='A', xy=(0, 0),
              drawselfloop=True,
              selflooplabel=r'$\\Delta_A$',
              selfloopangle=180)
```

### Jupyter Notebooks

See the [tutorial notebook](examples/notebooks/graphulator_tutorial.ipynb) for detailed examples:

```bash
jupyter notebook examples/notebooks/graphulator_tutorial.ipynb
```

## Examples

Graphulator includes several example graphs accessible via the GUI's **File → Examples** menu:

- **bowtie**: Bowtie coupling configuration
- **circulator**: Three-port circulator
- **FC_AB**: Frequency converter circuit

## Edge Styles

- **loopy**: Curved bidirectional edges (default)
- **single**: Single straight arrow
- **double**: Double straight arrows

## Node Colors

Available colors from `graphulator_config.MYCOLORS`:
- RED, BLUE, GREEN, ORANGE, PURPLE, CYAN, YELLOW, PINK, TEAL

## Export Options

### From GUI
1. **File → Export Code** (`Ctrl+Shift+E`): Generate Python code
2. **Export → PDF/SVG**: Export to publication-quality graphics
3. Adjust scaling via **Export Scaling** tab

### From Code
```python
graph.draw(figsize=12, overfrac=0.2)
plt.savefig('output.pdf', bbox_inches='tight')
plt.savefig('output.svg', bbox_inches='tight')
```

## Configuration

Customize default settings in `graphulator_config.py`:
- Node colors and sizes
- Edge styles and linewidths
- Label font sizes
- Grid spacing and rotation angles

## Requirements

- Python ≥ 3.9
- PySide6 ≥ 6.4.0
- matplotlib ≥ 3.6.0
- numpy ≥ 1.23.0

## Documentation

### Graph Primitives API

#### GraphCircuit
- `addnode(label, xy, nodecolor, R, fontscale, ...)`: Add a node
- `addedge(fromnode, tonode, label, style, ...)`: Add an edge
- `draw(figsize, overfrac)`: Render the graph

#### Node Parameters
- `label`: Node label (LaTeX supported)
- `xy`: Position (x, y) tuple
- `nodecolor`: Color from config
- `R`: Node radius (default 2.0)
- `fontscale`: Label size multiplier
- `drawselfloop`: Enable self-loop
- `selflooplabel`: Self-loop label
- `selfloopangle`: Self-loop angle (0-360°)

#### Edge Parameters
- `fromnode`, `tonode`: Node labels or IDs
- `label`: [forward_label, backward_label]
- `style`: 'loopy', 'single', or 'double'
- `whichedges`: 'both', 'forward', or 'backward'
- `theta`: Curvature angle for loopy edges
- `labelfontsize`: Label font size


## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Citation

If you use Graphulator in your research, please cite:

```bibtex
@software{graphulator,
  author = {Aumentado, J.},
  title = {Graphulator: Interactive Graph Drawing Tool},
  year = {2026},
  url = {https://gitlab.nist.gov/gitlab/aumentad/graphulator}
}
```


## param


## Author

**J. Aumentado**
Email: jose.aumentado@nist.gov

## Acknowledgments

Developed for coupled mode theory visualization and quantum circuit diagram creation.

## Links

- **Documentation**: [GitHub README](https://gitlab.nist.gov/gitlab/aumentad/graphulator#readme)
- **Issues**: [GitHub Issues](https://gitlab.nist.gov/gitlab/aumentad/graphulator/issues)
- **PyPI**: [graphulator](https://pypi.org/project/graphulator/) (when eventually published)
