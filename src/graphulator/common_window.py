"""Shared main-window behavior for Graphulator and Paragraphulator.

Both applications grew from the same code and their main-window classes ended
up with dozens of copy-pasted methods that drifted apart one bug fix at a
time. Everything here is behavior the two apps genuinely share: recent-files
handling, save/open plumbing, grid drawing, view math, the fast pan/zoom
path, undo/redo, and small interaction helpers.

App-specific differences are expressed as class attributes (APP_NAME,
FILE_EXTENSION, APP_CONFIG, properties-panel widget names) and overridable
hooks (_save_last_directory, _save_last_edge_props, _after_grid_change)
rather than by editing method bodies, so a fix made here lands in both apps.
"""

import json
import logging
import sys
from pathlib import Path

import matplotlib
import numpy as np
from PySide6.QtGui import QAction, QCursor
from PySide6.QtWidgets import QFileDialog, QMenu, QMessageBox

logger = logging.getLogger(__name__)


class GraphWindowCommonMixin:
    """Mixin for the two apps' QMainWindow classes (must precede QMainWindow
    in the bases so these methods override nothing from Qt except
    resizeEvent/closeEvent-style handlers the apps already define)."""

    # ---- App parametrization (each app class overrides as needed) ----
    APP_NAME = "Graphulator"
    APP_ABOUT_BLURB = "<p>A tool for drawing nice graphs.</p>"
    APP_ICON_FILENAME = "graphulator_ICON.png"
    FILE_DIALOG_FILTER = "Graph Files (*.graph);;All Files (*)"
    FILE_EXTENSION = ".graph"
    APP_CONFIG = None  # each app sets its own config module

    # Properties-panel widget attribute names (the two apps named them
    # differently; the sync helper looks them up via getattr)
    PANEL_SELFLOOP_ANGLE_SPINBOX = 'selfloop_angle_spinbox'
    PANEL_SELFLOOP_COMPASS = 'selfloop_angle_compass_label'
    PANEL_SELFLOOP_PINNED = 'selfloop_angle_pinned_checkbox'

    # ---- Hooks (no-ops here; Paragraphulator overrides) ----

    def _save_last_directory(self, filepath):
        """Remember the directory of the last opened/saved file."""

    def _get_default_directory(self):
        """Starting directory for file dialogs."""
        return ""

    def _save_last_edge_props(self, edge):
        """Remember edge properties for inheritance by newly placed edges."""

    def _after_grid_change(self):
        """Refresh the display after the grid type/rotation changed."""
        self._update_plot()

    def _resolve_conj_label_color(self, node):
        """Default label color for a node under the conjugation convention.

        Conjugation reads as an inversion of the unconjugated appearance:
        with AUTO on the color derives from the fill mode (hollow nodes take
        the node's own color so the label never vanishes); otherwise the
        literal CONJ_LABEL_COLOR_MODE choice applies. A per-node
        'label_color' override still wins over this default at the call
        site.
        """
        config = self.APP_CONFIG
        if not node.get('conj', False):
            return config.DEFAULT_NODE_LABEL_COLOR
        hollow = getattr(config, 'CONJ_NODE_FILL_MODE', 'dimmed') == 'transparent'
        if getattr(config, 'CONJ_LABEL_COLOR_AUTO', True):
            return node['color'] if hollow else config.DEFAULT_NODE_LABEL_COLOR
        mode = getattr(config, 'CONJ_LABEL_COLOR_MODE', 'default')
        if mode == 'node':
            return node['color']
        if mode == 'custom':
            return getattr(config, 'CONJ_NODE_LABEL_COLOR', 'white')
        return config.DEFAULT_NODE_LABEL_COLOR

    # ---- Hand-parametrized shared methods ----

    def _update_window_title(self):
        """Update window title with filename and modified status"""
        title = self.APP_NAME
        if self.current_filepath:
            title += f" - {Path(self.current_filepath).name}"
        if self.is_modified:
            title += " *"
        self.setWindowTitle(title)

    def _show_about(self):
        """Show the About dialog with version, logo, and project info."""
        import PySide6
        from PySide6.QtCore import Qt, qVersion
        from PySide6.QtGui import QPixmap

        from graphulator import __copyright__, __url__, __version__
        from graphulator._resources import resource_path

        py_version = ".".join(str(p) for p in sys.version_info[:3])
        text = (
            f"<h3>{self.APP_NAME} {__version__}</h3>"
            f"{self.APP_ABOUT_BLURB}"
            f"<p><small>PySide6 {PySide6.__version__} &middot; "
            f"Qt {qVersion()} &middot; Python {py_version}</small></p>"
            f"<p><small>{__copyright__} &middot; "
            f"<a href='{__url__}'>{__url__.replace('https://', '')}</a>"
            "</small></p>"
        )

        box = QMessageBox(self)
        box.setWindowTitle(f"About {self.APP_NAME}")
        box.setTextFormat(Qt.RichText)
        box.setText(text)

        icon_path = resource_path("assets", self.APP_ICON_FILENAME)
        if icon_path.is_file():
            pixmap = QPixmap(str(icon_path))
            if not pixmap.isNull():
                box.setIconPixmap(pixmap.scaled(
                    96, 96,
                    Qt.KeepAspectRatio, Qt.SmoothTransformation,
                ))

        box.setStandardButtons(QMessageBox.Ok)
        box.exec()

    def _save_graph_as(self):
        """Save the graph to a new file"""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Graph As", self._get_default_directory(),
            self.FILE_DIALOG_FILTER
        )

        if filepath:
            # Add the app's extension if not present
            if not filepath.endswith(self.FILE_EXTENSION):
                filepath += self.FILE_EXTENSION
            return self._save_graph_to_file(filepath)
        return False

    def _save_graph_to_file(self, filepath):
        """Save graph to specified file"""
        try:
            data = self._serialize_graph()

            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)

            self.current_filepath = filepath
            self._save_last_directory(filepath)
            self._set_modified(False)
            self._add_to_recent_files(filepath)

            # Also save as last graph (session restore)
            try:
                with open(self.last_graph_path, 'w') as f:
                    json.dump(data, f, indent=2)
            except Exception:
                logger.warning("Could not update the last-graph autosave", exc_info=True)

            logger.info(f"Saved graph to {filepath}")
            return True

        except Exception as e:
            QMessageBox.critical(
                self, "Error Saving File",
                f"Could not save file:\n{e}"
            )
            logger.error(f"Error saving graph: {e}")
            return False

    def _open_graph_file(self, filepath):
        """Open a specific graph file"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            self._deserialize_graph(data)
            self.current_filepath = filepath
            self._set_modified(False)
            self._add_to_recent_files(filepath)
            self._save_last_directory(filepath)
            logger.info(f"Opened graph from {filepath}")

        except Exception as e:
            QMessageBox.critical(
                self, "Error Opening File",
                f"Could not open file:\n{e}"
            )
            logger.error(f"Error opening graph: {e}")

    def _rotate_grid(self):
        """Rotate the grid"""
        increment = (self.APP_CONFIG.SQUARE_GRID_ROTATION_INCREMENT
                     if self.grid_type == "square"
                     else self.APP_CONFIG.TRIANGULAR_GRID_ROTATION_INCREMENT)
        self.grid_rotation = (self.grid_rotation + increment) % 360
        logger.debug(f"Rotated grid to {self.grid_rotation}°")
        self._after_grid_change()

    def _toggle_grid_type(self):
        """Toggle grid type"""
        self.grid_type = "triangular" if self.grid_type == "square" else "square"
        self.grid_rotation = 0
        logger.debug(f"Switched to {self.grid_type} grid")
        self._after_grid_change()

    def _apply_view_fast(self, use_idle=True):
        """Fast pan/zoom: update axis limits and rescale zoom-dependent linewidths
        on the EXISTING artists instead of rebuilding the scene.

        Node circles, edge paths and the cached label glyphs all live in data
        coordinates, so they rescale/reposition for free when the limits change;
        only stroke widths (which scale with zoom) and the grid extent need
        touching. Falls back to a full render if the scene hasn't been built yet,
        or when a secondary canvas is active (Paragraphulator's kron/scattering
        views always use full renders).
        """
        ax = self.canvas.ax
        if (self._zoom_lw_snapshot is None or self._build_ppu is None
                or getattr(self, 'original_canvas', self.canvas) is not self.canvas):
            self._update_plot(use_idle=use_idle)
            return

        new_xlim = self._get_xlim()
        new_ylim = self._get_ylim()

        # Keep strokes proportional to zoom (grid excluded; it has fixed width).
        new_ppu = self._points_per_data_unit(new_xlim, new_ylim)
        if new_ppu and self._build_ppu:
            factor = new_ppu / self._build_ppu
            for artist, base_lw in self._zoom_lw_snapshot:
                try:
                    artist.set_linewidth(base_lw * factor)
                except Exception:
                    pass

        # Rebuild the grid only if the view grew beyond the extent it covers.
        new_extent = max(abs(new_xlim[0]), abs(new_xlim[1]),
                         abs(new_ylim[0]), abs(new_ylim[1])) * 1.5
        if self._grid_built_extent is not None and new_extent > self._grid_built_extent:
            self._rebuild_grid_only()

        ax.set_xlim(*new_xlim)
        ax.set_ylim(*new_ylim)
        self._update_status_label()
        self.canvas.draw_idle()

    def _sync_selfloop_angle_widgets(self, edge):
        """Reflect a self-loop's angle into the properties-panel widgets."""
        panel = getattr(self, 'properties_panel', None)
        if panel is None:
            return
        spin = getattr(panel, self.PANEL_SELFLOOP_ANGLE_SPINBOX, None)
        if spin is None:
            return
        spin.blockSignals(True)
        spin.setValue(edge.get('selfloopangle', 0))
        spin.blockSignals(False)
        compass = getattr(panel, self.PANEL_SELFLOOP_COMPASS, None)
        if compass is not None:
            compass.setText(panel._compass_direction(edge.get('selfloopangle', 0)))
        pinned = getattr(panel, self.PANEL_SELFLOOP_PINNED, None)
        if pinned is not None:
            pinned.blockSignals(True)
            pinned.setChecked(True)
            pinned.blockSignals(False)

    def _adjust_selfloop_angle(self, action):
        """Adjust self-loop angle using Ctrl+Left/Right (configurable increments)"""
        if not self.selected_edges:
            return

        # Filter to only self-loops
        selfloops = [e for e in self.selected_edges if e.get('is_self_loop', False)]
        if not selfloops:
            return

        self._save_state()

        increment = self.APP_CONFIG.SELFLOOP_ANGLE_KEYBOARD_INCREMENT
        for edge in selfloops:
            current = edge.get('selfloopangle', 0)

            # Reverse direction: Left increases (counter-clockwise), Right decreases (clockwise)
            if action == 'increase':
                edge['selfloopangle'] = (current - increment) % 360
            elif action == 'decrease':
                edge['selfloopangle'] = (current + increment) % 360
            edge['angle_pinned'] = True

        # Update properties panel spinbox if showing a single self-loop
        if len(self.selected_edges) == 1:
            edge = self.selected_edges[0]
            if edge.get('is_self_loop', False):
                self._sync_selfloop_angle_widgets(edge)

        if len(selfloops) == 1:
            logger.debug(f"Self-loop angle: {selfloops[0]['selfloopangle']}°")
        else:
            logger.debug(f"Adjusted angle for {len(selfloops)} self-loop(s)")
        # Save the last one for inheritance by newly placed self-loops
        self._save_last_edge_props(selfloops[-1])

        self._update_plot()

    def _adjust_edge_looptheta_or_selfloop_angle(self, action):
        """Adjust looptheta for regular edges or selfloopangle for self-loops using Ctrl+Left/Right (2° increments for looptheta, configurable for selfloop)"""
        logger.debug(f"_adjust_edge_looptheta_or_selfloop_angle called with action={action}, selected_edges count={len(self.selected_edges)}")
        if not self.selected_edges:
            logger.debug("No edges selected, returning")
            return

        # Separate self-loops from regular edges
        selfloops = [e for e in self.selected_edges if e.get('is_self_loop', False)]
        regular_edges = [e for e in self.selected_edges if not e.get('is_self_loop', False)]
        logger.debug(f"selfloops={len(selfloops)}, regular_edges={len(regular_edges)}")

        if not selfloops and not regular_edges:
            logger.debug("No valid edges found")
            return

        self._save_state()

        # Adjust self-loop angles (configurable increments)
        increment = self.APP_CONFIG.SELFLOOP_ANGLE_KEYBOARD_INCREMENT
        for edge in selfloops:
            current = edge.get('selfloopangle', 0)
            # Reverse direction: Left increases (counter-clockwise), Right decreases (clockwise)
            if action == 'increase':
                edge['selfloopangle'] = (current - increment) % 360
            elif action == 'decrease':
                edge['selfloopangle'] = (current + increment) % 360
            edge['angle_pinned'] = True

        # Adjust regular edge looptheta (2° increments)
        for edge in regular_edges:
            current = edge.get('looptheta', 30)
            if action == 'increase':
                edge['looptheta'] = current + 2
            elif action == 'decrease':
                edge['looptheta'] = current - 2

        # Update properties panel if showing a single edge
        if len(self.selected_edges) == 1 and hasattr(self, 'properties_panel'):
            edge = self.selected_edges[0]
            if not edge.get('is_self_loop', False) and hasattr(self.properties_panel, 'looptheta_spinbox'):
                # Block signals to avoid triggering update again
                self.properties_panel.looptheta_spinbox.blockSignals(True)
                self.properties_panel.looptheta_spinbox.setValue(edge.get('looptheta', 30))
                self.properties_panel.looptheta_spinbox.blockSignals(False)
            elif edge.get('is_self_loop', False):
                self._sync_selfloop_angle_widgets(edge)

        # Log feedback and remember the last edge for inheritance
        if len(self.selected_edges) == 1:
            edge = self.selected_edges[0]
            if edge.get('is_self_loop', False):
                logger.debug(f"Self-loop angle: {edge['selfloopangle']}°")
            else:
                logger.debug(f"Edge looptheta: {edge.get('looptheta', 30)}°")
            self._save_last_edge_props(edge)
        else:
            if selfloops and regular_edges:
                logger.debug(f"Adjusted {len(selfloops)} self-loop(s) and {len(regular_edges)} edge(s)")
            elif selfloops:
                logger.debug(f"Adjusted angle for {len(selfloops)} self-loop(s)")
            else:
                logger.debug(f"Adjusted looptheta for {len(regular_edges)} edge(s)")
            if selfloops:
                self._save_last_edge_props(selfloops[-1])
            elif regular_edges:
                self._save_last_edge_props(regular_edges[-1])

        self._update_plot()

    # ---- Methods lifted verbatim from the (logger-based) originals ----

    def _add_to_recent_files(self, filepath):
        """Add a file to the recent files list"""
        filepath = str(filepath)
        # Remove if already in list
        if filepath in self.recent_files:
            self.recent_files.remove(filepath)
        # Add to front
        self.recent_files.insert(0, filepath)
        # Trim to max
        self.recent_files = self.recent_files[:self.max_recent_files]
        self._save_recent_files()
        self._update_recent_files_menu()

    def _calculate_graph_extents(self):
        """Calculate the full extents of the graph including all objects (nodes, edges, self-loops, labels)"""
        if not self.nodes:
            return 0, 0, 0, 0

        xlims = []
        ylims = []

        # Collect bounds from all nodes, labels, and self-loops
        for node in self.nodes:
            xy = node['pos']
            node_size_mult = node.get('node_size_mult', 1.0)
            R = self.node_radius * node_size_mult

            # Account for node radius and label extent
            label_padding = R * 3.5  # Estimate for label extent
            xlims.extend([xy[0] - label_padding, xy[0] + label_padding])
            ylims.extend([xy[1] - label_padding, xy[1] + label_padding])

            # Check if this node has a self-loop
            for edge in self.edges:
                if edge['is_self_loop'] and edge['from_node_id'] == node['node_id']:
                    selfloopscale = edge.get('selfloopscale', 1.0)
                    loop_extent = R * 6 * selfloopscale  # loopR radius
                    selfloopangle = edge.get('selfloopangle', 0)
                    angle_rad = selfloopangle * np.pi / 180
                    loop_x = xy[0] + loop_extent * np.cos(angle_rad)
                    loop_y = xy[1] + loop_extent * np.sin(angle_rad)
                    xlims.extend([loop_x - loop_extent/2, loop_x + loop_extent/2])
                    ylims.extend([loop_y - loop_extent/2, loop_y + loop_extent/2])
                    break

        # Account for edge extents
        for edge in self.edges:
            if not edge['is_self_loop']:
                from_pos = edge['from_node']['pos']
                to_pos = edge['to_node']['pos']
                # Loopy edges can extend significantly - add extra padding
                edge_padding = max(abs(from_pos[0] - to_pos[0]), abs(from_pos[1] - to_pos[1])) * 0.5
                xlims.extend([from_pos[0] - edge_padding, to_pos[0] + edge_padding])
                ylims.extend([from_pos[1] - edge_padding, to_pos[1] + edge_padding])

        x_min, x_max = min(xlims), max(xlims)
        y_min, y_max = min(ylims), max(ylims)

        return x_min, x_max, y_min, y_max

    def _check_unsaved_changes(self):
        """Check for unsaved changes and prompt user. Returns True if safe to proceed."""
        if not self.is_modified:
            return True

        reply = QMessageBox.question(
            self, "Unsaved Changes",
            "You have unsaved changes. Do you want to save them?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save
        )

        if reply == QMessageBox.Save:
            return self._save_graph()
        elif reply == QMessageBox.Discard:
            return True
        else:  # Cancel
            return False

    def _clear_recent_files(self):
        """Clear the recent files list"""
        self.recent_files = []
        self._save_recent_files()
        self._update_recent_files_menu()

    def _color_key_to_mode(self, color_key):
        """Map color key to prettynode mode letter"""
        # Map based on prettynode's default colors:
        # A=indianred, B=cornflowerblue, C=darkseagreen, D=sandybrown, E=cadetblue, F=mediumaquamarine
        color_to_mode = {
            'RED': 'A',      # indianred
            'BLUE': 'B',     # cornflowerblue
            'GREEN': 'C',    # darkseagreen
            'ORANGE': 'D',   # sandybrown
            'PURPLE': 'E',   # cadetblue (we use mediumpurple, close enough)
            'TEAL': 'F',     # mediumaquamarine
        }
        return color_to_mode.get(color_key, 'A')  # Default to 'A' if not found

    def _compute_best_selfloop_angle(self, node, exclude_edge=None):
        """Compute the self-loop angle that is farthest from all existing edges on this node.

        Uses the configurable SELFLOOP_ANGLE_KEYBOARD_INCREMENT to generate candidate
        angles, then picks the one with the largest minimum angular distance from any
        connected edge (including other self-loops, but excluding exclude_edge).

        Args:
            node: The node dict to compute the angle for.
            exclude_edge: Optional edge dict to exclude from angle collection
                (used when recomputing an existing self-loop's own angle).
        """
        node_id = node['node_id']
        node_pos = np.array(node['pos'])

        # Collect angles of all edges connected to this node
        edge_angles = []
        for edge in self.edges:
            if edge is exclude_edge:
                continue
            if edge.get('is_self_loop', False):
                # Existing self-loop on this node
                if edge.get('from_node_id') == node_id:
                    edge_angles.append(edge.get('selfloopangle', 0) % 360)
            else:
                # Regular edge - compute angle from this node to the other node
                if edge.get('from_node_id') == node_id:
                    other = edge.get('to_node', {})
                elif edge.get('to_node_id') == node_id:
                    other = edge.get('from_node', {})
                else:
                    continue
                other_pos = np.array(other['pos'])
                diff = other_pos - node_pos
                angle_deg = np.degrees(np.arctan2(diff[1], diff[0])) % 360
                edge_angles.append(angle_deg)

        # If no edges, return the default angle
        if not edge_angles:
            return self.APP_CONFIG.DEFAULT_SELFLOOP_ANGLE

        # Generate candidate angles based on configurable increment
        increment = self.APP_CONFIG.SELFLOOP_ANGLE_KEYBOARD_INCREMENT
        candidates = list(range(0, 360, increment))

        # Find candidate with largest minimum angular distance from any edge.
        # On ties, prefer the default angle (90° = Up) for aesthetics.
        best_angle = self.APP_CONFIG.DEFAULT_SELFLOOP_ANGLE
        best_min_dist = -1
        for candidate in candidates:
            min_dist = min(
                min(abs(candidate - ea), 360 - abs(candidate - ea))
                for ea in edge_angles
            )
            if min_dist > best_min_dist or (
                min_dist == best_min_dist and candidate == self.APP_CONFIG.DEFAULT_SELFLOOP_ANGLE
            ):
                best_min_dist = min_dist
                best_angle = candidate

        return best_angle

    def _copy_graph_to_clipboard_vector(self):
        """Copy the graph as vector PDF/SVG only (no raster PNG fallback).

        Forces vector-preferring apps that otherwise grab the PNG (Keynote,
        PowerPoint) to paste the editable PDF/SVG instead.
        """
        self._copy_graph_to_clipboard(include_png=False)

    def _draw_triangular_grid(self):
        """Draw rotated triangular grid"""
        spacing = self.grid_spacing
        rot_rad = np.radians(self.grid_rotation)
        sqrt3 = np.sqrt(3)

        xlim = self._get_xlim()
        ylim = self._get_ylim()
        # Generous extent so ordinary zoom-out stays covered without a rebuild.
        max_extent = max(abs(xlim[0]), abs(xlim[1]), abs(ylim[0]), abs(ylim[1])) * 3.0
        self._grid_built_extent = max_extent
        n = int(max_extent / spacing * 2) + 5

        # Three sets of lines
        for i in range(-n, n + 1):
            # Horizontal lines
            offset = i * spacing * sqrt3 / 2
            x1, y1 = -max_extent, offset
            x2, y2 = max_extent, offset
            x1r = x1 * np.cos(rot_rad) - y1 * np.sin(rot_rad)
            y1r = x1 * np.sin(rot_rad) + y1 * np.cos(rot_rad)
            x2r = x2 * np.cos(rot_rad) - y2 * np.sin(rot_rad)
            y2r = x2 * np.sin(rot_rad) + y2 * np.cos(rot_rad)
            line, = self.canvas.ax.plot([x1r, x2r], [y1r, y2r], 'lightgray', lw=0.5, zorder=0)
            line.set_gid('grid')

        for i in range(-n, n + 1):
            # 60° lines
            offset = i * spacing
            x0, y0 = offset, 0
            dx, dy = 1, sqrt3
            x1 = x0 - max_extent * dx
            y1 = y0 - max_extent * dy
            x2 = x0 + max_extent * dx
            y2 = y0 + max_extent * dy
            x1r = x1 * np.cos(rot_rad) - y1 * np.sin(rot_rad)
            y1r = x1 * np.sin(rot_rad) + y1 * np.cos(rot_rad)
            x2r = x2 * np.cos(rot_rad) - y2 * np.sin(rot_rad)
            y2r = x2 * np.sin(rot_rad) + y2 * np.cos(rot_rad)
            line, = self.canvas.ax.plot([x1r, x2r], [y1r, y2r], 'lightgray', lw=0.5, zorder=0)
            line.set_gid('grid')

        for i in range(-n, n + 1):
            # 120° lines
            offset = i * spacing
            x0, y0 = offset, 0
            dx, dy = 1, -sqrt3
            x1 = x0 - max_extent * dx
            y1 = y0 - max_extent * dy
            x2 = x0 + max_extent * dx
            y2 = y0 + max_extent * dy
            x1r = x1 * np.cos(rot_rad) - y1 * np.sin(rot_rad)
            y1r = x1 * np.sin(rot_rad) + y1 * np.cos(rot_rad)
            x2r = x2 * np.cos(rot_rad) - y2 * np.sin(rot_rad)
            y2r = x2 * np.sin(rot_rad) + y2 * np.cos(rot_rad)
            line, = self.canvas.ax.plot([x1r, x2r], [y1r, y2r], 'lightgray', lw=0.5, zorder=0)
            line.set_gid('grid')

    def _find_edge_at_position(self, x, y):
        """Find edge at given position (near center of edge or self-loop apex)"""
        for edge in self.edges:
            if edge['is_self_loop']:
                # For self-loops, check if click is near any part of the loop arc
                from_pos = edge['from_node']['pos']
                from_node = edge['from_node']
                from_radius = self.node_radius * from_node.get('node_size_mult', 1.0)

                # Calculate self-loop parameters
                selfloopscale = edge.get('selfloopscale', 1.0)
                LOOPYSCALE = 6 * selfloopscale
                selfloopangle = edge.get('selfloopangle', 0)
                loopR = from_radius * LOOPYSCALE

                # Check multiple points along the loop arc for easier selection
                # Sample points from start of arc to apex to end of arc
                detection_radius = max(from_radius * 2.0, loopR * 0.5)  # Larger detection area

                # Check several points along the arc (5 sample points)
                for t in [0.25, 0.5, 0.75, 1.0]:
                    # Distance from node center varies along arc
                    sample_distance = from_radius * 1.2 + loopR * t
                    sample_x = from_pos[0] + sample_distance * np.cos(selfloopangle * np.pi / 180)
                    sample_y = from_pos[1] + sample_distance * np.sin(selfloopangle * np.pi / 180)

                    dx = x - sample_x
                    dy = y - sample_y
                    distance = np.sqrt(dx*dx + dy*dy)
                    if distance <= detection_radius:
                        return edge
            else:
                # Regular edge - check midpoint
                from_pos = edge['from_node']['pos']
                to_pos = edge['to_node']['pos']

                # Calculate midpoint of edge
                mid_x = (from_pos[0] + to_pos[0]) / 2
                mid_y = (from_pos[1] + to_pos[1]) / 2

                # Calculate edge length
                edge_length = np.sqrt((to_pos[0] - from_pos[0])**2 + (to_pos[1] - from_pos[1])**2)

                # Click detection radius (80% of half edge length, max 2.0 units)
                detection_radius = min(edge_length * 0.4, 2.0)

                # Check if click is near midpoint
                dx = x - mid_x
                dy = y - mid_y
                distance = np.sqrt(dx*dx + dy*dy)
                if distance <= detection_radius:
                    return edge
        return None

    def _find_node_at_position(self, x, y):
        """Find node at given position (within node radius)"""
        for node in self.nodes:
            node_size_mult = node.get('node_size_mult', 1.0)
            radius = self.node_radius * node_size_mult
            dx = x - node['pos'][0]
            dy = y - node['pos'][1]
            distance = np.sqrt(dx*dx + dy*dy)
            if distance <= radius:
                return node
        return None

    def _get_canvas_aspect_ratio(self):
        """Get the aspect ratio (width/height) of the canvas"""
        bbox = self.canvas.ax.get_window_extent()
        width = bbox.width
        height = bbox.height
        if height > 0:
            return width / height
        return 1.0

    def _get_next_label(self):
        """Generate next alphabetical label"""
        if self.node_counter < 26:
            return chr(ord('A') + self.node_counter)
        else:
            first = chr(ord('A') + (self.node_counter // 26) - 1)
            second = chr(ord('A') + (self.node_counter % 26))
            return first + second

    def _get_xlim(self):
        """Get x limits based on zoom level and canvas aspect ratio"""
        center = (self.base_xlim[0] + self.base_xlim[1]) / 2
        base_half_width = (self.base_xlim[1] - self.base_xlim[0]) / 2
        base_half_height = (self.base_ylim[1] - self.base_ylim[0]) / 2

        # Get canvas aspect ratio
        canvas_aspect = self._get_canvas_aspect_ratio()

        # Calculate base data aspect ratio
        base_data_aspect = base_half_width / base_half_height

        # Expand the dimension that needs to grow to fill canvas
        if canvas_aspect > base_data_aspect:
            # Canvas is wider than base data - expand width
            half_width = base_half_height * canvas_aspect
        else:
            # Use base width
            half_width = base_half_width

        # Apply zoom
        half_width /= self.zoom_level

        return (center - half_width, center + half_width)

    def _get_ylim(self):
        """Get y limits based on zoom level and canvas aspect ratio"""
        center = (self.base_ylim[0] + self.base_ylim[1]) / 2
        base_half_width = (self.base_xlim[1] - self.base_xlim[0]) / 2
        base_half_height = (self.base_ylim[1] - self.base_ylim[0]) / 2

        # Get canvas aspect ratio
        canvas_aspect = self._get_canvas_aspect_ratio()

        # Calculate base data aspect ratio
        base_data_aspect = base_half_width / base_half_height

        # Expand the dimension that needs to grow to fill canvas
        if canvas_aspect < base_data_aspect:
            # Canvas is taller than base data - expand height
            half_height = base_half_width / canvas_aspect
        else:
            # Use base height
            half_height = base_half_height

        # Apply zoom
        half_height /= self.zoom_level

        return (center - half_height, center + half_height)

    def _points_per_data_unit(self, xlim, ylim):
        """Points per data unit for the current figure size and view limits."""
        fig = self.canvas.fig
        data_width = xlim[1] - xlim[0]
        data_height = ylim[1] - ylim[0]
        if data_width <= 0 or data_height <= 0:
            return None
        return min(fig.get_figwidth() * 72 / data_width,
                   fig.get_figheight() * 72 / data_height)

    def _rebuild_grid_only(self):
        """Remove just the grid line artists and redraw the grid for the current view."""
        for artist in [a for a in self.canvas.ax.lines if a.get_gid() == 'grid']:
            try:
                artist.remove()
            except Exception:
                pass
        self._draw_grid()

    def _recompute_unpinned_selfloop_angles(self, moved_node_ids):
        """Recompute angles for unpinned self-loops affected by moved nodes.

        Args:
            moved_node_ids: set of node_ids that were moved. Self-loops on these
                nodes AND self-loops on nodes connected to these nodes are affected.
        """
        if not self.APP_CONFIG.DYNAMIC_ADJUST_SELFLOOP_ANGLE:
            return

        # Find all affected node IDs (moved nodes + their neighbors)
        affected_node_ids = set(moved_node_ids)
        for edge in self.edges:
            if edge.get('is_self_loop', False):
                continue
            fid = edge.get('from_node_id')
            tid = edge.get('to_node_id')
            if fid in moved_node_ids:
                affected_node_ids.add(tid)
            if tid in moved_node_ids:
                affected_node_ids.add(fid)

        # Recompute unpinned self-loops on affected nodes
        for edge in self.edges:
            if (edge.get('is_self_loop', False) and
                    not edge.get('angle_pinned', False) and
                    edge.get('from_node_id') in affected_node_ids):
                node = edge.get('from_node')
                if node:
                    edge['selfloopangle'] = self._compute_best_selfloop_angle(node, exclude_edge=edge)

    def _render_with_latex(self):
        """Deprecated: the debounced LaTeX re-render is no longer used.

        Kept as a no-op so the (now-unused) debounce timer connection is safe.
        """
        return

    def _save_graph(self):
        """Save the current graph"""
        if self.current_filepath:
            return self._save_graph_to_file(self.current_filepath)
        else:
            return self._save_graph_as()

    def _save_state(self):
        """Save current state to undo stack"""
        self.undo_stack.append(self._capture_state())

        # Limit stack size
        if len(self.undo_stack) > self.max_undo:
            self.undo_stack.pop(0)

        # A new action invalidates the redo history
        self.redo_stack.clear()

        # Mark as modified
        self._set_modified(True)

    def _select_all(self):
        """Select all nodes and edges"""
        self.selected_nodes = self.nodes.copy()
        self.selected_edges = self.edges.copy()
        logger.info(f"Selected all: {len(self.selected_nodes)} node(s) and {len(self.selected_edges)} edge(s)")
        self._update_plot()

    def _set_modified(self, modified=True):
        """Set modified flag and update window title"""
        self.is_modified = modified
        self._update_window_title()

    def _show_color_context_menu(self, event, node):
        """Show context menu for color selection"""
        # Create context menu
        menu = QMenu(self)

        # Add color options
        for color_name in self.APP_CONFIG.MYCOLORS.keys():
            action = menu.addAction(color_name)
            # Use lambda with default argument to capture color_name
            action.triggered.connect(lambda _, c=color_name, n=node: self._change_node_color(n, c))

        # Show menu at mouse position
        menu.exec(QCursor.pos())

    def _snap_to_grid(self, x, y):
        """Snap coordinates to nearest grid point"""
        rot_rad = np.radians(-self.grid_rotation)
        grid_x = x * np.cos(rot_rad) - y * np.sin(rot_rad)
        grid_y = x * np.sin(rot_rad) + y * np.cos(rot_rad)

        if self.grid_type == "square":
            snap_x = np.round(grid_x / self.grid_spacing) * self.grid_spacing
            snap_y = np.round(grid_y / self.grid_spacing) * self.grid_spacing
        else:
            snap_x, snap_y = self._snap_to_hex(grid_x, grid_y)

        rot_rad = np.radians(self.grid_rotation)
        final_x = snap_x * np.cos(rot_rad) - snap_y * np.sin(rot_rad)
        final_y = snap_x * np.sin(rot_rad) + snap_y * np.cos(rot_rad)

        return final_x, final_y

    def _snap_to_hex(self, x, y):
        """Snap to triangular grid vertices"""
        spacing = self.grid_spacing
        sqrt3 = np.sqrt(3)

        j = np.round(y / (spacing * sqrt3 / 2))
        i = np.round((x - j * spacing / 2) / spacing)

        snap_x = i * spacing + j * spacing / 2
        snap_y = j * spacing * sqrt3 / 2

        return snap_x, snap_y

    def _status_message(self, msg, timeout=3000):
        """Show a transient message in the status bar."""
        self.statusBar().showMessage(msg, timeout)

    def _update_recent_files_menu(self):
        """Update the Recent Files submenu"""
        self.recent_files_menu.clear()

        if not self.recent_files:
            no_recent = QAction("(No recent files)", self)
            no_recent.setEnabled(False)
            self.recent_files_menu.addAction(no_recent)
        else:
            for filepath in self.recent_files:
                action = QAction(Path(filepath).name, self)
                action.setToolTip(filepath)
                action.triggered.connect(lambda checked, f=filepath: self._open_graph_file(f))
                self.recent_files_menu.addAction(action)

            self.recent_files_menu.addSeparator()
            clear_action = QAction("Clear Recent Files", self)
            clear_action.triggered.connect(self._clear_recent_files)
            self.recent_files_menu.addAction(clear_action)

    def resizeEvent(self, event):
        """Handle window resize event - redraw with debouncing to prevent freezing"""
        super().resizeEvent(event)

        # Just restart the debounce timer - _get_xlim() and _get_ylim() already
        # handle aspect ratio adjustments automatically
        self.resize_debounce_timer.stop()
        self.resize_debounce_timer.start(self.resize_debounce_timeout)

    def _nudge_selfloop_label(self, direction):
        """Nudge self-loop label position for selected self-loop edges"""
        if not self.selected_edges:
            return

        self._save_state()

        # Filter to only self-loops
        selfloops = [edge for edge in self.selected_edges if edge.get('is_self_loop', False)]
        if not selfloops:
            return

        for edge in selfloops:
            # Get the node this self-loop is attached to
            from_node_id = edge['from_node_id']
            from_node = next((n for n in self.nodes if n['node_id'] == from_node_id), None)
            if not from_node:
                continue

            node_size_mult = from_node.get('node_size_mult', 1.0)

            # Calculate increment based on node diameter
            base_diameter = 2 * self.node_radius
            diameter = base_diameter * node_size_mult
            increment = 0.02 * diameter

            # Get current nudge (default to (0, 0))
            current_nudge = edge.get('selflooplabelnudge', (0.0, 0.0))
            nudge_x, nudge_y = current_nudge

            # Update nudge based on direction
            if direction == 'left':
                nudge_x -= increment
            elif direction == 'right':
                nudge_x += increment
            elif direction == 'up':
                nudge_y += increment
            elif direction == 'down':
                nudge_y -= increment

            edge['selflooplabelnudge'] = (nudge_x, nudge_y)

        # Print feedback
        if len(selfloops) == 1:
            edge = selfloops[0]
            nudge = edge['selflooplabelnudge']
            logger.debug(f"Self-loop label nudge: ({nudge[0]:.3f}, {nudge[1]:.3f})")
        else:
            logger.debug(f"Nudged labels for {len(selfloops)} self-loop(s)")

        self._update_plot()

    def _reload_last_graph(self):
        """Reload the last saved graph"""
        if not self._check_unsaved_changes():
            return

        if not self.last_graph_path.exists():
            QMessageBox.information(
                self, "No Last Graph",
                "No last graph found."
            )
            return

        try:
            with open(self.last_graph_path, 'r') as f:
                data = json.load(f)

            self._deserialize_graph(data)
            self.current_filepath = None  # Don't set filepath for reloaded last graph
            self._set_modified(False)
            logger.info("Reloaded last graph")

        except Exception as e:
            QMessageBox.critical(
                self, "Error Loading Last Graph",
                f"Could not load last graph:\n{e}"
            )

    def _rotate_selected_nodes(self, angle_degrees):
        """Rotate selected nodes around their centroid

        Args:
            angle_degrees: Rotation angle in degrees. Positive = CCW, Negative = CW
        """
        if not self.selected_nodes:
            logger.info("No nodes selected to rotate")
            return

        self._save_state()

        # Calculate centroid of selected nodes
        positions = np.array([node['pos'] for node in self.selected_nodes])
        centroid = positions.mean(axis=0)

        # Convert angle to radians (negate to match user's expected direction)
        angle_rad = np.radians(-angle_degrees)  # Negate for intuitive CW/CCW
        cos_a = np.cos(angle_rad)
        sin_a = np.sin(angle_rad)

        # Get IDs of selected nodes for self-loop tracking
        selected_node_ids = {node['node_id'] for node in self.selected_nodes}

        # Rotate each node around the centroid
        for node in self.selected_nodes:
            # Get position relative to centroid
            pos = np.array(node['pos'])
            rel_pos = pos - centroid

            # Apply rotation matrix
            new_rel_pos = np.array([
                rel_pos[0] * cos_a - rel_pos[1] * sin_a,
                rel_pos[0] * sin_a + rel_pos[1] * cos_a
            ])

            # Update node position
            node['pos'] = tuple(centroid + new_rel_pos)

        # Rotate self-loop angles for edges attached to selected nodes
        for edge in self.edges:
            if edge.get('is_self_loop', False):
                # Check if this self-loop is attached to a selected node
                if edge['from_node_id'] in selected_node_ids:
                    # Update self-loop angle (negate angle_degrees for correct direction)
                    current_angle = edge.get('selfloopangle', 45)
                    edge['selfloopangle'] = current_angle - angle_degrees  # Subtract for correct rotation

        # Print feedback
        direction = "CCW" if angle_degrees > 0 else "CW"
        if len(self.selected_nodes) == 1:
            logger.debug(f"Rotated node '{self.selected_nodes[0]['label']}' {abs(angle_degrees)}° {direction}")
        else:
            logger.debug(f"Rotated {len(self.selected_nodes)} nodes {abs(angle_degrees)}° {direction} around centroid ({centroid[0]:.2f}, {centroid[1]:.2f})")

        self._update_plot()

    def _change_node_color(self, node, color_key):
        """Change the color of a node (or all selected nodes if multiple selected)"""
        self._save_state()

        # If the clicked node is in selection, change all selected nodes
        if node in self.selected_nodes and len(self.selected_nodes) > 1:
            for selected_node in self.selected_nodes:
                selected_node['color'] = self.APP_CONFIG.MYCOLORS[color_key]
                selected_node['color_key'] = color_key
            logger.debug(f"Changed color of {len(self.selected_nodes)} nodes to {color_key}")
            # Update last_node_props with the first selected node's properties
            last_modified = self.selected_nodes[0]
        else:
            # Change just this node
            node['color'] = self.APP_CONFIG.MYCOLORS[color_key]
            node['color_key'] = color_key
            logger.debug(f"Changed node '{node['label']}' color to {color_key}")
            last_modified = node

        # Update last_node_props so continuous mode inherits these properties
        self.last_node_props = {
            'label': last_modified['label'],
            'color': last_modified['color'],
            'color_key': last_modified['color_key'],
            'node_size_mult': last_modified.get('node_size_mult', 1.0),
            'label_size_mult': last_modified.get('label_size_mult', 1.0),
            'conj': last_modified.get('conj', False)
        }

        self._update_plot()

    def _load_recent_files(self):
        """Load recent files list from disk"""
        try:
            if self.recent_files_path.exists():
                with open(self.recent_files_path, 'r') as f:
                    self.recent_files = [line.strip() for line in f if line.strip()]
                # Keep only files that still exist
                self.recent_files = [f for f in self.recent_files if Path(f).exists()]
                self.recent_files = self.recent_files[:self.max_recent_files]
        except Exception as e:
            logger.error(f"Error loading recent files: {e}")
            self.recent_files = []

    def _draw_square_grid(self):
        """Draw rotated square grid"""
        spacing = self.grid_spacing
        rot_rad = np.radians(self.grid_rotation)

        xlim = self._get_xlim()
        ylim = self._get_ylim()
        # Build over a generous extent so ordinary zoom-out stays covered without
        # a rebuild (the fast view path rebuilds it only if the view grows beyond).
        max_extent = max(abs(xlim[0]), abs(xlim[1]), abs(ylim[0]), abs(ylim[1])) * 3.0
        self._grid_built_extent = max_extent
        n = int(max_extent / spacing) + 2

        for i in range(-n, n + 1):
            offset = i * spacing

            # Vertical lines
            x1 = offset * np.cos(rot_rad) - max_extent * np.sin(rot_rad)
            y1 = offset * np.sin(rot_rad) + max_extent * np.cos(rot_rad)
            x2 = offset * np.cos(rot_rad) + max_extent * np.sin(rot_rad)
            y2 = offset * np.sin(rot_rad) - max_extent * np.cos(rot_rad)
            line, = self.canvas.ax.plot([x1, x2], [y1, y2], 'lightgray', lw=0.5, zorder=0)
            line.set_gid('grid')

            # Horizontal lines
            x1 = -max_extent * np.cos(rot_rad) + offset * np.sin(rot_rad)
            y1 = -max_extent * np.sin(rot_rad) - offset * np.cos(rot_rad)
            x2 = max_extent * np.cos(rot_rad) + offset * np.sin(rot_rad)
            y2 = max_extent * np.sin(rot_rad) - offset * np.cos(rot_rad)
            line, = self.canvas.ax.plot([x1, x2], [y1, y2], 'lightgray', lw=0.5, zorder=0)
            line.set_gid('grid')

    def _adjust_edge_label_offset(self, direction):
        """Adjust edge label offset for selected edges using Shift+Up/Down"""
        if not self.selected_edges:
            return

        self._save_state()
        increment = 0.05  # Smaller increment (half of 0.1)

        for edge in self.selected_edges:
            if direction == 'up':
                # Increase label offset
                current = edge.get('label_offset_mult', 0.8)
                edge['label_offset_mult'] = min(current + increment, 2.0)
            elif direction == 'down':
                # Decrease label offset
                current = edge.get('label_offset_mult', 0.8)
                edge['label_offset_mult'] = max(current - increment, 0.1)

        # Print feedback
        if len(self.selected_edges) == 1:
            edge = self.selected_edges[0]
            logger.debug(f"Edge label offset: {edge['label_offset_mult']:.1f}")
        else:
            logger.debug(f"Adjusted label offset for {len(self.selected_edges)} edge(s)")

        self._update_plot()

    def _adjust_edge_rotation(self, direction):
        """Adjust edge label rotation angle by ±5 degrees"""
        if not self.selected_edges:
            return

        self._save_state()
        increment = 5  # degrees

        for edge in self.selected_edges:
            current_rotation = edge.get('label_rotation_offset', 0)

            if direction == 'left':
                edge['label_rotation_offset'] = current_rotation - increment
            elif direction == 'right':
                edge['label_rotation_offset'] = current_rotation + increment

        # Print feedback
        if len(self.selected_edges) == 1:
            edge = self.selected_edges[0]
            rotation = edge.get('label_rotation_offset', 0)
            logger.debug(f"Edge label rotation: {rotation:+d}°")
        else:
            logger.debug(f"Adjusted rotation for {len(self.selected_edges)} edge(s)")

        self._update_plot()

    def _parse_prettynode_label(self, label):
        """Parse label into mode and subscript for prettynode, or return None if not applicable"""
        import re
        # Check if label matches pattern: single letter (A-F) optionally followed by subscript
        match = re.match(r'^([A-F])(.*)$', label)
        if match:
            mode = match.group(1)
            sub = match.group(2)
            return mode, sub
        return None

    def _clear_nodes(self):
        """Clear all nodes"""
        self.nodes = []
        self.node_counter = 0
        logger.info("All nodes cleared")
        self._update_plot()

    def _toggle_continuous_mode(self):
        """Toggle continuous placement mode"""
        if self.placement_mode == 'continuous':
            self.placement_mode = None
            logger.debug("Exited continuous placement mode")
        else:
            self.placement_mode = 'continuous'
            logger.debug("Continuous placement mode - click to place nodes, press G again to exit")
        self._update_plot()

    def _set_placement_mode(self, mode):
        """Set placement mode"""
        self.placement_mode = mode
        logger.debug(f"Placement mode: {mode}")
        self._update_plot()

    def _toggle_edge_rotation_mode(self):
        """Toggle edge label rotation mode (Shift+F)"""
        if not self.selected_edges:
            logger.debug("Select an edge to adjust label rotation")
            return

        self.edge_rotation_mode = not self.edge_rotation_mode

        if self.edge_rotation_mode:
            logger.debug("Edge rotation mode: Use Left/Right arrows to adjust label angle (±5°)")
        else:
            logger.debug("Exited edge rotation mode")

    def _save_recent_files(self):
        """Save recent files list to disk"""
        try:
            with open(self.recent_files_path, 'w') as f:
                for filepath in self.recent_files:
                    f.write(f"{filepath}\n")
        except Exception as e:
            logger.error(f"Error saving recent files: {e}")

    def _toggle_latex_mode(self):
        """Toggle between MathText and LaTeX rendering"""
        self.use_latex = not self.use_latex
        matplotlib.rcParams['text.usetex'] = self.use_latex

        if self.use_latex:
            # Set up LaTeX preamble with sfmath for bold sans-serif fonts
            matplotlib.rcParams['text.latex.preamble'] = r'\usepackage{amsmath}\usepackage{sfmath}\renewcommand{\familydefault}{\sfdefault}'
        else:
            # Reset to MathText mode
            matplotlib.rcParams['text.latex.preamble'] = ''
            matplotlib.rcParams['mathtext.fontset'] = 'stix'
            matplotlib.rcParams['font.family'] = 'STIXGeneral'

        # Drop cached glyph paths (the global LaTeX preamble/fontset just changed).
        self._label_cache.clear()

        render_mode = "LaTeX" if self.use_latex else "MathText"
        logger.info(f"Rendering mode: {render_mode}")
        self._update_plot()

    def _handle_resize_complete(self):
        """Called when resize debounce timer completes - redraw the plot"""
        # The _get_xlim() and _get_ylim() functions automatically adjust limits
        # to match canvas aspect ratio, so we just need to trigger a redraw
        canvas_width = self.canvas.size().width()
        canvas_height = self.canvas.size().height()

        if canvas_height > 0 and canvas_width > 0:
            logger.debug("" + "="*60)
            logger.debug("WINDOW RESIZE COMPLETE - Redrawing")
            logger.debug("="*60)
            logger.debug(f"Canvas size: {canvas_width} x {canvas_height}")
            logger.debug(f"Canvas aspect ratio: {canvas_width/canvas_height:.3f}")
            xlim = self._get_xlim()
            ylim = self._get_ylim()
            logger.debug(f"Calculated xlim: [{xlim[0]:.2f}, {xlim[1]:.2f}]")
            logger.debug(f"Calculated ylim: [{ylim[0]:.2f}, {ylim[1]:.2f}]")
            logger.debug("="*60 + "\n")

            self._update_plot()

    def _undo(self):
        """Undo last action"""
        if not self.undo_stack:
            logger.info("Nothing to undo")
            self._status_message("Nothing to undo")
            return

        self.redo_stack.append(self._capture_state())
        self._restore_state(self.undo_stack.pop())
        logger.info(f"Undo - restored to {len(self.nodes)} node(s) and {len(self.edges)} edge(s)")

    def _redo(self):
        """Redo the last undone action"""
        if not self.redo_stack:
            logger.info("Nothing to redo")
            self._status_message("Nothing to redo")
            return

        self.undo_stack.append(self._capture_state())
        self._restore_state(self.redo_stack.pop())
        logger.info(f"Redo - restored to {len(self.nodes)} node(s) and {len(self.edges)} edge(s)")
