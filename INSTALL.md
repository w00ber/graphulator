# Graphulator Installation Guide

## Package Structure

The package has been successfully created at:
```
/Users/joe/WORKWORKWORK.nosync/PROGRAMMING/PYTHON/my_packages/graphulator
```

## Installation Steps

### 1. Install in Development Mode (Recommended for Testing)

From the package directory:
```bash
cd /Users/joe/WORKWORKWORK.nosync/PROGRAMMING/PYTHON/my_packages/graphulator
pip install -e .
```

This installs the package in "editable" mode, so any changes to the source code will be immediately reflected.

### 2. Install with Development Dependencies (for Jupyter)

```bash
pip install -e ".[dev]"
```

### 3. Verify Installation

Test the command-line interface:
```bash
graphulator
```

Or using Python module:
```bash
python -m graphulator
```

Test the library import:
```python
python -c "import graphulator; print(graphulator.__version__)"
```

## Building Distribution Packages

### Build wheel and source distribution:

```bash
pip install build
python -m build
```

This creates files in `dist/`:
- `graphulator-0.1.0-py3-none-any.whl` (wheel)
- `graphulator-0.1.0.tar.gz` (source)

### Install from wheel:

```bash
pip install dist/graphulator-0.1.0-py3-none-any.whl
```

## Publishing to PyPI

### 1. Install twine:
```bash
pip install twine
```

### 2. Test on TestPyPI (optional):
```bash
python -m twine upload --repository testpypi dist/*
```

### 3. Upload to PyPI:
```bash
python -m twine upload dist/*
```

You'll need PyPI credentials. Create an account at https://pypi.org/

## Usage

### Launch GUI
```bash
graphulator
```

### Access Examples
In the GUI: **File → Examples** to load:
- bowtie
- circulator
- FC_AB

### Run Tutorial Notebook
```bash
jupyter notebook examples/notebooks/graphulator_tutorial.ipynb
```

### Programmatic Usage
```python
import matplotlib.pyplot as plt
import graphulator.graph_primitives as gp
import graphulator.graphulator_config as config

graph = gp.GraphCircuit()
graph.addnode(label='A', xy=(0, 0), nodecolor=config.MYCOLORS['RED'])
graph.draw(figsize=8)
plt.show()
```

## Troubleshooting

### Import errors
If you get import errors, ensure you're in the correct Python environment and have installed all dependencies:
```bash
pip install PySide6 matplotlib numpy
```

### Examples not loading
The examples are packaged as resources. If they don't load, check:
```python
from importlib import resources
examples = resources.files('graphulator').joinpath('examples/graphs')
print(list(examples.iterdir()))
```

### Command not found
If `graphulator` command isn't found, ensure pip's bin directory is in your PATH:
```bash
python -m graphulator  # Alternative way to run
```

## Uninstalling

```bash
pip uninstall graphulator
```

## Next Steps

1. Test the installation
2. Try the example graphs
3. Run the tutorial notebook
4. Customize and extend as needed
5. (Optional) Publish to PyPI

For more information, see README.md
