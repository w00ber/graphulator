"""
ShortcutManager - Centralized keyboard shortcut management for Graphulator.

This module provides a centralized system for managing keyboard shortcuts with:
- OS-specific default key bindings
- User customization and persistence
- Conflict detection
- Dynamic updates to Qt shortcuts and menu actions
- Signals for documentation updates
"""

import logging
import sys
from typing import Dict, Optional, Callable, List, Any

logger = logging.getLogger(__name__)

from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtGui import QKeySequence, QShortcut, QAction
from PySide6.QtWidgets import QWidget

from .shortcut_definitions import (
    ShortcutDefinition,
    SHORTCUT_DEFINITIONS,
    SHORTCUT_CATEGORIES,
    get_definitions_by_category,
)


class ShortcutManager(QObject):
    """
    Centralized manager for all keyboard shortcuts.

    This class acts as a registry for shortcut definitions, manages current bindings,
    handles platform-specific defaults, and provides methods to create/update Qt shortcuts.

    Signals:
        shortcuts_changed: Emitted when any shortcut binding changes (for cache invalidation)
        shortcut_updated: Emitted with (action_id, old_key, new_key) when a specific shortcut changes
    """

    # Signal emitted when any shortcut changes (for documentation cache invalidation)
    shortcuts_changed = Signal()

    # Signal for specific shortcut change (action_id, old_key, new_key)
    shortcut_updated = Signal(str, str, str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # Shortcut definitions registry
        self._definitions: Dict[str, ShortcutDefinition] = {}

        # Current key bindings (action_id -> key sequence string)
        self._current_bindings: Dict[str, str] = {}

        # Qt objects for runtime updates
        self._qt_shortcuts: Dict[str, QShortcut] = {}
        self._qt_actions: Dict[str, QAction] = {}

        # Original handlers for re-binding after key changes
        self._handlers: Dict[str, Callable] = {}

        # Parent widget reference for creating shortcuts
        self._parent_widget = parent

        # Input focus wrapper function (set by main window)
        self._input_focus_wrapper: Optional[Callable] = None

        # Detect current platform
        self._platform = self._detect_platform()

        # Register all default shortcuts
        self._register_default_shortcuts()

    def _detect_platform(self) -> str:
        """Detect the current platform for default key selection."""
        if sys.platform == "darwin":
            return "darwin"
        elif sys.platform.startswith("win"):
            return "win32"
        return "linux"

    @property
    def platform(self) -> str:
        """Get the detected platform."""
        return self._platform

    def _get_default_for_platform(self, definition: ShortcutDefinition) -> str:
        """Get the default key sequence for the current platform."""
        # Try specific platform first
        if self._platform in definition.default_keys:
            return definition.default_keys[self._platform]
        # Fall back to "default" if present
        if "default" in definition.default_keys:
            return definition.default_keys["default"]
        # Last resort: first available
        return next(iter(definition.default_keys.values()), "")

    def _register_default_shortcuts(self):
        """Register all shortcut definitions from the definitions module."""
        for defn in SHORTCUT_DEFINITIONS:
            self._definitions[defn.action_id] = defn
            # Set current binding to platform default
            self._current_bindings[defn.action_id] = self._get_default_for_platform(defn)

    def set_input_focus_wrapper(self, wrapper: Callable):
        """
        Set the input focus wrapper function.

        This function wraps single-key shortcut handlers to prevent them from
        triggering when an input widget (spinbox, text edit, etc.) has focus.
        """
        self._input_focus_wrapper = wrapper

    # ===== Core Methods =====

    def get_definition(self, action_id: str) -> Optional[ShortcutDefinition]:
        """Get a shortcut definition by action ID."""
        return self._definitions.get(action_id)

    def get_key_sequence(self, action_id: str) -> str:
        """Get the current key sequence string for an action."""
        return self._current_bindings.get(action_id, "")

    def get_key_sequence_display(self, action_id: str) -> str:
        """Get the current key sequence formatted for display (native format)."""
        key_str = self._current_bindings.get(action_id, "")
        if not key_str:
            return "(none)"
        ks = QKeySequence(key_str)
        display = ks.toString(QKeySequence.SequenceFormat.NativeText)
        # Replace obscure escape symbol with more readable "Esc"
        display = display.replace("\u238b", "Esc")  # ⎋ symbol
        return display

    def set_key_sequence(self, action_id: str, key_sequence: str) -> bool:
        """
        Update the key sequence for an action.

        Args:
            action_id: The action to update
            key_sequence: New key sequence string (empty to clear)

        Returns:
            True if successful, False if conflict exists
        """
        # Check for conflicts (unless clearing)
        if key_sequence:
            conflict = self.check_conflict(key_sequence, exclude_action=action_id)
            if conflict:
                return False

        old_key = self._current_bindings.get(action_id, "")
        self._current_bindings[action_id] = key_sequence

        # Update Qt shortcut/action if exists
        self._update_qt_shortcut(action_id)
        self._update_qt_action(action_id)

        # Emit signals
        self.shortcut_updated.emit(action_id, old_key, key_sequence)
        self.shortcuts_changed.emit()
        return True

    def clear_key_sequence(self, action_id: str):
        """Clear/unassign the key sequence for an action."""
        self.set_key_sequence(action_id, "")

    def check_conflict(
        self, key_sequence: str, exclude_action: Optional[str] = None
    ) -> Optional[str]:
        """
        Check if a key sequence conflicts with an existing binding.

        Args:
            key_sequence: The key sequence to check
            exclude_action: Action ID to exclude from conflict check (e.g., the action being edited)

        Returns:
            The action_id of the conflicting action, or None if no conflict
        """
        if not key_sequence:
            return None

        # Normalize the key sequence for comparison
        normalized = QKeySequence(key_sequence).toString(
            QKeySequence.SequenceFormat.PortableText
        )

        for action_id, current_key in self._current_bindings.items():
            if action_id == exclude_action:
                continue
            if not current_key:
                continue

            current_normalized = QKeySequence(current_key).toString(
                QKeySequence.SequenceFormat.PortableText
            )
            if current_normalized == normalized:
                return action_id

        return None

    def reset_to_defaults(self):
        """Reset all shortcuts to their platform-specific defaults."""
        for action_id, definition in self._definitions.items():
            default_key = self._get_default_for_platform(definition)
            old_key = self._current_bindings.get(action_id, "")
            self._current_bindings[action_id] = default_key

            # Update Qt objects
            self._update_qt_shortcut(action_id)
            self._update_qt_action(action_id)

            if old_key != default_key:
                self.shortcut_updated.emit(action_id, old_key, default_key)

        self.shortcuts_changed.emit()

    def reset_single_to_default(self, action_id: str):
        """Reset a single shortcut to its platform-specific default."""
        if action_id not in self._definitions:
            return

        definition = self._definitions[action_id]
        default_key = self._get_default_for_platform(definition)
        self.set_key_sequence(action_id, default_key)

    def get_default_key_sequence(self, action_id: str) -> str:
        """Get the platform-specific default key sequence for an action."""
        definition = self._definitions.get(action_id)
        if not definition:
            return ""
        return self._get_default_for_platform(definition)

    # ===== Qt Integration =====

    def bind_shortcut(
        self,
        action_id: str,
        handler: Callable,
        parent_widget: Optional[QWidget] = None,
        wrap_for_input: bool = False,
        context: Qt.ShortcutContext = Qt.ShortcutContext.WindowShortcut,
    ) -> Optional[QShortcut]:
        """
        Create and bind a QShortcut for an action.

        Args:
            action_id: The action ID to bind
            handler: Callback function when shortcut is activated
            parent_widget: Parent widget for the shortcut (uses manager's parent if None)
            wrap_for_input: Whether to wrap handler for input focus protection
            context: Shortcut context (default: WindowShortcut)

        Returns:
            The created QShortcut, or None if action not found
        """
        definition = self._definitions.get(action_id)
        if not definition:
            logger.warning("Unknown shortcut action_id: %s", action_id)
            return None

        parent = parent_widget or self._parent_widget
        if not parent:
            logger.warning("No parent widget for shortcut: %s", action_id)
            return None

        key_seq = self._current_bindings.get(action_id, "")

        # Store original handler for re-binding
        self._handlers[action_id] = handler

        # Determine if we need input wrapping
        needs_wrap = wrap_for_input or definition.is_single_key
        if needs_wrap and self._input_focus_wrapper:
            actual_handler = self._input_focus_wrapper(handler)
        else:
            actual_handler = handler

        # Create the shortcut
        if key_seq:
            shortcut = QShortcut(QKeySequence(key_seq), parent)
            shortcut.setContext(context)
            shortcut.activated.connect(actual_handler)
        else:
            # Create a disabled shortcut that can be enabled later
            shortcut = QShortcut(parent)
            shortcut.setContext(context)
            shortcut.activated.connect(actual_handler)
            shortcut.setEnabled(False)

        self._qt_shortcuts[action_id] = shortcut
        return shortcut

    def bind_action(self, action_id: str, action: QAction) -> bool:
        """
        Bind a QAction to use the managed shortcut.

        The action's shortcut will be set to the current binding and updated
        when the binding changes.

        Args:
            action_id: The action ID to bind
            action: The QAction to bind

        Returns:
            True if successful, False if action_id not found
        """
        if action_id not in self._definitions:
            logger.warning("Unknown shortcut action_id: %s", action_id)
            return False

        key_seq = self._current_bindings.get(action_id, "")
        if key_seq:
            action.setShortcut(QKeySequence(key_seq))
        else:
            action.setShortcut(QKeySequence())

        self._qt_actions[action_id] = action
        return True

    def _update_qt_shortcut(self, action_id: str):
        """Update a Qt shortcut when the binding changes."""
        shortcut = self._qt_shortcuts.get(action_id)
        if not shortcut:
            return

        key_seq = self._current_bindings.get(action_id, "")
        if key_seq:
            shortcut.setKey(QKeySequence(key_seq))
            shortcut.setEnabled(True)
        else:
            shortcut.setKey(QKeySequence())
            shortcut.setEnabled(False)

    def _update_qt_action(self, action_id: str):
        """Update a Qt action's shortcut when the binding changes."""
        action = self._qt_actions.get(action_id)
        if not action:
            return

        key_seq = self._current_bindings.get(action_id, "")
        if key_seq:
            action.setShortcut(QKeySequence(key_seq))
        else:
            action.setShortcut(QKeySequence())

    # ===== Category Access =====

    def get_shortcuts_by_category(self) -> Dict[str, List[ShortcutDefinition]]:
        """Get all shortcuts grouped by category (ordered)."""
        result: Dict[str, List[ShortcutDefinition]] = {}

        # Initialize with empty lists in category order
        for category in SHORTCUT_CATEGORIES:
            result[category] = []

        # Add shortcuts to their categories
        for defn in self._definitions.values():
            if defn.category in result:
                result[defn.category].append(defn)
            else:
                # Category not in predefined list
                if defn.category not in result:
                    result[defn.category] = []
                result[defn.category].append(defn)

        # Remove empty categories
        return {k: v for k, v in result.items() if v}

    def get_categories(self) -> List[str]:
        """Get ordered list of categories that have shortcuts."""
        by_cat = self.get_shortcuts_by_category()
        return [c for c in SHORTCUT_CATEGORIES if c in by_cat]

    # ===== Persistence =====

    def export_bindings(self) -> Dict[str, str]:
        """
        Export current bindings for persistence.

        Returns a dict of action_id -> key_sequence for all non-default bindings.
        """
        result = {}
        for action_id, key_seq in self._current_bindings.items():
            # Only export if different from default
            default = self.get_default_key_sequence(action_id)
            if key_seq != default:
                result[action_id] = key_seq
        return result

    def export_all_bindings(self) -> Dict[str, str]:
        """Export all current bindings (including defaults)."""
        return dict(self._current_bindings)

    def import_bindings(self, bindings: Dict[str, str]):
        """
        Import bindings from persistence.

        Only updates bindings for known action IDs.
        """
        for action_id, key_sequence in bindings.items():
            if action_id in self._definitions:
                self._current_bindings[action_id] = key_sequence
                self._update_qt_shortcut(action_id)
                self._update_qt_action(action_id)

        self.shortcuts_changed.emit()

    def has_custom_bindings(self) -> bool:
        """Check if any shortcuts have been customized from defaults."""
        for action_id, key_seq in self._current_bindings.items():
            default = self.get_default_key_sequence(action_id)
            if key_seq != default:
                return True
        return False

    # ===== Utility Methods =====

    def get_all_action_ids(self) -> List[str]:
        """Get a list of all registered action IDs."""
        return list(self._definitions.keys())

    def is_modified(self, action_id: str) -> bool:
        """Check if a specific shortcut has been modified from default."""
        current = self._current_bindings.get(action_id, "")
        default = self.get_default_key_sequence(action_id)
        return current != default
