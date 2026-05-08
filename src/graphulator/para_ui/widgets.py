"""
Utility widgets for paragraphulator.

This module contains reusable widget classes that don't depend on the main
application logic.
"""

import base64
import os
import re

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QDoubleSpinBox, QPlainTextEdit, QTextEdit,
    QInputDialog, QMessageBox
)
from PySide6.QtCore import Qt, QSize, QRect, QBuffer, QIODevice, QEvent, QMimeData
from PySide6.QtGui import (
    QFont, QPainter, QColor, QTextFormat, QTextCursor, QImage
)


# Warn the user when a single pasted/dropped image would exceed this size in
# the (base64-encoded) graph file. 1 MB raw ≈ 1.36 MB encoded.
IMAGE_SIZE_WARN_BYTES = 1_000_000

# Recognized image extensions for drag-and-drop file inserts.
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"}
EXT_TO_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".bmp": "image/bmp",
}


class ConsoleRedirector:
    """Redirect stdout/stderr to a QTextEdit widget"""

    def __init__(self, text_widget, original_stream):
        self.text_widget = text_widget
        self.original_stream = original_stream

    def write(self, text):
        """Write text to both the widget and original stream"""
        # Write to original stream (terminal) if available
        # Note: On Windows GUI apps (no console), sys.stdout/stderr may be None
        if self.original_stream is not None:
            self.original_stream.write(text)
            self.original_stream.flush()

        # Write to GUI console
        if self.text_widget is not None:
            self.text_widget.append(text.rstrip('\n'))

    def flush(self):
        """Flush the original stream if available"""
        if self.original_stream is not None:
            self.original_stream.flush()


class FineControlSpinBox(QDoubleSpinBox):
    """Double spinbox with Shift+Up/Down for finer control.

    - Up/Down: Change by normal singleStep
    - Shift+Up/Down: Change by 1/10 of singleStep (finer control)
    - Alt+Up/Down: Change by 10x singleStep (coarser control)

    Note: The Shift+Up/Down behavior is primarily handled by the global
    shortcut handler (_nudge_label) which checks for spinbox focus.
    """

    # Default tooltip explaining modifier controls
    MODIFIER_TOOLTIP = "Up/Down: normal step\nShift+Up/Down: fine (1/10)\nAlt+Up/Down: coarse (10x)"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Disable keyboard tracking so valueChanged only fires when:
        # - User presses Enter
        # - Spinbox loses focus
        # - User uses up/down buttons/arrows
        # This prevents focus issues on Windows where valueChanged firing
        # on every keystroke can interfere with the focus restoration code
        self.setKeyboardTracking(False)
        # Set tooltip if none provided
        if not self.toolTip():
            self.setToolTip(self.MODIFIER_TOOLTIP)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Up, Qt.Key_Down):
            # Determine step multiplier based on modifiers
            modifiers = event.modifiers()

            if modifiers & Qt.ShiftModifier:
                # Shift: finer control (1/10 step)
                multiplier = 0.1
            elif modifiers & Qt.AltModifier:
                # Alt/Option: coarser control (10x step)
                multiplier = 10.0
            else:
                # No modifier: normal step
                super().keyPressEvent(event)
                return

            # Calculate the step and new value
            step = self.singleStep() * multiplier
            if event.key() == Qt.Key_Up:
                new_value = self.value() + step
            else:
                new_value = self.value() - step

            # Clamp to range and set
            new_value = max(self.minimum(), min(self.maximum(), new_value))
            self.setValue(new_value)
            event.accept()
        else:
            super().keyPressEvent(event)


class LineNumberArea(QWidget):
    """Line number area widget for LineNumberTextEdit"""

    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)


class LineNumberTextEdit(QPlainTextEdit):
    """Plain text editor with line numbers in the margin.

    When ``markdown_mode`` is True, the editor also handles:
      - Pasting and dropping images (inserted as base64 data URIs)
      - Markdown formatting shortcuts (Ctrl+B/I/K/Shift+C)
      - Smart list continuation on Enter
    """

    def __init__(self, parent=None, markdown_mode: bool = False):
        super().__init__(parent)
        self.markdown_mode = markdown_mode
        self.line_number_area = LineNumberArea(self)

        # Connect signals for updating line numbers
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.update_line_number_area_width(0)
        self.highlight_current_line()

        # Set monospace font
        font = QFont("Menlo, Monaco, Consolas, Courier New, monospace")
        font.setPointSize(12)
        self.setFont(font)

        # Set tab width to 4 spaces
        metrics = self.fontMetrics()
        self.setTabStopDistance(4 * metrics.horizontalAdvance(' '))

        if self.markdown_mode:
            self.setAcceptDrops(True)

    def line_number_area_width(self):
        """Calculate the width needed for line numbers"""
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num //= 10
            digits += 1
        space = 10 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def update_line_number_area_width(self, _):
        """Update viewport margins when line count changes"""
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        """Update line number area on scroll or content change"""
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        """Handle resize to update line number area geometry"""
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(),
                                                 self.line_number_area_width(), cr.height()))

    def highlight_current_line(self):
        """Highlight the line containing the cursor"""
        extra_selections = []

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            line_color = QColor(Qt.GlobalColor.yellow).lighter(180)
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)

        self.setExtraSelections(extra_selections)

    def line_number_area_paint_event(self, event):
        """Paint the line numbers"""
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor(240, 240, 240))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor(120, 120, 120))
                painter.drawText(0, top, self.line_number_area.width() - 5,
                               self.fontMetrics().height(),
                               Qt.AlignmentFlag.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def zoom_in(self):
        """Increase font size"""
        font = self.font()
        size = font.pointSize()
        if size < 48:
            font.setPointSize(size + 1)
            self.setFont(font)
            # Update tab stop for new font
            metrics = self.fontMetrics()
            self.setTabStopDistance(4 * metrics.horizontalAdvance(' '))

    def zoom_out(self):
        """Decrease font size"""
        font = self.font()
        size = font.pointSize()
        if size > 6:
            font.setPointSize(size - 1)
            self.setFont(font)
            # Update tab stop for new font
            metrics = self.fontMetrics()
            self.setTabStopDistance(4 * metrics.horizontalAdvance(' '))

    # ===== Markdown-mode behaviors =====

    def event(self, e):
        # Override ShortcutOverride so the global Ctrl+B/I/K/Shift+C menu
        # shortcuts don't fire while typing in the notes editor; we handle
        # them as markdown formatting in keyPressEvent below.
        if self.markdown_mode and e.type() == QEvent.Type.ShortcutOverride:
            mods = e.modifiers()
            key = e.key()
            ctrl = mods & Qt.KeyboardModifier.ControlModifier
            shift = mods & Qt.KeyboardModifier.ShiftModifier
            if ctrl and not (mods & Qt.KeyboardModifier.AltModifier):
                if key in (Qt.Key.Key_B, Qt.Key.Key_I, Qt.Key.Key_K) and not shift:
                    e.accept()
                    return True
                if key == Qt.Key.Key_C and shift:
                    e.accept()
                    return True
        return super().event(e)

    def keyPressEvent(self, event):
        if self.markdown_mode:
            mods = event.modifiers()
            key = event.key()
            ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
            shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
            alt = bool(mods & Qt.KeyboardModifier.AltModifier)

            if ctrl and not alt:
                if key == Qt.Key.Key_B and not shift:
                    self._wrap_selection("**", "**", placeholder="bold")
                    return
                if key == Qt.Key.Key_I and not shift:
                    self._wrap_selection("*", "*", placeholder="italic")
                    return
                if key == Qt.Key.Key_K and not shift:
                    self._insert_link()
                    return
                if key == Qt.Key.Key_C and shift:
                    self._wrap_code_block()
                    return

            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (shift or ctrl or alt):
                if self._handle_list_continuation():
                    return

        super().keyPressEvent(event)

    def insertFromMimeData(self, source: QMimeData):
        if self.markdown_mode:
            # Clipboard image (e.g. screenshot) takes precedence over text.
            if source.hasImage():
                image = source.imageData()
                if isinstance(image, QImage) and not image.isNull():
                    self._insert_qimage(image)
                    return
            # File URLs pointing to image files.
            if source.hasUrls():
                image_urls = [u for u in source.urls()
                              if u.isLocalFile()
                              and os.path.splitext(u.toLocalFile())[1].lower() in IMAGE_EXTENSIONS]
                if image_urls:
                    for url in image_urls:
                        self._insert_image_file(url.toLocalFile())
                    return
        super().insertFromMimeData(source)

    def dragEnterEvent(self, event):
        if self.markdown_mode and event.mimeData().hasUrls():
            if any(u.isLocalFile()
                   and os.path.splitext(u.toLocalFile())[1].lower() in IMAGE_EXTENSIONS
                   for u in event.mimeData().urls()):
                event.acceptProposedAction()
                return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if self.markdown_mode and event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        if self.markdown_mode and event.mimeData().hasUrls():
            image_urls = [u for u in event.mimeData().urls()
                          if u.isLocalFile()
                          and os.path.splitext(u.toLocalFile())[1].lower() in IMAGE_EXTENSIONS]
            if image_urls:
                # Move cursor to drop position so the image lands where the user dropped it.
                drop_cursor = self.cursorForPosition(event.position().toPoint())
                self.setTextCursor(drop_cursor)
                for url in image_urls:
                    self._insert_image_file(url.toLocalFile())
                event.acceptProposedAction()
                return
        super().dropEvent(event)

    # --- Markdown helpers ---

    def _wrap_selection(self, prefix: str, suffix: str, placeholder: str = "text"):
        cursor = self.textCursor()
        if cursor.hasSelection():
            selected = cursor.selectedText()
            cursor.insertText(f"{prefix}{selected}{suffix}")
        else:
            cursor.insertText(f"{prefix}{placeholder}{suffix}")
            # Select the placeholder so the user can immediately overtype.
            new_pos = cursor.position() - len(suffix)
            cursor.setPosition(new_pos - len(placeholder), QTextCursor.MoveMode.MoveAnchor)
            cursor.setPosition(new_pos, QTextCursor.MoveMode.KeepAnchor)
            self.setTextCursor(cursor)

    def _insert_link(self):
        cursor = self.textCursor()
        selected = cursor.selectedText() if cursor.hasSelection() else ""
        url, ok = QInputDialog.getText(self, "Insert Link", "URL:")
        if not ok or not url:
            return
        text = selected or "link"
        cursor.insertText(f"[{text}]({url})")

    def _wrap_code_block(self):
        cursor = self.textCursor()
        if cursor.hasSelection():
            selected = cursor.selectedText().replace(' ', '\n')
            cursor.insertText(f"```\n{selected}\n```")
        else:
            cursor.insertText("```\n\n```")
            # Place cursor on the empty middle line.
            new_pos = cursor.position() - len("\n```")
            cursor.setPosition(new_pos)
            self.setTextCursor(cursor)

    def _handle_list_continuation(self) -> bool:
        cursor = self.textCursor()
        if cursor.hasSelection():
            return False
        block_text = cursor.block().text()

        ul = re.match(r'^(\s*)([-*+])(\s+)(.*)$', block_text)
        if ul:
            indent, marker, sep, content = ul.groups()
            if not content.strip():
                self._clear_current_block(cursor)
                return True
            cursor.insertText(f"\n{indent}{marker}{sep}")
            return True

        ol = re.match(r'^(\s*)(\d+)([.)])(\s+)(.*)$', block_text)
        if ol:
            indent, num, dot, sep, content = ol.groups()
            if not content.strip():
                self._clear_current_block(cursor)
                return True
            cursor.insertText(f"\n{indent}{int(num) + 1}{dot}{sep}")
            return True

        return False

    @staticmethod
    def _clear_current_block(cursor: QTextCursor):
        # Drop the empty bullet/marker so the user can keep typing as plain text
        # on the (now blank) current line. The Enter keystroke is consumed.
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock,
                            QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()

    # --- Image insertion helpers ---

    def _insert_qimage(self, image: QImage, mime: str = "image/png"):
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        # PNG keeps screenshots crisp; format must match the mime declared above.
        fmt = "PNG" if mime == "image/png" else mime.split("/", 1)[1].upper()
        if not image.save(buffer, fmt):
            return
        raw = bytes(buffer.data())
        if not self._confirm_image_size(len(raw)):
            return
        b64 = base64.b64encode(raw).decode("ascii")
        self._insert_image_markdown(f"data:{mime};base64,{b64}", alt="pasted-image")

    def _insert_image_file(self, path: str):
        ext = os.path.splitext(path)[1].lower()
        mime = EXT_TO_MIME.get(ext, "image/png")
        try:
            with open(path, "rb") as f:
                raw = f.read()
        except OSError as exc:
            QMessageBox.warning(self, "Image Insert Failed",
                                f"Could not read {path}:\n{exc}")
            return
        if not self._confirm_image_size(len(raw)):
            return
        b64 = base64.b64encode(raw).decode("ascii")
        alt = os.path.splitext(os.path.basename(path))[0] or "image"
        self._insert_image_markdown(f"data:{mime};base64,{b64}", alt=alt)

    def _insert_image_markdown(self, src: str, alt: str = "image"):
        cursor = self.textCursor()
        cursor.insertText(f"![{alt}]({src})")

    def _confirm_image_size(self, raw_bytes: int) -> bool:
        if raw_bytes <= IMAGE_SIZE_WARN_BYTES:
            return True
        kb = raw_bytes / 1024
        encoded_kb = (raw_bytes * 4 / 3) / 1024
        reply = QMessageBox.question(
            self,
            "Large image",
            f"This image is {kb:.0f} KB (~{encoded_kb:.0f} KB once base64-encoded "
            f"into the graph file). Insert it anyway?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes


class AspectRatioWidget(QWidget):
    """Widget that maintains a fixed aspect ratio for its child widget"""

    def __init__(self, widget, aspect_ratio=4/3, parent=None):
        super().__init__(parent)
        self.aspect_ratio = aspect_ratio  # width/height
        self.widget = widget

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widget)

    def resizeEvent(self, event):
        """Maintain aspect ratio during resize"""
        super().resizeEvent(event)

        # Get available size
        available_width = self.width()
        available_height = self.height()

        # Calculate size that fits while maintaining aspect ratio
        if available_width / available_height > self.aspect_ratio:
            # Width-limited: height is the constraint
            new_height = available_height
            new_width = int(new_height * self.aspect_ratio)
        else:
            # Height-limited: width is the constraint
            new_width = available_width
            new_height = int(new_width / self.aspect_ratio)

        # Center the widget
        x_offset = (available_width - new_width) // 2
        y_offset = (available_height - new_height) // 2

        self.widget.setGeometry(x_offset, y_offset, new_width, new_height)
