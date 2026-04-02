"""
Shortcut Editor Widget for Graphulator Settings.

This module provides a user interface for viewing and editing keyboard shortcuts.
Features:
- Tree view of shortcuts grouped by category
- Search/filter functionality
- Key sequence recording with QKeySequenceEdit
- Conflict detection and resolution
- Reset to defaults (single or all)
"""

from typing import Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QPushButton,
    QLabel,
    QLineEdit,
    QMessageBox,
    QKeySequenceEdit,
    QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QFont, QColor

from .shortcut_manager import ShortcutManager


class ShortcutEditorWidget(QWidget):
    """
    Widget for viewing and editing keyboard shortcuts.

    This widget displays all shortcuts in a categorized tree view and allows
    users to record new shortcuts, clear shortcuts, and reset to defaults.

    Signals:
        shortcuts_modified: Emitted when shortcuts have been changed
    """

    shortcuts_modified = Signal()

    def __init__(self, shortcut_manager: ShortcutManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.shortcut_manager = shortcut_manager
        self._current_action_id: Optional[str] = None
        self._setup_ui()
        self._populate_shortcuts()

        # Connect to manager updates
        shortcut_manager.shortcuts_changed.connect(self._populate_shortcuts)

    def _setup_ui(self):
        """Set up the widget UI."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        # Search/filter box
        search_layout = QHBoxLayout()
        search_label = QLabel("Filter:")
        search_layout.addWidget(search_label)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Type to filter shortcuts...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._filter_shortcuts)
        search_layout.addWidget(self.search_edit)

        layout.addLayout(search_layout)

        # Tree widget showing shortcuts by category
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Action", "Shortcut", "Default"])
        self.tree.setColumnWidth(0, 220)
        self.tree.setColumnWidth(1, 140)
        self.tree.setColumnWidth(2, 140)
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(True)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.tree)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

        # Selected shortcut info
        self.selected_label = QLabel("Double-click a shortcut to edit, or select and use the controls below.")
        self.selected_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.selected_label)

        # Shortcut recording area
        record_frame = QFrame()
        record_frame.setFrameShape(QFrame.Shape.StyledPanel)
        record_layout = QVBoxLayout()
        record_frame.setLayout(record_layout)

        # Key sequence edit row
        key_row = QHBoxLayout()
        key_row.addWidget(QLabel("New Shortcut:"))

        self.key_sequence_edit = QKeySequenceEdit()
        self.key_sequence_edit.setFixedWidth(200)
        self.key_sequence_edit.editingFinished.connect(self._on_recording_finished)
        self.key_sequence_edit.keySequenceChanged.connect(self._on_key_sequence_changed)
        key_row.addWidget(self.key_sequence_edit)

        self.apply_btn = QPushButton("Apply")
        self.apply_btn.clicked.connect(self._apply_new_shortcut)
        self.apply_btn.setEnabled(False)
        key_row.addWidget(self.apply_btn)

        self.clear_btn = QPushButton("Clear Shortcut")
        self.clear_btn.clicked.connect(self._clear_shortcut)
        self.clear_btn.setEnabled(False)
        key_row.addWidget(self.clear_btn)

        self.reset_one_btn = QPushButton("Reset to Default")
        self.reset_one_btn.clicked.connect(self._reset_selected_to_default)
        self.reset_one_btn.setEnabled(False)
        key_row.addWidget(self.reset_one_btn)

        key_row.addStretch()
        record_layout.addLayout(key_row)

        # Status/conflict label
        self.status_label = QLabel("")
        record_layout.addWidget(self.status_label)

        layout.addWidget(record_frame)

        # Bottom buttons
        button_layout = QHBoxLayout()

        platform_label = QLabel(f"Platform: {self.shortcut_manager.platform}")
        platform_label.setStyleSheet("color: gray;")
        button_layout.addWidget(platform_label)

        button_layout.addStretch()

        reset_all_btn = QPushButton("Reset All to Defaults")
        reset_all_btn.clicked.connect(self._reset_all_to_defaults)
        button_layout.addWidget(reset_all_btn)

        layout.addLayout(button_layout)

    def _populate_shortcuts(self):
        """Populate the tree with shortcuts grouped by category."""
        self.tree.clear()

        shortcuts_by_category = self.shortcut_manager.get_shortcuts_by_category()

        for category in self.shortcut_manager.get_categories():
            shortcuts = shortcuts_by_category.get(category, [])
            if not shortcuts:
                continue

            # Create category item
            category_item = QTreeWidgetItem([category, "", ""])
            category_item.setFlags(category_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            font = category_item.font(0)
            font.setBold(True)
            category_item.setFont(0, font)
            self.tree.addTopLevelItem(category_item)

            for shortcut_def in shortcuts:
                current_key = self.shortcut_manager.get_key_sequence(shortcut_def.action_id)
                default_key = self.shortcut_manager.get_default_key_sequence(shortcut_def.action_id)

                # Format for display
                current_display = self._format_key_for_display(current_key)
                default_display = self._format_key_for_display(default_key)

                item = QTreeWidgetItem([
                    shortcut_def.display_name,
                    current_display,
                    default_display
                ])
                item.setData(0, Qt.ItemDataRole.UserRole, shortcut_def.action_id)
                item.setToolTip(0, shortcut_def.description)

                # Highlight if different from default
                if current_key != default_key:
                    item.setForeground(1, QColor("#0066cc"))  # Blue for modified
                    font = item.font(1)
                    font.setBold(True)
                    item.setFont(1, font)

                category_item.addChild(item)

            category_item.setExpanded(True)

        # Re-apply filter if there's search text
        if self.search_edit.text():
            self._filter_shortcuts(self.search_edit.text())

    def _format_key_for_display(self, key_sequence: str) -> str:
        """Format a key sequence for display using native format."""
        if not key_sequence:
            return "(none)"
        ks = QKeySequence(key_sequence)
        return ks.toString(QKeySequence.SequenceFormat.NativeText)

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle single click on an item."""
        action_id = item.data(0, Qt.ItemDataRole.UserRole)
        if action_id:
            self._select_action(action_id, item.text(0))

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle double-click to start recording new shortcut."""
        action_id = item.data(0, Qt.ItemDataRole.UserRole)
        if action_id:
            self._select_action(action_id, item.text(0))
            # Focus the key sequence edit and clear it for recording
            self.key_sequence_edit.clear()
            self.key_sequence_edit.setFocus()

    def _select_action(self, action_id: str, display_name: str):
        """Select an action for editing."""
        self._current_action_id = action_id
        self.selected_label.setText(f"Editing: {display_name}")
        self.selected_label.setStyleSheet("color: black; font-weight: bold;")

        # Update current value in key sequence edit
        current_key = self.shortcut_manager.get_key_sequence(action_id)
        self.key_sequence_edit.setKeySequence(QKeySequence(current_key))

        # Enable buttons
        self.apply_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.reset_one_btn.setEnabled(True)

        self._check_conflict()

    def _on_key_sequence_changed(self, key_sequence: QKeySequence):
        """Handle changes to the key sequence during recording."""
        self._check_conflict()

    def _on_recording_finished(self):
        """Handle completion of shortcut recording."""
        self._check_conflict()

    def _check_conflict(self):
        """Check for conflicts and update the status label."""
        if not self._current_action_id:
            self.status_label.setText("")
            return

        key_seq = self.key_sequence_edit.keySequence()
        if key_seq.isEmpty():
            self.status_label.setText("Enter a key combination or click 'Clear Shortcut' to remove.")
            self.status_label.setStyleSheet("color: gray;")
            return

        key_str = key_seq.toString(QKeySequence.SequenceFormat.PortableText)

        # Check for conflicts
        conflict_action = self.shortcut_manager.check_conflict(
            key_str,
            exclude_action=self._current_action_id
        )

        if conflict_action:
            conflict_def = self.shortcut_manager.get_definition(conflict_action)
            conflict_name = conflict_def.display_name if conflict_def else conflict_action
            self.status_label.setText(f"Conflict: Already assigned to '{conflict_name}'")
            self.status_label.setStyleSheet("color: #cc3300; font-weight: bold;")  # Red
        else:
            self.status_label.setText("No conflicts - click 'Apply' to save.")
            self.status_label.setStyleSheet("color: #009933;")  # Green

    def _apply_new_shortcut(self):
        """Apply the recorded shortcut."""
        if not self._current_action_id:
            return

        key_seq = self.key_sequence_edit.keySequence()
        key_str = key_seq.toString(QKeySequence.SequenceFormat.PortableText)

        # Check for conflicts
        conflict_action = self.shortcut_manager.check_conflict(
            key_str, exclude_action=self._current_action_id
        )

        if conflict_action:
            # Ask user if they want to override
            conflict_def = self.shortcut_manager.get_definition(conflict_action)
            conflict_name = conflict_def.display_name if conflict_def else conflict_action

            reply = QMessageBox.question(
                self,
                "Shortcut Conflict",
                f"This shortcut is already assigned to '{conflict_name}'.\n\n"
                f"Do you want to remove it from '{conflict_name}' and assign it here?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Clear the conflicting shortcut
                self.shortcut_manager.set_key_sequence(conflict_action, "")
            else:
                return

        # Apply the shortcut
        success = self.shortcut_manager.set_key_sequence(self._current_action_id, key_str)
        if success:
            self.status_label.setText("Shortcut applied successfully!")
            self.status_label.setStyleSheet("color: #009933;")
            self.shortcuts_modified.emit()
        else:
            self.status_label.setText("Failed to apply shortcut.")
            self.status_label.setStyleSheet("color: #cc3300;")

    def _clear_shortcut(self):
        """Clear/unassign the shortcut for the current action."""
        if not self._current_action_id:
            return

        self.shortcut_manager.clear_key_sequence(self._current_action_id)
        self.key_sequence_edit.clear()
        self.status_label.setText("Shortcut cleared.")
        self.status_label.setStyleSheet("color: gray;")
        self.shortcuts_modified.emit()

    def _reset_selected_to_default(self):
        """Reset the selected shortcut to its default."""
        if not self._current_action_id:
            return

        self.shortcut_manager.reset_single_to_default(self._current_action_id)

        # Update the key sequence edit
        default_key = self.shortcut_manager.get_key_sequence(self._current_action_id)
        self.key_sequence_edit.setKeySequence(QKeySequence(default_key))

        self.status_label.setText("Shortcut reset to default.")
        self.status_label.setStyleSheet("color: gray;")
        self.shortcuts_modified.emit()

    def _reset_all_to_defaults(self):
        """Reset all shortcuts to their defaults."""
        reply = QMessageBox.question(
            self,
            "Reset All Shortcuts",
            "Are you sure you want to reset all shortcuts to their default values?\n\n"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.shortcut_manager.reset_to_defaults()
            self.status_label.setText("All shortcuts reset to defaults.")
            self.status_label.setStyleSheet("color: gray;")
            self.shortcuts_modified.emit()

            # Clear selection
            self._current_action_id = None
            self.key_sequence_edit.clear()
            self.selected_label.setText("Double-click a shortcut to edit, or select and use the controls below.")
            self.selected_label.setStyleSheet("color: gray; font-style: italic;")
            self.apply_btn.setEnabled(False)
            self.clear_btn.setEnabled(False)
            self.reset_one_btn.setEnabled(False)

    def _filter_shortcuts(self, text: str):
        """Filter shortcuts based on search text."""
        text = text.lower().strip()

        for i in range(self.tree.topLevelItemCount()):
            category_item = self.tree.topLevelItem(i)
            category_visible = False

            for j in range(category_item.childCount()):
                child = category_item.child(j)
                action_name = child.text(0).lower()
                shortcut = child.text(1).lower()
                default = child.text(2).lower()

                # Match against action name, current shortcut, or default
                visible = (
                    not text or
                    text in action_name or
                    text in shortcut or
                    text in default
                )
                child.setHidden(not visible)

                if visible:
                    category_visible = True

            category_item.setHidden(not category_visible)
            if category_visible:
                category_item.setExpanded(True)
