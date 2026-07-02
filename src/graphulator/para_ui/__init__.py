"""
UI components for paragraphulator.
"""

from .doc_template import (
    CachedDocumentationProcessor,
    DocumentationTemplateProcessor,
    create_shortcut_reference_table,
)
from .shortcut_definitions import (
    SHORTCUT_CATEGORIES,
    SHORTCUT_DEFINITIONS,
    ShortcutDefinition,
    get_definition,
    get_definitions_by_category,
)
from .shortcut_editor import ShortcutEditorWidget
from .shortcut_manager import ShortcutManager

__all__ = [
    # Shortcut definitions
    "ShortcutDefinition",
    "SHORTCUT_DEFINITIONS",
    "SHORTCUT_CATEGORIES",
    "get_definitions_by_category",
    "get_definition",
    # Shortcut manager
    "ShortcutManager",
    # Shortcut editor UI
    "ShortcutEditorWidget",
    # Documentation templates
    "DocumentationTemplateProcessor",
    "CachedDocumentationProcessor",
    "create_shortcut_reference_table",
]
