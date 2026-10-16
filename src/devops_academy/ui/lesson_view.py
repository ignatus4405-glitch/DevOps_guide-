"""Просмотр урока: markdown-контент + отметка о прохождении и навигация."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..content import Lesson, Module
from ..markdown_renderer import render_lesson
from ..theme import lesson_css


class LessonView(QWidget):
    """Один урок: заголовок, метаданные, HTML-контент, кнопки навигации."""

    completed_toggled = Signal(str, bool)
    navigate = Signal(int)  # +1 следующая, -1 предыдущая

    def __init__(self, content_root, glossary: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.content_root = content_root
        self.glossary = glossary
        self.lesson: Lesson | None = None
        self.module: Module | None = None

        self.title_label = QLabel("", self)
        self.title_label.setObjectName("Title")
        self.meta_label = QLabel("", self)
        self.meta_label.setObjectName("Subtitle")

        self.browser = QTextBrowser(self)
        self.browser.setObjectName("Lesson")
        self.browser.setOpenExternalLinks(True)
        self.browser.setOpenLinks(True)

        self.done_box = QCheckBox("Урок изучен", self)
        self.done_box.toggled.connect(self._on_done_toggled)

        self.prev_button = QPushButton("← Предыдущий", self)
        self.next_button = QPushButton("Следующий →", self)
        self.next_button.setObjectName("Primary")
        self.prev_button.clicked.connect(lambda: self.navigate.emit(-1))
        self.next_button.clicked.connect(lambda: self.navigate.emit(1))

        nav = QHBoxLayout()
        nav.addWidget(self.prev_button)
        nav.addStretch(1)
        nav.addWidget(self.done_box)
        nav.addStretch(1)
        nav.addWidget(self.next_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.addWidget(self.title_label)
        layout.addWidget(self.meta_label)
        layout.addWidget(self.browser, 1)
        layout.addLayout(nav)

    def load(self, module: Module, lesson: Lesson, done: bool = False, position: int = 0) -> None:
        self.module = module
        self.lesson = lesson
        self.title_label.setText(lesson.title)
        self.meta_label.setText(
            f"{module.title} · урок {position + 1} из {module.lesson_count} · "
            f"~{lesson.minutes} мин · уровень: {module.level}"
        )
        html = render_lesson(lesson.body, self.content_root, self.glossary)
        self.browser.setHtml(html)
        self.browser.setStyleSheet(lesson_css(self.current_theme()))
        self.browser.verticalScrollBar().setValue(0)
        self.done_box.blockSignals(True)
        self.done_box.setChecked(done)
        self.done_box.blockSignals(False)
        self.prev_button.setEnabled(position > 0)
        self.next_button.setEnabled(position < module.lesson_count - 1)

    def current_theme(self) -> str:
        window = self.window()
        return getattr(window, "theme", "dark")

    def _on_done_toggled(self, checked: bool) -> None:
        if self.lesson:
            self.completed_toggled.emit(self.lesson.key, checked)

    def apply_theme(self, theme: str) -> None:
        if self.lesson and self.module:
            self.browser.setStyleSheet(lesson_css(theme))
