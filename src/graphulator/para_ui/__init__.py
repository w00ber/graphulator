"""
UI components for paragraphulator.
"""

from .shortcut_definitions import (
    ShortcutDefinition,
    SHORTCUT_DEFINITIONS,
    SHORTCUT_CATEGORIES,
    get_definitions_by_category,
    get_definition,
)
from .shortcut_manager import ShortcutManager
from .shortcut_editor import ShortcutEditorWidget
from .doc_template import (
    DocumentationTemplateProcessor,
    CachedDocumentationProcessor,
    create_shortcut_reference_table,
)

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
