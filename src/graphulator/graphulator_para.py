"""
Graphulator Para - Interactive Graph Drawing Tool
Advanced GUI for creating coupled mode theory graphs using PySide6. Modified from Graphulator (graphulator_qt.py) to focus on parametric graphs and associated Kron reduction and scattering calculations.

"""

import html as html_module
import json
import logging
import os
import re
import sys
import time
import traceback
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import seaborn as sns

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QGridLayout, QDialog, QLabel, QLineEdit,
                               QComboBox, QPushButton, QDialogButtonBox, QCheckBox,
                               QSplitter, QGroupBox, QSlider, QSpinBox, QDoubleSpinBox,
                               QFormLayout, QColorDialog, QMenu, QTextEdit, QFileDialog,
                               QMessageBox, QMenuBar, QTabWidget, QScrollArea, QRadioButton,
                               QPlainTextEdit, QButtonGroup, QFrame)
from PySide6.QtCore import Qt, Signal, QTimer, QThread, QSize, QRect, QUrl, QEvent
from PySide6.QtGui import (QKeySequence, QShortcut, QColor, QCursor, QAction,
                           QFont, QPainter, QTextFormat, QIcon)
from PySide6.QtWebEngineWidgets import QWebEngineView

import matplotlib
matplotlib.use('QtAgg')
# Use MathText instead of LaTeX for faster rendering
matplotlib.rcParams['text.usetex'] = False
matplotlib.rcParams['mathtext.fontset'] = 'stix'  # STIX fonts look similar to LaTeX
matplotlib.rcParams['font.family'] = 'STIXGeneral'

# Suppress matplotlib warnings about adjusting limits for aspect ratio
warnings.filterwarnings('ignore', message='.*fixed.*limits.*aspect.*', category=UserWarning)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT
from matplotlib.figure import Figure
import matplotlib.patches as patches

import sympy as sp
from sympy import Symbol, Matrix, simplify, latex, Abs, conjugate, Mul, Add, Pow, cancel
from sympy import fraction, expand, factor_terms
from sympy.printing.latex import LatexPrinter
from sympy.core.mul import Mul as MulType
from sympy.functions.elementary.complexes import conjugate as Conjugate

# Import modules (relative imports for package)
from . import graph_primitives as gp
from . import graphulator_para_config as config

# Import refactored modules
from .para_ui.widgets import (
    ConsoleRedirector, FineControlSpinBox, LineNumberArea,
    LineNumberTextEdit, AspectRatioWidget
)
from .para_features.sympy_utils import (
    CustomLaTeXPrinter, latex_custom, latex_matrix_factored, normalize_matrix_latex
)
from .para_rendering.latex_render import MatrixRenderWorker
from .para_rendering.katex_templates import (
    render_matrix_html, render_basis_html, render_placeholder_html
)
from .para_ui.dialogs import NodeInputDialog, EdgeInputDialog
from .para_ui.canvas import MplCanvas
from .para_ui.web_views import ZoomableWebView
from .para_ui.shortcut_manager import ShortcutManager
from .para_ui.doc_template import CachedDocumentationProcessor
from .para_core.settings_manager import (
    SettingsManager, get_settings_manager,
    USER_SETTINGS_DIR, USER_SETTINGS_FILE
)
from .para_core.interaction_state import InteractionMode, PlacementMode

logger = logging.getLogger(__name__)

EXPORT_RESCALE_DEFAULTS = {
    'NODELABELSCALE': 1.000,
    'SLCC': 0.650,
    'SELFLOOP_LABELSCALE': 0.140,
    'SLLW': 6.000,
    'SLSC': 0.900,
    'SLLNOFFSET': (0.0, 0.0),
    'SELFLOOP_LABELNUDGE_SCALE': 1.100,
    'EDGEFONTSCALE': 0.850,
    'EDGELWSCALE': 2.700,
    'EDGELABELOFFSET': 1.000,
    'GUI_SELFLOOP_LABEL_SCALE': 1.300,
    'EXPORT_SELFLOOP_LABEL_DISTANCE': 1.000,
}

# =============================================================================
# SETTINGS DIALOG PARAMETER DEFINITIONS
# =============================================================================

# Settings parameter definitions for the Settings Dialog
# Format: {tab_name: [(config_attr, display_name, type, min, max, step), ...]}
# Types: 'float', 'int', 'color', 'bool'
SETTINGS_PARAMS = {
    'Node & Edge Defaults': [
        # (param_name, display_name, type, min/options, max, step)
        # For 'dropdown' type: min/options is list of (display_name, value) tuples or list of values
        # --- Node settings ---
        ('DEFAULT_NODE_COLOR_KEY', 'Node Color', 'dropdown', 'MYCOLORS_KEYS', None, None),
        ('DEFAULT_NODE_RADIUS', 'Node Base Radius', 'float', 0.1, 2.0, 0.1),
        ('DEFAULT_NODE_SIZE_MULT', 'Node Size Scale (×)', 'float', 0.5, 3.0, 0.1),
        ('DEFAULT_NODE_LABEL_SIZE_MULT', 'Node Label Scale (×)', 'float', 0.5, 3.0, 0.1),
        ('DEFAULT_NODE_OUTLINE_ENABLED', 'Show Node Outline', 'bool', None, None, None),
        ('DEFAULT_NODE_OUTLINE_COLOR_KEY', 'Outline Color', 'dropdown', 'MYCOLORS_KEYS', None, None),
        ('DEFAULT_NODE_OUTLINE_WIDTH', 'Outline Width', 'float', 0.5, 5.0, 0.5),
        ('DEFAULT_NODE_OUTLINE_ALPHA', 'Outline Opacity', 'float', 0.0, 1.0, 0.1),
        # --- Edge settings ---
        ('DEFAULT_EDGE_LINEWIDTH_MULT', 'Edge Line Width (×)', 'float', 0.5, 3.0, 0.25),
        # Note: Edge Style and Direction are auto-determined from node conjugation states
    ],
    'Self-Loop Defaults': [
        ('DEFAULT_SELFLOOP_SCALE', 'Size Scale', 'float', 0.5, 2.0, 0.1),
        ('DEFAULT_SELFLOOP_ARROWLENGTH', 'Linewidth', 'float', 0.5, 3.0, 0.1),
        ('DEFAULT_SELFLOOP_ANGLE', 'Default Angle', 'dropdown', [
            ('0° (Right)', 0), ('45° (Up-Right)', 45), ('90° (Up)', 90),
            ('135° (Up-Left)', 135), ('180° (Left)', 180), ('225° (Down-Left)', 225),
            ('270° (Down)', 270), ('315° (Down-Right)', 315)
        ], None, None),
    ],
    'S-Parameter Plot': [
        ('SPARAMS_FONT_SCALE', 'Master Font Scale', 'float', 0.1, 3.0, 0.1),
        ('SPARAMS_LEGEND_FONTSIZE_SCALE', 'Legend Font Scale', 'float', 0.1, 3.0, 0.1),
        ('SPARAMS_PLOT_LINEWIDTH', 'Line Width', 'float', 0.5, 5.0, 0.5),
        ('SPARAMS_FREQ_ROW_Y_START', 'Freq Row Y Start', 'float', -0.2, 0.0, 0.01),
        ('SPARAMS_FREQ_ROW_Y_SPACING', 'Freq Row Spacing', 'float', 0.01, 0.2, 0.01),
        ('SPARAMS_PORT_LABEL_X', 'Port Label X Offset', 'float', -0.2, 0.0, 0.01),
        ('SPARAMS_XLABEL_Y_OFFSET', 'X-Label Y Offset', 'float', -0.2, 0.1, 0.01),
        ('SPARAMS_PLOT_BACKGROUND_COLOR', 'Background Color', 'color', None, None, None),
        ('SPARAMS_PLOT_GRID_COLOR', 'Grid Color', 'color', None, None, None),
    ],
    'Export Scaling': [
        ('GUI_SELFLOOP_LABEL_SCALE', 'GUI Self-loop Label Distance', 'float', 0.1, 5.0, 0.1),
        ('EXPORT_SELFLOOP_LABEL_DISTANCE', 'Export Self-loop Label Distance', 'float', 0.1, 5.0, 0.1),
        ('NODELABELSCALE', 'Node Label Scale', 'float', 0.1, 2.0, 0.05),
        ('SELFLOOP_LABELSCALE', 'Self-loop Label Size', 'float', 0.01, 2.0, 0.01),
        ('SLLW', 'Self-loop Linewidth', 'float', 0.1, 8.0, 0.1),
        ('SLSC', 'Self-loop Scale', 'float', 0.1, 3.0, 0.1),
        ('SELFLOOP_LABELNUDGE_SCALE', 'Self-loop Label Nudge Scale', 'float', 0.1, 3.0, 0.1),
        ('EDGEFONTSCALE', 'Edge Label Font Scale', 'float', 0.1, 5.0, 0.1),
        ('EDGELWSCALE', 'Edge Linewidth Scale', 'float', 0.1, 5.0, 0.1),
        ('EDGELABELOFFSET', 'Edge Label Offset', 'float', 0.1, 3.0, 0.05),
    ],
}


def _get_original_config_value(param_name):
    """Get the original value from the config module (as defined in code)."""
    return get_settings_manager().get_original_config_value(param_name)


def load_user_settings():
    """Load user settings from ~/.graphulator/settings.json and apply to config module."""
    return get_settings_manager().load()


def save_user_settings(settings_dict):
    """Save settings to ~/.graphulator/settings.json."""
    return get_settings_manager().save(settings_dict)


def delete_user_settings():
    """Delete the user settings file to reset to defaults."""
    return get_settings_manager().delete()


def sync_dialog_defaults_from_config():
    """Update dialog class variables from current config values.

    This function should be called:
    1. After load_user_settings() in Graphulator.__init__
    2. After settings are applied in SettingsDialog

    This ensures dialog defaults reflect the current config values,
    whether loaded from user settings file or changed via Settings dialog.
    """
    # Update NodeInputDialog defaults
    NodeInputDialog.last_color = config.DEFAULT_NODE_COLOR_KEY
    NodeInputDialog.last_node_size = config.DEFAULT_NODE_SIZE_MULT
    NodeInputDialog.last_label_size = config.DEFAULT_NODE_LABEL_SIZE_MULT
    NodeInputDialog.last_conj = config.DEFAULT_NODE_CONJUGATED
    NodeInputDialog.last_outline_enabled = config.DEFAULT_NODE_OUTLINE_ENABLED
    NodeInputDialog.last_outline_color = getattr(config, 'DEFAULT_NODE_OUTLINE_COLOR_KEY', 'BLACK')
    NodeInputDialog.last_outline_width = config.DEFAULT_NODE_OUTLINE_WIDTH
    NodeInputDialog.last_outline_alpha = config.DEFAULT_NODE_OUTLINE_ALPHA

    # Update EdgeInputDialog defaults
    # Map linewidth multiplier back to name
    linewidth_mult = config.DEFAULT_EDGE_LINEWIDTH_MULT
    linewidth_name = 'Medium'  # default
    for name, mult in config.EDGE_LINEWIDTH_OPTIONS.items():
        if abs(mult - linewidth_mult) < 0.01:
            linewidth_name = name
            break
    EdgeInputDialog.last_linewidth = linewidth_name
    EdgeInputDialog.last_direction = config.DEFAULT_EDGE_DIRECTION

    # Note: Self-loop defaults (DEFAULT_SELFLOOP_SCALE, DEFAULT_SELFLOOP_ANGLE)
    # are read directly from config in EdgeInputDialog when creating self-loops


class PropertiesPanel(QWidget):
    """Properties panel for selected objects"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.graphulator = parent
        self.current_object = None  # Currently displayed object (node or edge)
        self.current_type = None  # 'node', 'edge', or None
        self._matrix_render_worker = None  # Worker thread for async matrix rendering

        # Debounce timer for scattering parameter updates
        # This allows spinbox hold-to-repeat to work by not blocking the event loop
        self._scattering_update_timer = QTimer(self)
        self._scattering_update_timer.setSingleShot(True)
        self._scattering_update_timer.timeout.connect(self._do_scattering_update)
        self._pending_node_opacity_updates = set()  # Node IDs needing opacity update

        # Create main layout
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # Create tab widget
        self.tabs = QTabWidget()
        # Don't steal focus/scroll from canvas when interacting with panel
        self.tabs.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        main_layout.addWidget(self.tabs, stretch=1)

        # Tab 0: Properties
        properties_tab = QWidget()
        properties_tab_layout = QVBoxLayout()
        properties_tab.setLayout(properties_tab_layout)

        # Title label
        self.title_label = QLabel("No Selection")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        properties_tab_layout.addWidget(self.title_label)

        # Properties container (will be replaced based on selection)
        self.properties_widget = QWidget()
        self.properties_layout = QVBoxLayout()
        self.properties_widget.setLayout(self.properties_layout)
        properties_tab_layout.addWidget(self.properties_widget)

        properties_tab_layout.addStretch()

        self.tabs.addTab(properties_tab, "Properties")

        # Tab 1: Notes (with Edit/Preview subtabs)
        self._create_notes_tab()

        # Tab 2: Symbolic (with Matrix/Basis/Code subtabs)
        self._create_symbolic_tab()

        # Tab 3: Scattering
        self._create_scattering_tab()

        # Tab 4: Console Output
        self._create_console_tab()

        # Help button removed - now available from menu bar

        # Set minimum width (increased for Scattering tab parameter table)
        # self.setMinimumWidth(580)
        self.setMinimumWidth(650)

    def _create_console_tab(self):
        """Create the console output tab"""

        console_tab = QWidget()
        console_layout = QVBoxLayout()
        console_tab.setLayout(console_layout)

        # Add title
        title = QLabel("Console Output")
        title.setStyleSheet("font-weight: bold; font-size: 11px;")
        console_layout.addWidget(title)

        # Create text display for console output
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setFont(QFont("Courier", 10))
        self.console_output.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        console_layout.addWidget(self.console_output, stretch=1)

        # Add clear button
        clear_btn = QPushButton("Clear Console")
        clear_btn.clicked.connect(lambda: self.console_output.clear())
        console_layout.addWidget(clear_btn)

        self.tabs.addTab(console_tab, "Console")

    def _get_katex_dir(self):
        """Get the path to the KaTeX directory.

        Works both in development mode and PyInstaller bundles.
        Returns a Path object or None if not found.
        """
        if hasattr(self, '_katex_dir_cached'):
            return self._katex_dir_cached

        # Try to find KaTeX directory
        is_frozen = getattr(sys, 'frozen', False)

        # 1. Check relative to this file (development mode)
        script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        katex_dir = script_dir / 'katex'

        if not katex_dir.exists():
            # 2. Check in PyInstaller bundle location
            if is_frozen:
                # Running in PyInstaller bundle
                bundle_dir = Path(sys._MEIPASS)
                katex_dir = bundle_dir / 'graphulator' / 'katex'

        if katex_dir.exists():
            self._katex_dir_cached = katex_dir.resolve()
        else:
            self._katex_dir_cached = None

        return self._katex_dir_cached

    def _get_katex_base_qurl(self):
        """Get the base QUrl for KaTeX files (for use with setHtml baseUrl)."""
        katex_dir = self._get_katex_dir()
        if katex_dir:
            return QUrl.fromLocalFile(str(katex_dir) + '/')
        return QUrl()

    def _get_katex_html_header(self):
        """Get the HTML header for KaTeX rendering.

        Returns the CSS and JS includes needed for KaTeX.
        Uses relative paths - must be used with _get_katex_base_qurl() as baseUrl.
        """
        katex_dir = self._get_katex_dir()
        if katex_dir:
            # Use relative paths - will be resolved against baseUrl
            return '''
    <link rel="stylesheet" href="katex.min.css">
    <script src="katex.min.js"></script>
    <script src="contrib/auto-render.min.js"></script>'''
        else:
            # Fallback to CDN if local files not found
            return '''
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>'''

    def _get_katex_html_header_absolute(self):
        """Get the HTML header for KaTeX rendering with absolute file:// URLs.

        Use this when loading HTML from a temp file outside the KaTeX directory.
        """
        katex_dir = self._get_katex_dir()
        if katex_dir:
            # Use absolute file:// URLs
            # Convert to forward slashes and handle path prefix correctly
            katex_path = str(katex_dir).replace('\\', '/')
            # On Unix, paths start with /, so file:// + /path = file:///path (correct)
            # On Windows, paths are like C:/path, so file:/// + C:/path = file:///C:/path (correct)
            if katex_path.startswith('/'):
                file_url_prefix = 'file://'
            else:
                file_url_prefix = 'file:///'
            return f'''
    <link rel="stylesheet" href="{file_url_prefix}{katex_path}/katex.min.css">
    <script src="{file_url_prefix}{katex_path}/katex.min.js"></script>
    <script src="{file_url_prefix}{katex_path}/contrib/auto-render.min.js"></script>'''
        else:
            # Fallback to CDN if local files not found
            return '''
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>'''

    def _get_latex_context_menu_js(self):
        """Get JavaScript and CSS for right-click 'Copy LaTeX' context menu.

        Returns a string containing <style> and <script> tags that implement
        a custom context menu for copying LaTeX from rendered math elements.
        The calling code must add a data-latex attribute to the element.
        """
        return '''
    <style>
        #latex-context-menu {
            display: none;
            position: fixed;
            z-index: 10000;
            background: white;
            border: 1px solid #ccc;
            border-radius: 4px;
            box-shadow: 2px 2px 8px rgba(0,0,0,0.2);
            padding: 4px 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            font-size: 13px;
            min-width: 120px;
        }
        #latex-context-menu.visible {
            display: block;
        }
        .context-menu-item {
            padding: 6px 16px;
            cursor: pointer;
            color: #333;
        }
        .context-menu-item:hover {
            background: #e8e8e8;
        }
        #copy-feedback {
            display: none;
            position: fixed;
            z-index: 10001;
            background: rgba(0,0,0,0.75);
            color: white;
            padding: 8px 16px;
            border-radius: 4px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            font-size: 13px;
        }
        #copy-feedback.visible {
            display: block;
        }
    </style>
    <div id="latex-context-menu">
        <div class="context-menu-item" id="copy-latex-btn">Copy LaTeX</div>
    </div>
    <div id="copy-feedback">Copied!</div>
    <script>
    (function() {
        const menu = document.getElementById('latex-context-menu');
        const copyBtn = document.getElementById('copy-latex-btn');
        const feedback = document.getElementById('copy-feedback');
        let currentLatex = '';

        // Find element with data-latex attribute
        function findLatexElement(target) {
            let el = target;
            while (el && el !== document.body) {
                if (el.hasAttribute && el.hasAttribute('data-latex')) {
                    return el;
                }
                el = el.parentElement;
            }
            // Check if any parent container has it
            const containers = document.querySelectorAll('[data-latex]');
            for (let c of containers) {
                if (c.contains(target)) {
                    return c;
                }
            }
            return null;
        }

        // Show context menu on right-click
        document.addEventListener('contextmenu', function(e) {
            const latexEl = findLatexElement(e.target);
            if (latexEl) {
                e.preventDefault();
                currentLatex = latexEl.getAttribute('data-latex');
                menu.style.left = e.clientX + 'px';
                menu.style.top = e.clientY + 'px';
                menu.classList.add('visible');
            }
        });

        // Hide menu on click elsewhere
        document.addEventListener('click', function() {
            menu.classList.remove('visible');
        });

        // Hide menu on escape
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                menu.classList.remove('visible');
            }
        });

        // Copy text to clipboard with fallback for non-secure contexts
        function copyToClipboard(text) {
            // Try modern clipboard API first
            if (navigator.clipboard && navigator.clipboard.writeText) {
                return navigator.clipboard.writeText(text).catch(function() {
                    // Fall back to execCommand
                    return fallbackCopy(text);
                });
            }
            // Use fallback directly
            return fallbackCopy(text);
        }

        function fallbackCopy(text) {
            return new Promise(function(resolve, reject) {
                const textarea = document.createElement('textarea');
                textarea.value = text;
                textarea.style.position = 'fixed';
                textarea.style.left = '-9999px';
                textarea.style.top = '0';
                document.body.appendChild(textarea);
                textarea.focus();
                textarea.select();
                try {
                    const success = document.execCommand('copy');
                    document.body.removeChild(textarea);
                    if (success) {
                        resolve();
                    } else {
                        reject(new Error('execCommand copy failed'));
                    }
                } catch (err) {
                    document.body.removeChild(textarea);
                    reject(err);
                }
            });
        }

        // Copy LaTeX when clicked
        copyBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            if (currentLatex) {
                copyToClipboard(currentLatex).then(function() {
                    // Show feedback near the menu
                    feedback.style.left = menu.style.left;
                    feedback.style.top = (parseInt(menu.style.top) - 30) + 'px';
                    feedback.classList.add('visible');
                    setTimeout(function() {
                        feedback.classList.remove('visible');
                    }, 1000);
                }).catch(function(err) {
                    console.error('Failed to copy: ', err);
                });
            }
            menu.classList.remove('visible');
        });
    })();
    </script>'''

    def _create_notes_tab(self):
        """Create the notes tab with Edit/Preview subtabs"""
        notes_tab = QWidget()
        notes_layout = QVBoxLayout()
        notes_tab.setLayout(notes_layout)

        # Create sub-tabs for Edit and Preview
        self.notes_subtabs = QTabWidget()
        self.notes_subtabs.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        notes_layout.addWidget(self.notes_subtabs)

        # Edit subtab with LineNumberTextEdit
        edit_widget = QWidget()
        edit_layout = QVBoxLayout()
        edit_layout.setContentsMargins(0, 0, 0, 0)
        edit_widget.setLayout(edit_layout)

        self.notes_editor = LineNumberTextEdit()
        self.notes_editor.setPlaceholderText("Enter notes here (supports Markdown and LaTeX math: $...$ or $$...$$)")
        edit_layout.addWidget(self.notes_editor)

        self.notes_subtabs.addTab(edit_widget, "Edit")

        # Preview subtab with ZoomableWebView for markdown + LaTeX rendering
        preview_widget = QWidget()
        preview_layout = QVBoxLayout()
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_widget.setLayout(preview_layout)

        self.notes_preview = ZoomableWebView()
        self.notes_preview.setHtml("<html><body><p style='color: #888;'>Preview will appear here when you switch to this tab.</p></body></html>")
        preview_layout.addWidget(self.notes_preview)

        self.notes_subtabs.addTab(preview_widget, "Preview")

        # Update preview when switching to Preview tab
        self.notes_subtabs.currentChanged.connect(self._on_notes_subtab_changed)

        self.tabs.addTab(notes_tab, "Notes")

    def _on_notes_subtab_changed(self, index):
        """Handle notes subtab change - render preview when switching to Preview tab"""
        if index == 1:  # Preview tab
            self._render_notes_preview()

    def _render_notes_preview(self):
        """Render markdown notes with KaTeX LaTeX support (fast, offline-capable)"""

        markdown_text = self.notes_editor.toPlainText()

        # Protect math blocks from HTML escaping and markdown processing
        # Extract and replace with placeholders, then restore after processing
        # Use a placeholder without underscores/asterisks to avoid markdown processing
        math_blocks = {}
        math_counter = [0]  # Use list for mutable counter in nested function

        def protect_math(match):
            placeholder = f"MATHBLOCK{math_counter[0]:04d}ENDMATH"
            math_counter[0] += 1
            math_blocks[placeholder] = match.group(0)
            return placeholder

        # Protect display math first ($$...$$), then inline math ($...$)
        # Use DOTALL to match multiline display math
        text = re.sub(r'\$\$(.+?)\$\$', protect_math, markdown_text, flags=re.DOTALL)
        text = re.sub(r'\$([^\$\n]+?)\$', protect_math, text)

        # Also protect \[...\] and \(...\) style delimiters
        text = re.sub(r'\\\[(.+?)\\\]', protect_math, text, flags=re.DOTALL)
        text = re.sub(r'\\\((.+?)\\\)', protect_math, text)

        # Now escape HTML on the non-math parts
        text = html_module.escape(text)

        # Process code blocks first (before other transformations)
        # Fenced code blocks: ```language\ncode\n```
        def code_block_replacer(match):
            lang = match.group(1) or ''
            code = match.group(2)
            return f'<pre><code class="{lang}">{code}</code></pre>'
        text = re.sub(r'```(\w*)\n(.*?)\n```', code_block_replacer, text, flags=re.DOTALL)

        # Inline code: `code`
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)

        # Headers: # ## ### etc
        text = re.sub(r'^###### (.+)$', r'<h6>\1</h6>', text, flags=re.MULTILINE)
        text = re.sub(r'^##### (.+)$', r'<h5>\1</h5>', text, flags=re.MULTILINE)
        text = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', text, flags=re.MULTILINE)
        text = re.sub(r'^### (.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
        text = re.sub(r'^## (.+)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
        text = re.sub(r'^# (.+)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)

        # Bold: **text** or __text__
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)

        # Italic: *text* or _text_
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        text = re.sub(r'_(.+?)_', r'<em>\1</em>', text)

        # Strikethrough: ~~text~~
        text = re.sub(r'~~(.+?)~~', r'<del>\1</del>', text)

        # Horizontal rule: --- or ***
        text = re.sub(r'^[-*]{3,}$', r'<hr>', text, flags=re.MULTILINE)

        # Blockquote: > text
        text = re.sub(r'^> (.+)$', r'<blockquote>\1</blockquote>', text, flags=re.MULTILINE)

        # Unordered list: - item or * item
        text = re.sub(r'^[-*] (.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)
        text = re.sub(r'(<li>.*</li>\n?)+', r'<ul>\g<0></ul>', text)

        # Links: [text](url)
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)

        # Line breaks: convert newlines to <br> (except after block elements)
        lines = text.split('\n')
        result_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped and not any(stripped.startswith(tag) for tag in ['<h', '<pre', '<ul', '<li', '<blockquote', '<hr']):
                result_lines.append(line)
            else:
                result_lines.append(line)
        text = '<br>\n'.join(result_lines)

        # Restore math blocks (they were never HTML-escaped)
        for placeholder, math in math_blocks.items():
            text = text.replace(placeholder, math)

        # Get KaTeX header (CSS and JS includes)
        katex_header = self._get_katex_html_header()

        # Create HTML with KaTeX for LaTeX (much faster than MathJax)
        html_content = f'''<!DOCTYPE html>
<html>
<head>
    {katex_header}
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            font-size: 14px;
            line-height: 1.6;
            padding: 15px;
            max-width: 800px;
            color: #333;
        }}
        h1, h2, h3, h4, h5, h6 {{
            margin-top: 1em;
            margin-bottom: 0.5em;
            color: #222;
        }}
        h1 {{ font-size: 1.8em; border-bottom: 1px solid #eee; padding-bottom: 0.3em; }}
        h2 {{ font-size: 1.5em; border-bottom: 1px solid #eee; padding-bottom: 0.3em; }}
        h3 {{ font-size: 1.3em; }}
        code {{
            background: #f4f4f4;
            padding: 2px 5px;
            border-radius: 3px;
            font-family: "Menlo", "Monaco", "Consolas", monospace;
            font-size: 0.9em;
        }}
        pre {{
            background: #f4f4f4;
            padding: 10px;
            border-radius: 5px;
            overflow-x: auto;
        }}
        pre code {{
            background: none;
            padding: 0;
        }}
        blockquote {{
            border-left: 4px solid #ddd;
            margin: 0;
            padding-left: 15px;
            color: #666;
        }}
        ul {{
            padding-left: 25px;
        }}
        li {{
            margin: 5px 0;
        }}
        a {{
            color: #0066cc;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        hr {{
            border: none;
            border-top: 1px solid #ddd;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
{text}
<script>
    // Render all LaTeX in the document using KaTeX auto-render
    document.addEventListener("DOMContentLoaded", function() {{
        renderMathInElement(document.body, {{
            delimiters: [
                {{left: "$$", right: "$$", display: true}},
                {{left: "$", right: "$", display: false}},
                {{left: "\\\\[", right: "\\\\]", display: true}},
                {{left: "\\\\(", right: "\\\\)", display: false}}
            ],
            throwOnError: false
        }});
    }});
</script>
</body>
</html>'''

        self.notes_preview.setHtml(html_content, self._get_katex_base_qurl())

    def _create_symbolic_tab(self):
        """Create the Symbolic tab with Matrix/Basis/Code subtabs"""
        symbolic_tab = QWidget()
        symbolic_layout = QVBoxLayout()
        symbolic_layout.setContentsMargins(0, 0, 0, 0)
        symbolic_tab.setLayout(symbolic_layout)

        # Create sub-tabs for Matrix, Basis, and Code
        self.symbolic_subtabs = QTabWidget()
        self.symbolic_subtabs.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        symbolic_layout.addWidget(self.symbolic_subtabs)

        # Create the subtabs (these methods now add to symbolic_subtabs)
        self._create_matrix_tab()  # Index 0
        self._create_basis_tab()   # Index 1
        self._create_sympy_code_tab()  # Index 2

        self.tabs.addTab(symbolic_tab, "Symbolic")

    def _create_basis_tab(self):
        """Create the basis display tab"""
        basis_tab = QWidget()
        basis_layout = QVBoxLayout()
        basis_tab.setLayout(basis_layout)

        # Title
        # Title and zoom controls in a horizontal layout
        title_zoom_layout = QHBoxLayout()

        title = QLabel("Current Basis Order")
        title.setStyleSheet("font-weight: bold; font-size: 11px;")
        title_zoom_layout.addWidget(title)

        title_zoom_layout.addStretch()

        # Zoom controls for basis display
        zoom_out_basis_btn = QPushButton("-")
        zoom_out_basis_btn.setMaximumWidth(30)
        zoom_out_basis_btn.setToolTip("Zoom out (25%)")
        title_zoom_layout.addWidget(zoom_out_basis_btn)

        zoom_in_basis_btn = QPushButton("+")
        zoom_in_basis_btn.setMaximumWidth(30)
        zoom_in_basis_btn.setToolTip("Zoom in (25%)")
        title_zoom_layout.addWidget(zoom_in_basis_btn)

        zoom_reset_basis_btn = QPushButton("100%")
        zoom_reset_basis_btn.setMaximumWidth(45)
        zoom_reset_basis_btn.setToolTip("Reset zoom")
        title_zoom_layout.addWidget(zoom_reset_basis_btn)

        basis_layout.addLayout(title_zoom_layout)

        # Basis display using ZoomableWebView with MathJax for fast rendering
        self.basis_display = ZoomableWebView()
        self.basis_display.setMinimumHeight(150)
        basis_layout.addWidget(self.basis_display, stretch=1)

        # Connect zoom buttons directly
        zoom_in_basis_btn.clicked.connect(self.basis_display.zoom_in)
        zoom_out_basis_btn.clicked.connect(self.basis_display.zoom_out)
        zoom_reset_basis_btn.clicked.connect(self.basis_display.reset_zoom)

        # Button to enter basis ordering mode
        self.enter_basis_btn = QPushButton("Enter Basis Ordering Mode")
        self.enter_basis_btn.clicked.connect(self.graphulator._toggle_basis_ordering_mode)
        self.enter_basis_btn.setToolTip("Enter mode to reorder basis (Ctrl+B)")
        basis_layout.addWidget(self.enter_basis_btn)

        # Commit/Cancel buttons (shown during basis ordering mode)
        button_layout = QHBoxLayout()

        self.commit_basis_btn = QPushButton("Commit Basis Order")
        self.commit_basis_btn.clicked.connect(self.graphulator._commit_basis_ordering)
        self.commit_basis_btn.setEnabled(False)  # Disabled unless in basis ordering mode
        self.commit_basis_btn.setToolTip("Commit the selected basis order (Ctrl+Shift+Enter)")
        button_layout.addWidget(self.commit_basis_btn)

        self.cancel_basis_btn = QPushButton("Cancel")
        self.cancel_basis_btn.clicked.connect(self.graphulator._cancel_basis_ordering)
        self.cancel_basis_btn.setEnabled(False)  # Disabled unless in basis ordering mode
        self.cancel_basis_btn.setToolTip("Cancel basis ordering and exit mode (Esc)")
        button_layout.addWidget(self.cancel_basis_btn)

        basis_layout.addLayout(button_layout)
        basis_layout.addStretch()

        self.symbolic_subtabs.addTab(basis_tab, "Basis")

        # Update basis display
        self._update_basis_display()

    def _create_sympy_code_tab(self):
        """Create the SymPy code display tab"""
        sympy_tab = QWidget()
        sympy_layout = QVBoxLayout()
        sympy_tab.setLayout(sympy_layout)

        # Title
        title = QLabel("SymPy Code")
        title.setStyleSheet("font-weight: bold; font-size: 11px;")
        sympy_layout.addWidget(title)

        # Code display using QTextEdit with monospace font
        self.sympy_code_display = QTextEdit()
        self.sympy_code_display.setReadOnly(True)
        self.sympy_code_display.setFont(QFont("Courier", 10))
        self.sympy_code_display.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        sympy_layout.addWidget(self.sympy_code_display, stretch=1)

        # Export button
        export_btn = QPushButton("Export SymPy Code to Paste Buffer")
        export_btn.clicked.connect(self._export_sympy_code)
        export_btn.setToolTip("Export SymPy code to clipboard (Alt+E)")
        sympy_layout.addWidget(export_btn)

        self.symbolic_subtabs.addTab(sympy_tab, "Code")

        # Update SymPy code display
        self._update_sympy_code_display()

    def _create_scattering_tab(self):
        """Create the Scattering parameter assignment tab"""

        scattering_tab = QWidget()
        scattering_layout = QVBoxLayout()
        scattering_tab.setLayout(scattering_layout)

        # Title
        title = QLabel("Scattering Parameters")
        title.setStyleSheet("font-weight: bold; font-size: 11px;")
        scattering_layout.addWidget(title)

        # === Component Selection (for disconnected graphs) ===
        component_row = QHBoxLayout()
        component_row.addWidget(QLabel("Component:"))
        self.component_combo = QComboBox()
        self.component_combo.setToolTip("Select which connected component to configure (for disconnected graphs)")
        self.component_combo.setMinimumWidth(150)
        self.component_combo.addItem("All (single graph)", -1)  # Default for connected graphs
        component_row.addWidget(self.component_combo)
        self.component_info_label = QLabel("")
        self.component_info_label.setStyleSheet("color: #666; font-style: italic;")
        component_row.addWidget(self.component_info_label)
        component_row.addStretch()
        scattering_layout.addLayout(component_row)

        # === Signal Frequency Array Section ===
        freq_group = QFrame()
        freq_group.setFrameStyle(QFrame.Shape.StyledPanel)
        freq_layout = QVBoxLayout()
        freq_group.setLayout(freq_layout)

        freq_title = QLabel("Signal Frequency Array [a.u.]")
        freq_title.setStyleSheet("font-weight: bold;")
        freq_layout.addWidget(freq_title)

        freq_controls = QHBoxLayout()

        # Injection node dropdown
        freq_controls.addWidget(QLabel("Injection node:"))
        self.injection_node_combo = QComboBox()
        self.injection_node_combo.setToolTip("Root node for spanning tree (signal injection point)")
        self.injection_node_combo.setMinimumWidth(80)
        freq_controls.addWidget(self.injection_node_combo)

        freq_controls.addSpacing(15)  # Add space between injection node and frequency controls

        # Center frequency
        freq_controls.addWidget(QLabel("Center:"))
        self.freq_center_spin = FineControlSpinBox()
        self.freq_center_spin.setRange(config.FREQ_CENTER_MIN, config.FREQ_CENTER_MAX)
        self.freq_center_spin.setDecimals(config.FREQ_CENTER_DECIMALS)
        self.freq_center_spin.setSingleStep(config.FREQ_CENTER_STEP)
        self.freq_center_spin.setValue(config.FREQ_CENTER_DEFAULT)
        self.freq_center_spin.setToolTip("Center frequency")
        freq_controls.addWidget(self.freq_center_spin)

        # Frequency span
        freq_controls.addWidget(QLabel("Span:"))
        self.freq_span_spin = FineControlSpinBox()
        self.freq_span_spin.setRange(config.FREQ_SPAN_MIN, config.FREQ_SPAN_MAX)
        self.freq_span_spin.setDecimals(config.FREQ_SPAN_DECIMALS)
        self.freq_span_spin.setSingleStep(config.FREQ_SPAN_STEP)
        self.freq_span_spin.setValue(config.FREQ_SPAN_DEFAULT)
        self.freq_span_spin.setToolTip("Frequency span")
        freq_controls.addWidget(self.freq_span_spin)

        # Number of points
        freq_controls.addWidget(QLabel("Points:"))
        self.freq_points_spin = FineControlSpinBox()
        self.freq_points_spin.setRange(config.FREQ_POINTS_MIN, config.FREQ_POINTS_MAX)
        self.freq_points_spin.setDecimals(config.FREQ_POINTS_DECIMALS)
        self.freq_points_spin.setValue(config.FREQ_POINTS_DEFAULT)
        self.freq_points_spin.setToolTip("Number of frequency points")
        freq_controls.addWidget(self.freq_points_spin)

        # Connect frequency parameter changes to auto-recalculate S-parameters
        self.freq_center_spin.valueChanged.connect(self._auto_recalculate_sparams)
        self.freq_span_spin.valueChanged.connect(self._auto_recalculate_sparams)
        self.freq_points_spin.valueChanged.connect(self._auto_recalculate_sparams)

        freq_controls.addStretch()
        freq_layout.addLayout(freq_controls)
        scattering_layout.addWidget(freq_group)

        # === Node/Edge Assignment Section ===
        # Create horizontal splitter for Nodes | Edges
        assignment_splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- LEFT: Nodes Section ---
        nodes_frame = QFrame()
        nodes_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        # Set minimum width for nodes column - ADJUST THIS VALUE to fine-tune
        nodes_frame.setMinimumWidth(280)
        nodes_layout = QVBoxLayout()
        nodes_frame.setLayout(nodes_layout)

        nodes_title = QLabel("Nodes")
        nodes_title.setStyleSheet("font-weight: bold;")
        nodes_layout.addWidget(nodes_title)

        # Scrollable area for node parameters
        self.nodes_scroll = QScrollArea()
        self.nodes_scroll.setWidgetResizable(True)
        self.nodes_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.nodes_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # Allow Tab to pass through to child widgets instead of being captured by scroll area
        self.nodes_scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Container for node parameter grid
        self.nodes_param_widget = QWidget()
        self.nodes_param_layout = QGridLayout()
        self.nodes_param_layout.setContentsMargins(5, 5, 5, 5)
        self.nodes_param_layout.setHorizontalSpacing(8)  # Reduce horizontal spacing - ADJUST to fine-tune
        self.nodes_param_layout.setVerticalSpacing(8)     # Vertical spacing between rows
        self.nodes_param_layout.setAlignment(Qt.AlignmentFlag.AlignTop)  # Top-align content
        self.nodes_param_widget.setLayout(self.nodes_param_layout)
        self.nodes_scroll.setWidget(self.nodes_param_widget)

        nodes_layout.addWidget(self.nodes_scroll)

        # Show S button centered under nodes - double height
        show_s_layout = QHBoxLayout()
        show_s_layout.addStretch()
        self.show_s_button = QPushButton("Show S")
        self.show_s_button.setCheckable(True)
        self.show_s_button.setChecked(False)
        self.show_s_button.toggled.connect(self._on_show_s_clicked)
        self.show_s_button.setToolTip("Show/hide S-parameter plot (Ctrl+Shift+R)")
        self.show_s_button.setMinimumHeight(60)  # Double the default height
        show_s_layout.addWidget(self.show_s_button)
        show_s_layout.addStretch()
        nodes_layout.addLayout(show_s_layout)

        assignment_splitter.addWidget(nodes_frame)

        # --- RIGHT: Edges Section ---
        edges_frame = QFrame()
        edges_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        # Set minimum width for edges column - ADJUST THIS VALUE to fine-tune
        edges_frame.setMinimumWidth(230)
        edges_layout = QVBoxLayout()
        edges_frame.setLayout(edges_layout)

        edges_title = QLabel("Edges")
        edges_title.setStyleSheet("font-weight: bold;")
        edges_layout.addWidget(edges_title)

        # Scrollable area for edge parameters
        self.edges_scroll = QScrollArea()
        self.edges_scroll.setWidgetResizable(True)
        self.edges_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.edges_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # Allow Tab to pass through to child widgets instead of being captured by scroll area
        self.edges_scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Container for edge parameter grid
        self.edges_param_widget = QWidget()
        self.edges_param_layout = QGridLayout()
        self.edges_param_layout.setContentsMargins(5, 5, 5, 5)
        self.edges_param_layout.setHorizontalSpacing(8)
        self.edges_param_layout.setVerticalSpacing(8)
        self.edges_param_layout.setAlignment(Qt.AlignmentFlag.AlignTop)  # Top-align content
        self.edges_param_widget.setLayout(self.edges_param_layout)
        self.edges_scroll.setWidget(self.edges_param_widget)

        edges_layout.addWidget(self.edges_scroll)

        # Export buttons vertically stacked and centered under edges
        export_layout = QVBoxLayout()
        export_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        export_py_button = QPushButton("Export to .py")
        export_py_button.setToolTip("Export graph to Python code file")
        export_py_button.clicked.connect(self._on_export_py_clicked)
        export_layout.addWidget(export_py_button)

        export_buffer_button = QPushButton("Export to Paste Buffer")
        export_buffer_button.setToolTip("Export graph code to clipboard")
        export_buffer_button.clicked.connect(self._on_export_buffer_clicked)
        export_layout.addWidget(export_buffer_button)

        edges_layout.addLayout(export_layout)

        assignment_splitter.addWidget(edges_frame)

        # Set stretch factors to maintain 2:1 ratio (nodes:edges)
        assignment_splitter.setStretchFactor(0, 2)  # Nodes gets 2x
        assignment_splitter.setStretchFactor(1, 1)  # Edges gets 1x

        # Set initial splitter sizes (66/34 split - nodes get more space)
        assignment_splitter.setSizes([200, 300])

        scattering_layout.addWidget(assignment_splitter, stretch=1)

        # Add tab and store index for later show/hide
        self.scattering_tab_index = self.tabs.addTab(scattering_tab, "Scattering")

        # Hide by default - will be shown when scattering mode is activated
        self.tabs.setTabVisible(self.scattering_tab_index, False)

        # Initialize with empty parameter tables (will be populated when scattering mode is active)
        self._update_scattering_node_table()
        self._update_scattering_edge_table()


    def _create_matrix_tab(self):
        """Create the matrix display tab with Original/Kron subtabs"""

        matrix_tab = QWidget()
        matrix_layout = QVBoxLayout()
        matrix_tab.setLayout(matrix_layout)

        # Title
        title = QLabel("Symbolic Matrix")
        title.setStyleSheet("font-weight: bold; font-size: 11px;")
        matrix_layout.addWidget(title)

        # Create subtabs for Original and Kron views
        self.matrix_subtabs = QTabWidget()
        matrix_layout.addWidget(self.matrix_subtabs, stretch=1)

        # Original matrix subtab
        original_tab = QWidget()
        original_layout = QVBoxLayout()
        original_tab.setLayout(original_layout)

        # Radio buttons for Original matrix LaTeX method
        orig_latex_group = QWidget()
        orig_latex_layout = QHBoxLayout()
        orig_latex_layout.setContentsMargins(0, 0, 0, 0)
        orig_latex_group.setLayout(orig_latex_layout)

        orig_label = QLabel("LaTeX:")
        orig_label.setStyleSheet("font-size: 9px;")
        orig_latex_layout.addWidget(orig_label)

        self.orig_latex_radio_manual = QRadioButton("Manual")
        self.orig_latex_radio_manual.setStyleSheet("font-size: 9px;")
        self.orig_latex_radio_manual.setChecked(True)
        self.orig_latex_radio_manual.toggled.connect(self._on_orig_latex_method_changed)
        orig_latex_layout.addWidget(self.orig_latex_radio_manual)

        self.orig_latex_radio_custom = QRadioButton("latex_custom()")
        self.orig_latex_radio_custom.setStyleSheet("font-size: 9px;")
        self.orig_latex_radio_custom.toggled.connect(self._on_orig_latex_method_changed)
        orig_latex_layout.addWidget(self.orig_latex_radio_custom)

        self.orig_latex_radio_factored = QRadioButton("factored()")
        self.orig_latex_radio_factored.setStyleSheet("font-size: 9px;")
        self.orig_latex_radio_factored.toggled.connect(self._on_orig_latex_method_changed)
        orig_latex_layout.addWidget(self.orig_latex_radio_factored)

        # Zoom controls for matrix display
        zoom_out_matrix_btn = QPushButton("-")
        zoom_out_matrix_btn.setMaximumWidth(30)
        zoom_out_matrix_btn.setToolTip("Zoom out (25%)")
        orig_latex_layout.addWidget(zoom_out_matrix_btn)

        zoom_in_matrix_btn = QPushButton("+")
        zoom_in_matrix_btn.setMaximumWidth(30)
        zoom_in_matrix_btn.setToolTip("Zoom in (25%)")
        orig_latex_layout.addWidget(zoom_in_matrix_btn)

        zoom_reset_matrix_btn = QPushButton("100%")
        zoom_reset_matrix_btn.setMaximumWidth(45)
        zoom_reset_matrix_btn.setToolTip("Reset zoom")
        orig_latex_layout.addWidget(zoom_reset_matrix_btn)

        orig_latex_layout.addStretch()
        original_layout.addWidget(orig_latex_group)

        self.matrix_display = ZoomableWebView()
        self.matrix_display.setMinimumHeight(200)
        original_layout.addWidget(self.matrix_display, stretch=1)

        # Connect zoom buttons directly
        zoom_in_matrix_btn.clicked.connect(self.matrix_display.zoom_in)
        zoom_out_matrix_btn.clicked.connect(self.matrix_display.zoom_out)
        zoom_reset_matrix_btn.clicked.connect(self.matrix_display.reset_zoom)

        # Install event filter to detect resize events
        self.matrix_display.installEventFilter(self)
        self._matrix_resize_timer = QTimer()
        self._matrix_resize_timer.setSingleShot(True)
        self._matrix_resize_timer.timeout.connect(self._on_matrix_resize)

        self.matrix_subtabs.addTab(original_tab, "Original")

        # Kron-reduced matrix subtab
        kron_tab = QWidget()
        kron_layout = QVBoxLayout()
        kron_tab.setLayout(kron_layout)

        # Radio buttons for Kron matrix LaTeX method
        kron_latex_group = QWidget()
        kron_latex_layout = QHBoxLayout()
        kron_latex_layout.setContentsMargins(0, 0, 0, 0)
        kron_latex_group.setLayout(kron_latex_layout)

        kron_label = QLabel("LaTeX:")
        kron_label.setStyleSheet("font-size: 9px;")
        kron_latex_layout.addWidget(kron_label)

        self.kron_latex_radio_latex = QRadioButton("latex()")
        self.kron_latex_radio_latex.setStyleSheet("font-size: 9px;")
        self.kron_latex_radio_latex.toggled.connect(self._on_kron_latex_method_changed)
        kron_latex_layout.addWidget(self.kron_latex_radio_latex)

        self.kron_latex_radio_custom = QRadioButton("latex_custom()")
        self.kron_latex_radio_custom.setStyleSheet("font-size: 9px;")
        self.kron_latex_radio_custom.setChecked(True)
        self.kron_latex_radio_custom.toggled.connect(self._on_kron_latex_method_changed)
        kron_latex_layout.addWidget(self.kron_latex_radio_custom)

        self.kron_latex_radio_factored = QRadioButton("factored()")
        self.kron_latex_radio_factored.setStyleSheet("font-size: 9px;")
        self.kron_latex_radio_factored.toggled.connect(self._on_kron_latex_method_changed)
        kron_latex_layout.addWidget(self.kron_latex_radio_factored)

        # Zoom controls for kron matrix display
        zoom_out_kron_btn = QPushButton("-")
        zoom_out_kron_btn.setMaximumWidth(30)
        zoom_out_kron_btn.setToolTip("Zoom out (25%)")
        kron_latex_layout.addWidget(zoom_out_kron_btn)

        zoom_in_kron_btn = QPushButton("+")
        zoom_in_kron_btn.setMaximumWidth(30)
        zoom_in_kron_btn.setToolTip("Zoom in (25%)")
        kron_latex_layout.addWidget(zoom_in_kron_btn)

        zoom_reset_kron_btn = QPushButton("100%")
        zoom_reset_kron_btn.setMaximumWidth(45)
        zoom_reset_kron_btn.setToolTip("Reset zoom")
        kron_latex_layout.addWidget(zoom_reset_kron_btn)

        kron_latex_layout.addStretch()
        kron_layout.addWidget(kron_latex_group)

        self.kron_matrix_display = ZoomableWebView()
        self.kron_matrix_display.setMinimumHeight(200)
        kron_layout.addWidget(self.kron_matrix_display, stretch=1)

        # Connect zoom buttons directly
        zoom_in_kron_btn.clicked.connect(self.kron_matrix_display.zoom_in)
        zoom_out_kron_btn.clicked.connect(self.kron_matrix_display.zoom_out)
        zoom_reset_kron_btn.clicked.connect(self.kron_matrix_display.reset_zoom)

        # Install event filter for kron display too
        self.kron_matrix_display.installEventFilter(self)

        self.matrix_subtabs.addTab(kron_tab, "Kron")

        # Connect subtab change to update display
        self.matrix_subtabs.currentChanged.connect(self._on_matrix_subtab_changed)

        self.symbolic_subtabs.addTab(matrix_tab, "Matrix")

        # Update matrix display
        self._update_matrix_display()
        self._update_kron_matrix_display()

    def _update_basis_display(self):
        """Update the basis display with MathJax-rendered column vector (instant, no blocking)"""
        # Enable/disable buttons based on basis ordering mode
        if self.graphulator.basis_ordering_mode:
            self.enter_basis_btn.setEnabled(False)
            self.commit_basis_btn.setEnabled(True)
            self.cancel_basis_btn.setEnabled(True)
        else:
            self.enter_basis_btn.setEnabled(True)
            self.commit_basis_btn.setEnabled(False)
            self.cancel_basis_btn.setEnabled(False)

        if not self.graphulator.nodes:
            self.basis_display.setHtml(render_placeholder_html("No nodes yet"))
            return

        # Build basis labels based on mode
        basis_labels = []
        kron_labels = []  # For Kron mode display

        # During basis ordering mode, show current selection progress
        if self.graphulator.basis_ordering_mode and self.graphulator.basis_order:
            # Show only the selected basis order so far
            for node in self.graphulator.basis_order:
                label = node['label']
                if node.get('conj', False):
                    label += '^{*}'
                basis_labels.append(label)
        # During Kron mode, show original → Kron-reduced
        elif self.graphulator.kron_mode and self.graphulator.kron_selected_nodes:
            # Original basis (all nodes)
            for node in self.graphulator.nodes:
                label = node['label']
                if node.get('conj', False):
                    label += '^{*}'
                basis_labels.append(label)

            # Kron-reduced basis (only selected nodes)
            for node in self.graphulator.kron_selected_nodes:
                label = node['label']
                if node.get('conj', False):
                    label += '^{*}'
                kron_labels.append(label)
        # After Kron reduction is committed, show original → Kron-reduced
        elif hasattr(self.graphulator, 'kron_graph') and self.graphulator.kron_graph and self.graphulator.kron_reduced_nodes:
            # Original basis - always use original_graph nodes, which may have been reordered
            if hasattr(self.graphulator, 'original_graph') and self.graphulator.original_graph:
                for node in self.graphulator.original_graph['nodes']:
                    label = node['label']
                    if node.get('conj', False):
                        label += '^{*}'
                    basis_labels.append(label)
            else:
                # Fallback if original_graph not available
                for node in self.graphulator.nodes:
                    label = node['label']
                    if node.get('conj', False):
                        label += '^{*}'
                    basis_labels.append(label)

            # Kron-reduced basis (from kron_reduced_nodes)
            for node in self.graphulator.kron_reduced_nodes:
                label = node['label']
                if node.get('conj', False):
                    label += '^{*}'
                kron_labels.append(label)
        else:
            # Show current node order (normal mode or no selection yet)
            for node in self.graphulator.nodes:
                label = node['label']
                if node.get('conj', False):
                    label += '^{*}'
                basis_labels.append(label)

        # Create LaTeX string for bmatrix
        if kron_labels:
            # Kron mode: show original → Kron-reduced
            original_latex = r'\begin{bmatrix}' + r' \\ '.join(basis_labels) + r'\end{bmatrix}'
            kron_latex = r'\begin{bmatrix}' + r' \\ '.join(kron_labels) + r'\end{bmatrix}'
            latex_str = original_latex + r' \rightarrow ' + kron_latex
        else:
            # Normal or basis ordering mode: just show one vector
            latex_str = r'\begin{bmatrix}' + r' \\ '.join(basis_labels) + r'\end{bmatrix}'

        # Store for export
        self.graphulator.symbolic_basis_latex = latex_str

        # Render using consolidated template
        html = render_basis_html(
            latex_str,
            self._get_katex_html_header(),
            self._get_latex_context_menu_js()
        )

        self.basis_display.setHtml(html, self._get_katex_base_qurl())
        self.basis_display.setLatexContent(latex_str)

    def _update_sympy_code_display(self):
        """Update the SymPy code display with executable Python code"""
        # Check if manual code has been set (e.g., from Kron reduction)
        # Only use manual code when viewing the Kron matrix tab (index 1)
        if (hasattr(self, '_sympy_code_manual') and self._sympy_code_manual and
            hasattr(self, 'matrix_subtabs') and self.matrix_subtabs.currentIndex() == 1):
            self.sympy_code_display.setPlainText(self._sympy_code_manual)
            return

        if not self.graphulator.nodes:
            self.sympy_code_display.setPlainText("# No nodes yet")
            return

        # Generate SymPy code
        code_lines = []
        code_lines.append("# Import SymPy")
        code_lines.append("from sympy import symbols, Matrix, conjugate, I, simplify, latex")
        code_lines.append("")

        # Create symbols
        code_lines.append("# Define symbols")

        # Collect all Delta symbols
        delta_symbols = []
        for node in self.graphulator.nodes:
            label = self._get_clean_label(node)
            delta_symbols.append(f"Delta_{label}")

        # Collect all beta symbols (unique pairs)
        # We need to collect all symbols that will actually be used in the matrix
        beta_symbols_set = set()
        n = len(self.graphulator.nodes)

        for i, node_i in enumerate(self.graphulator.nodes):
            label_i = self._get_clean_label(node_i)
            conj_i = node_i.get('conj', False)

            for j, node_j in enumerate(self.graphulator.nodes):
                if i >= j:
                    continue  # Only process upper triangle

                label_j = self._get_clean_label(node_j)
                conj_j = node_j.get('conj', False)

                # Check if edge exists
                edge_exists = any(
                    (e['from_node'] == node_i and e['to_node'] == node_j) or
                    (e['from_node'] == node_j and e['to_node'] == node_i)
                    for e in self.graphulator.edges
                )

                if not edge_exists:
                    continue

                # Add the symbol that will be used in upper triangle
                # Based on the matrix building logic at lines 940-965
                if conj_i == conj_j:
                    # Same conjugation: use beta_{label_j}{label_i}
                    beta_symbols_set.add(f"beta_{label_j}{label_i}")
                else:
                    # Different conjugation: use beta_{label_j}{label_i}
                    beta_symbols_set.add(f"beta_{label_j}{label_i}")

        beta_symbols = sorted(list(beta_symbols_set))

        # Write symbol definitions
        all_symbols = delta_symbols + beta_symbols
        if all_symbols:
            code_lines.append(f"{', '.join(all_symbols)} = symbols('{' '.join(all_symbols)}', complex=True)")
        code_lines.append("")

        # Build matrix
        code_lines.append("# Build matrix M")
        n = len(self.graphulator.nodes)
        code_lines.append(f"M = Matrix([")

        for i, node_i in enumerate(self.graphulator.nodes):
            row_elements = []
            label_i = self._get_clean_label(node_i)
            conj_i = node_i.get('conj', False)

            for j, node_j in enumerate(self.graphulator.nodes):
                label_j = self._get_clean_label(node_j)
                conj_j = node_j.get('conj', False)

                if i == j:
                    # Diagonal
                    if conj_i:
                        row_elements.append(f"-conjugate(Delta_{label_i})")
                    else:
                        row_elements.append(f"Delta_{label_i}")
                else:
                    # Check if edge exists
                    edge_exists = any(
                        (e['from_node'] == node_i and e['to_node'] == node_j) or
                        (e['from_node'] == node_j and e['to_node'] == node_i)
                        for e in self.graphulator.edges
                    )

                    if not edge_exists:
                        row_elements.append("0")
                    else:
                        # Determine the element based on position and conjugation
                        if conj_i == conj_j:
                            # Same conjugation
                            if i < j:
                                # Upper triangle
                                if conj_i:
                                    row_elements.append(f"-beta_{label_j}{label_i}")
                                else:
                                    row_elements.append(f"beta_{label_j}{label_i}")
                            else:
                                # Lower triangle
                                if conj_i:
                                    row_elements.append(f"-conjugate(beta_{label_i}{label_j})")
                                else:
                                    row_elements.append(f"conjugate(beta_{label_i}{label_j})")
                        else:
                            # Different conjugation
                            if conj_i and not conj_j:
                                if i < j:
                                    row_elements.append(f"-conjugate(beta_{label_i}{label_j})")
                                else:
                                    row_elements.append(f"-conjugate(beta_{label_i}{label_j})")
                            else:
                                if i < j:
                                    row_elements.append(f"beta_{label_j}{label_i}")
                                else:
                                    row_elements.append(f"beta_{label_j}{label_i}")

            row_str = "[" + ", ".join(row_elements) + "]"
            if i < n - 1:
                code_lines.append(f"    {row_str},")
            else:
                code_lines.append(f"    {row_str}")

        code_lines.append("])")
        code_lines.append("")
        code_lines.append("# Display matrix")
        code_lines.append("print(M)")

        # Set the code in the display
        code_text = "\n".join(code_lines)
        self.sympy_code_display.setPlainText(code_text)

        # Store for export
        self.graphulator.sympy_code = code_text

    def _export_sympy_code(self):
        """Export SymPy code to clipboard"""
        code_text = self.sympy_code_display.toPlainText()
        if code_text and code_text.strip():
            clipboard = QApplication.clipboard()
            clipboard.setText(code_text)
            print("✓ Exported SymPy code to clipboard")
        else:
            print("No SymPy code to export")

    def _get_clean_label(self, node):
        """Get clean label for SymPy (remove LaTeX formatting, flatten subscripts)"""
        label = node['label']
        # Remove LaTeX subscript formatting: A_{0} -> A0
        label = re.sub(r'_\{([^}]+)\}', r'\1', label)
        # Remove simple subscript: A_0 -> A0
        label = re.sub(r'_(.)', r'\1', label)
        # Don't add conjugation star here - handled separately
        return label

    def _generate_symbolic_matrix(self):
        """Generate symbolic matrix with Δ and β notation using SymPy"""

        n = len(self.graphulator.nodes)

        # Create matrix elements
        matrix_elements = []

        for i, node_i in enumerate(self.graphulator.nodes):
            row = []
            label_i = self._get_clean_label(node_i)
            conj_i = node_i.get('conj', False)

            for j, node_j in enumerate(self.graphulator.nodes):
                label_j = self._get_clean_label(node_j)
                conj_j = node_j.get('conj', False)

                if i == j:
                    # Diagonal element: Δ or -Δ*
                    # Use complex symbol so conjugate shows up properly
                    delta_symbol = sp.Symbol(f'Delta_{label_i}', complex=True)
                    if conj_i:
                        # Conjugated node: -Δ*
                        element = -sp.conjugate(delta_symbol)
                    else:
                        # Non-conjugated node: Δ
                        element = delta_symbol
                else:
                    # Off-diagonal: check if edge exists
                    edge_exists = False
                    for edge in self.graphulator.edges:
                        if ((edge['from_node'] == node_i and edge['to_node'] == node_j) or
                            (edge['from_node'] == node_j and edge['to_node'] == node_i)):
                            edge_exists = True
                            break

                    if edge_exists:
                        # Beta subscripts use clean labels WITHOUT conjugation stars
                        # Determine forward direction based on basis order (earlier to later)
                        # Forward element M_{ij} where i<j is β_{ji}

                        if i < j:
                            # Forward direction: i to j
                            # M_{ij} uses β_{ji} (reversed indices)
                            beta_symbol = sp.Symbol(f'beta_{label_j}{label_i}', complex=True)

                            if conj_i == conj_j:
                                # Same conjugation (single-line edge)
                                if conj_i:
                                    # Both conjugated: M_{ij} = -β_{ji}
                                    element = -beta_symbol
                                else:
                                    # Both unconjugated: M_{ij} = β_{ji}
                                    element = beta_symbol
                            else:
                                # Different conjugation (double-line edge, anti-conjugation)
                                if conj_i and not conj_j:
                                    # i is conj, j is not: M_{ij} = -β_{ji}*
                                    element = -sp.conjugate(beta_symbol)
                                else:
                                    # i is not conj, j is: M_{ij} = β_{ji}
                                    element = beta_symbol
                        else:
                            # Backward direction: j to i (transpose position)
                            # M_{ij} where i>j uses β_{ij} (same indices)
                            beta_symbol = sp.Symbol(f'beta_{label_i}{label_j}', complex=True)

                            if conj_i == conj_j:
                                # Same conjugation (single-line edge)
                                # M_{ji} = β_{ij}* (conjugate of forward)
                                element = sp.conjugate(beta_symbol)
                            else:
                                # Different conjugation (double-line edge, anti-conjugation)
                                # Both cases need -β_{ij}*
                                element = -sp.conjugate(beta_symbol)
                    else:
                        # No edge
                        element = sp.Integer(0)

                row.append(element)
            matrix_elements.append(row)

        # Create SymPy matrix
        matrix = sp.Matrix(matrix_elements)
        return matrix

    def _generate_latex_matrix_string(self):
        """Generate LaTeX matrix string manually with proper superscripted conjugation"""
        n = len(self.graphulator.nodes)

        # Build matrix rows
        rows = []
        for i, node_i in enumerate(self.graphulator.nodes):
            row_elements = []
            label_i = self._get_clean_label(node_i)
            conj_i = node_i.get('conj', False)

            for j, node_j in enumerate(self.graphulator.nodes):
                label_j = self._get_clean_label(node_j)
                conj_j = node_j.get('conj', False)

                if i == j:
                    # Diagonal element
                    if conj_i:
                        # Conjugated node: -Δ_j^*
                        element_str = f"-\\Delta_{{{label_i}}}^{{*}}"
                    else:
                        # Non-conjugated node: Δ_j
                        element_str = f"\\Delta_{{{label_i}}}"
                else:
                    # Check if edge exists
                    edge_exists = False
                    for edge in self.graphulator.edges:
                        if ((edge['from_node'] == node_i and edge['to_node'] == node_j) or
                            (edge['from_node'] == node_j and edge['to_node'] == node_i)):
                            edge_exists = True
                            break

                    if edge_exists:
                        # Off-diagonal elements
                        # Convention: Beta subscripts always in basis order (smaller index first)

                        if i < j:
                            # Upper triangle: forward direction (i -> j in basis order)
                            # Always use β_{ij} since i < j in basis
                            if conj_i == conj_j:
                                # Same conjugation (conjugate relationship)
                                if conj_i:
                                    # Both conjugated: -β_{ij}
                                    element_str = f"-\\beta_{{{label_i}{label_j}}}"
                                else:
                                    # Both unconjugated: β_{ij}
                                    element_str = f"\\beta_{{{label_i}{label_j}}}"
                            else:
                                # Different conjugation (anti-conjugate relationship)
                                if conj_i and not conj_j:
                                    # i=conj, j=unconj: M[i,j] gets -β_{ij}^*
                                    element_str = f"-\\beta_{{{label_i}{label_j}}}^{{*}}"
                                else:
                                    # i=unconj, j=conj: M[i,j] gets β_{ij}
                                    element_str = f"\\beta_{{{label_i}{label_j}}}"
                        else:
                            # Lower triangle: backward direction (j -> i in basis order)
                            # Always use β_{ji} since j < i in basis
                            if conj_i == conj_j:
                                # Same conjugation (conjugate relationship)
                                if conj_i:
                                    # Both conjugated: -β_{ji}^*
                                    element_str = f"-\\beta_{{{label_j}{label_i}}}^{{*}}"
                                else:
                                    # Both unconjugated: β_{ji}^*
                                    element_str = f"\\beta_{{{label_j}{label_i}}}^{{*}}"
                            else:
                                # Different conjugation (anti-conjugate relationship)
                                if conj_i and not conj_j:
                                    # i=conj, j=unconj: M[i,j] gets -β_{ji}^*
                                    element_str = f"-\\beta_{{{label_j}{label_i}}}^{{*}}"
                                else:
                                    # i=unconj, j=conj: M[i,j] gets β_{ji}
                                    element_str = f"\\beta_{{{label_j}{label_i}}}"
                    else:
                        # No edge
                        element_str = "0"

                row_elements.append(element_str)

            rows.append(" & ".join(row_elements))

        # Create bmatrix LaTeX
        matrix_latex = "\\begin{bmatrix}\n" + " \\\\\\\\\n".join(rows) + "\n\\end{bmatrix}"
        return matrix_latex

    def _update_matrix_display(self):
        """Update the matrix display with KaTeX-rendered LaTeX (instant, no blocking)"""
        # Check if graphulator and nodes exist
        if not hasattr(self, 'graphulator') or self.graphulator is None:
            self.matrix_display.setHtml(render_placeholder_html("Initializing..."))
            return

        if not self.graphulator.nodes:
            self.matrix_display.setHtml(render_placeholder_html("No nodes in graph"))
            return

        # Check for invalid duplicate labels (excludes valid conjugate pairs)
        duplicate_nodes = self.graphulator._get_nodes_with_duplicate_labels()
        if duplicate_nodes:
            dup_labels = sorted(set(n['label'] for n in duplicate_nodes))
            self.matrix_display.setHtml(render_placeholder_html(
                f"Error: Duplicate node labels: {', '.join(dup_labels)}<br>"
                "Matrix requires unique labels (conjugate pairs allowed).",
                color="red"
            ))
            return

        # Generate LaTeX string based on selected method (Original tab)
        if self.orig_latex_radio_manual.isChecked():
            latex_str = self._generate_latex_matrix_string()
        elif self.orig_latex_radio_custom.isChecked():
            matrix = self._build_symbolic_matrix()
            latex_str = normalize_matrix_latex(latex_custom(matrix))
        elif self.orig_latex_radio_factored.isChecked():
            matrix = self._build_symbolic_matrix()
            latex_str = latex_matrix_factored(matrix)
        else:
            latex_str = self._generate_latex_matrix_string()

        # Store for export
        self.graphulator.symbolic_matrix_latex = latex_str

        # Render using consolidated template
        html = render_matrix_html(
            latex_str,
            self._get_katex_html_header(),
            self._get_latex_context_menu_js(),
            label_prefix="M"
        )

        self.matrix_display.setHtml(html, self._get_katex_base_qurl())
        self.matrix_display.setLatexContent(r'\mathbf{M} = ' + latex_str)

    def eventFilter(self, obj, event):
        """Event filter to detect resize events on matrix display"""
        if obj == self.matrix_display and event.type() == QEvent.Type.Resize:
            # Use timer to debounce resize events
            self._matrix_resize_timer.start(150)  # 150ms delay
        return super().eventFilter(obj, event)

    def _on_orig_latex_method_changed(self):
        """Handle Original matrix LaTeX method radio button change"""
        self._update_matrix_display()

    def _on_kron_latex_method_changed(self):
        """Handle Kron matrix LaTeX method radio button change"""
        self._update_kron_matrix_display()

    def _on_matrix_resize(self):
        """Handle matrix display resize - re-render with new size"""
        # Re-render the matrix to adjust to new size
        self._update_matrix_display()

    def _update_kron_matrix_display(self):
        """Update the Kron-reduced matrix display during selection"""
        if not hasattr(self, 'graphulator') or self.graphulator is None:
            self.kron_matrix_display.setHtml(render_placeholder_html("Initializing..."))
            return

        # Check if viewing committed reduction (original_graph set, not in active kron_mode)
        if (hasattr(self.graphulator, 'original_graph') and
            self.graphulator.original_graph is not None and
            not self.graphulator.kron_mode):
            # Committed reduction - regenerate LaTeX from stored matrix with current method
            M_reduced = self.graphulator.kron_reduced_matrix
            if self.kron_latex_radio_latex.isChecked():
                latex_str = normalize_matrix_latex(latex(M_reduced))
            elif self.kron_latex_radio_custom.isChecked():
                latex_str = normalize_matrix_latex(latex_custom(M_reduced))
            elif self.kron_latex_radio_factored.isChecked():
                latex_str = latex_matrix_factored(M_reduced)
            else:
                latex_str = normalize_matrix_latex(latex_custom(M_reduced))
        elif not self.graphulator.kron_mode:
            self.kron_matrix_display.setHtml(render_placeholder_html(
                "Enter Kron reduction mode (Ctrl+K) to see reduced matrix"
            ))
            return
        elif not self.graphulator.kron_selected_nodes:
            self.kron_matrix_display.setHtml(render_placeholder_html(
                "Select nodes to keep (click nodes to toggle selection)<br>"
                "Selected nodes will show green rings"
            ))
            return
        else:
            try:
                latex_str = self._compute_kron_reduced_matrix_latex()
            except Exception as e:
                logger.error("Error in _update_kron_matrix_display(): %s", e, exc_info=True)
                self.kron_matrix_display.setHtml(render_placeholder_html(
                    f"Error computing Kron reduction:<br>{type(e).__name__}: {str(e)}",
                    color="red"
                ))
                return

        # Render using consolidated template
        html = render_matrix_html(
            latex_str,
            self._get_katex_html_header(),
            self._get_latex_context_menu_js(),
            label_prefix=r"M_{\text{Kron}}"
        )
        self.kron_matrix_display.setHtml(html, self._get_katex_base_qurl())
        self.kron_matrix_display.setLatexContent(r'\mathbf{M}_{\text{Kron}} = ' + latex_str)

    def _compute_kron_reduced_matrix_latex(self):
        """Compute the Schur complement (Kron-reduced matrix) and return LaTeX string"""

        # Get all nodes and selected nodes
        all_nodes = self.graphulator.nodes
        selected_nodes = self.graphulator.kron_selected_nodes
        eliminated_nodes = [n for n in all_nodes if n not in selected_nodes]

        if not eliminated_nodes:
            # No nodes to eliminate, just show selected nodes matrix
            return self._generate_latex_matrix_string_for_nodes(selected_nodes)

        # Build index mappings using node id (nodes are dicts, can't be dict keys)
        node_to_idx = {id(node): i for i, node in enumerate(all_nodes)}
        selected_indices = [node_to_idx[id(n)] for n in selected_nodes]
        eliminated_indices = [node_to_idx[id(n)] for n in eliminated_nodes]

        # Build symbolic matrix (same as full matrix)
        n = len(all_nodes)
        M_full = self._build_symbolic_matrix()

        # Extract submatrices for Schur complement
        # M = [[M_aa, M_ab],
        #      [M_ba, M_bb]]
        # M_reduced = M_aa - M_ab @ inv(M_bb) @ M_ba

        M_aa = M_full[selected_indices, :][:, selected_indices]
        M_ab = M_full[selected_indices, :][:, eliminated_indices]
        M_ba = M_full[eliminated_indices, :][:, selected_indices]
        M_bb = M_full[eliminated_indices, :][:, eliminated_indices]

        # Compute Schur complement using ADJ method for faster symbolic inversion
        M_reduced = M_aa - M_ab @ M_bb.inv(method='ADJ') @ M_ba

        # Simplify with custom replacements for magnitude squared
        M_reduced = self._simplify_with_magnitude_squared(M_reduced)

        # Store the reduced matrix for later use
        self.graphulator.kron_reduced_matrix = M_reduced

        # Convert to LaTeX based on selected method (Kron tab)
        if self.kron_latex_radio_latex.isChecked():
            # Standard SymPy latex (for comparison/debugging)
            latex_str = normalize_matrix_latex(latex(M_reduced))
        elif self.kron_latex_radio_custom.isChecked():
            # Custom latex with conjugate handling
            latex_str = normalize_matrix_latex(latex_custom(M_reduced))
        elif self.kron_latex_radio_factored.isChecked():
            # Factored matrix latex (already normalized internally)
            latex_str = latex_matrix_factored(M_reduced)
        else:
            # Fallback to custom
            latex_str = normalize_matrix_latex(latex_custom(M_reduced))

        return latex_str

    def _build_symbolic_matrix(self):
        """Build the full symbolic matrix as a SymPy Matrix"""

        nodes = self.graphulator.nodes
        n = len(nodes)

        # Create matrix entries
        M_entries = [[0 for _ in range(n)] for _ in range(n)]

        # Create node to index mapping using id()
        node_to_idx = {id(node): i for i, node in enumerate(nodes)}

        # Diagonal elements
        for i, node in enumerate(nodes):
            label = self._get_symbol_label(node)
            node_label = node['label']
            if node.get('conj', False):
                # Create symbol with proper LaTeX representation
                delta_sym = Symbol(f'Delta_{label}', complex=True)
                M_entries[i][i] = -delta_sym.conjugate()
            else:
                delta_sym = Symbol(f'Delta_{label}', complex=True)
                M_entries[i][i] = delta_sym

        # Off-diagonal elements from edges
        for edge in self.graphulator.edges:
            from_node = edge['from_node']
            to_node = edge['to_node']

            # Skip edges that reference nodes not in the current node list
            from_id = id(from_node)
            to_id = id(to_node)
            if from_id not in node_to_idx or to_id not in node_to_idx:
                logger.warning("Edge references node not in current node list, skipping")
                continue

            i = node_to_idx[from_id]
            j = node_to_idx[to_id]

            if i == j:  # Self-loop
                continue

            # Determine edge type and create coupling symbol
            node1_conj = from_node.get('conj', False)
            node2_conj = to_node.get('conj', False)

            label1 = self._get_symbol_label(from_node)
            label2 = self._get_symbol_label(to_node)

            # Forward direction (i < j in basis order)
            # Use Symbol with subscript notation for proper LaTeX rendering
            if i < j:
                # Create with underscore so latex() renders as \beta_{subscript}
                beta_symbol = Symbol(f'beta_{label1}{label2}', complex=True)
            else:
                beta_symbol = Symbol(f'beta_{label2}{label1}', complex=True)

            # Apply conjugation rules
            same_conj = (node1_conj == node2_conj)

            if same_conj:
                # Both same: beta_{jk} = beta_{kj}^*
                if i < j:
                    M_entries[i][j] = beta_symbol
                    M_entries[j][i] = beta_symbol.conjugate()
                else:
                    M_entries[i][j] = beta_symbol.conjugate()
                    M_entries[j][i] = beta_symbol
            else:
                # Different: anti-conjugate with minus sign
                if i < j:
                    M_entries[i][j] = beta_symbol
                    M_entries[j][i] = -beta_symbol.conjugate()
                else:
                    M_entries[i][j] = -beta_symbol.conjugate()
                    M_entries[j][i] = beta_symbol

        return Matrix(M_entries)

    def _get_symbol_label(self, node):
        """Get clean symbol label from node (remove subscript underscores)"""
        label = node['label']
        # Remove underscores and braces for symbol names
        return label.replace('_', '').replace('{', '').replace('}', '').replace('^', '').replace('*', '')

    def _simplify_with_magnitude_squared(self, matrix):
        """Simplify matrix with custom rule: x * conjugate(x) -> |x|^2"""

        # First do standard simplification
        matrix = simplify(matrix)

        # Apply element-wise replacement for x * conjugate(x) -> |x|^2
        def replace_conj_products(expr):
            """Recursively replace x * conjugate(x) with |x|^2"""

            # Recursively process Add expressions
            if isinstance(expr, Add):
                return Add(*[replace_conj_products(arg) for arg in expr.args])

            # Base case: not a multiplication
            if not isinstance(expr, Mul):
                return expr

            # Check all pairs of arguments for conjugate pairs
            args = list(expr.args)
            changed = True

            while changed:
                changed = False
                for i in range(len(args)):
                    for j in range(len(args)):
                        if i != j:
                            # Check if args[i] and args[j] form a conjugate pair
                            # Case 1: args[i] is conjugate(x) and args[j] is x
                            if hasattr(args[i], 'func') and args[i].func == conjugate:
                                if len(args[i].args) > 0 and args[i].args[0] == args[j]:
                                    # Found conjugate(x) * x, replace with |x|^2
                                    remaining_args = [args[k] for k in range(len(args)) if k != i and k != j]
                                    if remaining_args:
                                        return replace_conj_products(Mul(Abs(args[j])**2, *remaining_args))
                                    else:
                                        return Abs(args[j])**2

                            # Case 2: args[j] is conjugate(x) and args[i] is x
                            if hasattr(args[j], 'func') and args[j].func == conjugate:
                                if len(args[j].args) > 0 and args[j].args[0] == args[i]:
                                    # Found x * conjugate(x), replace with |x|^2
                                    remaining_args = [args[k] for k in range(len(args)) if k != i and k != j]
                                    if remaining_args:
                                        return replace_conj_products(Mul(Abs(args[i])**2, *remaining_args))
                                    else:
                                        return Abs(args[i])**2

            return expr

        # Apply to each matrix element, then cancel and simplify to split fractions properly
        matrix = matrix.applyfunc(replace_conj_products)

        def cancel_and_split(expr):
            """Cancel common factors and attempt to split fractions"""

            # First cancel
            expr = cancel(expr)

            # Try to split fractions by polynomial division
            try:
                numer, denom = fraction(expr)
                if denom != 1:
                    # Expand both to standard form
                    numer_exp = expand(numer)
                    denom_exp = expand(denom)

                    # Try using factor_terms which can extract common factors
                    result = factor_terms(numer_exp / denom_exp)

                    # If that worked, return it
                    if result != expr:
                        return simplify(result)

                    # Alternative: manually try to extract whole parts
                    # Collect terms by the denominator as a variable
                    if isinstance(numer_exp, Add):
                        # Find the GCD of all numerator terms with respect to denom
                        from sympy import gcd as sympy_gcd, Poly, symbols as sympy_symbols

                        # Try to see if we can factor out (denom) from some terms
                        # This is tricky with Abs() so we'll try a simpler heuristic
                        # Divide numerator by denominator and see if we get quotient + remainder
                        try:
                            quotient = cancel(numer_exp / denom_exp)
                            quot_numer, quot_denom = fraction(quotient)

                            # If quotient simplified (denominator reduced), reconstruct
                            if quot_denom != denom_exp:
                                # We have partial cancellation
                                # Reconstruct as: quotient_whole + remainder/denom
                                # where numer = quotient_whole * denom + remainder

                                # Try to extract integer/whole part
                                # This is a heuristic: subtract denom * simple_factors and see what's left
                                pass
                        except:
                            pass
            except:
                pass

            return simplify(expr)

        matrix = matrix.applyfunc(cancel_and_split)
        return matrix

    def _post_process_latex(self, latex_str):
        """Post-process LaTeX string to use asterisk notation and fix beta subscripts"""

        # Helper function to replace \overline{...} with {...}^{*}
        def replace_overlines(s):
            r"""Replace all \overline{...} with {...}^{*}"""
            max_iterations = 20  # Safety limit
            iteration = 0

            while r'\overline' in s and iteration < max_iterations:
                iteration += 1
                # Match \overline{...} where ... can contain balanced braces
                # Use a helper function to find matching brace
                def find_matching_brace(text, start_pos):
                    """Find the position of the closing brace matching the opening brace at start_pos"""
                    if start_pos >= len(text) or text[start_pos] != '{':
                        return -1

                    depth = 0
                    for i in range(start_pos, len(text)):
                        if text[i] == '{':
                            depth += 1
                        elif text[i] == '}':
                            depth -= 1
                            if depth == 0:
                                return i
                    return -1

                # Find all \overline occurrences
                pos = s.find(r'\overline{')
                if pos == -1:
                    break

                # Find the matching closing brace
                open_brace_pos = pos + len(r'\overline')
                close_brace_pos = find_matching_brace(s, open_brace_pos)

                if close_brace_pos == -1:
                    break

                # Extract the content between braces
                content = s[open_brace_pos + 1:close_brace_pos]

                # Replace this occurrence with asterisk notation
                replacement = f'{{{content}}}^{{*}}'
                s = s[:pos] + replacement + s[close_brace_pos + 1:]

            return s

        # Fix 1: First pass - replace overlines
        latex_str = replace_overlines(latex_str)

        # Fix 2: Replace x * x^{*} patterns with |x|^2 in LaTeX
        # Helper function to find and replace magnitude squared patterns
        def replace_magnitude_squared_patterns(s):
            """Find x * x^{*} patterns and replace with |x|^2"""
            changed = True
            max_iter = 20
            iteration = 0

            while changed and iteration < max_iter:
                iteration += 1
                changed = False

                # Pattern 1: \beta_{...} {\beta_{...}}^{*} (second symbol wrapped in braces, space optional)
                pattern1 = r'(\\beta_\{[^}]+\})\s*\{(\\beta_\{[^}]+\})\}\^\{\*\}'
                matches = list(re.finditer(pattern1, s))
                for match in reversed(matches):  # Process from end to avoid index shifts
                    sym1 = match.group(1)
                    sym2 = match.group(2)
                    if sym1 == sym2:  # Same symbol
                        replacement = f'{{|{sym1}|}}^{{2}}'
                        s = s[:match.start()] + replacement + s[match.end():]
                        changed = True

                # Pattern 2: {\beta_{...}}^{*} \beta_{...}
                pattern2 = r'\{(\\beta_\{[^}]+\})\}\^\{\*\}\s*(\\beta_\{[^}]+\})'
                matches = list(re.finditer(pattern2, s))
                for match in reversed(matches):
                    sym1 = match.group(1)
                    sym2 = match.group(2)
                    if sym1 == sym2:
                        replacement = f'{{|{sym1}|}}^{{2}}'
                        s = s[:match.start()] + replacement + s[match.end():]
                        changed = True

                # Pattern 3: \Delta_{...} {\Delta_{...}}^{*}
                pattern3 = r'(\\Delta_\{[^}]+\})\s*\{(\\Delta_\{[^}]+\})\}\^\{\*\}'
                matches = list(re.finditer(pattern3, s))
                for match in reversed(matches):
                    sym1 = match.group(1)
                    sym2 = match.group(2)
                    if sym1 == sym2:
                        replacement = f'{{|{sym1}|}}^{{2}}'
                        s = s[:match.start()] + replacement + s[match.end():]
                        changed = True

                # Pattern 4: {\Delta_{...}}^{*} \Delta_{...}
                pattern4 = r'\{(\\Delta_\{[^}]+\})\}\^\{\*\}\s*(\\Delta_\{[^}]+\})'
                matches = list(re.finditer(pattern4, s))
                for match in reversed(matches):
                    sym1 = match.group(1)
                    sym2 = match.group(2)
                    if sym1 == sym2:
                        replacement = f'{{|{sym1}|}}^{{2}}'
                        s = s[:match.start()] + replacement + s[match.end():]
                        changed = True

            return s

        latex_str = replace_magnitude_squared_patterns(latex_str)

        # Fix 3: Second pass - replace any remaining overlines (from simplification)
        latex_str = replace_overlines(latex_str)

        # Fix 4: Convert \left|{...}\right| to |...| for magnitude squared notation
        # Pattern: \left|{content}\right|^{2} -> {|content|}^{2}
        latex_str = latex_str.replace(r'\left|{', '{|').replace(r'}\right|', '|}')

        # Fix 5: Ensure \beta is present in subscripts (SymPy sometimes drops the backslash)
        # Match patterns like "beta_{...}" without backslash
        latex_str = re.sub(r'(?<!\\)beta_', r'\\beta_', latex_str)

        # Fix 6: Same for Delta
        latex_str = re.sub(r'(?<!\\)Delta_', r'\\Delta_', latex_str)

        return latex_str

    def _generate_latex_matrix_string_for_nodes(self, nodes):
        """Generate LaTeX matrix string for a subset of nodes"""
        # This is a simplified version for when no reduction is needed
        # Just show the submatrix for selected nodes

        n = len(nodes)
        M_full = self._build_symbolic_matrix()
        all_nodes = self.graphulator.nodes
        node_to_idx = {id(node): i for i, node in enumerate(all_nodes)}
        selected_indices = [node_to_idx[id(n)] for n in nodes]

        M_sub = M_full[selected_indices, :][:, selected_indices]
        latex_str = latex(M_sub)
        latex_str = self._post_process_latex(latex_str)
        return latex_str

    def _on_matrix_subtab_changed(self, index):
        """Handle switching between Original and Kron matrix subtabs"""
        # When switching to Kron tab during reduction mode, update display
        if index == 1:  # Kron tab
            self._update_kron_matrix_display()

    def _on_graph_subtab_changed(self, index):
        """Handle switching between Original and Kron graph subtabs"""
        # The subtab change just needs to trigger a redraw
        # The actual graphs are already rendered when the tab becomes visible
        pass

    def _update_scaling_param(self, key, value):
        """Update a scaling parameter"""
        self.graphulator.export_rescale[key] = value
        # If it's the GUI parameter, update the plot immediately
        if key == 'GUI_SELFLOOP_LABEL_SCALE':
            self.graphulator._update_plot()

    def _reset_scaling_params(self):
        """Reset all scaling parameters to defaults"""
        defaults = EXPORT_RESCALE_DEFAULTS

        for key, value in defaults.items():
            self.graphulator.export_rescale[key] = value
            if key in self.scaling_spinboxes:
                self.scaling_spinboxes[key].setValue(value)

        self.graphulator._update_plot()

    def _set_current_as_defaults(self):
        """Update the default values in the code to match current settings"""
        current_values = self.graphulator.export_rescale.copy()

        # Create a formatted string for the new defaults
        lines = []
        lines.append("New default values to update in your code:\n")
        lines.append("self.export_rescale = {")
        for key, value in current_values.items():
            if isinstance(value, tuple):
                lines.append(f"    '{key}': {value},")
            elif isinstance(value, float):
                lines.append(f"    '{key}': {value:.3f},")
            else:
                lines.append(f"    '{key}': {value},")
        lines.append("}")

        message = "\n".join(lines)

        # Show a dialog with the values
        dialog = QDialog(self)
        dialog.setWindowTitle("Default Values")
        dialog.setMinimumWidth(500)
        dialog.setMinimumHeight(400)

        layout = QVBoxLayout()

        info_label = QLabel("Copy these values to update the defaults in graphulator_qt.py\n"
                           "(around line 952 in the __init__ method):")
        layout.addWidget(info_label)

        text_edit = QTextEdit()
        text_edit.setPlainText(message)
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.setLayout(layout)
        dialog.exec()

    def _save_scaling_preset(self):
        """Save current scaling parameters to a JSON file"""
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Scaling Preset",
            "",
            "JSON Files (*.json);;All Files (*)"
        )

        if filename:
            try:
                preset_data = {
                    'version': '1.0',
                    'description': 'Graphulator export scaling preset',
                    'parameters': self.graphulator.export_rescale.copy()
                }

                with open(filename, 'w') as f:
                    json.dump(preset_data, f, indent=2)

                QMessageBox.information(
                    self,
                    "Preset Saved",
                    f"Scaling preset saved to:\n{filename}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error Saving Preset",
                    f"Failed to save preset:\n{str(e)}"
                )

    def _load_scaling_preset(self):
        """Load scaling parameters from a JSON file"""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Load Scaling Preset",
            "",
            "JSON Files (*.json);;All Files (*)"
        )

        if filename:
            try:
                with open(filename, 'r') as f:
                    preset_data = json.load(f)

                # Validate preset data
                if 'parameters' not in preset_data:
                    raise ValueError("Invalid preset file: missing 'parameters' key")

                parameters = preset_data['parameters']

                # Update the export_rescale dictionary and UI spinboxes
                for key, value in parameters.items():
                    if key in self.graphulator.export_rescale:
                        self.graphulator.export_rescale[key] = value
                        if key in self.scaling_spinboxes:
                            self.scaling_spinboxes[key].setValue(value)

                # Update the GUI
                self.graphulator._update_plot()

                QMessageBox.information(
                    self,
                    "Preset Loaded",
                    f"Scaling preset loaded from:\n{filename}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error Loading Preset",
                    f"Failed to load preset:\n{str(e)}"
                )

    def clear_properties(self):
        """Clear all property widgets and layouts"""
        # Remove all items (widgets and layouts) from properties layout
        while self.properties_layout.count():
            item = self.properties_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # Recursively clear and delete nested layouts
                self._clear_layout(item.layout())

    def _show_help_dialog(self):
        """Show help dialog"""

        dialog = QDialog(self)
        dialog.setWindowTitle("Graphulator Help")
        dialog.resize(700, 800)

        layout = QVBoxLayout()
        dialog.setLayout(layout)

        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setStyleSheet("font-family: sans-serif; font-size: 11px;")

        # Try to load help content from help_para.md file
        help_content = None
        try:
            # Get path to help_para.md - handle both development and PyInstaller bundle
            script_dir = os.path.dirname(os.path.abspath(__file__))
            help_file = os.path.join(script_dir, 'help_para.md')

            # Check for PyInstaller bundle
            if not os.path.exists(help_file) and getattr(sys, 'frozen', False):
                bundle_dir = sys._MEIPASS
                help_file = os.path.join(bundle_dir, 'graphulator', 'help_para.md')

            if os.path.exists(help_file):
                with open(help_file, 'r') as f:
                    markdown_content = f.read()

                # Process shortcut templates if shortcut manager is available
                if hasattr(self.graphulator, 'shortcut_manager'):
                    from .para_ui.doc_template import DocumentationTemplateProcessor
                    processor = DocumentationTemplateProcessor(self.graphulator.shortcut_manager)
                    markdown_content = processor.process_markdown(markdown_content)

                # Try to convert markdown to HTML using markdown library
                try:
                    import markdown
                    help_content = markdown.markdown(
                        markdown_content,
                        extensions=['tables', 'nl2br']
                    )
                except ImportError:
                    # markdown library not available, use simple conversion
                    help_content = self._simple_markdown_to_html(markdown_content)
        except Exception as e:
            logger.warning("Could not load help_para.md: %s", e)

        # Fall back to hardcoded content if loading failed
        if help_content is None:
            help_content = """<b>Controls:</b><br>
• g: Place single node<br>
• Shift+G: Continuous node mode<br>
• Ctrl+G: Auto-increment mode<br>
• e: Place single edge<br>
• Ctrl+E: Continuous edge mode<br>
• c: Conjugation mode<br>
• Esc: Exit mode / Clear selection<br>
• r: Rotate grid (45° / 30°)<br>
• t: Toggle grid (square/triangular)<br>
• a: Auto-fit view<br>
• +/-: Zoom in/out<br>
<br>
<b>Selection & Editing:</b><br>
• Left click: Select / drag node<br>
• Right click: Color (nodes) / Width (edges) menu<br>
• Shift+click: Multi-select<br>
• Click+drag: Selection window<br>
• Double-click: Edit properties<br>
• Up/Down: Node/edge size<br>
• Left/Right: Label size<br>
• Shift+arrows: Nudge labels<br>
• Ctrl+A: Select all<br>
• Ctrl+C/X/V: Copy/cut/paste<br>
• Ctrl+Z: Undo<br>
• Ctrl+U: Rotate nodes 15° CCW<br>
• Ctrl+I: Rotate nodes 15° CW<br>
• d or Delete: Delete<br>
• f: Flip edge labels<br>
• Shift+F: Edge rotation mode<br>
<br>
<b>Basis Ordering:</b><br>
• Ctrl+B: Toggle basis ordering mode<br>
• Click nodes: Select basis order<br>
• Ctrl+Shift+Enter: Commit basis order<br>
• Esc: Cancel basis ordering<br>
• Ctrl+Z: Undo last selection<br>
• Ctrl+Shift+Z: Redo selection<br>
<br>
<b>Other:</b><br>
• Ctrl+Shift+E: Export code<br>
• Ctrl+Shift+C: Clear all<br>
• Ctrl+L: Toggle LaTeX<br>
• Ctrl+Q: Quit"""

        help_text.setHtml(help_content)
        layout.addWidget(help_text)

        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.close)
        layout.addWidget(close_button)

        dialog.show()  # Non-modal - allows interaction with main window

    def _simple_markdown_to_html(self, markdown_text):
        """Simple markdown to HTML conversion for basic formatting"""

        html = markdown_text

        # Convert headers
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)

        # Convert bold/italic
        html = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', html)
        html = re.sub(r'\*(.+?)\*', r'<i>\1</i>', html)

        # Convert code blocks
        html = re.sub(r'`(.+?)`', r'<code style="background: #f0f0f0; padding: 2px 4px;">\1</code>', html)

        # Convert tables (simple approach)
        lines = html.split('\n')
        in_table = False
        table_html = []

        for line in lines:
            if '|' in line and not line.strip().startswith('|---'):
                if not in_table:
                    table_html.append('<table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; margin: 10px 0;">')
                    in_table = True

                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                row_html = '<tr>' + ''.join(f'<td style="border: 1px solid #ddd; padding: 8px;">{cell}</td>' for cell in cells) + '</tr>'
                table_html.append(row_html)
            elif in_table and not ('|' in line):
                table_html.append('</table>')
                in_table = False
                table_html.append(line)
            else:
                if line.strip().startswith('|---'):
                    continue  # Skip separator lines
                table_html.append(line)

        if in_table:
            table_html.append('</table>')

        html = '\n'.join(table_html)

        # Convert horizontal rules
        html = re.sub(r'^---+$', '<hr>', html, flags=re.MULTILINE)

        # Convert bullets
        html = re.sub(r'^- (.+)$', r'• \1', html, flags=re.MULTILINE)

        # Convert line breaks - double newlines to paragraph breaks
        html = html.replace('\n\n', '<br><br>')

        return html

    def _show_tutorial_dialog(self):
        """Show tutorial in a non-modal window with markdown and image support"""

        # Close existing tutorial window if open
        if hasattr(self, 'tutorial_dialog') and self.tutorial_dialog is not None:
            try:
                self.tutorial_dialog.close()
            except:
                pass

        # Create non-modal dialog that stays on top of parent app (but not other apps)
        dialog = QDialog(self)
        dialog.setWindowTitle("Paragraphulator Tutorial")
        dialog.setWindowFlag(Qt.WindowType.Tool, True)
        dialog.resize(850, 700)

        layout = QVBoxLayout()
        dialog.setLayout(layout)

        # Use ZoomableWebView for proper rendering with images
        tutorial_view = ZoomableWebView()
        layout.addWidget(tutorial_view)

        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(lambda: dialog.close())
        layout.addWidget(close_button)

        # Try to load tutorial.md - handle both development and PyInstaller bundle
        import tempfile
        diagnostic_info = []
        is_frozen = getattr(sys, 'frozen', False)
        diagnostic_info.append(f"Frozen app: {is_frozen}")

        script_dir = os.path.dirname(os.path.abspath(__file__))
        tutorial_file = os.path.join(script_dir, 'tutorial.md')
        tutorial_images_dir = os.path.join(script_dir, 'tutorial_images')
        diagnostic_info.append(f"Script dir: {script_dir}")
        diagnostic_info.append(f"Initial tutorial path: {tutorial_file}")
        diagnostic_info.append(f"Initial tutorial exists: {os.path.exists(tutorial_file)}")

        # Check for PyInstaller bundle
        if not os.path.exists(tutorial_file) and is_frozen:
            bundle_dir = sys._MEIPASS
            diagnostic_info.append(f"Bundle dir (_MEIPASS): {bundle_dir}")
            tutorial_file = os.path.join(bundle_dir, 'graphulator', 'tutorial.md')
            tutorial_images_dir = os.path.join(bundle_dir, 'graphulator', 'tutorial_images')
            diagnostic_info.append(f"Bundle tutorial path: {tutorial_file}")
            diagnostic_info.append(f"Bundle tutorial exists: {os.path.exists(tutorial_file)}")
            # List bundle contents for debugging
            try:
                graphulator_dir = os.path.join(bundle_dir, 'graphulator')
                if os.path.exists(graphulator_dir):
                    contents = os.listdir(graphulator_dir)
                    diagnostic_info.append(f"Bundle graphulator/ contents: {contents[:20]}...")
            except Exception as e:
                diagnostic_info.append(f"Could not list bundle contents: {e}")

        tutorial_content = None
        load_error = None
        if os.path.exists(tutorial_file):
            try:
                with open(tutorial_file, 'r', encoding='utf-8') as f:
                    markdown_text = f.read()
                diagnostic_info.append(f"Markdown loaded: {len(markdown_text)} chars")

                # Process shortcut templates if shortcut manager is available
                if hasattr(self.graphulator, 'shortcut_manager'):
                    from .para_ui.doc_template import DocumentationTemplateProcessor
                    processor = DocumentationTemplateProcessor(self.graphulator.shortcut_manager)
                    markdown_text = processor.process_markdown(markdown_text)
                    diagnostic_info.append("Shortcut templates processed")

                tutorial_content = self._render_tutorial_markdown(markdown_text, tutorial_images_dir)
                diagnostic_info.append(f"HTML rendered: {len(tutorial_content)} chars")
            except Exception as e:
                load_error = f"{e}\n{traceback.format_exc()}"
                diagnostic_info.append(f"Load error: {load_error}")

        if tutorial_content is None:
            diag_html = "<br>".join(diagnostic_info)
            error_msg = f"<p style='color:red;'>{load_error}</p>" if load_error else ""
            tutorial_content = f'''<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: sans-serif; padding: 20px; color: #333; }}
        h1 {{ color: #cc0000; }}
        code {{ background: #f0f0f0; padding: 2px 5px; }}
        .diag {{ background: #f8f8f8; padding: 10px; margin-top: 20px; font-size: 12px; }}
    </style>
</head>
<body>
    <h1>Tutorial Not Found</h1>
    <p>The tutorial file (tutorial.md) was not found or could not be loaded.</p>
    <p>Expected location: <code>{tutorial_file}</code></p>
    {error_msg}
    <div class="diag">
        <strong>Diagnostic Information:</strong><br>
        {diag_html}
    </div>
</body>
</html>'''

        # Write HTML to temp file and load via URL (setHtml has ~2MB limit)
        # Use system temp directory (bundle directories may be read-only)
        temp_dir = tempfile.gettempdir()
        temp_tutorial_path = os.path.join(temp_dir, 'graphulator_tutorial.html')
        diagnostic_info.append(f"Temp file path: {temp_tutorial_path}")

        try:
            with open(temp_tutorial_path, 'w', encoding='utf-8') as f:
                f.write(tutorial_content)
            diagnostic_info.append(f"Temp file written: {os.path.exists(temp_tutorial_path)}")

            # On Windows, ensure proper file:// URL format
            temp_url = QUrl.fromLocalFile(temp_tutorial_path)
            diagnostic_info.append(f"Loading URL: {temp_url.toString()}")

            # Add load finished handler to detect failures
            def on_load_finished(ok):
                if not ok:
                    # Loading failed - show diagnostic info directly via setHtml
                    diag_html = "<br>".join(diagnostic_info)
                    fallback_html = f'''<html><body style="font-family:sans-serif;padding:20px;">
                        <h2 style="color:red;">Tutorial Load Failed</h2>
                        <p>The tutorial could not be loaded from: {temp_url.toString()}</p>
                        <div style="background:#f0f0f0;padding:10px;font-size:11px;">
                            <strong>Diagnostics:</strong><br>{diag_html}
                        </div>
                    </body></html>'''
                    tutorial_view.setHtml(fallback_html)

            tutorial_view.loadFinished.connect(on_load_finished)
            tutorial_view.setUrl(temp_url)
        except Exception as e:
            # If temp file fails, try setHtml as fallback (may truncate large content)
            diagnostic_info.append(f"Temp file error: {e}, falling back to setHtml")
            tutorial_view.setHtml(tutorial_content)

        # Keep reference to prevent garbage collection
        self.tutorial_dialog = dialog

        dialog.show()  # Non-modal

    def _render_tutorial_markdown(self, markdown_text, images_dir):
        """Render markdown for tutorial with image support"""
        import base64

        text = markdown_text

        # Get the script directory for absolute paths
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # Process images: ![alt](path) -> <img src="data:image/...;base64,..." alt="alt">
        # Embed images as base64 data URIs to avoid file access security issues
        def image_replacer(match):
            alt_text = match.group(1)
            img_path = match.group(2)

            # Build absolute path to image
            if img_path.startswith('tutorial_images/'):
                abs_path = os.path.join(script_dir, img_path)
            elif '/' not in img_path:
                # Just filename, assume tutorial_images/
                abs_path = os.path.join(script_dir, 'tutorial_images', img_path)
            else:
                # Already has a path, treat as relative to script_dir
                abs_path = os.path.join(script_dir, img_path)

            # Embed as base64 data URI to avoid file access security issues
            try:
                if os.path.exists(abs_path):
                    # Determine MIME type from extension
                    ext = os.path.splitext(abs_path)[1].lower()
                    mime_types = {
                        '.png': 'image/png',
                        '.jpg': 'image/jpeg',
                        '.jpeg': 'image/jpeg',
                        '.gif': 'image/gif',
                        '.webp': 'image/webp',
                        '.svg': 'image/svg+xml',
                    }
                    mime_type = mime_types.get(ext, 'image/png')

                    with open(abs_path, 'rb') as f:
                        img_data = base64.b64encode(f.read()).decode('utf-8')
                    return f'<img src="data:{mime_type};base64,{img_data}" alt="{alt_text}" style="max-width: 100%; height: auto; margin: 10px 0;">'
                else:
                    return f'<span style="color: red;">[Image not found: {img_path}]</span>'
            except Exception as e:
                return f'<span style="color: red;">[Error loading image: {e}]</span>'

        text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', image_replacer, text)

        # Strip HTML comments early (before other processing)
        text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)

        # Protect code blocks from processing
        code_blocks = {}
        code_counter = [0]

        def protect_code_block(match):
            placeholder = f"CODEBLOCK{code_counter[0]:04d}ENDCODE"
            code_counter[0] += 1
            lang = match.group(1) or ''
            code = html_module.escape(match.group(2))
            code_blocks[placeholder] = f'<pre><code class="{lang}">{code}</code></pre>'
            return placeholder

        text = re.sub(r'```(\w*)\n(.*?)\n```', protect_code_block, text, flags=re.DOTALL)

        # Inline code
        inline_codes = {}
        inline_counter = [0]

        def protect_inline_code(match):
            placeholder = f"INLINECODE{inline_counter[0]:04d}ENDINLINE"
            inline_counter[0] += 1
            code = html_module.escape(match.group(1))
            inline_codes[placeholder] = f'<code>{code}</code>'
            return placeholder

        text = re.sub(r'`([^`]+)`', protect_inline_code, text)

        # Protect math blocks from HTML escaping (so KaTeX can render them)
        math_blocks = {}
        math_counter = [0]

        def protect_math(match):
            placeholder = f"MATHBLOCK{math_counter[0]:04d}ENDMATH"
            math_counter[0] += 1
            math_blocks[placeholder] = match.group(0)  # Keep original including delimiters
            return placeholder

        # Protect display math first ($$...$$), then inline math ($...$)
        text = re.sub(r'\$\$(.+?)\$\$', protect_math, text, flags=re.DOTALL)
        text = re.sub(r'\$([^\$\n]+?)\$', protect_math, text)

        # GitHub-style callout blocks: > [!TYPE] followed by > content lines
        callout_blocks = {}
        callout_counter = [0]

        def process_callout(match):
            placeholder = f"CALLOUT{callout_counter[0]:04d}ENDCALLOUT"
            callout_counter[0] += 1
            callout_type = match.group(1).lower()  # tip, warning, note, etc.
            content_lines = match.group(2).strip()
            # Remove leading "> " from each line
            content = re.sub(r'^>\s?', '', content_lines, flags=re.MULTILINE)
            # Convert newlines to <br> for multi-line callouts
            content = content.replace('\n', '<br>\n')
            # Map callout types to CSS classes
            css_class = callout_type if callout_type in ['tip', 'warning', 'note', 'important', 'caution'] else 'note'
            callout_blocks[placeholder] = f'<div class="callout {css_class}"><strong>{callout_type.upper()}:</strong> {content}</div>'
            return placeholder

        # Match > [!TYPE] followed by continuation lines starting with >
        text = re.sub(
            r'^> \[!(\w+)\]\n((?:>.*\n?)+)',
            process_callout,
            text,
            flags=re.MULTILINE
        )

        # Escape HTML (but not our placeholders)
        lines = text.split('\n')
        escaped_lines = []
        for line in lines:
            # Don't escape lines that are already HTML (from image processing)
            if '<img' in line:
                escaped_lines.append(line)
            else:
                escaped_lines.append(html_module.escape(line))
        text = '\n'.join(escaped_lines)

        # Headers
        text = re.sub(r'^###### (.+)$', r'<h6>\1</h6>', text, flags=re.MULTILINE)
        text = re.sub(r'^##### (.+)$', r'<h5>\1</h5>', text, flags=re.MULTILINE)
        text = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', text, flags=re.MULTILINE)
        text = re.sub(r'^### (.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
        text = re.sub(r'^## (.+)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
        text = re.sub(r'^# (.+)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)

        # Bold and italic
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        text = re.sub(r'_([^_]+)_', r'<em>\1</em>', text)

        # Horizontal rule
        text = re.sub(r'^[-*]{3,}$', r'<hr>', text, flags=re.MULTILINE)

        # Blockquote
        text = re.sub(r'^&gt; (.+)$', r'<blockquote>\1</blockquote>', text, flags=re.MULTILINE)

        # Tables: | col1 | col2 | ... with |---|---| separator
        def is_separator_row(line):
            """Check if a line is a table separator row like |---|---|"""
            cells = line.split('|')[1:-1]  # Get cells between pipes
            if not cells:
                return False
            # Each cell should contain only dashes, colons, and spaces
            for cell in cells:
                if not re.match(r'^[\s\-:]+$', cell):
                    return False
            return True

        def process_table(match):
            table_text = match.group(0)
            lines = table_text.strip().split('\n')
            if len(lines) < 2:
                return table_text  # Not a valid table

            html_rows = []
            is_header = True
            for i, line in enumerate(lines):
                line = line.strip()
                if not line.startswith('|'):
                    continue
                # Skip separator row (|---|---|)
                if is_separator_row(line):
                    is_header = False
                    continue
                # Parse cells
                cells = [cell.strip() for cell in line.split('|')[1:-1]]  # Remove empty first/last
                if is_header:
                    row_html = '<tr>' + ''.join(f'<th>{cell}</th>' for cell in cells) + '</tr>'
                else:
                    row_html = '<tr>' + ''.join(f'<td>{cell}</td>' for cell in cells) + '</tr>'
                html_rows.append(row_html)

            if html_rows:
                return '\n<table>' + '\n'.join(html_rows) + '</table>\n'
            return table_text

        # Match table blocks (consecutive lines starting with |, allow trailing whitespace)
        text = re.sub(r'(^\|.+\|\s*$\n?)+', process_table, text, flags=re.MULTILINE)

        # Links: [text](url)
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)

        # Ordered lists (process first with temporary marker to distinguish from unordered)
        # Keep the number in the marker so we can extract the start value
        text = re.sub(r'^(\d+)\. (.+)$', r'<oli data-num="\1">\2</oli>', text, flags=re.MULTILINE)

        # Wrap consecutive ordered list items in <ol> with correct start attribute
        def wrap_ordered_list(match):
            items = match.group(0)
            # Extract the first number from the first item
            first_num_match = re.search(r'data-num="(\d+)"', items)
            start_num = first_num_match.group(1) if first_num_match else "1"
            # Remove the data-num attributes
            items = re.sub(r' data-num="\d+"', '', items)
            if start_num == "1":
                return f'<ol>{items}</ol>'
            else:
                return f'<ol start="{start_num}">{items}</ol>'

        text = re.sub(r'(<oli[^>]*>.*?</oli>\n?)+', wrap_ordered_list, text)

        # Unordered lists (won't match <oli> items)
        text = re.sub(r'^[-*] (.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)
        text = re.sub(r'(<li>.*</li>\n?)+', r'<ul>\g<0></ul>', text)

        # Now convert <oli> to <li> (after unordered list processing)
        text = text.replace('<oli>', '<li>').replace('</oli>', '</li>')

        # Restore callouts first (they may contain inline code/math placeholders)
        for placeholder, callout_html in callout_blocks.items():
            text = text.replace(placeholder, callout_html)
        # Then restore code blocks, inline code, and math blocks
        for placeholder, code_html in code_blocks.items():
            text = text.replace(placeholder, code_html)
        for placeholder, code_html in inline_codes.items():
            text = text.replace(placeholder, code_html)
        for placeholder, math_text in math_blocks.items():
            text = text.replace(placeholder, math_text)

        # Convert remaining newlines to <br> for paragraph flow
        text = re.sub(r'\n\n+', '</p><p>', text)
        text = re.sub(r'\n', '<br>\n', text)

        # Clean up <br> tags inside/around block elements (tables, lists)
        try:
            # Remove <br> before block elements
            text = re.sub(r'(<br>\s*)+(<table|<ul|<ol|<div)', r'\2', text)
            # Remove <br> after block element opening tags
            text = re.sub(r'(<table>|<ul>|<ol>|<div[^>]*>)\s*(<br>\s*)+', r'\1', text)
            # Remove <br> before block element closing tags
            text = re.sub(r'(<br>\s*)+(</table>|</ul>|</ol>|</div>)', r'\2', text)
            # Remove <br> after block element closing tags
            text = re.sub(r'(</table>|</ul>|</ol>|</div>)\s*(<br>\s*)+', r'\1', text)
            # Remove <br> between list items
            text = re.sub(r'(</li>)\s*(<br>\s*)+(<li)', r'\1\3', text)
            # Remove <br> between table rows
            text = re.sub(r'(</tr>)\s*(<br>\s*)+(<tr)', r'\1\3', text)
        except Exception as e:
            print(f"Error in cleanup regexes: {e}")

        # Get KaTeX header for LaTeX support (use absolute paths since HTML is in temp dir)
        katex_header = self._get_katex_html_header_absolute()

        html_content = f'''<!DOCTYPE html>
<html>
<head>
    {katex_header}
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            font-size: 14px;
            line-height: 1.6;
            padding: 20px;
            max-width: 800px;
            margin: 0 auto;
            color: #333;
        }}
        h1, h2, h3, h4, h5, h6 {{
            margin-top: 1.2em;
            margin-bottom: 0.5em;
            color: #222;
        }}
        h1 {{ font-size: 1.8em; border-bottom: 2px solid #0066cc; padding-bottom: 0.3em; color: #0066cc; }}
        h2 {{ font-size: 1.5em; border-bottom: 1px solid #ddd; padding-bottom: 0.3em; }}
        h3 {{ font-size: 1.3em; }}
        p {{ margin: 0.5em 0; }}
        code {{
            background: #f4f4f4;
            padding: 2px 5px;
            border-radius: 3px;
            font-family: "Menlo", "Monaco", "Consolas", monospace;
            font-size: 0.9em;
        }}
        pre {{
            background: #f4f4f4;
            padding: 12px;
            border-radius: 5px;
            overflow-x: auto;
            border: 1px solid #ddd;
        }}
        pre code {{
            background: none;
            padding: 0;
        }}
        blockquote {{
            border-left: 4px solid #0066cc;
            margin: 1em 0;
            padding: 0.5em 15px;
            color: #555;
            background: #f9f9f9;
        }}
        ul, ol {{
            padding-left: 25px;
        }}
        li {{
            margin: 5px 0;
        }}
        a {{
            color: #0066cc;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        hr {{
            border: none;
            border-top: 1px solid #ddd;
            margin: 25px 0;
        }}
        table {{
            border-collapse: collapse;
            margin: 10px 0;
            width: auto;
            display: block;
        }}
        br + table {{
            margin-top: 5px;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px 12px;
            text-align: left;
        }}
        th {{
            background: #f4f4f4;
            font-weight: bold;
        }}
        tr:nth-child(even) {{
            background: #fafafa;
        }}
        img {{
            border: 1px solid #ddd;
            border-radius: 4px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .callout {{
            padding: 10px 15px;
            margin: 15px 0;
            border-radius: 0 4px 4px 0;
            border-left: 4px solid #666;
            background: #f5f5f5;
        }}
        .callout strong {{
            display: block;
            margin-bottom: 5px;
        }}
        .callout.tip {{
            background: #e7f3ff;
            border-left-color: #0066cc;
        }}
        .callout.note {{
            background: #e7f3ff;
            border-left-color: #0066cc;
        }}
        .callout.warning {{
            background: #fff3e0;
            border-left-color: #ff9800;
        }}
        .callout.caution {{
            background: #fff3e0;
            border-left-color: #ff9800;
        }}
        .callout.important {{
            background: #fce4ec;
            border-left-color: #e91e63;
        }}
    </style>
</head>
<body>
<p>{text}</p>
<script>
    // Render LaTeX using KaTeX
    document.addEventListener("DOMContentLoaded", function() {{
        if (typeof renderMathInElement !== 'undefined') {{
            renderMathInElement(document.body, {{
                delimiters: [
                    {{left: "$$", right: "$$", display: true}},
                    {{left: "$", right: "$", display: false}},
                    {{left: "\\\\[", right: "\\\\]", display: true}},
                    {{left: "\\\\(", right: "\\\\)", display: false}}
                ],
                throwOnError: false
            }});
        }}
    }});
</script>
</body>
</html>'''
        return html_content

    def _clear_layout(self, layout):
        """Recursively clear a layout"""
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    self._clear_layout(item.layout())

    def show_node_properties(self, node):
        """Show properties for a node"""
        self.clear_properties()
        self.current_object = node
        self.current_type = 'node'
        self.title_label.setText(f"Node: {node['label']}")

        # Create form layout for properties
        form = QFormLayout()

        # Label
        self.label_edit = QLineEdit(node['label'])
        self.label_edit.textChanged.connect(lambda: self._update_node_label())
        form.addRow("Label:", self.label_edit)

        # Color dropdown (matching popup dialog)
        self.color_combo = QComboBox()
        for color_key, color_value in config.MYCOLORS.items():
            self.color_combo.addItem(f"  {color_key}", color_key)
            idx = self.color_combo.count() - 1
            self.color_combo.setItemData(idx, QColor(color_value), Qt.BackgroundRole)

        # Set to current color
        try:
            color_idx = list(config.MYCOLORS.keys()).index(node['color_key'])
            self.color_combo.setCurrentIndex(color_idx)
        except:
            self.color_combo.setCurrentIndex(0)

        self.color_combo.currentIndexChanged.connect(lambda: self._update_node_color_from_combo())
        form.addRow("Color:", self.color_combo)

        # Node size
        self.node_size_slider = QSlider(Qt.Horizontal)
        self.node_size_slider.setMinimum(config.NODE_SIZE_SLIDER_MIN)
        self.node_size_slider.setMaximum(config.NODE_SIZE_SLIDER_MAX)
        self.node_size_slider.setValue(int(node.get('node_size_mult', 1.0) * 100))
        self.node_size_slider.setToolTip("Up/Down (when node selected)")
        # Update label during drag, but only update plot when released
        self.node_size_slider.valueChanged.connect(lambda: self._update_node_size_label_only())
        self.node_size_slider.sliderReleased.connect(lambda: self._update_node_size())
        self.node_size_label = QLabel(f"{node.get('node_size_mult', 1.0):.3f}x")
        size_layout = QHBoxLayout()
        size_layout.addWidget(self.node_size_slider)
        size_layout.addWidget(self.node_size_label)
        form.addRow("Node Size:", size_layout)

        # Label size
        self.label_size_slider = QSlider(Qt.Horizontal)
        self.label_size_slider.setMinimum(config.NODE_LABEL_SIZE_SLIDER_MIN)
        self.label_size_slider.setMaximum(config.NODE_LABEL_SIZE_SLIDER_MAX)
        self.label_size_slider.setValue(int(node.get('label_size_mult', 1.0) * 100))
        self.label_size_slider.setToolTip("Left/Right (when node selected)")
        # Update label during drag, but only update plot when released
        self.label_size_slider.valueChanged.connect(lambda: self._update_label_size_label_only())
        self.label_size_slider.sliderReleased.connect(lambda: self._update_label_size())
        self.label_size_label = QLabel(f"{node.get('label_size_mult', 1.0):.3f}x")
        label_size_layout = QHBoxLayout()
        label_size_layout.addWidget(self.label_size_slider)
        label_size_layout.addWidget(self.label_size_label)
        form.addRow("Label Size:", label_size_layout)

        # Conjugation
        self.conj_checkbox = QCheckBox()
        self.conj_checkbox.setChecked(node.get('conj', False))
        self.conj_checkbox.stateChanged.connect(lambda: self._update_conjugation())
        form.addRow("Conjugated:", self.conj_checkbox)

        # Outline enabled
        self.outline_checkbox = QCheckBox()
        self.outline_checkbox.setChecked(node.get('outline_enabled', False))
        self.outline_checkbox.stateChanged.connect(lambda: self._update_outline_enabled())
        form.addRow("Outline:", self.outline_checkbox)

        # Outline color
        self.outline_color_combo = QComboBox()
        for color_key, color_value in config.MYCOLORS.items():
            self.outline_color_combo.addItem(f"  {color_key}", color_key)
            idx = self.outline_color_combo.count() - 1
            self.outline_color_combo.setItemData(idx, QColor(color_value), Qt.BackgroundRole)

        # Set to current outline color
        outline_color_key = node.get('outline_color_key', 'BLACK')
        try:
            outline_color_idx = list(config.MYCOLORS.keys()).index(outline_color_key)
            self.outline_color_combo.setCurrentIndex(outline_color_idx)
        except:
            self.outline_color_combo.setCurrentIndex(list(config.MYCOLORS.keys()).index('BLACK'))

        self.outline_color_combo.currentIndexChanged.connect(lambda: self._update_outline_color())
        form.addRow("Outline Color:", self.outline_color_combo)

        # Outline width
        self.outline_width_spin = FineControlSpinBox()
        self.outline_width_spin.setRange(0.5, 10.0)
        self.outline_width_spin.setDecimals(1)
        self.outline_width_spin.setSingleStep(0.5)
        self.outline_width_spin.setValue(node.get('outline_width', config.DEFAULT_NODE_OUTLINE_WIDTH))
        self.outline_width_spin.valueChanged.connect(lambda: self._update_outline_width())
        form.addRow("Outline Width:", self.outline_width_spin)

        # Outline alpha
        self.outline_alpha_spin = FineControlSpinBox()
        self.outline_alpha_spin.setRange(0.0, 1.0)
        self.outline_alpha_spin.setDecimals(2)
        self.outline_alpha_spin.setSingleStep(0.05)
        self.outline_alpha_spin.setValue(node.get('outline_alpha', config.DEFAULT_NODE_OUTLINE_ALPHA))
        self.outline_alpha_spin.valueChanged.connect(lambda: self._update_outline_alpha())
        form.addRow("Outline Alpha:", self.outline_alpha_spin)

        self.properties_layout.addLayout(form)

    def show_edge_properties(self, edge):
        """Show properties for an edge or self-loop"""
        self.clear_properties()
        self.current_object = edge
        self.current_type = 'edge'
        from_label = edge['from_node']['label']
        to_label = edge['to_node']['label']
        is_self_loop = edge.get('is_self_loop', False)

        if is_self_loop:
            self.title_label.setText(f"Self-Loop: {from_label}")
        else:
            self.title_label.setText(f"Edge: {from_label} → {to_label}")

        # Create form layout for properties
        form = QFormLayout()

        # Linewidth
        self.linewidth_combo = QComboBox()
        self.linewidth_combo.addItems(['Thin', 'Medium', 'Thick', 'X-Thick'])
        lw_map = {1.0: 'Thin', 1.5: 'Medium', 2.0: 'Thick', 2.5: 'X-Thick'}
        current_lw = edge.get('linewidth_mult', 1.5)
        closest_lw = min(lw_map.keys(), key=lambda k: abs(k - current_lw))
        self.linewidth_combo.setCurrentText(lw_map[closest_lw])
        self.linewidth_combo.currentTextChanged.connect(lambda: self._update_edge_linewidth())
        if is_self_loop:
            self.linewidth_combo.setToolTip("Up/Down (when self-loop selected)")
        else:
            self.linewidth_combo.setToolTip("Up/Down (when edge selected)")
        form.addRow("Line Width:", self.linewidth_combo)

        # Self-loop specific properties
        if is_self_loop:
            # Angle dropdown
            self.angle_combo = QComboBox()
            angle_options = ['0° (Right)', '45° (Up-Right)', '90° (Up)', '135° (Up-Left)',
                           '180° (Left)', '225° (Down-Left)', '270° (Down)', '315° (Down-Right)']
            self.angle_combo.addItems(angle_options)
            # Set current angle
            selfloopangle = edge.get('selfloopangle', 0)
            for i, option in enumerate(angle_options):
                if int(option.split('°')[0]) == selfloopangle:
                    self.angle_combo.setCurrentIndex(i)
                    break
            self.angle_combo.currentTextChanged.connect(lambda: self._update_edge_angle())
            self.angle_combo.setToolTip("Ctrl+Left/Right (when self-loop selected)")
            form.addRow("Angle:", self.angle_combo)

            # Scale dropdown
            self.scale_combo = QComboBox()
            self.scale_combo.addItems(list(config.SELFLOOP_SCALE_OPTIONS.keys()))
            # Set current scale
            selfloopscale = edge.get('selfloopscale', 1.0)
            scale_map_reverse = {0.7: 0, 1.0: 1, 1.3: 2, 1.6: 3}
            closest_scale = min(scale_map_reverse.keys(), key=lambda x: abs(x - selfloopscale))
            self.scale_combo.setCurrentIndex(scale_map_reverse[closest_scale])
            self.scale_combo.currentTextChanged.connect(lambda: self._update_edge_scale())
            self.scale_combo.setToolTip("Ctrl+Up/Down (when self-loop selected)")
            form.addRow("Loop Size:", self.scale_combo)

            # Flip checkbox
            self.flip_loop_checkbox = QCheckBox()
            self.flip_loop_checkbox.setChecked(edge.get('flip', False))
            self.flip_loop_checkbox.stateChanged.connect(lambda: self._update_edge_flip())
            form.addRow("Flip Direction:", self.flip_loop_checkbox)

        self.properties_layout.addLayout(form)

    def show_no_selection(self):
        """Show message when nothing is selected"""
        self.clear_properties()
        self.current_object = None
        self.current_type = None
        self.title_label.setText("No Selection")

        info = QLabel("Select a node or edge to edit its properties.\n\nShift+click to select multiple objects.")
        info.setWordWrap(True)
        self.properties_layout.addWidget(info)

    # Update methods
    def _update_node_label(self):
        if self.current_object and self.current_type == 'node':
            new_label = self.label_edit.text().strip()
            # Prevent empty labels - use placeholder if empty
            if not new_label:
                new_label = '?'
                self.label_edit.setText(new_label)
            self.current_object['label'] = new_label
            self.graphulator._update_plot()

    def _update_node_color_from_combo(self):
        if self.current_object and self.current_type == 'node':
            color_key = self.color_combo.currentData()
            self.current_object['color'] = config.MYCOLORS[color_key]
            self.current_object['color_key'] = color_key
            self.graphulator._update_plot()

    def _update_node_size_label_only(self):
        """Update only the label text, not the node or plot (for smoother dragging)"""
        if self.current_object and self.current_type == 'node':
            mult = self.node_size_slider.value() / 100.0
            self.node_size_label.setText(f"{mult:.3f}x")

    def _update_node_size(self):
        if self.current_object and self.current_type == 'node':
            mult = self.node_size_slider.value() / 100.0
            self.current_object['node_size_mult'] = mult
            self.node_size_label.setText(f"{mult:.3f}x")
            self.graphulator._update_plot()

    def _update_label_size_label_only(self):
        """Update only the label text, not the node or plot (for smoother dragging)"""
        if self.current_object and self.current_type == 'node':
            mult = self.label_size_slider.value() / 100.0
            self.label_size_label.setText(f"{mult:.3f}x")

    def _update_label_size(self):
        if self.current_object and self.current_type == 'node':
            mult = self.label_size_slider.value() / 100.0
            self.current_object['label_size_mult'] = mult
            self.label_size_label.setText(f"{mult:.3f}x")
            self.graphulator._update_plot()

    def _update_conjugation(self):
        if self.current_object and self.current_type == 'node':
            self.current_object['conj'] = self.conj_checkbox.isChecked()
            # Update edge styles for edges connected to this node
            self.graphulator._update_edge_styles_for_node(self.current_object)
            self.graphulator._update_plot()

    def _update_outline_enabled(self):
        """Update node outline enabled state"""
        if self.current_object and self.current_type == 'node':
            self.current_object['outline_enabled'] = self.outline_checkbox.isChecked()
            self.graphulator._update_plot()

    def _update_outline_color(self):
        """Update node outline color"""
        if self.current_object and self.current_type == 'node':
            outline_color_key = self.outline_color_combo.currentData()
            self.current_object['outline_color'] = config.MYCOLORS[outline_color_key]
            self.current_object['outline_color_key'] = outline_color_key
            self.graphulator._update_plot()

    def _update_outline_width(self):
        """Update node outline width"""
        if self.current_object and self.current_type == 'node':
            self.current_object['outline_width'] = self.outline_width_spin.value()
            self.graphulator._update_plot()

    def _update_outline_alpha(self):
        """Update node outline alpha"""
        if self.current_object and self.current_type == 'node':
            self.current_object['outline_alpha'] = self.outline_alpha_spin.value()
            self.graphulator._update_plot()

    def _choose_edge_label_bgcolor(self):
        """Choose background color for self-loop label"""
        if self.current_object and self.current_type == 'edge' and self.current_object.get('is_self_loop', False):
            current = self.current_object.get('label_bgcolor', 'white')
            color = QColorDialog.getColor(QColor(current), self.graphulator, "Choose Label Background Color")
            if color.isValid():
                self.current_object['label_bgcolor'] = color.name()
                self.graphulator._update_plot()
                self.show_edge_properties(self.current_object)

    def _clear_edge_label_bgcolor(self):
        """Clear background color for self-loop label"""
        if self.current_object and self.current_type == 'edge' and self.current_object.get('is_self_loop', False):
            if 'label_bgcolor' in self.current_object:
                del self.current_object['label_bgcolor']
            self.graphulator._update_plot()
            self.show_edge_properties(self.current_object)

    def _choose_edge_label1_bgcolor(self):
        """Choose background color for edge label1"""
        if self.current_object and self.current_type == 'edge' and not self.current_object.get('is_self_loop', False):
            current = self.current_object.get('label1_bgcolor', 'white')
            color = QColorDialog.getColor(QColor(current), self.graphulator, "Choose Label1 Background Color")
            if color.isValid():
                self.current_object['label1_bgcolor'] = color.name()
                self.graphulator._update_plot()
                self.show_edge_properties(self.current_object)

    def _clear_edge_label1_bgcolor(self):
        """Clear background color for edge label1"""
        if self.current_object and self.current_type == 'edge' and not self.current_object.get('is_self_loop', False):
            if 'label1_bgcolor' in self.current_object:
                del self.current_object['label1_bgcolor']
            self.graphulator._update_plot()
            self.show_edge_properties(self.current_object)

    def _choose_edge_label2_bgcolor(self):
        """Choose background color for edge label2"""
        if self.current_object and self.current_type == 'edge' and not self.current_object.get('is_self_loop', False):
            current = self.current_object.get('label2_bgcolor', 'white')
            color = QColorDialog.getColor(QColor(current), self.graphulator, "Choose Label2 Background Color")
            if color.isValid():
                self.current_object['label2_bgcolor'] = color.name()
                self.graphulator._update_plot()
                self.show_edge_properties(self.current_object)

    def _clear_edge_label2_bgcolor(self):
        """Clear background color for edge label2"""
        if self.current_object and self.current_type == 'edge' and not self.current_object.get('is_self_loop', False):
            if 'label2_bgcolor' in self.current_object:
                del self.current_object['label2_bgcolor']
            self.graphulator._update_plot()
            self.show_edge_properties(self.current_object)

    def _update_edge_labels(self):
        if self.current_object and self.current_type == 'edge':
            self.current_object['label1'] = self.edge_label1_edit.text()
            # Only update label2 if it exists (not present for self-loops)
            if hasattr(self, 'edge_label2_edit'):
                self.current_object['label2'] = self.edge_label2_edit.text()
            self.graphulator._update_plot()

    def _update_edge_linewidth(self):
        if self.current_object and self.current_type == 'edge':
            linewidth_name = self.linewidth_combo.currentText()
            self.current_object['linewidth_mult'] = config.EDGE_LINEWIDTH_OPTIONS[linewidth_name]
            # Update the class variable so next edges use this linewidth
            EdgeInputDialog.last_linewidth = linewidth_name
            # Save for inheritance
            self.graphulator._save_last_edge_props(self.current_object)
            self.graphulator._update_plot()

    def _update_edge_angle(self):
        """Update self-loop angle"""
        if self.current_object and self.current_type == 'edge':
            angle_text = self.angle_combo.currentText()
            selfloopangle = int(angle_text.split('°')[0])
            self.current_object['selfloopangle'] = selfloopangle
            # Save for inheritance
            self.graphulator._save_last_edge_props(self.current_object)
            self.graphulator._update_plot()

    def _update_edge_scale(self):
        """Update self-loop scale"""
        if self.current_object and self.current_type == 'edge':
            scale_text = self.scale_combo.currentText()
            selfloopscale = config.SELFLOOP_SCALE_OPTIONS[scale_text]
            self.current_object['selfloopscale'] = selfloopscale
            # Save for inheritance
            self.graphulator._save_last_edge_props(self.current_object)
            self.graphulator._update_plot()

    def _update_edge_flip(self):
        """Update self-loop flip direction"""
        if self.current_object and self.current_type == 'edge':
            self.current_object['flip'] = self.flip_loop_checkbox.isChecked()
            # Save for inheritance
            self.graphulator._save_last_edge_props(self.current_object)
            self.graphulator._update_plot()

    def _update_edge_style(self):
        if self.current_object and self.current_type == 'edge':
            self.current_object['style'] = self.style_combo.currentText()
            self.graphulator._update_plot()

    def _update_edge_direction(self):
        if self.current_object and self.current_type == 'edge':
            self.current_object['direction'] = self.direction_combo.currentText()
            # Save for inheritance
            self.graphulator._save_last_edge_props(self.current_object)
            self.graphulator._update_plot()

    def _update_edge_looptheta(self):
        if self.current_object and self.current_type == 'edge':
            self.current_object['looptheta'] = self.looptheta_spinbox.value()
            # Save for inheritance
            self.graphulator._save_last_edge_props(self.current_object)
            self.graphulator._update_plot()

    def _update_selfloop_angle(self):
        if self.current_object and self.current_type == 'edge':
            angle_text = self.selfloop_angle_combo.currentText()
            selfloopangle = int(angle_text.split('°')[0])
            self.current_object['selfloopangle'] = selfloopangle
            self.graphulator._update_plot()

    def _update_selfloop_scale(self):
        if self.current_object and self.current_type == 'edge':
            scale_text = self.selfloop_scale_combo.currentText()
            scale_map = {'Small (0.7x)': 0.7, 'Medium (1.0x)': 1.0, 'Large (1.3x)': 1.3, 'X-Large (1.6x)': 1.6}
            self.current_object['selfloopscale'] = scale_map[scale_text]
            self.graphulator._update_plot()

    def _update_selfloop_flip(self):
        if self.current_object and self.current_type == 'edge':
            self.current_object['flip'] = self.selfloop_flip_checkbox.isChecked()
            self.graphulator._update_plot()

    def _scroll_to_node_row(self, node):
        """Scroll to and highlight a node's row in the parameter table"""

        # Check if scattering tab is visible
        if not self.graphulator.scattering_mode:
            return

        # Find the row index for this node
        node_list = self.graphulator.basis_order if self.graphulator.basis_order else self.graphulator.nodes
        try:
            node_index = node_list.index(node)
            row = node_index + 1  # +1 because row 0 is headers
        except (ValueError, AttributeError):
            return

        # Get the widget at this row to scroll to it
        label_widget = self.nodes_param_layout.itemAtPosition(row, 0)
        if label_widget and label_widget.widget():
            # Ensure widget to scroll into view
            self.nodes_scroll.ensureWidgetVisible(label_widget.widget(), 50, 50)

            # Briefly highlight the row by changing background color
            widgets_in_row = []
            for col in range(4):  # 4 columns: label, freq, B_int, B_ext
                item = self.nodes_param_layout.itemAtPosition(row, col)
                if item and item.widget():
                    widgets_in_row.append(item.widget())

            # Apply highlight
            original_styles = []
            for widget in widgets_in_row:
                original_styles.append(widget.styleSheet())
                current_style = widget.styleSheet()
                widget.setStyleSheet(current_style + " background-color: rgba(100, 150, 255, 100);")

            # Remove highlight after 800ms
            def remove_highlight():
                for widget, orig_style in zip(widgets_in_row, original_styles):
                    widget.setStyleSheet(orig_style)

            QTimer.singleShot(800, remove_highlight)

    def _scroll_to_edge_row(self, edge):
        """Scroll to and highlight an edge's row in the parameter table"""

        # Check if scattering tab is visible
        if not self.graphulator.scattering_mode:
            return

        # Get ordered edges to find row index
        tree_edges, chord_edges = self._order_edges_by_spanning_tree()

        # Find which list the edge is in
        row = None
        try:
            if edge in tree_edges:
                edge_index = tree_edges.index(edge)
                row = edge_index + 1  # +1 because row 0 is headers
            elif edge in chord_edges:
                edge_index = chord_edges.index(edge)
                row = len(tree_edges) + edge_index + 1
        except (ValueError, AttributeError):
            return

        if row is None:
            return

        # Get the widget at this row to scroll to it
        label_widget = self.edges_param_layout.itemAtPosition(row, 0)
        if label_widget and label_widget.widget():
            # Ensure widget to scroll into view
            self.edges_scroll.ensureWidgetVisible(label_widget.widget(), 50, 50)

            # Briefly highlight the row by changing background color
            widgets_in_row = []
            for col in range(4):  # 4 columns: label, f_p, rate, phase
                item = self.edges_param_layout.itemAtPosition(row, col)
                if item and item.widget():
                    widgets_in_row.append(item.widget())

            # Apply highlight
            original_styles = []
            for widget in widgets_in_row:
                original_styles.append(widget.styleSheet())
                current_style = widget.styleSheet()
                widget.setStyleSheet(current_style + " background-color: rgba(100, 150, 255, 100);")

            # Remove highlight after 800ms
            def remove_highlight():
                for widget, orig_style in zip(widgets_in_row, original_styles):
                    widget.setStyleSheet(orig_style)

            QTimer.singleShot(800, remove_highlight)

    def _update_scattering_node_table(self):
        """Update the node parameter table in the Scattering tab based on current graph"""

        # Clear existing widgets
        while self.nodes_param_layout.count():
            item = self.nodes_param_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # If not in scattering mode or no nodes, show placeholder
        if not self.graphulator.scattering_mode or not self.graphulator.nodes:
            placeholder = QLabel("Enter Scattering mode to assign parameters")
            placeholder.setStyleSheet("color: gray; font-style: italic;")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.nodes_param_layout.addWidget(placeholder, 0, 0, 1, 4)
            return

        # Get the current component (for multi-component support)
        current_component = self.graphulator._get_current_component()

        # Use basis order if available, otherwise use current node order
        if self.graphulator.basis_order:
            node_list = self.graphulator.basis_order
        else:
            node_list = self.graphulator.nodes

        # Filter to current component if in multi-component mode
        if current_component is not None:
            component_node_ids = current_component['node_ids']
            node_list = [n for n in node_list if n['node_id'] in component_node_ids]

        # Add column headers
        row = 0
        self.nodes_param_layout.addWidget(QLabel(""), row, 0)  # Empty corner

        freq_header = QLabel("freq [au]")
        freq_header.setStyleSheet("font-weight: bold;")
        self.nodes_param_layout.addWidget(freq_header, row, 1, alignment=Qt.AlignmentFlag.AlignCenter)

        bint_header = QLabel("B_int [mau]")
        bint_header.setStyleSheet("font-weight: bold;")
        self.nodes_param_layout.addWidget(bint_header, row, 2, alignment=Qt.AlignmentFlag.AlignCenter)

        bext_header = QLabel("B_ext [mau]")
        bext_header.setStyleSheet("font-weight: bold;")
        self.nodes_param_layout.addWidget(bext_header, row, 3, alignment=Qt.AlignmentFlag.AlignCenter)

        # Add node parameter rows
        for i, node in enumerate(node_list):
            row = i + 1
            node_id = id(node)

            # Node label (bold)
            label_text = node['label']
            if node.get('conj', False):
                label_text += '*'
            node_label = QLabel(label_text)
            node_label.setStyleSheet("font-weight: bold;")
            node_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.nodes_param_layout.addWidget(node_label, row, 0)

            # Check if node has self-loop
            has_selfloop = any(
                edge.get('is_self_loop', False) and edge['from_node'] == node
                for edge in self.graphulator.edges
            )

            # Get existing assignments if any
            assignments = self.graphulator.scattering_assignments.get(node_id, {})

            # Frequency spinbox
            freq_spin = FineControlSpinBox()
            freq_spin.setRange(config.FREQ_SPINBOX_MIN, config.FREQ_SPINBOX_MAX)
            freq_spin.setDecimals(config.FREQ_SPINBOX_DECIMALS)
            freq_spin.setSingleStep(config.FREQ_SPINBOX_STEP)
            freq_spin.setMaximumWidth(config.FREQ_SPINBOX_WIDTH)
            freq_spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # Ensure arrow keys work
            freq_spin.setProperty('node_id', node_id)
            freq_spin.setProperty('param_name', 'freq')
            freq_spin.setProperty('obj_type', 'node')
            freq_spin.setProperty('obj_label', node['label'])
            freq_spin.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            freq_spin.customContextMenuRequested.connect(self._show_constraint_context_menu)

            if 'freq' in assignments:
                freq_spin.setValue(assignments['freq'])
                freq_spin.setProperty('user_assigned', True)
            else:
                freq_spin.setValue(config.DEFAULT_NODE_FREQ)
                freq_spin.setStyleSheet("color: lightgray;")
                freq_spin.setProperty('user_assigned', False)

            freq_spin.setToolTip("arb. units")
            freq_spin.valueChanged.connect(lambda val, nid=node_id, widget=freq_spin: self._on_node_param_changed(nid, 'freq', val, widget))
            # Also connect editingFinished to handle Enter on unchanged values
            freq_spin.editingFinished.connect(lambda nid=node_id, widget=freq_spin: self._on_node_param_changed(nid, 'freq', widget.value(), widget))
            self.nodes_param_layout.addWidget(freq_spin, row, 1)

            # B_int spinbox
            bint_spin = FineControlSpinBox()
            bint_spin.setRange(config.B_INT_SPINBOX_MIN, config.B_INT_SPINBOX_MAX)
            bint_spin.setDecimals(config.B_INT_SPINBOX_DECIMALS)
            bint_spin.setSingleStep(config.B_INT_SPINBOX_STEP)
            bint_spin.setMaximumWidth(config.B_INT_SPINBOX_WIDTH)
            bint_spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # Ensure arrow keys work
            bint_spin.setProperty('node_id', node_id)
            bint_spin.setProperty('param_name', 'B_int')
            bint_spin.setProperty('obj_type', 'node')
            bint_spin.setProperty('obj_label', node['label'])
            bint_spin.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            bint_spin.customContextMenuRequested.connect(self._show_constraint_context_menu)

            if 'B_int' in assignments:
                # Convert from arb. units (stored) to milliarb. units (display)
                bint_spin.setValue(assignments['B_int'] * 1000)
                bint_spin.setProperty('user_assigned', True)
            else:
                bint_spin.setValue(config.DEFAULT_NODE_B_INT)
                bint_spin.setStyleSheet("color: lightgray;")
                bint_spin.setProperty('user_assigned', False)

            bint_spin.setToolTip("milliarb. units")
            bint_spin.valueChanged.connect(lambda val, nid=node_id, widget=bint_spin: self._on_node_param_changed(nid, 'B_int', val, widget))
            # Also connect editingFinished to handle Enter on unchanged values
            bint_spin.editingFinished.connect(lambda nid=node_id, widget=bint_spin: self._on_node_param_changed(nid, 'B_int', widget.value(), widget))
            self.nodes_param_layout.addWidget(bint_spin, row, 2)

            # B_ext spinbox (only if node has self-loop)
            if has_selfloop:
                bext_spin = FineControlSpinBox()
                bext_spin.setRange(config.B_EXT_SPINBOX_MIN, config.B_EXT_SPINBOX_MAX)
                bext_spin.setDecimals(config.B_EXT_SPINBOX_DECIMALS)
                bext_spin.setSingleStep(config.B_EXT_SPINBOX_STEP)
                bext_spin.setMaximumWidth(config.B_EXT_SPINBOX_WIDTH)
                bext_spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # Ensure arrow keys work
                bext_spin.setProperty('node_id', node_id)
                bext_spin.setProperty('param_name', 'B_ext')
                bext_spin.setProperty('obj_type', 'node')
                bext_spin.setProperty('obj_label', node['label'])
                bext_spin.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                bext_spin.customContextMenuRequested.connect(self._show_constraint_context_menu)

                if 'B_ext' in assignments:
                    # Convert from arb. units (stored) to milliarb. units (display)
                    bext_spin.setValue(assignments['B_ext'] * 1000)
                    bext_spin.setProperty('user_assigned', True)
                else:
                    bext_spin.setValue(config.DEFAULT_NODE_B_EXT)
                    bext_spin.setStyleSheet("color: lightgray;")
                    bext_spin.setProperty('user_assigned', False)

                bext_spin.setToolTip("milliarb. units")
                bext_spin.valueChanged.connect(lambda val, nid=node_id, widget=bext_spin: self._on_node_param_changed(nid, 'B_ext', val, widget))
                # Also connect editingFinished to handle Enter on unchanged values
                bext_spin.editingFinished.connect(lambda nid=node_id, widget=bext_spin: self._on_node_param_changed(nid, 'B_ext', widget.value(), widget))
                self.nodes_param_layout.addWidget(bext_spin, row, 3)
            else:
                # Empty cell for nodes without self-loop
                self.nodes_param_layout.addWidget(QLabel("—"), row, 3, alignment=Qt.AlignmentFlag.AlignCenter)

        # Set column stretch factors to prevent label column from expanding
        self.nodes_param_layout.setColumnStretch(0, 0)  # Node labels: no stretch (stay narrow)
        self.nodes_param_layout.setColumnStretch(1, 1)  # freq spinbox: can stretch
        self.nodes_param_layout.setColumnStretch(2, 1)  # B_int spinbox: can stretch
        self.nodes_param_layout.setColumnStretch(3, 1)  # B_ext spinbox: can stretch

        # Add stretch at the bottom
        self.nodes_param_layout.setRowStretch(row + 1, 1)

        # Update Show S button state after table is populated
        self._update_show_s_button_state()

        # Reapply constraint group styling after table rebuild
        self._apply_constraint_styling()

    def _on_node_param_changed(self, node_id, param_name, value, widget):
        """Handle when a node parameter is changed"""
        # Only process if this is a user change (not programmatic initialization)
        if not widget.property('user_assigned'):
            # First time user is changing this value - mark as assigned
            widget.setProperty('user_assigned', True)
            widget.setStyleSheet("")  # Remove gray styling
            print(f"[Scattering] Node parameter NOW ASSIGNED: {param_name}={value}")

        # Initialize node assignments if needed
        if node_id not in self.graphulator.scattering_assignments:
            self.graphulator.scattering_assignments[node_id] = {}

        # Store the value (convert milliarb. to arb. units for B_int and B_ext)
        if param_name in ['B_int', 'B_ext']:
            self.graphulator.scattering_assignments[node_id][param_name] = value / 1000
        else:
            self.graphulator.scattering_assignments[node_id][param_name] = value

        # Synchronize constraint group if this widget is in one
        self._sync_constraint_group(widget, value)

        # Schedule debounced update (allows spinbox hold-to-repeat to work)
        self._schedule_scattering_update(node_id)

    def _schedule_scattering_update(self, node_id=None):
        """Schedule a debounced scattering graph/S-param update.

        This allows the spinbox's internal auto-repeat timer to run by not
        blocking the event loop with heavy calculations on every value change.
        """
        if node_id is not None:
            self._pending_node_opacity_updates.add(node_id)
        # Restart the timer - if user is still changing values, this resets the delay
        # self._scattering_update_timer.start(50)  # 50ms debounce delay
        self._scattering_update_timer.start(25)  # 25ms debounce delay

    def _do_scattering_update(self):
        """Execute the debounced scattering update."""

        # Save focused widget before operations that may steal focus
        # This is critical for PyInstaller builds where focus management can differ
        focused_widget = QApplication.focusWidget()

        # Update opacity for all pending nodes
        for node_id in self._pending_node_opacity_updates:
            self._update_node_opacity(node_id)
        self._pending_node_opacity_updates.clear()

        # Render scattering graph if in scattering mode
        if self.graphulator.scattering_mode:
            self.graphulator._render_scattering_graph()

        # Update Show S button enable/disable state
        self._update_show_s_button_state()

        # Auto-recalculate S-params if visible
        self._auto_recalculate_sparams()

        # Restore focus if it was stolen during updates
        if focused_widget is not None and focused_widget.isVisible():
            focused_widget.setFocus()

    def _update_node_opacity(self, node_id):
        """Update node opacity based on whether all required parameters are assigned.

        Note: This method only updates internal state. The actual rendering is
        triggered by _do_scattering_update() after debouncing.
        """
        # Find the node
        node = None
        for n in self.graphulator.nodes:
            if id(n) == node_id:
                node = n
                break

        if not node:
            return

        # Check if node has self-loop
        has_selfloop = any(
            edge.get('is_self_loop', False) and edge['from_node'] == node
            for edge in self.graphulator.edges
        )

        # Check if all required parameters are assigned
        assignments = self.graphulator.scattering_assignments.get(node_id, {})
        required_params = ['freq', 'B_int']
        if has_selfloop:
            required_params.append('B_ext')

        all_assigned = all(param in assignments for param in required_params)
        # The actual rendering will be done by _do_scattering_update() after debouncing

    def _order_edges_by_spanning_tree(self):
        """Order edges by spanning tree branches, from root to terminating nodes

        Returns:
            tuple: (ordered_tree_edges, chord_edges) where each is a list of edge dictionaries
        """
        if not self.graphulator.scattering_mode or not self.graphulator.nodes:
            return [], []

        # Get the current component (for multi-component support)
        current_component = self.graphulator._get_current_component()

        # Determine which edges to use
        if current_component is not None:
            edges_to_use = current_component['edges']
            nodes_to_use = current_component['nodes']
        else:
            edges_to_use = self.graphulator.edges
            nodes_to_use = self.graphulator.nodes

        # Get spanning tree and chord edge keys
        tree_edge_keys = self.graphulator.scattering_tree_edges
        chord_edge_keys = self.graphulator.scattering_chord_edges

        # Build node lookup
        node_map = {node['node_id']: node for node in self.graphulator.nodes}

        # Build mapping from edge key to edge object, adding node references
        edge_map = {}
        for edge in edges_to_use:
            # Skip self-loops
            if edge.get('is_self_loop', False):
                continue
            edge_key = tuple(sorted([edge['from_node_id'], edge['to_node_id']]))
            # Add from_node and to_node references to the edge
            edge['from_node'] = node_map[edge['from_node_id']]
            edge['to_node'] = node_map[edge['to_node_id']]
            edge_map[edge_key] = edge

        # Order tree edges by DFS from root
        ordered_tree_edges = []

        # Get appropriate root node
        if current_component is not None:
            # Use first node from current component
            root_node = nodes_to_use[0] if nodes_to_use else None
        elif self.graphulator.basis_order:
            root_node = self.graphulator.basis_order[0]
        else:
            root_node = self.graphulator.nodes[0]

        if root_node is None:
            return [], []

        visited = set()

        def dfs_order(node):
            """DFS to order edges from root to leaves"""
            visited.add(id(node))

            # Find all tree edges connected to this node
            for edge_key in tree_edge_keys:
                edge = edge_map.get(edge_key)
                if not edge:
                    continue

                # Determine the other node
                other_node = None
                if edge['from_node'] == node:
                    other_node = edge['to_node']
                elif edge['to_node'] == node:
                    other_node = edge['from_node']
                else:
                    continue

                # If other node not visited, this edge is part of the path
                if id(other_node) not in visited:
                    ordered_tree_edges.append(edge)
                    dfs_order(other_node)

        dfs_order(root_node)

        # Get chord edges
        chord_edges = [edge_map[key] for key in chord_edge_keys if key in edge_map]

        # Debug output
        print(f"_order_edges_by_spanning_tree:")
        print(f"  Tree edge keys from GUI: {sorted(tree_edge_keys)}")
        print(f"  Chord edge keys from GUI: {sorted(chord_edge_keys)}")
        print(f"  Returning {len(ordered_tree_edges)} tree edges, {len(chord_edges)} chord edges")
        for edge in chord_edges:
            print(f"    Chord edge: {edge['from_node_id']}→{edge['to_node_id']}")

        return ordered_tree_edges, chord_edges

    def _update_chord_frequency_displays(self):
        """Update the chord frequency display widgets using GraphExtractor"""
        if not self.graphulator.scattering_mode:
            return

        # Use GraphExtractor to compute chord frequencies
        from graphulator.autograph import GraphExtractor

        try:
            # Create extractor and set up graph data
            extractor = GraphExtractor()

            # Get root node from injection dropdown
            root_node_id = self.graphulator._get_selected_injection_node_id()
            if root_node_id is None:
                root_node_id = self.graphulator._get_default_root_node_id()

            # Build minimal graph data for extractor
            nodes = []
            for node in self.graphulator.nodes:
                node_data = {'node_id': node['node_id'], 'label': node['label'], 'pos': node['pos'], 'conj': node.get('conj', False)}
                # Add scattering parameters if assigned
                node_id_key = id(node)
                if node_id_key in self.graphulator.scattering_assignments:
                    params = self.graphulator.scattering_assignments[node_id_key]
                    node_data['freq'] = params.get('freq', None)
                    node_data['B_int'] = params.get('B_int', None)
                    node_data['B_ext'] = params.get('B_ext', None)
                else:
                    node_data['freq'] = None
                    node_data['B_int'] = None
                    node_data['B_ext'] = None
                nodes.append(node_data)

            edges = []
            for edge in self.graphulator.edges:
                edge_data = {
                    'from_node_id': edge['from_node_id'],
                    'to_node_id': edge['to_node_id'],
                    'is_self_loop': edge['is_self_loop']
                }
                # Add scattering parameters if assigned
                edge_id_key = id(edge)
                if edge_id_key in self.graphulator.scattering_assignments:
                    params = self.graphulator.scattering_assignments[edge_id_key]
                    edge_data['f_p'] = params.get('f_p', None)
                    edge_data['rate'] = params.get('rate', None)
                    edge_data['phase'] = params.get('phase', None)
                else:
                    edge_data['f_p'] = None
                    edge_data['rate'] = None
                    edge_data['phase'] = None
                edges.append(edge_data)

            # Create scattering_assignments dict mapping id() to params
            scattering_assignments = {}
            for node in self.graphulator.nodes:
                node_id_key = id(node)
                if node_id_key in self.graphulator.scattering_assignments:
                    scattering_assignments[id(next(n for n in nodes if n['node_id'] == node['node_id']))] = \
                        self.graphulator.scattering_assignments[node_id_key]

            for edge in self.graphulator.edges:
                edge_id_key = id(edge)
                if edge_id_key in self.graphulator.scattering_assignments:
                    matching_edge = next((e for e in edges if e['from_node_id'] == edge['from_node_id'] and e['to_node_id'] == edge['to_node_id']), None)
                    if matching_edge:
                        scattering_assignments[id(matching_edge)] = self.graphulator.scattering_assignments[edge_id_key]

            # Extract graph data with pre-computed tree/chord
            tree_edges_list = [[from_id, to_id] for from_id, to_id in self.graphulator.scattering_tree_edges]
            chord_edges_list = [[from_id, to_id] for from_id, to_id in self.graphulator.scattering_chord_edges]

            extractor.extract_graph_data(
                nodes=nodes,
                edges=edges,
                scattering_assignments=scattering_assignments,
                frequency_settings={'start': 0.0, 'stop': 10.0, 'points': 100},
                root_node_id=root_node_id,
                precomputed_tree_edges=tree_edges_list,
                precomputed_chord_edges=chord_edges_list
            )

            # Get computed chord frequencies
            chord_frequencies = extractor.get_chord_frequencies()

            print(f"_update_chord_frequency_displays: computed chord frequencies:")
            for key, val in chord_frequencies.items():
                print(f"  {key}: {val}")

            # Update the display labels in the table
            print("\n_update_chord_frequency_displays: Updating GUI table...")
            for i in range(self.edges_param_layout.count()):
                widget = self.edges_param_layout.itemAt(i).widget()
                if widget and widget.property('is_chord_fp_display'):
                    edge_id = widget.property('edge_id')
                    # Find the corresponding edge
                    edge = next((e for e in self.graphulator.edges if id(e) == edge_id), None)
                    if edge:
                        edge_key = (edge['from_node_id'], edge['to_node_id'])
                        edge_key_reversed = (edge_key[1], edge_key[0])
                        # Try both orderings
                        f_p_computed = chord_frequencies.get(edge_key, chord_frequencies.get(edge_key_reversed, None))
                        print(f"  Chord edge {edge['from_node_id']}→{edge['to_node_id']}: looking for key {edge_key} or {edge_key_reversed}, found={f_p_computed}")
                        if f_p_computed is not None:
                            widget.setText(f"{f_p_computed:.3f}")
                            widget.setStyleSheet("color: royalblue; font-weight: bold;")
                            widget.setToolTip(f"Auto-computed from accumulated frequencies")
                        else:
                            widget.setText("—")
                            widget.setStyleSheet("color: gray;")
                            widget.setToolTip("Waiting for tree edge frequencies")

        except Exception as e:
            print(f"Error computing chord frequencies: {e}")
            traceback.print_exc()

    def _update_scattering_edge_table(self):
        """Update the edge parameter table in the Scattering tab based on current graph"""

        # Clear existing widgets
        while self.edges_param_layout.count():
            item = self.edges_param_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # If not in scattering mode or no edges, show placeholder
        if not self.graphulator.scattering_mode or not self.graphulator.edges:
            placeholder = QLabel("Enter Scattering mode to assign parameters")
            placeholder.setStyleSheet("color: gray; font-style: italic;")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.edges_param_layout.addWidget(placeholder, 0, 0, 1, 4)
            return

        # Get ordered tree and chord edges
        tree_edges, chord_edges = self._order_edges_by_spanning_tree()

        # Add column headers
        row = 0
        self.edges_param_layout.addWidget(QLabel(""), row, 0)  # Empty corner

        fp_header = QLabel("f_p [au]")
        fp_header.setStyleSheet("font-weight: bold;")
        self.edges_param_layout.addWidget(fp_header, row, 1, alignment=Qt.AlignmentFlag.AlignCenter)

        rate_header = QLabel("g [mau]")
        rate_header.setStyleSheet("font-weight: bold;")
        self.edges_param_layout.addWidget(rate_header, row, 2, alignment=Qt.AlignmentFlag.AlignCenter)

        phase_header = QLabel("phase [°]")
        phase_header.setStyleSheet("font-weight: bold;")
        self.edges_param_layout.addWidget(phase_header, row, 3, alignment=Qt.AlignmentFlag.AlignCenter)

        # Add tree edge parameter rows
        for i, edge in enumerate(tree_edges):
            row = i + 1
            edge_id = id(edge)

            # Edge label (from -> to)
            from_label = edge['from_node']['label']
            to_label = edge['to_node']['label']
            if edge['from_node'].get('conj', False):
                from_label += '*'
            if edge['to_node'].get('conj', False):
                to_label += '*'
            edge_label = QLabel(f"{from_label}→{to_label}")
            edge_label.setStyleSheet("font-weight: bold;")
            edge_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.edges_param_layout.addWidget(edge_label, row, 0)

            # Get existing assignments if any
            assignments = self.graphulator.scattering_assignments.get(edge_id, {})

            # f_p spinbox (editable for tree edges)
            fp_spin = FineControlSpinBox()
            fp_spin.setRange(config.F_P_SPINBOX_MIN, config.F_P_SPINBOX_MAX)
            fp_spin.setDecimals(config.F_P_SPINBOX_DECIMALS)
            fp_spin.setSingleStep(config.F_P_SPINBOX_STEP)
            fp_spin.setMaximumWidth(config.F_P_SPINBOX_WIDTH)
            fp_spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # Ensure arrow keys work
            fp_spin.setProperty('edge_id', edge_id)
            fp_spin.setProperty('param_name', 'f_p')
            fp_spin.setProperty('obj_type', 'edge')
            fp_spin.setProperty('obj_label', f"{from_label}→{to_label}")
            fp_spin.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            fp_spin.customContextMenuRequested.connect(self._show_constraint_context_menu)

            if 'f_p' in assignments:
                fp_spin.setValue(assignments['f_p'])
                fp_spin.setProperty('user_assigned', True)
            else:
                fp_spin.setValue(config.DEFAULT_EDGE_F_P)
                fp_spin.setStyleSheet("color: lightgray;")
                fp_spin.setProperty('user_assigned', False)

            fp_spin.setToolTip("arb. units")
            fp_spin.valueChanged.connect(lambda val, eid=edge_id, widget=fp_spin: self._on_edge_param_changed(eid, 'f_p', val, widget))
            # Also connect editingFinished to handle Enter on unchanged values
            fp_spin.editingFinished.connect(lambda eid=edge_id, widget=fp_spin: self._on_edge_param_changed(eid, 'f_p', widget.value(), widget))
            self.edges_param_layout.addWidget(fp_spin, row, 1)

            # rate spinbox
            rate_spin = FineControlSpinBox()
            rate_spin.setRange(config.RATE_SPINBOX_MIN, config.RATE_SPINBOX_MAX)
            rate_spin.setDecimals(config.RATE_SPINBOX_DECIMALS)
            rate_spin.setSingleStep(config.RATE_SPINBOX_STEP)
            rate_spin.setMaximumWidth(config.RATE_SPINBOX_WIDTH)
            rate_spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # Ensure arrow keys work
            rate_spin.setProperty('edge_id', edge_id)
            rate_spin.setProperty('param_name', 'rate')
            rate_spin.setProperty('obj_type', 'edge')
            rate_spin.setProperty('obj_label', f"{from_label}→{to_label}")
            rate_spin.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            rate_spin.customContextMenuRequested.connect(self._show_constraint_context_menu)

            if 'rate' in assignments:
                # Convert from arb. units (stored) to milliarb. units (display)
                rate_spin.setValue(assignments['rate'] * 1000)
                rate_spin.setProperty('user_assigned', True)
            else:
                rate_spin.setValue(config.DEFAULT_EDGE_RATE)
                rate_spin.setStyleSheet("color: lightgray;")
                rate_spin.setProperty('user_assigned', False)

            rate_spin.setToolTip("milliarb. units")
            rate_spin.valueChanged.connect(lambda val, eid=edge_id, widget=rate_spin: self._on_edge_param_changed(eid, 'rate', val, widget))
            # Also connect editingFinished to handle Enter on unchanged values
            rate_spin.editingFinished.connect(lambda eid=edge_id, widget=rate_spin: self._on_edge_param_changed(eid, 'rate', widget.value(), widget))
            self.edges_param_layout.addWidget(rate_spin, row, 2)

            # phase spinbox
            phase_spin = FineControlSpinBox()
            phase_spin.setRange(config.PHASE_SPINBOX_MIN, config.PHASE_SPINBOX_MAX)
            phase_spin.setDecimals(config.PHASE_SPINBOX_DECIMALS)
            phase_spin.setSingleStep(config.PHASE_SPINBOX_STEP)
            phase_spin.setMaximumWidth(config.PHASE_SPINBOX_WIDTH)
            phase_spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # Ensure arrow keys work
            phase_spin.setProperty('edge_id', edge_id)
            phase_spin.setProperty('param_name', 'phase')
            phase_spin.setProperty('obj_type', 'edge')
            phase_spin.setProperty('obj_label', f"{from_label}→{to_label}")
            phase_spin.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            phase_spin.customContextMenuRequested.connect(self._show_constraint_context_menu)

            if 'phase' in assignments:
                phase_spin.setValue(assignments['phase'])
                phase_spin.setProperty('user_assigned', True)
            else:
                phase_spin.setValue(config.DEFAULT_EDGE_PHASE)
                phase_spin.setStyleSheet("color: lightgray;")
                phase_spin.setProperty('user_assigned', False)

            phase_spin.valueChanged.connect(lambda val, eid=edge_id, widget=phase_spin: self._on_edge_param_changed(eid, 'phase', val, widget))
            # Also connect editingFinished to handle Enter on unchanged values
            phase_spin.editingFinished.connect(lambda eid=edge_id, widget=phase_spin: self._on_edge_param_changed(eid, 'phase', widget.value(), widget))
            self.edges_param_layout.addWidget(phase_spin, row, 3)

        # Add chord edge rows (with non-editable f_p)
        for i, edge in enumerate(chord_edges):
            row = len(tree_edges) + i + 1
            edge_id = id(edge)

            # Edge label (from -> to) - indicate it's a chord
            from_label = edge['from_node']['label']
            to_label = edge['to_node']['label']
            if edge['from_node'].get('conj', False):
                from_label += '*'
            if edge['to_node'].get('conj', False):
                to_label += '*'
            edge_label = QLabel(f"{from_label}→{to_label} (chord)")
            edge_label.setStyleSheet("font-weight: bold; color: gray;")
            edge_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.edges_param_layout.addWidget(edge_label, row, 0)

            # Get existing assignments if any
            assignments = self.graphulator.scattering_assignments.get(edge_id, {})

            # f_p label (non-editable, computed from tree edge frequencies)
            fp_label = QLabel("—")
            fp_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            fp_label.setStyleSheet("color: royalblue;")
            fp_label.setProperty('edge_id', edge_id)  # Store edge_id for updating
            fp_label.setProperty('is_chord_fp_display', True)  # Mark as chord frequency display
            self.edges_param_layout.addWidget(fp_label, row, 1)

            # rate spinbox (editable)
            rate_spin = FineControlSpinBox()
            rate_spin.setRange(config.RATE_SPINBOX_MIN, config.RATE_SPINBOX_MAX)
            rate_spin.setDecimals(config.RATE_SPINBOX_DECIMALS)
            rate_spin.setSingleStep(config.RATE_SPINBOX_STEP)
            rate_spin.setMaximumWidth(config.RATE_SPINBOX_WIDTH)
            rate_spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # Ensure arrow keys work
            rate_spin.setProperty('edge_id', edge_id)
            rate_spin.setProperty('param_name', 'rate')
            rate_spin.setProperty('obj_type', 'edge')
            rate_spin.setProperty('obj_label', f"{from_label}→{to_label}")
            rate_spin.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            rate_spin.customContextMenuRequested.connect(self._show_constraint_context_menu)

            if 'rate' in assignments:
                # Convert from arb. units (stored) to milliarb. units (display)
                rate_spin.setValue(assignments['rate'] * 1000)
                rate_spin.setProperty('user_assigned', True)
            else:
                rate_spin.setValue(config.DEFAULT_EDGE_RATE)
                rate_spin.setStyleSheet("color: lightgray;")
                rate_spin.setProperty('user_assigned', False)

            rate_spin.setToolTip("milliarb. units")
            rate_spin.valueChanged.connect(lambda val, eid=edge_id, widget=rate_spin: self._on_edge_param_changed(eid, 'rate', val, widget))
            # Also connect editingFinished to handle Enter on unchanged values
            rate_spin.editingFinished.connect(lambda eid=edge_id, widget=rate_spin: self._on_edge_param_changed(eid, 'rate', widget.value(), widget))
            self.edges_param_layout.addWidget(rate_spin, row, 2)

            # phase spinbox (editable)
            phase_spin = FineControlSpinBox()
            phase_spin.setRange(config.PHASE_SPINBOX_MIN, config.PHASE_SPINBOX_MAX)
            phase_spin.setDecimals(config.PHASE_SPINBOX_DECIMALS)
            phase_spin.setSingleStep(config.PHASE_SPINBOX_STEP)
            phase_spin.setMaximumWidth(config.PHASE_SPINBOX_WIDTH)
            phase_spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # Ensure arrow keys work
            phase_spin.setProperty('edge_id', edge_id)
            phase_spin.setProperty('param_name', 'phase')
            phase_spin.setProperty('obj_type', 'edge')
            phase_spin.setProperty('obj_label', f"{from_label}→{to_label}")
            phase_spin.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            phase_spin.customContextMenuRequested.connect(self._show_constraint_context_menu)

            if 'phase' in assignments:
                phase_spin.setValue(assignments['phase'])
                phase_spin.setProperty('user_assigned', True)
            else:
                phase_spin.setValue(config.DEFAULT_EDGE_PHASE)
                phase_spin.setStyleSheet("color: lightgray;")
                phase_spin.setProperty('user_assigned', False)

            phase_spin.valueChanged.connect(lambda val, eid=edge_id, widget=phase_spin: self._on_edge_param_changed(eid, 'phase', val, widget))
            # Also connect editingFinished to handle Enter on unchanged values
            phase_spin.editingFinished.connect(lambda eid=edge_id, widget=phase_spin: self._on_edge_param_changed(eid, 'phase', widget.value(), widget))
            self.edges_param_layout.addWidget(phase_spin, row, 3)

        # Set column stretch factors
        self.edges_param_layout.setColumnStretch(0, 0)  # Labels: no stretch
        self.edges_param_layout.setColumnStretch(1, 1)  # Spinboxes: can stretch
        self.edges_param_layout.setColumnStretch(2, 1)
        self.edges_param_layout.setColumnStretch(3, 1)

        # Update chord frequency displays after table is built
        self._update_chord_frequency_displays()

        # Reapply constraint group styling after table rebuild
        self._apply_constraint_styling()

    def _on_edge_param_changed(self, edge_id, param_name, value, widget):
        """Handle when an edge parameter is changed"""
        # Only process if this is a user change (not programmatic initialization)
        if not widget.property('user_assigned'):
            # First time user is changing this value - mark as assigned
            widget.setProperty('user_assigned', True)
            widget.setStyleSheet("")  # Remove gray styling
            print(f"[Scattering] Edge parameter NOW ASSIGNED: {param_name}={value}")

        # Store the value (convert milliarb. to arb. units for rate)
        if edge_id not in self.graphulator.scattering_assignments:
            self.graphulator.scattering_assignments[edge_id] = {}
        if param_name == 'rate':
            self.graphulator.scattering_assignments[edge_id][param_name] = value / 1000
        else:
            self.graphulator.scattering_assignments[edge_id][param_name] = value

        print(f"[Scattering] Edge {edge_id} parameter '{param_name}' = {value}")

        # Synchronize constraint group if this widget is in one
        self._sync_constraint_group(widget, value)

        # If f_p changed on a tree edge, update chord frequency displays (lightweight, no debounce needed)
        if param_name == 'f_p':
            self._update_chord_frequency_displays()

        # Schedule debounced update (allows spinbox hold-to-repeat to work)
        self._schedule_scattering_update()

    # ========== Constraint Group Methods ==========

    def _get_constraint_key(self, widget):
        """Get a unique key for constraint grouping based on param_name and obj_type.

        Constraints are only allowed within the same parameter type (e.g., all 'freq'
        spinboxes can be grouped together, but not freq with B_int).
        """
        obj_type = widget.property('obj_type')  # 'node' or 'edge'
        param_name = widget.property('param_name')  # 'freq', 'B_int', 'B_ext', 'f_p', 'rate', 'phase'
        return f"{obj_type}_{param_name}"

    def _find_constraint_group(self, widget):
        """Find which constraint group a widget belongs to, if any.

        Returns (group_id, group_data) or (None, None) if not in a group.
        """
        obj_type = widget.property('obj_type')
        obj_label = widget.property('obj_label')
        param_name = widget.property('param_name')

        for group_id, group_data in self.graphulator.scattering_constraint_groups.items():
            if group_data['param_name'] == param_name and group_data['obj_type'] == obj_type:
                if obj_label in group_data['members']:
                    return group_id, group_data
        return None, None

    def _show_constraint_context_menu(self, pos):
        """Show context menu for constraint operations on a spinbox."""

        widget = self.sender()
        if not widget:
            return

        param_name = widget.property('param_name')
        obj_type = widget.property('obj_type')
        obj_label = widget.property('obj_label')
        constraint_key = self._get_constraint_key(widget)

        menu = QMenu(widget)

        # Check if this widget is already in a group
        current_group_id, current_group = self._find_constraint_group(widget)

        if current_group_id:
            # Widget is in a group - check if it's a conjugate pair constraint (fixed)
            is_conjugate_pair = current_group.get('is_conjugate_pair', False)

            if is_conjugate_pair:
                # Conjugate pair constraint - show info but disable removal
                info_action = menu.addAction(f"Conjugate pair constraint (group {current_group_id})")
                info_action.setEnabled(False)
                menu.addSeparator()
                hint_action = menu.addAction("(Toggle conjugation to remove)")
                hint_action.setEnabled(False)
            else:
                # User-created group - allow removal
                remove_action = menu.addAction(f"Remove from constraint group {current_group_id}")
                remove_action.triggered.connect(lambda: self._remove_from_constraint_group(widget))
        else:
            # Widget is not in a group - show create/join options
            create_action = menu.addAction("Start new constraint group")
            create_action.triggered.connect(lambda: self._start_constraint_group(widget))

            # Find existing groups with same param_name and obj_type
            compatible_groups = []
            for group_id, group_data in self.graphulator.scattering_constraint_groups.items():
                if group_data['param_name'] == param_name and group_data['obj_type'] == obj_type:
                    compatible_groups.append((group_id, group_data))

            if compatible_groups:
                menu.addSeparator()
                for group_id, group_data in compatible_groups:
                    members_str = ", ".join(group_data['members'][:3])
                    if len(group_data['members']) > 3:
                        members_str += f"... (+{len(group_data['members']) - 3})"
                    join_action = menu.addAction(f"Join group {group_id}: {members_str}")
                    join_action.triggered.connect(lambda checked, gid=group_id: self._add_to_constraint_group(widget, gid))

        # Always show Clear All Constraints option
        menu.addSeparator()
        clear_action = menu.addAction("Clear all constraints")
        clear_action.triggered.connect(self._clear_all_constraints)

        menu.exec(widget.mapToGlobal(pos))

    def _start_constraint_group(self, widget):
        """Create a new constraint group with this widget as the first member."""
        obj_type = widget.property('obj_type')
        obj_label = widget.property('obj_label')
        param_name = widget.property('param_name')

        group_id = self.graphulator._next_constraint_group_id
        self.graphulator._next_constraint_group_id += 1

        self.graphulator.scattering_constraint_groups[group_id] = {
            'param_name': param_name,
            'obj_type': obj_type,
            'members': [obj_label],
            'value': widget.value(),
            'is_conjugate_pair': False  # User-created, not auto-created conjugate pair
        }

        # Mark as user assigned so styling doesn't get cleared on next edit
        widget.setProperty('user_assigned', True)

        print(f"[Constraints] Created group {group_id} for {obj_type} {param_name} with {obj_label}")
        self._apply_constraint_styling()

    def _add_to_constraint_group(self, widget, group_id):
        """Add this widget to an existing constraint group."""
        obj_label = widget.property('obj_label')

        group_data = self.graphulator.scattering_constraint_groups.get(group_id)
        if not group_data:
            return

        if obj_label not in group_data['members']:
            group_data['members'].append(obj_label)
            # Sync the widget's value to the group's value
            widget.blockSignals(True)
            widget.setValue(group_data['value'])
            widget.blockSignals(False)
            # Mark as user assigned so styling doesn't get cleared on next edit
            widget.setProperty('user_assigned', True)
            # Update the stored assignment
            self._update_assignment_from_widget(widget)

        print(f"[Constraints] Added {obj_label} to group {group_id}")
        self._apply_constraint_styling()

    def _remove_from_constraint_group(self, widget):
        """Remove this widget from its constraint group."""
        obj_label = widget.property('obj_label')
        group_id, group_data = self._find_constraint_group(widget)

        if group_id and group_data:
            group_data['members'].remove(obj_label)
            print(f"[Constraints] Removed {obj_label} from group {group_id}")

            # If group has only one member left, dissolve the group
            if len(group_data['members']) < 2:
                del self.graphulator.scattering_constraint_groups[group_id]
                print(f"[Constraints] Dissolved group {group_id} (fewer than 2 members)")

        self._apply_constraint_styling()

    def _update_assignment_from_widget(self, widget):
        """Update the scattering_assignments from a widget's current value."""
        obj_type = widget.property('obj_type')
        param_name = widget.property('param_name')
        value = widget.value()

        if obj_type == 'node':
            node_id = widget.property('node_id')
            if node_id not in self.graphulator.scattering_assignments:
                self.graphulator.scattering_assignments[node_id] = {}
            # Convert milliarb. to arb. units for B_int and B_ext
            if param_name in ('B_int', 'B_ext'):
                self.graphulator.scattering_assignments[node_id][param_name] = value / 1000
            else:
                self.graphulator.scattering_assignments[node_id][param_name] = value
        else:  # edge
            edge_id = widget.property('edge_id')
            if edge_id not in self.graphulator.scattering_assignments:
                self.graphulator.scattering_assignments[edge_id] = {}
            # Convert milliarb. to arb. units for rate
            if param_name == 'rate':
                self.graphulator.scattering_assignments[edge_id][param_name] = value / 1000
            else:
                self.graphulator.scattering_assignments[edge_id][param_name] = value

    def _sync_constraint_group(self, widget, new_value):
        """Synchronize all widgets in the same constraint group to the new value."""
        group_id, group_data = self._find_constraint_group(widget)
        if not group_id:
            return

        obj_type = group_data['obj_type']
        param_name = group_data['param_name']

        # Update the group's stored value
        group_data['value'] = new_value

        # Find all spinboxes in the appropriate layout
        if obj_type == 'node':
            layout = self.nodes_param_layout
        else:
            layout = self.edges_param_layout

        # Iterate through widgets and update those in the same group
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if not item or not item.widget():
                continue
            w = item.widget()
            if not hasattr(w, 'value'):  # Skip labels
                continue

            w_obj_type = w.property('obj_type')
            w_param_name = w.property('param_name')
            w_obj_label = w.property('obj_label')

            # Check if this widget is in the same group
            if (w_obj_type == obj_type and
                w_param_name == param_name and
                w_obj_label in group_data['members'] and
                w != widget):  # Don't update the source widget

                w.blockSignals(True)
                w.setValue(new_value)
                w.blockSignals(False)
                # Update the stored assignment
                self._update_assignment_from_widget(w)

        print(f"[Constraints] Synced group {group_id} to value {new_value}")

    def _apply_constraint_styling(self):
        """Apply background color styling to all constrained spinboxes."""
        # Clear styling from all spinboxes first
        for layout in [self.nodes_param_layout, self.edges_param_layout]:
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if not item or not item.widget():
                    continue
                w = item.widget()
                if not hasattr(w, 'value'):  # Skip labels
                    continue

                # Reset to default styling (check if user_assigned)
                if w.property('user_assigned'):
                    w.setStyleSheet("")
                else:
                    w.setStyleSheet("color: lightgray;")

        # Apply constraint group colors
        for group_id, group_data in self.graphulator.scattering_constraint_groups.items():
            is_conjugate_pair = group_data.get('is_conjugate_pair', False)

            # Get color for this group (cycle through available colors)
            # For conjugate pairs, use pair_color_index so all 3 params share same color
            if is_conjugate_pair:
                color_idx = (group_data.get('pair_color_index', 1) - 1) % len(config.CONSTRAINT_GROUP_COLORS)
            else:
                color_idx = (group_id - 1) % len(config.CONSTRAINT_GROUP_COLORS)
            r, g, b, a = config.CONSTRAINT_GROUP_COLORS[color_idx]

            obj_type = group_data['obj_type']
            param_name = group_data['param_name']
            members = group_data['members']

            layout = self.nodes_param_layout if obj_type == 'node' else self.edges_param_layout

            for i in range(layout.count()):
                item = layout.itemAt(i)
                if not item or not item.widget():
                    continue
                w = item.widget()
                if not hasattr(w, 'value'):
                    continue

                w_obj_type = w.property('obj_type')
                w_param_name = w.property('param_name')
                w_obj_label = w.property('obj_label')

                if (w_obj_type == obj_type and
                    w_param_name == param_name and
                    w_obj_label in members):
                    # Apply background color (with dashed border for conjugate pair constraints)
                    base_style = "" if w.property('user_assigned') else "color: lightgray;"
                    if is_conjugate_pair:
                        # Dashed border to indicate fixed/auto-created conjugate pair constraint
                        w.setStyleSheet(
                            f"{base_style} "
                            f"background-color: rgba({r}, {g}, {b}, {a}); "
                            f"border: 2px dashed rgba({r}, {g}, {b}, 180);"
                        )
                    else:
                        # Normal user-created constraint
                        w.setStyleSheet(f"{base_style} background-color: rgba({r}, {g}, {b}, {a});")

    def _clear_all_constraints(self):
        """Clear all constraint groups (nuclear option)."""
        self.graphulator.scattering_constraint_groups = {}
        self.graphulator._next_constraint_group_id = 1
        print("[Constraints] Cleared all constraint groups")
        self._apply_constraint_styling()

    def _update_show_s_button_state(self):
        """Update Show S button enabled/disabled state based on parameter validation"""
        if not hasattr(self, 'show_s_button'):
            return

        # Only validate if button is not currently checked (tab not showing)
        if not self.show_s_button.isChecked():
            validation_ok, _ = self.graphulator._validate_scattering_parameters()
            self.show_s_button.setEnabled(validation_ok)

    def _auto_recalculate_sparams(self):
        """Auto-recalculate S-parameters if the tab is currently visible"""
        # Only recalculate if S-params tab exists and is visible
        if hasattr(self.graphulator, 'sparams_tab'):
            # Get current index dynamically
            sparams_tab_index = self.graphulator.graph_subtabs.indexOf(self.graphulator.sparams_tab)
            current_tab = self.graphulator.graph_subtabs.currentIndex()
            tab_visible = self.graphulator.graph_subtabs.isTabVisible(sparams_tab_index)

            if tab_visible and current_tab == sparams_tab_index:
                # Tab is showing - check validation
                validation_ok, error_msg = self.graphulator._validate_scattering_parameters()
                if validation_ok:
                    # Recompute and plot
                    self.graphulator._compute_and_plot_sparams()
                else:
                    # Show error on plot
                    self.graphulator._show_sparams_error(error_msg)

    def _on_show_s_clicked(self, checked):
        """Handle Show S / Hide S button toggle"""
        if checked:
            # Validate parameters before showing
            validation_ok, error_msg = self.graphulator._validate_scattering_parameters()
            if not validation_ok:
                # Validation failed - uncheck button and show error
                self.show_s_button.setChecked(False)
                QMessageBox.warning(self.graphulator, "Incomplete Parameters", error_msg)
                return

            # Show S-params tab and compute
            self.show_s_button.setText("Hide S")
            self.graphulator._show_sparams_tab()
        else:
            # Hide S-params tab
            self.show_s_button.setText("Show S")
            self.graphulator._hide_sparams_tab()

    def _on_export_py_clicked(self):
        """Handle Export to .py button click - export scattering calculation code to file"""

        code = self._generate_scattering_calculation_code()
        if not code:
            QMessageBox.warning(self.graphulator, "Export Failed",
                               "Could not generate scattering calculation code.\nEnsure all parameters are assigned.")
            return

        # Open file dialog to save
        default_filename = "scattering_calculation.py"
        filename, _ = QFileDialog.getSaveFileName(
            self.graphulator,
            "Save Scattering Calculation Code",
            default_filename,
            "Python Files (*.py);;All Files (*)"
        )

        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(code)
                print(f"✓ Exported scattering calculation code to {filename}")
                QMessageBox.information(self.graphulator, "Export Successful",
                                       f"Code exported to:\n{filename}")
            except Exception as e:
                QMessageBox.critical(self.graphulator, "Export Failed",
                                    f"Failed to write file:\n{str(e)}")

    def _on_export_buffer_clicked(self):
        """Handle Export to Paste Buffer button click - copy code to clipboard"""

        code = self._generate_scattering_calculation_code()
        if not code:
            QMessageBox.warning(self.graphulator, "Export Failed",
                               "Could not generate scattering calculation code.\nEnsure all parameters are assigned.")
            return

        # Copy to clipboard
        clipboard = QApplication.clipboard()
        clipboard.setText(code)
        print("✓ Exported scattering calculation code to clipboard")
        QMessageBox.information(self.graphulator, "Export Successful",
                               "Code copied to clipboard!")

    def _generate_scattering_calculation_code(self):
        """Generate Python code for scattering calculation"""
        if not self.graphulator.scattering_mode:
            return None

        # Get frequency settings
        center = self.freq_center_spin.value()
        span = self.freq_span_spin.value()
        points = self.freq_points_spin.value()

        # Get injection node
        injection_node_id = self.graphulator._get_selected_injection_node_id()
        if injection_node_id is None:
            injection_node_id = self.graphulator._get_default_root_node_id()

        # Get pre-computed tree and chord edges
        tree_edges_list = [[from_id, to_id] for from_id, to_id in self.graphulator.scattering_tree_edges]
        chord_edges_list = [[from_id, to_id] for from_id, to_id in self.graphulator.scattering_chord_edges]

        # Check for duplicate node labels
        label_counts = {}
        for node in self.graphulator.nodes:
            label = node['label']
            if label not in label_counts:
                label_counts[label] = []
            label_counts[label].append(node['node_id'])

        duplicate_labels = {label: node_ids for label, node_ids in label_counts.items() if len(node_ids) > 1}

        # Generate duplicate labels warning comment if needed
        if duplicate_labels:
            dup_entries = []
            for label, node_ids in sorted(duplicate_labels.items()):
                dup_entries.append(f"'{label}' (node_ids: {node_ids})")
            duplicate_labels_comment = f"# DUPLICATE LABELS: {', '.join(dup_entries)}\n# "
        else:
            duplicate_labels_comment = "# "

        # Get port node labels (nodes with B_ext > 0), including conjugation indicator
        port_node_labels = []
        for node in self.graphulator.nodes:
            node_id = id(node)
            params = self.graphulator.scattering_assignments.get(node_id, {})
            B_ext = params.get('B_ext', None)
            if B_ext is not None and B_ext > 0:
                label = node['label']
                if node.get('conj', False):
                    label += '*'
                port_node_labels.append(label)
        port_labels_str = ', '.join(port_node_labels)

        # Build constraint group variable mappings
        # Maps (obj_type, obj_label, param_name) -> variable_name
        constraint_var_map = {}
        constraint_var_definitions = []

        # Generate variable names for each constraint group
        param_name_to_var_prefix = {
            'freq': 'omega0',
            'B_int': 'gamma_int',
            'B_ext': 'gamma_ext',
            'f_p': 'omegaP',
            'rate': 'gP',
            'phase': 'phiP',
        }

        for group_id, group_data in self.graphulator.scattering_constraint_groups.items():
            param_name = group_data['param_name']
            obj_type = group_data['obj_type']
            members = group_data['members']
            value = group_data['value']

            # Only generate if group has 2+ members
            if len(members) >= 2:
                var_prefix = param_name_to_var_prefix.get(param_name, param_name)
                var_name = f"{var_prefix}_group{group_id}"

                # Convert value if needed (B_int, B_ext, rate are stored in milliunits in GUI)
                if param_name in ('B_int', 'B_ext', 'rate'):
                    # Value from GUI is in milliunits, but stored value is in arb. units
                    # Actually, constraint groups store the display value, need to convert
                    stored_value = value / 1000 if param_name in ('B_int', 'B_ext', 'rate') else value
                else:
                    stored_value = value

                # Generate variable definition with member list in comment
                members_str = ", ".join(members[:5])
                if len(members) > 5:
                    members_str += f", ... (+{len(members) - 5} more)"
                constraint_var_definitions.append(
                    f"{var_name} = {round(stored_value, 9)}  # Constrained {param_name}: {members_str}"
                )

                # Map each member to this variable
                for member_label in members:
                    constraint_var_map[(obj_type, member_label, param_name)] = var_name

        # Build node and edge data structures
        nodes_code = []
        node_assignments_code = []

        # Create node_id to label mapping for faster lookups
        node_id_to_label_map = {node['node_id']: node['label'] for node in self.graphulator.nodes}

        for idx, node in enumerate(self.graphulator.nodes):
            node_id = id(node)
            params = self.graphulator.scattering_assignments.get(node_id, {})

            freq = params.get('freq', None)
            B_int = params.get('B_int', None)
            B_ext = params.get('B_ext', None)
            conj = node.get('conj', False)

            # Round numeric values to 9 decimal places
            pos_str = f"[{round(node['pos'][0], 9)}, {round(node['pos'][1], 9)}]"

            nodes_code.append(f"    {{'node_id': {node['node_id']}, 'label': '{node['label']}', " +
                            f"'pos': {pos_str}, 'conj': {conj}}}")

            # Build scattering assignment for this node
            # Check if parameters are in constraint groups
            freq_var = constraint_var_map.get(('node', node['label'], 'freq'))
            B_int_var = constraint_var_map.get(('node', node['label'], 'B_int'))
            B_ext_var = constraint_var_map.get(('node', node['label'], 'B_ext'))

            freq_str = freq_var if freq_var else (f"{round(freq, 9)}" if freq is not None else "None")
            B_int_str = B_int_var if B_int_var else (f"{round(B_int, 9)}" if B_int is not None else "None")
            B_ext_str = B_ext_var if B_ext_var else (f"{round(B_ext, 9)}" if B_ext is not None else "None")

            node_assignments_code.append(
                f"    id(nodes[{idx}]): {{'freq': {freq_str}, 'B_int': {B_int_str}, 'B_ext': {B_ext_str}}},  # node {node['label']}"
            )

        edges_code = []
        edge_assignments_code = []

        for idx, edge in enumerate(self.graphulator.edges):
            edge_id = id(edge)
            params = self.graphulator.scattering_assignments.get(edge_id, {})

            f_p = params.get('f_p', None)
            rate = params.get('rate', None)
            phase = params.get('phase', 0.0)
            is_self_loop = edge.get('is_self_loop', False)

            edges_code.append(f"    {{'from_node_id': {edge['from_node_id']}, 'to_node_id': {edge['to_node_id']}, " +
                            f"'is_self_loop': {is_self_loop}}}")

            # Get node labels for comment and constraint lookup
            from_label = node_id_to_label_map[edge['from_node_id']]
            to_label = node_id_to_label_map[edge['to_node_id']]

            # Add asterisks for conjugated nodes (must match how spinbox obj_label is set)
            from_node = next((n for n in self.graphulator.nodes if n['node_id'] == edge['from_node_id']), None)
            to_node = next((n for n in self.graphulator.nodes if n['node_id'] == edge['to_node_id']), None)
            if from_node and from_node.get('conj', False):
                from_label += '*'
            if to_node and to_node.get('conj', False):
                to_label += '*'
            edge_label = f"{from_label}→{to_label}"

            # Build scattering assignment for this edge
            # Check if parameters are in constraint groups
            f_p_var = constraint_var_map.get(('edge', edge_label, 'f_p'))
            rate_var = constraint_var_map.get(('edge', edge_label, 'rate'))
            phase_var = constraint_var_map.get(('edge', edge_label, 'phase'))

            f_p_str = f_p_var if f_p_var else (f"{round(f_p, 9)}" if f_p is not None else "None")
            rate_str = rate_var if rate_var else (f"{round(rate, 9)}" if rate is not None else "None")
            phase_str = phase_var if phase_var else f"{round(phase, 9)}"

            edge_assignments_code.append(
                f"    id(edges[{idx}]): {{'f_p': {f_p_str}, 'rate': {rate_str}, 'phase': {phase_str}}},  # {from_label}→{to_label}"
            )

        # Add source file information if available
        if self.graphulator.current_filepath:
            source_comment = f"\nExported from: {self.graphulator.current_filepath}"
        else:
            source_comment = ""

        # Check for multiple components
        num_components = 1
        components_data = []
        component_port_labels = {}  # comp_idx -> list of port labels
        if hasattr(self.graphulator, 'sparams_data') and self.graphulator.sparams_data:
            components_data = self.graphulator.sparams_data.get('components', [])
            num_components = len(components_data) if components_data else 1
            for comp_data in components_data:
                comp_idx = comp_data.get('component_index', 0)
                port_dict = comp_data.get('port_dict', {})
                sorted_port_ids = sorted(port_dict.keys())
                port_labels = []
                for pid in sorted_port_ids:
                    info = port_dict.get(pid, {})
                    label = info.get('label', str(pid))
                    if info.get('conj', False):
                        label += '*'
                    port_labels.append(label)
                component_port_labels[comp_idx] = port_labels

        # Prepare note for multi-component graphs
        multi_component_warning = ""
        if num_components > 1:
            multi_component_warning = f"\n\nNOTE: Graph contains {num_components} disconnected components. " \
                "Each component has its own GSM with local port indices."

        # Default colors for auto-cycling
        default_colors = [
            'indianred', 'cornflowerblue', 'darkseagreen', 'sandybrown',
            'mediumpurple', 'mediumaquamarine', 'gray'
        ]

        # Get port info for comments (single component case)
        port_info_parts = []
        for idx, label in enumerate(port_node_labels):
            port_info_parts.append(f"{idx}: {label}")
        port_indices_comment = ", ".join(port_info_parts)

        # Collect checked traces grouped by component
        traces_by_component = {}  # comp_idx -> list of (j_idx, k_idx, color, j_label, k_label)
        color_idx = 0

        if hasattr(self.graphulator, 'sparams_checkboxes') and self.graphulator.sparams_checkboxes:
            for key, checkbox in self.graphulator.sparams_checkboxes.items():
                if len(key) == 3:
                    comp_idx, j_idx, k_idx = key
                else:
                    comp_idx = 0
                    j_idx, k_idx = key
                if checkbox.isChecked():
                    color = default_colors[color_idx % len(default_colors)]
                    comp_labels = component_port_labels.get(comp_idx, port_node_labels)
                    if j_idx < len(comp_labels) and k_idx < len(comp_labels):
                        j_label = comp_labels[j_idx]
                        k_label = comp_labels[k_idx]
                    else:
                        j_label = str(j_idx)
                        k_label = str(k_idx)
                    if comp_idx not in traces_by_component:
                        traces_by_component[comp_idx] = []
                    traces_by_component[comp_idx].append((j_idx, k_idx, color, j_label, k_label))
                    color_idx += 1
        else:
            # No checkbox data - add all S-parameters for component 0
            num_ports = len(port_node_labels)
            traces_by_component[0] = []
            for k_idx in range(num_ports):
                for j_idx in range(num_ports):
                    color = default_colors[color_idx % len(default_colors)]
                    j_label = port_node_labels[j_idx]
                    k_label = port_node_labels[k_idx]
                    traces_by_component[0].append((j_idx, k_idx, color, j_label, k_label))
                    color_idx += 1

        # Generate add_trace lines - different format for single vs multi-component
        if num_components == 1:
            # Single component - use gsm directly
            add_trace_calls = []
            for j_idx, k_idx, color, j_label, k_label in traces_by_component.get(0, []):
                add_trace_calls.append(
                    f"gsm.add_trace({j_idx}, {k_idx}, color='{color}', linestyle='-', linewidth=2.0)  # S_{j_label}{k_label}"
                )
            add_trace_lines = "\n".join(add_trace_calls) if add_trace_calls else "# No traces selected - use gsm.add_trace(j, k) to add S-parameters"
        else:
            # Multi-component - use gsm_components[comp_idx]
            add_trace_calls = []
            for comp_idx in sorted(traces_by_component.keys()):
                for j_idx, k_idx, color, j_label, k_label in traces_by_component[comp_idx]:
                    add_trace_calls.append(
                        f"gsm_components[{comp_idx}].add_trace({j_idx}, {k_idx}, color='{color}', linestyle='-', linewidth=2.0)  # C{comp_idx+1}: S_{j_label}{k_label}"
                    )
            add_trace_lines = "\n".join(add_trace_calls) if add_trace_calls else "# No traces selected"

        # Generate constraint variables section
        if constraint_var_definitions:
            constraint_vars_section = "\n# Constrained parameters (shared variables)\n" + "\n".join(constraint_var_definitions) + "\n"
        else:
            constraint_vars_section = ""

        # Build per-component node/edge info for multi-component graphs
        if num_components > 1 and hasattr(self.graphulator, 'scattering_components'):
            # Generate per-component data
            component_node_ids = {}  # comp_idx -> list of node_ids
            for comp in self.graphulator.scattering_components:
                comp_idx = comp['index']
                component_node_ids[comp_idx] = list(comp['node_ids'])

            # Generate component membership code
            component_membership_code = "# Component membership (node_id -> component_index)\n"
            component_membership_code += "component_node_ids = {\n"
            for comp_idx in sorted(component_node_ids.keys()):
                node_ids = component_node_ids[comp_idx]
                component_membership_code += f"    {comp_idx}: {node_ids},\n"
            component_membership_code += "}\n"
        else:
            component_membership_code = ""

        # Generate code - different templates for single vs multi-component
        if num_components == 1:
            # Single component code (original template)
            code = f'''"""
Scattering calculation code exported from Graphulator{source_comment}
"""

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from graphulator.autograph import GraphExtractor, GraphScatteringMatrix

# Set plot style (uncomment/modify to customize appearance)
# sns.set_theme(style='whitegrid', context='talk', font_scale=1.0)
{constraint_vars_section}
# Graph structure
nodes = [
{(',' + chr(10)).join(nodes_code)}
]

edges = [
{(',' + chr(10)).join(edges_code)}
]

# Scattering assignments keyed by object id
scattering_assignments = {{
{(',' + chr(10)).join(node_assignments_code + edge_assignments_code)}
}}

# Frequency settings
frequency_settings = {{
    'start': {round(center - span/2, 9)},
    'stop': {round(center + span/2, 9)},
    'points': {int(points)}
}}

# Root node for spanning tree
root_node_id = {injection_node_id}

# Pre-computed spanning tree decomposition
tree_edges = {tree_edges_list}
chord_edges = {chord_edges_list}

# Extract graph data
extractor = GraphExtractor()
graph_data = extractor.extract_graph_data(
    nodes=nodes,
    edges=edges,
    scattering_assignments=scattering_assignments,
    frequency_settings=frequency_settings,
    root_node_id=root_node_id,
    precomputed_tree_edges=tree_edges,
    precomputed_chord_edges=chord_edges
)

# Generate frequency array
f_center = {round(center, 9)}
f_span = {round(span, 9)}
frequencies = np.linspace(f_center - f_span/2, f_center + f_span/2, {int(points)})

# Compute S-matrix
scattering_matrix = GraphScatteringMatrix(extractor, frequencies)

print(f"Computed S-matrix: {{len(scattering_matrix.port_dict)}} ports, {{len(frequencies)}} frequency points")

# ============================================================================
# Plot S-parameters
# ============================================================================
gsm = scattering_matrix
gsm.clear_traces()
{add_trace_lines}

fig, ax = gsm.plot_SdB()
plt.show()
'''
        else:
            # Multi-component code
            code = f'''"""
Scattering calculation code exported from Graphulator{source_comment}{multi_component_warning}
"""

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from graphulator.autograph import GraphExtractor, GraphScatteringMatrix

# Set plot style (uncomment/modify to customize appearance)
# sns.set_theme(style='whitegrid', context='talk', font_scale=1.0)
{constraint_vars_section}
# Full graph structure
nodes = [
{(',' + chr(10)).join(nodes_code)}
]

edges = [
{(',' + chr(10)).join(edges_code)}
]

# Scattering assignments keyed by object id
scattering_assignments = {{
{(',' + chr(10)).join(node_assignments_code + edge_assignments_code)}
}}

{component_membership_code}
# Frequency settings
f_center = {round(center, 9)}
f_span = {round(span, 9)}
frequencies = np.linspace(f_center - f_span/2, f_center + f_span/2, {int(points)})

# ============================================================================
# Create GSM for each connected component
# ============================================================================
gsm_components = {{}}

for comp_idx, comp_node_ids in component_node_ids.items():
    comp_node_ids_set = set(comp_node_ids)

    # Filter nodes for this component
    comp_nodes = [n for n in nodes if n['node_id'] in comp_node_ids_set]

    # Filter edges for this component (both endpoints in component, or self-loop on component node)
    comp_edges = []
    for e in edges:
        if e.get('is_self_loop', False):
            if e['from_node_id'] in comp_node_ids_set:
                comp_edges.append(e)
        else:
            if e['from_node_id'] in comp_node_ids_set and e['to_node_id'] in comp_node_ids_set:
                comp_edges.append(e)

    # Filter scattering assignments
    comp_assignments = {{}}
    for i, n in enumerate(comp_nodes):
        orig_idx = next(j for j, orig_n in enumerate(nodes) if orig_n['node_id'] == n['node_id'])
        comp_assignments[id(comp_nodes[i])] = scattering_assignments[id(nodes[orig_idx])]
    for i, e in enumerate(comp_edges):
        orig_idx = next(j for j, orig_e in enumerate(edges)
                       if orig_e['from_node_id'] == e['from_node_id'] and orig_e['to_node_id'] == e['to_node_id'])
        comp_assignments[id(comp_edges[i])] = scattering_assignments[id(edges[orig_idx])]

    # Find a root node (first port node, or first node if no ports)
    port_nodes = [n for n in comp_nodes if any(
        e['from_node_id'] == n['node_id'] and e.get('is_self_loop', False) for e in comp_edges
    )]
    root_id = port_nodes[0]['node_id'] if port_nodes else comp_nodes[0]['node_id']

    # Create extractor and GSM for this component
    extractor = GraphExtractor()
    extractor.extract_graph_data(
        nodes=comp_nodes,
        edges=comp_edges,
        scattering_assignments=comp_assignments,
        frequency_settings={{'start': f_center - f_span/2, 'stop': f_center + f_span/2, 'points': {int(points)}}},
        root_node_id=root_id
    )

    gsm = GraphScatteringMatrix(extractor, frequencies)
    gsm_components[comp_idx] = gsm
    print(f"Component {{comp_idx+1}}: {{len(gsm.port_dict)}} ports")

# ============================================================================
# Add traces to each component's GSM
# ============================================================================
for gsm in gsm_components.values():
    gsm.clear_traces()

{add_trace_lines}

# ============================================================================
# Plot all components together
# ============================================================================
fig, ax = plt.subplots(figsize=(10, 6))

for comp_idx, gsm in gsm_components.items():
    if gsm._plot_traces:  # Only plot if component has traces
        gsm.plot_SdB(ax=ax)

ax.set_xlabel('Frequency')
ax.set_ylabel('|S| (dB)')
ax.legend()
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()
'''

        return code


class LabelPatternAnalyzer:
    """Analyzes node labels to detect patterns and compute next labels for smart paste.

    Supports these pattern types:
    - PATTERN_UNDERSCORE: A_1, A_2, Mode_12
    - PATTERN_LETTER_NUMBER: A0, A1, Mode2
    - PATTERN_PURE_NUMBER: 0, 1, 42
    - PATTERN_PURE_LETTER: A, B, AA (uppercase or lowercase)
    """

    PATTERN_LETTER_NUMBER = 'letter_number'
    PATTERN_UNDERSCORE = 'underscore'
    PATTERN_PURE_LETTER = 'pure_letter'
    PATTERN_PURE_NUMBER = 'pure_number'
    PATTERN_UNKNOWN = 'unknown'

    @classmethod
    def classify_label(cls, label):
        """Classify label into pattern type.

        Returns:
            tuple: (pattern_type, prefix, number) where prefix is the letter part
                   and number is the numeric value for sequencing.
        """

        # Pattern: Letter(s) + underscore + number (e.g., 'A_1', 'Mode_12')
        match = re.match(r'^([A-Za-z]+)_(\d+)$', label)
        if match:
            return (cls.PATTERN_UNDERSCORE, match.group(1), int(match.group(2)))

        # Pattern: Letter(s) followed directly by number (e.g., 'A0', 'B1', 'Mode2')
        match = re.match(r'^([A-Za-z]+)(\d+)$', label)
        if match:
            return (cls.PATTERN_LETTER_NUMBER, match.group(1), int(match.group(2)))

        # Pattern: Pure number (e.g., '0', '1', '42')
        match = re.match(r'^(\d+)$', label)
        if match:
            return (cls.PATTERN_PURE_NUMBER, '', int(match.group(1)))

        # Pattern: Pure uppercase letters (e.g., 'A', 'Z', 'AA')
        match = re.match(r'^([A-Z]+)$', label)
        if match:
            return (cls.PATTERN_PURE_LETTER, 'upper', cls._letters_to_number(match.group(1)))

        # Pattern: Pure lowercase letters (e.g., 'a', 'z', 'aa')
        match = re.match(r'^([a-z]+)$', label)
        if match:
            return (cls.PATTERN_PURE_LETTER, 'lower', cls._letters_to_number(match.group(1).upper()))

        return (cls.PATTERN_UNKNOWN, None, None)

    @classmethod
    def _letters_to_number(cls, letters):
        """Convert letters to number: A=1, B=2, ..., Z=26, AA=27."""
        num = 0
        for char in letters:
            num = num * 26 + (ord(char) - ord('A') + 1)
        return num

    @classmethod
    def _number_to_letters(cls, num, lowercase=False):
        """Convert number to letters: 1=A, 2=B, ..., 26=Z, 27=AA."""
        result = ''
        while num > 0:
            num -= 1
            result = chr(ord('A') + (num % 26)) + result
            num //= 26
        return result.lower() if lowercase else result

    @classmethod
    def analyze_graph_labels(cls, labels):
        """Analyze labels to find series and their max values.

        Args:
            labels: List of label strings from existing graph

        Returns:
            dict: Mapping of (pattern_type, prefix) -> {'max': int, 'labels': list}
        """
        from collections import defaultdict
        series = defaultdict(lambda: {'max': -1, 'labels': []})

        for label in labels:
            pattern_type, prefix, number = cls.classify_label(label)
            if pattern_type != cls.PATTERN_UNKNOWN and number is not None:
                key = (pattern_type, prefix or '')
                series[key]['labels'].append(label)
                series[key]['max'] = max(series[key]['max'], number)

        return dict(series)

    @classmethod
    def compute_next_labels(cls, clipboard_labels, existing_labels):
        """Compute new labels for clipboard nodes continuing existing patterns.

        Args:
            clipboard_labels: List of labels from clipboard nodes (in paste order)
            existing_labels: Set of all labels currently in the graph

        Returns:
            dict: Mapping of original_label -> new_label
        """
        analysis = cls.analyze_graph_labels(list(existing_labels))
        label_mapping = {}
        series_next = {}  # Track next number for each series during paste

        for orig_label in clipboard_labels:
            pattern_type, prefix, number = cls.classify_label(orig_label)

            if pattern_type == cls.PATTERN_UNKNOWN:
                # Unknown pattern - keep as-is, add suffix if duplicate
                new_label = orig_label
                suffix = 1
                while new_label in existing_labels or new_label in label_mapping.values():
                    new_label = f"{orig_label}_{suffix}"
                    suffix += 1
                label_mapping[orig_label] = new_label
                continue

            key = (pattern_type, prefix or '')

            # Initialize series_next from existing graph max
            if key not in series_next:
                if key in analysis:
                    series_next[key] = analysis[key]['max'] + 1
                else:
                    # New series - start from 0 for numbers, 1 for letters
                    series_next[key] = 0 if pattern_type != cls.PATTERN_PURE_LETTER else 1

            # Generate new label
            next_num = series_next[key]
            new_label = cls._format_label(pattern_type, prefix, next_num)

            # Ensure uniqueness
            while new_label in existing_labels or new_label in label_mapping.values():
                next_num += 1
                new_label = cls._format_label(pattern_type, prefix, next_num)

            label_mapping[orig_label] = new_label
            series_next[key] = next_num + 1

        return label_mapping

    @classmethod
    def _format_label(cls, pattern_type, prefix, number):
        """Format a label from pattern components."""
        if pattern_type == cls.PATTERN_LETTER_NUMBER:
            return f"{prefix}{number}"
        elif pattern_type == cls.PATTERN_UNDERSCORE:
            # Use braces for multi-digit numbers in underscore format
            return f"{prefix}_{{{number}}}" if number >= 10 else f"{prefix}_{number}"
        elif pattern_type == cls.PATTERN_PURE_NUMBER:
            return str(number)
        elif pattern_type == cls.PATTERN_PURE_LETTER:
            return cls._number_to_letters(number, lowercase=(prefix == 'lower'))
        return f"Node{number}"


class Graphulator(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Paragraphulator")

        # Load user settings from ~/.graphulator/settings.json (if exists)
        load_user_settings()
        # Sync dialog defaults with loaded config values
        sync_dialog_defaults_from_config()

        # Grid parameters
        self.grid_spacing = config.DEFAULT_GRID_SPACING
        self.grid_type = config.DEFAULT_GRID_TYPE
        self.grid_rotation = 0
        self.zoom_level = 1.0
        self.base_xlim = config.DEFAULT_XLIM
        self.base_ylim = config.DEFAULT_YLIM

        # Rendering mode
        self.use_latex = False  # Toggle between MathText and LaTeX rendering
        self.latex_debounce_timer = QTimer()
        self.latex_debounce_timer.setSingleShot(True)
        self.latex_debounce_timer.timeout.connect(self._render_with_latex)
        self.latex_debounce_timeout = 400  # milliseconds
        self.is_fast_rendering = False  # True when using MathText for quick feedback

        # Resize debounce timer to prevent excessive redraws during window resize
        self.resize_debounce_timer = QTimer()
        self.resize_debounce_timer.setSingleShot(True)
        self.resize_debounce_timer.timeout.connect(self._handle_resize_complete)
        self.resize_debounce_timeout = 100  # milliseconds
        self.pending_resize_limits = None  # Store pending axis limits

        # Edge label rotation mode
        self.edge_rotation_mode = False  # True when adjusting edge label rotation

        # Initialize export_rescale with defaults, then merge any saved user settings
        self.export_rescale = EXPORT_RESCALE_DEFAULTS.copy()
        # Update with any saved export rescale settings
        if USER_SETTINGS_FILE.exists():
            try:
                with open(USER_SETTINGS_FILE, 'r') as f:
                    saved = json.load(f)
                for key in self.export_rescale:
                    if key in saved:
                        self.export_rescale[key] = saved[key]
            except Exception:
                pass  # Silently ignore errors

        # Node parameters
        self.nodes = []
        self.node_counter = 0
        self.node_id_counter = 0  # Unique ID for each node, independent of labels
        self.node_radius = config.DEFAULT_NODE_RADIUS
        self.preview_patch = None
        self.preview_text = None
        self.preview_outline = None  # Outline circle for ghost preview

        # Edge parameters
        self.edges = []
        self.edge_mode_first_node = None  # First node selected in edge mode
        self.edge_mode_highlight_patch = None  # Visual highlight for first selected node

        # GraphCircuit for managing graph structure (allow duplicate labels)
        self.graph = gp.GraphCircuit(allow_duplicate_labels=True)

        # Symbolic matrix storage
        self.symbolic_matrix = None  # SymPy matrix
        self.symbolic_matrix_latex = None  # LaTeX string for display

        # Global code properties (for .pgraph format)
        self.global_imports = []  # List of import statements
        self.global_code = {}  # Global code snippets {name: code_string}

        # Placement mode
        self.placement_mode = None  # None, 'single', 'continuous', 'continuous_duplicate', 'conjugation', 'edge', or 'edge_continuous'

        # Last placed node properties for duplication
        self.last_node_props = None

        # Last placed edge properties for duplication (separate for regular edges and self-loops)
        self.last_edge_props = None
        self.last_selfloop_props = None

        # Pan and zoom window state
        self.panning = False
        self.pan_start = None
        self.zoom_window = False
        self.zoom_window_start = None
        self.zoom_window_rect = None

        # Node dragging state
        self.dragging_node = None
        self.dragging_group = False  # True if dragging multiple selected nodes
        self.drag_pending_node = None  # Node clicked but not yet dragging (waiting for motion)
        self.drag_pending_group = False  # Group clicked but not yet dragging
        self.drag_start_pos = None  # Starting position for group drag
        self.drag_threshold = 0.1  # Minimum distance to move before starting drag (data units)
        self.drag_preview_patches = []  # List of preview patches for group drag
        self.drag_preview_texts = []  # List of preview texts for group drag
        self.drag_preview_outlines = []  # List of preview outlines for group drag

        # Double-click tracking
        self.last_click_time = 0
        self.last_click_pos = None
        self.double_click_threshold = 0.3  # seconds

        # Selection state
        self.selected_nodes = []  # List of selected node references
        self.selected_edges = []  # List of selected edge references
        self.selection_window = False
        self.selection_window_start = None
        self.selection_window_rect = None
        self.clipboard = {'nodes': [], 'edges': []}  # Copied nodes and edges

        # Basis ordering mode state
        self.basis_ordering_mode = False  # True when in basis ordering mode
        self.basis_order = []  # List of nodes in the order they were selected for basis
        self.basis_order_undo_stack = []  # Stack for undo/redo in basis ordering mode

        # Kron reduction mode state
        self.kron_mode = False  # True when in Kron reduction mode
        self.kron_selected_nodes = []  # Nodes selected to keep (not eliminate)
        self.kron_reduced_matrix = None  # The Kron-reduced matrix
        self.kron_reduced_matrix_latex = None  # LaTeX string of the committed Kron-reduced matrix
        self.kron_reduced_nodes = []  # Nodes in the reduced graph
        self.kron_reduced_edges = []  # Edges in the reduced graph
        self.kron_affected_nodes = set()  # Nodes that were connected to eliminated nodes
        self.kron_new_edges = set()  # New edges created by reduction (tuples of node ids)
        self.kron_modified_edges = set()  # Modified edges (tuples of node ids)
        self.original_graph = None  # Store original graph before Kron reduction
        self.viewing_original = False  # True when viewing original graph (after reduction committed)

        # Scattering mode state
        self.scattering_mode = False  # True when in scattering mode
        self.scattering_graph = None  # Copy of original graph for scattering
        self.scattering_canvas = None  # Canvas for scattering graph
        self.scattering_tree_edges = set()  # Edge tuples in spanning tree
        self.scattering_chord_edges = set()  # Edge tuples closing loops (chords)
        self.scattering_assignments = {}  # Node/edge numerical value assignments
        self.scattering_base_xlim = None  # View extents for scattering canvas
        self.scattering_base_ylim = None
        self.scattering_selected_node = None  # Currently selected node in scattering view
        self.scattering_selected_edge = None  # Currently selected edge in scattering view
        self.scattering_constraint_groups = {}  # Constraint groups for linked parameters
        self._next_constraint_group_id = 1  # Counter for constraint group IDs
        # Multi-component support for disconnected graphs
        self.scattering_components = []  # List of component dicts from _find_connected_components()
        self.scattering_selected_component = 0  # Index of currently selected component
        self.scattering_per_component_data = {}  # Per-component: {idx: {'tree_edges': set, 'chord_edges': set, 'injection_node_id': int}}

        # Undo system
        self.undo_stack = []  # Stack of previous states
        self.max_undo = 50  # Maximum undo levels

        # Graph circuit
        self.graph = gp.GraphCircuit()

        # File management
        self.current_filepath = None  # Path to currently open file
        self.is_modified = False  # Track unsaved changes
        self.recent_files = []  # List of recent file paths
        self.max_recent_files = 10
        self.recent_files_path = Path.home() / '.graphulator_recent'
        self.last_graph_path = Path.home() / '.graphulator_last.graph'
        self.last_directory_path = Path.home() / '.graphulator_last_dir'
        self.last_directory = None  # Last directory used for open/save

        # Load recent files list and last directory
        self._load_recent_files()
        self._load_last_directory()

        # Initialize shortcut manager
        self.shortcut_manager = ShortcutManager(self)
        # Load saved shortcut bindings from settings
        if USER_SETTINGS_FILE.exists():
            try:
                with open(USER_SETTINGS_FILE, 'r') as f:
                    saved = json.load(f)
                if 'shortcuts' in saved:
                    self.shortcut_manager.import_bindings(saved['shortcuts'])
            except Exception:
                pass  # Silently ignore errors

        # Initialize documentation template processor (for dynamic Help/Tutorial)
        self.doc_processor = CachedDocumentationProcessor(self.shortcut_manager)

        # Create UI
        self._create_ui()
        self._create_menu_bar()
        self._create_shortcuts()
        self._update_plot()

        # Print instructions
        self._print_instructions()

    def _clear_all_previews(self):
        """Clear all preview patches and texts"""
        # Clear drag previews
        for patch in self.drag_preview_patches:
            try:
                patch.remove()
            except:
                pass
        for text in self.drag_preview_texts:
            try:
                text.remove()
            except:
                pass
        for outline in self.drag_preview_outlines:
            try:
                outline.remove()
            except:
                pass
        self.drag_preview_patches.clear()
        self.drag_preview_texts.clear()
        self.drag_preview_outlines.clear()

        # Clear placement preview
        if self.preview_patch:
            try:
                self.preview_patch.remove()
            except:
                pass
            self.preview_patch = None

        if self.preview_text:
            try:
                self.preview_text.remove()
            except:
                pass
            self.preview_text = None

        if self.preview_outline:
            try:
                self.preview_outline.remove()
            except:
                pass
            self.preview_outline = None

    def _create_ui(self):
        """Create the user interface"""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout (horizontal: canvas area | properties panel)
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)

        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # Left panel: Canvas area with status bar
        canvas_widget = QWidget()
        canvas_layout = QVBoxLayout()
        canvas_layout.setContentsMargins(0, 0, 0, 0)  # No margins
        canvas_layout.setSpacing(0)  # No spacing
        canvas_widget.setLayout(canvas_layout)

        # Status bar at top
        self.status_label = QLabel()
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                padding: 5px 10px;
                border-bottom: 1px solid #cccccc;
                font-family: monospace;
                font-size: 11px;
            }
        """)
        self.status_label.setWordWrap(False)
        canvas_layout.addWidget(self.status_label)

        # Create subtabs for Original and Kron graph views
        self.graph_subtabs = QTabWidget()
        canvas_layout.addWidget(self.graph_subtabs, stretch=1)

        # Original graph tab
        original_graph_tab = QWidget()
        original_graph_layout = QVBoxLayout()
        original_graph_layout.setContentsMargins(0, 0, 0, 0)
        original_graph_tab.setLayout(original_graph_layout)

        self.canvas = MplCanvas(self, width=12, height=12, dpi=100)
        original_graph_layout.addWidget(self.canvas, stretch=1)

        # Store reference to original canvas for grid rendering check
        self.original_canvas = self.canvas

        self.graph_subtabs.addTab(original_graph_tab, "Original")

        # Kron-reduced graph tab
        kron_graph_tab = QWidget()
        kron_graph_layout = QVBoxLayout()
        kron_graph_layout.setContentsMargins(0, 0, 0, 0)
        kron_graph_tab.setLayout(kron_graph_layout)

        self.kron_canvas = MplCanvas(self, width=12, height=12, dpi=100)
        kron_graph_layout.addWidget(self.kron_canvas, stretch=1)

        self.graph_subtabs.addTab(kron_graph_tab, "Kron")

        # Initially hide the Kron tab (shown only after Kron reduction is committed)
        self.graph_subtabs.setTabVisible(1, False)

        # S-params tab
        sparams_tab = QWidget()
        sparams_main_layout = QHBoxLayout()
        sparams_main_layout.setContentsMargins(5, 5, 5, 5)
        sparams_tab.setLayout(sparams_main_layout)

        # Left panel: S-parameter selection checkboxes
        sparams_selection_widget = QWidget()
        sparams_selection_layout = QVBoxLayout()
        sparams_selection_widget.setLayout(sparams_selection_layout)
        sparams_selection_widget.setMaximumWidth(120)

        sparams_selection_label = QLabel("S-parameters:")
        sparams_selection_label.setStyleSheet("font-weight: bold;")
        sparams_selection_layout.addWidget(sparams_selection_label)

        # Scrollable area for checkboxes
        self.sparams_checkbox_scroll = QScrollArea()
        self.sparams_checkbox_scroll.setWidgetResizable(True)
        self.sparams_checkbox_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.sparams_checkbox_widget = QWidget()
        self.sparams_checkbox_layout = QVBoxLayout()
        self.sparams_checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.sparams_checkbox_widget.setLayout(self.sparams_checkbox_layout)
        self.sparams_checkbox_scroll.setWidget(self.sparams_checkbox_widget)

        sparams_selection_layout.addWidget(self.sparams_checkbox_scroll)

        # Select All / Unselect All buttons (stacked vertically)
        self.sparams_select_all_btn = QPushButton("Select All")
        self.sparams_select_all_btn.clicked.connect(self._on_sparams_select_all)
        sparams_selection_layout.addWidget(self.sparams_select_all_btn)

        self.sparams_unselect_all_btn = QPushButton("Unselect All")
        self.sparams_unselect_all_btn.clicked.connect(self._on_sparams_unselect_all)
        sparams_selection_layout.addWidget(self.sparams_unselect_all_btn)

        sparams_main_layout.addWidget(sparams_selection_widget)

        # Right panel: Plot and controls
        sparams_plot_widget = QWidget()
        sparams_plot_layout = QVBoxLayout()
        sparams_plot_layout.setContentsMargins(0, 0, 0, 0)
        sparams_plot_widget.setLayout(sparams_plot_layout)

        # Matplotlib canvas for S-parameter plot (4:3 aspect ratio)
        self.sparams_canvas = MplCanvas(self, width=8, height=6, dpi=100, show_axes=True)
        # Set 4:3 aspect ratio for the plot
        self.sparams_canvas.ax.set_aspect('auto')  # Allow auto aspect within 4:3 figure

        # Wrap canvas in aspect ratio widget to maintain 4:3 ratio
        self.sparams_canvas_wrapper = AspectRatioWidget(self.sparams_canvas, aspect_ratio=4/3)
        self.sparams_canvas_wrapper.setMinimumSize(400, 300)  # Minimum 400x300

        # Add matplotlib navigation toolbar (zoom, pan, save, etc.)
        self.sparams_toolbar = NavigationToolbar2QT(self.sparams_canvas, self)
        sparams_plot_layout.addWidget(self.sparams_toolbar)

        # Add canvas wrapper (which maintains aspect ratio)
        sparams_plot_layout.addWidget(self.sparams_canvas_wrapper, stretch=1)

        # Axis controls below plot (organized as vertical columns: X, Y dB, Y Phase)
        axis_controls_group = QGroupBox("Axis Controls")
        axis_controls_layout = QGridLayout()

        # Row 0: Plot mode selector (3-way toggle: dB / Phase / Both)
        plot_mode_label = QLabel("<b>Plot:</b>")
        axis_controls_layout.addWidget(plot_mode_label, 0, 0)

        self.sparams_plot_mode_group = QButtonGroup(self)
        self.sparams_mode_db = QRadioButton("dB")
        self.sparams_mode_phase = QRadioButton("Phase")
        self.sparams_mode_both = QRadioButton("Both")

        # Set default based on config
        default_mode = config.SPARAMS_PLOT_MODE_DEFAULT
        self.sparams_mode_db.setChecked(default_mode == 'dB')
        self.sparams_mode_phase.setChecked(default_mode == 'phase')
        self.sparams_mode_both.setChecked(default_mode == 'both')

        self.sparams_plot_mode_group.addButton(self.sparams_mode_db, 0)
        self.sparams_plot_mode_group.addButton(self.sparams_mode_phase, 1)
        self.sparams_plot_mode_group.addButton(self.sparams_mode_both, 2)

        axis_controls_layout.addWidget(self.sparams_mode_db, 0, 1)
        axis_controls_layout.addWidget(self.sparams_mode_phase, 0, 2)
        axis_controls_layout.addWidget(self.sparams_mode_both, 0, 3)

        self.sparams_plot_mode_group.buttonClicked.connect(self._on_sparams_plot_mode_changed)

        # Row 1: Column headers
        axis_controls_layout.addWidget(QLabel("<b>X Axis</b>"), 1, 0, 1, 2)
        self.sparams_ydb_header = QLabel("<b>Y dB</b>")
        axis_controls_layout.addWidget(self.sparams_ydb_header, 1, 2, 1, 2)
        self.sparams_yphase_header = QLabel("<b>Y Phase</b>")
        axis_controls_layout.addWidget(self.sparams_yphase_header, 1, 4, 1, 2)

        # Row 2: X Autoscale, Y dB Autoscale, Y Phase Autoscale
        self.sparams_x_autoscale = QCheckBox("Autoscale")
        self.sparams_x_autoscale.setChecked(True)
        self.sparams_x_autoscale.stateChanged.connect(self._on_sparams_autoscale_changed)
        axis_controls_layout.addWidget(self.sparams_x_autoscale, 2, 0, 1, 2)

        self.sparams_y_autoscale = QCheckBox("Autoscale")
        self.sparams_y_autoscale.setChecked(True)
        self.sparams_y_autoscale.stateChanged.connect(self._on_sparams_autoscale_changed)
        axis_controls_layout.addWidget(self.sparams_y_autoscale, 2, 2, 1, 2)

        self.sparams_phase_autoscale = QCheckBox("Autoscale")
        self.sparams_phase_autoscale.setChecked(True)
        self.sparams_phase_autoscale.stateChanged.connect(self._on_sparams_autoscale_changed)
        axis_controls_layout.addWidget(self.sparams_phase_autoscale, 2, 4)

        # Unwrap checkbox (for phase) - next to Autoscale
        self.sparams_phase_unwrap = QCheckBox("Unwrap")
        self.sparams_phase_unwrap.setChecked(config.SPARAMS_PHASE_UNWRAP_DEFAULT)
        self.sparams_phase_unwrap.setToolTip("Unwrap phase to remove discontinuities")
        self.sparams_phase_unwrap.stateChanged.connect(self._on_sparams_axis_limit_changed)
        axis_controls_layout.addWidget(self.sparams_phase_unwrap, 2, 5)

        # Row 3: X max, Y dB max, Y Phase max
        axis_controls_layout.addWidget(QLabel("Max:"), 3, 0)
        self.sparams_xmax_spin = FineControlSpinBox()
        self.sparams_xmax_spin.setRange(0, 1000)
        self.sparams_xmax_spin.setValue(100)
        self.sparams_xmax_spin.setSingleStep(10)
        self.sparams_xmax_spin.setEnabled(False)
        self.sparams_xmax_spin.valueChanged.connect(self._on_sparams_axis_limit_changed)
        axis_controls_layout.addWidget(self.sparams_xmax_spin, 3, 1)

        self.sparams_ydb_max_label = QLabel("Max:")
        axis_controls_layout.addWidget(self.sparams_ydb_max_label, 3, 2)
        self.sparams_ymax_spin = FineControlSpinBox()
        self.sparams_ymax_spin.setRange(-100, 100)
        self.sparams_ymax_spin.setValue(10)
        self.sparams_ymax_spin.setSingleStep(5)
        self.sparams_ymax_spin.setEnabled(False)
        self.sparams_ymax_spin.valueChanged.connect(self._on_sparams_axis_limit_changed)
        axis_controls_layout.addWidget(self.sparams_ymax_spin, 3, 3)

        self.sparams_phase_max_label = QLabel("Max:")
        axis_controls_layout.addWidget(self.sparams_phase_max_label, 3, 4)
        self.sparams_phase_max_spin = FineControlSpinBox()
        self.sparams_phase_max_spin.setRange(-360, 720)
        self.sparams_phase_max_spin.setValue(config.SPARAMS_PHASE_YMAX_DEFAULT)
        self.sparams_phase_max_spin.setSingleStep(30)
        self.sparams_phase_max_spin.setEnabled(False)
        self.sparams_phase_max_spin.valueChanged.connect(self._on_sparams_axis_limit_changed)
        axis_controls_layout.addWidget(self.sparams_phase_max_spin, 3, 5)

        # Row 4: X min, Y dB min, Y Phase min
        axis_controls_layout.addWidget(QLabel("Min:"), 4, 0)
        self.sparams_xmin_spin = FineControlSpinBox()
        self.sparams_xmin_spin.setRange(0, 1000)
        self.sparams_xmin_spin.setValue(0)
        self.sparams_xmin_spin.setSingleStep(10)
        self.sparams_xmin_spin.setEnabled(False)
        self.sparams_xmin_spin.valueChanged.connect(self._on_sparams_axis_limit_changed)
        axis_controls_layout.addWidget(self.sparams_xmin_spin, 4, 1)

        self.sparams_ydb_min_label = QLabel("Min:")
        axis_controls_layout.addWidget(self.sparams_ydb_min_label, 4, 2)
        self.sparams_ymin_spin = FineControlSpinBox()
        self.sparams_ymin_spin.setRange(-100, 100)
        self.sparams_ymin_spin.setValue(-50)
        self.sparams_ymin_spin.setSingleStep(5)
        self.sparams_ymin_spin.setEnabled(False)
        self.sparams_ymin_spin.valueChanged.connect(self._on_sparams_axis_limit_changed)
        axis_controls_layout.addWidget(self.sparams_ymin_spin, 4, 3)

        self.sparams_phase_min_label = QLabel("Min:")
        axis_controls_layout.addWidget(self.sparams_phase_min_label, 4, 4)
        self.sparams_phase_min_spin = FineControlSpinBox()
        self.sparams_phase_min_spin.setRange(-720, 360)
        self.sparams_phase_min_spin.setValue(config.SPARAMS_PHASE_YMIN_DEFAULT)
        self.sparams_phase_min_spin.setSingleStep(30)
        self.sparams_phase_min_spin.setEnabled(False)
        self.sparams_phase_min_spin.valueChanged.connect(self._on_sparams_axis_limit_changed)
        axis_controls_layout.addWidget(self.sparams_phase_min_spin, 4, 5)

        # Row 5: Conjugate frequencies toggle (spans all columns)
        self.sparams_conjugate_freqs = QPushButton("Conjugate Freqs")
        self.sparams_conjugate_freqs.setCheckable(True)
        self.sparams_conjugate_freqs.setChecked(False)
        self.sparams_conjugate_freqs.clicked.connect(self._on_sparams_conjugate_toggled)
        axis_controls_layout.addWidget(self.sparams_conjugate_freqs, 5, 0, 1, 6)

        # Initialize visibility of phase controls based on default mode
        self._update_sparams_axis_controls_visibility()

        axis_controls_group.setLayout(axis_controls_layout)
        sparams_plot_layout.addWidget(axis_controls_group)

        sparams_main_layout.addWidget(sparams_plot_widget)

        # Store reference to S-params tab for dynamic indexing
        self.sparams_tab = sparams_tab
        self.graph_subtabs.addTab(self.sparams_tab, "S-params")
        # Initially hide S-params tab
        sparams_tab_index = self.graph_subtabs.indexOf(self.sparams_tab)
        self.graph_subtabs.setTabVisible(sparams_tab_index, False)

        # Connect tab change signal to refresh scattering view when switching to it
        self.graph_subtabs.currentChanged.connect(self._on_graph_tab_changed)

        splitter.addWidget(canvas_widget)

        # Right panel: Properties (20%)
        self.properties_panel = PropertiesPanel(self)
        splitter.addWidget(self.properties_panel)

        # Redirect stdout to console output tab
        sys.stdout = ConsoleRedirector(self.properties_panel.console_output, sys.stdout)

        # Set initial sizes (80:20 ratio = 4:1)
        # splitter.setSizes([960, 240])
        # Set initial sizes (70:30 ratio = 7:3)
        splitter.setSizes([840, 360])

        # Connect signals for original canvas
        self.canvas.click_signal.connect(self._on_click)
        self.canvas.release_signal.connect(self._on_release)
        self.canvas.motion_signal.connect(self._on_motion)
        self.canvas.scroll_signal.connect(self._on_scroll)

        # Connect signals for kron canvas (same handlers, but won't be interactive)
        self.kron_canvas.click_signal.connect(self._on_click)
        self.kron_canvas.release_signal.connect(self._on_release)
        self.kron_canvas.motion_signal.connect(self._on_motion)
        self.kron_canvas.scroll_signal.connect(self._on_scroll)

        # Set window size (wider and taller)
        self.resize(1400, 900)

    def _is_input_widget_focused(self):
        """Check if an input widget (spinbox, line edit, text edit) has focus.

        This is used to prevent global shortcuts from interfering with text input.
        More robust than just checking focusWidget() type, as it also checks
        parent widgets for spinboxes (whose internal QLineEdit gets focus).
        """

        focused = QApplication.focusWidget()
        if focused is None:
            return False

        # Direct check for input widgets
        if isinstance(focused, (QDoubleSpinBox, QSpinBox, QLineEdit, QTextEdit, QPlainTextEdit)):
            return True

        # Check if focused widget is inside a spinbox (the internal line edit)
        parent = focused.parent()
        while parent is not None:
            if isinstance(parent, (QDoubleSpinBox, QSpinBox)):
                return True
            parent = parent.parent()

        return False

    def _get_focused_spinbox(self):
        """Get the currently focused spinbox, if any.

        Handles both direct spinbox focus and internal line edit focus.
        Returns the spinbox widget or None.
        """

        focused = QApplication.focusWidget()
        if focused is None:
            return None

        # Direct spinbox focus
        if isinstance(focused, (QDoubleSpinBox, QSpinBox)):
            return focused

        # Check if it's a line edit inside a spinbox
        if isinstance(focused, QLineEdit):
            parent = focused.parent()
            if isinstance(parent, (QDoubleSpinBox, QSpinBox)):
                return parent

        # Check parent chain
        parent = focused.parent()
        while parent is not None:
            if isinstance(parent, (QDoubleSpinBox, QSpinBox)):
                return parent
            parent = parent.parent()

        return None

    def _shortcut_if_no_input_focus(self, handler):
        """Wrap a shortcut handler to only execute if no input widget has focus.

        This prevents single-key shortcuts from interfering with typing in
        spinboxes, text edits, and other input widgets.
        """
        def wrapper():
            if not self._is_input_widget_focused():
                handler()
        return wrapper

    def _create_shortcuts(self):
        """Create keyboard shortcuts using the ShortcutManager."""
        sm = self.shortcut_manager

        # Set up the input focus wrapper for single-key shortcuts
        sm.set_input_focus_wrapper(self._shortcut_if_no_input_focus)

        # ===== NODE PLACEMENT =====
        sm.bind_shortcut("node.place_single", lambda: self._set_placement_mode('single'), self)
        sm.bind_shortcut("node.place_continuous", self._toggle_continuous_mode, self)
        sm.bind_shortcut("node.place_duplicate", self._toggle_continuous_duplicate_mode, self)
        sm.bind_shortcut("node.exit_placement", self._exit_placement_mode, self)
        sm.bind_shortcut("node.toggle_conjugation", self._toggle_conjugation_mode, self)

        # ===== EDGE OPERATIONS =====
        sm.bind_shortcut("edge.place_single", self._toggle_edge_mode, self)
        sm.bind_shortcut("edge.place_continuous", self._toggle_edge_continuous_mode, self)

        # ===== GRID CONTROLS =====
        sm.bind_shortcut("grid.rotate", self._rotate_grid, self)
        sm.bind_shortcut("grid.toggle_type", self._toggle_grid_type, self)

        # ===== GRAPH ROTATION =====
        sm.bind_shortcut("rotate.ccw", lambda: self._rotate_selected_nodes(15), self)
        sm.bind_shortcut("rotate.cw", lambda: self._rotate_selected_nodes(-15), self)
        sm.bind_shortcut("graph.flip_horizontal", self._flip_selected_nodes_horizontal, self, wrap_for_input=True)
        sm.bind_shortcut("graph.flip_vertical", self._flip_selected_nodes_vertical, self)

        # ===== VIEW CONTROLS =====
        sm.bind_shortcut("view.auto_fit", self._auto_fit_view, self)
        sm.bind_shortcut("view.zoom_in", lambda: self._zoom(config.ZOOM_KEYBOARD_FACTOR), self)
        sm.bind_shortcut("view.zoom_in_equals", lambda: self._zoom(config.ZOOM_KEYBOARD_FACTOR), self)
        sm.bind_shortcut("view.zoom_out", lambda: self._zoom(1/config.ZOOM_KEYBOARD_FACTOR), self)

        # ===== EDIT OPERATIONS =====
        sm.bind_shortcut("edit.undo", self._undo, self)
        sm.bind_shortcut("edit.redo_basis", self._redo_basis_selection, self)
        sm.bind_shortcut("edit.delete", self._delete_selected_nodes, self)
        sm.bind_shortcut("edit.delete_d", self._delete_selected_nodes, self)
        sm.bind_shortcut("edit.clear_all", self._clear_nodes, self)
        sm.bind_shortcut("edit.toggle_latex", self._toggle_latex_mode, self)

        # ===== SELECTION & CLIPBOARD =====
        sm.bind_shortcut("select.all", self._select_all, self)
        sm.bind_shortcut("clipboard.copy", self._copy_nodes, self)
        sm.bind_shortcut("clipboard.cut", self._cut_nodes, self)
        sm.bind_shortcut("clipboard.paste", self._paste_nodes, self)
        sm.bind_shortcut("clipboard.paste_raw", self._paste_nodes_raw, self)
        sm.bind_shortcut("clipboard.copy_matrix_latex", self._copy_matrix_latex, self)
        sm.bind_shortcut("clipboard.export_sympy", lambda: self.properties_panel._export_sympy_code(), self)

        # ===== LABEL ADJUSTMENTS =====
        sm.bind_shortcut("label.nudge_left", lambda: self._nudge_label('left'), self)
        sm.bind_shortcut("label.nudge_right", lambda: self._nudge_label('right'), self)
        sm.bind_shortcut("label.nudge_up", lambda: self._nudge_label('up'), self)
        sm.bind_shortcut("label.nudge_down", lambda: self._nudge_label('down'), self)

        # ===== SELF-LOOP ADJUSTMENTS =====
        sm.bind_shortcut("selfloop.scale_increase", lambda: self._adjust_selfloop_scale('increase'), self)
        sm.bind_shortcut("selfloop.scale_decrease", lambda: self._adjust_selfloop_scale('decrease'), self)
        sm.bind_shortcut("selfloop.angle_decrease", lambda: self._adjust_edge_looptheta_or_selfloop_angle('decrease'), self)
        sm.bind_shortcut("selfloop.angle_increase", lambda: self._adjust_edge_looptheta_or_selfloop_angle('increase'), self)

        # ===== CANVAS NAVIGATION =====
        sm.bind_shortcut("pan.left", lambda: self._pan_arrow('left'), self)
        sm.bind_shortcut("pan.right", lambda: self._pan_arrow('right'), self)
        sm.bind_shortcut("pan.up", lambda: self._arrow_key_action('up'), self)
        sm.bind_shortcut("pan.down", lambda: self._arrow_key_action('down'), self)

        # ===== MATRIX DISPLAY =====
        sm.bind_shortcut("matrix.zoom_in", self._zoom_matrix_display_in, self)
        sm.bind_shortcut("matrix.zoom_in_plus", self._zoom_matrix_display_in, self)
        sm.bind_shortcut("matrix.zoom_out", self._zoom_matrix_display_out, self)
        sm.bind_shortcut("matrix.zoom_reset", self._zoom_matrix_display_reset, self)
        sm.bind_shortcut("matrix.pan_left", lambda: self._pan_matrix_display('left'), self)
        sm.bind_shortcut("matrix.pan_right", lambda: self._pan_matrix_display('right'), self)
        sm.bind_shortcut("matrix.pan_up", lambda: self._pan_matrix_display('up'), self)
        sm.bind_shortcut("matrix.pan_down", lambda: self._pan_matrix_display('down'), self)

        # ===== TABS =====
        sm.bind_shortcut("tab.matrix", self._show_matrix_tab, self)
        sm.bind_shortcut("tab.basis", self._show_basis_tab, self)
        sm.bind_shortcut("tab.code", self._show_code_tab, self)
        sm.bind_shortcut("tab.toggle_sparams", self._toggle_sparams_shortcut, self)

        # Tab switching (Ctrl+1-4) with ApplicationShortcut context
        sm.bind_shortcut("tab.switch_1", lambda: self._switch_to_nth_visible_tab(1), self,
                        context=Qt.ShortcutContext.ApplicationShortcut)
        sm.bind_shortcut("tab.switch_2", lambda: self._switch_to_nth_visible_tab(2), self,
                        context=Qt.ShortcutContext.ApplicationShortcut)
        sm.bind_shortcut("tab.switch_3", lambda: self._switch_to_nth_visible_tab(3), self,
                        context=Qt.ShortcutContext.ApplicationShortcut)
        sm.bind_shortcut("tab.switch_4", lambda: self._switch_to_nth_visible_tab(4), self,
                        context=Qt.ShortcutContext.ApplicationShortcut)

        # ===== SCATTERING & ANALYSIS =====
        sm.bind_shortcut("analysis.kron_mode_keyboard", self._enter_kron_mode, self)

        # Shared commit shortcut: routes to appropriate commit function based on current mode
        def commit_current_mode():
            if self.kron_mode:
                self._commit_kron_reduction()
            elif self.basis_ordering_mode:
                self._commit_basis_ordering()

        sm.bind_shortcut("analysis.commit_mode", commit_current_mode, self)

        # Note: File operations (Ctrl+N/O/S, etc.) and menu-specific shortcuts
        # (Ctrl+B, Ctrl+K, Ctrl+R, F1) are bound via _create_menu_bar() using bind_action()

    def _print_instructions(self):
        """Print usage instructions to console"""
        print("=" * 70)
        print("GRAPHULATOR - Interactive Graph Drawing Tool (Qt Version)")
        print("=" * 70)
        print("Controls:")
        print("  'g'             : Place single node (dialog for label/color)")
        print("  'G' (Shift+g)   : Continuous node placement mode")
        print("  'Ctrl+G'        : Continuous duplicate mode (auto-increment labels)")
        print("  'e'             : Place single edge (exits after one edge)")
        print("  'Ctrl+E'        : Toggle continuous edge mode")
        print("  'c'             : Conjugation mode (click nodes to toggle)")
        print("  'Esc'           : Exit placement mode / Clear selection")
        print("  'r'             : Rotate grid (45° square, 30° triangular)")
        print("  't'             : Toggle grid type (square/triangular)")
        print("  'Ctrl+Shift+C'  : Clear all nodes")
        print("  'a'             : Auto-fit view to nodes")
        print("  '+/-'           : Zoom in/out")
        print("  Mouse wheel     : Zoom in/out")
        print("  Arrow keys      : Pan view (or adjust size when selected)")
        print("")
        print("Node Selection & Editing:")
        print("  Left click      : Select node (drag to move)")
        print("  Right click     : Color menu (nodes) / Edge width menu (edges)")
        print("  Shift+click     : Add/remove node or edge from selection")
        print("  Click+drag      : Draw selection window")
        print("  Double-click    : Edit node or edge properties")
        print("  Up/Down arrows  : Increase/decrease node/edge size (when selected)")
        print("  Left/Right      : Adjust label size (nodes/edges when selected)")
        print("  Shift+Up/Down   : Nudge node label / Adjust edge label offset")
        print("  Shift+Left/Right: Nudge node label horizontally")
        print("  Ctrl+A          : Select all nodes and edges")
        print("  Ctrl+C          : Copy selected nodes and edges")
        print("  Ctrl+X          : Cut selected nodes and edges")
        print("  Ctrl+V          : Paste nodes and edges at view center")
        print("  Ctrl+Z          : Undo last action")
        print("  Ctrl+U          : Rotate selected nodes 15° CCW")
        print("  Ctrl+I          : Rotate selected nodes 15° CW")
        print("  Ctrl+Shift+E    : Export graph as Python code")
        print("  Ctrl+L          : Toggle LaTeX rendering mode")
        print("  'f'             : Flip edge labels (when edge selected)")
        print("  Shift+F         : Toggle edge label rotation mode (when edge selected)")
        print("                    Then use Left/Right arrows to rotate ±5°")
        print("  'd' or Delete   : Delete selected nodes and edges")
        print("")
        print("Navigation:")
        print("  Middle button   : Pan (click and drag)")
        print("  Right button    : Zoom window (click and drag)")
        print("  'Ctrl+Q'        : Quit")
        print("=" * 70)
        print(f"Current: {self.grid_type} grid, rotation={self.grid_rotation}°")
        print()

    def _create_menu_bar(self):
        """Create menu bar with File menu"""
        menubar = self.menuBar()
        sm = self.shortcut_manager

        # File menu
        file_menu = menubar.addMenu("&File")

        # New
        new_action = QAction("&New", self)
        sm.bind_action("file.new", new_action)
        new_action.triggered.connect(self._new_graph)
        file_menu.addAction(new_action)

        # Open
        open_action = QAction("&Open...", self)
        sm.bind_action("file.open", open_action)
        open_action.triggered.connect(self._open_graph)
        file_menu.addAction(open_action)

        # Recent Files submenu
        self.recent_files_menu = file_menu.addMenu("Open &Recent")
        self._update_recent_files_menu()

        # Examples submenu
        self.examples_menu = file_menu.addMenu("&Examples")
        self._populate_examples_menu()

        # Reload Last Graph
        reload_action = QAction("Reload Last Graph", self)
        reload_action.triggered.connect(self._reload_last_graph)
        file_menu.addAction(reload_action)

        file_menu.addSeparator()

        # Save
        save_action = QAction("&Save", self)
        sm.bind_action("file.save", save_action)
        save_action.triggered.connect(self._save_graph)
        file_menu.addAction(save_action)

        # Save As
        save_as_action = QAction("Save &As...", self)
        sm.bind_action("file.save_as", save_as_action)
        save_as_action.triggered.connect(self._save_graph_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        # Export submenu
        export_menu = file_menu.addMenu("&Export")

        export_code_action = QAction("Python Code...", self)
        sm.bind_action("file.export_code", export_code_action)
        export_code_action.triggered.connect(self._export_code)
        export_menu.addAction(export_code_action)

        export_png_action = QAction("PNG Image...", self)
        export_png_action.triggered.connect(self._export_png)
        export_menu.addAction(export_png_action)

        export_svg_action = QAction("SVG Image...", self)
        export_svg_action.triggered.connect(self._export_svg)
        export_menu.addAction(export_svg_action)

        export_pdf_action = QAction("PDF Document...", self)
        export_pdf_action.triggered.connect(self._export_pdf)
        export_menu.addAction(export_pdf_action)

        file_menu.addSeparator()

        # Settings (Preferences on macOS - will be moved to app menu automatically)
        settings_action = QAction("&Settings", self)
        sm.bind_action("file.settings", settings_action)
        settings_action.setMenuRole(QAction.MenuRole.PreferencesRole)  # macOS: move to app menu
        settings_action.triggered.connect(self._open_settings)
        file_menu.addAction(settings_action)

        # Show Settings File Location
        show_settings_file_action = QAction("Show Settings &File Location", self)
        show_settings_file_action.triggered.connect(self._show_settings_file_location)
        file_menu.addAction(show_settings_file_action)

        file_menu.addSeparator()

        # Exit
        exit_action = QAction("E&xit", self)
        sm.bind_action("file.quit", exit_action)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Action menu
        action_menu = menubar.addMenu("&Action")

        # Basis Ordering
        basis_action = QAction("Enter &Basis Ordering Mode", self)
        sm.bind_action("analysis.basis_mode", basis_action)
        basis_action.triggered.connect(self._toggle_basis_ordering_mode)
        action_menu.addAction(basis_action)

        # Commit Basis Order - display shortcut from manager
        commit_shortcut_display = sm.get_key_sequence_display("analysis.commit_mode")
        self.commit_basis_action = QAction(f"&Commit Basis Order\t{commit_shortcut_display}", self)
        self.commit_basis_action.triggered.connect(self._commit_basis_ordering)
        self.commit_basis_action.setEnabled(False)  # Disabled until basis ordering mode is active
        action_menu.addAction(self.commit_basis_action)

        action_menu.addSeparator()

        # Enable Scattering
        scattering_action = QAction("Enable &Scattering", self)
        sm.bind_action("analysis.scattering", scattering_action)
        scattering_action.setCheckable(True)
        scattering_action.triggered.connect(self._toggle_scattering_mode)
        action_menu.addAction(scattering_action)

        # Clear Scattering
        clear_scattering_action = QAction("Clear S&cattering", self)
        clear_scattering_action.triggered.connect(self._clear_scattering_data)
        action_menu.addAction(clear_scattering_action)

        # Clear All Constraints
        clear_constraints_action = QAction("Clear All C&onstraints", self)
        clear_constraints_action.triggered.connect(self.properties_panel._clear_all_constraints)
        action_menu.addAction(clear_constraints_action)

        action_menu.addSeparator()

        # Start Kron Reduction
        kron_action = QAction("Start &Kron Reduction", self)
        sm.bind_action("analysis.kron_mode", kron_action)
        kron_action.triggered.connect(self._enter_kron_mode)
        action_menu.addAction(kron_action)

        # Commit Kron Reduction - display shortcut from manager
        self.commit_kron_action = QAction(f"Commit Kron &Reduction\t{commit_shortcut_display}", self)
        self.commit_kron_action.triggered.connect(self._commit_kron_reduction)
        self.commit_kron_action.setEnabled(False)  # Disabled until at least one node is selected
        action_menu.addAction(self.commit_kron_action)

        # Clear Kron Reduction
        clear_kron_action = QAction("Clear Kron Reduct&ion", self)
        clear_kron_action.triggered.connect(self._clear_kron_reduction)
        action_menu.addAction(clear_kron_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        # Show Help
        help_action = QAction("Show &Help", self)
        sm.bind_action("help.show", help_action)
        help_action.triggered.connect(self.properties_panel._show_help_dialog)
        help_menu.addAction(help_action)

        # Tutorial
        tutorial_action = QAction("&Tutorial", self)
        tutorial_action.triggered.connect(self.properties_panel._show_tutorial_dialog)
        help_menu.addAction(tutorial_action)

    def _update_window_title(self):
        """Update window title with filename and modified status"""
        title = "Paragraphulator"
        if self.current_filepath:
            title += f" - {Path(self.current_filepath).name}"
        if self.is_modified:
            title += " *"
        self.setWindowTitle(title)

    def _set_modified(self, modified=True):
        """Set modified flag and update window title"""
        self.is_modified = modified
        self._update_window_title()

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
            print(f"Error loading recent files: {e}")
            self.recent_files = []

    def _save_recent_files(self):
        """Save recent files list to disk"""
        try:
            with open(self.recent_files_path, 'w') as f:
                for filepath in self.recent_files:
                    f.write(f"{filepath}\n")
        except Exception as e:
            print(f"Error saving recent files: {e}")

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

    def _clear_recent_files(self):
        """Clear the recent files list"""
        self.recent_files = []
        self._save_recent_files()
        self._update_recent_files_menu()

    def _load_last_directory(self):
        """Load the last used directory from disk"""
        try:
            if self.last_directory_path.exists():
                with open(self.last_directory_path, 'r') as f:
                    directory = f.read().strip()
                    if directory and Path(directory).is_dir():
                        self.last_directory = directory
                    else:
                        self.last_directory = None
            else:
                self.last_directory = None
        except Exception as e:
            print(f"Error loading last directory: {e}")
            self.last_directory = None

    def _save_last_directory(self, directory):
        """Save the last used directory to disk"""
        try:
            # Store the directory of the file, not the file itself
            dir_path = Path(directory)
            if dir_path.is_file():
                dir_path = dir_path.parent
            self.last_directory = str(dir_path)
            with open(self.last_directory_path, 'w') as f:
                f.write(self.last_directory)
        except Exception as e:
            print(f"Error saving last directory: {e}")

    def _get_default_directory(self):
        """Get the default directory for file dialogs.

        Returns the last used directory if it exists, otherwise falls back
        to the examples/pgraphs directory, or home directory as last resort.
        """
        # Try last used directory first
        if self.last_directory and Path(self.last_directory).is_dir():
            return self.last_directory

        # Fallback to examples/pgraphs directory from package resources
        try:
            from importlib import resources
            if hasattr(resources, 'files'):  # Python 3.9+
                examples_path = resources.files('graphulator').joinpath('examples/pgraphs')
                # Convert to actual path if possible
                if hasattr(examples_path, '__fspath__'):
                    examples_str = str(examples_path)
                    if Path(examples_str).is_dir():
                        return examples_str
            else:
                import pkg_resources
                examples_path = pkg_resources.resource_filename('graphulator', 'examples/pgraphs')
                if Path(examples_path).is_dir():
                    return examples_path
        except Exception:
            pass

        # Fallback: check project root examples/pgraphs (for development mode)
        try:
            this_file = Path(__file__).resolve()
            project_root = this_file.parent.parent.parent
            dev_examples = project_root / 'examples' / 'pgraphs'
            if dev_examples.is_dir():
                return str(dev_examples)
        except Exception:
            pass

        # Final fallback to home directory
        return str(Path.home())

    def _populate_examples_menu(self):
        """Populate the Examples submenu with example graphs from package resources"""
        self.examples_menu.clear()

        example_files = []

        # Try to find examples in package resources
        try:
            from importlib import resources
            if hasattr(resources, 'files'):  # Python 3.9+
                examples_path = resources.files('graphulator').joinpath('examples/pgraphs')
            else:  # Fallback for older Python
                import pkg_resources
                examples_path = Path(pkg_resources.resource_filename('graphulator', 'examples/pgraphs'))

            # Find all .pgraph files
            if hasattr(examples_path, 'iterdir'):
                try:
                    example_files = sorted([f for f in examples_path.iterdir() if f.name.endswith('.pgraph')])
                except (FileNotFoundError, OSError):
                    example_files = []
            else:
                example_files = sorted([Path(f) for f in examples_path.glob('*.pgraph')])
        except Exception as e:
            print(f"Could not load examples from package: {e}")

        # Fallback: check project root examples/pgraphs (for development mode)
        if not example_files:
            try:
                # Find project root by going up from this file's location
                this_file = Path(__file__).resolve()
                # Go up: graphulator_para.py -> graphulator -> src -> project_root
                project_root = this_file.parent.parent.parent
                dev_examples = project_root / 'examples' / 'pgraphs'
                if dev_examples.is_dir():
                    example_files = sorted([f for f in dev_examples.iterdir() if f.name.endswith('.pgraph')])
            except Exception as e:
                print(f"Could not load examples from project root: {e}")

        if not example_files:
            no_examples = QAction("(No examples available)", self)
            no_examples.setEnabled(False)
            self.examples_menu.addAction(no_examples)
        else:
            for example_file in example_files:
                action = QAction(example_file.stem, self)
                action.setToolTip(f"Load example: {example_file.name}")
                action.triggered.connect(lambda checked, f=example_file: self._load_example(f))
                self.examples_menu.addAction(action)

    def _load_example(self, example_path):
        """Load an example graph file"""
        try:
            # Read the example file content
            if hasattr(example_path, 'read_text'):
                # Using importlib.resources path
                content = example_path.read_text()
            else:
                # Using regular file path
                with open(example_path, 'r') as f:
                    content = f.read()

            # Parse and load the example
            import json
            data = json.loads(content)
            self._deserialize_graph(data)

            # Mark as not saved (it's from examples, not a file)
            self.current_filepath = None
            self._set_modified(False)
            self.setWindowTitle(f"Paragraphulator - {example_path.stem} (example)")
            print(f"Loaded example: {example_path.stem}")
        except Exception as e:
            print(f"Error loading example: {e}")
            QMessageBox.warning(self, "Load Error", f"Could not load example:\n{e}")

    def _serialize_graph(self):
        """Serialize graph to dictionary for saving as .pgraph format"""
        data = {
            "version": "2.0",  # New version for .pgraph format
            "format": "pgraph",
            "metadata": {
                "created": datetime.now().isoformat(),
                "modified": datetime.now().isoformat()
            },
            "view": {
                "grid_type": self.grid_type,
                "grid_rotation": self.grid_rotation,
                "zoom_level": self.zoom_level,
                "xlim": list(self.canvas.ax.get_xlim()),
                "ylim": list(self.canvas.ax.get_ylim()),
                "use_latex": self.use_latex
            },
            "nodes": [],
            "edges": [],
            # Extensible sections for future numeric and code properties
            "node_properties": {},  # Maps node_id -> {property_name: numeric_value}
            "edge_properties": {},  # Maps (from_id, to_id) -> {property_name: numeric_value}
            "code_properties": {    # Executable Python/SymPy/NumPy code strings
                "imports": [],      # List of import statements
                "node_code": {},    # Maps node_id -> {code_name: code_string}
                "edge_code": {},    # Maps (from_id, to_id) -> {code_name: code_string}
                "global_code": {}   # Global code snippets {name: code_string}
            }
        }

        # Serialize nodes
        for node in self.nodes:
            node_data = {
                "node_id": node["node_id"],
                "label": node["label"],
                "pos": list(node["pos"]),
                "color": node["color"],
                "color_key": node["color_key"],
                "node_size_mult": node.get("node_size_mult", 1.0),
                "label_size_mult": node.get("label_size_mult", 1.0),
                "conj": node.get("conj", False),
                "nodelabelnudge": list(node.get("nodelabelnudge", (0.0, 0.0))),
                "outline_enabled": node.get("outline_enabled", config.DEFAULT_NODE_OUTLINE_ENABLED),
                "outline_color_key": node.get("outline_color_key", "BLACK"),
                "outline_color": node.get("outline_color", config.DEFAULT_NODE_OUTLINE_COLOR),
                "outline_width": node.get("outline_width", config.DEFAULT_NODE_OUTLINE_WIDTH),
                "outline_alpha": node.get("outline_alpha", config.DEFAULT_NODE_OUTLINE_ALPHA)
            }

            # Check if node has a self-loop
            has_self_loop = any(
                edge['is_self_loop'] and edge['from_node_id'] == node['node_id']
                for edge in self.edges
            )

            # Add scattering parameters if they exist (convert from id() to node_id)
            node_id_key = id(node)
            if node_id_key in self.scattering_assignments:
                scattering_params = self.scattering_assignments[node_id_key]
                if 'freq' in scattering_params:
                    node_data['freq'] = scattering_params['freq']
                if 'B_int' in scattering_params:
                    node_data['B_int'] = scattering_params['B_int']
                if 'B_ext' in scattering_params:
                    # Only save B_ext if node has a self-loop; otherwise set to None
                    if has_self_loop:
                        node_data['B_ext'] = scattering_params['B_ext']
                    else:
                        node_data['B_ext'] = None

            data["nodes"].append(node_data)

            # Initialize empty numeric properties for this node (for future use)
            data["node_properties"][str(node["node_id"])] = node.get("numeric_properties", {})

            # Initialize empty code properties for this node (for future use)
            node_id_str = str(node["node_id"])
            data["code_properties"]["node_code"][node_id_str] = node.get("code_properties", {})

        # Serialize edges
        for edge in self.edges:
            # Create human-readable from_to string for better readability
            from_label = edge["from_node"]["label"]
            to_label = edge["to_node"]["label"]
            if edge["is_self_loop"]:
                from_to_str = f"{from_label} (self-loop)"
            else:
                from_to_str = f"{from_label} <-> {to_label}"

            edge_data = {
                "from_node_id": edge["from_node_id"],
                "to_node_id": edge["to_node_id"],
                "from_to": from_to_str,
                "label1": edge.get("label1", ""),
                "label2": edge.get("label2", ""),
                "linewidth_mult": edge["linewidth_mult"],
                "label_size_mult": edge["label_size_mult"],
                "label_offset_mult": edge.get("label_offset_mult", 1.0),
                "style": edge["style"],
                "direction": edge["direction"],
                "is_self_loop": edge["is_self_loop"],
                "flip_labels": edge.get("flip_labels", False),
                "label_rotation_offset": edge.get("label_rotation_offset", 0)
            }
            # Add self-loop specific parameters
            if edge["is_self_loop"]:
                edge_data["selfloopangle"] = edge.get("selfloopangle", 0)
                edge_data["selfloopscale"] = edge.get("selfloopscale", 1.0)
                edge_data["arrowlengthsc"] = edge.get("arrowlengthsc", 1.0)
                edge_data["flip"] = edge.get("flip", False)
                edge_data["selflooplabelnudge"] = list(edge.get("selflooplabelnudge", (0.0, 0.0)))
                edge_data["label_bgcolor"] = edge.get("label_bgcolor", None)
            else:
                # Regular edge label background colors
                edge_data["label1_bgcolor"] = edge.get("label1_bgcolor", None)
                edge_data["label2_bgcolor"] = edge.get("label2_bgcolor", None)

            # Add scattering parameters if they exist (convert from id() to edge tuple)
            edge_id_key = id(edge)
            if edge_id_key in self.scattering_assignments:
                scattering_params = self.scattering_assignments[edge_id_key]
                if 'f_p' in scattering_params:
                    edge_data['f_p'] = scattering_params['f_p']
                if 'rate' in scattering_params:
                    edge_data['rate'] = scattering_params['rate']
                if 'phase' in scattering_params:
                    edge_data['phase'] = scattering_params['phase']

            data["edges"].append(edge_data)

            # Initialize empty numeric properties for this edge (for future use)
            edge_key = f"{edge['from_node_id']}_{edge['to_node_id']}"
            data["edge_properties"][edge_key] = edge.get("numeric_properties", {})

            # Initialize empty code properties for this edge (for future use)
            data["code_properties"]["edge_code"][edge_key] = edge.get("code_properties", {})

        # Save Kron reduction data if it exists
        if hasattr(self, 'original_graph') and self.original_graph is not None:
            data["kron_reduction"] = {
                "original_graph": self.original_graph,
                "kron_graph": self.kron_graph if hasattr(self, 'kron_graph') and self.kron_graph else None,
                "kron_selected_node_ids": [node['node_id'] for node in self.kron_selected_nodes] if hasattr(self, 'kron_selected_nodes') else [],
                "kron_affected_node_ids": list(node['node_id'] for node in self.kron_affected_nodes) if hasattr(self, 'kron_affected_nodes') else [],
                "kron_new_edges": list(self.kron_new_edges) if hasattr(self, 'kron_new_edges') else [],
                "kron_modified_edges": list(self.kron_modified_edges) if hasattr(self, 'kron_modified_edges') else [],
                "kron_original_base_xlim": list(self.kron_original_base_xlim) if hasattr(self, 'kron_original_base_xlim') else None,
                "kron_original_base_ylim": list(self.kron_original_base_ylim) if hasattr(self, 'kron_original_base_ylim') else None,
            }

            # Serialize the SymPy matrix if it exists (convert to string representation)
            if hasattr(self, 'kron_reduced_matrix') and self.kron_reduced_matrix is not None:
                try:
                    from sympy import srepr
                    data["kron_reduction"]["kron_reduced_matrix_repr"] = srepr(self.kron_reduced_matrix)
                except Exception as e:
                    logger.warning("Could not serialize Kron reduced matrix: %s", e)
                    data["kron_reduction"]["kron_reduced_matrix_repr"] = None

            # Save the LaTeX representation
            if hasattr(self, 'kron_reduced_matrix_latex') and self.kron_reduced_matrix_latex is not None:
                data["kron_reduction"]["kron_reduced_matrix_latex"] = self.kron_reduced_matrix_latex

        # Save scattering data if scattering mode has been used
        if hasattr(self, 'scattering_tree_edges') and self.scattering_tree_edges:
            # Convert edge key sets to lists of tuples for JSON serialization
            tree_edges_list = [list(edge_key) for edge_key in self.scattering_tree_edges]
            chord_edges_list = [list(edge_key) for edge_key in self.scattering_chord_edges]

            # Get injection node ID from combo box
            injection_node_id = None
            if hasattr(self, 'properties_panel') and hasattr(self.properties_panel, 'injection_node_combo'):
                combo = self.properties_panel.injection_node_combo
                if combo.currentIndex() >= 0:
                    injection_node_id = combo.currentData()

            data["scattering"] = {
                "tree_edges": tree_edges_list,
                "chord_edges": chord_edges_list,
                "injection_node_id": injection_node_id,
                "frequency": {
                    "center": self.properties_panel.freq_center_spin.value(),
                    "span": self.properties_panel.freq_span_spin.value(),
                    "points": int(self.properties_panel.freq_points_spin.value())
                }
            }

            # Save S-parameter plot settings if they exist
            if hasattr(self, 'sparams_canvas') and self.sparams_canvas is not None:
                plot_mode = self._get_sparams_plot_mode()

                sparams_plot_settings = {
                    "xlim": list(self.sparams_canvas.ax.get_xlim()),
                    "ylim": list(self.sparams_canvas.ax.get_ylim()) if plot_mode in ('dB', 'both') else None,
                    "x_autoscale": self.sparams_x_autoscale.isChecked(),
                    "y_autoscale": self.sparams_y_autoscale.isChecked(),
                    "conjugate_freqs": self.sparams_conjugate_freqs.isChecked(),
                    # New phase-related settings
                    "plot_mode": plot_mode,
                    "phase_autoscale": self.sparams_phase_autoscale.isChecked(),
                    "phase_ylim": [self.sparams_phase_min_spin.value(), self.sparams_phase_max_spin.value()],
                    "phase_unwrap": self.sparams_phase_unwrap.isChecked(),
                }

                # Save selected S-parameters (checkbox states)
                # Keys are now (comp_idx, j_idx, k_idx) for multi-component support
                if hasattr(self, 'sparams_checkboxes') and self.sparams_checkboxes:
                    selected_sparams = []
                    for key, checkbox in self.sparams_checkboxes.items():
                        if checkbox.isChecked():
                            # Handle both old (j_idx, k_idx) and new (comp_idx, j_idx, k_idx) formats
                            if len(key) == 3:
                                selected_sparams.append(list(key))  # [comp_idx, j_idx, k_idx]
                            else:
                                selected_sparams.append([0] + list(key))  # Assume comp 0
                    sparams_plot_settings["selected"] = selected_sparams

                data["scattering"]["sparams_plot"] = sparams_plot_settings

            # Save constraint groups
            if hasattr(self, 'scattering_constraint_groups') and self.scattering_constraint_groups:
                data["scattering"]["constraint_groups"] = self.scattering_constraint_groups
                data["scattering"]["next_constraint_group_id"] = self._next_constraint_group_id

        # Save notes content
        data["notes"] = self.properties_panel.notes_editor.toPlainText()

        # Generate and embed SVG representation of the graph
        svg_string = self._generate_svg_string(use_kron_canvas=False)
        if svg_string:
            data["svg"] = svg_string

            # Also save Kron SVG if Kron reduction is active
            if hasattr(self, 'kron_graph') and self.kron_graph:
                kron_svg_string = self._generate_svg_string(use_kron_canvas=True)
                if kron_svg_string:
                    data["kron_svg"] = kron_svg_string

        return data

    def _deserialize_graph(self, data):
        """Deserialize graph from dictionary (supports both .graph and .pgraph formats)"""
        # Clear ALL scattering data and state first (comprehensive clear)
        self._clear_scattering_data()

        # Clear current graph
        self.nodes = []
        self.edges = []
        self.selected_nodes = []
        self.selected_edges = []
        self.undo_stack = []

        # Detect format version
        version = data.get("version", "1.0")
        file_format = data.get("format", "graph")  # Default to old format

        # Restore view settings
        view = data.get("view", {})
        self.grid_type = view.get("grid_type", config.DEFAULT_GRID_TYPE)
        self.grid_rotation = view.get("grid_rotation", 0)
        self.zoom_level = view.get("zoom_level", 1.0)

        self.use_latex = view.get("use_latex", False)

        # Get extensible property dictionaries (new .pgraph format)
        node_properties = data.get("node_properties", {})
        edge_properties = data.get("edge_properties", {})
        code_properties = data.get("code_properties", {
            "imports": [],
            "node_code": {},
            "edge_code": {},
            "global_code": {}
        })

        # Restore nodes
        node_id_map = {}  # Map from saved node_id to node object
        max_node_id = 0

        for node_data in data.get("nodes", []):
            node = {
                "node_id": node_data["node_id"],
                "label": node_data["label"],
                "pos": tuple(node_data["pos"]),
                "color": node_data["color"],
                "color_key": node_data["color_key"],
                "node_size_mult": node_data.get("node_size_mult", 1.0),
                "label_size_mult": node_data.get("label_size_mult", 1.0),
                "conj": node_data.get("conj", False),
                "nodelabelnudge": tuple(node_data.get("nodelabelnudge", (0.0, 0.0))),
                "outline_enabled": node_data.get("outline_enabled", config.DEFAULT_NODE_OUTLINE_ENABLED),
                "outline_color_key": node_data.get("outline_color_key", "BLACK"),
                "outline_color": node_data.get("outline_color", config.DEFAULT_NODE_OUTLINE_COLOR),
                "outline_width": node_data.get("outline_width", config.DEFAULT_NODE_OUTLINE_WIDTH),
                "outline_alpha": node_data.get("outline_alpha", config.DEFAULT_NODE_OUTLINE_ALPHA)
            }

            # Restore numeric properties if present (new .pgraph format)
            node_id_str = str(node_data["node_id"])
            if node_id_str in node_properties:
                node["numeric_properties"] = node_properties[node_id_str]

            # Restore code properties if present (new .pgraph format)
            if node_id_str in code_properties.get("node_code", {}):
                node["code_properties"] = code_properties["node_code"][node_id_str]

            self.nodes.append(node)
            node_id_map[node_data["node_id"]] = node
            max_node_id = max(max_node_id, node_data["node_id"])

            # Load scattering parameters if present (stored using node_id, need to convert to id())
            if 'freq' in node_data or 'B_int' in node_data or 'B_ext' in node_data:
                node_obj_id = id(node)
                if node_obj_id not in self.scattering_assignments:
                    self.scattering_assignments[node_obj_id] = {}
                if 'freq' in node_data:
                    self.scattering_assignments[node_obj_id]['freq'] = node_data['freq']
                if 'B_int' in node_data:
                    self.scattering_assignments[node_obj_id]['B_int'] = node_data['B_int']
                if 'B_ext' in node_data:
                    self.scattering_assignments[node_obj_id]['B_ext'] = node_data['B_ext']

        # Update counters
        self.node_counter = len(self.nodes)
        self.node_id_counter = max_node_id + 1

        # Restore edges
        for edge_data in data.get("edges", []):
            from_node = node_id_map.get(edge_data["from_node_id"])
            to_node = node_id_map.get(edge_data["to_node_id"])

            if from_node and to_node:
                edge = {
                    "from_node": from_node,
                    "to_node": to_node,
                    "from_node_id": edge_data["from_node_id"],
                    "to_node_id": edge_data["to_node_id"],
                    "label1": edge_data.get("label1", ""),
                    "label2": edge_data.get("label2", ""),
                    "linewidth_mult": edge_data["linewidth_mult"],
                    "label_size_mult": edge_data["label_size_mult"],
                    "label_offset_mult": edge_data.get("label_offset_mult", 1.0),
                    "style": edge_data["style"],
                    "direction": edge_data["direction"],
                    "is_self_loop": edge_data["is_self_loop"],
                    "flip_labels": edge_data.get("flip_labels", False),
                    "label_rotation_offset": edge_data.get("label_rotation_offset", 0),
                    "looptheta": edge_data.get("looptheta", 30)
                }
                # Restore self-loop specific parameters
                if edge_data["is_self_loop"]:
                    edge["selfloopangle"] = edge_data.get("selfloopangle", 0)
                    edge["selfloopscale"] = edge_data.get("selfloopscale", 1.0)
                    edge["arrowlengthsc"] = edge_data.get("arrowlengthsc", 1.0)
                    edge["flip"] = edge_data.get("flip", False)
                    edge["selflooplabelnudge"] = tuple(edge_data.get("selflooplabelnudge", (0.0, 0.0)))
                    edge["label_bgcolor"] = edge_data.get("label_bgcolor", None)
                else:
                    # Restore regular edge label background colors
                    edge["label1_bgcolor"] = edge_data.get("label1_bgcolor", None)
                    edge["label2_bgcolor"] = edge_data.get("label2_bgcolor", None)

                # Restore numeric properties if present (new .pgraph format)
                edge_key = f"{edge_data['from_node_id']}_{edge_data['to_node_id']}"
                if edge_key in edge_properties:
                    edge["numeric_properties"] = edge_properties[edge_key]

                # Restore code properties if present (new .pgraph format)
                if edge_key in code_properties.get("edge_code", {}):
                    edge["code_properties"] = code_properties["edge_code"][edge_key]

                self.edges.append(edge)

                # Load scattering parameters if present (stored using edge tuple, need to convert to id())
                if 'f_p' in edge_data or 'rate' in edge_data or 'phase' in edge_data:
                    edge_obj_id = id(edge)
                    if edge_obj_id not in self.scattering_assignments:
                        self.scattering_assignments[edge_obj_id] = {}
                    if 'f_p' in edge_data:
                        self.scattering_assignments[edge_obj_id]['f_p'] = edge_data['f_p']
                    if 'rate' in edge_data:
                        self.scattering_assignments[edge_obj_id]['rate'] = edge_data['rate']
                    if 'phase' in edge_data:
                        self.scattering_assignments[edge_obj_id]['phase'] = edge_data['phase']

        # Store global code properties if present (new .pgraph format)
        if file_format == "pgraph":
            self.global_imports = code_properties.get("imports", [])
            self.global_code = code_properties.get("global_code", {})
            print(f"Loaded .pgraph file (version {version})")
        else:
            self.global_imports = []
            self.global_code = {}
            print(f"Loaded legacy .graph file (version {version})")

        # Restore Kron reduction data if present
        kron_data = data.get("kron_reduction", None)

        # Legacy support: check for old format where original_graph was at top level
        if kron_data is None and "original_graph" in data:
            kron_data = {"original_graph": data["original_graph"]}

        if kron_data is not None:
            # Restore original graph
            self.original_graph = kron_data.get("original_graph", None)

            # Restore Kron graph
            self.kron_graph = kron_data.get("kron_graph", None)

            # Restore base limits for Kron view
            if kron_data.get("kron_original_base_xlim"):
                self.kron_original_base_xlim = tuple(kron_data["kron_original_base_xlim"])
            if kron_data.get("kron_original_base_ylim"):
                self.kron_original_base_ylim = tuple(kron_data["kron_original_base_ylim"])

            # Restore selected nodes (need to map node IDs to actual node objects)
            kron_selected_node_ids = kron_data.get("kron_selected_node_ids", [])
            self.kron_selected_nodes = []
            if self.kron_graph and kron_selected_node_ids:
                kron_node_id_map = {n['node_id']: n for n in self.kron_graph['nodes']}
                self.kron_selected_nodes = [kron_node_id_map[nid] for nid in kron_selected_node_ids if nid in kron_node_id_map]

            # Restore affected nodes (need to map node IDs to actual node objects)
            kron_affected_node_ids = kron_data.get("kron_affected_node_ids", [])
            self.kron_affected_nodes = set()
            if self.kron_graph and kron_affected_node_ids:
                kron_node_id_map = {n['node_id']: n for n in self.kron_graph['nodes']}
                self.kron_affected_nodes = {kron_node_id_map[nid] for nid in kron_affected_node_ids if nid in kron_node_id_map}

            # Restore edge sets
            self.kron_new_edges = set(kron_data.get("kron_new_edges", []))
            self.kron_modified_edges = set(kron_data.get("kron_modified_edges", []))

            # Restore SymPy matrix
            matrix_repr = kron_data.get("kron_reduced_matrix_repr", None)
            if matrix_repr:
                try:
                    from sympy.parsing.sympy_parser import parse_expr
                    from sympy import sympify
                    # Use sympify to reconstruct the matrix from its string representation
                    self.kron_reduced_matrix = sympify(matrix_repr)
                    print("Restored Kron reduced matrix from saved representation")
                except Exception as e:
                    logger.warning("Could not restore Kron reduced matrix: %s", e)
                    self.kron_reduced_matrix = None
            else:
                self.kron_reduced_matrix = None

            # Restore LaTeX representation
            self.kron_reduced_matrix_latex = kron_data.get("kron_reduced_matrix_latex", None)

            if self.original_graph is not None:
                print(f"Restored Kron reduction:")
                print(f"  - Original graph: {len(self.original_graph.get('nodes', []))} nodes")
                if self.kron_graph:
                    print(f"  - Kron graph: {len(self.kron_graph.get('nodes', []))} nodes")
                if self.kron_selected_nodes:
                    print(f"  - Selected nodes: {len(self.kron_selected_nodes)}")
                if self.kron_reduced_matrix is not None:
                    print(f"  - Reduced matrix: restored")

                # Show the Kron tab (always index 1, right after Original)
                if hasattr(self, 'graph_subtabs'):
                    self.graph_subtabs.setTabVisible(1, True)

                # Update the Kron matrix display
                if hasattr(self, 'properties_panel'):
                    self.properties_panel._update_kron_matrix_display()

                # Update basis display to show original -> Kron mapping
                if hasattr(self, 'properties_panel'):
                    self.properties_panel._update_basis_display()

                # Render the Kron canvas if kron_graph exists
                if self.kron_graph and hasattr(self, 'kron_canvas'):
                    saved_canvas = self.canvas
                    saved_nodes = self.nodes
                    saved_edges = self.edges
                    saved_base_xlim = self.base_xlim
                    saved_base_ylim = self.base_ylim

                    self.canvas = self.kron_canvas
                    self.nodes = self.kron_graph['nodes']
                    self.edges = self.kron_graph['edges']
                    if hasattr(self, 'kron_original_base_xlim'):
                        self.base_xlim = self.kron_original_base_xlim
                        self.base_ylim = self.kron_original_base_ylim
                    self._update_plot()

                    self.canvas = saved_canvas
                    self.nodes = saved_nodes
                    self.edges = saved_edges
                    self.base_xlim = saved_base_xlim
                    self.base_ylim = saved_base_ylim

                # Regenerate SymPy code with Kron reduction
                if hasattr(self, 'properties_panel') and self.kron_reduced_matrix is not None:
                    # Regenerate the entire SymPy code from scratch
                    old_manual_code = getattr(self.properties_panel, '_sympy_code_manual', None)
                    self.properties_panel._sympy_code_manual = None

                    # Generate the base matrix code for the current graph
                    self.properties_panel._update_sympy_code_display()
                    base_code = self.properties_panel.sympy_code_display.toPlainText()

                    # Generate SymPy code for the Kron reduction
                    kron_code = self._generate_kron_sympy_code()

                    # Append the Kron reduction code to the base matrix code
                    separator = "\n\n# " + "="*70 + "\n"
                    separator += "# Kron Reduction\n"
                    separator += "# " + "="*70 + "\n\n"

                    new_code = base_code + separator + kron_code
                    self.properties_panel.sympy_code_display.setPlainText(new_code)
                    self.properties_panel._sympy_code_manual = new_code

        # Load scattering data if present
        if "scattering" in data:
            scattering_data = data["scattering"]

            # Load tree and chord edges (convert lists back to sets of tuples)
            if "tree_edges" in scattering_data:
                self.scattering_tree_edges = set(tuple(edge) for edge in scattering_data["tree_edges"])
            if "chord_edges" in scattering_data:
                self.scattering_chord_edges = set(tuple(edge) for edge in scattering_data["chord_edges"])

            # Load frequency settings
            if "frequency" in scattering_data:
                freq_settings = scattering_data["frequency"]
                if hasattr(self, 'properties_panel'):
                    # Handle both old (start/stop) and new (center/span) formats
                    if "center" in freq_settings and "span" in freq_settings:
                        self.properties_panel.freq_center_spin.setValue(freq_settings.get("center", config.FREQ_CENTER_DEFAULT))
                        self.properties_panel.freq_span_spin.setValue(freq_settings.get("span", config.FREQ_SPAN_DEFAULT))
                    elif "start" in freq_settings and "stop" in freq_settings:
                        # Convert old format to center/span
                        start = freq_settings.get("start", 0.0)
                        stop = freq_settings.get("stop", 10.0)
                        center = (start + stop) / 2
                        span = stop - start
                        self.properties_panel.freq_center_spin.setValue(center)
                        self.properties_panel.freq_span_spin.setValue(span)
                    self.properties_panel.freq_points_spin.setValue(freq_settings.get("points", config.FREQ_POINTS_DEFAULT))

            # Load injection node selection
            if "injection_node_id" in scattering_data and scattering_data["injection_node_id"] is not None:
                injection_node_id = scattering_data["injection_node_id"]
                # Set injection node after updating the combo box (deferred via QTimer)
                if hasattr(self, 'properties_panel') and hasattr(self.properties_panel, 'injection_node_combo'):
                    combo = self.properties_panel.injection_node_combo
                    # Find index with matching node_id
                    for i in range(combo.count()):
                        if combo.itemData(i) == injection_node_id:
                            combo.setCurrentIndex(i)
                            print(f"Restored injection node: {combo.itemText(i)} (node_id={injection_node_id})")
                            break

            # Load S-parameter plot settings if present
            if "sparams_plot" in scattering_data:
                sparams_settings = scattering_data["sparams_plot"]

                # Store settings to apply after S-params are calculated
                self._pending_sparams_settings = sparams_settings
                print(f"Loaded S-parameter plot settings: xlim={sparams_settings.get('xlim')}, "
                      f"ylim={sparams_settings.get('ylim')}, selected={sparams_settings.get('selected')}")

            # Load constraint groups if present
            if "constraint_groups" in scattering_data:
                # Convert string keys back to integers
                loaded_groups = scattering_data["constraint_groups"]
                self.scattering_constraint_groups = {
                    int(k): v for k, v in loaded_groups.items()
                }
                self._next_constraint_group_id = scattering_data.get("next_constraint_group_id", 1)
                # Backward compatibility: ensure old files have is_conjugate_pair field
                for group_data in self.scattering_constraint_groups.values():
                    if 'is_conjugate_pair' not in group_data:
                        group_data['is_conjugate_pair'] = False
                print(f"Loaded {len(self.scattering_constraint_groups)} constraint groups")

        # Update scattering parameter tables to reflect loaded/cleared data
        if hasattr(self, 'properties_panel'):
            self.properties_panel._update_scattering_node_table()
            self.properties_panel._update_scattering_edge_table()
            # Apply constraint styling after tables are rebuilt
            self.properties_panel._apply_constraint_styling()

        # Update conjugate pair constraints (ensures consistency after load)
        self._update_conjugate_pair_constraints()

        # Load notes content (backward compatible - default to empty string)
        notes = data.get("notes", "")
        if hasattr(self, 'properties_panel') and hasattr(self.properties_panel, 'notes_editor'):
            self.properties_panel.notes_editor.setPlainText(notes)
            # Reset preview - if notes are empty, show placeholder; otherwise render will happen on tab switch
            if hasattr(self.properties_panel, 'notes_preview'):
                if not notes.strip():
                    self.properties_panel.notes_preview.setHtml(
                        "<html><body><p style='color: #888; font-style: italic;'>"
                        "No notes yet. Add notes using the Edit tab.</p></body></html>"
                    )
                else:
                    # Render the notes preview so it's ready when user switches to Preview tab
                    self.properties_panel._render_notes_preview()

        # Determine initial tab/mode based on loaded content
        has_notes = bool(notes and notes.strip())
        has_scattering_assignments = bool(self.scattering_assignments)

        # Enable scattering mode if any assignments exist (independent of tab display)
        if has_scattering_assignments:
            self._enter_scattering_mode()
            print("Enabled scattering mode (scattering assignments detected)")

        # Tab display priority: Notes > Scattering > Symbolic/Matrix
        if has_notes:
            # Show Notes tab with Preview subtab
            if hasattr(self, 'properties_panel'):
                self.properties_panel.tabs.setCurrentIndex(1)  # Notes tab
                self.properties_panel.notes_subtabs.setCurrentIndex(1)  # Preview subtab
                print("Opened Notes tab with Preview (notes content detected)")
        elif has_scattering_assignments:
            # Show Scattering assignment tab
            if hasattr(self, 'properties_panel'):
                self.properties_panel.tabs.setCurrentIndex(self.properties_panel.scattering_tab_index)
                print("Opened Scattering tab (scattering assignments detected)")
        else:
            # Show Symbolic tab with Matrix subtab (default)
            if hasattr(self, 'properties_panel'):
                self.properties_panel.tabs.setCurrentIndex(2)  # Symbolic tab
                self.properties_panel.symbolic_subtabs.setCurrentIndex(0)  # Matrix subtab
                print("Opened Symbolic/Matrix tab (default)")

        # ALWAYS render the Original graph canvas first (before auto-fit which may switch views)
        self._update_plot()

        # Auto-fit view to loaded graph (center and zoom to fit all objects)
        self._auto_fit_view()

    def _new_graph(self):
        """Create a new graph"""
        if not self._check_unsaved_changes():
            return

        self.nodes = []
        self.edges = []
        self.selected_nodes = []
        self.selected_edges = []
        self.undo_stack = []
        self.current_filepath = None
        self.node_counter = 0
        self.node_id_counter = 0

        # Reset global code properties
        self.global_imports = []
        self.global_code = {}

        # Reset Kron reduction state
        self.kron_mode = False
        self.kron_selected_nodes = []
        self.kron_reduced_matrix = None
        self.kron_reduced_matrix_latex = None
        self.kron_reduced_nodes = []
        self.kron_reduced_edges = []
        self.kron_affected_nodes = set()
        self.kron_new_edges = set()
        self.kron_modified_edges = set()
        self.original_graph = None
        self.viewing_original = False

        # Clear scattering data (exit mode and reset all state)
        self._clear_scattering_data()

        # Reset view
        self.grid_type = config.DEFAULT_GRID_TYPE
        self.grid_rotation = 0
        self.zoom_level = 1.0
        self.canvas.ax.set_xlim(*config.DEFAULT_XLIM)
        self.canvas.ax.set_ylim(*config.DEFAULT_YLIM)

        # Clear matrix displays and SymPy code
        if hasattr(self, 'properties_panel'):
            # Clear the manual SymPy code cache
            self.properties_panel._sympy_code_manual = None
            self.properties_panel._update_matrix_display()
            self.properties_panel._update_kron_matrix_display()
            self.properties_panel._update_sympy_code_display()
            # Clear notes and reset preview
            if hasattr(self.properties_panel, 'notes_editor'):
                self.properties_panel.notes_editor.clear()
            if hasattr(self.properties_panel, 'notes_preview'):
                self.properties_panel.notes_preview.setHtml(
                    "<html><body><p style='color: #888; font-style: italic;'>"
                    "No notes yet. Add notes using the Edit tab.</p></body></html>"
                )

        # Reset graph subtabs to show original graph and hide Kron tab
        if hasattr(self, 'graph_subtabs'):
            self.graph_subtabs.setCurrentIndex(0)
            # Hide Kron tab on new graph (always index 1)
            self.graph_subtabs.setTabVisible(1, False)

        self._set_modified(False)
        self._update_plot()
        print("New graph created")

    def _open_graph(self):
        """Open a graph from file"""
        if not self._check_unsaved_changes():
            return

        filepath, _ = QFileDialog.getOpenFileName(
            self, "Open Graph", self._get_default_directory(),
            "Parametric Graph Files (*.pgraph);;Legacy Graph Files (*.graph);;All Files (*)"
        )

        if filepath:
            self._open_graph_file(filepath)

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
            print(f"Opened graph from {filepath}")

        except Exception as e:
            QMessageBox.critical(
                self, "Error Opening File",
                f"Could not open file:\n{e}"
            )
            print(f"Error opening graph: {e}")

    def _open_settings(self):
        """Open the settings dialog"""
        from .para_ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self)
        dialog.exec()

    def _show_settings_file_location(self):
        """Open the file manager at the settings file location"""
        import subprocess

        # Ensure the settings directory exists
        USER_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)

        # Create a default settings file if it doesn't exist
        if not USER_SETTINGS_FILE.exists():
            # Save current settings to create the file
            save_user_settings()

        # Open file manager with the settings file selected (platform-specific)
        if sys.platform == 'darwin':
            # macOS: open Finder with file selected
            subprocess.run(['open', '-R', str(USER_SETTINGS_FILE)])
        elif sys.platform == 'win32':
            # Windows: open Explorer with file selected
            subprocess.run(['explorer', '/select,', str(USER_SETTINGS_FILE)])
        else:
            # Linux/other: open file manager at directory
            subprocess.run(['xdg-open', str(USER_SETTINGS_DIR)])

    def _save_graph(self):
        """Save the current graph"""
        if self.current_filepath:
            return self._save_graph_to_file(self.current_filepath)
        else:
            return self._save_graph_as()

    def _save_graph_as(self):
        """Save the graph to a new file"""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Graph As", self._get_default_directory(),
            "Parametric Graph Files (*.pgraph);;All Files (*)"
        )

        if filepath:
            # Add .pgraph extension if not present
            if not filepath.endswith('.pgraph'):
                filepath += '.pgraph'
            return self._save_graph_to_file(filepath)
        return False

    def _save_graph_to_file(self, filepath):
        """Save graph to specified file"""
        try:
            data = self._serialize_graph()

            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)

            self.current_filepath = filepath
            self._set_modified(False)
            self._add_to_recent_files(filepath)
            self._save_last_directory(filepath)

            # Also save as last graph
            try:
                with open(self.last_graph_path, 'w') as f:
                    json.dump(data, f, indent=2)
            except:
                pass  # Don't fail if we can't save last graph

            print(f"Saved graph to {filepath}")
            return True

        except Exception as e:
            QMessageBox.critical(
                self, "Error Saving File",
                f"Could not save file:\n{e}"
            )
            print(f"Error saving graph: {e}")
            return False

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
            print("Reloaded last graph")

        except Exception as e:
            QMessageBox.critical(
                self, "Error Loading Last Graph",
                f"Could not load last graph:\n{e}"
            )

    def _export_png(self):
        """Export graph as PNG image"""
        # Determine which canvas to export based on currently displayed tab
        export_kron = False
        saved_canvas = None
        saved_nodes = None
        saved_edges = None

        if hasattr(self, 'graph_subtabs') and hasattr(self, 'kron_graph') and self.kron_graph:
            current_tab = self.graph_subtabs.currentIndex()
            tab_text = self.graph_subtabs.tabText(current_tab) if current_tab >= 0 else ""
            if tab_text == "Kron":
                export_kron = True
                print("Exporting Kron canvas...")
                saved_canvas = self.canvas
                saved_nodes = self.nodes
                saved_edges = self.edges
                self.canvas = self.kron_canvas
                self.nodes = self.kron_graph['nodes']
                self.edges = self.kron_graph['edges']

        try:
            if not self.nodes:
                print("No nodes to export")
                return

            filepath, _ = QFileDialog.getSaveFileName(
                self, "Export PNG", "", "PNG Images (*.png);;All Files (*)"
            )

            if filepath:
                if not filepath.endswith('.png'):
                    filepath += '.png'
                try:
                    # Save current title
                    current_title = self.canvas.ax.get_title()

                    # Clear title for export
                    self.canvas.ax.set_title('')

                    # Redraw without grid
                    self._update_plot_no_grid()

                    # Export
                    self.canvas.fig.savefig(filepath, dpi=300, bbox_inches='tight')

                    # Restore title and redraw with grid
                    self.canvas.ax.set_title(current_title)
                    self._update_plot()

                    print(f"Exported PNG to {filepath}")
                except Exception as e:
                    QMessageBox.critical(self, "Export Error", f"Could not export PNG:\n{e}")
        finally:
            # Restore original canvas/nodes/edges if we swapped to Kron
            if export_kron:
                self.canvas = saved_canvas
                self.nodes = saved_nodes
                self.edges = saved_edges

    def _export_svg(self):
        """Export graph as SVG image"""
        # Determine which canvas to export based on currently displayed tab
        export_kron = False
        saved_canvas = None
        saved_nodes = None
        saved_edges = None

        if hasattr(self, 'graph_subtabs') and hasattr(self, 'kron_graph') and self.kron_graph:
            current_tab = self.graph_subtabs.currentIndex()
            tab_text = self.graph_subtabs.tabText(current_tab) if current_tab >= 0 else ""
            if tab_text == "Kron":
                export_kron = True
                print("Exporting Kron canvas...")
                saved_canvas = self.canvas
                saved_nodes = self.nodes
                saved_edges = self.edges
                self.canvas = self.kron_canvas
                self.nodes = self.kron_graph['nodes']
                self.edges = self.kron_graph['edges']

        try:
            if not self.nodes:
                print("No nodes to export")
                return

            filepath, _ = QFileDialog.getSaveFileName(
                self, "Export SVG", "", "SVG Images (*.svg);;All Files (*)"
            )

            if filepath:
                if not filepath.endswith('.svg'):
                    filepath += '.svg'
                try:
                    # Save current title
                    current_title = self.canvas.ax.get_title()

                    # Clear title for export
                    self.canvas.ax.set_title('')

                    # Redraw without grid
                    self._update_plot_no_grid()

                    # Export
                    self.canvas.fig.savefig(filepath, format='svg', bbox_inches='tight')

                    # Restore title and redraw with grid
                    self.canvas.ax.set_title(current_title)
                    self._update_plot()

                    print(f"Exported SVG to {filepath}")
                except Exception as e:
                    QMessageBox.critical(self, "Export Error", f"Could not export SVG:\n{e}")
        finally:
            # Restore original canvas/nodes/edges if we swapped to Kron
            if export_kron:
                self.canvas = saved_canvas
                self.nodes = saved_nodes
                self.edges = saved_edges

    def _generate_svg_string(self, use_kron_canvas: bool = False) -> str:
        """Generate SVG string from the current graph canvas.

        Parameters
        ----------
        use_kron_canvas : bool, default=False
            If True and Kron reduction is active, generate SVG from the Kron canvas.
            Otherwise, generate from the main canvas.

        Returns
        -------
        str
            The SVG content as a string, or empty string if generation fails.
        """
        import io

        if not self.nodes:
            return ""

        # Determine which canvas to use
        canvas_to_use = self.canvas
        if use_kron_canvas and hasattr(self, 'kron_graph') and self.kron_graph and hasattr(self, 'kron_canvas'):
            canvas_to_use = self.kron_canvas

        try:
            # Save current title
            current_title = canvas_to_use.ax.get_title()

            # Clear title for export
            canvas_to_use.ax.set_title('')

            # Redraw without grid
            self._update_plot_no_grid()

            # Generate SVG to string buffer
            svg_buffer = io.StringIO()
            canvas_to_use.fig.savefig(svg_buffer, format='svg', bbox_inches='tight')
            svg_string = svg_buffer.getvalue()
            svg_buffer.close()

            # Restore title and redraw with grid
            canvas_to_use.ax.set_title(current_title)
            self._update_plot()

            return svg_string

        except Exception as e:
            logger.warning("Could not generate SVG string: %s", e)
            return ""

    def _export_pdf(self):
        """Export graph as PDF document"""
        # Determine which canvas to export based on currently displayed tab
        export_kron = False
        saved_canvas = None
        saved_nodes = None
        saved_edges = None

        if hasattr(self, 'graph_subtabs') and hasattr(self, 'kron_graph') and self.kron_graph:
            current_tab = self.graph_subtabs.currentIndex()
            tab_text = self.graph_subtabs.tabText(current_tab) if current_tab >= 0 else ""
            if tab_text == "Kron":
                export_kron = True
                print("Exporting Kron canvas...")
                saved_canvas = self.canvas
                saved_nodes = self.nodes
                saved_edges = self.edges
                self.canvas = self.kron_canvas
                self.nodes = self.kron_graph['nodes']
                self.edges = self.kron_graph['edges']

        try:
            if not self.nodes:
                print("No nodes to export")
                return

            filepath, _ = QFileDialog.getSaveFileName(
                self, "Export PDF", "", "PDF Documents (*.pdf);;All Files (*)"
            )

            if filepath:
                if not filepath.endswith('.pdf'):
                    filepath += '.pdf'
                try:
                    # Save current title
                    current_title = self.canvas.ax.get_title()

                    # Clear title for export
                    self.canvas.ax.set_title('')

                    # Redraw without grid
                    self._update_plot_no_grid()

                    # For LaTeX mode, save as SVG first, then convert to PDF to get outlined text
                    # SVG naturally stores LaTeX text as paths, which Illustrator can read
                    if self.use_latex:
                        print("LaTeX mode: Exporting via SVG for text-as-paths compatibility")
                        # Save as SVG (text will be paths)
                        svg_filepath = filepath.replace('.pdf', '_temp.svg')
                        self.canvas.fig.savefig(svg_filepath, format='svg', bbox_inches='tight')

                        # Try to convert SVG to PDF using cairosvg or similar
                        try:
                            import cairosvg
                            cairosvg.svg2pdf(url=svg_filepath, write_to=filepath)
                            os.remove(svg_filepath)  # Clean up temp file
                            print(f"Exported PDF with outlined text to {filepath}")
                        except ImportError:
                            print("Note: cairosvg not installed. Saved as SVG instead.")
                            print("Install with: pip install cairosvg")
                            print("Or use the SVG export which already has text as paths.")
                            # Fall back to regular PDF export
                            import matplotlib
                            original_fonttype = matplotlib.rcParams.get('pdf.fonttype', 42)
                            matplotlib.rcParams['pdf.fonttype'] = 42
                            self.canvas.fig.savefig(filepath, format='pdf', bbox_inches='tight', dpi=300)
                            matplotlib.rcParams['pdf.fonttype'] = original_fonttype
                            print(f"Exported PDF (fonts embedded) to {filepath}")
                    else:
                        # Non-LaTeX mode: standard PDF export
                        import matplotlib
                        original_fonttype = matplotlib.rcParams.get('pdf.fonttype', 42)
                        matplotlib.rcParams['pdf.fonttype'] = 42
                        self.canvas.fig.savefig(filepath, format='pdf', bbox_inches='tight', dpi=300)
                        matplotlib.rcParams['pdf.fonttype'] = original_fonttype

                    # Restore title and redraw with grid
                    self.canvas.ax.set_title(current_title)
                    self._update_plot()

                    print(f"Exported PDF to {filepath}")
                except Exception as e:
                    QMessageBox.critical(self, "Export Error", f"Could not export PDF:\n{e}")
        except Exception as e:
            # Catch any outer exceptions
            print(f"Error in PDF export: {e}")
        finally:
            # Restore original canvas/nodes/edges if we swapped to Kron
            if export_kron:
                self.canvas = saved_canvas
                self.nodes = saved_nodes
                self.edges = saved_edges

    def closeEvent(self, event):
        """Handle window close event"""
        if self._check_unsaved_changes():
            # Save last graph automatically
            try:
                data = self._serialize_graph()
                with open(self.last_graph_path, 'w') as f:
                    json.dump(data, f, indent=2)
            except:
                pass  # Don't prevent closing if save fails

            # Clean up matplotlib canvases to prevent segfault
            try:
                if hasattr(self, 'canvas') and self.canvas:
                    self.canvas.close()
                if hasattr(self, 'kron_canvas') and self.kron_canvas:
                    self.kron_canvas.close()
                if hasattr(self, 'scattering_canvas') and self.scattering_canvas:
                    self.scattering_canvas.close()
            except:
                pass  # Don't prevent closing if cleanup fails

            event.accept()
        else:
            event.ignore()

    def resizeEvent(self, event):
        """Handle window resize event - redraw with debouncing to prevent freezing"""
        super().resizeEvent(event)

        # Just restart the debounce timer - _get_xlim() and _get_ylim() already
        # handle aspect ratio adjustments automatically
        self.resize_debounce_timer.stop()
        self.resize_debounce_timer.start(self.resize_debounce_timeout)

    def _handle_resize_complete(self):
        """Called when resize debounce timer completes - redraw the plot"""
        # The _get_xlim() and _get_ylim() functions automatically adjust limits
        # to match canvas aspect ratio, so we just need to trigger a redraw
        canvas_width = self.canvas.size().width()
        canvas_height = self.canvas.size().height()

        if canvas_height > 0 and canvas_width > 0:
            print("\n" + "="*60)
            print("WINDOW RESIZE COMPLETE - Redrawing")
            print("="*60)
            print(f"Canvas size: {canvas_width} x {canvas_height}")
            print(f"Canvas aspect ratio: {canvas_width/canvas_height:.3f}")
            xlim = self._get_xlim()
            ylim = self._get_ylim()
            print(f"Calculated xlim: [{xlim[0]:.2f}, {xlim[1]:.2f}]")
            print(f"Calculated ylim: [{ylim[0]:.2f}, {ylim[1]:.2f}]")
            print("="*60 + "\n")

            self._update_plot()

    def _set_placement_mode(self, mode):
        """Set placement mode"""
        self.placement_mode = mode
        print(f"Placement mode: {mode}")
        self._update_plot()

    def _toggle_continuous_mode(self):
        """Toggle continuous placement mode"""
        if self.placement_mode == 'continuous':
            self.placement_mode = None
            print("Exited continuous placement mode")
        else:
            self.placement_mode = 'continuous'
            print("Continuous placement mode - click to place nodes, press G again to exit")
        self._update_plot()

    def _auto_increment_label(self, label):
        """Auto-increment a label based on its pattern

        Examples:
        - 'A' -> 'B', 'Z' -> 'AA'
        - 'A_1' -> 'A_2', 'A_9' -> 'A_{10}'
        - 'A0' -> 'A1', 'B9' -> 'B10'
        - '1' -> '2', '99' -> '100'
        """

        # Pattern 1: Letter with underscore and number (e.g., 'A_1', 'B_12')
        match = re.match(r'^([A-Za-z]+)_(\d+)$', label)
        if match:
            prefix = match.group(1)
            num = int(match.group(2))
            next_num = num + 1
            # Use braces for multi-digit numbers
            if next_num >= 10:
                return f"{prefix}_{{{next_num}}}"
            else:
                return f"{prefix}_{next_num}"

        # Pattern 2: Letter(s) followed directly by number (e.g., 'A0', 'B1', 'Mode2')
        match = re.match(r'^([A-Za-z]+)(\d+)$', label)
        if match:
            prefix = match.group(1)
            num = int(match.group(2))
            return f"{prefix}{num + 1}"

        # Pattern 3: Pure number (e.g., '1', '42')
        match = re.match(r'^(\d+)$', label)
        if match:
            num = int(match.group(1))
            return str(num + 1)

        # Pattern 4: Pure uppercase letter(s) (e.g., 'A', 'Z', 'AA')
        match = re.match(r'^([A-Z]+)$', label)
        if match:
            letters = match.group(1)
            # Convert to number, increment, convert back
            # A=1, B=2, ..., Z=26, AA=27, etc.
            num = 0
            for char in letters:
                num = num * 26 + (ord(char) - ord('A') + 1)
            num += 1

            # Convert back to letters
            result = ''
            while num > 0:
                num -= 1
                result = chr(ord('A') + (num % 26)) + result
                num //= 26
            return result

        # Pattern 5: Pure lowercase letters
        match = re.match(r'^([a-z]+)$', label)
        if match:
            letters = match.group(1)
            num = 0
            for char in letters:
                num = num * 26 + (ord(char) - ord('a') + 1)
            num += 1

            result = ''
            while num > 0:
                num -= 1
                result = chr(ord('a') + (num % 26)) + result
                num //= 26
            return result

        # If no pattern matches, just return the original label
        return label

    def _reset_last_node_props_to_defaults(self, preserve_label=True):
        """Reset last_node_props to current config defaults.

        Called when settings are changed via Settings dialog to ensure
        continuous duplicate mode uses the new default values.

        Args:
            preserve_label: If True and last_node_props exists, preserve its label
                           to maintain auto-increment sequence. Default True.
        """
        # Preserve current label if requested and it exists
        current_label = ''
        if preserve_label and self.last_node_props is not None:
            current_label = self.last_node_props.get('label', '')

        default_color_key = config.DEFAULT_NODE_COLOR_KEY
        outline_color_key = getattr(config, 'DEFAULT_NODE_OUTLINE_COLOR_KEY', 'BLACK')
        self.last_node_props = {
            'label': current_label,
            'color': config.MYCOLORS.get(default_color_key, 'indianred'),
            'color_key': default_color_key,
            'node_size_mult': config.DEFAULT_NODE_SIZE_MULT,
            'label_size_mult': config.DEFAULT_NODE_LABEL_SIZE_MULT,
            'conj': config.DEFAULT_NODE_CONJUGATED,
            'outline_enabled': config.DEFAULT_NODE_OUTLINE_ENABLED,
            'outline_color_key': outline_color_key,
            'outline_color': config.MYCOLORS.get(outline_color_key, 'black'),
            'outline_width': config.DEFAULT_NODE_OUTLINE_WIDTH,
            'outline_alpha': config.DEFAULT_NODE_OUTLINE_ALPHA
        }

    def _toggle_continuous_duplicate_mode(self):
        """Toggle continuous duplicate placement mode"""
        if self.placement_mode == 'continuous_duplicate':
            self.placement_mode = None
            print("Exited continuous duplicate mode")
        else:
            # If no previous node, use defaults from config
            if self.last_node_props is None:
                self._reset_last_node_props_to_defaults()
                print("Continuous duplicate mode - starting with 'A'")
            else:
                print(f"Continuous duplicate mode - duplicating '{self.last_node_props['label']}' ({self.last_node_props['color_key']}) with auto-increment")

            self.placement_mode = 'continuous_duplicate'
            print("Click to place nodes, press Ctrl+G again to exit")
        self._update_plot()

    def _toggle_conjugation_mode(self):
        """Toggle conjugation mode or toggle selected nodes"""
        # If nodes are selected, toggle their conjugation directly
        if self.selected_nodes:
            self._save_state()
            for node in self.selected_nodes:
                node['conj'] = not node.get('conj', False)
                # Update edge styles for edges connected to this node
                self._update_edge_styles_for_node(node)
            conj_count = sum(1 for node in self.selected_nodes if node.get('conj', False))
            print(f"Toggled conjugation for {len(self.selected_nodes)} node(s) ({conj_count} now conjugated)")
            # Update conjugate pair constraints (may create or dissolve constraint groups)
            self._update_conjugate_pair_constraints()
            self._update_plot()
        # Otherwise, enter/exit conjugation mode
        elif self.placement_mode == 'conjugation':
            self.placement_mode = None
            print("Exited conjugation mode")
            self._update_plot()
        else:
            self.placement_mode = 'conjugation'
            print("Conjugation mode - click nodes to toggle conjugation ('c' or Esc to exit)")
            self._update_plot()

    def _toggle_basis_ordering_mode(self):
        """Toggle basis ordering mode"""
        if self.basis_ordering_mode:
            # Exit basis ordering mode
            self.basis_ordering_mode = False
            self.basis_order.clear()
            self.basis_order_undo_stack.clear()
            print("Exited basis ordering mode")
            # Disable commit action in menu
            self.commit_basis_action.setEnabled(False)
            self.properties_panel._update_basis_display()
            self._update_plot()
        else:
            # Enter basis ordering mode
            self.basis_ordering_mode = True
            self.basis_order.clear()
            self.basis_order_undo_stack.clear()
            print("Basis ordering mode - click nodes to set basis order (Ctrl+Shift+B to exit, Ctrl+Shift+Enter to commit)")
            print("  Ctrl+Z: Undo last selection | Ctrl+Shift+Z: Redo | Esc: Cancel")

            # Enable commit action in menu
            self.commit_basis_action.setEnabled(True)

            # Auto-switch to Basis tab (inside Symbolic tab)
            self.properties_panel.tabs.setCurrentIndex(2)  # Symbolic tab
            self.properties_panel.symbolic_subtabs.setCurrentIndex(1)  # Basis subtab

            self.properties_panel._update_basis_display()
            self._update_plot()

    def _commit_basis_ordering(self):
        """Commit the basis ordering and update node order"""
        if not self.basis_ordering_mode:
            return

        if not self.basis_order:
            print("No basis order selected - keeping current order")
            self.basis_ordering_mode = False
            self._update_plot()
            return

        # Reorder nodes: selected nodes first in selection order, then remaining nodes in current order
        ordered_nodes = self.basis_order.copy()
        remaining_nodes = [node for node in self.nodes if node not in self.basis_order]
        self.nodes = ordered_nodes + remaining_nodes

        print(f"✓ Basis order committed: {[node['label'] for node in self.nodes]}")

        # If Kron reduction exists, update the stored original_graph to reflect the new node order
        if hasattr(self, 'original_graph') and self.original_graph:
            self.original_graph['nodes'] = [n.copy() for n in self.nodes]

        # Exit basis ordering mode
        self.basis_ordering_mode = False
        self.basis_order.clear()
        self.basis_order_undo_stack.clear()

        # Disable commit action in menu
        self.commit_basis_action.setEnabled(False)

        # Clear any cached manual SymPy code so it regenerates based on new node order
        if hasattr(self.properties_panel, '_sympy_code_manual'):
            self.properties_panel._sympy_code_manual = None

        # Update displays
        self.properties_panel._update_basis_display()
        self.properties_panel._update_matrix_display()
        self.properties_panel._update_sympy_code_display()
        self._update_plot()

    def _cancel_basis_ordering(self):
        """Cancel basis ordering and exit mode"""
        if self.basis_ordering_mode:
            self.basis_ordering_mode = False
            self.basis_order.clear()
            self.basis_order_undo_stack.clear()
            # Disable commit action in menu
            self.commit_basis_action.setEnabled(False)
            print("Cancelled basis ordering")
            self._update_plot()

    def _undo_basis_selection(self):
        """Undo the last node selection in basis ordering mode"""
        if self.basis_ordering_mode and self.basis_order:
            removed_node = self.basis_order.pop()
            self.basis_order_undo_stack.append(removed_node)
            print(f"Removed '{removed_node['label']}' from basis order")
            self._update_plot()

    def _redo_basis_selection(self):
        """Redo the last undone node selection in basis ordering mode"""
        if self.basis_ordering_mode and self.basis_order_undo_stack:
            node = self.basis_order_undo_stack.pop()
            self.basis_order.append(node)
            print(f"Re-added '{node['label']}' to basis order")
            self._update_plot()

    # === Kron Reduction Mode Methods ===

    def _enter_kron_mode(self):
        """Enter Kron reduction mode"""
        print("DEBUG: _enter_kron_mode() called")
        # Check if already in another mode
        if self.basis_ordering_mode:
            print("Cannot enter Kron mode while in basis ordering mode")
            return

        if self.kron_mode:
            print("Already in Kron reduction mode")
            return

        if not self.nodes:
            print("Cannot enter Kron mode: no nodes in graph")
            return

        # Enter mode
        self.kron_mode = True
        print(f"DEBUG: Set kron_mode = True")
        self.kron_selected_nodes.clear()

        # Clear any active selections and deactivate placement modes
        self.selected_nodes.clear()
        self.selected_edges.clear()
        self.placement_mode = None
        self.edge_placement_mode = False
        self.edge_placement_start_node = None

        # Switch to Matrix tab (inside Symbolic tab), then Kron subtab
        self.properties_panel.tabs.setCurrentIndex(2)  # Symbolic tab
        self.properties_panel.symbolic_subtabs.setCurrentIndex(0)  # Matrix subtab
        self.properties_panel.matrix_subtabs.setCurrentIndex(1)  # 1 = Kron subtab

        # Update display
        self._update_plot()

        # Print instructions
        print("=" * 70)
        print("KRON REDUCTION MODE")
        print("=" * 70)
        print("Click nodes to select/deselect for KEEPING (not eliminating)")
        print("Selected nodes will show GREEN rings")
        print("Unselected nodes will show RED rings and will be ELIMINATED")
        print()
        print("The Schur complement will compute effective couplings between")
        print("the kept nodes, eliminating the unselected nodes.")
        print()
        print("Controls:")
        print("  - Click node: Toggle selection (keep/eliminate)")
        print("  - Esc: Cancel and exit mode")
        print("  - Ctrl+Shift+Enter: Commit reduction")
        print()
        print("Shortcut: Ctrl+Shift+K to enter Kron reduction mode")
        print("=" * 70)

    def _build_kron_graph(self):
        """Build the kron_graph structure from reduced matrix.

        Creates:
        - nodes: Copies of selected nodes with original styling preserved
        - edges: NEW edges determined by non-zero off-diagonal elements in reduced matrix
        """
        import copy

        # Get the reduced matrix (already computed and stored)
        M_reduced = self.kron_reduced_matrix
        n = len(self.kron_selected_nodes)

        # DEBUG: Print the matrix we're working with
        print(f"\n[DEBUG _build_kron_graph]")
        print(f"Number of selected nodes: {n}")
        print(f"Selected node labels: {[node['label'] for node in self.kron_selected_nodes]}")
        print(f"Reduced matrix M_reduced:")
        print(M_reduced)

        # Create node list (deep copies of selected nodes)
        kron_nodes = []
        for node in self.kron_selected_nodes:
            node_copy = copy.deepcopy(node)
            # Apply Kron graph styling: slategray node outlines
            node_copy['edgecolor'] = 'slategray'
            kron_nodes.append(node_copy)

        # Build the original matrix for just the selected nodes (for comparison)
        # This matrix has the ORIGINAL coupling values between selected nodes
        M_original_subset = Matrix.zeros(n, n)
        for i, node_i in enumerate(self.kron_selected_nodes):
            for j, node_j in enumerate(self.kron_selected_nodes):
                if i == j:
                    # Diagonal: on-site energy
                    M_original_subset[i, j] = Symbol(f'Delta_{{{node_i["label"]}}}', real=True)
                else:
                    # Off-diagonal: look for edge between these nodes in original graph
                    edge_found = None
                    for edge in self.original_graph['edges']:
                        if ((edge['from_node'] == node_i and edge['to_node'] == node_j) or
                            (edge['from_node'] == node_j and edge['to_node'] == node_i)):
                            edge_found = edge
                            break

                    if edge_found:
                        # Use the edge's beta symbol
                        from_label = edge_found['from_node']['label']
                        to_label = edge_found['to_node']['label']
                        if from_label < to_label:
                            beta_sym = Symbol(f'beta_{{{from_label}{to_label}}}', complex=True)
                        else:
                            beta_sym = Symbol(f'beta_{{{to_label}{from_label}}}', complex=True)
                        M_original_subset[i, j] = beta_sym
                    else:
                        # No edge in original graph
                        M_original_subset[i, j] = 0

        # Build a mapping from node to index in reduced matrix
        node_to_idx = {id(node): i for i, node in enumerate(self.kron_selected_nodes)}

        # Build original graph edge mapping for comparison
        # Maps (from_node_id, to_node_id) -> edge_dict
        original_edges_map = {}
        for edge in self.original_graph['edges']:
            from_id = id(edge['from_node'])
            to_id = id(edge['to_node'])
            # Store both directions for undirected edges
            original_edges_map[(from_id, to_id)] = edge
            original_edges_map[(to_id, from_id)] = edge

        # Create edges from the reduced matrix
        kron_edges = []

        for i in range(n):
            for j in range(i+1, n):  # Only upper triangle to avoid duplicates
                # Get matrix element M_reduced[i,j]
                elem_reduced = M_reduced[i, j]
                elem_original = M_original_subset[i, j]

                # Check if this element is non-zero (symbolically)
                elem_simplified = simplify(elem_reduced)

                # DEBUG: Print what we're seeing
                print(f"\n[DEBUG] Edge ({kron_nodes[i]['label']}, {kron_nodes[j]['label']}):")
                print(f"  elem_reduced = {elem_reduced}")
                print(f"  elem_simplified = {elem_simplified}")
                print(f"  is zero? {elem_simplified == 0}")

                if elem_simplified == 0:
                    print(f"  -> SKIPPING (zero element)")
                    continue  # Skip zero elements
                else:
                    print(f"  -> CREATING EDGE")

                # Create edge between nodes i and j
                from_node = kron_nodes[i]
                to_node = kron_nodes[j]

                # Check if this edge existed in the original graph
                from_id_orig = id(self.kron_selected_nodes[i])
                to_id_orig = id(self.kron_selected_nodes[j])

                edge_existed_in_original = (from_id_orig, to_id_orig) in original_edges_map

                # Compare matrix elements to determine if edge changed
                # Simplify both elements and compare symbolically
                diff = simplify(elem_reduced - elem_original)
                edge_unchanged = (diff == 0)

                if edge_existed_in_original:
                    # Edge existed - check if matrix element changed
                    original_edge = original_edges_map[(from_id_orig, to_id_orig)]

                    # Determine color based on whether the matrix element changed
                    if edge_unchanged:
                        edge_color = original_edge.get('color', 'black')  # Unchanged: keep original color
                    else:
                        edge_color = 'darkseagreen'  # Modified: use darkseagreen

                    # Copy edge styling from original
                    edge = {
                        'from_node': from_node,
                        'to_node': to_node,
                        'double_line': original_edge.get('double_line', False),
                        'color': edge_color,
                        'linewidth': original_edge.get('linewidth', 1.5),
                        'linewidth_mult': original_edge.get('linewidth_mult', 1.0),
                        'label_size_mult': original_edge.get('label_size_mult', 1.0),
                        'is_self_loop': False,  # Kron edges between different nodes
                        'style': original_edge.get('style', 'single'),
                        'direction': original_edge.get('direction', 'both'),
                        'flip_labels': original_edge.get('flip_labels', False),
                        'looptheta': original_edge.get('looptheta', 30)
                    }
                else:
                    # New edge created by Kron reduction (didn't exist in original)
                    # These should definitely be styled as darkseagreen
                    edge = {
                        'from_node': from_node,
                        'to_node': to_node,
                        'double_line': False,  # New edges are single-line by default
                        'color': 'darkseagreen',
                        'linewidth': 1.5,
                        'linewidth_mult': 1.0,
                        'label_size_mult': 1.0,
                        'is_self_loop': False,  # Kron edges between different nodes
                        'style': 'single',
                        'direction': 'both',
                        'flip_labels': False,
                        'looptheta': 30
                    }

                kron_edges.append(edge)

        # Add self-loops from original graph for nodes that were kept
        print(f"\n[DEBUG] Adding self-loops from original graph...")
        for i, kept_node in enumerate(self.kron_selected_nodes):
            kept_node_id = id(kept_node)

            # Find self-loops in original graph attached to this node
            for orig_edge in self.original_graph['edges']:
                if orig_edge.get('is_self_loop', False):
                    # Check if this self-loop belongs to the kept node
                    if id(orig_edge['from_node']) == kept_node_id:
                        # Copy the self-loop, updating node references to kron_nodes
                        selfloop_copy = orig_edge.copy()
                        selfloop_copy['from_node'] = kron_nodes[i]
                        selfloop_copy['to_node'] = kron_nodes[i]
                        selfloop_copy['from_node_id'] = id(kron_nodes[i])
                        selfloop_copy['to_node_id'] = id(kron_nodes[i])
                        kron_edges.append(selfloop_copy)
                        print(f"  Added self-loop for node '{kron_nodes[i]['label']}'")

        # Store the kron_graph
        self.kron_graph = {
            'nodes': kron_nodes,
            'edges': kron_edges
        }

    def _cancel_kron_mode(self):
        """Cancel Kron reduction mode and exit"""
        if not self.kron_mode:
            return

        self.kron_mode = False
        self.kron_selected_nodes.clear()

        # Disable commit action in menu
        self.commit_kron_action.setEnabled(False)

        # If Kron reduction was never committed, hide the Kron tab
        if not hasattr(self, 'kron_graph') or self.kron_graph is None:
            if hasattr(self, 'graph_subtabs'):
                # Hide Kron tab (always index 1)
                self.graph_subtabs.setTabVisible(1, False)
                # Switch back to Original tab
                self.graph_subtabs.setCurrentIndex(0)

        print("Cancelled Kron reduction mode")
        self._update_plot()

    def _clear_kron_reduction(self):
        """Clear any existing Kron reduction and return to raw state"""
        # Exit Kron mode if currently active
        if self.kron_mode:
            self._cancel_kron_mode()

        # Clear all Kron reduction state
        self._invalidate_kron_reduction()

        # Hide the Kron tab
        if hasattr(self, 'graph_subtabs'):
            # Hide Kron tab (always index 1)
            self.graph_subtabs.setTabVisible(1, False)
            # Switch back to Original tab
            self.graph_subtabs.setCurrentIndex(0)

        print("Cleared Kron reduction")

    def _commit_kron_reduction(self):
        """Commit the Kron reduction - save reduced graph and add SymPy code to SymPy tab"""
        if not self.kron_mode:
            print("Not in Kron reduction mode")
            return

        if not self.kron_selected_nodes:
            print("No nodes selected to keep. Select at least one node to keep.")
            return

        # Save the current graph as original_graph
        # Always update to reflect the current state (in case graph was modified after previous reduction)
        self.original_graph = {
            'nodes': [n.copy() for n in self.nodes],
            'edges': [e.copy() for e in self.edges]
        }

        # Compute the Kron reduced matrix (SymPy Matrix object)
        # Note: Active graph (self.nodes/self.edges) remains UNCHANGED
        try:
            kron_latex = self.properties_panel._compute_kron_reduced_matrix_latex()
        except Exception as e:
            print("=" * 70)
            print("ERROR in _commit_kron_reduction()")
            print("=" * 70)
            print(f"Exception type: {type(e).__name__}")
            print(f"Exception message: {e}")
            print(f"Exception repr: {repr(e)}")
            print("\nFull traceback:")
            traceback.print_exc()
            print("=" * 70)
            return

        # Store the LaTeX string for persistent display
        self.kron_reduced_matrix_latex = kron_latex

        # Build the kron_graph structure from the reduced matrix
        # This creates nodes (copies of selected nodes) and NEW edges from matrix
        self._build_kron_graph()

        # Regenerate the entire SymPy code from scratch to ensure M matrix reflects current graph
        # First, temporarily clear the manual code cache so we get fresh matrix code
        old_manual_code = getattr(self.properties_panel, '_sympy_code_manual', None)
        self.properties_panel._sympy_code_manual = None

        # Generate the base matrix code for the current graph
        self.properties_panel._update_sympy_code_display()
        base_code = self.properties_panel.sympy_code_display.toPlainText()

        # Generate SymPy code for the Kron reduction
        kron_code = self._generate_kron_sympy_code()

        # Append the Kron reduction code to the base matrix code
        separator = "\n\n# " + "="*70 + "\n"
        separator += "# Kron Reduction\n"
        separator += "# " + "="*70 + "\n\n"

        new_code = base_code + separator + kron_code
        self.properties_panel.sympy_code_display.setPlainText(new_code)

        # Save count before clearing
        num_kept = len(self.kron_selected_nodes)
        num_eliminated = len(self.nodes) - num_kept

        # Store the kept nodes for persistent basis display
        self.kron_reduced_nodes = [n.copy() for n in self.kron_selected_nodes]

        # Store the updated code so it persists across updates
        self.properties_panel._sympy_code_manual = new_code

        # Exit Kron mode
        self.kron_mode = False
        self.kron_selected_nodes.clear()

        # Disable commit action in menu
        self.commit_kron_action.setEnabled(False)

        print("=" * 70)
        print("KRON REDUCTION COMMITTED")
        print("=" * 70)
        print(f"Original graph saved ({len(self.original_graph['nodes'])} nodes)")
        print(f"Kron graph built ({len(self.kron_graph['nodes'])} nodes, {len(self.kron_graph['edges'])} edges)")
        print(f"Kept {num_kept} nodes, eliminated {num_eliminated} nodes")
        print("SymPy code added to SymPy tab for debugging")
        print("=" * 70)

        # Show the Kron graph tab (always index 1, right after Original)
        self.graph_subtabs.setTabVisible(1, True)

        # Update the plot to remove selection rings (since kron_mode is now False)
        self._update_plot()

        # Render both canvases using the separate graph structures
        print(f"\n[DEBUG] About to render both canvases")
        print(f"  kron_graph has {len(self.kron_graph['nodes'])} nodes, {len(self.kron_graph['edges'])} edges")

        saved_canvas = self.canvas
        saved_nodes = self.nodes
        saved_edges = self.edges
        saved_base_xlim = self.base_xlim
        saved_base_ylim = self.base_ylim

        # Store the current base limits BEFORE rendering so Kron canvas can use them
        # This ensures both canvases start with the same coordinate system
        self.kron_original_base_xlim = self.base_xlim
        self.kron_original_base_ylim = self.base_ylim

        # Render original graph to Original canvas (first subtab)
        # self.canvas is already pointing to the original canvas
        self.nodes = self.original_graph['nodes']
        self.edges = self.original_graph['edges']
        print(f"[DEBUG] Rendering original graph: {len(self.nodes)} nodes, {len(self.edges)} edges")
        self._do_plot_render()

        # Render kron graph to Kron canvas (second subtab)
        self.canvas = self.kron_canvas
        self.nodes = self.kron_graph['nodes']
        self.edges = self.kron_graph['edges']
        # Use the same base limits as the original graph for consistent scaling
        self.base_xlim = self.kron_original_base_xlim
        self.base_ylim = self.kron_original_base_ylim
        print(f"[DEBUG] Rendering kron graph: {len(self.nodes)} nodes, {len(self.edges)} edges")
        self._do_plot_render()

        # Restore canvas and graph pointers
        self.canvas = saved_canvas
        self.nodes = saved_nodes
        self.edges = saved_edges
        self.base_xlim = saved_base_xlim
        self.base_ylim = saved_base_ylim

        # Switch to Kron tab to show the reduced result (index 1: Original=0, Kron=1)
        self.graph_subtabs.setCurrentIndex(1)

        # Also update the matrix display for the Kron-reduced matrix
        self.properties_panel._update_matrix_display()

    def _generate_kron_sympy_code(self):
        """Generate SymPy code for the current Kron reduction"""
        # Get node labels
        node_labels = []
        for node in self.nodes:
            label = node['label']
            if node.get('conj', False):
                label += '_conj'
            node_labels.append(label)

        # Determine which nodes to keep vs eliminate
        kept_indices = []
        eliminated_indices = []
        for i, node in enumerate(self.nodes):
            if node in self.kron_selected_nodes:
                kept_indices.append(i)
            else:
                eliminated_indices.append(i)

        # Build code that uses the existing M matrix
        code = "# Using the matrix M defined above\n"
        code += f"# Nodes to keep: {[node_labels[i] for i in kept_indices]}\n"
        code += f"# Nodes to eliminate: {[node_labels[i] for i in eliminated_indices]}\n\n"

        # Partition the matrix
        code += "# Partition M into blocks:\n"
        code += "# M = [M_AA  M_AB]\n"
        code += "#     [M_BA  M_BB]\n"
        code += "# where A = kept nodes, B = eliminated nodes\n\n"

        code += f"kept_indices = {kept_indices}\n"
        code += f"elim_indices = {eliminated_indices}\n\n"

        code += "# Extract blocks\n"
        code += "M_AA = Matrix([[M[i, j] for j in kept_indices] for i in kept_indices])\n"
        code += "M_AB = Matrix([[M[i, j] for j in elim_indices] for i in kept_indices])\n"
        code += "M_BA = Matrix([[M[i, j] for j in kept_indices] for i in elim_indices])\n"
        code += "M_BB = Matrix([[M[i, j] for j in elim_indices] for i in elim_indices])\n\n"

        code += "# Compute Schur complement (Kron-reduced matrix)\n"
        code += "# Using ADJ method for faster symbolic matrix inversion\n"
        code += "M_kron = M_AA - M_AB * M_BB.inv(method='ADJ') * M_BA\n\n"

        code += "# Simplify\n"
        code += "M_kron = simplify(M_kron)\n\n"

        code += "# Display\n"
        code += "print(\"Kron-reduced matrix M_kron:\")\n"
        code += "print(M_kron)\n"
        code += "print(\"\\nLaTeX:\")\n"
        code += "print(latex(M_kron))\n"

        return code

    def _toggle_edge_mode(self):
        """Enter single edge placement mode (exits after one edge)"""
        # Clear any node selections when entering edge mode
        if self.selected_nodes:
            self.selected_nodes.clear()
        self.placement_mode = 'edge'
        self.edge_mode_first_node = None
        print("Edge mode - click two nodes to connect them (single edge, exits after placement)")
        self._update_plot()

    def _toggle_edge_continuous_mode(self):
        """Toggle continuous edge mode (stays active, uses last edge settings)"""
        if self.placement_mode == 'edge_continuous':
            self.placement_mode = None
            self.edge_mode_first_node = None
            print("Exited continuous edge mode")
            self._update_plot()
        else:
            # Clear any node selections when entering edge mode
            if self.selected_nodes:
                self.selected_nodes.clear()
            self.placement_mode = 'edge_continuous'
            self.edge_mode_first_node = None
            print("Continuous edge mode - click nodes to connect them (Ctrl+E to exit)")
            self._update_plot()

    def _exit_placement_mode(self):
        """Exit any placement mode and clear selections"""
        # Clear focus from any widget (e.g., spinboxes in properties panel)
        if self.focusWidget():
            self.focusWidget().clearFocus()

        # Cancel any active dragging operations
        if self.dragging_node is not None:
            print("Cancelled node drag")
            self.dragging_node = None
            self.dragging_group = False
            self.drag_start_pos = None
            self._update_plot()
            return

        # Cancel basis ordering mode
        if self.basis_ordering_mode:
            self._cancel_basis_ordering()
            return

        # Cancel Kron reduction mode
        if self.kron_mode:
            self._cancel_kron_mode()
            return

        if self.placement_mode is not None:
            print(f"Exited {self.placement_mode} mode")
            self.placement_mode = None
            # Clear edge mode state if exiting edge mode
            if self.edge_mode_first_node is not None:
                self.edge_mode_first_node = None
            self._update_plot()
        elif self.selected_nodes or self.selected_edges:
            print(f"Cleared selection of {len(self.selected_nodes)} node(s) and {len(self.selected_edges)} edge(s)")
            self.selected_nodes.clear()
            self.selected_edges.clear()
            self._update_plot()

    def _get_selected_injection_node_id(self):
        """Get the node_id of the currently selected injection node

        Returns:
            int or None: The node_id of selected injection node, or None if no selection
        """
        if not hasattr(self, 'properties_panel') or not hasattr(self.properties_panel, 'injection_node_combo'):
            return None

        combo = self.properties_panel.injection_node_combo
        if combo.count() == 0:
            return None

        # Get node_id from combo box data
        return combo.currentData()

    def _get_default_root_node_id(self):
        """Get the default root node ID - first port node (with B_ext > 0), or first node

        Returns:
            int: The node_id to use as default root
        """
        # Try to find first port node (node with self-loop and B_ext > 0)
        for node in self.nodes:
            node_id = node['node_id']
            # Check if node has self-loop
            has_selfloop = any(
                edge.get('is_self_loop', False) and
                edge['from_node_id'] == node_id and
                edge['to_node_id'] == node_id
                for edge in self.edges
            )
            # Check if node has B_ext > 0
            node_obj_id = id(node)
            if has_selfloop and node_obj_id in self.scattering_assignments:
                B_ext = self.scattering_assignments[node_obj_id].get('B_ext', None)
                if B_ext is not None and B_ext > 0:
                    return node_id

        # If no port node found, return first node
        return self.nodes[0]['node_id'] if self.nodes else 0

    def _update_injection_node_dropdown(self):
        """Update the injection node dropdown with port nodes (nodes with self-loops).

        If a component is selected, only shows port nodes from that component.
        """
        if not hasattr(self, 'properties_panel') or not hasattr(self.properties_panel, 'injection_node_combo'):
            return

        combo = self.properties_panel.injection_node_combo

        # Block signals to avoid triggering recomputation during update
        combo.blockSignals(True)

        # Remember current selection
        current_id = combo.currentData()

        # Get the current component (if multi-component mode)
        current_component = self._get_current_component()

        # Determine which nodes to show
        if current_component is not None:
            # Filter to nodes in this component
            nodes_to_show = current_component['nodes']
            port_node_ids = current_component['port_node_ids']
        else:
            # Show all nodes
            nodes_to_show = self.nodes
            # Find all port node IDs
            port_node_ids = set()
            for edge in self.edges:
                if edge.get('is_self_loop', False):
                    port_node_ids.add(edge['from_node_id'])

        # Clear and repopulate with port nodes only (nodes that have self-loops)
        combo.clear()
        for node in nodes_to_show:
            node_id = node['node_id']
            # Only add port nodes to the injection node dropdown
            if node_id in port_node_ids:
                label = node['label']
                combo.addItem(label, node_id)

        # Restore selection if node still exists in the filtered list
        if current_id is not None:
            index = combo.findData(current_id)
            if index >= 0:
                combo.setCurrentIndex(index)

        combo.blockSignals(False)

    def _on_injection_node_changed(self):
        """Handle injection node selection change - recompute spanning tree"""
        if not self.scattering_mode:
            return

        print(f"Injection node changed to: {self.properties_panel.injection_node_combo.currentText()}")

        # Recompute spanning tree with new root
        self.scattering_tree_edges, self.scattering_chord_edges = self._compute_spanning_tree()

        # Update the scattering parameter tables to reflect new tree/chord classification
        self.properties_panel._update_scattering_node_table()
        self.properties_panel._update_scattering_edge_table()

        # Update the plot to show new tree/chord styling
        self._update_plot()

    def _update_component_dropdown(self):
        """Update the component dropdown with connected components.

        Called when entering scattering mode to populate the component selector.
        """
        if not hasattr(self, 'properties_panel') or not hasattr(self.properties_panel, 'component_combo'):
            return

        combo = self.properties_panel.component_combo
        combo.blockSignals(True)

        # Find connected components
        self.scattering_components = self._find_connected_components()

        # Clear and repopulate
        combo.clear()

        if len(self.scattering_components) <= 1:
            # Single component (connected graph) - show "All" option
            combo.addItem("All (connected)", -1)
            if self.scattering_components:
                comp = self.scattering_components[0]
                node_labels = [n['label'] for n in comp['nodes']]
                self.properties_panel.component_info_label.setText(
                    f"{len(comp['nodes'])} nodes, {len(comp['port_node_ids'])} ports"
                )
            else:
                self.properties_panel.component_info_label.setText("")
        else:
            # Multiple components (disconnected graph)
            for comp in self.scattering_components:
                # Create label showing component info
                node_labels = sorted([n['label'] for n in comp['nodes']])
                port_labels = sorted([n['label'] for n in comp['nodes'] if n['node_id'] in comp['port_node_ids']])
                label = f"Component {comp['index'] + 1}: {', '.join(node_labels[:3])}"
                if len(node_labels) > 3:
                    label += f"... ({len(node_labels)} nodes)"
                combo.addItem(label, comp['index'])

            # Update info label
            self.properties_panel.component_info_label.setText(
                f"{len(self.scattering_components)} disconnected components"
            )

        # Initialize per-component data storage
        self.scattering_per_component_data = {}
        for comp in self.scattering_components:
            self.scattering_per_component_data[comp['index']] = {
                'tree_edges': set(),
                'chord_edges': set(),
                'injection_node_id': None
            }

        combo.blockSignals(False)
        self.scattering_selected_component = combo.currentData() if combo.currentData() is not None else 0

    def _on_component_changed(self):
        """Handle component selection change - update injection dropdown and tables."""
        if not self.scattering_mode:
            return

        combo = self.properties_panel.component_combo
        selected_idx = combo.currentData()
        if selected_idx is None:
            selected_idx = 0

        print(f"Component changed to: {combo.currentText()} (index={selected_idx})")
        self.scattering_selected_component = selected_idx

        # Update injection dropdown to show only ports from this component
        self._update_injection_node_dropdown()

        # IMPORTANT: Recompute spanning tree BEFORE updating edge table
        # Edge table uses _order_edges_by_spanning_tree which needs current tree
        self.scattering_tree_edges, self.scattering_chord_edges = self._compute_spanning_tree()

        # Update parameter tables to show only this component's nodes/edges
        self.properties_panel._update_scattering_node_table()
        self.properties_panel._update_scattering_edge_table()

        # Update plot
        self._update_plot()

    def _get_current_component(self):
        """Get the currently selected component dict, or None if showing all."""
        if not self.scattering_components:
            return None

        if len(self.scattering_components) == 1:
            return self.scattering_components[0]

        idx = self.scattering_selected_component
        if idx == -1 or idx is None:
            return None  # "All" selected

        for comp in self.scattering_components:
            if comp['index'] == idx:
                return comp
        return None

    def _find_connected_components(self):
        """Find all connected components in the graph.

        Uses a union-find / BFS approach to identify disconnected subgraphs.
        Only considers non-self-loop edges for connectivity.

        Returns:
            list[dict]: List of component dicts, each containing:
                - 'node_ids': set of node_ids in the component
                - 'nodes': list of node dicts in the component
                - 'edges': list of edge dicts in the component (including self-loops)
                - 'port_node_ids': set of node_ids that have self-loops (ports)
                - 'index': component index (0-based)
        """
        if not self.nodes:
            return []

        # Build adjacency list (excluding self-loops)
        adjacency = {}
        for node in self.nodes:
            adjacency[node['node_id']] = set()

        for edge in self.edges:
            if edge.get('is_self_loop', False):
                continue
            from_id = edge['from_node_id']
            to_id = edge['to_node_id']
            if from_id in adjacency and to_id in adjacency:
                adjacency[from_id].add(to_id)
                adjacency[to_id].add(from_id)

        # Find connected components using BFS
        visited = set()
        components = []

        for node in self.nodes:
            node_id = node['node_id']
            if node_id in visited:
                continue

            # BFS to find all nodes in this component
            component_node_ids = set()
            queue = [node_id]
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                component_node_ids.add(current)
                for neighbor in adjacency.get(current, []):
                    if neighbor not in visited:
                        queue.append(neighbor)

            components.append(component_node_ids)

        # Build component dicts with full info
        result = []
        for idx, node_ids in enumerate(components):
            # Get nodes in this component
            comp_nodes = [n for n in self.nodes if n['node_id'] in node_ids]

            # Get edges in this component (both endpoints in component, or self-loop on component node)
            comp_edges = []
            for edge in self.edges:
                if edge.get('is_self_loop', False):
                    # Self-loop: include if the node is in this component
                    if edge['from_node_id'] in node_ids:
                        comp_edges.append(edge)
                else:
                    # Regular edge: include if both endpoints are in this component
                    if edge['from_node_id'] in node_ids and edge['to_node_id'] in node_ids:
                        comp_edges.append(edge)

            # Find port nodes (nodes with self-loops)
            port_node_ids = set()
            for edge in comp_edges:
                if edge.get('is_self_loop', False):
                    port_node_ids.add(edge['from_node_id'])

            result.append({
                'node_ids': node_ids,
                'nodes': comp_nodes,
                'edges': comp_edges,
                'port_node_ids': port_node_ids,
                'index': idx
            })

        # Sort by number of nodes (largest first) for consistent ordering
        result.sort(key=lambda c: len(c['node_ids']), reverse=True)
        # Re-index after sorting
        for idx, comp in enumerate(result):
            comp['index'] = idx

        print(f"Found {len(result)} connected component(s):")
        for comp in result:
            port_labels = [n['label'] for n in comp['nodes'] if n['node_id'] in comp['port_node_ids']]
            node_labels = [n['label'] for n in comp['nodes']]
            print(f"  Component {comp['index']}: {len(comp['nodes'])} nodes {node_labels}, {len(comp['port_node_ids'])} ports {port_labels}")

        return result

    def _compute_spanning_tree(self):
        """Compute spanning tree using GraphExtractor from the selected injection node.

        For disconnected graphs, computes spanning tree only for the currently selected
        component. The injection node dropdown should already be filtered to show only
        nodes from the selected component.

        Returns:
            tuple: (tree_edges, chord_edges) where each is a set of (from_node_id, to_node_id) tuples
        """
        if not self.nodes:
            return set(), set()

        # Get the current component (if in multi-component mode)
        current_component = self._get_current_component()

        # Determine which nodes/edges to use
        if current_component is not None:
            nodes_to_use = current_component['nodes']
            edges_to_use = current_component['edges']
            component_name = f"Component {current_component['index']}"
        else:
            nodes_to_use = self.nodes
            edges_to_use = self.edges
            component_name = "full graph"

        if not nodes_to_use:
            return set(), set()

        # Get root node from injection node dropdown
        root_node_id = self._get_selected_injection_node_id()
        if root_node_id is None:
            # Fallback to default root (first port node) if dropdown not ready
            root_node_id = self._get_default_root_node_id()

        # Verify root node is in the current component
        if current_component is not None:
            if root_node_id not in current_component['node_ids']:
                # Root not in component - use first port node from this component
                if current_component['port_node_ids']:
                    root_node_id = next(iter(current_component['port_node_ids']))
                else:
                    # No ports in component, use first node
                    root_node_id = current_component['nodes'][0]['node_id'] if current_component['nodes'] else None

        if root_node_id is None:
            logger.warning("No valid root node found for %s", component_name)
            return set(), set()

        # Use GraphExtractor to compute spanning tree
        from graphulator.autograph import GraphExtractor
        extractor = GraphExtractor()

        # Convert GUI nodes/edges to format expected by GraphExtractor
        gui_nodes = [{'node_id': node['node_id']} for node in nodes_to_use]
        gui_edges = [
            {
                'from_node_id': edge['from_node_id'],
                'to_node_id': edge['to_node_id'],
                'is_self_loop': edge['is_self_loop']
            }
            for edge in edges_to_use
        ]

        # Compute spanning tree with selected root
        tree_edges_nested, chord_edges_list, is_connected = extractor.compute_spanning_tree(
            gui_nodes, gui_edges, root_node_id
        )

        # Convert nested branch format back to flat set of tuples
        tree_edges = set()
        for branch in tree_edges_nested:
            for from_id, to_id in branch:
                edge_key = tuple(sorted([from_id, to_id]))
                tree_edges.add(edge_key)

        # Convert chord edges list to set of tuples
        chord_edges = set()
        for from_id, to_id in chord_edges_list:
            edge_key = tuple(sorted([from_id, to_id]))
            chord_edges.add(edge_key)

        print(f"Spanning tree computed for {component_name} (root={root_node_id}): {len(tree_edges)} tree edges, {len(chord_edges)} chord edges")
        print(f"  Tree edges: {sorted(tree_edges)}")
        print(f"  Chord edges: {sorted(chord_edges)}")

        return tree_edges, chord_edges

    def _toggle_scattering_mode(self):
        """Toggle scattering mode ON/OFF"""
        if not self.scattering_mode:
            # Enter scattering mode
            self._enter_scattering_mode()
        else:
            # Exit scattering mode
            self._exit_scattering_mode()

    def _enter_scattering_mode(self):
        """Enter scattering mode - create scattering graph and tabs"""
        if not self.nodes:
            print("Cannot enter scattering mode: No nodes in graph")
            return

        print("Entering scattering mode...")
        self.scattering_mode = True

        # Update menu checkmark
        if hasattr(self, 'scattering_action'):
            self.scattering_action.setChecked(True)

        # Clear any active selections and deactivate placement modes
        self.selected_nodes.clear()
        self.selected_edges.clear()
        self.placement_mode = None
        self.edge_placement_mode = False
        self.edge_placement_start_node = None

        # Update component dropdown (finds connected components)
        self._update_component_dropdown()

        # Connect component dropdown to handle component selection changes
        if hasattr(self, 'properties_panel') and hasattr(self.properties_panel, 'component_combo'):
            try:
                self.properties_panel.component_combo.currentIndexChanged.disconnect()
            except:
                pass
            self.properties_panel.component_combo.currentIndexChanged.connect(self._on_component_changed)

        # Update injection node dropdown with current nodes (filtered by component)
        self._update_injection_node_dropdown()

        # Connect injection node dropdown to recompute spanning tree when changed
        if hasattr(self, 'properties_panel') and hasattr(self.properties_panel, 'injection_node_combo'):
            # Disconnect any existing connections to avoid duplicates
            try:
                self.properties_panel.injection_node_combo.currentIndexChanged.disconnect()
            except:
                pass
            # Connect to trigger recomputation
            self.properties_panel.injection_node_combo.currentIndexChanged.connect(self._on_injection_node_changed)

        # Compute spanning tree (only if not already loaded from file)
        if not self.scattering_tree_edges and not self.scattering_chord_edges:
            self.scattering_tree_edges, self.scattering_chord_edges = self._compute_spanning_tree()
        else:
            print(f"Using pre-computed spanning tree from file: {len(self.scattering_tree_edges)} tree edges, {len(self.scattering_chord_edges)} chord edges")

        # Create deep copy of original graph
        self.scattering_graph = {
            'nodes': [n.copy() for n in self.nodes],
            'edges': [e.copy() for e in self.edges]
        }

        # Store base view extents (use current original graph extents)
        self.scattering_base_xlim = self.base_xlim
        self.scattering_base_ylim = self.base_ylim
        # Also store as scattering_original_base_* for pan/zoom consistency with kron
        self.scattering_original_base_xlim = self.base_xlim
        self.scattering_original_base_ylim = self.base_ylim

        # Create scattering canvas if it doesn't exist
        if not hasattr(self, 'scattering_canvas') or self.scattering_canvas is None:
            self.scattering_canvas = MplCanvas(self, width=12, height=12, dpi=100)

            # Connect mouse events for scattering canvas (same as main and kron canvases)
            self.scattering_canvas.click_signal.connect(self._on_click)
            self.scattering_canvas.release_signal.connect(self._on_release)
            self.scattering_canvas.motion_signal.connect(self._on_motion)
            self.scattering_canvas.scroll_signal.connect(self._on_scroll)

        # Create scattering graph tab (insert at index 1, between Original and Kron)
        if not hasattr(self, 'scattering_graph_tab'):
            scattering_graph_tab = QWidget()
            scattering_layout = QVBoxLayout()
            scattering_layout.setContentsMargins(0, 0, 0, 0)
            scattering_graph_tab.setLayout(scattering_layout)
            scattering_layout.addWidget(self.scattering_canvas)

            self.graph_subtabs.insertTab(2, scattering_graph_tab, "Scattering")
            self.scattering_graph_tab = scattering_graph_tab

        # Show the scattering graph tab
        self.graph_subtabs.setTabVisible(2, True)

        # Show the scattering properties tab
        if hasattr(self.properties_panel, 'scattering_tab_index'):
            self.properties_panel.tabs.setTabVisible(self.properties_panel.scattering_tab_index, True)
            # Switch to the Scattering properties tab
            self.properties_panel.tabs.setCurrentIndex(self.properties_panel.scattering_tab_index)

        # Update the scattering parameter tables in properties panel
        self.properties_panel._update_scattering_node_table()
        self.properties_panel._update_scattering_edge_table()

        # Render the scattering graph
        self._render_scattering_graph()

        # Switch to the Scattering graph tab (index 2, after Kron)
        self.graph_subtabs.setCurrentIndex(2)

        print("Scattering mode activated")

    def _refresh_scattering_view(self):
        """Refresh the scattering view - recompute spanning tree and update display

        Call this when switching to scattering tab or when graph structure changes.
        """
        if not self.scattering_mode:
            return

        print("Refreshing scattering view...")

        # Recompute spanning tree from current graph structure
        self.scattering_tree_edges, self.scattering_chord_edges = self._compute_spanning_tree()

        # Update the deep copy of the graph
        self.scattering_graph = {
            'nodes': [n.copy() for n in self.nodes],
            'edges': [e.copy() for e in self.edges]
        }

        # Update injection node dropdown in case nodes changed
        self._update_injection_node_dropdown()

        # Update the scattering parameter tables
        if hasattr(self, 'properties_panel'):
            self.properties_panel._update_scattering_node_table()
            self.properties_panel._update_scattering_edge_table()

        # Re-render the scattering graph
        self._render_scattering_graph()

        print(f"Scattering view refreshed: {len(self.scattering_tree_edges)} tree edges, {len(self.scattering_chord_edges)} chord edges")

    def _exit_scattering_mode(self):
        """Exit scattering mode - remove scattering tab but preserve state"""
        print("Exiting scattering mode...")
        self.scattering_mode = False

        # Update menu checkmark
        if hasattr(self, 'scattering_action'):
            self.scattering_action.setChecked(False)

        # Remove scattering graph tab (not just hide it)
        # This is important so Kron tab shifts back to index 1
        if hasattr(self, 'scattering_graph_tab'):
            # Find the tab index (should be 1)
            for i in range(self.graph_subtabs.count()):
                if self.graph_subtabs.widget(i) == self.scattering_graph_tab:
                    self.graph_subtabs.removeTab(i)
                    break
            # Delete the reference so it will be recreated next time
            del self.scattering_graph_tab

        # Hide scattering properties tab
        if hasattr(self.properties_panel, 'scattering_tab_index'):
            self.properties_panel.tabs.setTabVisible(self.properties_panel.scattering_tab_index, False)

        # Switch back to Original graph tab
        self.graph_subtabs.setCurrentIndex(0)

        print("Scattering mode deactivated (state preserved)")

    def _clear_scattering_data(self):
        """Clear all scattering data and exit scattering mode"""
        # Exit scattering mode if currently active
        if self.scattering_mode:
            self._exit_scattering_mode()

        # Clear all scattering state
        self.scattering_mode = False
        self.scattering_graph = None
        self.scattering_tree_edges = set()
        self.scattering_chord_edges = set()
        self.scattering_assignments = {}
        self.scattering_constraint_groups = {}
        self._next_constraint_group_id = 1
        self.scattering_base_xlim = None
        self.scattering_base_ylim = None
        self.scattering_original_base_xlim = None
        self.scattering_original_base_ylim = None
        self.scattering_selected_node = None
        self.scattering_selected_edge = None

        # Clear any computed S-parameter data (these are on self, not properties_panel)
        if hasattr(self, 'sparams_data'):
            self.sparams_data = None
        # Reset port IDs cache so checkboxes get rebuilt on next compute
        if hasattr(self, '_last_port_ids'):
            self._last_port_ids = None
        if hasattr(self, '_last_all_ports_sig'):
            self._last_all_ports_sig = None

        # Update S-parameter checkboxes (will clear them since sparams_data is None)
        self._update_sparams_checkboxes()

        # Clear S-parameter plot (sparams_canvas is on self)
        if hasattr(self, 'sparams_canvas') and self.sparams_canvas:
            self.sparams_canvas.ax.clear()
            self.sparams_canvas.ax.set_xlim(0, 1)
            self.sparams_canvas.ax.set_ylim(0, 1)
            self.sparams_canvas.draw_idle()

        # Reset frequency settings to defaults
        if hasattr(self, 'properties_panel'):
            self.properties_panel.freq_center_spin.setValue(config.FREQ_CENTER_DEFAULT)
            self.properties_panel.freq_span_spin.setValue(config.FREQ_SPAN_DEFAULT)
            self.properties_panel.freq_points_spin.setValue(config.FREQ_POINTS_DEFAULT)

        # Clear scattering canvas if it exists
        if hasattr(self, 'scattering_canvas') and self.scattering_canvas:
            self.scattering_canvas.ax.clear()
            self.scattering_canvas.ax.set_xlim(-10, 10)
            self.scattering_canvas.ax.set_ylim(-10, 10)
            self.scattering_canvas.ax.set_aspect('equal')
            self.scattering_canvas.ax.axis('off')
            self.scattering_canvas.draw_idle()

        # Update scattering action menu checkmark
        if hasattr(self, 'scattering_action'):
            self.scattering_action.setChecked(False)

        # Hide scattering properties tab
        if hasattr(self.properties_panel, 'scattering_tab_index'):
            self.properties_panel.tabs.setTabVisible(self.properties_panel.scattering_tab_index, False)

        # Switch back to Graph tab
        if hasattr(self, 'graph_subtabs'):
            self.graph_subtabs.setCurrentIndex(0)

        print("Cleared all scattering data")

    def _is_node_fully_assigned(self, node):
        """Check if a node has all required scattering parameters assigned

        Args:
            node: The node dictionary to check (may be from scattering_graph copy)

        Returns:
            bool: True if all required parameters are assigned
        """
        # Use original nodes for lookup (stored when rendering scattering graph)
        original_nodes = getattr(self, '_original_nodes_for_lookup', self.nodes)
        original_edges = getattr(self, '_original_edges_for_lookup', self.edges)

        if not original_nodes:
            return False

        # Find the corresponding original node by matching label and position
        # (scattering_graph nodes are copies with different IDs)
        original_node = None
        for orig_node in original_nodes:
            if (orig_node['label'] == node['label'] and
                orig_node['pos'] == node['pos']):
                original_node = orig_node
                break

        if not original_node:
            return False

        node_id = id(original_node)
        assignments = self.scattering_assignments.get(node_id, {})

        # Check if node has self-loop (check in original edges)
        has_selfloop = any(
            edge.get('is_self_loop', False) and edge['from_node'] == original_node
            for edge in original_edges
        ) if original_edges else False

        # Required parameters
        required_params = ['freq', 'B_int']
        if has_selfloop:
            required_params.append('B_ext')

        return all(param in assignments for param in required_params)

    def _is_edge_fully_assigned(self, edge):
        """Check if an edge has all required scattering parameters assigned

        Args:
            edge: The edge dictionary to check (may be from scattering_graph copy)

        Returns:
            bool: True if all required parameters are assigned
        """
        # Use original edges for lookup (stored when rendering scattering graph)
        original_edges = getattr(self, '_original_edges_for_lookup', self.edges)

        if not original_edges:
            return False

        # Find the corresponding original edge by matching from/to node labels
        # (scattering_graph edges are copies with different IDs)
        from_label = edge['from_node']['label']
        to_label = edge['to_node']['label']
        is_self_loop = edge.get('is_self_loop', False)

        original_edge = None
        for orig_edge in original_edges:
            orig_from_label = orig_edge['from_node']['label']
            orig_to_label = orig_edge['to_node']['label']
            orig_is_self_loop = orig_edge.get('is_self_loop', False)

            # Match by node labels and self-loop status
            if (orig_from_label == from_label and
                orig_to_label == to_label and
                orig_is_self_loop == is_self_loop):
                original_edge = orig_edge
                break

        if not original_edge:
            return False

        edge_id = id(original_edge)
        assignments = self.scattering_assignments.get(edge_id, {})

        # Check if this is a chord edge (chord f_p is computed, not assigned)
        edge_key = tuple(sorted([original_edge['from_node_id'], original_edge['to_node_id']]))
        is_chord = edge_key in self.scattering_chord_edges

        # Required parameters
        if is_chord:
            # Chords don't need f_p assigned (it's computed)
            required_params = ['rate', 'phase']
        else:
            # Tree edges need all three parameters
            required_params = ['f_p', 'rate', 'phase']

        return all(param in assignments for param in required_params)

    def _render_scattering_graph(self):
        """Render the scattering graph with spanning tree/chord styling"""
        if not self.scattering_graph:
            return

        # Temporarily switch context to scattering canvas
        saved_canvas = self.canvas
        saved_nodes = self.nodes
        saved_edges = self.edges
        saved_base_xlim = self.base_xlim
        saved_base_ylim = self.base_ylim

        # Store references to original graph for assignment lookups
        self._original_nodes_for_lookup = saved_nodes
        self._original_edges_for_lookup = saved_edges

        # Set scattering context
        self.canvas = self.scattering_canvas
        self.nodes = self.scattering_graph['nodes']
        self.edges = self.scattering_graph['edges']
        # Use scattering_original_base_xlim/ylim for pan/zoom consistency
        if hasattr(self, 'scattering_original_base_xlim'):
            self.base_xlim = self.scattering_original_base_xlim
            self.base_ylim = self.scattering_original_base_ylim
        else:
            self.base_xlim = self.scattering_base_xlim
            self.base_ylim = self.scattering_base_ylim

        # Render the plot (will use special styling for scattering mode)
        self._update_plot()

        # Save the current limits back (in case they changed during rendering)
        if hasattr(self, 'scattering_original_base_xlim'):
            self.scattering_original_base_xlim = self.base_xlim
            self.scattering_original_base_ylim = self.base_ylim

        # Restore original context
        self.canvas = saved_canvas
        self.nodes = saved_nodes
        self.edges = saved_edges
        self.base_xlim = saved_base_xlim
        self.base_ylim = saved_base_ylim

    def _validate_scattering_parameters(self):
        """Validate that all required scattering parameters are assigned

        Returns:
            tuple: (is_valid, error_message)
        """
        try:
            from graphulator.autograph import GraphExtractor

            # Build extractor with current parameters
            extractor = GraphExtractor()

            # Get root node
            root_node_id = self._get_selected_injection_node_id()
            if root_node_id is None:
                root_node_id = self._get_default_root_node_id()

            # Build nodes and edges data (similar to _update_chord_frequency_displays)
            nodes = []
            for node in self.nodes:
                node_data = {
                    'node_id': node['node_id'],
                    'label': node['label'],
                    'pos': node['pos'],
                    'conj': node.get('conj', False)
                }
                node_id_key = id(node)
                if node_id_key in self.scattering_assignments:
                    params = self.scattering_assignments[node_id_key]
                    node_data['freq'] = params.get('freq', None)
                    node_data['B_int'] = params.get('B_int', None)
                    node_data['B_ext'] = params.get('B_ext', None)
                else:
                    node_data['freq'] = None
                    node_data['B_int'] = None
                    node_data['B_ext'] = None
                nodes.append(node_data)

            edges = []
            for edge in self.edges:
                edge_data = {
                    'from_node_id': edge['from_node_id'],
                    'to_node_id': edge['to_node_id'],
                    'is_self_loop': edge['is_self_loop']
                }
                edge_id_key = id(edge)
                if edge_id_key in self.scattering_assignments:
                    params = self.scattering_assignments[edge_id_key]
                    edge_data['f_p'] = params.get('f_p', None)
                    edge_data['rate'] = params.get('rate', None)
                    edge_data['phase'] = params.get('phase', None)
                else:
                    edge_data['f_p'] = None
                    edge_data['rate'] = None
                    edge_data['phase'] = None
                edges.append(edge_data)

            # Build scattering_assignments dict
            scattering_assignments = {}
            for node in self.nodes:
                node_id_key = id(node)
                if node_id_key in self.scattering_assignments:
                    matching_node = next(n for n in nodes if n['node_id'] == node['node_id'])
                    scattering_assignments[id(matching_node)] = self.scattering_assignments[node_id_key]

            for edge in self.edges:
                edge_id_key = id(edge)
                if edge_id_key in self.scattering_assignments:
                    matching_edge = next((e for e in edges if e['from_node_id'] == edge['from_node_id'] and e['to_node_id'] == edge['to_node_id']), None)
                    if matching_edge:
                        scattering_assignments[id(matching_edge)] = self.scattering_assignments[edge_id_key]

            # Extract graph data
            tree_edges_list = [[from_id, to_id] for from_id, to_id in self.scattering_tree_edges]
            chord_edges_list = [[from_id, to_id] for from_id, to_id in self.scattering_chord_edges]

            extractor.extract_graph_data(
                nodes=nodes,
                edges=edges,
                scattering_assignments=scattering_assignments,
                frequency_settings={'start': 0.0, 'stop': 10.0, 'points': 100},
                root_node_id=root_node_id,
                precomputed_tree_edges=tree_edges_list,
                precomputed_chord_edges=chord_edges_list
            )

            # Validate
            validation = extractor.validate_scattering_assignments()
            if validation['missing_nodes'] or validation['missing_edges']:
                error_msg = extractor.get_assignment_summary()
                return False, error_msg

            return True, ""

        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def _show_sparams_tab(self):
        """Show S-params tab and compute scattering matrix"""
        # Get current index dynamically (changes when scattering tab is inserted/removed)
        sparams_tab_index = self.graph_subtabs.indexOf(self.sparams_tab)

        # Make tab visible and switch to it
        self.graph_subtabs.setTabVisible(sparams_tab_index, True)
        self.graph_subtabs.setCurrentIndex(sparams_tab_index)

        # Compute and plot S-parameters
        self._compute_and_plot_sparams()

    def _hide_sparams_tab(self):
        """Hide S-params tab"""
        # Get current index dynamically
        sparams_tab_index = self.graph_subtabs.indexOf(self.sparams_tab)
        self.graph_subtabs.setTabVisible(sparams_tab_index, False)

        # Switch back to scattering view if it's active
        if self.scattering_mode:
            self.graph_subtabs.setCurrentIndex(2)  # Scattering tab

    def _toggle_sparams_shortcut(self):
        """Toggle S-params tab via Ctrl+Shift+R shortcut

        Behavior:
        - If NOT in scattering mode: enter scattering mode and show S-params tab
          (with error overlay if assignments incomplete)
        - If IN scattering mode: toggle S-params tab visibility
        """
        if not self.scattering_mode:
            # Not in scattering mode - enter it first
            self._enter_scattering_mode()

            # Now show S-params tab (validate first)
            validation_ok, error_msg = self._validate_scattering_parameters()

            # Show the S-params tab regardless (with error if invalid)
            sparams_tab_index = self.graph_subtabs.indexOf(self.sparams_tab)
            self.graph_subtabs.setTabVisible(sparams_tab_index, True)
            self.graph_subtabs.setCurrentIndex(sparams_tab_index)

            if validation_ok:
                self._compute_and_plot_sparams()
            else:
                # Show message on canvas that assignments are incomplete
                self._show_sparams_error("Complete assignments in the\nScattering tab to compute S-parameters")

            # Update Show S button state
            if hasattr(self.properties_panel, 'show_s_button'):
                self.properties_panel.show_s_button.setChecked(True)
                self.properties_panel.show_s_button.setText("Hide S")
        else:
            # Already in scattering mode - toggle/switch S-params tab
            sparams_tab_index = self.graph_subtabs.indexOf(self.sparams_tab)
            tab_visible = self.graph_subtabs.isTabVisible(sparams_tab_index)
            current_tab_index = self.graph_subtabs.currentIndex()

            # If on Scattering graph tab (index 2), switch to S-params tab
            if current_tab_index == 2:  # Scattering graph tab
                # Show and switch to S-params tab
                validation_ok, error_msg = self._validate_scattering_parameters()

                self.graph_subtabs.setTabVisible(sparams_tab_index, True)
                self.graph_subtabs.setCurrentIndex(sparams_tab_index)

                if validation_ok:
                    self._compute_and_plot_sparams()
                else:
                    self._show_sparams_error("Complete assignments in the\nScattering tab to compute S-parameters")

                # Update Show S button state
                if hasattr(self.properties_panel, 'show_s_button'):
                    self.properties_panel.show_s_button.setChecked(True)
                    self.properties_panel.show_s_button.setText("Hide S")
            elif current_tab_index == sparams_tab_index:
                # On S-params tab - hide it and go back to Scattering graph
                self._hide_sparams_tab()

                # Update Show S button state
                if hasattr(self.properties_panel, 'show_s_button'):
                    self.properties_panel.show_s_button.setChecked(False)
                    self.properties_panel.show_s_button.setText("Show S")
            elif tab_visible:
                # S-params visible but on another tab - hide S-params tab
                self._hide_sparams_tab()

                # Update Show S button state
                if hasattr(self.properties_panel, 'show_s_button'):
                    self.properties_panel.show_s_button.setChecked(False)
                    self.properties_panel.show_s_button.setText("Show S")
            else:
                # S-params not visible - show and switch to it
                validation_ok, error_msg = self._validate_scattering_parameters()

                self.graph_subtabs.setTabVisible(sparams_tab_index, True)
                self.graph_subtabs.setCurrentIndex(sparams_tab_index)

                if validation_ok:
                    self._compute_and_plot_sparams()
                else:
                    self._show_sparams_error("Complete assignments in the\nScattering tab to compute S-parameters")

                # Update Show S button state
                if hasattr(self.properties_panel, 'show_s_button'):
                    self.properties_panel.show_s_button.setChecked(True)
                    self.properties_panel.show_s_button.setText("Hide S")

    def _compute_and_plot_sparams(self):
        """Compute S-matrix and plot selected parameters.

        For disconnected graphs with multiple components, computes S-parameters
        for each component separately and plots them together.
        """
        import numpy as np
        from graphulator.autograph import GraphExtractor, GraphScatteringMatrix

        try:
            # Get frequency settings from GUI (shared across all components)
            freq_center = self.properties_panel.freq_center_spin.value()
            freq_span = self.properties_panel.freq_span_spin.value()
            freq_points = int(self.properties_panel.freq_points_spin.value())
            freq_start = freq_center - freq_span / 2
            freq_stop = freq_center + freq_span / 2
            f_root_s = np.linspace(freq_start, freq_stop, freq_points)

            # Determine which components to compute
            if len(self.scattering_components) > 1:
                # Multiple components - compute for each
                components_to_compute = self.scattering_components
            else:
                # Single component - use full graph
                components_to_compute = [None]  # None means use full graph

            # Store results for all components
            all_sparams_data = []

            for comp_idx, component in enumerate(components_to_compute):
                comp_name = 'full graph' if component is None else f"Component {component['index']}"
                print(f"\n=== Computing S-parameters for {comp_name} ===")

                result = self._compute_sparams_for_component(
                    component, f_root_s, freq_start, freq_stop, freq_points
                )

                if result is not None:
                    result['component_index'] = component['index'] if component else 0
                    result['component_label'] = f"C{component['index']+1}" if component and len(components_to_compute) > 1 else ""
                    all_sparams_data.append(result)

            if not all_sparams_data:
                print("No valid S-parameter data computed")
                return

            # Store combined results
            self.sparams_data = {
                'frequencies': f_root_s,
                'components': all_sparams_data,
                'num_components': len(all_sparams_data)
            }

            # For backward compatibility, also store first component's data at top level
            if all_sparams_data:
                first = all_sparams_data[0]
                self.sparams_data['S'] = first['S']
                self.sparams_data['SdB'] = first['SdB']
                self.sparams_data['port_dict'] = first['port_dict']
                self.sparams_data['drive_signals'] = first['drive_signals']
                self.sparams_data['port_ids'] = first['port_ids']

            # Update checkboxes with port labels (handles multi-component)
            self._update_sparams_checkboxes()

            # Plot
            self._plot_sparams()

            print(f"S-matrix computed successfully for {len(all_sparams_data)} component(s)")

        except Exception as e:
            print(f"Error computing S-parameters: {e}")
            traceback.print_exc()
            # Show error on plot
            self._show_sparams_error(str(e))

    def _compute_sparams_for_component(self, component, f_root_s, freq_start, freq_stop, freq_points):
        """Compute S-parameters for a single component (or full graph if component is None).

        Args:
            component: Component dict from _find_connected_components(), or None for full graph
            f_root_s: Frequency array for plotting (positive)
            freq_start, freq_stop, freq_points: Frequency range settings

        Returns:
            dict with S-parameter results, or None if computation fails
        """
        import numpy as np
        from graphulator.autograph import GraphExtractor, GraphScatteringMatrix

        # Determine which nodes/edges to use
        if component is not None:
            nodes_to_use = component['nodes']
            edges_to_use = component['edges']
            comp_name = f"Component {component['index']}"
        else:
            nodes_to_use = self.nodes
            edges_to_use = self.edges
            comp_name = "full graph"

        if not nodes_to_use:
            print(f"  No nodes in {comp_name}")
            return None

        # For this component, we need to compute its own spanning tree
        # Get injection node for this component
        if component is not None and component['port_node_ids']:
            root_node_id = next(iter(component['port_node_ids']))
        else:
            root_node_id = self._get_selected_injection_node_id()
            if root_node_id is None:
                root_node_id = self._get_default_root_node_id()

        # Build nodes data
        nodes = []
        for node in nodes_to_use:
            node_data = {
                'node_id': node['node_id'],
                'label': node['label'],
                'pos': node['pos'],
                'conj': node.get('conj', False)
            }
            node_id_key = id(node)
            if node_id_key in self.scattering_assignments:
                params = self.scattering_assignments[node_id_key]
                node_data['freq'] = params.get('freq', None)
                node_data['B_int'] = params.get('B_int', None)
                node_data['B_ext'] = params.get('B_ext', None)
            else:
                node_data['freq'] = None
                node_data['B_int'] = None
                node_data['B_ext'] = None
            nodes.append(node_data)

        # Build edges data
        edges = []
        for edge in edges_to_use:
            edge_data = {
                'from_node_id': edge['from_node_id'],
                'to_node_id': edge['to_node_id'],
                'is_self_loop': edge['is_self_loop']
            }
            edge_id_key = id(edge)
            if edge_id_key in self.scattering_assignments:
                params = self.scattering_assignments[edge_id_key]
                edge_data['f_p'] = params.get('f_p', None)
                edge_data['rate'] = params.get('rate', None)
                edge_data['phase'] = params.get('phase', None)
            else:
                edge_data['f_p'] = None
                edge_data['rate'] = None
                edge_data['phase'] = None
            edges.append(edge_data)

        # Build scattering_assignments dict for this component
        scattering_assignments = {}
        for node in nodes_to_use:
            node_id_key = id(node)
            if node_id_key in self.scattering_assignments:
                matching_node = next((n for n in nodes if n['node_id'] == node['node_id']), None)
                if matching_node:
                    scattering_assignments[id(matching_node)] = self.scattering_assignments[node_id_key]

        for edge in edges_to_use:
            edge_id_key = id(edge)
            if edge_id_key in self.scattering_assignments:
                matching_edge = next((e for e in edges if e['from_node_id'] == edge['from_node_id'] and e['to_node_id'] == edge['to_node_id']), None)
                if matching_edge:
                    scattering_assignments[id(matching_edge)] = self.scattering_assignments[edge_id_key]

        # Compute spanning tree for this component
        extractor = GraphExtractor()
        gui_nodes = [{'node_id': node['node_id']} for node in nodes_to_use]
        gui_edges = [
            {
                'from_node_id': edge['from_node_id'],
                'to_node_id': edge['to_node_id'],
                'is_self_loop': edge['is_self_loop']
            }
            for edge in edges_to_use
        ]

        tree_edges_nested, chord_edges_list, is_connected = extractor.compute_spanning_tree(
            gui_nodes, gui_edges, root_node_id
        )

        # Convert to list format for extractor
        tree_edges_list = []
        for branch in tree_edges_nested:
            for from_id, to_id in branch:
                tree_edges_list.append([from_id, to_id])

        try:
            extractor.extract_graph_data(
                nodes=nodes,
                edges=edges,
                scattering_assignments=scattering_assignments,
                frequency_settings={'start': freq_start, 'stop': freq_stop, 'points': freq_points},
                root_node_id=root_node_id,
                precomputed_tree_edges=tree_edges_list,
                precomputed_chord_edges=chord_edges_list
            )

            # Check if injection node is conjugated
            root_node = next((n for n in nodes if n['node_id'] == root_node_id), None)
            f_calc = f_root_s
            if root_node and root_node.get('conj', False):
                f_calc = -f_root_s
                print(f"  {comp_name}: Injection node is conjugated - using negative frequencies")

            # Compute S-matrix
            scattering_calc = GraphScatteringMatrix(extractor, f_calc)

            print(f"  {comp_name}: {len(scattering_calc.port_dict)} ports computed")

            # Build enriched port_dict with labels for checkbox/plot code
            # Original port_dict: {node_id: B_ext}
            # Enriched: {node_id: {'B_ext': B_ext, 'label': label, 'conj': bool}}
            enriched_port_dict = {}
            for port_id, B_ext in scattering_calc.port_dict.items():
                port_node = next((n for n in nodes_to_use if n['node_id'] == port_id), None)
                label = port_node['label'] if port_node else str(port_id)
                conj = port_node.get('conj', False) if port_node else False
                enriched_port_dict[port_id] = {'B_ext': B_ext, 'label': label, 'conj': conj}

            return {
                'S': scattering_calc.S,
                'SdB': scattering_calc.SdB,
                'port_dict': enriched_port_dict,
                'drive_signals': scattering_calc.drive_signals,
                'port_ids': sorted(scattering_calc.port_dict.keys())
            }

        except Exception as e:
            print(f"  {comp_name}: Error computing S-parameters: {e}")
            traceback.print_exc()
            return None

    def _update_sparams_checkboxes(self):
        """Update checkboxes for S-parameter selection.

        For multi-component graphs, creates checkboxes for ALL components' ports
        with component labels (e.g., "C1: S_ab", "C2: S_cd").
        """

        # Check if sparams_data exists and is valid
        if not hasattr(self, 'sparams_data') or self.sparams_data is None:
            # Clear existing checkboxes if they exist
            if hasattr(self, 'sparams_checkbox_layout'):
                while self.sparams_checkbox_layout.count():
                    item = self.sparams_checkbox_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
            if hasattr(self, 'sparams_checkboxes'):
                self.sparams_checkboxes = {}
            return

        # Get components list (or create single-element list for backward compatibility)
        components = self.sparams_data.get('components', [])
        if not components:
            # Backward compatibility: create single component from top-level data
            components = [{
                'port_dict': self.sparams_data.get('port_dict', {}),
                'component_label': '',
                'component_index': 0,
                'S': self.sparams_data.get('S'),
                'SdB': self.sparams_data.get('SdB'),
                'port_ids': self.sparams_data.get('port_ids', []),
                'drive_signals': self.sparams_data.get('drive_signals', {})
            }]

        num_components = len(components)

        # Build a signature of all ports across all components for change detection
        all_ports_sig = []
        for comp in components:
            port_ids = sorted(comp.get('port_dict', {}).keys())
            all_ports_sig.append((comp.get('component_index', 0), tuple(port_ids)))
        all_ports_sig = tuple(all_ports_sig)

        # Check if port configuration has changed - if not, no need to rebuild checkboxes
        if hasattr(self, '_last_all_ports_sig') and self._last_all_ports_sig == all_ports_sig:
            # Port configuration unchanged, checkboxes are still valid
            return

        # Port configuration changed - save this for future comparisons
        self._last_all_ports_sig = all_ports_sig

        # Save current checkbox states by full S-parameter name (including component label)
        saved_states = {}
        if hasattr(self, 'sparams_checkboxes') and self.sparams_checkboxes:
            for key, checkbox in self.sparams_checkboxes.items():
                try:
                    sparam_name = checkbox.text()
                    saved_states[sparam_name] = checkbox.isChecked()
                except (IndexError, StopIteration):
                    continue

        # Clear existing checkboxes
        while self.sparams_checkbox_layout.count():
            item = self.sparams_checkbox_layout.takeAt(0)
            if item.widget():
                widget = item.widget()
                widget.setParent(None)
                widget.deleteLater()

        # Create checkboxes for ALL components
        # Key format: (component_index, j_idx, k_idx)
        self.sparams_checkboxes = {}

        for comp_idx, comp_data in enumerate(components):
            port_dict = comp_data.get('port_dict', {})
            port_ids = sorted(port_dict.keys())
            comp_label = comp_data.get('component_label', '')

            if not port_ids:
                continue

            # Add component separator label if multiple components
            if num_components > 1:
                comp_header = QLabel(f"--- {comp_label or f'Component {comp_idx+1}'} ---")
                comp_header.setStyleSheet("font-weight: bold; color: #888; margin-top: 5px;")
                self.sparams_checkbox_layout.addWidget(comp_header)

            # Create checkboxes for this component in column-major order
            for k_idx, k in enumerate(port_ids):
                for j_idx, j in enumerate(port_ids):
                    # Find node labels and conjugation status from port_dict
                    j_info = port_dict.get(j, {})
                    k_info = port_dict.get(k, {})
                    j_label = j_info.get('label', str(j))
                    k_label = k_info.get('label', str(k))
                    # Add * suffix for conjugated nodes
                    if j_info.get('conj', False):
                        j_label += '*'
                    if k_info.get('conj', False):
                        k_label += '*'

                    # Create checkbox with optional component prefix
                    if num_components > 1 and comp_label:
                        sparam_name = f"{comp_label}: S_{j_label}{k_label}"
                    else:
                        sparam_name = f"S_{j_label}{k_label}"

                    checkbox = QCheckBox(sparam_name)

                    # Restore saved state if available, otherwise default to checked
                    if sparam_name in saved_states:
                        checkbox.setChecked(saved_states[sparam_name])
                    else:
                        checkbox.setChecked(True)  # All checked initially

                    checkbox.stateChanged.connect(self._on_sparams_checkbox_changed)
                    # Store component index and port indices as properties
                    checkbox.setProperty('component_index', comp_data.get('component_index', comp_idx))
                    checkbox.setProperty('port_indices', (j_idx, k_idx))

                    self.sparams_checkbox_layout.addWidget(checkbox)
                    # Use compound key: (component_index, j_idx, k_idx)
                    self.sparams_checkboxes[(comp_data.get('component_index', comp_idx), j_idx, k_idx)] = checkbox

        # Apply pending S-parameter settings from loaded file
        if hasattr(self, '_pending_sparams_settings') and self._pending_sparams_settings:
            settings = self._pending_sparams_settings

            # Apply checkbox selections
            # Support both old format (j_idx, k_idx) and new format (comp_idx, j_idx, k_idx)
            if "selected" in settings:
                selected_set = set()
                for item in settings["selected"]:
                    if len(item) == 2:
                        # Old format: (j_idx, k_idx) - assume component 0
                        selected_set.add((0, item[0], item[1]))
                    elif len(item) == 3:
                        # New format: (comp_idx, j_idx, k_idx)
                        selected_set.add(tuple(item))

                for key, checkbox in self.sparams_checkboxes.items():
                    checkbox.blockSignals(True)
                    checkbox.setChecked(key in selected_set)
                    checkbox.blockSignals(False)

            # Apply autoscale settings
            if "x_autoscale" in settings:
                self.sparams_x_autoscale.setChecked(settings["x_autoscale"])
            if "y_autoscale" in settings:
                self.sparams_y_autoscale.setChecked(settings["y_autoscale"])

            # Apply axis limits (set spinbox values)
            if "xlim" in settings and not settings.get("x_autoscale", True):
                xlim = settings["xlim"]
                self.sparams_xmin_spin.setValue(xlim[0])
                self.sparams_xmax_spin.setValue(xlim[1])
            if "ylim" in settings and not settings.get("y_autoscale", True):
                ylim = settings["ylim"]
                self.sparams_ymin_spin.setValue(ylim[0])
                self.sparams_ymax_spin.setValue(ylim[1])

            # Apply conjugate freqs setting
            if "conjugate_freqs" in settings:
                self.sparams_conjugate_freqs.setChecked(settings["conjugate_freqs"])
                # Update button text to match state
                if settings["conjugate_freqs"]:
                    self.sparams_conjugate_freqs.setText("Unconjugate Freqs")
                else:
                    self.sparams_conjugate_freqs.setText("Conjugate Freqs")

            # Apply plot mode setting
            if "plot_mode" in settings:
                plot_mode = settings["plot_mode"]
                self.sparams_mode_db.setChecked(plot_mode == 'dB')
                self.sparams_mode_phase.setChecked(plot_mode == 'phase')
                self.sparams_mode_both.setChecked(plot_mode == 'both')
                # Update axis controls visibility
                self._update_sparams_axis_controls_visibility()

            # Apply phase autoscale setting
            if "phase_autoscale" in settings:
                self.sparams_phase_autoscale.setChecked(settings["phase_autoscale"])

            # Apply phase y-limits
            if "phase_ylim" in settings and not settings.get("phase_autoscale", True):
                phase_ylim = settings["phase_ylim"]
                self.sparams_phase_min_spin.setValue(phase_ylim[0])
                self.sparams_phase_max_spin.setValue(phase_ylim[1])

            # Apply phase unwrap setting
            if "phase_unwrap" in settings:
                self.sparams_phase_unwrap.setChecked(settings["phase_unwrap"])

            # Clear pending settings after applying
            self._pending_sparams_settings = None
            print("Applied pending S-parameter plot settings")

    def _on_sparams_checkbox_changed(self):
        """Handle checkbox state changes - replot"""
        self._plot_sparams()

    def _on_sparams_select_all(self):
        """Select all S-parameter checkboxes"""
        if hasattr(self, 'sparams_checkboxes'):
            for checkbox in self.sparams_checkboxes.values():
                checkbox.setChecked(True)

    def _on_sparams_unselect_all(self):
        """Unselect all S-parameter checkboxes"""
        if hasattr(self, 'sparams_checkboxes'):
            for checkbox in self.sparams_checkboxes.values():
                checkbox.setChecked(False)

    def _plot_sparams(self):
        """Plot selected S-parameters (supports dB, phase, and both modes).

        For multi-component graphs, plots S-parameters from ALL components
        with appropriate labels (e.g., "C1: S_ab", "C2: S_cd").
        """
        if not hasattr(self, 'sparams_data') or self.sparams_data is None:
            return

        # Get plot mode
        plot_mode = self._get_sparams_plot_mode()

        # Get color palette from SPARAMS_TRACE_COLORS (independent from node colors)
        colors = config.SPARAMS_TRACE_COLORS

        # Get seaborn talk context font sizes
        talk_context = sns.plotting_context('talk')
        font_scale = talk_context['font.size'] / 10  # Base is 10, talk is typically 14

        # Clear figure and set up axes based on mode
        self.sparams_canvas.fig.clear()

        if plot_mode == 'both':
            # Create two subplots with shared x-axis
            self.sparams_ax_db = self.sparams_canvas.fig.add_subplot(2, 1, 1)
            self.sparams_ax_phase = self.sparams_canvas.fig.add_subplot(2, 1, 2, sharex=self.sparams_ax_db)
            self.sparams_canvas.ax = self.sparams_ax_db  # Primary axis for compatibility
            axes_list = [self.sparams_ax_db, self.sparams_ax_phase]
        else:
            # Single axis
            self.sparams_canvas.ax = self.sparams_canvas.fig.add_subplot(1, 1, 1)
            self.sparams_ax_db = self.sparams_canvas.ax if plot_mode == 'dB' else None
            self.sparams_ax_phase = self.sparams_canvas.ax if plot_mode == 'phase' else None
            axes_list = [self.sparams_canvas.ax]

        # Apply seaborn darkgrid style to all axes
        for ax in axes_list:
            ax.set_facecolor(config.SPARAMS_PLOT_BACKGROUND_COLOR)
        self.sparams_canvas.fig.patch.set_facecolor(config.SPARAMS_PLOT_FIGURE_BACKGROUND)

        # Get frequencies (shared across all components)
        frequencies = self.sparams_data['frequencies']

        # Get component list for multi-component support
        components = self.sparams_data.get('components', [])
        if not components:
            # Backward compatibility: create single component from top-level data
            components = [{
                'port_dict': self.sparams_data.get('port_dict', {}),
                'component_label': '',
                'component_index': 0,
                'S': self.sparams_data.get('S'),
                'SdB': self.sparams_data.get('SdB'),
                'port_ids': self.sparams_data.get('port_ids', []),
                'drive_signals': self.sparams_data.get('drive_signals', {})
            }]

        num_components = len(components)

        # Build component lookup by index
        comp_by_index = {comp.get('component_index', i): comp for i, comp in enumerate(components)}

        # Apply conjugate frequency transformation if toggle is active
        conjugate_mode = self.sparams_conjugate_freqs.isChecked()
        if conjugate_mode:
            frequencies = -frequencies[::-1]

        # Use rc_context to set mathtext font for subscripts (sans-serif)
        import matplotlib as mpl

        # Apply sans-serif mathtext settings for entire plot
        # Use stixsans which is explicitly sans-serif
        with mpl.rc_context({'mathtext.fontset': 'stixsans',
                            'mathtext.default': 'regular'}):

            # Plot each selected S-parameter with fixed colors based on matrix position
            # Each S-parameter gets a consistent color regardless of which traces are shown
            for key, checkbox in self.sparams_checkboxes.items():
                if checkbox.isChecked():
                    try:
                        # Parse compound key: (comp_idx, j_idx, k_idx)
                        if len(key) == 3:
                            comp_idx, j_idx, k_idx = key
                        else:
                            # Old format (j_idx, k_idx) - assume component 0
                            j_idx, k_idx = key
                            comp_idx = 0

                        # Get component data
                        comp_data = comp_by_index.get(comp_idx)
                        if comp_data is None:
                            continue

                        S_complex = comp_data.get('S')
                        SdB = comp_data.get('SdB')
                        port_dict = comp_data.get('port_dict', {})
                        port_ids = sorted(port_dict.keys())
                        comp_label = comp_data.get('component_label', '')

                        if S_complex is None or SdB is None:
                            continue

                        # Check if indices are valid for this component
                        num_ports = len(port_ids)
                        if j_idx >= num_ports or k_idx >= num_ports:
                            continue

                        # Compute phase from complex S-matrix
                        S_phase_rad = np.angle(S_complex)
                        if self.sparams_phase_unwrap.isChecked():
                            S_phase_rad_unwrapped = np.zeros_like(S_phase_rad)
                            for j in range(S_phase_rad.shape[1]):
                                for k in range(S_phase_rad.shape[2]):
                                    S_phase_rad_unwrapped[:, j, k] = np.unwrap(S_phase_rad[:, j, k])
                            S_phase_deg = np.degrees(S_phase_rad_unwrapped)
                        else:
                            S_phase_deg = np.degrees(S_phase_rad)

                        # Apply conjugate transformation to data if active
                        if conjugate_mode:
                            SdB = SdB[::-1, :, :]
                            S_phase_deg = S_phase_deg[::-1, :, :]

                        # Get port labels and conjugation status from port_dict
                        j_port_id = port_ids[j_idx]
                        k_port_id = port_ids[k_idx]
                        j_info = port_dict.get(j_port_id, {})
                        k_info = port_dict.get(k_port_id, {})
                        j_label = j_info.get('label', str(j_port_id))
                        k_label = k_info.get('label', str(k_port_id))
                        # Add * suffix for conjugated nodes
                        if j_info.get('conj', False):
                            j_label += '*'
                        if k_info.get('conj', False):
                            k_label += '*'

                        # Calculate fixed color index based on S-parameter position in matrix
                        # Column-major order: S_AA=0, S_BA=1, S_AB=2, S_BB=3, etc.
                        color_idx = k_idx * num_ports + j_idx
                        trace_color = colors[color_idx % len(colors)]

                        # Build label with optional component prefix
                        if num_components > 1 and comp_label:
                            label_str = f'{comp_label}: S$_{{{j_label}{k_label}}}$'
                        else:
                            label_str = f'S$_{{{j_label}{k_label}}}$'

                        # Plot based on mode
                        if plot_mode == 'dB':
                            self.sparams_canvas.ax.plot(
                                frequencies, SdB[:, j_idx, k_idx],
                                label=label_str, color=trace_color,
                                linewidth=config.SPARAMS_PLOT_LINEWIDTH
                            )
                        elif plot_mode == 'phase':
                            self.sparams_canvas.ax.plot(
                                frequencies, S_phase_deg[:, j_idx, k_idx],
                                label=label_str, color=trace_color,
                                linewidth=config.SPARAMS_PLOT_LINEWIDTH
                            )
                        else:  # 'both'
                            self.sparams_ax_db.plot(
                                frequencies, SdB[:, j_idx, k_idx],
                                label=label_str, color=trace_color,
                                linewidth=config.SPARAMS_PLOT_LINEWIDTH
                            )
                            self.sparams_ax_phase.plot(
                                frequencies, S_phase_deg[:, j_idx, k_idx],
                                label=label_str, color=trace_color,
                                linewidth=config.SPARAMS_PLOT_LINEWIDTH
                            )

                    except (IndexError, StopIteration, KeyError) as e:
                        # Stale checkbox or data mismatch, skip this S-parameter
                        logger.warning("Skipping S-parameter plot for key %s: %s", key, e)
                        continue

            # Set y-labels and styling
            ylabel_fontsize = talk_context['axes.labelsize'] * config.SPARAMS_FONT_SCALE
            tick_fontsize = talk_context['xtick.labelsize'] * config.SPARAMS_FONT_SCALE
            legend_fontsize = talk_context['legend.fontsize'] * config.SPARAMS_FONT_SCALE * config.SPARAMS_LEGEND_FONTSIZE_SCALE

            if plot_mode == 'dB':
                ylabel = self.sparams_canvas.ax.set_ylabel('S [dB]', fontsize=ylabel_fontsize)
                ylabel.set_fontfamily('sans-serif')
            elif plot_mode == 'phase':
                ylabel = self.sparams_canvas.ax.set_ylabel('Phase [deg]', fontsize=ylabel_fontsize)
                ylabel.set_fontfamily('sans-serif')
            else:  # 'both'
                ylabel_db = self.sparams_ax_db.set_ylabel('S [dB]', fontsize=ylabel_fontsize)
                ylabel_db.set_fontfamily('sans-serif')
                ylabel_phase = self.sparams_ax_phase.set_ylabel('Phase [deg]', fontsize=ylabel_fontsize)
                ylabel_phase.set_fontfamily('sans-serif')

            # Set tick label sizes and font for all axes
            for ax in axes_list:
                ax.tick_params(labelsize=tick_fontsize)
                for label in ax.get_xticklabels() + ax.get_yticklabels():
                    label.set_fontfamily('sans-serif')

            # Add legend to appropriate axis/axes
            if plot_mode == 'both':
                # Only show legend on dB plot to avoid duplication
                legend = self.sparams_ax_db.legend(fontsize=legend_fontsize, loc='lower left')
            else:
                legend = self.sparams_canvas.ax.legend(fontsize=legend_fontsize, loc='lower left')
            for text in legend.get_texts():
                text.set_fontfamily('sans-serif')

        # Apply darkgrid style: white grid lines on gray background
        for ax in axes_list:
            ax.grid(True, which='major', color=config.SPARAMS_PLOT_GRID_COLOR, linestyle='-',
                   linewidth=talk_context['grid.linewidth'] * config.SPARAMS_PLOT_GRID_LINEWIDTH_SCALE)
            ax.set_axisbelow(True)  # Grid behind plot elements
            # Hide spines (remove plot frame)
            for spine in ax.spines.values():
                spine.set_visible(False)

        # Apply axis limits
        # X-axis limits (applies to all axes due to sharex in 'both' mode)
        if self.sparams_x_autoscale.isChecked():
            self.sparams_canvas.ax.set_xlim(frequencies.min(), frequencies.max())
        else:
            self.sparams_canvas.ax.set_xlim(self.sparams_xmin_spin.value(), self.sparams_xmax_spin.value())

        # Y-axis limits for dB
        if plot_mode in ('dB', 'both') and not self.sparams_y_autoscale.isChecked():
            ax_db = self.sparams_ax_db if plot_mode == 'both' else self.sparams_canvas.ax
            ax_db.set_ylim(self.sparams_ymin_spin.value(), self.sparams_ymax_spin.value())

        # Y-axis limits for phase
        if plot_mode in ('phase', 'both') and not self.sparams_phase_autoscale.isChecked():
            ax_phase = self.sparams_ax_phase if plot_mode == 'both' else self.sparams_canvas.ax
            ax_phase.set_ylim(self.sparams_phase_min_spin.value(), self.sparams_phase_max_spin.value())

        # Determine bottom axis for x-axis labels (phase axis in 'both' mode)
        if plot_mode == 'both':
            bottom_ax = self.sparams_ax_phase
            # In 'both' mode, hide x-tick labels on top axis
            self.sparams_ax_db.tick_params(axis='x', labelbottom=False)
        else:
            bottom_ax = self.sparams_canvas.ax

        # Add driven frequency tick labels for each displayed port
        # NOTE: For multi-component graphs, skip complex port-specific frequency labeling
        # (would need significant rework to handle different components' port frequencies)
        num_freq_rows = 0  # Track number of frequency label rows

        # Only do port-specific labeling for single-component graphs
        if num_components == 1 and 'drive_signals' in self.sparams_data and 'port_ids' in self.sparams_data:
            drive_signals = self.sparams_data['drive_signals']
            port_ids_all = self.sparams_data['port_ids']

            # Determine which ports need x-tick labels and whether to show port labels
            # Rules:
            # - S_jj (diagonal): need port j, NO port label
            # - S_jk (off-diagonal, j!=k): need BOTH ports j and k, WITH port labels
            displayed_ports = set()
            has_offdiagonal = False

            for key, checkbox in self.sparams_checkboxes.items():
                if checkbox.isChecked():
                    # Parse compound key: (comp_idx, j_idx, k_idx) or old (j_idx, k_idx)
                    if len(key) == 3:
                        comp_idx, j_idx, k_idx = key
                    else:
                        j_idx, k_idx = key
                        comp_idx = 0

                    if j_idx == k_idx:
                        # Diagonal: need port j only
                        if j_idx < len(port_ids_all):
                            displayed_ports.add(j_idx)
                    else:
                        # Off-diagonal: need both ports j and k
                        has_offdiagonal = True
                        if j_idx < len(port_ids_all):
                            displayed_ports.add(j_idx)
                        if k_idx < len(port_ids_all):
                            displayed_ports.add(k_idx)

            # Group ports by unique drive_signals arrays
            if displayed_ports:
                from collections import defaultdict

                # Map from tuple(drive_signals) -> list of (port_id, port_label)
                freq_groups = defaultdict(list)

                for port_idx in displayed_ports:
                    port_id = port_ids_all[port_idx]
                    port_node = next((n for n in self.nodes if n['node_id'] == port_id), None)

                    if port_node and port_id in drive_signals:
                        port_label = port_node['label']
                        driven_freqs = drive_signals[port_id]
                        # Apply conjugate transformation if active
                        if conjugate_mode:
                            driven_freqs = -driven_freqs[::-1]
                        # Use tuple as key for grouping
                        freq_key = tuple(driven_freqs)
                        freq_groups[freq_key].append((port_id, port_label))

                # Show extra rows with port labels if:
                # 1. Any off-diagonal S_jk is checked, OR
                # 2. Multiple diagonal S_jj with different frequency arrays
                # Use original x-axis only if: no off-diagonal AND single/no frequency group
                if not has_offdiagonal and len(freq_groups) <= 1:
                    # Only diagonal elements with same/single frequency - use original x-axis
                    num_freq_rows = 0
                    # Disable tight_layout to allow manual margin control
                    self.sparams_canvas.fig.set_tight_layout(False)
                    self.sparams_canvas.fig.subplots_adjust(
                        bottom=config.SPARAMS_MARGIN_BOTTOM_SINGLE,
                        left=config.SPARAMS_MARGIN_LEFT_SINGLE
                    )
                    # Ensure original tick labels are visible (may have been hidden from previous render)
                    bottom_ax.tick_params(axis='x', labelbottom=True)

                    # Translate tick labels to match the port's drive_signals frequency
                    if len(freq_groups) == 1:
                        # Get the single frequency group
                        freq_key = list(freq_groups.keys())[0]
                        driven_freqs = np.array(freq_key)
                        freq_offset = driven_freqs[0] - frequencies[0]

                        if abs(freq_offset) > 1e-10:  # Only relabel if there's an actual offset
                            # Get current tick positions and formatter
                            tick_locs = bottom_ax.get_xticks()
                            xlim = bottom_ax.get_xlim()
                            visible_ticks = [t for t in tick_locs if xlim[0] <= t <= xlim[1]]

                            # Create new labels with translated frequencies
                            formatter = bottom_ax.xaxis.get_major_formatter()
                            new_labels = [formatter(t + freq_offset) for t in visible_ticks]

                            # Set the new tick labels
                            bottom_ax.set_xticks(visible_ticks)
                            bottom_ax.set_xticklabels(new_labels)

                    # Set font family to match the rest of the plot
                    for label in bottom_ax.get_xticklabels():
                        label.set_fontfamily('sans-serif')
                else:
                    # Multiple unique frequency arrays - show extra rows
                    # Limit to 6 unique frequency arrays
                    unique_freq_arrays = list(freq_groups.items())[:6]
                    num_freq_rows = len(unique_freq_arrays)

                    # Disable tight_layout to allow manual margin control
                    self.sparams_canvas.fig.set_tight_layout(False)

                    # Adjust margins: left for port labels, bottom for frequency rows
                    bottom_margin = (config.SPARAMS_MARGIN_BOTTOM_BASE +
                                     num_freq_rows * config.SPARAMS_MARGIN_BOTTOM_PER_ROW +
                                     config.SPARAMS_MARGIN_BOTTOM_XLABEL)
                    left_margin = config.SPARAMS_MARGIN_LEFT_MULTI

                    self.sparams_canvas.fig.subplots_adjust(bottom=bottom_margin, left=left_margin)

                    # Hide the original x-axis tick labels (we're replacing them with port-specific ones)
                    bottom_ax.tick_params(axis='x', labelbottom=False)

                    # Get main axis tick positions and filter to visible range
                    xlim = bottom_ax.get_xlim()
                    all_tick_locs = bottom_ax.get_xticks()
                    main_ax_tick_locs = [t for t in all_tick_locs if xlim[0] <= t <= xlim[1]]
                    main_ax_formatter = bottom_ax.xaxis.get_major_formatter()

                    # Get main frequency array for offset calculation
                    main_freqs = frequencies

                    # Add tick labels for each unique frequency group
                    for row_idx, (freq_key, port_list) in enumerate(unique_freq_arrays):
                        driven_freqs = np.array(freq_key)

                        # Create port label string
                        port_labels_str = ', '.join([label for _, label in port_list])
                        if len(port_list) == 1:
                            label_text = f'Port {port_labels_str}'
                        else:
                            label_text = f'Ports {port_labels_str}'

                        # Position below the x-axis (in axes coordinates for y)
                        y_pos = config.SPARAMS_FREQ_ROW_Y_START - (row_idx * config.SPARAMS_FREQ_ROW_Y_SPACING)

                        # Calculate frequency offset: driven_freqs = main_freqs + offset
                        freq_offset = driven_freqs[0] - main_freqs[0]

                        # Add port label on the left
                        port_label_fontsize = talk_context['axes.labelsize'] * 0.80 * config.SPARAMS_FONT_SCALE
                        bottom_ax.text(
                            config.SPARAMS_PORT_LABEL_X, y_pos,
                            label_text,
                            transform=bottom_ax.transAxes,
                            fontsize=port_label_fontsize,
                            verticalalignment='center',
                            horizontalalignment='right',
                            fontfamily='sans-serif',
                            fontweight='bold',
                            clip_on=False
                        )

                        # Add tick labels using same positions as main axis, but translated values
                        freq_tick_fontsize = talk_context['xtick.labelsize'] * config.SPARAMS_FONT_SCALE
                        for tick_pos in main_ax_tick_locs:
                            # Translate the tick value by the frequency offset
                            translated_freq = tick_pos + freq_offset

                            # Format using main axis formatter
                            freq_label = main_ax_formatter(translated_freq)

                            bottom_ax.text(
                                tick_pos, y_pos,
                                freq_label,
                                transform=bottom_ax.get_xaxis_transform(),
                                fontsize=freq_tick_fontsize,
                                verticalalignment='center',
                                horizontalalignment='center',
                                fontfamily='sans-serif',
                                clip_on=False
                            )
            else:
                # No labels to show, reset to default margins
                self.sparams_canvas.fig.set_tight_layout(False)
                self.sparams_canvas.fig.subplots_adjust(
                    bottom=config.SPARAMS_MARGIN_BOTTOM_SINGLE,
                    left=config.SPARAMS_MARGIN_LEFT_SINGLE
                )
                bottom_ax.tick_params(axis='x', labelbottom=True)
                for label in bottom_ax.get_xticklabels():
                    label.set_fontfamily('sans-serif')
        else:
            # No drive signals data, use default margins
            self.sparams_canvas.fig.set_tight_layout(False)
            bottom_ax.tick_params(axis='x', labelbottom=True)
            self.sparams_canvas.fig.subplots_adjust(
                bottom=config.SPARAMS_MARGIN_BOTTOM_SINGLE,
                left=config.SPARAMS_MARGIN_LEFT_SINGLE
            )
            for label in bottom_ax.get_xticklabels():
                label.set_fontfamily('sans-serif')

        # Add x-axis label below all frequency rows
        if num_freq_rows > 0:
            # Position x-label below all frequency rows
            xlabel_y_pos = (config.SPARAMS_FREQ_ROW_Y_START -
                           (num_freq_rows * config.SPARAMS_FREQ_ROW_Y_SPACING) +
                           config.SPARAMS_XLABEL_Y_OFFSET)
        else:
            # Standard position
            xlabel_y_pos = config.SPARAMS_FREQ_ROW_Y_START

        xlabel_fontsize = talk_context['axes.labelsize'] * config.SPARAMS_FONT_SCALE
        xlabel = bottom_ax.set_xlabel('f [a.u.]', fontsize=xlabel_fontsize)
        xlabel.set_fontfamily('sans-serif')
        # Reposition xlabel
        bottom_ax.xaxis.set_label_coords(0.5, xlabel_y_pos)

        # Apply tight layout to prevent label cutoff
        self.sparams_canvas.fig.tight_layout()
        self.sparams_canvas.draw()

        # Autopopulate axis limit spinboxes with current autoscaled values
        xlim = self.sparams_canvas.ax.get_xlim()

        # Update spinbox values (blocking signals to avoid recursion)
        self.sparams_xmin_spin.blockSignals(True)
        self.sparams_xmax_spin.blockSignals(True)
        self.sparams_ymin_spin.blockSignals(True)
        self.sparams_ymax_spin.blockSignals(True)
        self.sparams_phase_min_spin.blockSignals(True)
        self.sparams_phase_max_spin.blockSignals(True)

        # Update X spinboxes if X autoscale is on
        if self.sparams_x_autoscale.isChecked():
            self.sparams_xmin_spin.setValue(xlim[0])
            self.sparams_xmax_spin.setValue(xlim[1])

        # Update Y dB spinboxes if Y autoscale is on
        if plot_mode in ('dB', 'both') and self.sparams_y_autoscale.isChecked():
            ax_db = self.sparams_ax_db if plot_mode == 'both' else self.sparams_canvas.ax
            ylim_db = ax_db.get_ylim()
            self.sparams_ymin_spin.setValue(ylim_db[0])
            self.sparams_ymax_spin.setValue(ylim_db[1])

        # Update Y Phase spinboxes if Phase autoscale is on
        if plot_mode in ('phase', 'both') and self.sparams_phase_autoscale.isChecked():
            ax_phase = self.sparams_ax_phase if plot_mode == 'both' else self.sparams_canvas.ax
            ylim_phase = ax_phase.get_ylim()
            self.sparams_phase_min_spin.setValue(ylim_phase[0])
            self.sparams_phase_max_spin.setValue(ylim_phase[1])

        self.sparams_xmin_spin.blockSignals(False)
        self.sparams_xmax_spin.blockSignals(False)
        self.sparams_ymin_spin.blockSignals(False)
        self.sparams_ymax_spin.blockSignals(False)
        self.sparams_phase_min_spin.blockSignals(False)
        self.sparams_phase_max_spin.blockSignals(False)

    def _show_sparams_error(self, error_msg):
        """Show error message on S-params plot"""
        self.sparams_canvas.ax.clear()
        self.sparams_canvas.ax.text(
            0.5, 0.5,
            f"Error:\n{error_msg}",
            ha='center', va='center',
            fontsize=12, color='red',
            transform=self.sparams_canvas.ax.transAxes,
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5)
        )
        self.sparams_canvas.ax.set_xlim(0, 1)
        self.sparams_canvas.ax.set_ylim(0, 1)
        self.sparams_canvas.ax.axis('off')
        self.sparams_canvas.draw()

    def _on_sparams_autoscale_changed(self, state):
        """Handle autoscale checkbox state changes"""
        # Enable/disable X spinboxes based on X autoscale
        x_autoscale = self.sparams_x_autoscale.isChecked()
        self.sparams_xmin_spin.setEnabled(not x_autoscale)
        self.sparams_xmax_spin.setEnabled(not x_autoscale)

        # Enable/disable Y dB spinboxes based on Y autoscale
        y_autoscale = self.sparams_y_autoscale.isChecked()
        self.sparams_ymin_spin.setEnabled(not y_autoscale)
        self.sparams_ymax_spin.setEnabled(not y_autoscale)

        # Enable/disable Y Phase spinboxes based on Phase autoscale
        phase_autoscale = self.sparams_phase_autoscale.isChecked()
        self.sparams_phase_min_spin.setEnabled(not phase_autoscale)
        self.sparams_phase_max_spin.setEnabled(not phase_autoscale)

        # Replot
        if hasattr(self, 'sparams_data') and self.sparams_data is not None:
            self._plot_sparams()

    def _get_sparams_plot_mode(self):
        """Get current S-parameter plot mode: 'dB', 'phase', or 'both'"""
        if self.sparams_mode_db.isChecked():
            return 'dB'
        elif self.sparams_mode_phase.isChecked():
            return 'phase'
        else:
            return 'both'

    def _update_sparams_axis_controls_visibility(self):
        """Show/hide Y dB and Y Phase columns based on plot mode"""
        mode = self._get_sparams_plot_mode()
        show_db = mode in ('dB', 'both')
        show_phase = mode in ('phase', 'both')

        # Y dB column visibility
        self.sparams_ydb_header.setVisible(show_db)
        self.sparams_y_autoscale.setVisible(show_db)
        self.sparams_ydb_max_label.setVisible(show_db)
        self.sparams_ymax_spin.setVisible(show_db)
        self.sparams_ydb_min_label.setVisible(show_db)
        self.sparams_ymin_spin.setVisible(show_db)

        # Y Phase column visibility
        self.sparams_yphase_header.setVisible(show_phase)
        self.sparams_phase_autoscale.setVisible(show_phase)
        self.sparams_phase_max_label.setVisible(show_phase)
        self.sparams_phase_max_spin.setVisible(show_phase)
        self.sparams_phase_min_label.setVisible(show_phase)
        self.sparams_phase_min_spin.setVisible(show_phase)
        self.sparams_phase_unwrap.setVisible(show_phase)

    def _on_sparams_plot_mode_changed(self, button):
        """Handle plot mode radio button change"""
        self._update_sparams_axis_controls_visibility()

        # Replot with new mode
        if hasattr(self, 'sparams_data') and self.sparams_data is not None:
            self._plot_sparams()

    def _on_sparams_axis_limit_changed(self):
        """Handle axis limit spinbox changes"""
        # Replot when limits change (plot function will check autoscale state)
        if hasattr(self, 'sparams_data') and self.sparams_data is not None:
            self._plot_sparams()

    def _on_sparams_conjugate_toggled(self):
        """Handle conjugate frequencies toggle button"""
        # Update button text based on state
        if self.sparams_conjugate_freqs.isChecked():
            self.sparams_conjugate_freqs.setText("Unconjugate Freqs")
        else:
            self.sparams_conjugate_freqs.setText("Conjugate Freqs")

        # Replot with transformed data
        if hasattr(self, 'sparams_data') and self.sparams_data is not None:
            self._plot_sparams()

    def _on_scattering_click(self, event):
        """Handle mouse click on scattering canvas"""
        # Placeholder for selection and double-click handling
        if event.dblclick:
            # Double-click - show assignment dialog
            print("Double-click on scattering canvas (dialog placeholder)")
        # TODO: Implement selection highlighting and dialog

    def _create_scattering_properties_tab(self):
        """Create the Scattering tab in properties panel"""
        scattering_tab = QWidget()
        scattering_layout = QVBoxLayout()
        scattering_tab.setLayout(scattering_layout)

        # Create vertical splitter for top/bottom sections
        splitter = QSplitter(Qt.Orientation.Vertical)
        scattering_layout.addWidget(splitter)

        # Top section: Assignment widgets (placeholder)
        top_widget = QWidget()
        top_layout = QVBoxLayout()
        top_widget.setLayout(top_layout)

        title_label = QLabel("Node/Edge Assignment")
        title_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        top_layout.addWidget(title_label)

        placeholder_label = QLabel("Assignment widgets will go here\n(placeholder)")
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_label.setStyleSheet("color: gray; font-style: italic; padding: 40px;")
        top_layout.addWidget(placeholder_label, stretch=1)

        splitter.addWidget(top_widget)

        # Bottom section: Computed plots (placeholder)
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout()
        bottom_widget.setLayout(bottom_layout)

        plot_title_label = QLabel("Computed Data")
        plot_title_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        bottom_layout.addWidget(plot_title_label)

        plot_placeholder_label = QLabel("Matplotlib plots will go here\n(placeholder)")
        plot_placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        plot_placeholder_label.setStyleSheet("color: gray; font-style: italic; padding: 40px;")
        bottom_layout.addWidget(plot_placeholder_label, stretch=1)

        splitter.addWidget(bottom_widget)

        # Set initial splitter sizes (50/50 split)
        splitter.setSizes([300, 300])

        # Insert tab after SymPy Code tab (index 2)
        self.properties_panel.tabs.insertTab(3, scattering_tab, "Scattering")
        self.properties_panel.scattering_tab_index = 3

        # Hide initially
        self.properties_panel.tabs.setTabVisible(3, False)

    def _show_color_context_menu(self, event, node):
        """Show context menu for color selection"""
        # Create context menu
        menu = QMenu(self)

        # Add color options
        for color_name in config.MYCOLORS.keys():
            action = menu.addAction(color_name)
            # Use lambda with default argument to capture color_name
            action.triggered.connect(lambda _, c=color_name, n=node: self._change_node_color(n, c))

        # Show menu at mouse position
        menu.exec(QCursor.pos())

    def _change_node_color(self, node, color_key):
        """Change the color of a node (or all selected nodes if multiple selected)"""
        self._save_state()

        # If the clicked node is in selection, change all selected nodes
        if node in self.selected_nodes and len(self.selected_nodes) > 1:
            for selected_node in self.selected_nodes:
                selected_node['color'] = config.MYCOLORS[color_key]
                selected_node['color_key'] = color_key
            print(f"Changed color of {len(self.selected_nodes)} nodes to {color_key}")
            # Update last_node_props with the first selected node's properties
            last_modified = self.selected_nodes[0]
        else:
            # Change just this node
            node['color'] = config.MYCOLORS[color_key]
            node['color_key'] = color_key
            print(f"Changed node '{node['label']}' color to {color_key}")
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

    def _show_edge_context_menu(self, _event, edge):
        """Show context menu for edge width selection"""
        # Select the edge if not already selected
        if edge not in self.selected_edges:
            self.selected_edges.clear()
            self.selected_edges.append(edge)
            self.selected_nodes.clear()  # Clear node selection when selecting edge
            self._update_plot()

        # Create context menu
        menu = QMenu(self)

        # Add edge width options
        width_options = [
            ('Thin', 0.7),
            ('Medium', 1.0),
            ('Large', 1.5),
            ('X-Large', 2.0)
        ]

        for width_name, width_mult in width_options:
            action = menu.addAction(width_name)
            action.triggered.connect(lambda _, w=width_mult, e=edge: self._change_edge_width(e, w))

        # Show menu at mouse position
        menu.exec(QCursor.pos())

    def _change_edge_width(self, edge, width_mult):
        """Change the width of an edge (or all selected edges if multiple selected)"""
        self._save_state()

        # If the clicked edge is in selection, change all selected edges
        if edge in self.selected_edges and len(self.selected_edges) > 1:
            for selected_edge in self.selected_edges:
                selected_edge['linewidth_mult'] = width_mult
            print(f"Changed width of {len(self.selected_edges)} edge(s) to {width_mult}x")
        else:
            # Change just this edge
            edge['linewidth_mult'] = width_mult
            print(f"Changed edge width to {width_mult}x")

        self._update_plot()

    def _show_matrix_tab(self):
        """Show the Matrix subtab within the Symbolic tab (M shortcut)"""
        self.properties_panel.tabs.setCurrentIndex(2)  # Symbolic tab
        self.properties_panel.symbolic_subtabs.setCurrentIndex(0)  # Matrix subtab

    def _show_basis_tab(self):
        """Show the Basis subtab within the Symbolic tab (B shortcut)"""
        self.properties_panel.tabs.setCurrentIndex(2)  # Symbolic tab
        self.properties_panel.symbolic_subtabs.setCurrentIndex(1)  # Basis subtab

    def _show_code_tab(self):
        """Show the Code subtab within the Symbolic tab (S shortcut)"""
        self.properties_panel.tabs.setCurrentIndex(2)  # Symbolic tab
        self.properties_panel.symbolic_subtabs.setCurrentIndex(2)  # Code subtab

    def _toggle_flip_labels(self):
        """Toggle flip_labels for selected edges using 'f' key"""
        if not self.selected_edges:
            return

        self._save_state()

        for edge in self.selected_edges:
            current = edge.get('flip_labels', False)
            edge['flip_labels'] = not current

        # Print feedback
        if len(self.selected_edges) == 1:
            edge = self.selected_edges[0]
            state = "flipped" if edge['flip_labels'] else "normal"
            print(f"Edge labels: {state}")
        else:
            flipped_count = sum(1 for e in self.selected_edges if e.get('flip_labels', False))
            print(f"Toggled flip for {len(self.selected_edges)} edge(s) ({flipped_count} now flipped)")

        self._update_plot()

    def _toggle_edge_rotation_mode(self):
        """Toggle edge label rotation mode (Shift+F)"""
        if not self.selected_edges:
            print("Select an edge to adjust label rotation")
            return

        self.edge_rotation_mode = not self.edge_rotation_mode

        if self.edge_rotation_mode:
            print("Edge rotation mode: Use Left/Right arrows to adjust label angle (±5°)")
        else:
            print("Exited edge rotation mode")

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
            print(f"Edge label rotation: {rotation:+d}°")
        else:
            print(f"Adjusted rotation for {len(self.selected_edges)} edge(s)")

        self._update_plot()

    def _update_both_canvases(self):
        """Update main canvas, Scattering canvas (if active), and Kron canvas (if exists)"""
        # Update main canvas
        self._update_plot()

        # Update Scattering canvas if it exists
        if self.scattering_mode and hasattr(self, 'scattering_canvas') and self.scattering_canvas:
            saved_canvas = self.canvas
            saved_nodes = self.nodes
            saved_edges = self.edges
            saved_base_xlim = self.base_xlim
            saved_base_ylim = self.base_ylim

            self.canvas = self.scattering_canvas
            self.nodes = self.scattering_graph['nodes']
            self.edges = self.scattering_graph['edges']
            if hasattr(self, 'scattering_original_base_xlim'):
                self.base_xlim = self.scattering_original_base_xlim
                self.base_ylim = self.scattering_original_base_ylim
            self._update_plot()

            # Restore
            self.canvas = saved_canvas
            self.nodes = saved_nodes
            self.edges = saved_edges
            self.base_xlim = saved_base_xlim
            self.base_ylim = saved_base_ylim

        # Update Kron canvas if it exists
        if hasattr(self, 'kron_graph') and self.kron_graph:
            saved_canvas = self.canvas
            saved_nodes = self.nodes
            saved_edges = self.edges
            saved_base_xlim = self.base_xlim
            saved_base_ylim = self.base_ylim

            self.canvas = self.kron_canvas
            self.nodes = self.kron_graph['nodes']
            self.edges = self.kron_graph['edges']
            # Use the same base limits as saved for the Kron canvas
            if hasattr(self, 'kron_original_base_xlim'):
                self.base_xlim = self.kron_original_base_xlim
                self.base_ylim = self.kron_original_base_ylim
            self._update_plot()

            # Restore
            self.canvas = saved_canvas
            self.nodes = saved_nodes
            self.edges = saved_edges
            self.base_xlim = saved_base_xlim
            self.base_ylim = saved_base_ylim

    def _rotate_grid(self):
        """Rotate the grid"""
        increment = config.SQUARE_GRID_ROTATION_INCREMENT if self.grid_type == "square" else config.TRIANGULAR_GRID_ROTATION_INCREMENT
        self.grid_rotation = (self.grid_rotation + increment) % 360
        print(f"Rotated grid to {self.grid_rotation}°")
        self._update_both_canvases()

    def _toggle_grid_type(self):
        """Toggle grid type"""
        self.grid_type = "triangular" if self.grid_type == "square" else "square"
        self.grid_rotation = 0
        print(f"Switched to {self.grid_type} grid")
        self._update_both_canvases()

    def _clear_nodes(self):
        """Clear all nodes"""
        self.nodes = []
        self.node_counter = 0
        print("All nodes cleared")
        self._update_plot()

    def _zoom(self, factor):
        """Zoom by factor - updates the currently visible canvas"""
        self.zoom_level *= factor
        print(f"Zoom level: {self.zoom_level:.3f}x")

        # Determine which canvas is currently visible and update only that one
        current_tab = self.graph_subtabs.currentIndex()
        tab_text = self.graph_subtabs.tabText(current_tab) if current_tab >= 0 else ""

        if tab_text == "Scattering" and self.scattering_mode and hasattr(self, 'scattering_canvas') and self.scattering_canvas:
            # Viewing Scattering canvas - update it
            saved_canvas = self.canvas
            saved_nodes = self.nodes
            saved_edges = self.edges
            saved_base_xlim = self.base_xlim
            saved_base_ylim = self.base_ylim

            self.canvas = self.scattering_canvas
            self.nodes = self.scattering_graph['nodes']
            self.edges = self.scattering_graph['edges']
            if hasattr(self, 'scattering_original_base_xlim'):
                self.base_xlim = self.scattering_original_base_xlim
                self.base_ylim = self.scattering_original_base_ylim
            self._update_plot()

            self.canvas = saved_canvas
            self.nodes = saved_nodes
            self.edges = saved_edges
            self.base_xlim = saved_base_xlim
            self.base_ylim = saved_base_ylim
        elif tab_text == "Kron" and hasattr(self, 'kron_graph') and self.kron_graph:
            # Viewing Kron canvas - update it
            saved_canvas = self.canvas
            saved_nodes = self.nodes
            saved_edges = self.edges
            saved_base_xlim = self.base_xlim
            saved_base_ylim = self.base_ylim

            self.canvas = self.kron_canvas
            self.nodes = self.kron_graph['nodes']
            self.edges = self.kron_graph['edges']
            if hasattr(self, 'kron_original_base_xlim'):
                self.base_xlim = self.kron_original_base_xlim
                self.base_ylim = self.kron_original_base_ylim
            self._update_plot()

            self.canvas = saved_canvas
            self.nodes = saved_nodes
            self.edges = saved_edges
            self.base_xlim = saved_base_xlim
            self.base_ylim = saved_base_ylim
        else:
            # Viewing original canvas
            self._update_plot()

    def _zoom_matrix_display_in(self):
        """Zoom in Matrix/Basis/Notes display (Ctrl+Plus)"""
        # Get the currently visible display in the properties panel
        current_tab = self.properties_panel.tabs.currentIndex()
        if current_tab == 1:  # Notes tab
            notes_subtab = self.properties_panel.notes_subtabs.currentIndex()
            if notes_subtab == 0:  # Edit subtab - zoom font
                self.properties_panel.notes_editor.zoom_in()
            elif notes_subtab == 1:  # Preview subtab - zoom web view
                self.properties_panel.notes_preview.zoom_in()
        elif current_tab == 2:  # Symbolic tab
            symbolic_subtab = self.properties_panel.symbolic_subtabs.currentIndex()
            if symbolic_subtab == 0:  # Matrix subtab
                matrix_subtab = self.properties_panel.matrix_subtabs.currentIndex()
                if matrix_subtab == 0:  # Original matrix
                    self.properties_panel.matrix_display.zoom_in()
                elif matrix_subtab == 1:  # Kron matrix
                    self.properties_panel.kron_matrix_display.zoom_in()
            elif symbolic_subtab == 1:  # Basis subtab
                self.properties_panel.basis_display.zoom_in()

    def _zoom_matrix_display_out(self):
        """Zoom out Matrix/Basis/Notes display (Ctrl+Minus)"""
        current_tab = self.properties_panel.tabs.currentIndex()
        if current_tab == 1:  # Notes tab
            notes_subtab = self.properties_panel.notes_subtabs.currentIndex()
            if notes_subtab == 0:  # Edit subtab - zoom font
                self.properties_panel.notes_editor.zoom_out()
            elif notes_subtab == 1:  # Preview subtab - zoom web view
                self.properties_panel.notes_preview.zoom_out()
        elif current_tab == 2:  # Symbolic tab
            symbolic_subtab = self.properties_panel.symbolic_subtabs.currentIndex()
            if symbolic_subtab == 0:  # Matrix subtab
                matrix_subtab = self.properties_panel.matrix_subtabs.currentIndex()
                if matrix_subtab == 0:  # Original matrix
                    self.properties_panel.matrix_display.zoom_out()
                elif matrix_subtab == 1:  # Kron matrix
                    self.properties_panel.kron_matrix_display.zoom_out()
            elif symbolic_subtab == 1:  # Basis subtab
                self.properties_panel.basis_display.zoom_out()

    def _zoom_matrix_display_reset(self):
        """Reset zoom for Matrix/Basis/Notes display (Ctrl+0)"""
        current_tab = self.properties_panel.tabs.currentIndex()
        if current_tab == 1:  # Notes tab
            notes_subtab = self.properties_panel.notes_subtabs.currentIndex()
            if notes_subtab == 0:  # Edit subtab - reset font to default
                font = self.properties_panel.notes_editor.font()
                font.setPointSize(12)  # Default size
                self.properties_panel.notes_editor.setFont(font)
            elif notes_subtab == 1:  # Preview subtab - reset web view zoom
                self.properties_panel.notes_preview.reset_zoom()
        elif current_tab == 2:  # Symbolic tab
            symbolic_subtab = self.properties_panel.symbolic_subtabs.currentIndex()
            if symbolic_subtab == 0:  # Matrix subtab
                matrix_subtab = self.properties_panel.matrix_subtabs.currentIndex()
                if matrix_subtab == 0:  # Original matrix
                    self.properties_panel.matrix_display.reset_zoom()
                elif matrix_subtab == 1:  # Kron matrix
                    self.properties_panel.kron_matrix_display.reset_zoom()
            elif symbolic_subtab == 1:  # Basis subtab
                self.properties_panel.basis_display.reset_zoom()

    def _pan_matrix_display(self, direction):
        """Pan Matrix/Basis display using JavaScript (Alt+Arrow keys)"""
        current_tab = self.properties_panel.tabs.currentIndex()

        # Determine which display to pan
        display = None
        display_name = ""
        is_basis = False

        if current_tab == 2:  # Symbolic tab
            symbolic_subtab = self.properties_panel.symbolic_subtabs.currentIndex()
            if symbolic_subtab == 0:  # Matrix subtab
                matrix_subtab = self.properties_panel.matrix_subtabs.currentIndex()
                if matrix_subtab == 0:  # Original matrix
                    display = self.properties_panel.matrix_display
                    display_name = "Matrix Original"
                elif matrix_subtab == 1:  # Kron matrix
                    display = self.properties_panel.kron_matrix_display
                    display_name = "Matrix Kron"
            elif symbolic_subtab == 1:  # Basis subtab
                display = self.properties_panel.basis_display
                display_name = "Basis"
                is_basis = True

        if display is None:
            return

        # Execute JavaScript to scroll the container element (not window)
        # For matrix displays, scroll the #matrix-container div
        # For basis display, scroll the body (it doesn't have #matrix-container)
        step = 50  # pixels to scroll
        js_code = ""

        if is_basis:  # Basis subtab - scroll body
            if direction == 'left':
                js_code = f"document.body.scrollLeft -= {step};"
            elif direction == 'right':
                js_code = f"document.body.scrollLeft += {step};"
            elif direction == 'up':
                js_code = f"document.body.scrollTop -= {step};"
            elif direction == 'down':
                js_code = f"document.body.scrollTop += {step};"
        else:  # Matrix subtab - scroll #matrix-container
            if direction == 'left':
                js_code = f"var c = document.getElementById('matrix-container'); if(c) c.scrollLeft -= {step};"
            elif direction == 'right':
                js_code = f"var c = document.getElementById('matrix-container'); if(c) c.scrollLeft += {step};"
            elif direction == 'up':
                js_code = f"var c = document.getElementById('matrix-container'); if(c) c.scrollTop -= {step};"
            elif direction == 'down':
                js_code = f"var c = document.getElementById('matrix-container'); if(c) c.scrollTop += {step};"

        if js_code:
            display.page().runJavaScript(js_code)
            print(f"[{display_name} Pan] {direction.upper()}")

    def _pan_arrow(self, direction):
        """Pan view using arrow keys, or adjust node/edge properties if selected"""

        # If any input widget has focus, don't intercept arrow keys
        # This allows spinboxes, line edits, etc. to handle their own navigation
        if self._is_input_widget_focused():
            # For spinboxes, handle up/down with fine/coarse control
            spinbox = self._get_focused_spinbox()
            if spinbox is not None and direction in ('up', 'down'):
                modifiers = QApplication.keyboardModifiers()
                if modifiers & Qt.ShiftModifier:
                    multiplier = 0.1  # Fine control
                elif modifiers & Qt.AltModifier:
                    multiplier = 10.0  # Coarse control
                else:
                    multiplier = 1.0

                step = spinbox.singleStep() * multiplier
                if direction == 'up':
                    new_value = spinbox.value() + step
                else:
                    new_value = spinbox.value() - step
                new_value = max(spinbox.minimum(), min(spinbox.maximum(), new_value))
                spinbox.setValue(new_value)
            # For left/right in spinboxes, let the widget handle cursor movement
            return

        # If in edge rotation mode, adjust label rotation
        if self.edge_rotation_mode and self.selected_edges and direction in ['left', 'right']:
            self._adjust_edge_rotation(direction)
            return

        # If nodes are selected, adjust their size instead of panning
        if self.selected_nodes:
            self._adjust_node_size(direction)
            return

        # If edges are selected, adjust their properties instead of panning
        if self.selected_edges:
            self._adjust_edge_properties(direction)
            return

        # Otherwise, pan the view
        # Determine which canvas is currently visible
        current_tab = self.graph_subtabs.currentIndex()
        tab_text = self.graph_subtabs.tabText(current_tab) if current_tab >= 0 else ""

        if tab_text == "Scattering" and self.scattering_mode and hasattr(self, 'scattering_canvas') and self.scattering_canvas:
            # Panning Scattering canvas
            if hasattr(self, 'scattering_original_base_xlim'):
                # Temporarily swap to scattering base limits to calculate pan amount
                saved_base_xlim = self.base_xlim
                saved_base_ylim = self.base_ylim
                self.base_xlim = self.scattering_original_base_xlim
                self.base_ylim = self.scattering_original_base_ylim

                xlim = self._get_xlim()
                ylim = self._get_ylim()

                # Pan by 10% of current view width/height
                pan_amount_x = (xlim[1] - xlim[0]) * 0.1
                pan_amount_y = (ylim[1] - ylim[0]) * 0.1

                if direction == 'left':
                    self.scattering_original_base_xlim = (self.scattering_original_base_xlim[0] - pan_amount_x,
                                                           self.scattering_original_base_xlim[1] - pan_amount_x)
                elif direction == 'right':
                    self.scattering_original_base_xlim = (self.scattering_original_base_xlim[0] + pan_amount_x,
                                                           self.scattering_original_base_xlim[1] + pan_amount_x)
                elif direction == 'up':
                    self.scattering_original_base_ylim = (self.scattering_original_base_ylim[0] + pan_amount_y,
                                                           self.scattering_original_base_ylim[1] + pan_amount_y)
                elif direction == 'down':
                    self.scattering_original_base_ylim = (self.scattering_original_base_ylim[0] - pan_amount_y,
                                                           self.scattering_original_base_ylim[1] - pan_amount_y)

                # Update scattering canvas with new limits
                self.base_xlim = self.scattering_original_base_xlim
                self.base_ylim = self.scattering_original_base_ylim
                self.scattering_canvas.ax.set_xlim(*self._get_xlim())
                self.scattering_canvas.ax.set_ylim(*self._get_ylim())
                self.scattering_canvas.draw_idle()

                # Restore original base limits
                self.base_xlim = saved_base_xlim
                self.base_ylim = saved_base_ylim
        elif tab_text == "Kron" and hasattr(self, 'kron_graph') and self.kron_graph:
            # Panning Kron canvas
            if hasattr(self, 'kron_original_base_xlim'):
                # Temporarily swap to kron base limits to calculate pan amount
                saved_base_xlim = self.base_xlim
                saved_base_ylim = self.base_ylim
                self.base_xlim = self.kron_original_base_xlim
                self.base_ylim = self.kron_original_base_ylim

                xlim = self._get_xlim()
                ylim = self._get_ylim()

                # Pan by 10% of current view width/height
                pan_amount_x = (xlim[1] - xlim[0]) * 0.1
                pan_amount_y = (ylim[1] - ylim[0]) * 0.1

                if direction == 'left':
                    self.kron_original_base_xlim = (self.kron_original_base_xlim[0] - pan_amount_x,
                                                     self.kron_original_base_xlim[1] - pan_amount_x)
                elif direction == 'right':
                    self.kron_original_base_xlim = (self.kron_original_base_xlim[0] + pan_amount_x,
                                                     self.kron_original_base_xlim[1] + pan_amount_x)
                elif direction == 'up':
                    self.kron_original_base_ylim = (self.kron_original_base_ylim[0] + pan_amount_y,
                                                     self.kron_original_base_ylim[1] + pan_amount_y)
                elif direction == 'down':
                    self.kron_original_base_ylim = (self.kron_original_base_ylim[0] - pan_amount_y,
                                                     self.kron_original_base_ylim[1] - pan_amount_y)

                # Update kron canvas with new limits
                self.base_xlim = self.kron_original_base_xlim
                self.base_ylim = self.kron_original_base_ylim
                self.kron_canvas.ax.set_xlim(*self._get_xlim())
                self.kron_canvas.ax.set_ylim(*self._get_ylim())
                self.kron_canvas.draw_idle()

                # Restore original base limits
                self.base_xlim = saved_base_xlim
                self.base_ylim = saved_base_ylim
        else:
            # Panning original canvas
            xlim = self._get_xlim()
            ylim = self._get_ylim()

            # Pan by 10% of current view width/height
            pan_amount_x = (xlim[1] - xlim[0]) * 0.1
            pan_amount_y = (ylim[1] - ylim[0]) * 0.1

            if direction == 'left':
                self.base_xlim = (self.base_xlim[0] - pan_amount_x, self.base_xlim[1] - pan_amount_x)
            elif direction == 'right':
                self.base_xlim = (self.base_xlim[0] + pan_amount_x, self.base_xlim[1] + pan_amount_x)
            elif direction == 'up':
                self.base_ylim = (self.base_ylim[0] + pan_amount_y, self.base_ylim[1] + pan_amount_y)
            elif direction == 'down':
                self.base_ylim = (self.base_ylim[0] - pan_amount_y, self.base_ylim[1] - pan_amount_y)

            self._update_plot()

    def _adjust_node_size(self, direction):
        """Adjust node size or label size for selected nodes"""
        if not self.selected_nodes:
            return

        self._save_state()

        # Use increment from config for smooth adjustment
        increment = config.NODE_SIZE_KEYBOARD_INCREMENT

        for node in self.selected_nodes:
            if direction == 'up':
                # Increase node size
                current = node.get('node_size_mult', 1.0)
                node['node_size_mult'] = min(current + increment, config.NODE_SIZE_MAX)
            elif direction == 'down':
                # Decrease node size
                current = node.get('node_size_mult', 1.0)
                node['node_size_mult'] = max(current - increment, config.NODE_SIZE_MIN)
            elif direction == 'left':
                # Decrease label size
                current = node.get('label_size_mult', 1.0)
                node['label_size_mult'] = max(current - increment, config.NODE_LABEL_SIZE_MIN)
            elif direction == 'right':
                # Increase label size
                current = node.get('label_size_mult', 1.0)
                node['label_size_mult'] = min(current + increment, config.NODE_LABEL_SIZE_MAX)

        # Print feedback
        if len(self.selected_nodes) == 1:
            node = self.selected_nodes[0]
            if direction in ['up', 'down']:
                print(f"Node '{node['label']}' size: {node['node_size_mult']:.1f}")
            else:
                print(f"Node '{node['label']}' label size: {node['label_size_mult']:.1f}")
        else:
            if direction in ['up', 'down']:
                print(f"Adjusted node size for {len(self.selected_nodes)} nodes")
            else:
                print(f"Adjusted label size for {len(self.selected_nodes)} nodes")

        self._update_plot()

    def _rotate_selected_nodes(self, angle_degrees):
        """Rotate selected nodes around their centroid

        Args:
            angle_degrees: Rotation angle in degrees. Positive = CCW, Negative = CW
        """
        if not self.selected_nodes:
            print("No nodes selected to rotate")
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
            print(f"Rotated node '{self.selected_nodes[0]['label']}' {abs(angle_degrees)}° {direction}")
        else:
            print(f"Rotated {len(self.selected_nodes)} nodes {abs(angle_degrees)}° {direction} around centroid ({centroid[0]:.2f}, {centroid[1]:.2f})")

        self._update_plot()

    def _flip_selected_nodes_horizontal(self):
        """Flip selected nodes horizontally (reflect across Y axis through centroid)

        This mirrors nodes left-to-right around the vertical center line of the selection.
        """
        if not self.selected_nodes:
            print("No nodes selected to flip")
            return

        self._save_state()

        # Calculate centroid of selected nodes
        positions = np.array([node['pos'] for node in self.selected_nodes])
        centroid_x = positions[:, 0].mean()

        # Get IDs of selected nodes for self-loop tracking
        selected_node_ids = {node['node_id'] for node in self.selected_nodes}

        # Flip each node's x position around the centroid
        for node in self.selected_nodes:
            x, y = node['pos']
            node['pos'] = (2 * centroid_x - x, y)

        # Adjust self-loop angles for edges attached to selected nodes
        for edge in self.edges:
            if edge.get('is_self_loop', False):
                if edge['from_node_id'] in selected_node_ids:
                    angle = edge.get('selfloopangle', 45)
                    edge['selfloopangle'] = -angle + 180

        # Print feedback
        if len(self.selected_nodes) == 1:
            print(f"Flipped node '{self.selected_nodes[0]['label']}' horizontally")
        else:
            print(f"Flipped {len(self.selected_nodes)} nodes horizontally around x={centroid_x:.2f}")

        self._update_plot()

    def _flip_selected_nodes_vertical(self):
        """Flip selected nodes vertically (reflect across X axis through centroid)

        This mirrors nodes up-to-down around the horizontal center line of the selection.
        """
        if not self.selected_nodes:
            print("No nodes selected to flip")
            return

        self._save_state()

        # Calculate centroid of selected nodes
        positions = np.array([node['pos'] for node in self.selected_nodes])
        centroid_y = positions[:, 1].mean()

        # Get IDs of selected nodes for self-loop tracking
        selected_node_ids = {node['node_id'] for node in self.selected_nodes}

        # Flip each node's y position around the centroid
        for node in self.selected_nodes:
            x, y = node['pos']
            node['pos'] = (x, 2 * centroid_y - y)

        # Adjust self-loop angles for edges attached to selected nodes
        for edge in self.edges:
            if edge.get('is_self_loop', False):
                if edge['from_node_id'] in selected_node_ids:
                    angle = edge.get('selfloopangle', 45)
                    edge['selfloopangle'] = -angle

        # Print feedback
        if len(self.selected_nodes) == 1:
            print(f"Flipped node '{self.selected_nodes[0]['label']}' vertically")
        else:
            print(f"Flipped {len(self.selected_nodes)} nodes vertically around y={centroid_y:.2f}")

        self._update_plot()

    def _nudge_label(self, direction):
        """Nudge node label position for selected nodes, or edge label offset for edges"""
        # If a spinbox has focus, use Shift+Arrow for fine control instead
        focused_widget = QApplication.focusWidget()
        if isinstance(focused_widget, (QDoubleSpinBox, QSpinBox)) and direction in ('up', 'down'):
            # Shift+Up/Down: finer control (1/10 step)
            step = focused_widget.singleStep() * 0.1
            if direction == 'up':
                new_value = focused_widget.value() + step
            else:
                new_value = focused_widget.value() - step
            new_value = max(focused_widget.minimum(), min(focused_widget.maximum(), new_value))
            focused_widget.setValue(new_value)
            return

        # If edges are selected, check if they are self-loops
        if self.selected_edges:
            # Check if any selected edges are self-loops
            has_selfloop = any(edge.get('is_self_loop', False) for edge in self.selected_edges)
            if has_selfloop:
                self._nudge_selfloop_label(direction)
            else:
                self._adjust_edge_label_offset(direction)
            return

        if not self.selected_nodes:
            return

        self._save_state()

        # Calculate nudge increment: 0.02 × diameter
        # diameter = 2 × radius × node_size_mult
        # Use reference node radius from config
        base_diameter = 2 * self.node_radius

        for node in self.selected_nodes:
            # Get current nudge (default to (0, 0))
            current_nudge = node.get('nodelabelnudge', (0.0, 0.0))
            node_size_mult = node.get('node_size_mult', 1.0)

            # Calculate increment based on this node's actual diameter
            diameter = base_diameter * node_size_mult
            increment = 0.01 * diameter

            # Update nudge based on direction
            nudge_x, nudge_y = current_nudge
            if direction == 'left':
                nudge_x -= increment
            elif direction == 'right':
                nudge_x += increment
            elif direction == 'up':
                nudge_y += increment
            elif direction == 'down':
                nudge_y -= increment

            node['nodelabelnudge'] = (nudge_x, nudge_y)

        # Print feedback
        if len(self.selected_nodes) == 1:
            node = self.selected_nodes[0]
            nudge = node['nodelabelnudge']
            print(f"Node '{node['label']}' label nudge: ({nudge[0]:.3f}, {nudge[1]:.3f})")
        else:
            print(f"Nudged labels for {len(self.selected_nodes)} nodes")

        self._update_plot()

    def _adjust_edge_properties(self, direction):
        """Adjust edge thickness or label size for selected edges"""
        if not self.selected_edges:
            return

        self._save_state()

        for edge in self.selected_edges:
            # Use larger increments for loopy style edges
            is_loopy = edge.get('style', 'loopy') == 'loopy'
            linewidth_increment = 0.2 if is_loopy else 0.1

            if direction == 'up':
                # Increase linewidth
                current = edge.get('linewidth_mult', 1.5)
                edge['linewidth_mult'] = min(current + linewidth_increment, 3.0)
            elif direction == 'down':
                # Decrease linewidth
                current = edge.get('linewidth_mult', 1.5)
                edge['linewidth_mult'] = max(current - linewidth_increment, 0.2)
            elif direction == 'left':
                # Decrease label size
                current = edge.get('label_size_mult', 1.4)
                edge['label_size_mult'] = max(current - 0.1, 0.5)
            elif direction == 'right':
                # Increase label size
                current = edge.get('label_size_mult', 1.4)
                edge['label_size_mult'] = min(current + 0.1, 3.0)

        # Print feedback and save last props
        if len(self.selected_edges) == 1:
            edge = self.selected_edges[0]
            if direction in ['up', 'down']:
                print(f"Edge linewidth: {edge['linewidth_mult']:.1f}")
            else:
                print(f"Edge label size: {edge['label_size_mult']:.1f}")
            # Save for inheritance
            self._save_last_edge_props(edge)
        else:
            print(f"Adjusted properties for {len(self.selected_edges)} edge(s)")
            # Save the last one for inheritance
            if self.selected_edges:
                self._save_last_edge_props(self.selected_edges[-1])

        self._update_plot()

    def _arrow_key_action(self, direction):
        """Handle Up/Down arrow keys - adjust self-loop linewidth if self-loop selected, otherwise pan"""

        # If any input widget has focus, handle spinbox increment or let widget handle it
        if self._is_input_widget_focused():
            spinbox = self._get_focused_spinbox()
            if spinbox is not None:
                # Handle spinbox up/down with fine/coarse control
                modifiers = QApplication.keyboardModifiers()
                if modifiers & Qt.ShiftModifier:
                    multiplier = 0.1  # Fine control
                elif modifiers & Qt.AltModifier:
                    multiplier = 10.0  # Coarse control
                else:
                    multiplier = 1.0

                step = spinbox.singleStep() * multiplier
                if direction == 'up':
                    new_value = spinbox.value() + step
                else:
                    new_value = spinbox.value() - step
                new_value = max(spinbox.minimum(), min(spinbox.maximum(), new_value))
                spinbox.setValue(new_value)
            return

        # Check if a single self-loop is selected
        if len(self.selected_edges) == 1 and self.selected_edges[0].get('is_self_loop', False):
            self._adjust_selfloop_linewidth(direction)
        else:
            self._pan_arrow(direction)

    def _adjust_selfloop_linewidth(self, direction):
        """Adjust self-loop linewidth using Up/Down keys (20% increments)"""
        if not self.selected_edges or not self.selected_edges[0].get('is_self_loop', False):
            return

        self._save_state()
        edge = self.selected_edges[0]

        current = edge.get('linewidth_mult', 1.5)
        increment = current * 0.2  # 20% of current value

        if direction == 'up':
            edge['linewidth_mult'] = min(current + increment, 8.0)
        elif direction == 'down':
            edge['linewidth_mult'] = max(current - increment, 0.2)

        print(f"Self-loop linewidth: {edge['linewidth_mult']:.3f}")
        # Save for inheritance
        self._save_last_edge_props(edge)
        self._update_plot()

    def _adjust_selfloop_scale(self, action):
        """Adjust self-loop scale using Ctrl+Up/Down (20% increments)"""
        if not self.selected_edges:
            return

        # Filter to only self-loops
        selfloops = [e for e in self.selected_edges if e.get('is_self_loop', False)]
        if not selfloops:
            return

        self._save_state()

        for edge in selfloops:
            current = edge.get('selfloopscale', 1.0)
            increment = current * 0.2  # 20% of current value

            if action == 'increase':
                edge['selfloopscale'] = min(current + increment, 3.0)
            elif action == 'decrease':
                edge['selfloopscale'] = max(current - increment, 0.3)

        if len(selfloops) == 1:
            print(f"Self-loop scale: {selfloops[0]['selfloopscale']:.3f}")
            # Save for inheritance
            self._save_last_edge_props(selfloops[0])
        else:
            print(f"Adjusted scale for {len(selfloops)} self-loop(s)")
            # Save the last one for inheritance
            if selfloops:
                self._save_last_edge_props(selfloops[-1])

        self._update_plot()

    def _adjust_selfloop_angle(self, action):
        """Adjust self-loop angle using Ctrl+Left/Right (15° increments)"""
        if not self.selected_edges:
            return

        # Filter to only self-loops
        selfloops = [e for e in self.selected_edges if e.get('is_self_loop', False)]
        if not selfloops:
            return

        self._save_state()

        for edge in selfloops:
            current = edge.get('selfloopangle', 0)

            # Reverse direction: Left increases (counter-clockwise), Right decreases (clockwise)
            if action == 'increase':
                edge['selfloopangle'] = (current - 15) % 360
            elif action == 'decrease':
                edge['selfloopangle'] = (current + 15) % 360

        if len(selfloops) == 1:
            print(f"Self-loop angle: {selfloops[0]['selfloopangle']}°")
            # Save for inheritance
            self._save_last_edge_props(selfloops[0])
        else:
            print(f"Adjusted angle for {len(selfloops)} self-loop(s)")
            # Save the last one for inheritance
            if selfloops:
                self._save_last_edge_props(selfloops[-1])

        self._update_plot()

    def _adjust_edge_looptheta_or_selfloop_angle(self, action):
        """Adjust looptheta for regular edges or selfloopangle for self-loops using Ctrl+Left/Right (2° increments for looptheta, 15° for selfloop)"""
        print(f"DEBUG: _adjust_edge_looptheta_or_selfloop_angle called with action={action}, selected_edges count={len(self.selected_edges)}")
        if not self.selected_edges:
            print("DEBUG: No edges selected, returning")
            return

        # Separate self-loops from regular edges
        selfloops = [e for e in self.selected_edges if e.get('is_self_loop', False)]
        regular_edges = [e for e in self.selected_edges if not e.get('is_self_loop', False)]
        print(f"DEBUG: selfloops={len(selfloops)}, regular_edges={len(regular_edges)}")

        if not selfloops and not regular_edges:
            print("DEBUG: No valid edges found")
            return

        self._save_state()

        # Adjust self-loop angles (15° increments)
        for edge in selfloops:
            current = edge.get('selfloopangle', 0)
            # Reverse direction: Left increases (counter-clockwise), Right decreases (clockwise)
            if action == 'increase':
                edge['selfloopangle'] = (current - 15) % 360
            elif action == 'decrease':
                edge['selfloopangle'] = (current + 15) % 360

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

        # Print feedback and save for inheritance
        if len(self.selected_edges) == 1:
            edge = self.selected_edges[0]
            if edge.get('is_self_loop', False):
                print(f"Self-loop angle: {edge['selfloopangle']}°")
            else:
                print(f"Edge looptheta: {edge.get('looptheta', 30)}°")
            # Save for inheritance
            self._save_last_edge_props(edge)
        else:
            if selfloops and regular_edges:
                print(f"Adjusted {len(selfloops)} self-loop(s) and {len(regular_edges)} edge(s)")
            elif selfloops:
                print(f"Adjusted angle for {len(selfloops)} self-loop(s)")
            else:
                print(f"Adjusted looptheta for {len(regular_edges)} edge(s)")
            # Save the last modified edge for inheritance
            if selfloops:
                self._save_last_edge_props(selfloops[-1])
            elif regular_edges:
                self._save_last_edge_props(regular_edges[-1])

        self._update_plot()

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
            print(f"Edge label offset: {edge['label_offset_mult']:.1f}")
        else:
            print(f"Adjusted label offset for {len(self.selected_edges)} edge(s)")

        self._update_plot()

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
            print(f"Self-loop label nudge: ({nudge[0]:.3f}, {nudge[1]:.3f})")
        else:
            print(f"Nudged labels for {len(selfloops)} self-loop(s)")

        self._update_plot()

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

    def _get_canvas_aspect_ratio(self):
        """Get the aspect ratio (width/height) of the canvas"""
        bbox = self.canvas.ax.get_window_extent()
        width = bbox.width
        height = bbox.height
        if height > 0:
            return width / height
        return 1.0

    def _draw_grid(self):
        """Draw the grid overlay (only on Original canvas)

        Grid is only shown on the editable Original view to indicate editability.
        Scattering and Kron views are read-only, so no grid is displayed.
        """
        # Only draw grid on the original canvas
        if self.canvas != self.original_canvas:
            return

        if self.grid_type == "square":
            self._draw_square_grid()
        else:
            self._draw_triangular_grid()

    def _draw_square_grid(self):
        """Draw rotated square grid"""
        spacing = self.grid_spacing
        rot_rad = np.radians(self.grid_rotation)

        xlim = self._get_xlim()
        ylim = self._get_ylim()
        max_extent = max(abs(xlim[0]), abs(xlim[1]), abs(ylim[0]), abs(ylim[1])) * 1.5
        n = int(max_extent / spacing) + 2

        for i in range(-n, n + 1):
            offset = i * spacing

            # Vertical lines
            x1 = offset * np.cos(rot_rad) - max_extent * np.sin(rot_rad)
            y1 = offset * np.sin(rot_rad) + max_extent * np.cos(rot_rad)
            x2 = offset * np.cos(rot_rad) + max_extent * np.sin(rot_rad)
            y2 = offset * np.sin(rot_rad) - max_extent * np.cos(rot_rad)
            self.canvas.ax.plot([x1, x2], [y1, y2], 'lightgray', lw=0.5, zorder=0)

            # Horizontal lines
            x1 = -max_extent * np.cos(rot_rad) + offset * np.sin(rot_rad)
            y1 = -max_extent * np.sin(rot_rad) - offset * np.cos(rot_rad)
            x2 = max_extent * np.cos(rot_rad) + offset * np.sin(rot_rad)
            y2 = max_extent * np.sin(rot_rad) - offset * np.cos(rot_rad)
            self.canvas.ax.plot([x1, x2], [y1, y2], 'lightgray', lw=0.5, zorder=0)

    def _draw_triangular_grid(self):
        """Draw rotated triangular grid"""
        spacing = self.grid_spacing
        rot_rad = np.radians(self.grid_rotation)
        sqrt3 = np.sqrt(3)

        xlim = self._get_xlim()
        ylim = self._get_ylim()
        max_extent = max(abs(xlim[0]), abs(xlim[1]), abs(ylim[0]), abs(ylim[1])) * 1.5
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
            self.canvas.ax.plot([x1r, x2r], [y1r, y2r], 'lightgray', lw=0.5, zorder=0)

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
            self.canvas.ax.plot([x1r, x2r], [y1r, y2r], 'lightgray', lw=0.5, zorder=0)

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
            self.canvas.ax.plot([x1r, x2r], [y1r, y2r], 'lightgray', lw=0.5, zorder=0)

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

    def _get_next_label(self):
        """Generate next alphabetical label"""
        if self.node_counter < 26:
            return chr(ord('A') + self.node_counter)
        else:
            first = chr(ord('A') + (self.node_counter // 26) - 1)
            second = chr(ord('A') + (self.node_counter % 26))
            return first + second

    def _get_ghost_node_properties(self):
        """Get predicted properties for the next node to be placed.

        Returns a dict with the properties that the ghost preview should display,
        based on the current placement mode and dialog/node defaults.
        """
        from .para_ui.dialogs import NodeInputDialog

        # For continuous_duplicate mode, use last_node_props with auto-incremented label
        if self.placement_mode == 'continuous_duplicate' and self.last_node_props:
            current_label = self.last_node_props['label']
            if current_label == '':
                next_label = 'A'
            else:
                next_label = self._auto_increment_label(current_label)
            return {
                'label': next_label,
                'color': self.last_node_props['color'],
                'color_key': self.last_node_props['color_key'],
                'node_size_mult': self.last_node_props['node_size_mult'],
                'label_size_mult': self.last_node_props['label_size_mult'],
                'conj': self.last_node_props['conj'],
                'outline_enabled': self.last_node_props.get('outline_enabled', False),
                'outline_color': self.last_node_props.get('outline_color', 'black'),
                'outline_width': self.last_node_props.get('outline_width', config.DEFAULT_NODE_OUTLINE_WIDTH),
                'outline_alpha': self.last_node_props.get('outline_alpha', config.DEFAULT_NODE_OUTLINE_ALPHA),
            }

        # For continuous mode with existing last_node_props, inherit those properties
        if self.placement_mode == 'continuous' and self.last_node_props:
            return {
                'label': self._get_next_label(),
                'color': self.last_node_props['color'],
                'color_key': self.last_node_props['color_key'],
                'node_size_mult': self.last_node_props['node_size_mult'],
                'label_size_mult': self.last_node_props['label_size_mult'],
                'conj': self.last_node_props['conj'],
                'outline_enabled': self.last_node_props.get('outline_enabled', False),
                'outline_color': self.last_node_props.get('outline_color', 'black'),
                'outline_width': self.last_node_props.get('outline_width', config.DEFAULT_NODE_OUTLINE_WIDTH),
                'outline_alpha': self.last_node_props.get('outline_alpha', config.DEFAULT_NODE_OUTLINE_ALPHA),
            }

        # For single mode or continuous mode without prior nodes,
        # use the NodeInputDialog class defaults (which persist last choices)
        color_key = NodeInputDialog.last_color
        color = config.MYCOLORS.get(color_key, config.DEFAULT_NODE_COLOR)
        outline_color_key = NodeInputDialog.last_outline_color
        outline_color = config.MYCOLORS.get(outline_color_key, 'black')

        return {
            'label': self._get_next_label(),
            'color': color,
            'color_key': color_key,
            'node_size_mult': NodeInputDialog.last_node_size,
            'label_size_mult': NodeInputDialog.last_label_size,
            'conj': NodeInputDialog.last_conj,
            'outline_enabled': NodeInputDialog.last_outline_enabled,
            'outline_color': outline_color,
            'outline_width': NodeInputDialog.last_outline_width,
            'outline_alpha': NodeInputDialog.last_outline_alpha,
        }

    def _save_last_edge_props(self, edge):
        """Save edge properties for inheritance by subsequent edges.

        Call this after modifying an edge via the properties panel or keyboard shortcuts.
        """
        if edge is None:
            return

        is_self_loop = edge.get('is_self_loop', False)

        if is_self_loop:
            self.last_selfloop_props = {
                'linewidth_mult': edge.get('linewidth_mult', config.DEFAULT_EDGE_LINEWIDTH_MULT),
                'selfloopangle': edge.get('selfloopangle', config.DEFAULT_SELFLOOP_ANGLE),
                'selfloopscale': edge.get('selfloopscale', config.DEFAULT_SELFLOOP_SCALE),
                'flip': edge.get('flip', config.DEFAULT_SELFLOOP_FLIP),
                'arrowlengthsc': edge.get('arrowlengthsc', config.DEFAULT_SELFLOOP_ARROWLENGTH)
            }
        else:
            self.last_edge_props = {
                'linewidth_mult': edge.get('linewidth_mult', config.DEFAULT_EDGE_LINEWIDTH_MULT),
                'direction': edge.get('direction', 'both'),
                'looptheta': edge.get('looptheta', 30)
            }

    def _update_edge_styles_for_node(self, node):
        """Update edge styles for all edges connected to a node based on conjugation states"""
        for edge in self.edges:
            # Skip self-loops (they always use 'loopy' style)
            if edge['is_self_loop']:
                continue

            # Check if this edge involves the given node
            if edge['from_node'] == node or edge['to_node'] == node:
                from_conj = edge['from_node'].get('conj', False)
                to_conj = edge['to_node'].get('conj', False)

                # Determine style based on conjugation states
                same_conj = (from_conj == to_conj)
                new_style = 'single' if same_conj else 'double'

                # Update the edge style
                edge['style'] = new_style

    def _get_nodes_with_duplicate_labels(self):
        """Return a list of nodes that have duplicate labels, excluding valid conjugate pairs.

        A valid conjugate pair is exactly two nodes with the same label where one has
        conj=True and the other has conj=False. Such pairs are allowed and do not
        trigger duplicate warnings.
        """
        label_counts = {}
        # Count occurrences of each label
        for node in self.nodes:
            label = node['label']
            if label not in label_counts:
                label_counts[label] = []
            label_counts[label].append(node)

        # Find all nodes with duplicate labels (excluding valid conjugate pairs)
        duplicate_nodes = []
        for label, nodes in label_counts.items():
            if len(nodes) > 1:
                # Check for valid conjugate pair: exactly 2 nodes, one conj=True, one conj=False
                if len(nodes) == 2:
                    conj_states = [node.get('conj', False) for node in nodes]
                    if sorted(conj_states) == [False, True]:
                        # Valid conjugate pair - skip these nodes
                        continue
                # Not a valid pair - all nodes are duplicates
                duplicate_nodes.extend(nodes)

        return duplicate_nodes

    def _get_conjugate_pairs(self):
        """Return a list of valid conjugate pairs.

        Each pair is a tuple of (unconjugated_node, conjugated_node) where both
        share the same label, one has conj=False and the other has conj=True.

        Returns:
            List of tuples: [(node_A, node_A*), (node_B, node_B*), ...]
        """
        label_to_nodes = {}
        for node in self.nodes:
            label = node['label']
            if label not in label_to_nodes:
                label_to_nodes[label] = []
            label_to_nodes[label].append(node)

        pairs = []
        for label, nodes in label_to_nodes.items():
            if len(nodes) == 2:
                conj_states = [node.get('conj', False) for node in nodes]
                if sorted(conj_states) == [False, True]:
                    # Valid pair - order as (unconjugated, conjugated)
                    if nodes[0].get('conj', False):
                        pairs.append((nodes[1], nodes[0]))
                    else:
                        pairs.append((nodes[0], nodes[1]))
        return pairs

    def _update_conjugate_pair_constraints(self):
        """Update constraint groups for conjugate pairs.

        Creates fixed constraint groups for valid conjugate pairs and removes
        constraint groups for pairs that no longer exist.
        """
        current_pairs = self._get_conjugate_pairs()

        # Build set of current pair labels
        current_pair_labels = set()
        for unconj_node, conj_node in current_pairs:
            current_pair_labels.add(unconj_node['label'])

        # Remove conjugate pair constraints for pairs that no longer exist
        groups_to_remove = []
        for group_id, group_data in self.scattering_constraint_groups.items():
            if group_data.get('is_conjugate_pair', False):
                # Check if any member label is still a valid pair
                member_labels = set(group_data['members'])
                # Conjugate pair groups have members like ['A', 'A'] (same label twice)
                if len(member_labels) == 1:
                    base_label = list(member_labels)[0]
                    if base_label not in current_pair_labels:
                        groups_to_remove.append(group_id)

        for group_id in groups_to_remove:
            del self.scattering_constraint_groups[group_id]
            print(f"[Constraints] Dissolved conjugate pair group {group_id} (pair no longer valid)")

        # Track color indices for conjugate pairs (all 3 params share same color per pair)
        # Find existing pair_color_index values to avoid conflicts
        existing_color_indices = set()
        pair_label_to_color_index = {}
        for group_data in self.scattering_constraint_groups.values():
            if group_data.get('is_conjugate_pair', False):
                pair_color_index = group_data.get('pair_color_index', 0)
                existing_color_indices.add(pair_color_index)
                # Map the label to this color index
                member_labels = set(group_data['members'])
                if len(member_labels) == 1:
                    pair_label_to_color_index[list(member_labels)[0]] = pair_color_index

        # Next available color index for new pairs
        next_color_index = max(existing_color_indices, default=0) + 1 if existing_color_indices else 1

        # Create constraint groups for new pairs
        for unconj_node, conj_node in current_pairs:
            label = unconj_node['label']

            # Determine color index for this pair (reuse existing or assign new)
            if label in pair_label_to_color_index:
                pair_color_index = pair_label_to_color_index[label]
            else:
                pair_color_index = next_color_index
                pair_label_to_color_index[label] = pair_color_index
                next_color_index += 1

            # Check and create constraint groups for each parameter
            for param_name in ['freq', 'B_int', 'B_ext']:
                # Check if constraint group already exists for this pair and param
                exists = False
                for group_data in self.scattering_constraint_groups.values():
                    if (group_data.get('is_conjugate_pair', False) and
                        group_data['param_name'] == param_name and
                        group_data['obj_type'] == 'node' and
                        label in group_data['members']):
                        exists = True
                        break

                if not exists:
                    # Create new conjugate pair constraint group
                    group_id = self._next_constraint_group_id
                    self._next_constraint_group_id += 1

                    # Get current value from unconjugated node's assignment (or default)
                    node_id = id(unconj_node)
                    if node_id in self.scattering_assignments:
                        if param_name in self.scattering_assignments[node_id]:
                            value = self.scattering_assignments[node_id][param_name]
                            # Convert to display units for B_int/B_ext (stored as fraction, displayed as milli)
                            if param_name in ('B_int', 'B_ext'):
                                value = value * 1000
                        else:
                            # Use default
                            if param_name == 'freq':
                                value = config.DEFAULT_NODE_FREQ
                            elif param_name == 'B_int':
                                value = config.DEFAULT_NODE_B_INT
                            else:
                                value = config.DEFAULT_NODE_B_EXT
                    else:
                        # Use default
                        if param_name == 'freq':
                            value = config.DEFAULT_NODE_FREQ
                        elif param_name == 'B_int':
                            value = config.DEFAULT_NODE_B_INT
                        else:
                            value = config.DEFAULT_NODE_B_EXT

                    self.scattering_constraint_groups[group_id] = {
                        'param_name': param_name,
                        'obj_type': 'node',
                        'members': [label, label],  # Both nodes have same label
                        'value': value,
                        'is_conjugate_pair': True,
                        'pair_color_index': pair_color_index  # Shared color for all params of this pair
                    }
                    print(f"[Constraints] Created conjugate pair group {group_id} for '{label}' {param_name} (color {pair_color_index})")

        # Update styling if properties panel exists
        if hasattr(self, 'properties_panel') and self.properties_panel is not None:
            self.properties_panel._apply_constraint_styling()

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

    def _edit_node(self, node):
        """Edit an existing node"""
        print(f"Editing node '{node['label']}'...")

        # Save original state in case user cancels
        original_state = {
            'label': node['label'],
            'color': node['color'],
            'color_key': node['color_key'],
            'node_size_mult': node.get('node_size_mult', 1.0),
            'label_size_mult': node.get('label_size_mult', 1.0),
            'conj': node.get('conj', False)
        }

        # Create dialog with current values - pass node and graphulator for live updates
        dialog = NodeInputDialog(default_label=node['label'], parent=self, node=node, graphulator=self)

        # Set current values (block signals to avoid triggering live updates during initialization)
        dialog.color_combo.blockSignals(True)
        dialog.node_size_slider.blockSignals(True)
        dialog.label_size_slider.blockSignals(True)
        dialog.conj_checkbox.blockSignals(True)

        try:
            color_idx = list(config.MYCOLORS.keys()).index(node['color_key'])
            dialog.color_combo.setCurrentIndex(color_idx)
        except:
            pass

        # Set slider values from multipliers
        node_size_mult = node.get('node_size_mult', 1.0)
        label_size_mult = node.get('label_size_mult', 1.0)

        dialog.node_size_slider.setValue(int(node_size_mult * 100))
        dialog.label_size_slider.setValue(int(label_size_mult * 100))

        # Update labels to show current values
        dialog.node_size_label.setText(f"{node_size_mult:.3f}x")
        dialog.label_size_label.setText(f"{label_size_mult:.3f}x")

        # Set current conjugation state
        conj = node.get('conj', False)
        dialog.conj_checkbox.setChecked(conj)

        # Re-enable signals so live updates work
        dialog.color_combo.blockSignals(False)
        dialog.node_size_slider.blockSignals(False)
        dialog.label_size_slider.blockSignals(False)
        dialog.conj_checkbox.blockSignals(False)

        if dialog.exec() == QDialog.Accepted:
            result = dialog.get_result()
            if result:
                self._save_state()

                # Update label (other properties already updated via live updates)
                node['label'] = result['label']

                # Update last_node_props so continuous mode inherits these properties
                self.last_node_props = {
                    'label': result['label'],
                    'color': result['color'],
                    'color_key': result['color_key'],
                    'node_size_mult': result['node_size_mult'],
                    'label_size_mult': result['label_size_mult'],
                    'conj': result['conj']
                }

                print(f"✓ Updated node to '{result['label']}' ({result['color_key']})")
                self._update_plot()
        else:
            # User canceled - restore original state
            node['label'] = original_state['label']
            node['color'] = original_state['color']
            node['color_key'] = original_state['color_key']
            node['node_size_mult'] = original_state['node_size_mult']
            node['label_size_mult'] = original_state['label_size_mult']
            node['conj'] = original_state['conj']
            # Update edge styles in case conjugation changed
            self._update_edge_styles_for_node(node)
            self._update_plot()
            print("✗ Edit canceled")

    def _edit_edge(self, edge):
        """Edit an existing edge"""
        from_node = edge['from_node']
        to_node = edge['to_node']
        from_label = from_node['label']
        to_label = to_node['label']
        is_self_loop = edge['is_self_loop']

        print(f"Editing edge '{from_label}' → '{to_label}'...")

        # Save original state in case user cancels
        original_state = {
            'linewidth_mult': edge.get('linewidth_mult', 1.5),
            'selfloopangle': edge.get('selfloopangle', 0),
            'selfloopscale': edge.get('selfloopscale', 1.0),
            'flip': edge.get('flip', False)
        }

        # Create dialog with current values - pass edge and graphulator for live updates
        dialog = EdgeInputDialog(
            node1_label=from_label,
            node2_label=to_label,
            is_self_loop=is_self_loop,
            node1_conj=from_node.get('conj', False),
            node2_conj=to_node.get('conj', False),
            parent=self,
            edge=edge,
            graphulator=self
        )

        # Block signals to avoid triggering live updates during initialization
        dialog.lw_combo.blockSignals(True)
        if dialog.angle_combo:
            dialog.angle_combo.blockSignals(True)
        if dialog.scale_combo:
            dialog.scale_combo.blockSignals(True)
        if dialog.flip_loop_checkbox:
            dialog.flip_loop_checkbox.blockSignals(True)

        # Map multipliers back to size names (use closest match for floating point safety)
        def find_closest_key(value, mapping):
            return min(mapping.keys(), key=lambda k: abs(k - value))

        linewidth_mult = edge.get('linewidth_mult', 1.0)
        lw_map = {1.0: 'Thin', 1.5: 'Medium', 2.0: 'Thick', 2.5: 'X-Thick'}
        lw_name = lw_map[find_closest_key(linewidth_mult, lw_map)]

        dialog.lw_combo.setCurrentText(lw_name)

        # Style is now auto-determined, no need to set it

        # Set direction for regular edges
        if not is_self_loop and dialog.dir_combo:
            dialog.dir_combo.setCurrentText(edge['direction'])

        # Set looptheta for regular edges
        if not is_self_loop and hasattr(dialog, 'looptheta_spinbox') and dialog.looptheta_spinbox:
            dialog.looptheta_spinbox.setValue(edge.get('looptheta', 30))

        # Set self-loop specific values if applicable
        if is_self_loop and dialog.angle_combo and dialog.scale_combo and dialog.flip_loop_checkbox:
            selfloopangle = edge.get('selfloopangle', 0)
            # Find matching angle option
            angle_options = ['0° (Right)', '45° (Up-Right)', '90° (Up)', '135° (Up-Left)',
                           '180° (Left)', '225° (Down-Left)', '270° (Down)', '315° (Down-Right)']
            for i, option in enumerate(angle_options):
                if int(option.split('°')[0]) == selfloopangle:
                    dialog.angle_combo.setCurrentIndex(i)
                    break

            selfloopscale = edge.get('selfloopscale', 1.0)
            scale_map_reverse = {0.7: 0, 1.0: 1, 1.3: 2, 1.6: 3}
            closest_scale = min(scale_map_reverse.keys(), key=lambda x: abs(x - selfloopscale))
            dialog.scale_combo.setCurrentIndex(scale_map_reverse[closest_scale])

            dialog.flip_loop_checkbox.setChecked(edge.get('flip', False))

        # Re-enable signals so live updates work
        dialog.lw_combo.blockSignals(False)
        if dialog.angle_combo:
            dialog.angle_combo.blockSignals(False)
        if dialog.scale_combo:
            dialog.scale_combo.blockSignals(False)
        if dialog.flip_loop_checkbox:
            dialog.flip_loop_checkbox.blockSignals(False)

        if dialog.exec() == QDialog.Accepted:
            result = dialog.get_result()
            if result:
                self._save_state()

                # Update edge properties
                edge['label1'] = result['label1']
                edge['label2'] = result['label2']
                edge['linewidth_mult'] = result['linewidth_mult']
                edge['label_size_mult'] = result['label_size_mult']
                edge['label_offset_mult'] = result['label_offset_mult']
                edge['style'] = result['style']
                edge['direction'] = result['direction']
                edge['flip_labels'] = result.get('flip_labels', False)

                # Update looptheta for regular edges
                if not is_self_loop:
                    edge['looptheta'] = result.get('looptheta', 30)

                # Update self-loop specific properties
                if is_self_loop:
                    edge['selfloopangle'] = result.get('selfloopangle', 0)
                    edge['selfloopscale'] = result.get('selfloopscale', 1.0)
                    edge['arrowlengthsc'] = result.get('arrowlengthsc', 1.0)
                    edge['flip'] = result.get('flip', False)

                if is_self_loop:
                    print(f"✓ Updated self-loop on node '{from_label}'")
                    # Save self-loop properties for inheritance
                    self.last_selfloop_props = {
                        'linewidth_mult': result['linewidth_mult'],
                        'selfloopangle': result.get('selfloopangle', 0),
                        'selfloopscale': result.get('selfloopscale', 1.0),
                        'flip': result.get('flip', False),
                        'arrowlengthsc': result.get('arrowlengthsc', 1.0)
                    }
                else:
                    print(f"✓ Updated edge '{from_label}' → '{to_label}'")
                    # Save edge properties for inheritance
                    self.last_edge_props = {
                        'linewidth_mult': result['linewidth_mult'],
                        'direction': result['direction'],
                        'looptheta': result.get('looptheta', 30)
                    }
                print(f"  linewidth_mult={edge['linewidth_mult']}, label_size_mult={edge['label_size_mult']}, style={edge['style']}")
                self._update_plot()
        else:
            # User canceled - restore original state
            edge['linewidth_mult'] = original_state['linewidth_mult']
            edge['selfloopangle'] = original_state['selfloopangle']
            edge['selfloopscale'] = original_state['selfloopscale']
            edge['flip'] = original_state['flip']
            self._update_plot()
            print("✗ Edit canceled")

    def _edit_scattering_node_parameters(self, node):
        """Edit scattering parameters for a node via dialog"""

        # Find the original node for assignment storage
        original_node = None
        if hasattr(self, '_original_nodes_for_lookup') and self._original_nodes_for_lookup:
            for orig_node in self._original_nodes_for_lookup:
                if (orig_node['label'] == node['label'] and
                    orig_node['pos'] == node['pos']):
                    original_node = orig_node
                    break

        if not original_node:
            print(f"Could not find original node for '{node['label']}'")
            return

        node_id = id(original_node)
        node_label = node['label']
        if node.get('conj', False):
            node_label += '*'

        # Check if node has self-loop
        has_selfloop = any(
            edge.get('is_self_loop', False) and edge['from_node'] == original_node
            for edge in (self._original_edges_for_lookup if hasattr(self, '_original_edges_for_lookup') else self.edges)
        )

        # Get current assignments
        assignments = self.scattering_assignments.get(node_id, {})

        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Scattering Parameters: Node {node_label}")
        layout = QVBoxLayout()
        dialog.setLayout(layout)

        # Frequency parameter
        freq_layout = QHBoxLayout()
        freq_layout.addWidget(QLabel("freq [a.u.]:"))
        freq_spin = FineControlSpinBox()
        freq_spin.setRange(0.0, 1e6)
        freq_spin.setDecimals(3)
        freq_spin.setSingleStep(0.1)
        freq_spin.setValue(assignments.get('freq', 5.0))
        freq_layout.addWidget(freq_spin)
        layout.addLayout(freq_layout)

        # B_int parameter
        bint_layout = QHBoxLayout()
        bint_layout.addWidget(QLabel("B_int [ma.u.]:"))
        bint_spin = FineControlSpinBox()
        bint_spin.setRange(0.0, 1e6)
        bint_spin.setDecimals(1)
        bint_spin.setSingleStep(0.1)
        bint_spin.setValue(assignments.get('B_int', 1.0))
        bint_layout.addWidget(bint_spin)
        layout.addLayout(bint_layout)

        # B_ext parameter (only if has self-loop)
        bext_spin = None
        if has_selfloop:
            bext_layout = QHBoxLayout()
            bext_layout.addWidget(QLabel("B_ext:"))
            bext_spin = FineControlSpinBox()
            bext_spin.setRange(0.0, 1e6)
            bext_spin.setDecimals(1)
            bext_spin.setSingleStep(0.1)
            bext_spin.setValue(assignments.get('B_ext', 0.5))
            bext_layout.addWidget(bext_spin)
            layout.addLayout(bext_layout)

        # OK/Cancel buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        # Show dialog
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Store assignments
            if node_id not in self.scattering_assignments:
                self.scattering_assignments[node_id] = {}

            self.scattering_assignments[node_id]['freq'] = freq_spin.value()
            self.scattering_assignments[node_id]['B_int'] = bint_spin.value() / 1000 #JAA
            if has_selfloop and bext_spin:
                self.scattering_assignments[node_id]['B_ext'] = bext_spin.value() / 1000 #JAA

            print(f"[Scattering] Updated node '{node_label}' parameters:")
            print(f"  freq={freq_spin.value()}, B_int={bint_spin.value()}" +
                  (f", B_ext={bext_spin.value()}" if has_selfloop and bext_spin else ""))

            # Update the scattering parameter table to reflect changes
            if hasattr(self.properties_panel, '_update_scattering_node_table'):
                self.properties_panel._update_scattering_node_table()

            # Scroll to and highlight the row if scattering tab is visible
            if hasattr(self.properties_panel, '_scroll_to_node_row'):
                self.properties_panel._scroll_to_node_row(original_node)

        # Clear selection to remove red indicator (whether OK or Cancel was clicked)
        self.selected_nodes.clear()
        self.selected_edges.clear()

        # Re-render to update opacity and clear selection indicators
        self._render_scattering_graph()

    def _edit_scattering_edge_parameters(self, edge):
        """Edit scattering parameters for an edge via dialog"""

        # Find the original edge for assignment storage
        original_edge = None
        if hasattr(self, '_original_edges_for_lookup') and self._original_edges_for_lookup:
            from_label = edge['from_node']['label']
            to_label = edge['to_node']['label']
            is_self_loop = edge.get('is_self_loop', False)

            for orig_edge in self._original_edges_for_lookup:
                orig_from_label = orig_edge['from_node']['label']
                orig_to_label = orig_edge['to_node']['label']
                orig_is_self_loop = orig_edge.get('is_self_loop', False)

                if (orig_from_label == from_label and
                    orig_to_label == to_label and
                    orig_is_self_loop == is_self_loop):
                    original_edge = orig_edge
                    break

        if not original_edge:
            print(f"Could not find original edge")
            return

        edge_id = id(original_edge)

        # Build edge label
        from_label = edge['from_node']['label']
        to_label = edge['to_node']['label']
        if edge['from_node'].get('conj', False):
            from_label += '*'
        if edge['to_node'].get('conj', False):
            to_label += '*'
        edge_label = f"{from_label}→{to_label}"

        # Check if this is a chord edge
        edge_key = tuple(sorted([original_edge['from_node_id'], original_edge['to_node_id']]))
        is_chord = edge_key in self.scattering_chord_edges

        # Get current assignments
        assignments = self.scattering_assignments.get(edge_id, {})

        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Scattering Parameters: Edge {edge_label}" + (" (chord)" if is_chord else ""))
        layout = QVBoxLayout()
        dialog.setLayout(layout)

        # f_p parameter (only editable for tree edges)
        fp_spin = None
        if not is_chord:
            fp_layout = QHBoxLayout()
            fp_layout.addWidget(QLabel("f_p [a.u.]:"))
            fp_spin = FineControlSpinBox()
            fp_spin.setRange(0.0, 1e6)
            fp_spin.setDecimals(3)
            fp_spin.setSingleStep(0.1)
            fp_spin.setValue(assignments.get('f_p', 0.0))
            fp_layout.addWidget(fp_spin)
            layout.addLayout(fp_layout)
        else:
            # For chords, show non-editable f_p label
            fp_label_layout = QHBoxLayout()
            fp_label_layout.addWidget(QLabel("f_p [a.u.]: (computed)"))
            layout.addLayout(fp_label_layout)

        # rate parameter
        rate_layout = QHBoxLayout()
        rate_layout.addWidget(QLabel("rate:"))
        rate_spin = FineControlSpinBox()
        rate_spin.setRange(0.0, 1e6)
        rate_spin.setDecimals(1)
        rate_spin.setSingleStep(0.1)
        rate_spin.setValue(assignments.get('rate', 1.0))
        rate_layout.addWidget(rate_spin)
        layout.addLayout(rate_layout)

        # phase parameter
        phase_layout = QHBoxLayout()
        phase_layout.addWidget(QLabel("phase [°]:"))
        phase_spin = FineControlSpinBox()
        phase_spin.setRange(-180.0, 180.0)
        phase_spin.setDecimals(1)
        phase_spin.setSingleStep(5.0)
        phase_spin.setValue(assignments.get('phase', 0.0))
        phase_layout.addWidget(phase_spin)
        layout.addLayout(phase_layout)

        # OK/Cancel buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        # Show dialog
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Store assignments
            if edge_id not in self.scattering_assignments:
                self.scattering_assignments[edge_id] = {}

            if not is_chord and fp_spin:
                self.scattering_assignments[edge_id]['f_p'] = fp_spin.value()
            self.scattering_assignments[edge_id]['rate'] = rate_spin.value() / 1000 #JAA
            self.scattering_assignments[edge_id]['phase'] = phase_spin.value()

            print(f"[Scattering] Updated edge '{edge_label}' parameters:")
            print(f"  " + (f"f_p={fp_spin.value()}, " if not is_chord and fp_spin else "") +
                  f"rate={rate_spin.value()}, phase={phase_spin.value()}")

            # Update the scattering parameter table to reflect changes
            if hasattr(self.properties_panel, '_update_scattering_edge_table'):
                self.properties_panel._update_scattering_edge_table()

            # Scroll to and highlight the row if scattering tab is visible
            if hasattr(self.properties_panel, '_scroll_to_edge_row'):
                self.properties_panel._scroll_to_edge_row(original_edge)

        # Clear selection to remove red indicator (whether OK or Cancel was clicked)
        self.selected_nodes.clear()
        self.selected_edges.clear()

        # Re-render to update opacity and clear selection indicators
        self._render_scattering_graph()

    def _draw_nodes(self):
        """Draw all nodes"""
        # Calculate scaling factor once for all nodes
        fig = self.canvas.fig
        ax = self.canvas.ax
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()

        # Get figure size in inches and pixels
        fig_width_inches = fig.get_figwidth()
        fig_height_inches = fig.get_figheight()

        # Calculate points per data unit using average of x and y to handle aspect ratio
        fig_width_points = fig_width_inches * 72  # 72 points per inch
        fig_height_points = fig_height_inches * 72

        # For GUI: Use actual axis limits so fonts scale with zoom
        # This makes text size relative to nodes consistent when zooming
        data_width = xlim[1] - xlim[0]
        data_height = ylim[1] - ylim[0]
        points_per_data_unit_x = fig_width_points / data_width
        points_per_data_unit_y = fig_height_points / data_height
        # Use minimum to ensure font scales with the tighter dimension
        # This keeps text size consistent relative to nodes regardless of aspect ratio
        points_per_data_unit = min(points_per_data_unit_x, points_per_data_unit_y)

        # Get nodes with duplicate labels for validation
        duplicate_nodes = self._get_nodes_with_duplicate_labels()

        for node in self.nodes:
            # Get size multipliers (default to 1.0 for old nodes without these fields)
            node_size_mult = node.get('node_size_mult', 1.0)
            label_size_mult = node.get('label_size_mult', 1.0)
            conj = node.get('conj', False)

            # Draw circle with size multiplier (no outline, like prettynodes)
            node_radius = self.node_radius * node_size_mult

            # Apply conjugation transparency
            node_alpha = 0.5 if conj else 1.0

            # Apply scattering mode transparency
            if self.canvas == self.scattering_canvas:
                # Check if node is fully assigned - if so, use full opacity
                if self._is_node_fully_assigned(node):
                    node_alpha = 1.0
                else:
                    node_alpha = 0.5

            circle = patches.Circle(
                node['pos'], node_radius,
                facecolor=node['color'],
                edgecolor=node.get('edgecolor', 'none'),  # Support Kron graph styling
                linewidth=4 if node.get('edgecolor') else 0,  # Add visible linewidth for edges
                alpha=node_alpha,
                zorder=10
            )
            self.canvas.ax.add_patch(circle)

            # Draw custom outline if enabled
            if node.get('outline_enabled', False):
                outline_color = node.get('outline_color', config.DEFAULT_NODE_OUTLINE_COLOR)
                outline_width = node.get('outline_width', config.DEFAULT_NODE_OUTLINE_WIDTH)
                outline_alpha = node.get('outline_alpha', config.DEFAULT_NODE_OUTLINE_ALPHA)
                # Convert outline width to display units (similar to how we handle other linewidths)
                outline_linewidth = outline_width
                outline_circle = patches.Circle(
                    node['pos'], node_radius,
                    fill=False,
                    edgecolor=outline_color,
                    linewidth=outline_linewidth,
                    alpha=outline_alpha,
                    zorder=10.5  # Draw on top of filled circle but below labels
                )
                self.canvas.ax.add_patch(outline_circle)

            # Font size should be proportional to node radius
            # Aim for text to be about 35% of node diameter
            # Reduce size by 8% for conjugated nodes to accommodate asterisk
            conj_scale = 0.92 if conj else 1.0
            font_size_points = node_radius * 2 * points_per_data_unit * config.PLOT_NODE_LABEL_FONT_SCALE * label_size_mult * conj_scale

            # Draw label - use bold sans-serif text with proper subscript/superscript handling
            label_text = node['label']

            # Skip drawing label if it's empty or whitespace only
            if not label_text or not label_text.strip():
                continue

            # Format label with bold sans-serif, handling subscripts/superscripts
            # Split on _ and ^ while keeping the delimiters
                parts = re.split(r'([_^])', label_text)

            # Choose font command based on rendering mode
            if self.use_latex:
                # LaTeX with sfmath: just use \mathbf (sfmath provides sans-serif)
                def apply_font(text):
                    return r'\mathbf{' + text + '}'
            else:
                # MathText: use \mathbf{\mathsf{...}} explicitly
                def apply_font(text):
                    return r'\mathbf{\mathsf{' + text + '}}'

            formatted_parts = []
            i = 0
            while i < len(parts):
                if parts[i] in ['_', '^']:
                    # This is a sub/superscript operator
                    formatted_parts.append(parts[i])
                    i += 1
                    if i < len(parts):
                        # Next part is the sub/superscript content
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

            # Add conjugation marker with proper formatting
            if conj:
                # Use asterisk (not superscripted) for conjugation
                formatted_text = rf"${formatted_label}\ast$"
            else:
                formatted_text = rf"${formatted_label}$"

            # For better centering of capital letters:
            # Empirically, for LaTeX math mode bold sans-serif, the visual center
            # is better approximated by using va='center' with a small downward adjustment
            # Math mode adds extra vertical space, so we compensate

            # Small adjustment factor - tune this to improve centering
            # Positive values move text down, negative values move text up
            adjustment_fraction = 0.05  # 5% of font size downward (base)

            vertical_adjustment_points = font_size_points * adjustment_fraction
            vertical_adjustment_data = vertical_adjustment_points / points_per_data_unit

            # Apply label nudge if present
            # Nudge should be relative to the base position, then apply vertical adjustment
            nudge = node.get('nodelabelnudge', (0.0, 0.0))
            label_x = node['pos'][0] + nudge[0]
            label_y = node['pos'][1] + nudge[1] - vertical_adjustment_data

            # Create bbox dict for label background if specified
            self.canvas.ax.text(
                label_x, label_y, formatted_text,
                ha='center', va='center',
                fontsize=font_size_points,
                color=node.get('label_color', config.DEFAULT_NODE_LABEL_COLOR),
                zorder=11
            )

            # Draw selection indicator
            # Draw selection ring first (salmon color)
            if node in self.selected_nodes:
                # Calculate linewidth for selection ring
                selection_linewidth = node_radius * 2 * points_per_data_unit * config.PLOT_SELECTION_LINEWIDTH_SCALE
                selection_ring = patches.Circle(
                    node['pos'], node_radius * config.PLOT_SELECTION_RING_SCALE,
                    fill=False, edgecolor='salmon', linewidth=selection_linewidth,
                    linestyle='-', zorder=12
                )
                self.canvas.ax.add_patch(selection_ring)

            # Draw invalid node indicator (dark red ring for duplicate labels)
            if node in duplicate_nodes:
                # Calculate linewidth for invalid ring
                invalid_linewidth = node_radius * 2 * points_per_data_unit * config.PLOT_INVALID_LINEWIDTH_SCALE
                invalid_ring = patches.Circle(
                    node['pos'], node_radius * config.PLOT_INVALID_RING_SCALE,
                    fill=False, edgecolor='darkred', linewidth=invalid_linewidth,
                    linestyle='-', zorder=13, alpha=0.7
                )
                self.canvas.ax.add_patch(invalid_ring)

            # Draw basis ordering mode indicators
            if self.basis_ordering_mode:
                basis_linewidth = node_radius * 2 * points_per_data_unit * config.PLOT_BASIS_LINEWIDTH_SCALE
                if node in self.basis_order:
                    # Green ring for nodes in basis order
                    basis_ring = patches.Circle(
                        node['pos'], node_radius * config.PLOT_BASIS_RING_SCALE,
                        fill=False, edgecolor='green', linewidth=basis_linewidth,
                        linestyle='-', zorder=14, alpha=0.6
                    )
                    self.canvas.ax.add_patch(basis_ring)
                else:
                    # Dark red ring for unselected nodes (only in basis ordering mode)
                    unselected_ring = patches.Circle(
                        node['pos'], node_radius * config.PLOT_BASIS_RING_SCALE,
                        fill=False, edgecolor='darkred', linewidth=basis_linewidth,
                        linestyle='-', zorder=14, alpha=0.6
                    )
                    self.canvas.ax.add_patch(unselected_ring)

    def _draw_edges(self):
        """Draw all edges and self-loops"""
        import numpy as np

        # Debug: verify this is being called
        # print(f"[DEBUG _draw_edges] Drawing {len(self.edges)} edges")
        # for i, edge in enumerate(self.edges):
        #     from_label = edge['from_node'].get('label', '?')
        #     to_label = edge['to_node'].get('label', '?')
        #     is_selfloop = edge['is_self_loop']
        #     print(f"  Edge {i}: {from_label} -> {to_label}, self_loop={is_selfloop}")

        # Calculate scaling factor for edges (same as nodes)
        fig = self.canvas.fig
        ax = self.canvas.ax
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()

        # Get figure size in points
        fig_width_inches = fig.get_figwidth()
        fig_height_inches = fig.get_figheight()
        fig_width_points = fig_width_inches * 72
        fig_height_points = fig_height_inches * 72

        # Calculate points per data unit
        data_width = xlim[1] - xlim[0]
        data_height = ylim[1] - ylim[0]
        points_per_data_unit_x = fig_width_points / data_width
        points_per_data_unit_y = fig_height_points / data_height
        points_per_data_unit = min(points_per_data_unit_x, points_per_data_unit_y)

        # Base values calibrated for reference view (figsize=12, span~20 units)
        # This gives points_per_data_unit ≈ 43 for that reference
        reference_points_per_data_unit = 43.0

        for edge in self.edges:
            from_node = edge['from_node']
            to_node = edge['to_node']

            if edge['is_self_loop']:
                # Draw self-loop using graph_primitives selfloop function
                from_pos = from_node['pos']
                from_radius = self.node_radius * from_node.get('node_size_mult', 1.0)

                # Scale linewidth proportionally to zoom (base 2.0 at reference zoom)
                base_lw = 2.0
                scaled_lw = base_lw * edge['linewidth_mult'] * (points_per_data_unit / reference_points_per_data_unit)

                # Self-loop parameters following graph_primitives conventions
                selfloopscale = edge.get('selfloopscale', 1.0)
                LOOPYSCALE = 6 * selfloopscale
                selfloopangle = edge.get('selfloopangle', 0)  # Default 0 = right-pointing
                arrowlengthsc = edge.get('arrowlengthsc', 1.0)

                # Calculate loopR based on node radius (matches graph_primitives)
                loopR = from_radius * LOOPYSCALE

                # Calculate arrowlength (matches graph_primitives formula)
                arrowlength = from_radius / 2 * 2.25 / 4 * arrowlengthsc

                # Determine edge color and alpha for scattering mode
                edge_color = edge.get('color', 'black')
                edge_alpha = 1.0
                if self.canvas == self.scattering_canvas:
                    # Check if self-loop (and its node) is fully assigned
                    # For self-loops, we check the node's assignment status
                    node = edge['from_node']
                    if self._is_node_fully_assigned(node):
                        edge_alpha = 1.0
                    else:
                        edge_alpha = 0.5
                    edge_color = edge.get('color', 'black')  # Keep original color

                # Draw the self-loop arc
                gp.selfloop(
                    ax=self.canvas.ax,
                    nodecent=from_pos,
                    R=from_radius * 1.2,  # graph_primitives uses R*1.2
                    baseangle=selfloopangle,
                    dtheta=-34,  # Matches graph_primitives
                    loopR=loopR,
                    arrowlength=arrowlength,
                    lw=scaled_lw,
                    color=edge_color,
                    flip=edge.get('flip', False),
                    alpha=edge_alpha
                )

                # Draw self-loop label manually if present (use label1 for self-loops)
                selfloop_label = edge.get('label1', '')
                if selfloop_label and selfloop_label.strip():
                    # Calculate label position based on selfloopangle
                    # Match graph_primitives: Ranchor = 3.2 * R where R is the node radius
                    # Position is in data coordinates and should be zoom-independent
                    # GUI needs a scaling adjustment to match exported rendering (tunable in Export Scaling tab)
                    GUI_SELFLOOP_LABEL_SCALE = self.export_rescale.get('GUI_SELFLOOP_LABEL_SCALE', 1.5)
                    Ranchor = 3.2 * from_radius * GUI_SELFLOOP_LABEL_SCALE
                    label_x = from_pos[0] + 1.05 * Ranchor * np.cos(selfloopangle * np.pi / 180)
                    label_y = from_pos[1] + 1.05 * Ranchor * np.sin(selfloopangle * np.pi / 180)

                    # Apply nudge if present
                    nudge = edge.get('selflooplabelnudge', (0.0, 0.0))
                    label_x += nudge[0]
                    label_y += nudge[1]

                    # Auto-enclose label with $ signs for math mode
                    if not selfloop_label.startswith('$'):
                        formatted_label = f'${selfloop_label}$'
                    else:
                        formatted_label = selfloop_label

                    # Scale font size
                    base_font_size = 12
                    scaled_font_size = base_font_size * edge['label_size_mult'] * (points_per_data_unit / reference_points_per_data_unit)

                    # Create bbox for label background if specified
                    bbox_props = None
                    if edge.get('label_bgcolor'):
                        bbox_props = dict(boxstyle='round,pad=0.1',
                                        facecolor=edge['label_bgcolor'],
                                        edgecolor='none',
                                        alpha=1.0)

                    self.canvas.ax.text(
                        label_x, label_y, formatted_label,
                        fontsize=scaled_font_size,
                        color=edge.get('label_color', 'black'),
                        ha='center', va='center',
                        bbox=bbox_props,
                        zorder=20,
                        usetex=self.use_latex
                    )

                # Calculate the Bezier curve control points (matching graph_primitives selfloop)
                dtheta = -34  # Matches graph_primitives
                R_node = from_radius * 1.2  # Node radius for selfloop attachment

                # Start and end points on the node circle
                theta_start = selfloopangle + dtheta
                theta_end = selfloopangle - dtheta
                v_start = [from_pos[0] + R_node * np.cos(theta_start * np.pi / 180),
                          from_pos[1] + R_node * np.sin(theta_start * np.pi / 180)]
                v_end = [from_pos[0] + R_node * np.cos(theta_end * np.pi / 180),
                        from_pos[1] + R_node * np.sin(theta_end * np.pi / 180)]

                # Bezier control points (perpendicular to node, extending by loopR/2)
                bz_start = [v_start[0] + loopR/2 * np.cos(theta_start * np.pi / 180),
                           v_start[1] + loopR/2 * np.sin(theta_start * np.pi / 180)]
                bz_end = [v_end[0] + loopR/2 * np.cos(theta_end * np.pi / 180),
                         v_end[1] + loopR/2 * np.sin(theta_end * np.pi / 180)]

                # Calculate apex of bezier curve at t=0.5 for selection indicator
                # For cubic Bezier: B(t) = (1-t)³P0 + 3(1-t)²t*P1 + 3(1-t)t²P2 + t³P3
                t = 0.5
                apex_x = ((1-t)**3 * v_start[0] +
                         3*(1-t)**2*t * bz_start[0] +
                         3*(1-t)*t**2 * bz_end[0] +
                         t**3 * v_end[0])
                apex_y = ((1-t)**3 * v_start[1] +
                         3*(1-t)**2*t * bz_start[1] +
                         3*(1-t)*t**2 * bz_end[1] +
                         t**3 * v_end[1])

                # Draw selection indicator for selected self-loops
                if edge in self.selected_edges:
                    # Place indicator at 75% along the bezier curve from node center
                    apex_dist_from_center = np.sqrt((apex_x - from_pos[0])**2 + (apex_y - from_pos[1])**2)
                    indicator_distance = apex_dist_from_center * 0.75
                    apex_angle = np.arctan2(apex_y - from_pos[1], apex_x - from_pos[0])
                    indicator_x = from_pos[0] + indicator_distance * np.cos(apex_angle)
                    indicator_y = from_pos[1] + indicator_distance * np.sin(apex_angle)

                    selection_circle = patches.Circle(
                        (indicator_x, indicator_y), from_radius * 0.3,
                        facecolor='lightcoral',
                        edgecolor='red',
                        linewidth=2,
                        zorder=25
                    )
                    self.canvas.ax.add_patch(selection_circle)
            else:
                # Draw edge using graph_primitives edge function
                from_pos = from_node['pos']
                to_pos = to_node['pos']
                from_radius = self.node_radius * from_node.get('node_size_mult', 1.0)
                to_radius = self.node_radius * to_node.get('node_size_mult', 1.0)

                # Calculate angle from from_node to to_node
                dx = to_pos[0] - from_pos[0]
                dy = to_pos[1] - from_pos[1]
                labeltheta = np.arctan2(dy, dx) * 180 / np.pi

                # Flip labels by 180 degrees if requested
                if edge.get('flip_labels', False):
                    labeltheta += 180

                # Add fine-tuning rotation offset
                labeltheta += edge.get('label_rotation_offset', 0)

                # Debug: print edge positions
                # from_label = from_node.get('label', '?')
                # to_label = to_node.get('label', '?')
                # print(f"  Edge {from_label}→{to_label}: from={from_pos}, to={to_pos}, angle={labeltheta:.1f}°, flip={flip}")

                # Scale linewidth proportionally to zoom (base 5.5 at reference zoom)
                base_lw = 2.0
                linewidth_mult = edge.get('linewidth_mult', 1.0)
                scaled_lw = base_lw * linewidth_mult * (points_per_data_unit / reference_points_per_data_unit)

                # Edge label font size - graph_primitives will scale it based on points_per_data_unit
                # We just pass the multiplier (labelfontsize acts as a multiplier in graph_primitives)
                base_labelfontsize = config.PLOT_EDGE_LABEL_BASE_FONTSIZE
                label_size_mult = edge.get('label_size_mult', 1.0)
                scaled_labelfontsize = base_labelfontsize * label_size_mult
                # NOTE: DO NOT scale by points_per_data_unit here - graph_primitives does this internally!

                # Debug: print edge properties (comment out later)
                # print(f"Drawing edge: lw_mult={linewidth_mult}, label_mult={label_size_mult}, style={edge.get('style')}")

                # Scale label offset (base 2.3 at reference zoom)
                base_labeloffset = 2.3
                scaled_labeloffset = base_labeloffset * edge.get('label_offset_mult', 1.0)

                # Format labels with math mode if they contain backslash
                label1_text = edge.get('label1', '')
                label2_text = edge.get('label2', '')

                # Add math mode if not already present
                if label1_text and not label1_text.startswith('$'):
                    label1_text = f'${label1_text}$'
                if label2_text and not label2_text.startswith('$'):
                    label2_text = f'${label2_text}$'

                # Convert empty strings to None for graph_primitives
                label1_formatted = label1_text if label1_text else None
                label2_formatted = label2_text if label2_text else None

                # Adjust linewidth for single/double styles (they multiply by 3.5x and 7x respectively)
                # Since graph_primitives only multiplies if 'lw' is NOT in loopkwargs,
                # we need to pre-multiply when passing 'lw' ourselves
                style = edge['style']
                single_double_lw_unit = 3.0
                if style == 'single':
                    final_lw = scaled_lw * single_double_lw_unit
                elif style == 'double':
                    final_lw = scaled_lw * 2. * single_double_lw_unit
                else:  # loopy
                    final_lw = scaled_lw

                # Determine edge color and alpha for scattering mode
                edge_color = edge.get('color', 'black')
                edge_alpha = 1.0
                if self.canvas == self.scattering_canvas:
                    # Check if this edge is a tree or chord edge
                    edge_key = tuple(sorted([edge['from_node_id'], edge['to_node_id']]))
                    if edge_key in self.scattering_tree_edges:
                        # Tree edge: check if fully assigned
                        if self._is_edge_fully_assigned(edge):
                            edge_alpha = 1.0
                        else:
                            edge_alpha = 0.5
                    elif edge_key in self.scattering_chord_edges:
                        # Chord edge: check if fully assigned (rate & phase)
                        if self._is_edge_fully_assigned(edge):
                            edge_alpha = 1.0
                        else:
                            edge_alpha = 0.5
                        edge_color = 'steelblue'

                gp.edge(
                    ax=self.canvas.ax,
                    nodexy=[from_pos, to_pos],
                    nodeR=[from_radius, to_radius],
                    label=[label1_formatted, label2_formatted],
                    labeltheta=labeltheta,
                    labeloffset=scaled_labeloffset,
                    labelfontsize=scaled_labelfontsize,
                    labelbgcolor=[edge.get('label1_bgcolor', None), edge.get('label2_bgcolor', None)],
                    style=style,
                    whichedges=edge['direction'],
                    theta=edge.get('looptheta', 30),  # Looptheta parameter (adjustable via Ctrl+Left/Right)
                    loopkwargs={'lw': final_lw, 'arrowlength': 0.4, 'color': edge_color, 'alpha': edge_alpha}  # Add arrowheads, color, and alpha
                )

                # Draw selection indicator for selected edges
                if edge in self.selected_edges:
                    mid_x = (from_pos[0] + to_pos[0]) / 2
                    mid_y = (from_pos[1] + to_pos[1]) / 2
                    # Draw a small circle at the edge midpoint
                    selection_circle = patches.Circle(
                        (mid_x, mid_y), 0.3,
                        facecolor='lightcoral',
                        edgecolor='red',
                        linewidth=2,
                        zorder=20
                    )
                    self.canvas.ax.add_patch(selection_circle)

    def _on_motion(self, event):
        """Handle mouse motion"""
        # Check if event came from main canvas, scattering canvas, or kron canvas
        valid_axes = [self.canvas.ax, self.kron_canvas.ax]
        if hasattr(self, 'scattering_canvas') and self.scattering_canvas:
            valid_axes.append(self.scattering_canvas.ax)

        if event.inaxes not in valid_axes:
            return

        # Check for pending drag - activate if motion threshold exceeded
        if (self.drag_pending_node or self.drag_pending_group) and self.drag_start_pos is not None:
            dx = event.xdata - self.drag_start_pos[0]
            dy = event.ydata - self.drag_start_pos[1]
            distance = np.sqrt(dx**2 + dy**2)

            if distance > self.drag_threshold:
                # Activate dragging
                if self.drag_pending_group:
                    self.dragging_group = True
                    self.drag_pending_group = False
                    print(f"Dragging {len(self.selected_nodes)} node(s)...")
                elif self.drag_pending_node:
                    self.dragging_node = self.drag_pending_node
                    self.drag_pending_node = None
                    print(f"Dragging node '{self.dragging_node['label']}'...")
                # Fall through to dragging handling below

        # Handle panning
        if self.panning and self.pan_start is not None:
            dx = event.xdata - self.pan_start[0]
            dy = event.ydata - self.pan_start[1]

            # Determine which canvas is being panned
            if hasattr(self, 'scattering_canvas') and self.scattering_canvas and event.inaxes == self.scattering_canvas.ax:
                # Panning Scattering canvas
                if hasattr(self, 'scattering_original_base_xlim'):
                    self.scattering_original_base_xlim = (self.scattering_original_base_xlim[0] - dx,
                                                           self.scattering_original_base_xlim[1] - dx)
                    self.scattering_original_base_ylim = (self.scattering_original_base_ylim[0] - dy,
                                                           self.scattering_original_base_ylim[1] - dy)

                    # Temporarily swap base limits to calculate Scattering canvas limits
                    saved_base_xlim = self.base_xlim
                    saved_base_ylim = self.base_ylim
                    self.base_xlim = self.scattering_original_base_xlim
                    self.base_ylim = self.scattering_original_base_ylim

                    # Update the Scattering canvas view using the standard methods
                    self.scattering_canvas.ax.set_xlim(*self._get_xlim())
                    self.scattering_canvas.ax.set_ylim(*self._get_ylim())
                    self.scattering_canvas.draw_idle()

                    # Restore original base limits
                    self.base_xlim = saved_base_xlim
                    self.base_ylim = saved_base_ylim
            elif event.inaxes == self.kron_canvas.ax:
                # Panning Kron canvas
                if hasattr(self, 'kron_original_base_xlim'):
                    self.kron_original_base_xlim = (self.kron_original_base_xlim[0] - dx,
                                                     self.kron_original_base_xlim[1] - dx)
                    self.kron_original_base_ylim = (self.kron_original_base_ylim[0] - dy,
                                                     self.kron_original_base_ylim[1] - dy)

                    # Temporarily swap base limits to calculate Kron canvas limits
                    saved_base_xlim = self.base_xlim
                    saved_base_ylim = self.base_ylim
                    self.base_xlim = self.kron_original_base_xlim
                    self.base_ylim = self.kron_original_base_ylim

                    # Update the Kron canvas view using the standard methods
                    self.kron_canvas.ax.set_xlim(*self._get_xlim())
                    self.kron_canvas.ax.set_ylim(*self._get_ylim())
                    self.kron_canvas.draw_idle()

                    # Restore original base limits
                    self.base_xlim = saved_base_xlim
                    self.base_ylim = saved_base_ylim
            else:
                # Panning main canvas
                self.base_xlim = (self.base_xlim[0] - dx, self.base_xlim[1] - dx)
                self.base_ylim = (self.base_ylim[0] - dy, self.base_ylim[1] - dy)
                # Update main canvas view
                self.canvas.ax.set_xlim(*self._get_xlim())
                self.canvas.ax.set_ylim(*self._get_ylim())
                self.canvas.draw_idle()

            # Keep pan_start fixed in world coordinates for smoother panning
            # (don't update pan_start)
            return

        # Handle selection window drawing
        if self.selection_window and self.selection_window_start is not None:
            # Remove old rectangle
            if self.selection_window_rect:
                try:
                    self.selection_window_rect.remove()
                except:
                    pass

            # Draw new rectangle
            x0, y0 = self.selection_window_start
            width = event.xdata - x0
            height = event.ydata - y0

            self.selection_window_rect = patches.Rectangle(
                (x0, y0), width, height,
                fill=False, edgecolor='darkgray', linestyle=':', linewidth=1.5, zorder=20,
            )
            self.canvas.ax.add_patch(self.selection_window_rect)
            self.canvas.draw_idle()
            return

        # Handle zoom window drawing
        if self.zoom_window and self.zoom_window_start is not None:
            # Remove old rectangle
            if self.zoom_window_rect:
                try:
                    self.zoom_window_rect.remove()
                except:
                    pass

            # Draw new rectangle
            x0, y0 = self.zoom_window_start
            width = event.xdata - x0
            height = event.ydata - y0

            self.zoom_window_rect = patches.Rectangle(
                (x0, y0), width, height,
                fill=False, edgecolor='slategray', linestyle='--', linewidth=1, zorder=19,
            )
            # Draw on the canvas where the event occurred
            if hasattr(self, 'scattering_canvas') and self.scattering_canvas and event.inaxes == self.scattering_canvas.ax:
                self.scattering_canvas.ax.add_patch(self.zoom_window_rect)
                self.scattering_canvas.draw_idle()
            elif event.inaxes == self.kron_canvas.ax and hasattr(self, 'kron_graph') and self.kron_graph:
                self.kron_canvas.ax.add_patch(self.zoom_window_rect)
                self.kron_canvas.draw_idle()
            else:
                self.canvas.ax.add_patch(self.zoom_window_rect)
                self.canvas.draw_idle()
            return

        # Handle group dragging
        if self.dragging_group and self.drag_start_pos is not None:
            # Calculate offset from drag start
            dx = event.xdata - self.drag_start_pos[0]
            dy = event.ydata - self.drag_start_pos[1]

            # Remove old previews
            for patch in self.drag_preview_patches:
                try:
                    patch.remove()
                except:
                    pass
            for text in self.drag_preview_texts:
                try:
                    text.remove()
                except:
                    pass
            for outline in self.drag_preview_outlines:
                try:
                    outline.remove()
                except:
                    pass
            self.drag_preview_patches.clear()
            self.drag_preview_texts.clear()
            self.drag_preview_outlines.clear()

            # Determine which canvas/nodes to use
            if event.inaxes == self.kron_canvas.ax and hasattr(self, 'kron_graph') and self.kron_graph:
                target_canvas = self.kron_canvas
                target_nodes = self.kron_graph['nodes']
            else:
                target_canvas = self.canvas
                target_nodes = self.nodes

            # Draw preview for each selected node
            any_occupied = False
            for node in self.selected_nodes:
                new_x = node['pos'][0] + dx
                new_y = node['pos'][1] + dy
                snap_x, snap_y = self._snap_to_grid(new_x, new_y)

                # Check if occupied by non-selected node
                occupied = any(
                    other_node not in self.selected_nodes and
                    np.isclose(other_node['pos'][0], snap_x, atol=0.01) and
                    np.isclose(other_node['pos'][1], snap_y, atol=0.01)
                    for other_node in target_nodes
                )
                any_occupied = any_occupied or occupied

                # Ghost appearance: use semi-transparent fill
                color = 'red' if occupied else 'lightblue'
                node_size_mult = node.get('node_size_mult', 1.0)

                preview_patch = patches.Circle(
                    (snap_x, snap_y), self.node_radius * node_size_mult,
                    fill=True, facecolor=color, edgecolor='gray',
                    linestyle=':', linewidth=1.5, alpha=0.5, zorder=15
                )
                target_canvas.ax.add_patch(preview_patch)
                self.drag_preview_patches.append(preview_patch)

                preview_text = target_canvas.ax.text(
                    snap_x, snap_y, node['label'],
                    ha='center', va='center', fontsize=14, color='gray', alpha=0.7, zorder=16
                )
                self.drag_preview_texts.append(preview_text)

            target_canvas.draw_idle()
            return

        # Handle single node dragging
        if self.dragging_node is not None:
            snap_x, snap_y = self._snap_to_grid(event.xdata, event.ydata)

            # Determine which canvas/nodes to use
            if event.inaxes == self.kron_canvas.ax and hasattr(self, 'kron_graph') and self.kron_graph:
                target_canvas = self.kron_canvas
                target_nodes = self.kron_graph['nodes']
            else:
                target_canvas = self.canvas
                target_nodes = self.nodes

            # Check if occupied by another node
            occupied = any(
                node != self.dragging_node and
                np.isclose(node['pos'][0], snap_x, atol=0.01) and
                np.isclose(node['pos'][1], snap_y, atol=0.01)
                for node in target_nodes
            )

            # Remove old preview
            for patch in self.drag_preview_patches:
                try:
                    patch.remove()
                except:
                    pass
            for text in self.drag_preview_texts:
                try:
                    text.remove()
                except:
                    pass
            for outline in self.drag_preview_outlines:
                try:
                    outline.remove()
                except:
                    pass
            self.drag_preview_patches.clear()
            self.drag_preview_texts.clear()
            self.drag_preview_outlines.clear()

            # Draw preview with actual node appearance
            node = self.dragging_node
            node_size_mult = node.get('node_size_mult', 1.0)
            ghost_radius = self.node_radius * node_size_mult
            ghost_alpha = 0.5

            if occupied:
                # Position occupied - show red warning circle
                preview_patch = patches.Circle(
                    (snap_x, snap_y), ghost_radius,
                    fill=True, facecolor='red', edgecolor='darkred',
                    linestyle=':', linewidth=2, alpha=ghost_alpha, zorder=15
                )
                target_canvas.ax.add_patch(preview_patch)
                self.drag_preview_patches.append(preview_patch)
            else:
                # Position available - show actual node appearance
                preview_patch = patches.Circle(
                    (snap_x, snap_y), ghost_radius,
                    fill=True, facecolor=node['color'], edgecolor='gray',
                    linestyle=':', linewidth=1, alpha=ghost_alpha, zorder=15
                )
                target_canvas.ax.add_patch(preview_patch)
                self.drag_preview_patches.append(preview_patch)

                # Draw outline preview if enabled
                if node.get('outline_enabled', False):
                    outline_patch = patches.Circle(
                        (snap_x, snap_y), ghost_radius,
                        fill=False, edgecolor=node.get('outline_color', 'black'),
                        linewidth=node.get('outline_width', config.DEFAULT_NODE_OUTLINE_WIDTH),
                        alpha=node.get('outline_alpha', 1.0) * ghost_alpha,
                        linestyle=':', zorder=15.5
                    )
                    target_canvas.ax.add_patch(outline_patch)
                    self.drag_preview_outlines.append(outline_patch)

                # Format label text with same bold sans-serif styling as actual nodes
                label_text = node['label']
                conj = node.get('conj', False)

                # Choose font command based on rendering mode
                if self.use_latex:
                    def apply_font(text):
                        return r'\mathbf{' + text + '}'
                else:
                    def apply_font(text):
                        return r'\mathbf{\mathsf{' + text + '}}'

                # Handle subscripts/superscripts
                        parts = re.split(r'([_^])', label_text)

                formatted_parts = []
                i = 0
                while i < len(parts):
                    if parts[i] in ['_', '^']:
                        formatted_parts.append(parts[i])
                        i += 1
                        if i < len(parts):
                            content = parts[i]
                            if content.startswith('{') and content.endswith('}'):
                                inner = content[1:-1]
                                formatted_parts.append('{' + apply_font(inner) + '}')
                            else:
                                formatted_parts.append(apply_font(content))
                            i += 1
                    elif parts[i]:
                        formatted_parts.append(apply_font(parts[i]))
                        i += 1
                    else:
                        i += 1

                formatted_label = ''.join(formatted_parts)

                # Add conjugation marker if applicable
                if conj:
                    display_text = rf"${formatted_label}\ast$"
                else:
                    display_text = rf"${formatted_label}$"

                # Calculate font size proportional to node radius
                fig = target_canvas.fig
                ax = target_canvas.ax
                xlim = ax.get_xlim()
                fig_width_points = fig.get_figwidth() * 72
                data_width = xlim[1] - xlim[0]
                points_per_data_unit = fig_width_points / data_width

                label_size_mult = node.get('label_size_mult', 1.0)
                conj_scale = 0.92 if conj else 1.0
                font_size = ghost_radius * 2 * points_per_data_unit * config.PLOT_NODE_LABEL_FONT_SCALE * label_size_mult * conj_scale

                preview_text = target_canvas.ax.text(
                    snap_x, snap_y, display_text,
                    ha='center', va='center', fontsize=font_size,
                    color='white', alpha=0.8, zorder=16
                )
                self.drag_preview_texts.append(preview_text)

            target_canvas.draw_idle()
            return

        # Handle node placement preview
        if self.placement_mode not in ['single', 'continuous', 'continuous_duplicate']:
            return

        snap_x, snap_y = self._snap_to_grid(event.xdata, event.ydata)

        # Check if occupied
        occupied = any(
            np.isclose(node['pos'][0], snap_x, atol=0.01) and
            np.isclose(node['pos'][1], snap_y, atol=0.01)
            for node in self.nodes
        )

        # Remove old preview elements
        if self.preview_patch:
            try:
                self.preview_patch.remove()
            except:
                pass

        if self.preview_text:
            try:
                self.preview_text.remove()
            except:
                pass

        if self.preview_outline:
            try:
                self.preview_outline.remove()
            except:
                pass

        # Get predicted properties for the next node
        ghost_props = self._get_ghost_node_properties()

        # Calculate node radius with size multiplier
        ghost_radius = self.node_radius * ghost_props['node_size_mult']

        # Ghost preview alpha (reduced from normal to indicate it's a preview)
        ghost_alpha = 0.5

        # Draw preview - use actual color when not occupied, red when occupied
        if occupied:
            # Position occupied - show red warning circle
            self.preview_patch = patches.Circle(
                (snap_x, snap_y), ghost_radius,
                fill=True, facecolor='red', edgecolor='darkred',
                linestyle=':', linewidth=2, zorder=15, alpha=ghost_alpha
            )
            self.canvas.ax.add_patch(self.preview_patch)
            self.preview_outline = None
        else:
            # Position available - show actual node appearance
            self.preview_patch = patches.Circle(
                (snap_x, snap_y), ghost_radius,
                fill=True, facecolor=ghost_props['color'], edgecolor='gray',
                linestyle=':', linewidth=1, zorder=15, alpha=ghost_alpha
            )
            self.canvas.ax.add_patch(self.preview_patch)

            # Draw outline preview if enabled
            if ghost_props['outline_enabled']:
                self.preview_outline = patches.Circle(
                    (snap_x, snap_y), ghost_radius,
                    fill=False, edgecolor=ghost_props['outline_color'],
                    linewidth=ghost_props['outline_width'],
                    alpha=ghost_props['outline_alpha'] * ghost_alpha,
                    linestyle=':', zorder=15.5
                )
                self.canvas.ax.add_patch(self.preview_outline)
            else:
                self.preview_outline = None

            # Format label text with same bold sans-serif styling as actual nodes
            label_text = ghost_props['label']

            # Choose font command based on rendering mode (same as _draw_nodes)
            if self.use_latex:
                def apply_font(text):
                    return r'\mathbf{' + text + '}'
            else:
                def apply_font(text):
                    return r'\mathbf{\mathsf{' + text + '}}'

            # Handle subscripts/superscripts (same logic as _draw_nodes)
                parts = re.split(r'([_^])', label_text)

            formatted_parts = []
            i = 0
            while i < len(parts):
                if parts[i] in ['_', '^']:
                    formatted_parts.append(parts[i])
                    i += 1
                    if i < len(parts):
                        content = parts[i]
                        if content.startswith('{') and content.endswith('}'):
                            inner = content[1:-1]
                            formatted_parts.append('{' + apply_font(inner) + '}')
                        else:
                            formatted_parts.append(apply_font(content))
                        i += 1
                elif parts[i]:
                    formatted_parts.append(apply_font(parts[i]))
                    i += 1
                else:
                    i += 1

            formatted_label = ''.join(formatted_parts)

            # Add conjugation marker if applicable
            if ghost_props['conj']:
                display_text = rf"${formatted_label}\ast$"
            else:
                display_text = rf"${formatted_label}$"

            # Calculate font size proportional to node radius (similar to _draw_nodes)
            # Use a simplified calculation for the preview
            fig = self.canvas.fig
            ax = self.canvas.ax
            xlim = ax.get_xlim()
            fig_width_points = fig.get_figwidth() * 72
            data_width = xlim[1] - xlim[0]
            points_per_data_unit = fig_width_points / data_width

            conj_scale = 0.92 if ghost_props['conj'] else 1.0
            font_size = ghost_radius * 2 * points_per_data_unit * config.PLOT_NODE_LABEL_FONT_SCALE * ghost_props['label_size_mult'] * conj_scale

            self.preview_text = self.canvas.ax.text(
                snap_x, snap_y, display_text,
                ha='center', va='center', fontsize=font_size,
                color='white', alpha=0.8, zorder=16
            )

        self.canvas.draw_idle()

    def _on_click(self, event):
        """Handle mouse click"""
        # Check if event came from main canvas, scattering canvas, or kron canvas
        valid_axes = [self.canvas.ax, self.kron_canvas.ax]
        if hasattr(self, 'scattering_canvas') and self.scattering_canvas:
            valid_axes.append(self.scattering_canvas.ax)

        if event.inaxes not in valid_axes:
            return

        # Middle button - start panning
        if event.button == 2:
            self.panning = True
            self.pan_start = (event.xdata, event.ydata)
            return

        # Right button - show context menu if on node/edge, otherwise start zoom window
        if event.button == 3:
            clicked_node = self._find_node_at_position(event.xdata, event.ydata)
            if clicked_node:
                # Show context menu for color selection
                self._show_color_context_menu(event, clicked_node)
                return

            clicked_edge = self._find_edge_at_position(event.xdata, event.ydata)
            if clicked_edge:
                # Show context menu for edge width selection
                self._show_edge_context_menu(event, clicked_edge)
                return

            # Start zoom window if not on node or edge
            self.zoom_window = True
            self.zoom_window_start = (event.xdata, event.ydata)
            return

        # Left button - node placement, editing, dragging, or selection
        if event.button == 1:
            # Check for double-click on node (for editing)
            current_time = time.time()
            clicked_node = None

            # Use Qt's keyboard modifiers for reliable Shift/Ctrl detection
            modifiers = QApplication.keyboardModifiers()
            shift_pressed = modifiers & Qt.ShiftModifier
            ctrl_pressed = modifiers & Qt.ControlModifier

            # Basis ordering mode - select nodes in order
            if self.basis_ordering_mode:
                clicked_node = self._find_node_at_position(event.xdata, event.ydata)
                if clicked_node:
                    if clicked_node in self.basis_order:
                        print(f"Node '{clicked_node['label']}' is already in basis order")
                    else:
                        # Clear redo stack when making a new selection
                        self.basis_order_undo_stack.clear()
                        self.basis_order.append(clicked_node)
                        print(f"Added '{clicked_node['label']}' to basis (position {len(self.basis_order)})")
                        self._update_plot()
                        self.properties_panel._update_basis_display()
                return

            # Kron reduction mode - toggle node selection (keep vs eliminate)
            if self.kron_mode:
                clicked_node = self._find_node_at_position(event.xdata, event.ydata)
                if clicked_node:
                    if clicked_node in self.kron_selected_nodes:
                        # Deselect: will be eliminated
                        self.kron_selected_nodes.remove(clicked_node)
                        print(f"Deselected '{clicked_node['label']}' - will be ELIMINATED")
                    else:
                        # Select: will be kept
                        self.kron_selected_nodes.append(clicked_node)
                        print(f"Selected '{clicked_node['label']}' - will be KEPT")

                    # Enable/disable commit action based on whether at least one node is selected
                    self.commit_kron_action.setEnabled(len(self.kron_selected_nodes) > 0)

                    self._update_plot()
                    # Update Kron matrix display and basis display
                    self.properties_panel._update_kron_matrix_display()
                    self.properties_panel._update_basis_display()
                return

            # Conjugation mode - toggle conjugation on clicked nodes (handle before other modes)
            if self.placement_mode == 'conjugation':
                clicked_node = self._find_node_at_position(event.xdata, event.ydata)
                if clicked_node:
                    self._save_state()
                    # Toggle conjugation state
                    clicked_node['conj'] = not clicked_node.get('conj', False)
                    conj_state = "conjugated" if clicked_node['conj'] else "unconjugated"
                    print(f"Node '{clicked_node['label']}' is now {conj_state}")
                    # Update edge styles for edges connected to this node
                    self._update_edge_styles_for_node(clicked_node)
                    # Update conjugate pair constraints (may create or dissolve constraint groups)
                    self._update_conjugate_pair_constraints()
                    self._update_plot()
                return

            # Edge mode - connect two nodes
            if self.placement_mode in ['edge', 'edge_continuous']:
                clicked_node = self._find_node_at_position(event.xdata, event.ydata)
                if clicked_node:
                    if self.edge_mode_first_node is None:
                        # First node selected
                        self.edge_mode_first_node = clicked_node
                        print(f"First node selected: '{clicked_node['label']}'. Click another node to connect.")
                        self._update_plot()
                    else:
                        # Second node selected - show dialog or use last settings
                        second_node = clicked_node
                        is_self_loop = (self.edge_mode_first_node == second_node)

                        # Determine style based on conjugation (always auto-determined)
                        node1_conj = self.edge_mode_first_node.get('conj', False)
                        node2_conj = second_node.get('conj', False)
                        same_conj = (node1_conj == node2_conj)
                        style = 'single' if same_conj else 'double'

                        if is_self_loop:
                            # Self-loop: inherit from last_selfloop_props if available
                            if self.last_selfloop_props:
                                result = {
                                    'label1': '',
                                    'label2': '',
                                    'linewidth_mult': self.last_selfloop_props.get('linewidth_mult', config.DEFAULT_EDGE_LINEWIDTH_MULT),
                                    'label_size_mult': 1.0,
                                    'label_offset_mult': 1.0,
                                    'style': 'loopy',
                                    'direction': 'both',
                                    'flip_labels': False,
                                    'looptheta': 30,
                                    'selfloopangle': self.last_selfloop_props.get('selfloopangle', config.DEFAULT_SELFLOOP_ANGLE),
                                    'selfloopscale': self.last_selfloop_props.get('selfloopscale', config.DEFAULT_SELFLOOP_SCALE),
                                    'flip': self.last_selfloop_props.get('flip', config.DEFAULT_SELFLOOP_FLIP),
                                    'arrowlengthsc': self.last_selfloop_props.get('arrowlengthsc', config.DEFAULT_SELFLOOP_ARROWLENGTH)
                                }
                            else:
                                # Use defaults for first self-loop
                                result = {
                                    'label1': '',
                                    'label2': '',
                                    'linewidth_mult': config.DEFAULT_EDGE_LINEWIDTH_MULT,
                                    'label_size_mult': 1.0,
                                    'label_offset_mult': 1.0,
                                    'style': 'loopy',
                                    'direction': 'both',
                                    'flip_labels': False,
                                    'looptheta': 30,
                                    'selfloopangle': config.DEFAULT_SELFLOOP_ANGLE,
                                    'selfloopscale': config.DEFAULT_SELFLOOP_SCALE,
                                    'flip': config.DEFAULT_SELFLOOP_FLIP,
                                    'arrowlengthsc': config.DEFAULT_SELFLOOP_ARROWLENGTH
                                }
                            # Store for next self-loop
                            self.last_selfloop_props = result.copy()
                        else:
                            # Regular edge: inherit from last_edge_props if available
                            if self.last_edge_props:
                                result = {
                                    'label1': '',
                                    'label2': '',
                                    'linewidth_mult': self.last_edge_props.get('linewidth_mult', config.DEFAULT_EDGE_LINEWIDTH_MULT),
                                    'label_size_mult': 1.0,
                                    'label_offset_mult': 1.0,
                                    'style': style,  # Auto-determined from conjugation
                                    'direction': self.last_edge_props.get('direction', EdgeInputDialog.last_direction),
                                    'flip_labels': False,
                                    'looptheta': self.last_edge_props.get('looptheta', 30),
                                    'selfloopangle': None,
                                    'selfloopscale': None,
                                    'flip': None,
                                    'arrowlengthsc': 1.0
                                }
                            else:
                                # Use defaults for first edge
                                result = {
                                    'label1': '',
                                    'label2': '',
                                    'linewidth_mult': config.DEFAULT_EDGE_LINEWIDTH_MULT,
                                    'label_size_mult': 1.0,
                                    'label_offset_mult': 1.0,
                                    'style': style,  # Auto-determined from conjugation
                                    'direction': EdgeInputDialog.last_direction,
                                    'flip_labels': False,
                                    'looptheta': 30,
                                    'selfloopangle': None,
                                    'selfloopscale': None,
                                    'flip': None,
                                    'arrowlengthsc': 1.0
                                }
                            # Store for next regular edge
                            self.last_edge_props = result.copy()

                        if result:
                            self._save_state()

                            # Override style based on current node conjugation states
                            # (important for continuous mode and when conjugation changes)
                            if not is_self_loop:
                                node1_conj = self.edge_mode_first_node.get('conj', False)
                                node2_conj = second_node.get('conj', False)
                                same_conj = (node1_conj == node2_conj)
                                result['style'] = 'single' if same_conj else 'double'

                            # Check if edge already exists between these nodes (in either direction)
                            existing_edge = None
                            for edge in self.edges:
                                # Check both directions for regular edges
                                if not is_self_loop:
                                    if ((edge['from_node_id'] == self.edge_mode_first_node['node_id'] and
                                         edge['to_node_id'] == second_node['node_id']) or
                                        (edge['from_node_id'] == second_node['node_id'] and
                                         edge['to_node_id'] == self.edge_mode_first_node['node_id'])):
                                        existing_edge = edge
                                        break
                                # Check for existing self-loop
                                else:
                                    if (edge['is_self_loop'] and
                                        edge['from_node_id'] == self.edge_mode_first_node['node_id']):
                                        existing_edge = edge
                                        break

                            # Update existing edge or create new one
                            if existing_edge:
                                # Replace existing edge properties
                                existing_edge['from_node'] = self.edge_mode_first_node
                                existing_edge['to_node'] = second_node
                                existing_edge['from_node_id'] = self.edge_mode_first_node['node_id']
                                existing_edge['to_node_id'] = second_node['node_id']
                                existing_edge['label1'] = result['label1']
                                existing_edge['label2'] = result['label2']
                                existing_edge['linewidth_mult'] = result['linewidth_mult']
                                existing_edge['label_size_mult'] = result['label_size_mult']
                                existing_edge['label_offset_mult'] = result['label_offset_mult']
                                existing_edge['style'] = result['style']
                                existing_edge['direction'] = result['direction']
                                existing_edge['flip_labels'] = result.get('flip_labels', False)
                                existing_edge['is_self_loop'] = is_self_loop
                                # Self-loop specific parameters
                                if is_self_loop:
                                    existing_edge['selfloopangle'] = result.get('selfloopangle', 0)
                                    existing_edge['selfloopscale'] = result.get('selfloopscale', 1.0)
                                    existing_edge['arrowlengthsc'] = result.get('arrowlengthsc', 1.0)
                                    existing_edge['flip'] = result.get('flip', False)
                                if is_self_loop:
                                    print(f"Replaced self-loop on node '{self.edge_mode_first_node['label']}'")
                                else:
                                    print(f"Replaced edge: '{self.edge_mode_first_node['label']}' ↔ '{second_node['label']}'")
                            else:
                                # Create new edge
                                edge = {
                                    'from_node': self.edge_mode_first_node,
                                    'to_node': second_node,
                                    'from_node_id': self.edge_mode_first_node['node_id'],
                                    'to_node_id': second_node['node_id'],
                                    'label1': result['label1'],
                                    'label2': result['label2'],
                                    'linewidth_mult': result['linewidth_mult'],
                                    'label_size_mult': result['label_size_mult'],
                                    'label_offset_mult': result['label_offset_mult'],
                                    'style': result['style'],
                                    'direction': result['direction'],
                                    'flip_labels': result.get('flip_labels', False),
                                    'looptheta': result.get('looptheta', 30),
                                    'is_self_loop': is_self_loop
                                }
                                # Self-loop specific parameters
                                if is_self_loop:
                                    edge['selfloopangle'] = result.get('selfloopangle', 0)
                                    edge['selfloopscale'] = result.get('selfloopscale', 1.0)
                                    edge['arrowlengthsc'] = result.get('arrowlengthsc', 1.0)
                                    edge['flip'] = result.get('flip', False)
                                self.edges.append(edge)

                                # Invalidate Kron reduction and scattering data since graph was modified
                                self._invalidate_kron_reduction()
                                self._invalidate_scattering_data()

                                # Auto-update matrix display
                                if hasattr(self, 'properties_panel'):
                                    self.properties_panel._update_matrix_display()

                                if is_self_loop:
                                    print(f"Added self-loop to node '{self.edge_mode_first_node['label']}'")
                                else:
                                    print(f"Added edge: '{self.edge_mode_first_node['label']}' → '{second_node['label']}'")
                                    # Check if this edge connects previously disconnected components
                                    # and merge any linked constraint groups
                                    self._merge_linked_constraint_groups()

                        # Exit single edge mode after placement, continue in continuous mode
                        if self.placement_mode == 'edge':
                            self.placement_mode = None
                            print("Edge placed - exited edge mode")

                        # Reset for next edge
                        self.edge_mode_first_node = None
                        self._update_plot()
                return

            if self.placement_mode is None:
                # Disable node manipulation on Kron canvas - it's read-only (computed data)
                if event.inaxes == self.kron_canvas.ax:
                    return

                clicked_node = self._find_node_at_position(event.xdata, event.ydata)

                # Handle node selection with Shift key (do this before double-click check)
                if clicked_node and shift_pressed:
                    if clicked_node in self.selected_nodes:
                        self.selected_nodes.remove(clicked_node)
                        print(f"Deselected node '{clicked_node['label']}'")
                    else:
                        self.selected_nodes.append(clicked_node)
                        print(f"Selected node '{clicked_node['label']}'")
                    # Don't update click tracking for shift-clicks
                    self._update_plot()
                    return

                # Check if this is a double-click on node or edge
                if self.last_click_pos:
                    time_diff = current_time - self.last_click_time
                    pos_diff = np.sqrt((event.xdata - self.last_click_pos[0])**2 +
                                      (event.ydata - self.last_click_pos[1])**2)

                    if time_diff < self.double_click_threshold and pos_diff < 0.5:
                        # Double-click detected
                        # Determine which canvas was clicked based on event.inaxes
                        is_scattering_view = (hasattr(self, 'scattering_canvas') and
                                             self.scattering_canvas and
                                             event.inaxes == self.scattering_canvas.ax)

                        if clicked_node:
                            # In scattering view, show scattering parameter dialog
                            if is_scattering_view:
                                self._edit_scattering_node_parameters(clicked_node)
                            else:
                                # Edit node appearance (only in original graph view)
                                self._edit_node(clicked_node)
                        else:
                            # Check for edge
                            clicked_edge = self._find_edge_at_position(event.xdata, event.ydata)
                            if clicked_edge:
                                # In scattering view, show scattering parameter dialog
                                if is_scattering_view:
                                    self._edit_scattering_edge_parameters(clicked_edge)
                                else:
                                    # Edit edge appearance (only in original graph view)
                                    self._edit_edge(clicked_edge)
                        self.last_click_time = 0
                        self.last_click_pos = None
                        return

                # Update click tracking
                self.last_click_time = current_time
                self.last_click_pos = (event.xdata, event.ydata)

                # Single click on node - select and prepare for potential dragging
                if clicked_node:
                    # If clicking on an already selected node, prepare to drag the whole group
                    if clicked_node in self.selected_nodes and len(self.selected_nodes) > 1:
                        self.drag_pending_group = True
                        self.drag_start_pos = (event.xdata, event.ydata)
                        # Don't print yet - wait until actual drag starts
                    else:
                        # Select only this node and prepare to drag it
                        if clicked_node not in self.selected_nodes:
                            self.selected_nodes.clear()
                            self.selected_edges.clear()  # Clear edge selection when selecting node
                            self.selected_nodes.append(clicked_node)
                            self._update_plot()
                        self.drag_pending_node = clicked_node
                        self.drag_start_pos = (event.xdata, event.ydata)
                        # Don't print yet - wait until actual drag starts
                    return

                # Single click on edge (if no node was clicked) - select edge
                if not clicked_node:
                    clicked_edge = self._find_edge_at_position(event.xdata, event.ydata)
                    if clicked_edge:
                        # Toggle edge selection with Shift, otherwise select only this edge
                        is_self_loop = clicked_edge.get('is_self_loop', False)
                        from_label = clicked_edge['from_node']['label']
                        to_label = clicked_edge['to_node']['label']

                        if shift_pressed:
                            if clicked_edge in self.selected_edges:
                                self.selected_edges.remove(clicked_edge)
                                if is_self_loop:
                                    print(f"Deselected self-loop on '{from_label}'")
                                else:
                                    print(f"Deselected edge '{from_label}' → '{to_label}'")
                            else:
                                self.selected_edges.append(clicked_edge)
                                if is_self_loop:
                                    print(f"Selected self-loop on '{from_label}'")
                                else:
                                    print(f"Selected edge '{from_label}' → '{to_label}'")
                        else:
                            self.selected_nodes.clear()  # Clear node selection when selecting edge
                            self.selected_edges.clear()
                            self.selected_edges.append(clicked_edge)
                            if is_self_loop:
                                print(f"Selected self-loop on '{from_label}'")
                            else:
                                print(f"Selected edge '{from_label}' → '{to_label}'")
                        self._update_plot()
                        return

                # Click on empty space - start selection window or clear selection
                if not clicked_node:
                    self.selected_nodes.clear()
                    self.selected_edges.clear()
                    self.selection_window = True
                    self.selection_window_start = (event.xdata, event.ydata)
                    self._update_plot()
                    return

            # Node placement mode
            if self.placement_mode in ['single', 'continuous', 'continuous_duplicate']:
                snap_x, snap_y = self._snap_to_grid(event.xdata, event.ydata)

                # Check if occupied
                occupied = any(
                    np.isclose(node['pos'][0], snap_x, atol=0.01) and
                    np.isclose(node['pos'][1], snap_y, atol=0.01)
                    for node in self.nodes
                )

                if occupied:
                    print(f"Position ({snap_x:.3f}, {snap_y:.3f}) already occupied!")
                    return

                # Continuous duplicate mode - use last node properties
                if self.placement_mode == 'continuous_duplicate':
                    if self.last_node_props:
                        self._save_state()

                        # Auto-increment the label (or use 'A' if empty string)
                        current_label = self.last_node_props['label']
                        if current_label == '':
                            # First node - start with 'A'
                            next_label = 'A'
                        else:
                            next_label = self._auto_increment_label(current_label)

                        # Add node with duplicated properties and incremented label
                        self.nodes.append({
                            'node_id': self.node_id_counter,
                            'label': next_label,
                            'pos': (snap_x, snap_y),
                            'color': self.last_node_props['color'],
                            'color_key': self.last_node_props['color_key'],
                            'node_size_mult': self.last_node_props['node_size_mult'],
                            'label_size_mult': self.last_node_props['label_size_mult'],
                            'conj': self.last_node_props['conj'],
                            'outline_enabled': self.last_node_props.get('outline_enabled', False),
                            'outline_color_key': self.last_node_props.get('outline_color_key', 'BLACK'),
                            'outline_color': self.last_node_props.get('outline_color', 'black'),
                            'outline_width': self.last_node_props.get('outline_width', config.DEFAULT_NODE_OUTLINE_WIDTH),
                            'outline_alpha': self.last_node_props.get('outline_alpha', config.DEFAULT_NODE_OUTLINE_ALPHA)
                        })
                        self.node_counter += 1
                        self.node_id_counter += 1

                        # Invalidate Kron reduction and scattering data since graph was modified
                        self._invalidate_kron_reduction()
                        self._invalidate_scattering_data()

                        # Auto-update matrix display and SymPy code
                        if hasattr(self, 'properties_panel'):
                            self.properties_panel._update_matrix_display()
                            self.properties_panel._update_sympy_code_display()

                        # Update last_node_props with the new label for next placement
                        self.last_node_props['label'] = next_label

                        print(f"✓ Node '{next_label}' ({self.last_node_props['color_key']}) placed at ({snap_x:.3f}, {snap_y:.3f})")
                        self._update_plot()
                    return

                # Show dialog for single and continuous modes
                # In continuous mode, inherit properties from last node
                default_label = self._get_next_label()
                if self.placement_mode == 'continuous' and self.last_node_props:
                    # Use properties from last modified node
                    dialog = NodeInputDialog(
                        default_label=default_label,
                        default_color=self.last_node_props['color_key'],
                        parent=self
                    )
                    # Set the dialog defaults to match last node
                    node_size_mult = self.last_node_props['node_size_mult']
                    label_size_mult = self.last_node_props['label_size_mult']

                    # Set slider values (sliders use percentage, e.g., 1.0 = 100)
                    dialog.node_size_slider.setValue(int(node_size_mult * 100))
                    dialog.label_size_slider.setValue(int(label_size_mult * 100))
                    dialog.conj_checkbox.setChecked(self.last_node_props['conj'])

                    # Also set outline properties if available
                    if 'outline_enabled' in self.last_node_props:
                        dialog.outline_checkbox.setChecked(self.last_node_props['outline_enabled'])
                    if 'outline_color_key' in self.last_node_props:
                        try:
                            outline_idx = list(config.MYCOLORS.keys()).index(self.last_node_props['outline_color_key'])
                            dialog.outline_color_combo.setCurrentIndex(outline_idx)
                        except (ValueError, KeyError):
                            pass
                    if 'outline_width' in self.last_node_props:
                        dialog.outline_width_slider.setValue(int(self.last_node_props['outline_width'] * 10))
                    if 'outline_alpha' in self.last_node_props:
                        dialog.outline_alpha_slider.setValue(int(self.last_node_props['outline_alpha'] * 100))
                else:
                    dialog = NodeInputDialog(default_label=default_label, default_color='BLUE', parent=self)

                if dialog.exec() == QDialog.Accepted:
                    result = dialog.get_result()
                    if result:
                        # Add node
                        new_node = {
                            'node_id': self.node_id_counter,
                            'label': result['label'],
                            'pos': (snap_x, snap_y),
                            'color': result['color'],
                            'color_key': result['color_key'],
                            'node_size_mult': result['node_size_mult'],
                            'label_size_mult': result['label_size_mult'],
                            'conj': result['conj'],
                            'outline_enabled': result['outline_enabled'],
                            'outline_color_key': result['outline_color_key'],
                            'outline_color': result['outline_color'],
                            'outline_width': result['outline_width'],
                            'outline_alpha': result['outline_alpha']
                        }
                        self.nodes.append(new_node)
                        self.node_counter += 1
                        self.node_id_counter += 1

                        # Invalidate Kron reduction and scattering data since graph was modified
                        self._invalidate_kron_reduction()
                        self._invalidate_scattering_data()

                        # Auto-update matrix display and SymPy code
                        if hasattr(self, 'properties_panel'):
                            self.properties_panel._update_matrix_display()
                            self.properties_panel._update_sympy_code_display()

                        # Save properties for duplication
                        self.last_node_props = {
                            'label': result['label'],
                            'color': result['color'],
                            'color_key': result['color_key'],
                            'node_size_mult': result['node_size_mult'],
                            'label_size_mult': result['label_size_mult'],
                            'conj': result['conj'],
                            'outline_enabled': result['outline_enabled'],
                            'outline_color_key': result['outline_color_key'],
                            'outline_color': result['outline_color'],
                            'outline_width': result['outline_width'],
                            'outline_alpha': result['outline_alpha']
                        }

                        print(f"✓ Node '{result['label']}' ({result['color_key']}) placed at ({snap_x:.3f}, {snap_y:.3f})")

                        # Exit single mode
                        if self.placement_mode == 'single':
                            self.placement_mode = None
                            print("Exited placement mode")

                        self._update_plot()

    def _on_release(self, event):
        """Handle mouse release"""
        # Middle button - stop panning
        if event.button == 2:
            self.panning = False
            self.pan_start = None
            return

        # Left button - complete selection window
        if event.button == 1:
            if self.selection_window and self.selection_window_start is not None:
                if event.inaxes == self.canvas.ax:
                    x0, y0 = self.selection_window_start
                    x1, y1 = event.xdata, event.ydata

                    # Ensure x0 < x1 and y0 < y1
                    if x1 < x0:
                        x0, x1 = x1, x0
                    if y1 < y0:
                        y0, y1 = y1, y0

                    # Select all nodes within the rectangle
                    for node in self.nodes:
                        nx, ny = node['pos']
                        if x0 <= nx <= x1 and y0 <= ny <= y1:
                            if node not in self.selected_nodes:
                                self.selected_nodes.append(node)

                    # Select all edges whose midpoints are within the rectangle
                    for edge in self.edges:
                        from_pos = edge['from_node']['pos']
                        to_pos = edge['to_node']['pos']
                        mid_x = (from_pos[0] + to_pos[0]) / 2
                        mid_y = (from_pos[1] + to_pos[1]) / 2
                        if x0 <= mid_x <= x1 and y0 <= mid_y <= y1:
                            if edge not in self.selected_edges:
                                self.selected_edges.append(edge)

                    msg = []
                    if self.selected_nodes:
                        msg.append(f"{len(self.selected_nodes)} node(s)")
                    if self.selected_edges:
                        msg.append(f"{len(self.selected_edges)} edge(s)")
                    if msg:
                        print(f"Selected {' and '.join(msg)}")

                # Clean up
                self.selection_window = False
                self.selection_window_start = None
                if self.selection_window_rect:
                    try:
                        self.selection_window_rect.remove()
                    except:
                        pass
                    self.selection_window_rect = None

                self._update_plot()
                return

        # Right button - complete zoom window
        if event.button == 3:
            if self.zoom_window and self.zoom_window_start is not None:
                # Check if event is in main canvas, scattering canvas, or kron canvas
                valid_canvas = (event.inaxes == self.canvas.ax or
                               (hasattr(self, 'kron_canvas') and event.inaxes == self.kron_canvas.ax) or
                               (hasattr(self, 'scattering_canvas') and self.scattering_canvas and event.inaxes == self.scattering_canvas.ax))

                if valid_canvas:
                    x0, y0 = self.zoom_window_start
                    x1, y1 = event.xdata, event.ydata

                    # Ensure x0 < x1 and y0 < y1
                    if x1 < x0:
                        x0, x1 = x1, x0
                    if y1 < y0:
                        y0, y1 = y1, y0

                    # Check minimum size
                    if abs(x1 - x0) > 0.5 and abs(y1 - y0) > 0.5:
                        # Determine which canvas the zoom window was drawn on
                        if hasattr(self, 'scattering_canvas') and self.scattering_canvas and event.inaxes == self.scattering_canvas.ax:
                            # Zoom window on scattering canvas
                            self.scattering_original_base_xlim = (x0, x1)
                            self.scattering_original_base_ylim = (y0, y1)
                            print(f"Scattering zoom window: ({x0:.3f}, {y0:.3f}) to ({x1:.3f}, {y1:.3f})")
                        elif hasattr(self, 'kron_canvas') and event.inaxes == self.kron_canvas.ax:
                            # Zoom window on kron canvas
                            self.kron_original_base_xlim = (x0, x1)
                            self.kron_original_base_ylim = (y0, y1)
                            print(f"Kron zoom window: ({x0:.3f}, {y0:.3f}) to ({x1:.3f}, {y1:.3f})")
                        else:
                            # Zoom window on original canvas
                            self.base_xlim = (x0, x1)
                            self.base_ylim = (y0, y1)
                            print(f"Zoom window: ({x0:.3f}, {y0:.3f}) to ({x1:.3f}, {y1:.3f})")

                        self.zoom_level = 1.0

                # Clean up
                self.zoom_window = False
                self.zoom_window_start = None
                if self.zoom_window_rect:
                    try:
                        self.zoom_window_rect.remove()
                    except:
                        pass
                    self.zoom_window_rect = None

                self._update_both_canvases()
            return

        # Left button - complete group or single node dragging
        if event.button == 1:
            # Complete group dragging
            if self.dragging_group and self.drag_start_pos is not None:
                # Determine which canvas/nodes to use
                if event.inaxes == self.kron_canvas.ax and hasattr(self, 'kron_graph') and self.kron_graph:
                    target_nodes = self.kron_graph['nodes']
                    target_canvas = self.kron_canvas
                elif event.inaxes == self.canvas.ax:
                    target_nodes = self.nodes
                    target_canvas = self.canvas
                else:
                    target_nodes = None
                    target_canvas = None

                if target_nodes is not None:
                    dx = event.xdata - self.drag_start_pos[0]
                    dy = event.ydata - self.drag_start_pos[1]

                    # Check if all new positions are valid
                    new_positions = []
                    all_valid = True
                    for node in self.selected_nodes:
                        new_x = node['pos'][0] + dx
                        new_y = node['pos'][1] + dy
                        snap_x, snap_y = self._snap_to_grid(new_x, new_y)

                        # Check if occupied by non-selected node
                        occupied = any(
                            other_node not in self.selected_nodes and
                            np.isclose(other_node['pos'][0], snap_x, atol=0.01) and
                            np.isclose(other_node['pos'][1], snap_y, atol=0.01)
                            for other_node in target_nodes
                        )

                        if occupied:
                            all_valid = False
                            break

                        new_positions.append((node, snap_x, snap_y))

                    # If all positions valid, move all nodes
                    if all_valid:
                        self._save_state()
                        for node, snap_x, snap_y in new_positions:
                            node['pos'] = (snap_x, snap_y)
                        print(f"✓ Moved {len(self.selected_nodes)} node(s)")
                    else:
                        print(f"✗ Cannot move group - some positions occupied")

                # Clean up
                self.dragging_group = False
                self.drag_pending_group = False
                self.drag_start_pos = None
                for patch in self.drag_preview_patches:
                    try:
                        patch.remove()
                    except:
                        pass
                for text in self.drag_preview_texts:
                    try:
                        text.remove()
                    except:
                        pass
                for outline in self.drag_preview_outlines:
                    try:
                        outline.remove()
                    except:
                        pass
                self.drag_preview_patches.clear()
                self.drag_preview_texts.clear()
                self.drag_preview_outlines.clear()

                # Update both canvases (only if we have a valid kron_graph)
                if target_canvas == self.kron_canvas and hasattr(self, 'kron_graph') and self.kron_graph:
                    saved_canvas = self.canvas
                    saved_nodes = self.nodes
                    saved_edges = self.edges

                    self.canvas = self.kron_canvas
                    self.nodes = self.kron_graph['nodes']
                    self.edges = self.kron_graph['edges']
                    self._update_plot()

                    self.canvas = saved_canvas
                    self.nodes = saved_nodes
                    self.edges = saved_edges
                else:
                    self._update_plot()
                return

            # Complete single node dragging
            if self.dragging_node is not None:
                # Determine which canvas/nodes to use
                if event.inaxes == self.kron_canvas.ax and hasattr(self, 'kron_graph') and self.kron_graph:
                    target_nodes = self.kron_graph['nodes']
                    target_canvas = self.kron_canvas
                elif event.inaxes == self.canvas.ax:
                    target_nodes = self.nodes
                    target_canvas = self.canvas
                else:
                    target_nodes = None
                    target_canvas = None

                if target_nodes is not None:
                    snap_x, snap_y = self._snap_to_grid(event.xdata, event.ydata)

                    # Check if occupied by another node
                    occupied = any(
                        node != self.dragging_node and
                        np.isclose(node['pos'][0], snap_x, atol=0.01) and
                        np.isclose(node['pos'][1], snap_y, atol=0.01)
                        for node in target_nodes
                    )

                    if not occupied:
                        self._save_state()
                        old_pos = self.dragging_node['pos']
                        self.dragging_node['pos'] = (snap_x, snap_y)

                        # Also update the corresponding node in original_graph if it exists
                        if hasattr(self, 'original_graph') and self.original_graph:
                            for orig_node in self.original_graph['nodes']:
                                if (orig_node['label'] == self.dragging_node['label'] and
                                    orig_node.get('conj', False) == self.dragging_node.get('conj', False)):
                                    orig_node['pos'] = (snap_x, snap_y)
                                    break

                        print(f"✓ Moved node '{self.dragging_node['label']}' from ({old_pos[0]:.3f}, {old_pos[1]:.3f}) to ({snap_x:.3f}, {snap_y:.3f})")
                    else:
                        print(f"✗ Cannot move node '{self.dragging_node['label']}' - position occupied")

                # Clean up
                self.dragging_node = None
                self.drag_pending_node = None
                self.drag_start_pos = None
                for patch in self.drag_preview_patches:
                    try:
                        patch.remove()
                    except:
                        pass
                for text in self.drag_preview_texts:
                    try:
                        text.remove()
                    except:
                        pass
                for outline in self.drag_preview_outlines:
                    try:
                        outline.remove()
                    except:
                        pass
                self.drag_preview_patches.clear()
                self.drag_preview_texts.clear()
                self.drag_preview_outlines.clear()

                # Update appropriate canvas (only if we have a valid kron_graph)
                if target_canvas == self.kron_canvas and hasattr(self, 'kron_graph') and self.kron_graph:
                    saved_canvas = self.canvas
                    saved_nodes = self.nodes
                    saved_edges = self.edges

                    self.canvas = self.kron_canvas
                    self.nodes = self.kron_graph['nodes']
                    self.edges = self.kron_graph['edges']
                    self._update_plot()

                    self.canvas = saved_canvas
                    self.nodes = saved_nodes
                    self.edges = saved_edges
                else:
                    self._update_plot()

                    # Also update both canvases if Kron graph exists (when main canvas node is moved)
                    # Need to sync node positions and re-render, matching _commit_kron_reduction()
                    if hasattr(self, 'kron_graph') and self.kron_graph:
                        # First, sync the Kron graph node positions with original graph
                        # The kron_graph nodes are copies, so we need to update their positions
                        for kron_node in self.kron_graph['nodes']:
                            # Find the corresponding node in original_graph by label
                            for orig_node in self.original_graph['nodes']:
                                if orig_node['label'] == kron_node['label'] and orig_node.get('conj', False) == kron_node.get('conj', False):
                                    kron_node['pos'] = orig_node['pos']
                                    break

                        saved_canvas = self.canvas
                        saved_nodes = self.nodes
                        saved_edges = self.edges
                        saved_base_xlim = self.base_xlim
                        saved_base_ylim = self.base_ylim

                        # Render original graph to Original canvas (self.canvas is already the main canvas)
                        self.nodes = self.original_graph['nodes']
                        self.edges = self.original_graph['edges']
                        self._do_plot_render()

                        # Store/update the original base limits for Kron canvas
                        self.kron_original_base_xlim = self.base_xlim
                        self.kron_original_base_ylim = self.base_ylim

                        # Render kron graph to Kron canvas
                        self.canvas = self.kron_canvas
                        self.nodes = self.kron_graph['nodes']
                        self.edges = self.kron_graph['edges']
                        self.base_xlim = self.kron_original_base_xlim
                        self.base_ylim = self.kron_original_base_ylim
                        self._do_plot_render()

                        # Restore canvas and graph pointers
                        self.canvas = saved_canvas
                        self.nodes = saved_nodes
                        self.edges = saved_edges
                        self.base_xlim = saved_base_xlim
                        self.base_ylim = saved_base_ylim
                return

            # Clear pending drag states if mouse was released without dragging
            if self.drag_pending_node or self.drag_pending_group:
                self.drag_pending_node = None
                self.drag_pending_group = False
                self.drag_start_pos = None
                return

    def _on_scroll(self, event):
        """Handle mouse scroll - optimized for smooth trackpad scrolling"""
        # Check if mouse is in the active canvas axes
        if event.inaxes is None:
            return

        # Update zoom level
        if event.button == 'up':
            self.zoom_level *= config.ZOOM_SCROLL_FACTOR
        elif event.button == 'down':
            self.zoom_level /= config.ZOOM_SCROLL_FACTOR

        # Only update the currently visible canvas for better performance
        # Use non-blocking draw_idle() for smooth scrolling (especially on trackpads)
        # Determine which canvas the event came from
        if hasattr(self, 'kron_canvas') and self.kron_canvas and event.inaxes and event.inaxes == self.kron_canvas.ax:
            # Event from Kron canvas - update Kron view
            if hasattr(self, 'kron_graph') and self.kron_graph:
                saved_canvas = self.canvas
                saved_nodes = self.nodes
                saved_edges = self.edges
                saved_base_xlim = self.base_xlim
                saved_base_ylim = self.base_ylim

                self.canvas = self.kron_canvas
                self.nodes = self.kron_graph['nodes']
                self.edges = self.kron_graph['edges']
                if hasattr(self, 'kron_original_base_xlim'):
                    self.base_xlim = self.kron_original_base_xlim
                    self.base_ylim = self.kron_original_base_ylim
                self._update_plot(use_idle=True)

                self.canvas = saved_canvas
                self.nodes = saved_nodes
                self.edges = saved_edges
                self.base_xlim = saved_base_xlim
                self.base_ylim = saved_base_ylim
        elif hasattr(self, 'scattering_canvas') and self.scattering_canvas and event.inaxes and event.inaxes == self.scattering_canvas.ax:
            # Event from Scattering canvas - update Scattering view
            if self.scattering_mode and hasattr(self, 'scattering_graph') and self.scattering_graph:
                saved_canvas = self.canvas
                saved_nodes = self.nodes
                saved_edges = self.edges
                saved_base_xlim = self.base_xlim
                saved_base_ylim = self.base_ylim

                self.canvas = self.scattering_canvas
                self.nodes = self.scattering_graph['nodes']
                self.edges = self.scattering_graph['edges']
                if hasattr(self, 'scattering_original_base_xlim'):
                    self.base_xlim = self.scattering_original_base_xlim
                    self.base_ylim = self.scattering_original_base_ylim
                self._update_plot(use_idle=True)

                self.canvas = saved_canvas
                self.nodes = saved_nodes
                self.edges = saved_edges
                self.base_xlim = saved_base_xlim
                self.base_ylim = saved_base_ylim
        else:
            # Event from original canvas - update original view
            self._update_plot(use_idle=True)

    def _invalidate_kron_reduction(self):
        """Reset/invalidate any existing Kron reduction when the graph is modified"""
        if hasattr(self, 'original_graph') and self.original_graph:
            print("Graph modified - resetting Kron reduction")
            # Clear the stored Kron reduction data
            self.original_graph = None
            self.kron_graph = None
            self.kron_reduced_matrix = None
            self.kron_reduced_matrix_latex = None
            self.kron_reduced_nodes = []
            self.kron_selected_nodes = []
            self.kron_affected_nodes = set()
            self.kron_new_edges = set()
            self.kron_modified_edges = set()
            self.viewing_original = False

            # Clear Kron matrix display
            if hasattr(self, 'kron_matrix_view'):
                self.kron_matrix_view.setHtml("")

            # Clear Kron canvas
            if hasattr(self, 'kron_canvas'):
                self.kron_canvas.ax.clear()
                self.kron_canvas.ax.set_xlim(-10, 10)
                self.kron_canvas.ax.set_ylim(-10, 10)
                self.kron_canvas.ax.set_aspect('equal')
                self.kron_canvas.ax.axis('off')
                self.kron_canvas.draw_idle()

            # Update displays to reflect cleared state
            if hasattr(self, 'properties_panel'):
                self.properties_panel._update_basis_display()
                self.properties_panel._update_matrix_display()
                self.properties_panel._update_sympy_code_display()

            # Switch back to Graph tab (tab 0)
            self.graph_subtabs.setCurrentIndex(0)

    def _invalidate_scattering_data(self):
        """Invalidate computed scattering data when graph structure changes.

        Unlike _clear_scattering_data(), this does NOT exit scattering mode.
        It clears computed S-parameters and updates displays, allowing the user
        to stay in scattering mode and recompute with the modified graph.
        """
        # Clear computed S-parameter data (these are on self, not properties_panel)
        if hasattr(self, 'sparams_data'):
            self.sparams_data = None
        if hasattr(self, '_last_port_ids'):
            self._last_port_ids = None
        if hasattr(self, '_last_all_ports_sig'):
            self._last_all_ports_sig = None

        # Clear S-parameter checkboxes
        if hasattr(self, 'sparams_checkboxes'):
            self.sparams_checkboxes = {}

        # Clear S-parameter plot (sparams_canvas is on self)
        if hasattr(self, 'sparams_canvas') and self.sparams_canvas:
            self.sparams_canvas.ax.clear()
            self.sparams_canvas.ax.set_xlabel('Frequency')
            self.sparams_canvas.ax.set_ylabel('Magnitude')
            self.sparams_canvas.draw_idle()

        # Clear scattering assignments for deleted nodes/edges
        # Keep only assignments for nodes/edges that still exist
        # Note: scattering_assignments uses Python id() as keys, not node['node_id']
        if hasattr(self, 'scattering_assignments') and self.scattering_assignments:
            node_obj_ids = {id(n) for n in self.nodes}
            edge_obj_ids = {id(e) for e in self.edges}

            # Find nodes that have self-loops (ports)
            port_node_obj_ids = set()
            for edge in self.edges:
                if edge.get('is_self_loop', False):
                    port_node_obj_ids.add(id(edge['from_node']))

            valid_assignments = {}
            for key, value in self.scattering_assignments.items():
                # Both node and edge assignments use Python id() as keys
                if key in node_obj_ids:
                    # Node assignment - check if it's a port (has self-loop)
                    if key in port_node_obj_ids:
                        # Node is a port, keep all assignments
                        valid_assignments[key] = value
                    else:
                        # Node is not a port, clear B_ext but keep other assignments
                        filtered_value = {k: v for k, v in value.items() if k != 'B_ext'}
                        if filtered_value:
                            valid_assignments[key] = filtered_value
                elif key in edge_obj_ids:
                    valid_assignments[key] = value
            self.scattering_assignments = valid_assignments

        # If in scattering mode, update the scattering graph/components
        if hasattr(self, 'scattering_mode') and self.scattering_mode:
            print("Graph modified - scattering data invalidated, recomputing...")
            # Re-find connected components since graph structure changed
            self.scattering_components = self._find_connected_components()
            # Update component dropdown (which also updates port count display)
            self._update_component_dropdown()
            # Update injection node dropdown (filters to port nodes only)
            self._update_injection_node_dropdown()
            # Update scattering tables to reflect new graph
            if hasattr(self, 'properties_panel'):
                self.properties_panel._update_scattering_node_table()
                self.properties_panel._update_scattering_edge_table()
            # Redraw scattering graph
            self._render_scattering_graph()
            # Recompute S-parameters with new graph structure
            # This will also update checkboxes and plot
            self._compute_and_plot_sparams()

    def _merge_linked_constraint_groups(self):
        """Merge constraint groups that were created via paste and are now connected.

        When an edge connects two previously disconnected graph components,
        constraint groups that were pasted (with 'linked_to' references) should
        merge with their original source groups if both still exist and match.
        """
        if not hasattr(self, 'scattering_constraint_groups') or not self.scattering_constraint_groups:
            return

        # Find all groups with 'linked_to' references
        linked_groups = {
            gid: gdata for gid, gdata in self.scattering_constraint_groups.items()
            if gdata.get('linked_to') is not None
        }

        if not linked_groups:
            return

        # Find connected components in the graph
        components = self._find_graph_components()
        if len(components) <= 1:
            # All nodes are connected - check for mergeable constraint groups
            pass
        else:
            # Still disconnected - don't merge yet
            return

        groups_to_delete = []
        merged_any = False

        for linked_gid, linked_data in linked_groups.items():
            original_gid = linked_data['linked_to']

            # Check if original group still exists
            if original_gid not in self.scattering_constraint_groups:
                continue

            original_data = self.scattering_constraint_groups[original_gid]

            # Check if groups are compatible (same param_name and obj_type)
            if (linked_data['param_name'] != original_data['param_name'] or
                linked_data['obj_type'] != original_data['obj_type']):
                continue

            # Merge: add linked group's members to original group
            for member in linked_data['members']:
                if member not in original_data['members']:
                    original_data['members'].append(member)

            # Mark linked group for deletion
            groups_to_delete.append(linked_gid)
            merged_any = True
            print(f"[Constraints] Merged group {linked_gid} into group {original_gid} "
                  f"({original_data['param_name']} for {original_data['obj_type']})")

        # Delete merged groups
        for gid in groups_to_delete:
            del self.scattering_constraint_groups[gid]

        # Update constraint styling if we merged any groups
        if merged_any and hasattr(self, 'properties_panel'):
            self.properties_panel._apply_constraint_styling()

    def _find_graph_components(self):
        """Find connected components in the graph (for constraint merging)."""
        if not self.nodes:
            return []

        # Build adjacency from edges
        adjacency = {id(node): set() for node in self.nodes}
        for edge in self.edges:
            from_id = id(edge['from_node'])
            to_id = id(edge['to_node'])
            if from_id in adjacency and to_id in adjacency:
                adjacency[from_id].add(to_id)
                adjacency[to_id].add(from_id)

        # Find connected components using BFS
        visited = set()
        components = []

        for node in self.nodes:
            node_id = id(node)
            if node_id in visited:
                continue

            # BFS from this node
            component = []
            queue = [node_id]
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                component.append(current)
                for neighbor in adjacency.get(current, []):
                    if neighbor not in visited:
                        queue.append(neighbor)

            components.append(component)

        return components

    def _save_state(self):
        """Save current state to undo stack"""
        # Don't invalidate Kron reduction - we update it dynamically when nodes move
        # self._invalidate_kron_reduction()

        # Deep copy the nodes list
        nodes_state = []
        for node in self.nodes:
            nodes_state.append({
                'node_id': node['node_id'],
                'label': node['label'],
                'pos': node['pos'],
                'color': node['color'],
                'color_key': node['color_key'],
                'node_size_mult': node.get('node_size_mult', 1.0),
                'label_size_mult': node.get('label_size_mult', 1.0),
                'conj': node.get('conj', False),
                'nodelabelnudge': node.get('nodelabelnudge', (0.0, 0.0))
            })

        # Deep copy the edges list
        edges_state = []
        for edge in self.edges:
            # Store edge by node IDs so we can reconnect after undo
            edge_state = {
                'from_node_id': edge['from_node_id'],
                'to_node_id': edge['to_node_id'],
                'label1': edge.get('label1', ''),
                'label2': edge.get('label2', ''),
                'linewidth_mult': edge['linewidth_mult'],
                'label_size_mult': edge['label_size_mult'],
                'label_offset_mult': edge.get('label_offset_mult', 1.0),
                'style': edge['style'],
                'direction': edge['direction'],
                'flip_labels': edge.get('flip_labels', False),
                'label_rotation_offset': edge.get('label_rotation_offset', 0),
                'is_self_loop': edge['is_self_loop']
            }
            # Save self-loop specific parameters
            if edge['is_self_loop']:
                edge_state['selfloopangle'] = edge.get('selfloopangle', 0)
                edge_state['selfloopscale'] = edge.get('selfloopscale', 1.0)
                edge_state['arrowlengthsc'] = edge.get('arrowlengthsc', 1.0)
                edge_state['flip'] = edge.get('flip', False)
            edges_state.append(edge_state)

        state = {'nodes': nodes_state, 'edges': edges_state}
        self.undo_stack.append(state)

        # Limit stack size
        if len(self.undo_stack) > self.max_undo:
            self.undo_stack.pop(0)

        # Mark as modified
        self._set_modified(True)

    def _undo(self):
        """Undo last action"""
        # In basis ordering mode, undo basis selection instead
        if self.basis_ordering_mode:
            self._undo_basis_selection()
            return

        if not self.undo_stack:
            print("Nothing to undo")
            return

        # Restore previous state
        previous_state = self.undo_stack.pop()

        # Restore nodes
        self.nodes = previous_state['nodes']

        # Build node_id-to-node mapping for reconnecting edges
        id_to_node = {}
        for node in self.nodes:
            id_to_node[node['node_id']] = node

        # Restore edges by reconnecting to nodes via IDs
        self.edges = []
        for edge_state in previous_state['edges']:
            from_node_id = edge_state['from_node_id']
            to_node_id = edge_state['to_node_id']

            # Only restore edge if both nodes still exist
            if from_node_id in id_to_node and to_node_id in id_to_node:
                edge = {
                    'from_node': id_to_node[from_node_id],
                    'to_node': id_to_node[to_node_id],
                    'from_node_id': from_node_id,
                    'to_node_id': to_node_id,
                    'label1': edge_state.get('label1', ''),
                    'label2': edge_state.get('label2', ''),
                    'linewidth_mult': edge_state['linewidth_mult'],
                    'label_size_mult': edge_state['label_size_mult'],
                    'label_offset_mult': edge_state.get('label_offset_mult', 1.0),
                    'style': edge_state['style'],
                    'direction': edge_state['direction'],
                    'flip_labels': edge_state.get('flip_labels', False),
                    'label_rotation_offset': edge_state.get('label_rotation_offset', 0),
                    'looptheta': edge_state.get('looptheta', 30),
                    'is_self_loop': edge_state['is_self_loop']
                }
                # Restore self-loop specific parameters
                if edge_state['is_self_loop']:
                    edge['selfloopangle'] = edge_state.get('selfloopangle', 0)
                    edge['selfloopscale'] = edge_state.get('selfloopscale', 1.0)
                    edge['arrowlengthsc'] = edge_state.get('arrowlengthsc', 1.0)
                    edge['flip'] = edge_state.get('flip', False)
                    edge['selflooplabelnudge'] = edge_state.get('selflooplabelnudge', (0.0, 0.0))
                self.edges.append(edge)

        # Clear selections
        self.selected_nodes.clear()
        self.selected_edges.clear()

        # Invalidate Kron reduction and scattering data since graph was restored
        self._invalidate_kron_reduction()
        self._invalidate_scattering_data()

        # Auto-update matrix display
        if hasattr(self, 'properties_panel'):
            self.properties_panel._update_matrix_display()

        print(f"Undo - restored to {len(self.nodes)} node(s) and {len(self.edges)} edge(s)")
        self._update_plot()

    def _select_all(self):
        """Select all nodes and edges"""
        self.selected_nodes = self.nodes.copy()
        self.selected_edges = self.edges.copy()
        print(f"Selected all: {len(self.selected_nodes)} node(s) and {len(self.selected_edges)} edge(s)")
        self._update_plot()

    def _copy_nodes(self):
        """Copy selected nodes and edges to clipboard"""
        if not self.selected_nodes and not self.selected_edges:
            print("No nodes or edges selected to copy")
            return

        self.clipboard = {'nodes': [], 'edges': []}

        # Basis ordering mode state
        self.basis_ordering_mode = False  # True when in basis ordering mode
        self.basis_order = []  # List of nodes in the order they were selected for basis
        self.basis_order_undo_stack = []  # Stack for undo/redo in basis ordering mode

        # Copy nodes
        for node in self.selected_nodes:
            node_copy = {
                'node_id': node['node_id'],
                'label': node['label'],
                'pos': node['pos'],
                'color': node['color'],
                'color_key': node['color_key'],
                'node_size_mult': node.get('node_size_mult', 1.0),
                'label_size_mult': node.get('label_size_mult', 1.0),
                'conj': node.get('conj', False),
                'nodelabelnudge': node.get('nodelabelnudge', (0.0, 0.0))
            }
            # Copy scattering parameters if assigned
            node_obj_id = id(node)
            if node_obj_id in self.scattering_assignments:
                node_copy['scattering_params'] = dict(self.scattering_assignments[node_obj_id])
            else:
                node_copy['scattering_params'] = None
            self.clipboard['nodes'].append(node_copy)

        # Copy edges where BOTH endpoints are in selected nodes
        # (This includes edges between selected nodes, even if not explicitly selected)
        for edge in self.edges:
            if edge['from_node'] in self.selected_nodes and edge['to_node'] in self.selected_nodes:
                edge_copy = {
                    'from_node_id': edge['from_node_id'],
                    'to_node_id': edge['to_node_id'],
                    'label1': edge.get('label1', ''),
                    'label2': edge.get('label2', ''),
                    'linewidth_mult': edge['linewidth_mult'],
                    'label_size_mult': edge['label_size_mult'],
                    'label_offset_mult': edge.get('label_offset_mult', 1.0),
                    'style': edge['style'],
                    'direction': edge['direction'],
                    'looptheta': edge.get('looptheta', 30),
                    'is_self_loop': edge['is_self_loop']
                }
                # Copy self-loop specific parameters
                if edge['is_self_loop']:
                    edge_copy['selfloopangle'] = edge.get('selfloopangle', 0)
                    edge_copy['selfloopscale'] = edge.get('selfloopscale', 1.0)
                    edge_copy['arrowlengthsc'] = edge.get('arrowlengthsc', 1.0)
                    edge_copy['flip'] = edge.get('flip', False)
                    edge_copy['selflooplabelnudge'] = edge.get('selflooplabelnudge', (0.0, 0.0))
                    edge_copy['label_bgcolor'] = edge.get('label_bgcolor', None)
                else:
                    edge_copy['label1_bgcolor'] = edge.get('label1_bgcolor', None)
                    edge_copy['label2_bgcolor'] = edge.get('label2_bgcolor', None)
                # Copy scattering parameters if assigned
                edge_obj_id = id(edge)
                if edge_obj_id in self.scattering_assignments:
                    edge_copy['scattering_params'] = dict(self.scattering_assignments[edge_obj_id])
                else:
                    edge_copy['scattering_params'] = None
                self.clipboard['edges'].append(edge_copy)

        # Copy constraint groups that involve copied nodes/edges
        self.clipboard['constraint_groups'] = []
        copied_node_labels = {n['label'] for n in self.clipboard['nodes']}
        copied_edge_labels = set()
        for edge in self.edges:
            if edge['from_node'] in self.selected_nodes and edge['to_node'] in self.selected_nodes:
                from_label = edge['from_node']['label']
                to_label = edge['to_node']['label']
                if edge['from_node'].get('conj', False):
                    from_label += '*'
                if edge['to_node'].get('conj', False):
                    to_label += '*'
                copied_edge_labels.add(f"{from_label}→{to_label}")

        for group_id, group_data in self.scattering_constraint_groups.items():
            obj_type = group_data['obj_type']
            members = group_data['members']

            # Find members being copied
            if obj_type == 'node':
                copied_members = [m for m in members if m.rstrip('*') in copied_node_labels or m in copied_node_labels]
            else:  # edge
                copied_members = [m for m in members if m in copied_edge_labels]

            # Only copy if at least one member is being copied
            if copied_members:
                self.clipboard['constraint_groups'].append({
                    'original_group_id': group_id,
                    'param_name': group_data['param_name'],
                    'obj_type': obj_type,
                    'members': copied_members,
                    'value': group_data['value'],
                    'is_conjugate_pair': group_data.get('is_conjugate_pair', False)
                })

        msg = []
        if len(self.clipboard['nodes']) > 0:
            msg.append(f"{len(self.clipboard['nodes'])} node(s)")
        if len(self.clipboard['edges']) > 0:
            msg.append(f"{len(self.clipboard['edges'])} edge(s)")
        if len(self.clipboard['constraint_groups']) > 0:
            msg.append(f"{len(self.clipboard['constraint_groups'])} constraint group(s)")
        print(f"Copied {' and '.join(msg)}")

    def _cut_nodes(self):
        """Cut selected nodes and edges to clipboard"""
        if not self.selected_nodes and not self.selected_edges:
            print("No nodes or edges selected to cut")
            return

        self._save_state()

        self.clipboard = {'nodes': [], 'edges': []}

        # Basis ordering mode state
        self.basis_ordering_mode = False  # True when in basis ordering mode
        self.basis_order = []  # List of nodes in the order they were selected for basis
        self.basis_order_undo_stack = []  # Stack for undo/redo in basis ordering mode
        nodes_to_remove = list(self.selected_nodes)
        edges_to_remove = []

        # Copy and remove nodes
        for node in nodes_to_remove:
            node_copy = {
                'node_id': node['node_id'],
                'label': node['label'],
                'pos': node['pos'],
                'color': node['color'],
                'color_key': node['color_key'],
                'node_size_mult': node.get('node_size_mult', 1.0),
                'label_size_mult': node.get('label_size_mult', 1.0),
                'conj': node.get('conj', False),
                'nodelabelnudge': node.get('nodelabelnudge', (0.0, 0.0))
            }
            # Copy scattering parameters if assigned
            node_obj_id = id(node)
            if node_obj_id in self.scattering_assignments:
                node_copy['scattering_params'] = dict(self.scattering_assignments[node_obj_id])
            else:
                node_copy['scattering_params'] = None
            self.clipboard['nodes'].append(node_copy)
            self.nodes.remove(node)

            # Find all edges connected to this node
            for edge in self.edges:
                if edge['from_node'] == node or edge['to_node'] == node:
                    if edge not in edges_to_remove:
                        edges_to_remove.append(edge)

        # Copy edges to clipboard where BOTH endpoints are in selected nodes
        # (This includes edges between selected nodes, even if not explicitly selected)
        for edge in edges_to_remove:
            if edge['from_node'] in nodes_to_remove and edge['to_node'] in nodes_to_remove:
                edge_copy = {
                    'from_node_id': edge['from_node_id'],
                    'to_node_id': edge['to_node_id'],
                    'label1': edge.get('label1', ''),
                    'label2': edge.get('label2', ''),
                    'linewidth_mult': edge['linewidth_mult'],
                    'label_size_mult': edge['label_size_mult'],
                    'label_offset_mult': edge.get('label_offset_mult', 1.0),
                    'style': edge['style'],
                    'direction': edge['direction'],
                    'looptheta': edge.get('looptheta', 30),
                    'is_self_loop': edge['is_self_loop']
                }
                # Copy self-loop specific parameters
                if edge['is_self_loop']:
                    edge_copy['selfloopangle'] = edge.get('selfloopangle', 0)
                    edge_copy['selfloopscale'] = edge.get('selfloopscale', 1.0)
                    edge_copy['arrowlengthsc'] = edge.get('arrowlengthsc', 1.0)
                    edge_copy['flip'] = edge.get('flip', False)
                    edge_copy['selflooplabelnudge'] = edge.get('selflooplabelnudge', (0.0, 0.0))
                    edge_copy['label_bgcolor'] = edge.get('label_bgcolor', None)
                else:
                    edge_copy['label1_bgcolor'] = edge.get('label1_bgcolor', None)
                    edge_copy['label2_bgcolor'] = edge.get('label2_bgcolor', None)
                # Copy scattering parameters if assigned
                edge_obj_id = id(edge)
                if edge_obj_id in self.scattering_assignments:
                    edge_copy['scattering_params'] = dict(self.scattering_assignments[edge_obj_id])
                else:
                    edge_copy['scattering_params'] = None
                self.clipboard['edges'].append(edge_copy)

        # Copy constraint groups that involve cut nodes/edges (before removing)
        self.clipboard['constraint_groups'] = []
        cut_node_labels = {n['label'] for n in self.clipboard['nodes']}
        cut_edge_labels = set()
        for edge_copy in self.clipboard['edges']:
            # Reconstruct edge label from clipboard data
            from_node = next((n for n in nodes_to_remove if n['node_id'] == edge_copy['from_node_id']), None)
            to_node = next((n for n in nodes_to_remove if n['node_id'] == edge_copy['to_node_id']), None)
            if from_node and to_node:
                from_label = from_node['label']
                to_label = to_node['label']
                if from_node.get('conj', False):
                    from_label += '*'
                if to_node.get('conj', False):
                    to_label += '*'
                cut_edge_labels.add(f"{from_label}→{to_label}")

        for group_id, group_data in self.scattering_constraint_groups.items():
            obj_type = group_data['obj_type']
            members = group_data['members']

            # Find members being cut
            if obj_type == 'node':
                cut_members = [m for m in members if m.rstrip('*') in cut_node_labels or m in cut_node_labels]
            else:  # edge
                cut_members = [m for m in members if m in cut_edge_labels]

            # Only copy if at least one member is being cut
            if cut_members:
                self.clipboard['constraint_groups'].append({
                    'original_group_id': group_id,
                    'param_name': group_data['param_name'],
                    'obj_type': obj_type,
                    'members': cut_members,
                    'value': group_data['value'],
                    'is_conjugate_pair': group_data.get('is_conjugate_pair', False)
                })

        # Remove all edges
        for edge in edges_to_remove:
            if edge in self.edges:
                self.edges.remove(edge)

        msg = []
        if len(self.clipboard['nodes']) > 0:
            msg.append(f"{len(self.clipboard['nodes'])} node(s)")
        if len(self.clipboard['edges']) > 0:
            msg.append(f"{len(self.clipboard['edges'])} edge(s)")
        if len(self.clipboard['constraint_groups']) > 0:
            msg.append(f"{len(self.clipboard['constraint_groups'])} constraint group(s)")
        print(f"Cut {' and '.join(msg)}")

        self.selected_nodes.clear()
        self.selected_edges.clear()
        self._update_plot()

    def _paste_nodes(self):
        """Smart paste with autoincrement labels and scattering params."""
        if not self.clipboard or (not self.clipboard.get('nodes') and not self.clipboard.get('edges')):
            print("Clipboard is empty")
            return

        self._save_state()

        # Compute smart label mapping
        existing_labels = set(node['label'] for node in self.nodes)
        clipboard_labels = [n['label'] for n in self.clipboard.get('nodes', [])]
        label_mapping = LabelPatternAnalyzer.compute_next_labels(clipboard_labels, existing_labels)

        # Calculate offset to paste nodes relative to the center of the view
        xlim = self._get_xlim()
        ylim = self._get_ylim()
        view_center_x = (xlim[0] + xlim[1]) / 2
        view_center_y = (ylim[0] + ylim[1]) / 2

        # Calculate centroid of clipboard nodes
        if self.clipboard.get('nodes'):
            clip_x = sum(n['pos'][0] for n in self.clipboard['nodes']) / len(self.clipboard['nodes'])
            clip_y = sum(n['pos'][1] for n in self.clipboard['nodes']) / len(self.clipboard['nodes'])

            # Snap the centroid to grid to get the base offset
            snap_center_x, snap_center_y = self._snap_to_grid(view_center_x, view_center_y)

            # Calculate offset based on snapped centroid
            offset_x = snap_center_x - clip_x
            offset_y = snap_center_y - clip_y
        else:
            offset_x, offset_y = 0, 0

        # Clear selection and paste nodes
        self.selected_nodes.clear()
        self.selected_edges.clear()

        # Map old node IDs to new nodes
        old_id_to_new_node = {}

        for clip_node in self.clipboard.get('nodes', []):
            # Apply offset but DON'T snap individually - maintain relative positions
            new_x = clip_node['pos'][0] + offset_x
            new_y = clip_node['pos'][1] + offset_y

            # Check if position is occupied
            occupied = any(
                np.isclose(node['pos'][0], new_x, atol=0.01) and
                np.isclose(node['pos'][1], new_y, atol=0.01)
                for node in self.nodes
            )

            if not occupied:
                # Use smart mapped label
                orig_label = clip_node['label']
                new_label = label_mapping.get(orig_label, orig_label)
                new_node = {
                    'node_id': self.node_id_counter,
                    'label': new_label,
                    'pos': (new_x, new_y),
                    'color': clip_node['color'],
                    'color_key': clip_node['color_key'],
                    'node_size_mult': clip_node.get('node_size_mult', 1.0),
                    'label_size_mult': clip_node.get('label_size_mult', 1.0),
                    'conj': clip_node.get('conj', False),
                    'nodelabelnudge': clip_node.get('nodelabelnudge', (0.0, 0.0))
                }
                self.nodes.append(new_node)
                self.node_id_counter += 1
                self.selected_nodes.append(new_node)
                old_id_to_new_node[clip_node['node_id']] = new_node

                # Restore scattering parameters if present
                if clip_node.get('scattering_params'):
                    self.scattering_assignments[id(new_node)] = dict(clip_node['scattering_params'])

        # Invalidate Kron reduction if nodes were pasted
        # Note: scattering data invalidation moved to after edges are pasted
        # to avoid clearing B_ext before self-loops are restored
        if len(old_id_to_new_node) > 0:
            self._invalidate_kron_reduction()

            # Auto-update matrix display
            if hasattr(self, 'properties_panel'):
                self.properties_panel._update_matrix_display()

        # Paste edges (only if both endpoint nodes were pasted)
        for clip_edge in self.clipboard.get('edges', []):
            from_node_id = clip_edge['from_node_id']
            to_node_id = clip_edge['to_node_id']

            if from_node_id in old_id_to_new_node and to_node_id in old_id_to_new_node:
                from_new_node = old_id_to_new_node[from_node_id]
                to_new_node = old_id_to_new_node[to_node_id]
                new_edge = {
                    'from_node': from_new_node,
                    'to_node': to_new_node,
                    'from_node_id': from_new_node['node_id'],
                    'to_node_id': to_new_node['node_id'],
                    'label1': clip_edge.get('label1', ''),
                    'label2': clip_edge.get('label2', ''),
                    'linewidth_mult': clip_edge['linewidth_mult'],
                    'label_size_mult': clip_edge['label_size_mult'],
                    'label_offset_mult': clip_edge.get('label_offset_mult', 1.0),
                    'style': clip_edge['style'],
                    'direction': clip_edge['direction'],
                    'looptheta': clip_edge.get('looptheta', 30),
                    'is_self_loop': clip_edge['is_self_loop']
                }
                # Restore self-loop specific parameters
                if clip_edge['is_self_loop']:
                    new_edge['selfloopangle'] = clip_edge.get('selfloopangle', 0)
                    new_edge['selfloopscale'] = clip_edge.get('selfloopscale', 1.0)
                    new_edge['arrowlengthsc'] = clip_edge.get('arrowlengthsc', 1.0)
                    new_edge['flip'] = clip_edge.get('flip', False)
                    new_edge['selflooplabelnudge'] = clip_edge.get('selflooplabelnudge', (0.0, 0.0))
                    new_edge['label_bgcolor'] = clip_edge.get('label_bgcolor', None)
                else:
                    new_edge['label1_bgcolor'] = clip_edge.get('label1_bgcolor', None)
                    new_edge['label2_bgcolor'] = clip_edge.get('label2_bgcolor', None)
                self.edges.append(new_edge)
                self.selected_edges.append(new_edge)

                # Restore scattering parameters if present
                if clip_edge.get('scattering_params'):
                    self.scattering_assignments[id(new_edge)] = dict(clip_edge['scattering_params'])

        # Invalidate scattering data after edges are pasted (so B_ext is preserved for port nodes)
        # Note: Kron invalidation already done above when nodes were pasted
        if len(old_id_to_new_node) > 0:
            self._invalidate_scattering_data()

        # Recreate constraint groups from clipboard with mapped labels
        pasted_constraint_count = 0
        if self.clipboard.get('constraint_groups'):
            # Build edge label mapping (old edge label -> new edge label)
            edge_label_mapping = {}
            for clip_edge in self.clipboard.get('edges', []):
                from_node_id = clip_edge['from_node_id']
                to_node_id = clip_edge['to_node_id']
                if from_node_id in old_id_to_new_node and to_node_id in old_id_to_new_node:
                    # Get old node labels from clipboard
                    old_from_node = next((n for n in self.clipboard['nodes'] if n['node_id'] == from_node_id), None)
                    old_to_node = next((n for n in self.clipboard['nodes'] if n['node_id'] == to_node_id), None)
                    if old_from_node and old_to_node:
                        old_from_label = old_from_node['label']
                        old_to_label = old_to_node['label']
                        if old_from_node.get('conj', False):
                            old_from_label += '*'
                        if old_to_node.get('conj', False):
                            old_to_label += '*'
                        old_edge_label = f"{old_from_label}→{old_to_label}"

                        # Get new node labels
                        new_from_node = old_id_to_new_node[from_node_id]
                        new_to_node = old_id_to_new_node[to_node_id]
                        new_from_label = new_from_node['label']
                        new_to_label = new_to_node['label']
                        if new_from_node.get('conj', False):
                            new_from_label += '*'
                        if new_to_node.get('conj', False):
                            new_to_label += '*'
                        new_edge_label = f"{new_from_label}→{new_to_label}"

                        edge_label_mapping[old_edge_label] = new_edge_label

            # Create new constraint groups with mapped labels
            for clip_group in self.clipboard['constraint_groups']:
                obj_type = clip_group['obj_type']
                old_members = clip_group['members']

                # Map old labels to new labels
                if obj_type == 'node':
                    new_members = []
                    for old_label in old_members:
                        # Handle conjugate suffix
                        base_label = old_label.rstrip('*')
                        has_conj = old_label.endswith('*')
                        new_base = label_mapping.get(base_label, base_label)
                        new_label = new_base + ('*' if has_conj else '')
                        new_members.append(new_label)
                else:  # edge
                    new_members = [edge_label_mapping.get(old_label, old_label) for old_label in old_members]

                # Only create group if we have members
                if new_members:
                    new_group_id = self._next_constraint_group_id
                    self._next_constraint_group_id += 1

                    self.scattering_constraint_groups[new_group_id] = {
                        'param_name': clip_group['param_name'],
                        'obj_type': obj_type,
                        'members': new_members,
                        'value': clip_group['value'],
                        'is_conjugate_pair': clip_group.get('is_conjugate_pair', False),
                        'linked_to': clip_group['original_group_id']  # Link to original for potential merge
                    }
                    pasted_constraint_count += 1

            # Update constraint styling if we pasted any groups
            if pasted_constraint_count > 0 and hasattr(self, 'properties_panel'):
                self.properties_panel._apply_constraint_styling()

        msg = []
        if len(self.selected_nodes) > 0:
            msg.append(f"{len(self.selected_nodes)} node(s)")
        if len(self.selected_edges) > 0:
            msg.append(f"{len(self.selected_edges)} edge(s)")
        if pasted_constraint_count > 0:
            msg.append(f"{pasted_constraint_count} constraint group(s)")
        print(f"Pasted {' and '.join(msg)}")
        self._update_plot()

    def _paste_nodes_raw(self):
        """Raw paste keeping original labels and scattering params (Ctrl+Shift+V)."""
        if not self.clipboard or (not self.clipboard.get('nodes') and not self.clipboard.get('edges')):
            print("Clipboard is empty")
            return

        self._save_state()

        # Calculate offset to paste nodes relative to the center of the view
        xlim = self._get_xlim()
        ylim = self._get_ylim()
        view_center_x = (xlim[0] + xlim[1]) / 2
        view_center_y = (ylim[0] + ylim[1]) / 2

        # Calculate centroid of clipboard nodes
        if self.clipboard.get('nodes'):
            clip_x = sum(n['pos'][0] for n in self.clipboard['nodes']) / len(self.clipboard['nodes'])
            clip_y = sum(n['pos'][1] for n in self.clipboard['nodes']) / len(self.clipboard['nodes'])

            # Snap the centroid to grid to get the base offset
            snap_center_x, snap_center_y = self._snap_to_grid(view_center_x, view_center_y)

            # Calculate offset based on snapped centroid
            offset_x = snap_center_x - clip_x
            offset_y = snap_center_y - clip_y
        else:
            offset_x, offset_y = 0, 0

        # Clear selection and paste nodes
        self.selected_nodes.clear()
        self.selected_edges.clear()

        # Map old node IDs to new nodes
        old_id_to_new_node = {}

        for clip_node in self.clipboard.get('nodes', []):
            # Apply offset but DON'T snap individually - maintain relative positions
            new_x = clip_node['pos'][0] + offset_x
            new_y = clip_node['pos'][1] + offset_y

            # Check if position is occupied
            occupied = any(
                np.isclose(node['pos'][0], new_x, atol=0.01) and
                np.isclose(node['pos'][1], new_y, atol=0.01)
                for node in self.nodes
            )

            if not occupied:
                # Raw paste: keep original label
                new_node = {
                    'node_id': self.node_id_counter,
                    'label': clip_node['label'],  # Keep original label
                    'pos': (new_x, new_y),
                    'color': clip_node['color'],
                    'color_key': clip_node['color_key'],
                    'node_size_mult': clip_node.get('node_size_mult', 1.0),
                    'label_size_mult': clip_node.get('label_size_mult', 1.0),
                    'conj': clip_node.get('conj', False),
                    'nodelabelnudge': clip_node.get('nodelabelnudge', (0.0, 0.0))
                }
                self.nodes.append(new_node)
                self.node_id_counter += 1
                self.selected_nodes.append(new_node)
                old_id_to_new_node[clip_node['node_id']] = new_node

                # Restore scattering parameters if present
                if clip_node.get('scattering_params'):
                    self.scattering_assignments[id(new_node)] = dict(clip_node['scattering_params'])

        # Invalidate Kron reduction if nodes were pasted
        # Note: scattering data invalidation moved to after edges are pasted
        # to avoid clearing B_ext before self-loops are restored
        if len(old_id_to_new_node) > 0:
            self._invalidate_kron_reduction()

            # Auto-update matrix display
            if hasattr(self, 'properties_panel'):
                self.properties_panel._update_matrix_display()

        # Paste edges (only if both endpoint nodes were pasted)
        for clip_edge in self.clipboard.get('edges', []):
            from_node_id = clip_edge['from_node_id']
            to_node_id = clip_edge['to_node_id']

            if from_node_id in old_id_to_new_node and to_node_id in old_id_to_new_node:
                from_new_node = old_id_to_new_node[from_node_id]
                to_new_node = old_id_to_new_node[to_node_id]
                new_edge = {
                    'from_node': from_new_node,
                    'to_node': to_new_node,
                    'from_node_id': from_new_node['node_id'],
                    'to_node_id': to_new_node['node_id'],
                    'label1': clip_edge.get('label1', ''),
                    'label2': clip_edge.get('label2', ''),
                    'linewidth_mult': clip_edge['linewidth_mult'],
                    'label_size_mult': clip_edge['label_size_mult'],
                    'label_offset_mult': clip_edge.get('label_offset_mult', 1.0),
                    'style': clip_edge['style'],
                    'direction': clip_edge['direction'],
                    'looptheta': clip_edge.get('looptheta', 30),
                    'is_self_loop': clip_edge['is_self_loop']
                }
                # Restore self-loop specific parameters
                if clip_edge['is_self_loop']:
                    new_edge['selfloopangle'] = clip_edge.get('selfloopangle', 0)
                    new_edge['selfloopscale'] = clip_edge.get('selfloopscale', 1.0)
                    new_edge['arrowlengthsc'] = clip_edge.get('arrowlengthsc', 1.0)
                    new_edge['flip'] = clip_edge.get('flip', False)
                    new_edge['selflooplabelnudge'] = clip_edge.get('selflooplabelnudge', (0.0, 0.0))
                    new_edge['label_bgcolor'] = clip_edge.get('label_bgcolor', None)
                else:
                    new_edge['label1_bgcolor'] = clip_edge.get('label1_bgcolor', None)
                    new_edge['label2_bgcolor'] = clip_edge.get('label2_bgcolor', None)
                self.edges.append(new_edge)
                self.selected_edges.append(new_edge)

                # Restore scattering parameters if present
                if clip_edge.get('scattering_params'):
                    self.scattering_assignments[id(new_edge)] = dict(clip_edge['scattering_params'])

        # Invalidate scattering data after edges are pasted (so B_ext is preserved for port nodes)
        if len(old_id_to_new_node) > 0:
            self._invalidate_scattering_data()

        # Recreate constraint groups from clipboard (raw paste keeps same labels)
        pasted_constraint_count = 0
        if self.clipboard.get('constraint_groups'):
            # Build edge label mapping for raw paste (labels stay the same but may need reconstruction)
            edge_label_mapping = {}
            for clip_edge in self.clipboard.get('edges', []):
                from_node_id = clip_edge['from_node_id']
                to_node_id = clip_edge['to_node_id']
                if from_node_id in old_id_to_new_node and to_node_id in old_id_to_new_node:
                    old_from_node = next((n for n in self.clipboard['nodes'] if n['node_id'] == from_node_id), None)
                    old_to_node = next((n for n in self.clipboard['nodes'] if n['node_id'] == to_node_id), None)
                    if old_from_node and old_to_node:
                        from_label = old_from_node['label']
                        to_label = old_to_node['label']
                        if old_from_node.get('conj', False):
                            from_label += '*'
                        if old_to_node.get('conj', False):
                            to_label += '*'
                        edge_label = f"{from_label}→{to_label}"
                        edge_label_mapping[edge_label] = edge_label  # Same label in raw paste

            # Create new constraint groups (labels unchanged in raw paste)
            for clip_group in self.clipboard['constraint_groups']:
                obj_type = clip_group['obj_type']
                members = clip_group['members']

                # For raw paste, labels stay the same
                if obj_type == 'node':
                    new_members = list(members)
                else:  # edge
                    new_members = [m for m in members if m in edge_label_mapping]

                if new_members:
                    new_group_id = self._next_constraint_group_id
                    self._next_constraint_group_id += 1

                    self.scattering_constraint_groups[new_group_id] = {
                        'param_name': clip_group['param_name'],
                        'obj_type': obj_type,
                        'members': new_members,
                        'value': clip_group['value'],
                        'is_conjugate_pair': clip_group.get('is_conjugate_pair', False),
                        'linked_to': clip_group['original_group_id']
                    }
                    pasted_constraint_count += 1

            if pasted_constraint_count > 0 and hasattr(self, 'properties_panel'):
                self.properties_panel._apply_constraint_styling()

        msg = []
        if len(self.selected_nodes) > 0:
            msg.append(f"{len(self.selected_nodes)} node(s)")
        if len(self.selected_edges) > 0:
            msg.append(f"{len(self.selected_edges)} edge(s)")
        if pasted_constraint_count > 0:
            msg.append(f"{pasted_constraint_count} constraint group(s)")
        print(f"Raw pasted {' and '.join(msg)}")
        self._update_plot()

    def _delete_selected_nodes(self):
        """Delete selected nodes and edges"""
        if not self.selected_nodes and not self.selected_edges:
            print("No nodes or edges selected to delete")
            return

        self._save_state()

        # Delete selected nodes and any edges connected to them
        nodes_to_remove = list(self.selected_nodes)
        edges_to_remove = []

        for node in nodes_to_remove:
            if node in self.nodes:
                self.nodes.remove(node)
                # Find all edges connected to this node
                for edge in self.edges:
                    if edge['from_node'] == node or edge['to_node'] == node:
                        if edge not in edges_to_remove:
                            edges_to_remove.append(edge)

        # Delete selected edges
        for edge in self.selected_edges:
            if edge not in edges_to_remove and edge in self.edges:
                edges_to_remove.append(edge)

        # Remove all edges
        for edge in edges_to_remove:
            if edge in self.edges:
                self.edges.remove(edge)
            if edge in self.selected_edges:
                self.selected_edges.remove(edge)

        node_count = len(nodes_to_remove)
        edge_count = len(edges_to_remove)

        # Invalidate Kron reduction and scattering data if anything was deleted
        if node_count > 0 or edge_count > 0:
            self._invalidate_kron_reduction()
            self._invalidate_scattering_data()

            # Update conjugate pair constraints (pairs may have been broken)
            self._update_conjugate_pair_constraints()

            # Auto-update matrix display
            if hasattr(self, 'properties_panel'):
                self.properties_panel._update_matrix_display()

        msg = []
        if node_count > 0:
            msg.append(f"{node_count} node(s)")
        if edge_count > 0:
            msg.append(f"{edge_count} edge(s)")
        print(f"Deleted {' and '.join(msg)}")

        self.selected_nodes.clear()
        self.selected_edges.clear()
        self._update_plot()

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

    def _parse_prettynode_label(self, label):
        """Parse label into mode and subscript for prettynode, or return None if not applicable"""
        # Check if label matches pattern: single letter (A-F) optionally followed by subscript
        match = re.match(r'^([A-F])(.*)$', label)
        if match:
            mode = match.group(1)
            sub = match.group(2)
            return mode, sub
        return None

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

        render_mode = "LaTeX" if self.use_latex else "MathText"
        print(f"Rendering mode: {render_mode}")
        self._update_plot()

    def _copy_matrix_latex(self):
        """Copy the matrix LaTeX markup to clipboard (Ctrl+Shift+L)"""
        if hasattr(self, 'properties_panel') and hasattr(self.properties_panel.graphulator, 'symbolic_matrix_latex'):
            latex_str = self.properties_panel.graphulator.symbolic_matrix_latex
            if latex_str:
                # Copy to clipboard - latex_str is already normalized and complete
                clipboard = QApplication.clipboard()
                full_latex = f"$M = {latex_str}$"
                clipboard.setText(full_latex)
                print(f"✓ Copied LaTeX to clipboard:\n{full_latex}")
            else:
                print("No matrix LaTeX available yet")
        else:
            print("No matrix generated yet")

    def _calculate_graph_extents(self):
        """Calculate the full extents of the graph including all objects (nodes, edges, self-loops, labels)"""
        if not self.nodes:
            return 0, 0, 0, 0

        import numpy as np
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

    def _export_code(self):
        """Export graph as Python code using graph_primitives GraphCircuit"""
        # Determine which graph to export based on currently displayed tab
        export_kron = False
        saved_nodes = None
        saved_edges = None

        if hasattr(self, 'graph_subtabs') and hasattr(self, 'kron_graph') and self.kron_graph:
            current_tab = self.graph_subtabs.currentIndex()
            tab_text = self.graph_subtabs.tabText(current_tab) if current_tab >= 0 else ""
            if tab_text == "Kron":
                export_kron = True
                print("Exporting Kron-reduced graph...")
            else:
                print("Exporting Original graph...")

        # Temporarily swap to the appropriate graph data
        if export_kron:
            saved_nodes = self.nodes
            saved_edges = self.edges
            self.nodes = self.kron_graph['nodes']
            self.edges = self.kron_graph['edges']

        try:
            if not self.nodes:
                print("No nodes to export")
                return

            # Calculate full graph extents including all objects first
            # This will be used for both scaling calculations and final plot limits
            import numpy as np
            extent_x_min, extent_x_max, extent_y_min, extent_y_max = self._calculate_graph_extents()
    
            # Calculate graph center - we'll shift all coordinates to center at origin
            x_center = (extent_x_min + extent_x_max) / 2
            y_center = (extent_y_min + extent_y_max) / 2
    
            # Calculate the actual plot extent we'll use (with 10% padding)
            full_extent_span = max(extent_x_max - extent_x_min, extent_y_max - extent_y_min) * 1.1
    
            # Calculate points_per_data_unit for node label nudge calculations
            # This is still needed for vertical adjustment compensation
            figsize = 12
            fig_size_points = figsize * 72
            export_points_per_data_unit = fig_size_points / (full_extent_span * 2)  # *2 because extent is from -x_extent to +x_extent
    
            # NO fontscale_compensation needed anymore!
            # graph_primitives.py now auto-scales all labels (node, self-loop, edge) based on
            # points_per_data_unit, so they maintain correct proportions regardless of extent
            # All font size parameters (fontscale, selflooplabelscale, labelfontsize) now work
            # consistently as multipliers on auto-calculated base sizes
    
            # Debug: print the extent
            print(f"Graph extent span: {full_extent_span:.3f}")
    
            # Calculate linewidth scaling factor to keep linewidths proportional to node size
            # Linewidths are in points (absolute), but need to scale with graph extent
            # Use a reference extent (typical small graph is ~10-15 units after padding)
            reference_extent = 15.0
            lw_extent_scale = reference_extent / full_extent_span
            print(f"Linewidth extent scale factor: {lw_extent_scale:.3f}")
    
            # Use the export_rescale dictionary (tunable via UI in Export Scaling tab)
            # These parameters provide absolute control over scaling, independent of graph size
            RESCALE = self.export_rescale
    
    
            # Generate Python code
            code_lines = []
            code_lines.append("#!/usr/bin/env python")
            code_lines.append('"""')
            code_lines.append("Generated graph code using graph_primitives")
            code_lines.append('"""')
            code_lines.append("")
            code_lines.append("import matplotlib.pyplot as plt")
            code_lines.append("import graphulator.graph_primitives as gp")
            code_lines.append("import graphulator.graphulator_config as config")
            code_lines.append("")
            code_lines.append("# Create graph circuit (allow duplicate labels)")
            code_lines.append("# Set use_latex=True for LaTeX rendering, False for MathText (default)")
            use_latex_str = "True" if self.use_latex else "False"
            code_lines.append(f"graph = gp.GraphCircuit(allow_duplicate_labels=True, use_latex={use_latex_str})")
            code_lines.append("")
    
            # Check for duplicate labels
            label_counts = {}
            has_duplicates = False
            for node in self.nodes:
                label = node['label']
                label_counts[label] = label_counts.get(label, 0) + 1
                if label_counts[label] > 1:
                    has_duplicates = True
    
            # Find self-loops for each node
            node_selfloops = {}  # Maps node_id to self-loop edge
            for edge in self.edges:
                if edge['is_self_loop']:
                    node_selfloops[edge['from_node_id']] = edge
    
            code_lines.append("# Add nodes")
    
            for i, node in enumerate(self.nodes):
                label = node['label']
                # Handle empty labels - use space to avoid math parsing errors
                if not label or not label.strip():
                    label = ' '
                node_id = node['node_id']
                x, y = node['pos']
                color_key = node['color_key']
                node_size_mult = node.get('node_size_mult', 1.0)
                label_size_mult = node.get('label_size_mult',1.0) * 0.75
                conj = node.get('conj', False)
    
                # HACK to fix the label_size_mult
                # label_size_mult *= 0.1
    
                # Use addnode for all nodes (consistent parameterization)
                radius = self.node_radius * node_size_mult
    
                # Check if this node has a self-loop
                has_selfloop = node_id in node_selfloops
                selfloop_edge = None
                selfloop_label = ''
                if has_selfloop:
                    selfloop_edge = node_selfloops[node_id]
                    selfloop_label = selfloop_edge.get('label1', '')
    
                # Shift coordinates to center graph at origin
                x_shifted = x - x_center
                y_shifted = y - y_center
    
                code_lines.append(f"# Node {i+1}: {label if label.strip() else '(blank)'}")
                if has_duplicates:
                    # Include node_id to disambiguate
                    code_lines.append(f"graph.addnode(label='{label}', xy=({x_shifted:.3f}, {y_shifted:.3f}), node_id={node_id},")
                else:
                    code_lines.append(f"graph.addnode(label='{label}', xy=({x_shifted:.3f}, {y_shifted:.3f}),")
                code_lines.append(f"             nodecolor=config.MYCOLORS['{color_key}'],")
                code_lines.append(f"             R={radius:.3f},")
                # fontscale is now a simple multiplier - graph_primitives handles auto-scaling
                code_lines.append(f"             fontscale={label_size_mult * RESCALE['NODELABELSCALE']:.3f},")
                code_lines.append(f"             conj={conj},")

                # Add outline properties if enabled
                outline_enabled = node.get('outline_enabled', False)
                if outline_enabled:
                    outline_color_key = node.get('outline_color_key', 'BLACK')
                    outline_width = node.get('outline_width', config.DEFAULT_NODE_OUTLINE_WIDTH)
                    outline_alpha = node.get('outline_alpha', config.DEFAULT_NODE_OUTLINE_ALPHA)
                    code_lines.append(f"             nodeoutlinecolor=config.MYCOLORS['{outline_color_key}'],")
                    code_lines.append(f"             nodelw={outline_width:.1f},")
                    code_lines.append(f"             nodeoutlinealpha={outline_alpha:.2f},")

                # Add nodelabelnudge if non-zero
                # Compensate for GUI's vertical adjustment (5% of font size downward)
                # so exported position matches GUI appearance
                nudge = node.get('nodelabelnudge', (0.0, 0.0))
                if nudge != (0.0, 0.0) and (abs(nudge[0]) > 0.001 or abs(nudge[1]) > 0.001):
                    # Calculate vertical adjustment used in GUI rendering
                    # Use export parameters to calculate points_per_data_unit
                    conj_scale = 0.92 if conj else 1.0
                    font_size_points = radius * 2 * export_points_per_data_unit * 0.35 * label_size_mult * conj_scale
                    adjustment_fraction = 0.05
                    vertical_adjustment_points = font_size_points * adjustment_fraction
                    vertical_adjustment_data = vertical_adjustment_points / export_points_per_data_unit
    
                    # Subtract the adjustment from y-component of nudge for export
                    # (GUI nudge is relative to adjusted position, export needs absolute position)
                    export_nudge = (nudge[0], nudge[1] - vertical_adjustment_data)
                    code_lines.append(f"             nodelabelnudge=({export_nudge[0]:.3f}, {export_nudge[1]:.3f}),")
    
                # Add self-loop parameters if this node has a self-loop
                if has_selfloop and selfloop_edge is not None:
                    code_lines.append(f"             drawselfloop=True,")
                    if selfloop_label:
                        # Auto-enclose label with $ signs for math mode if not already present
                        if not selfloop_label.startswith('$'):
                            export_label = f'${selfloop_label}$'
                        else:
                            export_label = selfloop_label
                        code_lines.append(f"             selflooplabel=r'{export_label}',")
    
                        # Add selflooplabelscale if non-default
                        label_size_mult = selfloop_edge.get('label_size_mult', 1.4)
                        if abs(label_size_mult - 1.4) > 0.01:
                            # selflooplabelscale works as multiplier relative to node label size
                            # It multiplies scaled_nodelabelsize, so it automatically scales proportionally
                            code_lines.append(f"             selflooplabelscale={label_size_mult * RESCALE['SELFLOOP_LABELSCALE']:.3f},")
    
                    code_lines.append(f"             selflooplw={2.5 * selfloop_edge['linewidth_mult'] * RESCALE['SLLW'] * lw_extent_scale:.1f},")
    
                    # Add selfloopangle
                    selfloopangle = selfloop_edge.get('selfloopangle', 0)
                    if selfloopangle != 0:
                        code_lines.append(f"             selfloopangle={selfloopangle},")
    
                    # Add selfloopscale
                    selfloopscale = selfloop_edge.get('selfloopscale', 1.0)
                    if abs(selfloopscale - 1.0) > 0.01:
                        code_lines.append(f"             selfloopscale={selfloopscale * RESCALE['SLSC']:.3f},")
    
                    # Add arrowlengthsc
                    arrowlengthsc = selfloop_edge.get('arrowlengthsc', 1.0)
                    if abs(arrowlengthsc - 1.0) > 0.01:
                        code_lines.append(f"             arrowlengthsc={arrowlengthsc:.3f},")
    
                    # Add flipselfloop
                    flip = selfloop_edge.get('flip', False)
                    if flip:
                        code_lines.append(f"             flipselfloop={flip},")
    
                    # Add selflooplabelnudge if non-zero
                    # Apply SELFLOOP_LABELNUDGE_SCALE and EXPORT_SELFLOOP_LABEL_DISTANCE
                    nudge = selfloop_edge.get('selflooplabelnudge', (0.0, 0.0))
                    nudge_scale = RESCALE.get('SELFLOOP_LABELNUDGE_SCALE', 1.0)
                    export_distance_scale = RESCALE.get('EXPORT_SELFLOOP_LABEL_DISTANCE', 1.0)
    
                    # Calculate scaled nudge accounting for both the fine-tuning nudge and distance scaling
                    # The distance scale adjusts the overall radial position from the node center
                    # We approximate this by scaling the nudge in the direction of the self-loop angle
                    selfloopangle = selfloop_edge.get('selfloopangle', 0)
                    angle_rad = selfloopangle * np.pi / 180
    
                    # Base nudge from user adjustments
                    scaled_nudge_x = nudge[0] * nudge_scale
                    scaled_nudge_y = nudge[1] * nudge_scale
    
                    # Add distance scaling component (moves label radially based on angle)
                    if abs(export_distance_scale - 1.0) > 0.001:
                        # Calculate radial offset to adjust distance from node center
                        # This mimics changing the 3.2*R factor in the label positioning
                        radial_adjustment = (export_distance_scale - 1.0) * 0.5  # Scale factor for nudge
                        scaled_nudge_x += radial_adjustment * np.cos(angle_rad)
                        scaled_nudge_y += radial_adjustment * np.sin(angle_rad)
    
                    if (abs(scaled_nudge_x) > 0.001 or abs(scaled_nudge_y) > 0.001):
                        code_lines.append(f"             selflooplabelnudge=({scaled_nudge_x:.3f}, {scaled_nudge_y:.3f}),")
    
                    # Add selfloop label background color if set
                    label_bgcolor = selfloop_edge.get('label_bgcolor', None)
                    if label_bgcolor is not None:
                        code_lines.append(f"             selflooplabelbgcolor='{label_bgcolor}',")
    
                    # Close the addnode call
                    code_lines.append(f"             )")
                else:
                    code_lines.append(f"             drawselfloop=False)")
                code_lines.append("")
    
            # Add edges if any exist (skip self-loops, they're handled in addnode)
            non_selfloop_edges = [e for e in self.edges if not e['is_self_loop']]
            if non_selfloop_edges:
                code_lines.append("# Add edges")
                for i, edge in enumerate(non_selfloop_edges):
                    from_node = edge['from_node']
                    to_node = edge['to_node']
                    from_label = from_node['label']
                    to_label = to_node['label']
                    from_node_id = edge['from_node_id']
                    to_node_id = edge['to_node_id']
    
                    edge_label1 = edge.get('label1', '')
                    edge_label2 = edge.get('label2', '')
                    style = edge['style']
                    direction = edge['direction']
                    linewidth_mult = edge['linewidth_mult']
                    label_size_mult = edge['label_size_mult']
                    label_offset_mult = edge.get('label_offset_mult', 1.0)
    
                    code_lines.append(f"# Edge {i+1}: {from_label} → {to_label}")
    
                    # Calculate labeltheta from node positions
                    from_pos = from_node['pos']
                    to_pos = to_node['pos']
                    dx = to_pos[0] - from_pos[0]
                    dy = to_pos[1] - from_pos[1]
                    labeltheta = np.arctan2(dy, dx) * 180 / np.pi
    
                    # Flip labels by 180 degrees if requested
                    if edge.get('flip_labels', False):
                        labeltheta += 180
    
                    # Add fine-tuning rotation offset
                    labeltheta += edge.get('label_rotation_offset', 0)
    
                    # Base values for figsize=12
                    base_lw = 4
                    base_labelfontsize = config.EXPORT_EDGE_LABEL_BASE_FONTSIZE
                    base_labeloffset = 2.3
    
                    # Apply multipliers and extent scaling
                    # Scale linewidths inversely with extent to keep them proportional to circles
                    scaled_lw = base_lw * linewidth_mult * lw_extent_scale
                    scaled_labelfontsize = base_labelfontsize * label_size_mult
                    scaled_labeloffset = base_labeloffset * label_offset_mult
    
                    # Adjust linewidth for single/double styles (graph_primitives multiplies these)
                    # Since we're passing 'lw' in loopkwargs, we need to pre-multiply
                    single_double_lw_unit = 3.5
                    if style == 'single':
                        scaled_lw *= single_double_lw_unit * 0.4
                    elif style == 'double':
                        scaled_lw *= 0.9 * single_double_lw_unit
                    elif style == 'loopy':
                        scaled_lw *= 0.4
    
                    # Format labels - add $ if not already present
                    def format_label(label_text):
                        if label_text:
                            if not label_text.startswith('$'):
                                return f'${label_text}$'
                            return label_text
                        return None
    
                    formatted_label1 = format_label(edge_label1)
                    formatted_label2 = format_label(edge_label2)
    
                    # Build label list string
                    label1_str = f"r'{formatted_label1}'" if formatted_label1 else "None"
                    label2_str = f"r'{formatted_label2}'" if formatted_label2 else "None"
                    label_str = f"[{label1_str}, {label2_str}]"
    
                    # Use node_id if there are duplicates, otherwise use labels
                    if has_duplicates:
                        code_lines.append(f"graph.addedge(fromnode_id={from_node_id}, tonode_id={to_node_id},")
                    else:
                        code_lines.append(f"graph.addedge(fromnode='{from_label}', tonode='{to_label}',")
                    code_lines.append(f"             label={label_str},")
                    code_lines.append(f"             labeltheta={labeltheta:.1f},")
                    code_lines.append(f"             labeloffset={scaled_labeloffset * RESCALE['EDGELABELOFFSET']:.1f},")
                    code_lines.append(f"             labelfontsize={scaled_labelfontsize * RESCALE['EDGEFONTSCALE']:.0f},")
    
                    # Add label background colors if set
                    label1_bgcolor = edge.get('label1_bgcolor', None)
                    label2_bgcolor = edge.get('label2_bgcolor', None)
                    if label1_bgcolor or label2_bgcolor:
                        bgcolor1_str = f"'{label1_bgcolor}'" if label1_bgcolor else "None"
                        bgcolor2_str = f"'{label2_bgcolor}'" if label2_bgcolor else "None"
                        code_lines.append(f"             labelbgcolor=[{bgcolor1_str}, {bgcolor2_str}],")
    
                    code_lines.append(f"             style='{style}',")
                    code_lines.append(f"             whichedges='{direction}',")
                    code_lines.append(f"             theta={edge.get('looptheta', 30)},")
                    code_lines.append(f"             loopkwargs={{'lw': {scaled_lw * RESCALE['EDGELWSCALE']:.1f}, 'arrowlength': 0.4}})")
                    code_lines.append("")
    
            code_lines.append("")
            code_lines.append("# Draw the graph")
            code_lines.append("# overfrac adds padding around the graph to ensure all elements are visible")
            code_lines.append("# Increase overfrac if labels or self-loops are cut off")
            code_lines.append("graph.draw(figsize=12, overfrac=0.2)")
            code_lines.append("")

            # Add explicit y-axis limits if they differ from graph.draw() auto-calculated limits
            # graph.draw() auto-centers based on graph extent, but user may have panned/zoomed
            current_ylim = self.canvas.ax.get_ylim()

            # Calculate what graph.draw would set (symmetric around graph center)
            # We can compare against the current view to see if user has adjusted it
            # For simplicity, if ylim is non-default, export it explicitly
            y_tolerance = 0.1  # Tolerance for considering limits "different"

            # Check if current limits differ significantly from a symmetric auto-scale
            # (graph.draw auto-centers, so we check if user has manually adjusted)
            ylim_modified = False

            # Simple heuristic: if the y-range or center is notably different from defaults,
            # assume user wants to preserve it
            current_y_center = (current_ylim[0] + current_ylim[1]) / 2
            current_y_range = current_ylim[1] - current_ylim[0]

            # If center is not near 0 or range is not near graph extent, preserve limits
            if abs(current_y_center) > y_tolerance or current_y_range < (extent_y_max - extent_y_min) * 0.8:
                ylim_modified = True

            if ylim_modified:
                code_lines.append("# Set explicit y-axis limits (preserving GUI view)")
                code_lines.append(f"plt.ylim({current_ylim[0]:.2f}, {current_ylim[1]:.2f})")
                code_lines.append("")

            code_lines.append("plt.axis('off')")
            code_lines.append("plt.title('')  # Remove title")
            code_lines.append("plt.show()")
    
            # Join and copy to clipboard or print
            code = "\n".join(code_lines)
    
            # Try to copy to system clipboard
            try:
                clipboard = QApplication.clipboard()
                clipboard.setText(code)
                edge_str = f", {len(self.edges)} edge(s)" if self.edges else ""
                print(f"✓ Exported code for {len(self.nodes)} node(s){edge_str} to clipboard")
            except Exception as clipboard_error:
                logger.warning("Could not copy to clipboard: %s", clipboard_error)
                print(f"✓ Generated code for {len(self.nodes)} node(s)")
        except Exception as e:
            print(f"Code export (clipboard failed: {e}, printing to console):")
            print("=" * 70)
            print(code)
            print("=" * 70)
        finally:
            # Restore original nodes/edges if we swapped to Kron graph
            if export_kron:
                self.nodes = saved_nodes
                self.edges = saved_edges

    def _update_properties_panel(self):
        """Update the properties panel based on current selection"""
        # Single node selected
        if len(self.selected_nodes) == 1 and len(self.selected_edges) == 0:
            self.properties_panel.show_node_properties(self.selected_nodes[0])
        # Single edge selected
        elif len(self.selected_edges) == 1 and len(self.selected_nodes) == 0:
            self.properties_panel.show_edge_properties(self.selected_edges[0])
        # Multiple or mixed selection
        elif len(self.selected_nodes) > 1 or len(self.selected_edges) > 1:
            self.properties_panel.clear_properties()
            self.properties_panel.title_label.setText(f"Multiple Selection")
            count_text = []
            if self.selected_nodes:
                count_text.append(f"{len(self.selected_nodes)} node(s)")
            if self.selected_edges:
                count_text.append(f"{len(self.selected_edges)} edge(s)")
            info = QLabel(f"Selected: {' and '.join(count_text)}\n\nSelect a single object to edit properties.")
            info.setWordWrap(True)
            self.properties_panel.properties_layout.addWidget(info)
        # No selection
        else:
            self.properties_panel.show_no_selection()

    def _auto_fit_view(self):
        """Auto-fit view to original graph nodes - applies same extents to Original, Scattering, and Kron views"""
        # Always use the original graph nodes for calculating extents
        if not self.nodes:
            print("No nodes to fit view to")
            return

        # Calculate extents based on original graph
        positions = np.array([node['pos'] for node in self.nodes])
        centroid = positions.mean(axis=0)

        distances = np.sqrt(((positions - centroid) ** 2).sum(axis=1))
        max_distance = distances.max() + self.node_radius

        extent = max_distance * config.AUTOFIT_PADDING_FACTOR

        # Apply the same extents to all three views
        self.base_xlim = (centroid[0] - extent, centroid[0] + extent)
        self.base_ylim = (centroid[1] - extent, centroid[1] + extent)
        self.scattering_base_xlim = (centroid[0] - extent, centroid[0] + extent)
        self.scattering_base_ylim = (centroid[1] - extent, centroid[1] + extent)
        self.scattering_original_base_xlim = (centroid[0] - extent, centroid[0] + extent)
        self.scattering_original_base_ylim = (centroid[1] - extent, centroid[1] + extent)
        self.kron_original_base_xlim = (centroid[0] - extent, centroid[0] + extent)
        self.kron_original_base_ylim = (centroid[1] - extent, centroid[1] + extent)
        self.zoom_level = 1.0

        print(f"Auto-fit: centered on ({centroid[0]:.3f}, {centroid[1]:.3f}), extent={extent:.3f}")
        print("Applied same extents to Original, Scattering, and Kron views")

        # Check which graph subtab is currently active and update the appropriate canvas
        current_tab = self.graph_subtabs.currentIndex()
        tab_text = self.graph_subtabs.tabText(current_tab) if current_tab >= 0 else ""

        if tab_text == "Scattering" and self.scattering_mode and hasattr(self, 'scattering_canvas') and self.scattering_canvas:
            # Viewing Scattering graph - re-render the scattering canvas with the new base limits
            self._render_scattering_graph()
        elif tab_text == "Kron" and hasattr(self, 'kron_graph') and self.kron_graph:
            # Viewing Kron graph - re-render the Kron canvas with the new base limits
            saved_canvas = self.canvas
            saved_nodes = self.nodes
            saved_edges = self.edges
            saved_base_xlim = self.base_xlim
            saved_base_ylim = self.base_ylim

            self.canvas = self.kron_canvas
            self.nodes = self.kron_graph['nodes']
            self.edges = self.kron_graph['edges']
            self.base_xlim = self.kron_original_base_xlim
            self.base_ylim = self.kron_original_base_ylim
            self._update_plot()

            self.canvas = saved_canvas
            self.nodes = saved_nodes
            self.edges = saved_edges
            self.base_xlim = saved_base_xlim
            self.base_ylim = saved_base_ylim
        else:
            # Viewing original graph - update the main canvas
            self._update_plot()

    def _on_graph_tab_changed(self, index):
        """Handle graph tab changes - refresh scattering view when switching to it"""
        # Check if scattering mode is active and we're switching to scattering tab (index 2)
        if self.scattering_mode and index == 2:
            # Refresh scattering view when switching to it
            self._refresh_scattering_view()

    def _switch_to_nth_visible_tab(self, n: int):
        """Switch to the Nth visible tab in graph_subtabs (1-indexed).

        Args:
            n: 1-indexed position of the visible tab to switch to
        """
        visible_count = 0
        for i in range(self.graph_subtabs.count()):
            if self.graph_subtabs.isTabVisible(i):
                visible_count += 1
                if visible_count == n:
                    self.graph_subtabs.setCurrentIndex(i)
                    tab_name = self.graph_subtabs.tabText(i)
                    print(f"Switched to {tab_name} view")
                    return
        print(f"No tab at position {n}")

    def _update_plot_no_grid(self):
        """Redraw the plot without grid (for export)"""
        # Clear any stale preview patches first
        self._clear_all_previews()

        self.canvas.ax.clear()

        # Set limits and aspect FIRST before drawing
        self.canvas.ax.set_xlim(*self._get_xlim())
        self.canvas.ax.set_ylim(*self._get_ylim())
        self.canvas.ax.set_aspect('equal', adjustable='datalim', anchor='C')
        # Force axes to use full figure area (reapply after aspect is set)
        self.canvas.ax.set_position([0, 0, 1, 1])

        # Skip grid drawing for export

        # Draw edges BEFORE nodes so nodes appear on top
        self._draw_edges()

        # Draw nodes (now after aspect is set, so limits are correct)
        self._draw_nodes()

        # No edge mode highlight for export

        # No title for export
        self.canvas.ax.set_title('')
        self.canvas.ax.axis('off')

        # Update properties panel
        if self.selected_nodes and len(self.selected_nodes) == 1:
            self.properties_panel.show_node_properties(self.selected_nodes[0])
        elif self.selected_edges and len(self.selected_edges) == 1:
            self.properties_panel.show_edge_properties(self.selected_edges[0])
        else:
            self.properties_panel.show_no_selection()

        self.canvas.draw()

        # Update matrix display when graph changes
        if hasattr(self, 'properties_panel'):
            # Clear manual SymPy code so it regenerates from the current graph
            self.properties_panel._sympy_code_manual = None
            self.properties_panel._update_matrix_display()
            self.properties_panel._update_sympy_code_display()

    def _update_plot(self, force_latex=False, use_idle=False):
        """Redraw the plot with debounced LaTeX rendering

        Args:
            force_latex: If True, render with LaTeX immediately without debouncing
            use_idle: If True, use non-blocking draw_idle() for smoother scrolling
        """
        # If in LaTeX mode and not forcing, use fast rendering with debounce
        if self.use_latex and not force_latex:
            # Stop any pending LaTeX render
            self.latex_debounce_timer.stop()

            # Temporarily switch to MathText for fast rendering
            # Always reset font params to ensure consistency, even if already in fast mode
            self.is_fast_rendering = True
            # Switch to MathText with same styling as non-LaTeX mode
            matplotlib.rcParams['text.usetex'] = False
            matplotlib.rcParams['text.latex.preamble'] = ''
            matplotlib.rcParams['mathtext.fontset'] = 'stix'
            matplotlib.rcParams['font.family'] = 'STIXGeneral'

            # Do the fast render
            self._do_plot_render(use_idle=use_idle)

            # Schedule LaTeX render after timeout
            self.latex_debounce_timer.start(self.latex_debounce_timeout)
        else:
            # Normal render (MathText mode or forced LaTeX)
            self._do_plot_render(use_idle=use_idle)

    def _render_with_latex(self):
        """Called by timer to render with LaTeX after changes settle"""
        if self.is_fast_rendering:
            self.is_fast_rendering = False
            # Switch back to LaTeX
            matplotlib.rcParams['text.usetex'] = True
            matplotlib.rcParams['text.latex.preamble'] = r'\usepackage{amsmath}\usepackage{sfmath}\renewcommand{\familydefault}{\sfdefault}'

            print("Rendering with LaTeX...")
            # Re-render with LaTeX
            self._do_plot_render()

    def _do_plot_render(self, use_idle=False):
        """Actually perform the plot rendering

        Args:
            use_idle: If True, use draw_idle() for non-blocking rendering (better for scrolling)
        """
        # Clear any stale preview patches first
        self._clear_all_previews()

        self.canvas.ax.clear()


        # print("DEBUG: CHECKING HOW PLOT FILLS CANVAS AREA")
        # print(f"DEBUG: {self._get_xlim()}")
        # print(f"DEBUG: {self._get_ylim()}")

        # Set limits and aspect FIRST before drawing
        self.canvas.ax.set_xlim(*self._get_xlim())
        self.canvas.ax.set_ylim(*self._get_ylim())
        self.canvas.ax.set_aspect('equal', adjustable='datalim', anchor='C')
        # Force axes to use full figure area (reapply after aspect is set)
        self.canvas.ax.set_position([0, 0, 1, 1])

        # Draw grid
        self._draw_grid()

        # Draw edges BEFORE nodes so nodes appear on top
        self._draw_edges()

        # Draw nodes (now after aspect is set, so limits are correct)
        self._draw_nodes()

        # Draw Kron mode selection rings
        if self.kron_mode:
            for node in self.nodes:
                node_radius = self.node_radius * node.get('node_size_mult', 1.0)
                # Check if node is selected (to be kept)
                is_selected = node in self.kron_selected_nodes

                # Draw colored ring: green for selected (keep), dark red for unselected (eliminate)
                ring_color = 'green' if is_selected else 'darkred'
                ring_alpha = 0.6

                selection_ring = patches.Circle(
                    node['pos'], node_radius * 1.3,
                    facecolor='none',
                    edgecolor=ring_color,
                    linewidth=3,
                    alpha=ring_alpha,
                    zorder=15
                )
                self.canvas.ax.add_patch(selection_ring)

        # Draw edge mode highlight (if first node is selected)
        if self.placement_mode in ['edge', 'edge_continuous'] and self.edge_mode_first_node is not None:
            node = self.edge_mode_first_node
            highlight_circle = patches.Circle(
                node['pos'], self.node_radius * node.get('node_size_mult', 1.0) * 1.3,
                facecolor='none',
                edgecolor='firebrick',
                linewidth=2,
                linestyle=':',
                zorder=15
            )
            self.canvas.ax.add_patch(highlight_circle)

        # Update status bar instead of title
        mode_str = f" | Mode: {self.placement_mode}" if self.placement_mode else ""
        edge_str = f" | Edges: {len(self.edges)}" if self.edges else ""
        latex_str = " | LaTeX" if self.use_latex else ""
        basis_str = " | BASIS ORDERING" if self.basis_ordering_mode else ""
        kron_str = " | KRON REDUCTION MODE" if self.kron_mode else ""
        fast_str = " (fast)" if self.is_fast_rendering else ""
        status_text = (
            f'{self.grid_type.capitalize()} Grid (rotation={self.grid_rotation}°, '
            f'zoom={self.zoom_level:.3f}x) | Nodes: {len(self.nodes)}{edge_str}{mode_str}{latex_str}{basis_str}{kron_str}{fast_str}'
        )
        self.status_label.setText(status_text)

        # No title on plot
        self.canvas.ax.set_title('')
        self.canvas.ax.axis('off')

        if use_idle:
            # Non-blocking render (better for smooth scrolling)
            self.canvas.draw_idle()
        else:
            # Blocking render (ensures immediate update)
            self.canvas.draw()
            # Force Qt to process events immediately
            QApplication.processEvents()

        # Update properties panel based on selection
        self._update_properties_panel()

        # Update basis display to reflect any changes to nodes/labels
        self.properties_panel._update_basis_display()

        # Update matrix display to reflect any changes to nodes/edges
        self.properties_panel._update_matrix_display()

        # Update SymPy code display to reflect any changes
        self.properties_panel._update_sympy_code_display()


def main():
    try:
        from Foundation import NSBundle
        bundle = NSBundle.mainBundle()
        info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
        info['CFBundleName'] = 'Paragraphulator'
    except ImportError:
        pass
    app = QApplication(sys.argv)
    icon_path = Path(__file__).resolve().parent.parent.parent / "misc" / "paragraphulator_ICON.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = Graphulator()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
