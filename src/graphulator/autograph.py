"""
autograph.py

Automated graph analysis and scattering calculation module for Graphulator.
This module extracts numerical information from graph structures and performs
scattering parameter calculations independent of the GUI.

Author: Graphulator Development Team
"""

import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional, Any, Union
from more_itertools import collapse

def load_pgraph(filepath: Optional[Union[str, Path]] = None, use_dialog: bool = False) -> Dict[str, Any]:
    """
    Load a .pgraph file from disk.

    Parameters
    ----------
    filepath : Optional[Union[str, Path]], default=None
        Path to the .pgraph file to load. Can be a string or Path object.
        If None and use_dialog=False, raises ValueError.
        If None and use_dialog=True, opens a file dialog.
    use_dialog : bool, default=False
        If True, opens a file dialog for user to select the file.
        If filepath is also provided, the dialog is ignored.

    Returns
    -------
    Dict[str, Any]
        The loaded pgraph data structure containing:
        - nodes: List of node dictionaries
        - edges: List of edge dictionaries
        - scattering: Scattering data (if present)
        - metadata, view settings, etc.

    Raises
    ------
    ValueError
        If filepath is None and use_dialog is False
    FileNotFoundError
        If the specified file does not exist
    json.JSONDecodeError
        If the file is not valid JSON
    KeyError
        If the file is missing required pgraph structure

    Examples
    --------
    Load with explicit path:
    >>> data = load_pgraph("my_graph.pgraph")

    Load with dialog:
    >>> data = load_pgraph(use_dialog=True)

    Load with Path object:
    >>> from pathlib import Path
    >>> data = load_pgraph(Path("graphs/my_graph.pgraph"))
    """
    # Handle file dialog case
    if filepath is None and use_dialog:
        try:
            import tkinter as tk
            from tkinter import filedialog

            # Create hidden root window
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)

            # Open file dialog
            filepath = filedialog.askopenfilename(
                title="Select .pgraph file",
                filetypes=[
                    ("Parametric Graph files", "*.pgraph"),
                    ("All files", "*.*")
                ]
            )

            root.destroy()

            if not filepath:
                raise ValueError("No file selected in dialog")

        except ImportError:
            raise ImportError(
                "tkinter is required for file dialogs. "
                "Install it or provide filepath directly."
            )

    # Validate filepath
    if filepath is None:
        raise ValueError("Must provide filepath or set use_dialog=True")

    # Convert to Path object
    filepath = Path(filepath)

    # Check file exists
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    # Load JSON data
    with open(filepath, 'r') as f:
        data = json.load(f)

    # Validate basic pgraph structure
    if "nodes" not in data or "edges" not in data:
        raise KeyError(
            f"Invalid pgraph file: missing required 'nodes' or 'edges' keys. "
            f"Found keys: {list(data.keys())}"
        )

    # Add filepath to data for reference
    data['_source_file'] = str(filepath.absolute())

    print(f"Loaded pgraph: {filepath.name}")
    print(f"  Nodes: {len(data['nodes'])}")
    print(f"  Edges: {len(data['edges'])}")
    if 'scattering' in data:
        print(f"  Scattering data: ✓")
        print(f"    Tree edges: {len(data['scattering'].get('tree_edges', []))}")
        print(f"    Chord edges: {len(data['scattering'].get('chord_edges', []))}")
    else:
        print(f"  Scattering data: ✗")

    return data


def get_svg(data: Dict[str, Any], kron: bool = False) -> Optional[str]:
    """
    Extract embedded SVG string from pgraph data.

    Parameters
    ----------
    data : Dict[str, Any]
        The pgraph data structure (from load_pgraph or a loaded JSON dict).
    kron : bool, default=False
        If True, return the Kron-reduced graph SVG (if available).
        Otherwise, return the main graph SVG.

    Returns
    -------
    Optional[str]
        The SVG string if available, None otherwise.

    Examples
    --------
    >>> data = load_pgraph("my_graph.pgraph")
    >>> svg = get_svg(data)
    >>> if svg:
    ...     print(f"SVG has {len(svg)} characters")
    """
    if kron:
        return data.get("kron_svg")
    return data.get("svg")


def save_svg(data: Dict[str, Any], filepath: Union[str, Path], kron: bool = False) -> bool:
    """
    Save embedded SVG from pgraph data to a file.

    Parameters
    ----------
    data : Dict[str, Any]
        The pgraph data structure (from load_pgraph or a loaded JSON dict).
    filepath : Union[str, Path]
        Path where the SVG file will be saved.
    kron : bool, default=False
        If True, save the Kron-reduced graph SVG (if available).
        Otherwise, save the main graph SVG.

    Returns
    -------
    bool
        True if SVG was saved successfully, False otherwise.

    Examples
    --------
    >>> data = load_pgraph("my_graph.pgraph")
    >>> save_svg(data, "my_graph.svg")
    True
    """
    svg = get_svg(data, kron=kron)
    if svg is None:
        print(f"No {'Kron ' if kron else ''}SVG data found in pgraph")
        return False

    filepath = Path(filepath)
    if not filepath.suffix:
        filepath = filepath.with_suffix('.svg')

    with open(filepath, 'w') as f:
        f.write(svg)

    print(f"Saved SVG to {filepath}")
    return True


def display_svg(data: Dict[str, Any], kron: bool = False, width: Optional[int] = None):
    """
    Display embedded SVG from pgraph data in a Jupyter notebook.

    This function uses IPython.display.SVG for rendering in Jupyter environments.
    In non-Jupyter environments, it will print a message indicating no display
    is available and suggest using save_svg() instead.

    Parameters
    ----------
    data : Dict[str, Any]
        The pgraph data structure (from load_pgraph or a loaded JSON dict).
    kron : bool, default=False
        If True, display the Kron-reduced graph SVG (if available).
        Otherwise, display the main graph SVG.
    width : Optional[int], default=None
        Optional width in pixels for the displayed SVG.
        If None, uses the SVG's native size.

    Returns
    -------
    None
        Always returns None. The SVG is displayed as a side effect.

    Examples
    --------
    In Jupyter notebook:
    >>> data = load_pgraph("my_graph.pgraph")
    >>> display_svg(data)  # Displays the graph inline

    With custom width:
    >>> display_svg(data, width=600)

    Display Kron-reduced graph:
    >>> display_svg(data, kron=True)
    """
    svg = get_svg(data, kron=kron)
    if svg is None:
        print(f"No {'Kron ' if kron else ''}SVG data found in pgraph")
        return None

    try:
        from IPython.display import SVG, display, HTML
        import re

        if width is not None:
            # Remove existing width/height attributes and set new width
            # The viewBox will maintain aspect ratio automatically
            svg_modified = re.sub(r'\s*width="[^"]*"', '', svg)
            svg_modified = re.sub(r'\s*height="[^"]*"', '', svg_modified)
            svg_modified = re.sub(
                r'<svg\s',
                f'<svg width="{width}" ',
                svg_modified,
                count=1
            )
            display(HTML(svg_modified))
            return None
        else:
            svg_obj = SVG(data=svg)
            display(svg_obj)
            return None  # Don't return svg_obj - Jupyter would display it again

    except ImportError:
        print("IPython not available. Use save_svg() to save to a file instead.")
        print("  Example: save_svg(data, 'output.svg')")
        return None


def show_graph(filepath: Optional[Union[str, Path]] = None,
               use_dialog: bool = False,
               kron: bool = False,
               width: Optional[int] = None):
    """
    Convenience function to load and display a pgraph's SVG in one call.

    This combines load_pgraph() and display_svg() for quick visualization
    in Jupyter notebooks.

    Parameters
    ----------
    filepath : Optional[Union[str, Path]], default=None
        Path to the .pgraph file to load.
    use_dialog : bool, default=False
        If True, opens a file dialog for user to select the file.
    kron : bool, default=False
        If True, display the Kron-reduced graph SVG (if available).
    width : Optional[int], default=None
        Optional width in pixels for the displayed SVG.

    Returns
    -------
    Dict[str, Any]
        The loaded pgraph data (for further processing if needed).

    Examples
    --------
    Quick display in Jupyter:
    >>> data = show_graph("my_graph.pgraph")

    With file dialog:
    >>> data = show_graph(use_dialog=True)

    Show Kron-reduced version with custom width:
    >>> data = show_graph("my_graph.pgraph", kron=True, width=500)
    """
    data = load_pgraph(filepath, use_dialog=use_dialog)
    display_svg(data, kron=kron, width=width)
    return data


class GraphExtractor:
    """
    Extracts and processes graph structure and numerical parameters for
    scattering calculations.

    This class handles:
    - Extraction of node and edge data from graph dictionaries
    - Spanning tree computation via DFS
    - Conversion to numerical formats suitable for matrix calculations
    """

    def __init__(self):
        """Initialize the GraphExtractor."""
        self.graph_data = None
        self.accumulated_frequencies = None
        self.chord_frequencies = None
        self._needs_recompute = False  # Dirty flag for lazy recomputation
        self.sign_override = False  # Default: auto-compute f_p signs
        self._unique_labels = True  # Flag indicating if all node labels are unique
        self._duplicate_labels = {}  # Dict mapping duplicate labels to list of node_ids
        self.label_to_node_id = None  # Mapping from label to node_id (only if labels are unique)
        self.node_id_to_label = {}  # Mapping from node_id to label (always available)

    def extract_graph_data(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        scattering_assignments: Dict[int, Dict[str, float]],
        frequency_settings: Dict[str, float],
        basis_order: Optional[List[Dict[str, Any]]] = None,
        root_node_id: Optional[int] = None,
        precomputed_tree_edges: Optional[List[List[int]]] = None,
        precomputed_chord_edges: Optional[List[List[int]]] = None
    ) -> Dict[str, Any]:
        """
        Extract all graph structure and numerical parameters into a single dictionary.

        Parameters
        ----------
        nodes : List[Dict]
            List of node dictionaries from GUI (must contain 'node_id', 'label', 'pos')
        edges : List[Dict]
            List of edge dictionaries from GUI (must contain 'from_node_id', 'to_node_id')
        scattering_assignments : Dict[int, Dict[str, float]]
            Dictionary mapping Python object id() to parameter assignments.
            Note: These IDs need to be converted to node_id for storage.
        frequency_settings : Dict[str, float]
            Dictionary with keys: 'start', 'stop', 'points'
        basis_order : Optional[List[Dict]], default=None
            Ordered list of nodes defining the matrix basis. If None, uses nodes list.
        root_node_id : Optional[int], default=None
            Node ID to use as root for spanning tree. If None, uses first node in basis_order.
        precomputed_tree_edges : Optional[List[List[int]]], default=None
            Pre-computed tree edges as [[from_id, to_id], ...]. If provided, these will be used
            instead of computing a spanning tree. These will be converted to branch format.
        precomputed_chord_edges : Optional[List[List[int]]], default=None
            Pre-computed chord edges as [[from_id, to_id], ...]. If provided, these will be used
            instead of computing chords.

        Returns
        -------
        Dict[str, Any]
            Extracted graph data with structure:
            {
                'nodes': List of node dicts with node_id, label, pos, and scattering params
                'edges': List of edge dicts with from_node_id, to_node_id, and scattering params
                'tree_edges': List of branches, where each branch is a list of [from_id, to_id, f_p] edges
                'chord_edges': List of [from_id, to_id] edge keys (loop-closing)
                'frequency': Dict with 'start', 'stop', 'points'
                'basis_order': List of node_ids defining matrix ordering
                'root_node_id': The root node ID used for spanning tree
                'is_connected': Boolean indicating if graph is fully connected
            }

        Raises
        ------
        ValueError
            If root_node_id is specified but not found in nodes
        """
        # Use basis_order if provided, otherwise use nodes list
        if basis_order is None:
            basis_order = nodes

        # Create node_id to object id mapping for scattering assignment lookup
        # (This is needed because scattering_assignments keys are Python id() values)
        node_id_to_obj_id = {node['node_id']: id(node) for node in nodes}
        edge_id_to_obj_id = {
            (edge['from_node_id'], edge['to_node_id']): id(edge)
            for edge in edges
        }

        # Extract node data with scattering parameters
        extracted_nodes = []
        for node in nodes:
            node_id = node['node_id']
            obj_id = node_id_to_obj_id[node_id]

            node_data = {
                'node_id': node_id,
                'label': node.get('label', ''),
                'pos': node.get('pos', (0.0, 0.0)),
                'conj': node.get('conj', False),
                # Initialize all scattering parameters to None
                'freq': None,
                'B_int': None,
                'B_ext': None
            }

            # Assign scattering parameters if available
            if obj_id in scattering_assignments:
                params = scattering_assignments[obj_id]
                node_data['freq'] = params.get('freq', None)
                node_data['B_int'] = params.get('B_int', None)
                node_data['B_ext'] = params.get('B_ext', None)

            extracted_nodes.append(node_data)

        # Check for duplicate labels and create lookup dictionaries
        label_counts = {}
        self._duplicate_labels = {}

        for node in extracted_nodes:
            label = node['label']
            if label not in label_counts:
                label_counts[label] = []
            label_counts[label].append(node['node_id'])

        # Identify duplicates
        for label, node_ids in label_counts.items():
            if len(node_ids) > 1:
                self._duplicate_labels[label] = node_ids

        # Set unique labels flag
        self._unique_labels = len(self._duplicate_labels) == 0

        # Always create node_id_to_label mapping (always safe)
        self.node_id_to_label = {n['node_id']: n['label'] for n in extracted_nodes}

        # Only create label_to_node_id if labels are unique
        if self._unique_labels:
            self.label_to_node_id = {n['label']: n['node_id'] for n in extracted_nodes}
        else:
            self.label_to_node_id = None
            # Print warning about duplicate labels
            dup_labels_str = ', '.join(
                f"'{label}' (node_ids: {node_ids})"
                for label, node_ids in sorted(self._duplicate_labels.items())
            )
            print(f"⚠ Warning: Duplicate node labels detected: {dup_labels_str}")
            print("  label_to_node_id mapping will not be available.")

        # Determine root node - default to first port node (B_ext > 0) in basis order
        if root_node_id is None:
            if not basis_order:
                raise ValueError("Cannot determine root node: no nodes in graph")

            # Try to find first port node in basis order
            for node in basis_order:
                # Find corresponding extracted node data
                extracted = next((n for n in extracted_nodes if n['node_id'] == node['node_id']), None)
                if extracted and extracted['B_ext'] is not None and extracted['B_ext'] > 0:
                    root_node_id = node['node_id']
                    break

            # If no port node found, fall back to first node in basis order
            if root_node_id is None:
                root_node_id = basis_order[0]['node_id']

        # Validate root exists
        root_exists = any(node['node_id'] == root_node_id for node in nodes)
        if not root_exists:
            raise ValueError(f"Root node_id {root_node_id} not found in graph nodes")

        # Extract edge data with scattering parameters
        extracted_edges = []
        for edge in edges:
            from_id = edge['from_node_id']
            to_id = edge['to_node_id']
            edge_key = (from_id, to_id)
            obj_id = edge_id_to_obj_id.get(edge_key)

            edge_data = {
                'from_node_id': from_id,
                'to_node_id': to_id,
                'is_self_loop': edge.get('is_self_loop', False),
                # Initialize all scattering parameters to None
                'f_p': None,
                'rate': None,
                'phase': None
            }

            # Assign scattering parameters if available
            if obj_id and obj_id in scattering_assignments:
                params = scattering_assignments[obj_id]
                edge_data['f_p'] = params.get('f_p', None)
                edge_data['rate'] = params.get('rate', None)
                edge_data['phase'] = params.get('phase', None)

            extracted_edges.append(edge_data)

        # Use pre-computed tree/chord edges if provided, otherwise compute them
        if precomputed_tree_edges is not None and precomputed_chord_edges is not None:
            # Use pre-computed data - convert tree edges to branch format
            # root_node_id is guaranteed to be set by this point (checked above)
            assert root_node_id is not None, "root_node_id must be set"
            tree_edges = self._convert_to_branch_format(
                precomputed_tree_edges, nodes, root_node_id
            )
            chord_edges = precomputed_chord_edges
            # Check connectivity
            visited_nodes = set()
            for branch in tree_edges:
                for from_id, to_id in branch:
                    visited_nodes.add(from_id)
                    visited_nodes.add(to_id)
            is_connected = len(visited_nodes) == len(nodes)
        else:
            # Compute spanning tree and chord edges
            tree_edges, chord_edges, is_connected = self.compute_spanning_tree(
                nodes, edges, root_node_id
            )

        # Augment tree edges with f_p values: [from_id, to_id] -> [from_id, to_id, f_p]
        # tree_edges is now nested by branch, so we need to preserve that structure
        # Create edge lookup dictionary for quick access
        edge_lookup = {}
        for edge in extracted_edges:
            key = tuple(sorted([edge['from_node_id'], edge['to_node_id']]))
            edge_lookup[key] = edge

        # Add f_p to each tree edge, preserving branch grouping
        tree_edges_with_fp = []
        for branch in tree_edges:
            branch_with_fp = []
            for from_id, to_id in branch:
                edge_key = tuple(sorted([from_id, to_id]))
                edge = edge_lookup.get(edge_key)
                f_p = edge['f_p'] if edge else None
                branch_with_fp.append([from_id, to_id, f_p])
            tree_edges_with_fp.append(branch_with_fp)

        # Create basis order list (node_ids)
        basis_node_ids = [node['node_id'] for node in basis_order]

        # Assemble final data structure
        self.graph_data = {
            'nodes': extracted_nodes,
            'edges': extracted_edges,
            'tree_edges': tree_edges_with_fp,
            'chord_edges': chord_edges,
            'frequency': frequency_settings.copy(),
            'basis_order': basis_node_ids,
            'root_node_id': root_node_id,
            'is_connected': is_connected
        }

        # Automatically compute accumulated and chord frequencies
        self.accumulated_frequencies = self._compute_accumulated_frequencies()
        self.chord_frequencies = self._compute_chord_frequencies()
        self._assign_chord_frequencies_to_edges()
        self._needs_recompute = False  # Just computed, so not dirty

        return self.graph_data

    def extract_from_pgraph(
        self,
        pgraph_data: Dict[str, Any],
        root_node_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Extract graph data directly from a loaded .pgraph file.

        This is a convenience method that handles the conversion from the
        .pgraph file format (where scattering parameters are stored directly
        in node/edge dicts) to the format expected by extract_graph_data().

        Parameters
        ----------
        pgraph_data : Dict[str, Any]
            The loaded .pgraph data (e.g., from load_pgraph())
        root_node_id : Optional[int], default=None
            Node ID to use as root for spanning tree.
            If None, uses first node in the file.

        Returns
        -------
        Dict[str, Any]
            Extracted graph data (same format as extract_graph_data())

        Examples
        --------
        >>> pgraph = load_pgraph("my_graph.pgraph")
        >>> extractor = GraphExtractor()
        >>> data = extractor.extract_from_pgraph(pgraph)
        """
        nodes = pgraph_data['nodes']
        edges = pgraph_data['edges']

        # Convert scattering parameters from node/edge dicts to assignments dict
        # In .pgraph files, parameters are stored as node['freq'], edge['f_p'], etc.
        # We need to convert to scattering_assignments[id(node)] = {'freq': ...}
        scattering_assignments = {}

        # Build node assignments (parameters stored directly in node dicts)
        for node in nodes:
            # Always create entry, use None for missing parameters
            node_params = {
                'freq': node.get('freq', None),
                'B_int': node.get('B_int', None),
                'B_ext': node.get('B_ext', None)
            }
            scattering_assignments[id(node)] = node_params

        # Build edge assignments (parameters stored directly in edge dicts)
        for edge in edges:
            # Always create entry, use None for missing parameters
            edge_params = {
                'f_p': edge.get('f_p', None),
                'rate': edge.get('rate', None),
                'phase': edge.get('phase', None)
            }
            scattering_assignments[id(edge)] = edge_params

        # Get frequency settings and pre-computed tree/chord from scattering data
        precomputed_tree_edges = None
        precomputed_chord_edges = None

        if 'scattering' in pgraph_data:
            scattering = pgraph_data['scattering']
            frequency_settings = scattering.get('frequency', {'start': 0.0, 'stop': 10.0, 'points': 100})

            # Use pre-computed tree/chord if available
            if 'tree_edges' in scattering and 'chord_edges' in scattering:
                precomputed_tree_edges = scattering['tree_edges']
                precomputed_chord_edges = scattering['chord_edges']
        else:
            frequency_settings = {'start': 0.0, 'stop': 10.0, 'points': 100}

        # Call the main extraction method
        return self.extract_graph_data(
            nodes=nodes,
            edges=edges,
            scattering_assignments=scattering_assignments,
            frequency_settings=frequency_settings,
            basis_order=None,  # pgraph files don't store basis_order separately
            root_node_id=root_node_id,
            precomputed_tree_edges=precomputed_tree_edges,
            precomputed_chord_edges=precomputed_chord_edges
        )

    def _convert_to_branch_format(
        self,
        tree_edges: List[List[int]],
        nodes: List[Dict[str, Any]],
        root_node_id: int
    ) -> List[List[List[int]]]:
        """
        Convert flat list of tree edges to nested branch format.

        Parameters
        ----------
        tree_edges : List[List[int]]
            Flat list of tree edges as [[from_id, to_id], ...]
        nodes : List[Dict]
            List of node dictionaries
        root_node_id : int
            Root node ID for the tree

        Returns
        -------
        List[List[List[int]]]
            Tree edges organized into branches
        """
        # Build adjacency list from tree edges
        adjacency = {node['node_id']: [] for node in nodes}
        for from_id, to_id in tree_edges:
            adjacency[from_id].append(to_id)
            adjacency[to_id].append(from_id)

        # DFS to organize into branches
        visited = set()
        branches = []

        def dfs_branch(node_id, parent_id, current_branch):
            visited.add(node_id)

            # Find unvisited neighbors
            unvisited = [n for n in adjacency[node_id] if n not in visited]

            if len(unvisited) == 0:
                # Leaf - end current branch
                if current_branch:
                    branches.append(current_branch)
            elif len(unvisited) == 1:
                # Linear continuation
                next_id = unvisited[0]
                current_branch.append([node_id, next_id])
                dfs_branch(next_id, node_id, current_branch)
            else:
                # Branch point - finish current branch and start new ones
                if current_branch:
                    branches.append(current_branch)
                for next_id in unvisited:
                    new_branch = [[node_id, next_id]]
                    dfs_branch(next_id, node_id, new_branch)

        # Start DFS from root
        dfs_branch(root_node_id, None, [])

        return branches

    def compute_spanning_tree(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        root_node_id: int
    ) -> Tuple[List[List[List[int]]], List[List[int]], bool]:
        """
        Compute spanning tree using depth-first search from root node.

        This algorithm traverses the graph starting from the root node,
        marking edges as either tree edges (part of the spanning tree)
        or chord edges (closing loops). The result is a tree structure
        that connects all reachable nodes.

        Parameters
        ----------
        nodes : List[Dict]
            List of node dictionaries with 'node_id' keys
        edges : List[Dict]
            List of edge dictionaries with 'from_node_id', 'to_node_id' keys
        root_node_id : int
            The node_id to use as the root of the spanning tree

        Returns
        -------
        tree_edges : List[List[List[int]]]
            List of branches, where each branch is a list of [from_node_id, to_node_id] pairs.
            Branches are linear paths in the tree (no branching points within a branch).
            A new branch starts when a node has multiple unvisited neighbors.
        chord_edges : List[List[int]]
            List of [from_node_id, to_node_id] pairs that close loops
        is_connected : bool
            True if all nodes were reached from root (graph is connected)

        Notes
        -----
        - Self-loops are excluded from the spanning tree
        - For disconnected graphs, only the component containing the root
          will have tree edges assigned
        - Edge keys are normalized as [min_id, max_id] for undirected edges
        - Branches group edges into linear paths for easier iteration
        """
        # Create node_id to node mapping
        node_map = {node['node_id']: node for node in nodes}

        # Find root node
        root_node = node_map.get(root_node_id)
        if root_node is None:
            raise ValueError(f"Root node_id {root_node_id} not found")

        # Build adjacency information
        # edge_dict: Maps edge_key -> edge object
        # adjacency: Maps node_id -> set of (neighbor_id, edge_key) tuples
        edge_dict = {}
        adjacency = {node['node_id']: set() for node in nodes}

        for edge in edges:
            # Skip self-loops for spanning tree
            if edge.get('is_self_loop', False):
                continue

            from_id = edge['from_node_id']
            to_id = edge['to_node_id']

            # Create normalized edge key (undirected)
            edge_key = tuple(sorted([from_id, to_id]))
            edge_dict[edge_key] = edge

            # Add to adjacency (both directions for undirected graph)
            adjacency[from_id].add((to_id, edge_key))
            adjacency[to_id].add((from_id, edge_key))

        # DFS to build spanning tree, grouped by branches
        visited = set()
        tree_branches = []  # List of branches, each branch is a list of edges
        chord_edge_keys = []

        def dfs_branch(node_id, current_branch):
            """
            DFS traversal that groups edges into branches.
            A branch is a linear path from a node until it either:
            - Reaches a leaf (no unvisited neighbors)
            - Reaches a node with multiple unvisited neighbors (branch point)
            """
            visited.add(node_id)

            # Get all unvisited neighbors
            unvisited_neighbors = [
                (neighbor_id, edge_key)
                for neighbor_id, edge_key in adjacency[node_id]
                if neighbor_id not in visited
            ]

            # Mark chord edges (edges to already-visited nodes)
            for neighbor_id, edge_key in adjacency[node_id]:
                if neighbor_id in visited and edge_key not in chord_edge_keys:
                    # Check if this edge is not already in any branch
                    edge_in_tree = any(edge_key in branch for branch in tree_branches)
                    if not edge_in_tree and edge_key not in [e for edges in [current_branch] for e in edges]:
                        chord_edge_keys.append(edge_key)

            if len(unvisited_neighbors) == 0:
                # Leaf node - end of current branch
                if current_branch:
                    tree_branches.append(current_branch)
                return

            elif len(unvisited_neighbors) == 1:
                # Linear continuation - add to current branch
                neighbor_id, edge_key = unvisited_neighbors[0]
                current_branch.append(edge_key)
                dfs_branch(neighbor_id, current_branch)

            else:
                # Branch point - multiple unvisited neighbors
                # Finish current branch if it has edges
                if current_branch:
                    tree_branches.append(current_branch)

                # Start a new branch for each unvisited neighbor
                # BUT: check if still unvisited (might have been visited by previous neighbor's DFS)
                for neighbor_id, edge_key in unvisited_neighbors:
                    if neighbor_id not in visited:  # Re-check: might have been visited by earlier neighbor
                        new_branch = [edge_key]
                        dfs_branch(neighbor_id, new_branch)

        # Start DFS from root with empty branch
        dfs_branch(root_node_id, [])

        # Check if graph is fully connected
        is_connected = (len(visited) == len(nodes))

        if not is_connected:
            unreached = [node['node_id'] for node in nodes if node['node_id'] not in visited]
            print(f"Warning: Graph is disconnected. Unreached nodes: {unreached}")

        # Convert edge keys back to [from_id, to_id] lists, nested by branch
        tree_edges = [[list(key) for key in branch] for branch in tree_branches]
        chord_edges = [list(key) for key in chord_edge_keys]

        return tree_edges, chord_edges, is_connected

    def validate_scattering_assignments(self) -> Dict[str, List[str]]:
        """
        Check if all required scattering parameters are assigned.

        Returns
        -------
        Dict[str, List[str]]
            Dictionary with keys 'missing_nodes' and 'missing_edges',
            each containing lists of descriptive strings for incomplete assignments

        Raises
        ------
        RuntimeError
            If extract_graph_data() has not been called yet
        """
        if self.graph_data is None:
            raise RuntimeError("Must call extract_graph_data() before validation")

        missing = {
            'missing_nodes': [],
            'missing_edges': []
        }

        # Check nodes
        for node in self.graph_data['nodes']:
            node_id = node['node_id']
            label = node['label']
            required = ['freq', 'B_int']

            # Check if node has self-loop (requires B_ext)
            has_self_loop = any(
                edge['is_self_loop'] and
                (edge['from_node_id'] == node_id or edge['to_node_id'] == node_id)
                for edge in self.graph_data['edges']
            )
            if has_self_loop:
                required.append('B_ext')

            # Check for missing parameters (now checking for None values)
            missing_params = [p for p in required if node.get(p) is None]
            if missing_params:
                missing['missing_nodes'].append(
                    f"Node {label} (id={node_id}): missing {missing_params}"
                )

        # Check edges (only tree edges need f_p, all edges need rate and phase)
        # Extract just the (from_id, to_id) pairs from tree_edges (ignoring f_p value)
        # tree_edges is now nested by branch, so we need to flatten it first
        tree_edge_set = set(
            tuple(sorted([e[0], e[1]]))
            for branch in self.graph_data['tree_edges']
            for e in branch
        )

        for edge in self.graph_data['edges']:
            if edge.get('is_self_loop', False):
                continue  # Self-loops don't need edge parameters

            from_id = edge['from_node_id']
            to_id = edge['to_node_id']
            edge_key = tuple(sorted([from_id, to_id]))

            required = ['rate', 'phase']
            if edge_key in tree_edge_set:
                required.append('f_p')

            # Check for missing parameters (now checking for None values)
            missing_params = [p for p in required if edge.get(p) is None]
            if missing_params:
                missing['missing_edges'].append(
                    f"Edge {from_id}→{to_id}: missing {missing_params}"
                )

        return missing

    def get_assignment_summary(self) -> str:
        """
        Get a compact summary of parameter assignment completeness.

        Returns a formatted string showing:
        - Total nodes and how many are complete/incomplete
        - Total edges and how many are complete/incomplete
        - Specific missing parameters in compact form

        Returns
        -------
        str
            Multi-line formatted summary string

        Raises
        ------
        RuntimeError
            If extract_graph_data() or extract_from_pgraph() has not been called yet

        Examples
        --------
        >>> extractor = GraphExtractor()
        >>> extractor.extract_from_pgraph(pgraph_data, root_node_id=0)
        >>> print(extractor.get_assignment_summary())
        Parameter Assignment Summary
        ============================
        Nodes: 2/3 complete
        Edges: 1/3 complete

        Missing Parameters:
        ------------------
        Nodes:
          - Node a (id=0): missing ['freq', 'B_int']
        Edges:
          - Edge 0→1: missing ['rate', 'phase']
          - Edge 1→2: missing ['f_p', 'rate', 'phase']
        """
        if self.graph_data is None:
            raise RuntimeError("Must call extract_graph_data() or extract_from_pgraph() first")

        validation = self.validate_scattering_assignments()

        # Count total and incomplete
        total_nodes = len(self.graph_data['nodes'])
        incomplete_nodes = len(validation['missing_nodes'])
        complete_nodes = total_nodes - incomplete_nodes

        total_edges = len([e for e in self.graph_data['edges'] if not e.get('is_self_loop', False)])
        incomplete_edges = len(validation['missing_edges'])
        complete_edges = total_edges - incomplete_edges

        # Build summary
        lines = [
            "Parameter Assignment Summary",
            "============================",
            f"Nodes: {complete_nodes}/{total_nodes} complete",
            f"Edges: {complete_edges}/{total_edges} complete"
        ]

        # Add missing details if any
        if validation['missing_nodes'] or validation['missing_edges']:
            lines.append("")
            lines.append("Missing Parameters:")
            lines.append("------------------")

            if validation['missing_nodes']:
                lines.append("Nodes:")
                for msg in validation['missing_nodes']:
                    lines.append(f"  - {msg}")

            if validation['missing_edges']:
                if validation['missing_nodes']:
                    lines.append("")
                lines.append("Edges:")
                for msg in validation['missing_edges']:
                    lines.append(f"  - {msg}")
        else:
            lines.append("")
            lines.append("✓ All parameters assigned!")

        return "\n".join(lines)

    def _compute_accumulated_frequencies(self):
        """
        Compute accumulated pump frequency offset for each node in each branch.

        This is a private method called automatically during extraction and
        when parameters are modified.

        Returns
        -------
        accumulated_by_branch : List[List[Tuple[int, float]]]
            For each branch, a list of (node_id, accumulated_f_p) tuples
        """
        if self.graph_data is None:
            return []

        tree_edges = self.graph_data['tree_edges']

        # Build node lookup for frequency and conjugation state
        node_info = {
            node['node_id']: {
                'freq': node['freq'],
                'conj': node['conj']
            }
            for node in self.graph_data['nodes']
        }

        def _determine_fp_sign(from_id, to_id, f_p):
            """
            Determine the sign of f_p based on effective frequency change.

            Effective frequencies:
            - Unconjugated node with f₀: effective frequency = +f₀
            - Conjugated node with f₀: effective frequency = -f₀

            Sign is positive for upconversion, negative for downconversion.
            """
            if f_p is None:
                return 0.0

            from_info = node_info[from_id]
            to_info = node_info[to_id]

            # Compute effective frequencies
            eff_from = -from_info['freq'] if from_info['conj'] else +from_info['freq']
            eff_to = -to_info['freq'] if to_info['conj'] else +to_info['freq']

            # Upconversion (+f_p) or downconversion (-f_p)?
            if eff_to > eff_from:
                return +f_p  # Upconversion
            else:
                return -f_p  # Downconversion

        accumulated_by_branch = []

        # Track accumulated frequency for each node across all branches
        node_accumulated = {}

        for branch in tree_edges:
            if not branch:
                accumulated_by_branch.append([])
                continue

            # Start with the root node of this branch (from_id of first edge)
            branch_accumulation = []
            root_node = branch[0][0]

            # Check if this node was reached in a previous branch
            if root_node in node_accumulated:
                accumulated_f_p = node_accumulated[root_node]
            else:
                # First branch - this is the tree root
                accumulated_f_p = 0.0
                node_accumulated[root_node] = accumulated_f_p

            # Add root node with its accumulated offset
            branch_accumulation.append((root_node, round(accumulated_f_p, 12)))

            # Accumulate along the branch
            for from_id, to_id, f_p in branch:
                if self.sign_override:
                    # User provided signed f_p, use as-is
                    signed_f_p = f_p if f_p is not None else 0.0
                else:
                    # Automatically compute sign based on effective frequency
                    signed_f_p = _determine_fp_sign(from_id, to_id, f_p)

                accumulated_f_p += signed_f_p

                # Add the destination node with accumulated offset (rounded to 12 places)
                branch_accumulation.append((to_id, round(accumulated_f_p, 12)))

                # Store this node's accumulated frequency for future branches
                node_accumulated[to_id] = accumulated_f_p

            accumulated_by_branch.append(branch_accumulation)

        return accumulated_by_branch

    def _compute_chord_frequencies(self):
        """
        Compute pump frequencies for chord edges based on accumulated branch frequencies.

        This is a private method called automatically during extraction and
        when parameters are modified.

        Returns
        -------
        chord_frequencies : dict
            Dictionary mapping chord edge (from_id, to_id) to computed f_p
        """
        if self.graph_data is None or self.accumulated_frequencies is None:
            return {}

        # Build a lookup: node_id -> accumulated frequency
        node_to_freq = {}
        for branch_accum in self.accumulated_frequencies:
            for node_id, f_accum in branch_accum:
                if node_id not in node_to_freq:
                    node_to_freq[node_id] = []
                node_to_freq[node_id].append(f_accum)

        chord_frequencies = {}

        for chord_edge in self.graph_data['chord_edges']:
            from_id, to_id = chord_edge[0], chord_edge[1]

            # Get accumulated frequencies at both nodes
            from_freqs = node_to_freq.get(from_id, [0.0])
            to_freqs = node_to_freq.get(to_id, [0.0])

            # Use the first occurrence of each node
            from_f = from_freqs[0]
            to_f = to_freqs[0]

            # Chord frequency is the absolute difference (always positive)
            f_p_chord = round(abs(to_f - from_f), 12)

            chord_frequencies[(from_id, to_id)] = f_p_chord

        return chord_frequencies

    def _assign_chord_frequencies_to_edges(self):
        """
        Assign computed chord frequencies to the edges in graph_data.

        This updates the 'f_p' field for chord edges with the automatically
        computed values based on accumulated frequencies.
        """
        if self.graph_data is None or self.chord_frequencies is None:
            return

        # Update f_p for each chord edge
        for edge in self.graph_data['edges']:
            if edge.get('is_self_loop', False):
                continue

            from_id = edge['from_node_id']
            to_id = edge['to_node_id']
            edge_key = tuple(sorted([from_id, to_id]))

            # Check if this is a chord edge
            chord_key_forward = (from_id, to_id)
            chord_key_reverse = (to_id, from_id)

            if chord_key_forward in self.chord_frequencies:
                edge['f_p'] = self.chord_frequencies[chord_key_forward]
            elif chord_key_reverse in self.chord_frequencies:
                edge['f_p'] = self.chord_frequencies[chord_key_reverse]

    def _recompute_derived_quantities(self):
        """
        Recompute accumulated and chord frequencies if needed (dirty flag pattern).

        This method implements lazy recomputation - it only recalculates when
        the dirty flag is set, which happens when parameters are modified.
        """
        if not self._needs_recompute:
            return

        # Recompute accumulated frequencies
        self.accumulated_frequencies = self._compute_accumulated_frequencies()

        # Recompute chord frequencies
        self.chord_frequencies = self._compute_chord_frequencies()

        # Update chord edges in graph_data
        self._assign_chord_frequencies_to_edges()

        # Clear dirty flag
        self._needs_recompute = False

    def get_accumulated_frequencies(self):
        """
        Get accumulated pump frequencies for each branch.

        Automatically recomputes if parameters have been modified since last call.

        Returns
        -------
        accumulated_by_branch : List[List[Tuple[int, float]]]
            For each branch, a list of (node_id, accumulated_f_p) tuples

        Examples
        --------
        >>> extractor = GraphExtractor()
        >>> extractor.extract_from_pgraph(pgraph_data, root_node_id=0)
        >>> accumulated = extractor.get_accumulated_frequencies()
        >>> for branch_idx, branch in enumerate(accumulated):
        >>>     for node_id, freq_offset in branch:
        >>>         print(f"Branch {branch_idx}, Node {node_id}: {freq_offset}")
        """
        self._recompute_derived_quantities()
        return self.accumulated_frequencies

    def get_chord_frequencies(self):
        """
        Get computed pump frequencies for chord edges.

        Automatically recomputes if parameters have been modified since last call.

        Returns
        -------
        chord_frequencies : dict
            Dictionary mapping chord edge (from_id, to_id) to computed f_p

        Examples
        --------
        >>> extractor = GraphExtractor()
        >>> extractor.extract_from_pgraph(pgraph_data, root_node_id=0)
        >>> chord_freqs = extractor.get_chord_frequencies()
        >>> for (from_id, to_id), f_p in chord_freqs.items():
        >>>     print(f"Chord {from_id}→{to_id}: f_p = {f_p}")
        """
        self._recompute_derived_quantities()
        return self.chord_frequencies

    def assign_node_parameters(
        self,
        node_id: int,
        freq: Optional[float] = None,
        B_int: Optional[float] = None, 
        B_ext: Optional[float] = None
    ) -> None:
        """
        Assign scattering parameters to a specific node.

        This method allows programmatic assignment of parameters after loading
        a graph structure. Useful for assigning values outside the GUI.

        Parameters
        ----------
        node_id : int
            The node_id to assign parameters to
        freq : Optional[float], default=None
            Frequency parameter [a.u.]. If None, parameter is not updated.
        B_int : Optional[float], default=None
            Internal coupling parameter [ma.u.]. If None, parameter is not updated.
        B_ext : Optional[float], default=None
            External coupling parameter.[ma.u.]  If None, parameter is not updated.

        Raises
        ------
        RuntimeError
            If extract_graph_data() has not been called yet
        ValueError
            If node_id is not found in the extracted graph

        Examples
        --------
        >>> extractor = GraphExtractor()
        >>> data = extractor.extract_from_pgraph(pgraph)
        >>> extractor.assign_node_parameters(0, freq=5.5, B_int=1.2)
        >>> extractor.assign_node_parameters(1, freq=6.0, B_int=1.0, B_ext=0.5)
        """
        if self.graph_data is None:
            raise RuntimeError("Must call extract_graph_data() or extract_from_pgraph() first")

        # Find the node in extracted data
        node_found = False
        for node in self.graph_data['nodes']:
            if node['node_id'] == node_id:
                node_found = True
                if freq is not None:
                    node['freq'] = freq
                if B_int is not None:
                    node['B_int'] = B_int
                if B_ext is not None:
                    node['B_ext'] = B_ext
                break

        if not node_found:
            raise ValueError(f"Node with node_id={node_id} not found in graph")

        # Mark that derived quantities need recomputation
        self._needs_recompute = True

    def assign_edge_parameters(
        self,
        from_node_id: int,
        to_node_id: int,
        f_p: Optional[float] = None,
        rate: Optional[float] = None,
        phase: Optional[float] = None
    ) -> None:
        """
        Assign scattering parameters to a specific edge.

        This method allows programmatic assignment of parameters after loading
        a graph structure. Useful for assigning values outside the GUI.

        Parameters
        ----------
        from_node_id : int
            The source node_id
        to_node_id : int
            The target node_id
        f_p : Optional[float], default=None
            Pump frequency parameter [a.u.]. If None, parameter is not updated.

            By default, f_p should be a POSITIVE value. The sign will be automatically
            determined based on node conjugation states and frequency ordering when
            computing accumulated frequencies via compute_accumulated_frequencies().

            If you prefer to manually specify signed f_p values, you can do so,
            but you MUST set sign_override=True when calling compute_accumulated_frequencies().
        rate : Optional[float], default=None
            Rate parameter. If None, parameter is not updated.
        phase : Optional[float], default=None
            Phase parameter [°]. If None, parameter is not updated.

        Raises
        ------
        RuntimeError
            If extract_graph_data() has not been called yet
        ValueError
            If edge is not found in the extracted graph

        Notes
        -----
        The pump frequency f_p represents the approximate frequency difference needed
        to couple two modes. When using automatic sign computation (recommended),
        provide positive values and the sign will be determined by:

        - Effective frequencies: unconjugated nodes use +f₀, conjugated nodes use -f₀
        - If edge goes from lower to higher effective frequency: upconversion (+f_p)
        - If edge goes from higher to lower effective frequency: downconversion (-f_p)

        Examples
        --------
        >>> # Typical usage with positive f_p (automatic sign computation)
        >>> extractor = GraphExtractor()
        >>> data = extractor.extract_from_pgraph(pgraph)
        >>> extractor.assign_edge_parameters(0, 1, f_p=4.0, rate=1.0, phase=0.0)
        >>> # Later: compute_accumulated_frequencies(..., sign_override=False)

        >>> # Advanced: manual sign control
        >>> extractor.assign_edge_parameters(0, 1, f_p=-4.0, rate=1.0, phase=0.0)
        >>> # Later: compute_accumulated_frequencies(..., sign_override=True)
        """
        if self.graph_data is None:
            raise RuntimeError("Must call extract_graph_data() or extract_from_pgraph() first")

        # Find the edge in extracted data (edges are undirected, so check both directions)
        edge_found = False
        for edge in self.graph_data['edges']:
            if ((edge['from_node_id'] == from_node_id and edge['to_node_id'] == to_node_id) or
                (edge['from_node_id'] == to_node_id and edge['to_node_id'] == from_node_id)):
                edge_found = True
                if f_p is not None:
                    edge['f_p'] = f_p
                if rate is not None:
                    edge['rate'] = rate
                if phase is not None:
                    edge['phase'] = phase
                break

        if not edge_found:
            raise ValueError(f"Edge {from_node_id}→{to_node_id} not found in graph")

        # Mark that derived quantities need recomputation
        self._needs_recompute = True

    def assign_all_nodes(
        self,
        freq: Optional[float] = None,
        B_int: Optional[float] = None,
        B_ext: Optional[float] = None
    ) -> None:
        """
        Assign the same scattering parameters to all nodes.

        Useful for setting uniform initial values or defaults.

        Parameters
        ----------
        freq : Optional[float], default=None
            Frequency parameter to assign to all nodes. If None, not assigned.
        B_int : Optional[float], default=None
            Internal coupling to assign to all nodes. If None, not assigned.
        B_ext : Optional[float], default=None
            External coupling to assign to all nodes. If None, not assigned.

        Raises
        ------
        RuntimeError
            If extract_graph_data() has not been called yet

        Examples
        --------
        Set all nodes to same frequency and coupling:
        >>> extractor.assign_all_nodes(freq=5.0, B_int=1.0)
        """
        if self.graph_data is None:
            raise RuntimeError("Must call extract_graph_data() or extract_from_pgraph() first")

        for node in self.graph_data['nodes']:
            if freq is not None:
                node['freq'] = freq
            if B_int is not None:
                node['B_int'] = B_int
            if B_ext is not None:
                node['B_ext'] = B_ext

        # Mark that derived quantities need recomputation
        self._needs_recompute = True

    def assign_all_edges(
        self,
        f_p: Optional[float] = None,
        rate: Optional[float] = None,
        phase: Optional[float] = None
    ) -> None:
        """
        Assign the same scattering parameters to all edges.

        Useful for setting uniform initial values or defaults.

        Parameters
        ----------
        f_p : Optional[float], default=None
            Pump frequency to assign to all edges. If None, not assigned.
        rate : Optional[float], default=None
            Rate parameter to assign to all edges. If None, not assigned.
        phase : Optional[float], default=None
            Phase parameter to assign to all edges. If None, not assigned.

        Raises
        ------
        RuntimeError
            If extract_graph_data() has not been called yet

        Examples
        --------
        Set all edges to same rate and phase:
        >>> extractor.assign_all_edges(rate=1.0, phase=0.0)
        """
        if self.graph_data is None:
            raise RuntimeError("Must call extract_graph_data() or extract_from_pgraph() first")

        for edge in self.graph_data['edges']:
            if not edge.get('is_self_loop', False):  # Skip self-loops
                if f_p is not None:
                    edge['f_p'] = f_p
                if rate is not None:
                    edge['rate'] = rate
                if phase is not None:
                    edge['phase'] = phase

        # Mark that derived quantities need recomputation
        self._needs_recompute = True

    def get_node_ids(self) -> List[int]:
        """
        Get list of all node IDs in the extracted graph.

        Returns
        -------
        List[int]
            List of node_id values

        Raises
        ------
        RuntimeError
            If extract_graph_data() has not been called yet

        Examples
        --------
        >>> node_ids = extractor.get_node_ids()
        >>> for node_id in node_ids:
        >>>     extractor.assign_node_parameters(node_id, freq=5.0 + node_id*0.1, B_int=1.0)
        """
        if self.graph_data is None:
            raise RuntimeError("Must call extract_graph_data() or extract_from_pgraph() first")

        return [node['node_id'] for node in self.graph_data['nodes']]

    def get_edge_list(self) -> List[Tuple[int, int]]:
        """
        Get list of all edges in the extracted graph as (from_id, to_id) tuples.

        Returns
        -------
        List[Tuple[int, int]]
            List of (from_node_id, to_node_id) tuples

        Raises
        ------
        RuntimeError
            If extract_graph_data() has not been called yet

        Examples
        --------
        >>> edges = extractor.get_edge_list()
        >>> for from_id, to_id in edges:
        >>>     extractor.assign_edge_parameters(from_id, to_id, rate=1.0, phase=0.0)
        """
        if self.graph_data is None:
            raise RuntimeError("Must call extract_graph_data() or extract_from_pgraph() first")

        return [(edge['from_node_id'], edge['to_node_id'])
                for edge in self.graph_data['edges']
                if not edge.get('is_self_loop', False)]

class GraphScatteringMatrix:
    '''Class to build the scattering matrix S from an EoM "M" matrix built
     using a GraphExtractor graph data and an array of drive frequencies.
     '''

    # Proportional spacing multipliers for frequency x-tick labels
    # These control spacing relative to font size for resize-invariant layouts
    # # ORIGINAL VALUES:
    # ROW_SPACING_MULT = 1.8      # Vertical spacing between freq rows (× font height)
    # ROW_START_MULT = 1.2        # Starting Y offset from x-axis (× font height)
    # PORT_LABEL_X_MULT = 0.5     # X offset for port labels (× font width)
    # XLABEL_EXTRA_MULT = 0.5     # Extra offset for xlabel below freq rows (× row_spacing)

    ROW_SPACING_MULT = 1.65    # Vertical spacing between freq rows (× font height)
    ROW_START_MULT = 0.95       # Starting Y offset from x-axis (× font height)
    PORT_LABEL_X_MULT = 0.55     # X offset for port labels (× font width)
    XLABEL_EXTRA_MULT = -0.75    # Extra offset for xlabel below freq rows (× row_spacing)    

    def __init__(self, extractor: GraphExtractor, f_root_s: np.ndarray, verbose: bool = False):
        self.extractor = extractor
        self.verbose = verbose  
        self.f_root_s = f_root_s
        self.num_modes = len(extractor.graph_data['nodes'])
        self.M = np.zeros((len(self.f_root_s), self.num_modes, self.num_modes), dtype=complex)

        self._build_f_drivesignals()
        self._build_M_matrix()
        self._build_K_matrix()
        self._build_S_matrix()
        self._build_det_M()

    def _build_f_drivesignals(self):
        accumulated_frequencies_flattened = list(
            collapse(self.extractor.get_accumulated_frequencies(), base_type=tuple)
        )
        self.drive_signals = {
            node_id: self.f_root_s + f_offset
            for node_id, f_offset in accumulated_frequencies_flattened
        }

    def _build_M_matrix(self):
        # Assemble diagonals
        accumulated_frequencies_flattened = list(
            collapse(self.extractor.get_accumulated_frequencies(), base_type=tuple)
        )

        if self.verbose:
            print("\n[DEBUG _build_M_matrix] Node diagonal values:")

        for idx, node in enumerate(self.extractor.graph_data['nodes']):
            node_id = node['node_id']
            f0 = node['freq']
            if node['B_ext'] is None:
                Btot = node['B_int']
            else:
                Btot = node['B_int'] + node['B_ext']
            conj_state = node['conj']
            if self.verbose:
                print(f"  Node {node_id}: f0={f0}, B_int={node['B_int']}, B_ext={node['B_ext']}, Btot={Btot}")

            for f_idx, f_root in enumerate(self.f_root_s):
                # Compute drive signals for this f_root
                drive_signals = {
                    node_id: f_root + f_offset
                    for node_id, f_offset in accumulated_frequencies_flattened
                }

                # Handle single-node case: if node not in drive_signals, use f_root directly
                f_drive = drive_signals.get(node_id, f_root)

                if conj_state:
                    self.M[f_idx, idx, idx] = f_drive + f0 + Btot * 1j / 2
                else:
                    self.M[f_idx, idx, idx] = f_drive - f0 + Btot * 1j / 2

        # Assemble off-diagonals
        basis = self.extractor.graph_data['basis_order']
        if self.verbose:
            print("\n[DEBUG _build_M_matrix] Edge off-diagonal values:")
        for edge in self.extractor.graph_data['edges']:
            from_id = edge['from_node_id']
            to_id = edge['to_node_id']

            j = basis.index(from_id)
            k = basis.index(to_id)

            if j != k:
                f_p = edge['f_p']
                rate = edge['rate']
                phase = edge['phase']

                beta = rate/2 * np.exp(1j * phase * np.pi / 180)
                if self.verbose:
                    print(f"  Edge {from_id}→{to_id}: f_p={f_p}, rate={rate}, phase={phase}, beta={beta}")

                conj_j = self.extractor.graph_data['nodes'][j]['conj']
                conj_k = self.extractor.graph_data['nodes'][k]['conj']

                if conj_j == conj_k:
                    if j < k:
                        self.M[:, j, k] = beta
                        self.M[:, k, j] = np.conj(beta)
                    else:
                        self.M[:, k, j] = beta
                        self.M[:, j, k] = np.conj(beta)
                else:
                    if j < k:
                        self.M[:, j, k] = beta
                        self.M[:, k, j] = -np.conj(beta)
                    else:
                        self.M[:, k, j] = beta
                        self.M[:, j, k] = -np.conj(beta)   

    def _build_K_matrix(self):
        self.port_dict = {}

        if self.verbose:
            print("\n[DEBUG _build_K_matrix] Building port dictionary:")
        for node in self.extractor.graph_data['nodes']:
            node_id = node['node_id']
            # print(node)
            if node['B_ext'] is not None and node['B_ext'] > 0:
                self.port_dict[node_id] = node['B_ext']
                if self.verbose:
                    print(f"  Added port: node_id={node_id}, B_ext={node['B_ext']}")

        self.num_ports = len(self.port_dict)

        if self.verbose:
            print(f"[DEBUG _build_K_matrix] Total ports: {self.num_ports}")
        self.K = np.zeros(shape=(self.num_modes, len(self.port_dict)), dtype=float)

        if self.verbose:
            print("[DEBUG _build_K_matrix] K matrix entries:")
        for node_id, B_ext in self.port_dict.items():
            mode_idx = self.extractor.graph_data['basis_order'].index(node_id)
            port_idx = list(self.port_dict.keys()).index(node_id)
            self.K[mode_idx, port_idx] = np.sqrt(B_ext)
            if self.verbose:
                print(f"  K[{mode_idx},{port_idx}] = sqrt({B_ext}) = {np.sqrt(B_ext)}")

    def _build_S_matrix(self):
        self.S = np.empty(shape=(len(self.f_root_s), self.num_ports, self.num_ports), dtype=complex)
        self.SdB = np.empty(shape=(len(self.f_root_s), self.num_ports, self.num_ports), dtype=float)
        for idx,_ in enumerate(self.f_root_s):
            M = self.M[idx,:,:]
            I = np.eye(self.num_ports)
            K = self.K

            self.S[idx,:,:] = 1j * K.T @ np.linalg.inv(M) @ K - I
            self.SdB[idx,:,:] = 20 * np.log10(np.abs(self.S[idx,:,:]))

        # Initialize empty trace list for plotting
        self._plot_traces = []

    def _build_det_M(self):
        """Compute the determinant of M at each frequency point.

        Creates:
            self.det_M : np.ndarray
                Complex determinant of M matrix at each frequency, shape (len(f_root_s),)
            self.det_M_dB : np.ndarray
                Magnitude of determinant in dB, shape (len(f_root_s),)
        """
        self.det_M = np.empty(len(self.f_root_s), dtype=complex)
        for idx in range(len(self.f_root_s)):
            self.det_M[idx] = np.linalg.det(self.M[idx, :, :])
        self.det_M_dB = 20 * np.log10(np.abs(self.det_M))

    # =========================================================================
    # Plotting API - Trace Management
    # =========================================================================

    # Default color palette for auto-coloring (matches GUI MYCOLORS)
    _DEFAULT_COLORS = [
        'indianred', 'cornflowerblue', 'darkseagreen', 'sandybrown',
        'mediumpurple', 'mediumaquamarine', 'gray'
    ]

    def add_trace(self, j, k, color='auto', linestyle='-', linewidth=2.0, label=None):
        """Add an S_jk trace to the plot list.

        Parameters
        ----------
        j : int
            'To' port index (row index in S-matrix). This is the port where
            the signal is detected/output.
        k : int
            'From' port index (column index in S-matrix). This is the port
            where the signal is driven/input.
        color : str, optional
            Color for the trace. Use 'auto' to cycle through default palette.
        linestyle : str, optional
            Matplotlib linestyle (e.g., '-', '--', ':', '-.').
        linewidth : float, optional
            Line width for the trace.
        label : str, optional
            Custom legend label. If None, uses 'S_{jk}' format.

        Returns
        -------
        self : GraphScatteringMatrix
            Returns self for method chaining.

        Example
        -------
        >>> gsm.add_trace(0, 0, color='red').add_trace(0, 1, color='blue')
        """
        self._plot_traces.append({
            'j': j,
            'k': k,
            'color': color,
            'linestyle': linestyle,
            'linewidth': linewidth,
            'label': label
        })
        return self

    def clear_traces(self):
        """Clear all traces from the plot list.

        Returns
        -------
        self : GraphScatteringMatrix
            Returns self for method chaining.
        """
        self._plot_traces = []
        return self

    def _resolve_trace_colors(self):
        """Resolve 'auto' colors to actual color values."""
        auto_idx = 0
        resolved = []
        for trace in self._plot_traces:
            t = trace.copy()
            if t['color'] == 'auto':
                t['color'] = self._DEFAULT_COLORS[auto_idx % len(self._DEFAULT_COLORS)]
                auto_idx += 1
            resolved.append(t)
        return resolved

    def _get_port_label(self, port_id):
        """Get node label for a port ID."""
        for node in self.extractor.graph_data['nodes']:
            if node['node_id'] == port_id:
                return node.get('label', str(port_id))
        return str(port_id)

    def _check_traces_not_empty(self, method_name):
        """Check that traces have been added and warn if empty."""
        if not self._plot_traces:
            import warnings
            warnings.warn(
                f"{method_name}() called with no traces added. "
                "Use add_trace(j, k, ...) to add S-parameters to plot.",
                UserWarning
            )
            return False
        return True

    # =========================================================================
    # Plotting API - Frequency Label Logic
    # =========================================================================

    def _apply_freq_labels(self, ax, fig, traces, frequencies, conjugate=False):
        """Apply port-specific x-tick labels based on selected traces.

        Font sizes are read from rcParams (set by seaborn/matplotlib).

        Rules:
        - S_jj only (diagonal): show x-ticks for port j, NO port label
        - S_jk (off-diagonal, j!=k): show x-ticks for BOTH ports, WITH port labels

        Parameters
        ----------
        ax : matplotlib.axes.Axes
            The axes to apply labels to.
        fig : matplotlib.figure.Figure
            The figure containing the axes.
        traces : list
            List of trace dicts with 'j' and 'k' keys.
        frequencies : np.ndarray
            The base frequency array (f_root_s).
        conjugate : bool
            Whether conjugate mode is active (negates and flips frequencies).
        """
        from collections import defaultdict
        import matplotlib.pyplot as plt

        port_ids = sorted(self.port_dict.keys())

        # Read font sizes from rcParams (respects seaborn settings)
        label_fontsize = plt.rcParams.get('axes.labelsize', 12)
        tick_fontsize = plt.rcParams.get('xtick.labelsize', 10)
        # Handle string values like 'medium', 'large'
        if isinstance(label_fontsize, str):
            label_fontsize = 12
        if isinstance(tick_fontsize, str):
            tick_fontsize = 10

        # Calculate row spacing proportionally based on font size and figure dimensions
        # This ensures rows don't overlap when resizing
        # Multipliers are class attributes (ROW_SPACING_MULT, etc.)
        ax_bbox = ax.get_position()
        fig_height_inches = fig.get_size_inches()[1]
        ax_height_inches = ax_bbox.height * fig_height_inches
        # Row height = font size in inches (72 pt/inch) * multiplier for padding
        row_height_inches = (tick_fontsize / 72) * self.ROW_SPACING_MULT
        # Convert to axes coordinates
        row_spacing = row_height_inches / ax_height_inches


        # Determine which ports are displayed and whether any off-diagonal
        displayed_ports = set()
        has_offdiagonal = False

        for trace in traces:
            j, k = trace['j'], trace['k']
            if j == k:
                displayed_ports.add(j)
            else:
                has_offdiagonal = True
                displayed_ports.add(j)
                displayed_ports.add(k)

        if not displayed_ports:
            return 0  # No frequency rows

        # Group ports by unique drive_signals arrays
        freq_groups = defaultdict(list)

        for port_idx in displayed_ports:
            if port_idx >= len(port_ids):
                continue
            port_id = port_ids[port_idx]

            if port_id in self.drive_signals:
                port_label = self._get_port_label(port_id)
                driven_freqs = self.drive_signals[port_id].copy()

                if conjugate:
                    driven_freqs = -driven_freqs[::-1]

                freq_key = tuple(driven_freqs)
                freq_groups[freq_key].append((port_id, port_label))

        # Determine display mode
        if not has_offdiagonal and len(freq_groups) <= 1:
            # Only diagonal elements with same/single frequency - use original x-axis
            fig.set_tight_layout(False)
            fig.subplots_adjust(bottom=0.15, left=0.15)
            ax.tick_params(axis='x', labelbottom=True)

            # Translate tick labels to match the port's drive_signals frequency
            if len(freq_groups) == 1:
                freq_key = list(freq_groups.keys())[0]
                driven_freqs = np.array(freq_key)

                # Apply conjugate to base frequencies for comparison
                base_freqs = frequencies
                if conjugate:
                    base_freqs = -base_freqs[::-1]

                freq_offset = driven_freqs[0] - base_freqs[0]

                if abs(freq_offset) > 1e-10:
                    tick_locs = ax.get_xticks()
                    xlim = ax.get_xlim()
                    visible_ticks = [t for t in tick_locs if xlim[0] <= t <= xlim[1]]
                    formatter = ax.xaxis.get_major_formatter()
                    new_labels = [formatter(t + freq_offset) for t in visible_ticks]
                    ax.set_xticks(visible_ticks)
                    ax.set_xticklabels(new_labels)

            return 0  # No extra frequency rows

        else:
            # Multiple frequency arrays or off-diagonal - show extra rows with port labels
            unique_freq_arrays = list(freq_groups.items())[:6]  # Limit to 6
            num_freq_rows = len(unique_freq_arrays)

            fig.set_tight_layout(False)

            # Adjust margins based on font size
            bottom_margin = 0.05 + num_freq_rows * row_spacing + 0.05
            left_margin = 0.16
            fig.subplots_adjust(bottom=bottom_margin, left=left_margin)

            # Hide original x-axis tick labels
            ax.tick_params(axis='x', labelbottom=False)

            # Get tick positions
            xlim = ax.get_xlim()
            all_tick_locs = ax.get_xticks()
            main_ax_tick_locs = [t for t in all_tick_locs if xlim[0] <= t <= xlim[1]]
            main_ax_formatter = ax.xaxis.get_major_formatter()

            # Get base frequencies for offset calculation
            main_freqs = frequencies
            if conjugate:
                main_freqs = -main_freqs[::-1]

            # Calculate proportional starting y position (same approach as row_spacing)
            start_y_inches = (tick_fontsize / 72) * self.ROW_START_MULT
            y_start = -start_y_inches / ax_height_inches

            # Calculate proportional x position for port labels
            fig_width_inches = fig.get_size_inches()[0]
            ax_width_inches = ax_bbox.width * fig_width_inches
            port_label_x_inches = (label_fontsize / 72) * self.PORT_LABEL_X_MULT
            port_label_x = -port_label_x_inches / ax_width_inches

            # Add tick labels for each frequency group
            for row_idx, (freq_key, port_list) in enumerate(unique_freq_arrays):
                driven_freqs = np.array(freq_key)

                # Create port label
                port_labels_str = ', '.join([label for _, label in port_list])
                label_text = f'Port{"s" if len(port_list) > 1 else ""} {port_labels_str}'

                # Position below x-axis (proportionally scaled)
                y_pos = y_start - (row_idx * row_spacing)

                # Frequency offset
                freq_offset = driven_freqs[0] - main_freqs[0]

                # Add port label (use axes label size)
                ax.text(
                    port_label_x, y_pos, label_text,
                    transform=ax.transAxes,
                    fontsize=label_fontsize * 0.9,
                    fontweight='bold',
                    verticalalignment='center',
                    horizontalalignment='right',
                    clip_on=False
                )

                # Add tick labels (use tick label size)
                for tick_pos in main_ax_tick_locs:
                    translated_freq = tick_pos + freq_offset
                    freq_label = main_ax_formatter(translated_freq)
                    ax.text(
                        tick_pos, y_pos, freq_label,
                        transform=ax.get_xaxis_transform(),
                        fontsize=tick_fontsize,
                        verticalalignment='center',
                        horizontalalignment='center',
                        clip_on=False
                    )

            return num_freq_rows

    def _finalize_plot(self, ax, fig, ylabel, frequencies, conjugate=False):
        """Apply common plot styling and frequency labels.

        Styling (colors, fonts, grid) is controlled by seaborn/matplotlib rcParams.
        Call sns.set_theme() before plotting to customize appearance.

        Parameters
        ----------
        ax : matplotlib.axes.Axes
            The axes to style.
        fig : matplotlib.figure.Figure
            The figure containing the axes.
        ylabel : str
            Label for the y-axis.
        frequencies : np.ndarray
            The base frequency array.
        conjugate : bool
            Whether conjugate mode is active.
        """
        import matplotlib.pyplot as plt

        # Get the actual plotted frequencies (after conjugate transform)
        plot_freqs = frequencies
        if conjugate:
            plot_freqs = -frequencies[::-1]

        # Set x-limits to the frequency array bounds FIRST (needed for tick positioning)
        ax.set_xlim(plot_freqs[0], plot_freqs[-1])

        # Set labels (styling comes from rcParams)
        ax.set_ylabel(ylabel)

        # Add legend
        if self._plot_traces:
            ax.legend(loc='lower left')

        # Force a draw to update tick positions before applying frequency labels
        fig.canvas.draw_idle()

        # Apply frequency labels
        traces = self._plot_traces
        num_freq_rows = self._apply_freq_labels(ax, fig, traces, frequencies, conjugate)

        # Add x-axis label, positioned below any frequency rows
        # Calculate proportional positioning (consistent with _apply_freq_labels)
        tick_fontsize = plt.rcParams.get('xtick.labelsize', 10)
        if isinstance(tick_fontsize, str):
            tick_fontsize = 10

        ax_bbox = ax.get_position()
        fig_height_inches = fig.get_size_inches()[1]
        ax_height_inches = ax_bbox.height * fig_height_inches

        # Row spacing in axes coords (uses class attributes)
        row_height_inches = (tick_fontsize / 72) * self.ROW_SPACING_MULT
        row_spacing = row_height_inches / ax_height_inches

        # Starting y position
        start_y_inches = (tick_fontsize / 72) * self.ROW_START_MULT
        y_start = -start_y_inches / ax_height_inches

        if num_freq_rows > 0:
            # Position below all frequency rows
            xlabel_y_pos = y_start - (num_freq_rows * row_spacing) - (row_spacing * self.XLABEL_EXTRA_MULT)
        else:
            # Default position when no extra rows
            xlabel_y_pos = y_start

        ax.set_xlabel('f [a.u.]')
        ax.xaxis.set_label_coords(0.5, xlabel_y_pos)

    # =========================================================================
    # Plotting API - Plot Methods
    # =========================================================================

    def plot_Smag(self, ax=None, conjugate=False, figsize=None):
        """Plot linear magnitude |S_jk| for all added traces.

        Parameters
        ----------
        ax : matplotlib.axes.Axes, optional
            Axes to plot on. If None, creates a new figure.
        conjugate : bool, optional
            If True, negates and flips frequency axis.
        figsize : tuple, optional
            Figure size if creating new figure. If None, uses rcParams['figure.figsize'].

        Returns
        -------
        fig, ax : tuple
            The figure and axes objects.
        """
        import matplotlib.pyplot as plt

        if not self._check_traces_not_empty('plot_Smag'):
            if ax is None:
                fig, ax = plt.subplots() if figsize is None else plt.subplots(figsize=figsize)
            else:
                fig = ax.get_figure()
            return fig, ax

        if ax is None:
            fig, ax = plt.subplots() if figsize is None else plt.subplots(figsize=figsize)
        else:
            fig = ax.get_figure()

        # Get frequencies and apply conjugate transform
        frequencies = self.f_root_s.copy()
        S = self.S.copy()
        if conjugate:
            frequencies = -frequencies[::-1]
            S = S[::-1, :, :]

        # Plot traces
        resolved_traces = self._resolve_trace_colors()
        port_ids = sorted(self.port_dict.keys())

        for trace in resolved_traces:
            j, k = trace['j'], trace['k']

            if j >= len(port_ids) or k >= len(port_ids):
                continue

            j_label = self._get_port_label(port_ids[j])
            k_label = self._get_port_label(port_ids[k])
            label = trace['label'] or f'{j_label}{k_label}'

            ax.plot(
                frequencies,
                np.abs(S[:, j, k]),
                label=label,
                color=trace['color'],
                linestyle=trace['linestyle'],
                linewidth=trace['linewidth']
            )

        self._finalize_plot(ax, fig, '|S|', self.f_root_s, conjugate)
        return fig, ax

    def plot_SdB(self, ax=None, conjugate=False, figsize=None):
        """Plot S-parameters in dB for all added traces.

        Parameters
        ----------
        ax : matplotlib.axes.Axes, optional
            Axes to plot on. If None, creates a new figure.
        conjugate : bool, optional
            If True, negates and flips frequency axis.
        figsize : tuple, optional
            Figure size if creating new figure. If None, uses rcParams['figure.figsize'].

        Returns
        -------
        fig, ax : tuple
            The figure and axes objects.
        """
        import matplotlib.pyplot as plt

        if not self._check_traces_not_empty('plot_SdB'):
            if ax is None:
                fig, ax = plt.subplots() if figsize is None else plt.subplots(figsize=figsize)
            else:
                fig = ax.get_figure()
            return fig, ax

        if ax is None:
            fig, ax = plt.subplots() if figsize is None else plt.subplots(figsize=figsize)
        else:
            fig = ax.get_figure()

        # Get frequencies and apply conjugate transform
        frequencies = self.f_root_s.copy()
        SdB = self.SdB.copy()
        if conjugate:
            frequencies = -frequencies[::-1]
            SdB = SdB[::-1, :, :]

        # Plot traces
        resolved_traces = self._resolve_trace_colors()
        port_ids = sorted(self.port_dict.keys())

        for trace in resolved_traces:
            j, k = trace['j'], trace['k']

            if j >= len(port_ids) or k >= len(port_ids):
                continue

            j_label = self._get_port_label(port_ids[j])
            k_label = self._get_port_label(port_ids[k])
            label = trace['label'] or f'{j_label}{k_label}'

            ax.plot(
                frequencies,
                SdB[:, j, k],
                label=label,
                color=trace['color'],
                linestyle=trace['linestyle'],
                linewidth=trace['linewidth']
            )

        self._finalize_plot(ax, fig, 'S [dB]', self.f_root_s, conjugate)
        return fig, ax

    def plot_phase(self, ax=None, conjugate=False, unwrap=True, figsize=None):
        """Plot phase of S-parameters in degrees for all added traces.

        Parameters
        ----------
        ax : matplotlib.axes.Axes, optional
            Axes to plot on. If None, creates a new figure.
        conjugate : bool, optional
            If True, negates and flips frequency axis.
        unwrap : bool, optional
            If True (default), unwrap phase to avoid discontinuities.
        figsize : tuple, optional
            Figure size if creating new figure. If None, uses rcParams['figure.figsize'].

        Returns
        -------
        fig, ax : tuple
            The figure and axes objects.
        """
        import matplotlib.pyplot as plt

        if not self._check_traces_not_empty('plot_phase'):
            if ax is None:
                fig, ax = plt.subplots() if figsize is None else plt.subplots(figsize=figsize)
            else:
                fig = ax.get_figure()
            return fig, ax

        if ax is None:
            fig, ax = plt.subplots() if figsize is None else plt.subplots(figsize=figsize)
        else:
            fig = ax.get_figure()

        # Get frequencies and apply conjugate transform
        frequencies = self.f_root_s.copy()
        S = self.S.copy()
        if conjugate:
            frequencies = -frequencies[::-1]
            S = S[::-1, :, :]

        # Plot traces
        resolved_traces = self._resolve_trace_colors()
        port_ids = sorted(self.port_dict.keys())

        for trace in resolved_traces:
            j, k = trace['j'], trace['k']

            if j >= len(port_ids) or k >= len(port_ids):
                continue

            j_label = self._get_port_label(port_ids[j])
            k_label = self._get_port_label(port_ids[k])
            label = trace['label'] or f'{j_label}{k_label}'

            # Get phase in radians for unwrapping, then convert to degrees
            phase_rad = np.angle(S[:, j, k])
            if unwrap:
                phase_rad = np.unwrap(phase_rad)
            phase_deg = np.rad2deg(phase_rad)

            ax.plot(
                frequencies,
                phase_deg,
                label=label,
                color=trace['color'],
                linestyle=trace['linestyle'],
                linewidth=trace['linewidth']
            )

        self._finalize_plot(ax, fig, 'Phase [deg]', self.f_root_s, conjugate)
        return fig, ax

    def plot_SdB_phase(self, conjugate=False, unwrap=True, figsize=None):
        """Plot both dB and phase in 2x1 subplots with shared x-axis.

        Parameters
        ----------
        conjugate : bool, optional
            If True, negates and flips frequency axis.
        unwrap : bool, optional
            If True (default), unwrap phase to avoid discontinuities.
        figsize : tuple, optional
            Figure size. If None, uses rcParams['figure.figsize'].

        Returns
        -------
        fig, (ax_dB, ax_phase) : tuple
            The figure and tuple of axes objects.
        """
        import matplotlib.pyplot as plt

        # WILL OVERRIDE CLASS-LEVEL CUSTOM XTICKS SETTINGS because the subplot layout messes things up
        # a little bit. Save original settings to restore later.
        orig_custom_xticks_settings = dict(    
            ROW_SPACING_MULT = self.ROW_SPACING_MULT,
            ROW_START_MULT = self.ROW_START_MULT,
            PORT_LABEL_X_MULT = self.PORT_LABEL_X_MULT,
            XLABEL_EXTRA_MULT = self.XLABEL_EXTRA_MULT  
        )

        self.ROW_SPACING_MULT = 1.2    # Vertical spacing between freq rows (× font height)
        self.ROW_START_MULT = 0.8       # Starting Y offset from x-axis (× font height)
        self.PORT_LABEL_X_MULT = 0.55     # X offset for port labels (× font width)
        self.XLABEL_EXTRA_MULT = -0.9    # Extra offset for xlabel below freq rows (× row_spacing)    
            

        if not self._check_traces_not_empty('plot_SdB_phase'):
            if figsize is None:
                fig, (ax_dB, ax_phase) = plt.subplots(2, 1, sharex=True)
            else:
                fig, (ax_dB, ax_phase) = plt.subplots(2, 1, figsize=figsize, sharex=True)
            return fig, (ax_dB, ax_phase)

        if figsize is None:
            fig, (ax_dB, ax_phase) = plt.subplots(2, 1, sharex=True)
        else:
            fig, (ax_dB, ax_phase) = plt.subplots(2, 1, figsize=figsize, sharex=True)

        # Get frequencies and apply conjugate transform
        frequencies = self.f_root_s.copy()
        S = self.S.copy()
        SdB = self.SdB.copy()
        if conjugate:
            frequencies = -frequencies[::-1]
            S = S[::-1, :, :]
            SdB = SdB[::-1, :, :]

        # Plot traces
        resolved_traces = self._resolve_trace_colors()
        port_ids = sorted(self.port_dict.keys())

        for trace in resolved_traces:
            j, k = trace['j'], trace['k']

            if j >= len(port_ids) or k >= len(port_ids):
                continue

            j_label = self._get_port_label(port_ids[j])
            k_label = self._get_port_label(port_ids[k])
            label_dB = trace['label'] or f'{j_label}{k_label}'
            label_phase = trace['label'] or f'{j_label}{k_label}'

            # Plot dB
            ax_dB.plot(
                frequencies,
                SdB[:, j, k],
                label=label_dB,
                color=trace['color'],
                linestyle=trace['linestyle'],
                linewidth=trace['linewidth']
            )

            # Plot phase (with optional unwrapping)
            phase_rad = np.angle(S[:, j, k])
            if unwrap:
                phase_rad = np.unwrap(phase_rad)
            phase_deg = np.rad2deg(phase_rad)
            ax_phase.plot(
                frequencies,
                phase_deg,
                label=label_phase,
                color=trace['color'],
                linestyle=trace['linestyle'],
                linewidth=trace['linewidth']
            )

        # Set x-limits to frequency array bounds (shared x-axis)
        ax_phase.set_xlim(frequencies[0], frequencies[-1])

        # Set axis labels and legends (styling controlled by seaborn/matplotlib rcParams)
        ax_dB.set_ylabel('S [dB]')
        ax_dB.legend(loc='lower left')

        ax_phase.set_ylabel('Phase [deg]')
        ax_phase.legend(loc='lower left')

        # Force a draw to update tick positions before applying frequency labels
        fig.canvas.draw_idle()

        # Apply frequency labels to bottom subplot
        traces = self._plot_traces
        num_freq_rows = self._apply_freq_labels(ax_phase, fig, traces, self.f_root_s, conjugate)

        # Add x-axis label with proportional position adjusted for frequency rows
        tick_fontsize = plt.rcParams.get('xtick.labelsize', 10)
        if isinstance(tick_fontsize, str):
            tick_fontsize = 10

        ax_bbox = ax_phase.get_position()
        fig_height_inches = fig.get_size_inches()[1]
        ax_height_inches = ax_bbox.height * fig_height_inches

        # Row spacing in axes coords (uses class attributes)
        row_height_inches = (tick_fontsize / 72) * self.ROW_SPACING_MULT
        row_spacing = row_height_inches / ax_height_inches

        # Starting y position
        start_y_inches = (tick_fontsize / 72) * self.ROW_START_MULT
        y_start = -start_y_inches / ax_height_inches

        if num_freq_rows > 0:
            xlabel_y_pos = y_start - (num_freq_rows * row_spacing) - (row_spacing * self.XLABEL_EXTRA_MULT)
        else:
            xlabel_y_pos = y_start

        ax_phase.set_xlabel('f [a.u.]')
        ax_phase.xaxis.set_label_coords(0.5, xlabel_y_pos)

        plt.tight_layout()

        # Restore original custom xtick settings
        self.ROW_SPACING_MULT = orig_custom_xticks_settings['ROW_SPACING_MULT']
        self.ROW_START_MULT = orig_custom_xticks_settings['ROW_START_MULT']
        self.PORT_LABEL_X_MULT = orig_custom_xticks_settings['PORT_LABEL_X_MULT']
        self.XLABEL_EXTRA_MULT = orig_custom_xticks_settings['XLABEL_EXTRA_MULT']

        return fig, (ax_dB, ax_phase)


