# Graphulator & Paragraphulator
[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

This repository contains two related projects: **Graphulator** and **Paragraphulator**. These are both built to facilitate drawing and computing scattering using generalized coupled mode graphs. The theory is largely described in 
- L. Ranzani and J. Aumentado, New Journal of Physics 17, 023024 (2015)
- F. Lecocq et al., Physical Review Applied 7 (2017)
- G. Aaron Peterson, Ph.D. thesis, University of Colorado, Boulder (2020)
- O. Naaman and J. Aumentado, PRX Quantum 3 (2022)

It is closely related to coupling matrix synthesis techniques in microwave filter design, but perhaps more generalized to generic coupled mode systems. The intent of these tools is to expedite the process of drawing and computing scattering in these systems, which can be quite tedious to do by hand, especially for larger graphs. It also provides a more consistent way to draw these graphs that allows one to focus on the structure of a graph rather than the details of how to draw a nice looking self-loop or pick a color or font or whatever. Likewise, the tedium (and requisite bughunting) surrounding coding scattering calculations for every new graph idea has been eliminated. 

It's important to note that, despite the author's affiliation with NIST, this project is a personal project, leveraging AI heavily, especially for the otherwise-maddening task of writing GUI code. It's also important to state that this was largely written during November 2025, which many of you might remember as another Month That the US Government Shut Down, so you know, I had a lot of free time on my hands to catch up on projects like these. It's unclear how much more I'll push on this, but I wanted to get it to a point where it was usable and could be shared with others who might find it useful. If you find it useful at all, please drop me a note! If you find that it's yielding incorrect results, please let me know that too! I have tested it against a number of known graphs and it seems to be working correctly, but it's entirely possible that there are still bugs lurking in there somewhere. For what it's worth, to kick the tires a bit, I ran every important graph in my career so far, and setting up the same graphs and calculations for ALL OF THEM took something like 20 minutes. 

***NOTE from the author:*** This is very much a work in progress and there are a lot of things to still polish, including proper documentation, especially example notebooks. The workflow is *HEAVILY KEYBOARD SHORTCUT DRIVEN* because we (well I) want to draw graphs as quickly as possible.

---

## Graphulator

**Graphulator** is an interactive graph drawing tool designed for creating coupled mode theory diagrams and quantum circuit visualizations. Built with PySide6 and matplotlib, it provides both a powerful GUI application and a flexible Python library for programmatic graph creation.

### Features

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

- **Node placement**: `G` (single), `Shift+G` (continuous), `Ctrl+G` (auto-increment)
- **Edge creation**: `E` (single), `Ctrl+E` (continuous)
- **Selection**: Click to select, `Shift+Click` for multi-select, `Ctrl+A` for select all
- **Editing**: Arrow keys for pan, `Shift+Arrow` for label nudge, `Ctrl+Arrow` for parameter adjustment
- **File operations**: `Ctrl+N` (new), `Ctrl+O` (open), `Ctrl+S` (save)
- **View**: `A` (auto-fit), `+/-` (zoom), `R` (rotate grid)

---

## Paragraphulator

**Paragraphulator** is an interactive graph calculation tool for computing scattering in parametric coupled mode systems. It uses a simplified graph language for rapid setup of scattering calculations, with live symbolic matrix generation and S-parameter visualization. Paragraphulator evolved out of Graphulator, but stripped down the graph styling (following O. Naaman and J. Aumentado, PRX Quantum 3 (2022)) to focus on the graph structure and calculating scattering from it. It is intended to be a more focused tool for quickly setting up and analyzing scattering calculations, while Graphulator remains a more tool for drawing nice-looking graphs for presentations and papers.

### Symbolic Math Engine

- **Automatic equation-of-motion matrix generation** from graph topology using SymPy
- **Live matrix preview** rendered with KaTeX in a web-based viewer
- **Matrix zoom and pan** (`Ctrl+Plus/Minus`, `Alt+Arrow`)
- **Copy LaTeX** of the full matrix to clipboard (`Ctrl+Shift+L`)
- **Export SymPy code** to clipboard for use in Jupyter notebooks (`Alt+E`)
- **Custom LaTeX printer** with magnitude-squared notation, conjugate asterisks, and Greek letter support (overriding a lot of annoying/ugly SymPy defaults-- like you, know, overbars for conjugation instead of asterisks, etc.)

### Basis Ordering & Kron Reduction

- **Basis ordering mode** (`Ctrl+B`): click nodes in desired sequence to reorder the system matrix
- **Kron reduction** (`Ctrl+K`): select nodes to keep and compute the Schur complement, reducing the system to a smaller effective model
- **Undo/redo** for basis and Kron selections

### Scattering Parameter Analysis

- **Scattering mode** (`Ctrl+R`): assign physical parameters to nodes and edges
- **Per-node parameters**: resonator frequency, internal dissipation, external coupling
- **Per-edge parameters**: pump frequency, coupling rate, pump phase
- **Constraint groups**: link parameters across nodes/edges so they change together (right-click any spinbox)
- **Frequency sweep configuration**: center frequency, span, and number of points
- **Live S-parameter plots** (`Ctrl+Shift+R`) with:
  - Individual S-parameter toggles
  - Magnitude, phase, and dB display modes
  - Auto-scaling with manual override
  - Real-time updates as parameters change
- **Fine control on all spinboxes**: `Shift` for 1/10 step, `Alt` for 10x step

### Markdown Notes

- **Built-in notes editor** with live preview, saved with the graph file
- **LaTeX math support**: inline (`$...$`) and display (`$$...$$`) math rendered in the preview
- **Edit/Preview subtabs** with line numbers and monospace font

### Graph Construction & Editing

- **Node placement modes**: single (`G`), continuous (`Shift+G`), auto-increment (`Ctrl+G`)
- **Edge placement modes**: single (`E`), continuous (`Ctrl+E`)
- **Self-loops** for port definition with adjustable scale and angle
- **Conjugated nodes** with visual distinction (transparent fill, double-line edges)
- **Copy/paste** (`Ctrl+C/V`) with smart label auto-increment, or raw paste (`Ctrl+Shift+V`)
- **Undo** (`Ctrl+Z`) for node/edge operations
- **Rotation** (`Ctrl+U/I`) and **flipping** (`F`, `Shift+F`) of selections
- **Grid modes**: square (45 degree increments) and triangular (30 degree), toggle with `T`

### Visualization & Export

- **Real-time matplotlib rendering** with smooth node/edge display
- **LaTeX toggle** (`Ctrl+L`): switch between fast MathText and publication-quality system LaTeX
- **Export to PNG, SVG, and PDF** with granular scaling controls for nodes, edges, labels, and self-loops
- **Export Python code** (`Ctrl+Shift+E`) for reproducing graphs programmatically

### Settings & Customization

- **Settings dialog** (`Ctrl+,`) with tabs for node defaults, edge defaults, self-loops, S-parameter plot styling, and export scaling
- **Customizable keyboard shortcuts** with full rebinding support
- **Persistent settings** stored in `~/.graphulator/settings.json`

### Example Library

- 25+ pre-built parametric graphs accessible via **File > Examples**
- Includes circulators, frequency converters, amplifier chains, filter designs, and more
- Quick-start templates for common coupled-mode topologies

---

## Installation

### From Source

```bash
git clone https://github.com/w00ber/graphulator.git
cd graphulator
pip install -e .
```

<!-- ### Development Installation

```bash
pip install -e ".[dev]"
``` -->

## Quick Start

### Launch the GUIs

```bash
graphulator       # graph drawing tool
paragraphulator   # parametric graph calculator
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

See the [tutorial notebook](examples/notebooks/graphulator_tutorial.ipynb) for detailed examples for drawing stuff, but this needs to get cleaned up.  Check out the [readme](examples/notebooks/README.md) in the notebooks directory explaining what a mess it currently is.

```bash
jupyter notebook examples/notebooks/graphulator_tutorial.ipynb
```

## Requirements

- Python >= 3.9
- PySide6 >= 6.4.0, < 6.9.0
- matplotlib >= 3.6.0
- numpy >= 1.23.0
- sympy >= 1.11.0
- seaborn >= 0.12.0

## Building Standalone Apps

Standalone macOS `.app` bundles and Windows `.exe` files can be built with PyInstaller. As with any PyInstaller project, it'll probably end up being huge. Sorry? Maybe just don't do it? Just start them from the command line with `graphulator` and `paragraphulator` otherwise. It's not that hard. 
See [building/README.md](building/README.md) for instructions.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Citation

If you use Graphulator or Paragraphulator in your research, please cite:

```bibtex
@software{graphulator,
  author = {Aumentado, J.},
  title = {Paragraphulator: an interactive graph drawing and scattering calculation tool for coupled mode theory},
  year = {2026},
  url = {https://github.com/w00ber/graphulator}
}
```

## Author

**J. Aumentado**
Email: jose.aumentado@gmail.com

## Links

- **Documentation**: [GitHub README](https://github.com/w00ber/graphulator#readme)
- **Issues**: [GitHub Issues](https://github.com/w00ber/graphulator/issues)
<!-- - **PyPI**: [graphulator](https://pypi.org/project/graphulator/) (when eventually published) -->
