"""
Utility widgets for paragraphulator.

This module contains reusable widget classes that don't depend on the main
application logic.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QDoubleSpinBox, QPlainTextEdit, QTextEdit
)
from PySide6.QtCore import Qt, QSize, QRect
from PySide6.QtGui import QFont, QPainter, QColor, QTextFormat


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
    """Plain text editor with line numbers in the margin"""

    def __init__(self, parent=None):
        super().__init__(parent)
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
