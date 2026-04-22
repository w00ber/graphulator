"""
Documentation Template Processor for Graphulator.

This module provides template processing for documentation files (help, tutorial)
that contain shortcut placeholders. Placeholders are replaced with the user's
current shortcut bindings, formatted for display.

Placeholder format: {{shortcut:action.id}}
Example: {{shortcut:file.new}} -> `Ctrl+N` (on Windows/Linux) or `Cmd+N` (on macOS)
"""

import re
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .shortcut_manager import ShortcutManager


class DocumentationTemplateProcessor:
    """
    Processes documentation templates with dynamic shortcut values.

    Replaces {{shortcut:action_id}} placeholders with the current
    key bindings from the ShortcutManager.
    """

    # Regex pattern to match shortcut placeholders
    # Matches: {{shortcut:action.id}} or {{shortcut:action_id}}
    SHORTCUT_PATTERN = re.compile(r'\{\{shortcut:([a-zA-Z0-9_.]+)\}\}')

    def __init__(self, shortcut_manager: 'ShortcutManager'):
        """
        Initialize the template processor.

        Args:
            shortcut_manager: The ShortcutManager instance to get bindings from
        """
        self.shortcut_manager = shortcut_manager

    def process_markdown(self, template_content: str) -> str:
        """
        Replace shortcut placeholders with current bindings.

        Args:
            template_content: The markdown content with placeholders

        Returns:
            Processed markdown with placeholders replaced
        """
        def replace_shortcut(match: re.Match) -> str:
            action_id = match.group(1)
            display = self.shortcut_manager.get_key_sequence_display(action_id)

            if display == "(none)":
                return "`(unassigned)`"
            return f"`{display}`"

        return self.SHORTCUT_PATTERN.sub(replace_shortcut, template_content)

    def load_and_process(self, template_path: Path) -> str:
        """
        Load a template file and process it.

        Args:
            template_path: Path to the template file

        Returns:
            Processed content with placeholders replaced

        Raises:
            FileNotFoundError: If the template file doesn't exist
        """
        content = template_path.read_text(encoding='utf-8')
        return self.process_markdown(content)


class CachedDocumentationProcessor:
    """
    Cached wrapper for DocumentationTemplateProcessor.

    Caches processed documents and invalidates the cache when shortcuts change.
    """

    def __init__(self, shortcut_manager: 'ShortcutManager'):
        """
        Initialize the cached processor.

        Args:
            shortcut_manager: The ShortcutManager instance
        """
        self.shortcut_manager = shortcut_manager
        self.processor = DocumentationTemplateProcessor(shortcut_manager)
        self._cache: dict[str, str] = {}

        # Invalidate cache when shortcuts change
        shortcut_manager.shortcuts_changed.connect(self._invalidate_cache)

    def _invalidate_cache(self):
        """Clear the document cache."""
        self._cache.clear()

    def get_processed_document(self, doc_path: Path) -> str:
        """
        Get a processed document, using cache if available.

        Args:
            doc_path: Path to the document file

        Returns:
            Processed document content
        """
        cache_key = str(doc_path)

        if cache_key not in self._cache:
            self._cache[cache_key] = self.processor.load_and_process(doc_path)

        return self._cache[cache_key]

    def process_content(self, content: str, cache_key: Optional[str] = None) -> str:
        """
        Process content directly, optionally caching.

        Args:
            content: The markdown content to process
            cache_key: Optional cache key for this content

        Returns:
            Processed content
        """
        if cache_key and cache_key in self._cache:
            return self._cache[cache_key]

        processed = self.processor.process_markdown(content)

        if cache_key:
            self._cache[cache_key] = processed

        return processed


def create_shortcut_reference_table(shortcut_manager: 'ShortcutManager') -> str:
    """
    Generate a markdown table of all shortcuts.

    This can be used to dynamically generate a shortcut reference section
    in documentation.

    Args:
        shortcut_manager: The ShortcutManager instance

    Returns:
        Markdown formatted table of shortcuts
    """
    lines = [
        "| Action | Shortcut | Description |",
        "|--------|----------|-------------|",
    ]

    for category in shortcut_manager.get_categories():
        shortcuts = shortcut_manager.get_shortcuts_by_category().get(category, [])
        if not shortcuts:
            continue

        # Add category header
        lines.append(f"| **{category}** | | |")

        for defn in shortcuts:
            display = shortcut_manager.get_key_sequence_display(defn.action_id)
            lines.append(f"| {defn.display_name} | `{display}` | {defn.description} |")

    return "\n".join(lines)
