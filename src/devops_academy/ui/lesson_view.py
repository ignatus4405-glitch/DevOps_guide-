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

NEXT_LABEL = "Следующий →"
EXAM_LABEL = "Итоговый экзамен →"


class LessonView(QWidget):
    """Один урок: заголовок, метаданные, HTML-контент, кнопки навигации."""

    completed_toggled = Signal(str, bool)
    navigate = Signal(int)  # +1 следующая, -1 предыдущая
    quiz_requested = Signal()
    practice_requested = Signal()

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

        self.quiz_button = QPushButton("Пройти тест · 3 вопроса", self)
        self.quiz_button.setObjectName("Secondary")
        self.quiz_button.clicked.connect(self.quiz_requested.emit)

        self.practice_button = QPushButton("Практика модуля", self)
        self.practice_button.setObjectName("Secondary")
        self.practice_button.setToolTip("Открыть пошаговые практические задания модуля")
        self.practice_button.clicked.connect(self.practice_requested.emit)

        self.prev_button = QPushButton("← Предыдущий", self)
        self.next_button = QPushButton(NEXT_LABEL, self)
        self.next_button.setObjectName("Primary")
        self.prev_button.clicked.connect(lambda: self.navigate.emit(-1))
        self.next_button.clicked.connect(lambda: self.navigate.emit(1))

        nav = QHBoxLayout()
        nav.addWidget(self.prev_button)
        nav.addStretch(1)
        nav.addWidget(self.done_box)
        nav.addWidget(self.quiz_button)
        nav.addWidget(self.practice_button)
        nav.addStretch(1)
        nav.addWidget(self.next_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.addWidget(self.title_label)
        layout.addWidget(self.meta_label)
        layout.addWidget(self.browser, 1)
        layout.addLayout(nav)

    def load(
        self,
        module: Module,
        lesson: Lesson,
        done: bool = False,
        position: int = 0,
        *,
        has_prev: bool | None = None,
        has_next: bool | None = None,
        next_label: str = NEXT_LABEL,
        quiz_score: int | None = None,
    ) -> None:
        """Показывает урок.

        ``has_prev``/``has_next`` задаёт вызывающий: уроки идут сплошной лентой
        через границы модулей, поэтому «край модуля» — не то же самое, что «край
        курса». Если их не передали, поведение прежнее — навигация внутри модуля.
        """
        self.module = module
        self.lesson = lesson
        self.title_label.setText(lesson.title)
        self.meta_label.setText(
            f"{module.title} · урок {position + 1} из {module.lesson_count} · "
            f"~{lesson.minutes} мин · уровень: {module.level}"
        )
        self.browser.setStyleSheet(lesson_css(self.current_theme()))
        self.browser.setHtml(self._render())
        self.browser.verticalScrollBar().setValue(0)
        self.done_box.blockSignals(True)
        self.done_box.setChecked(done)
        self.done_box.blockSignals(False)
        self.set_quiz_score(quiz_score)
        self.practice_button.setVisible(bool(module.practice and module.practice.tasks))

        if has_prev is None:
            has_prev = position > 0
        if has_next is None:
            has_next = position < module.lesson_count - 1
        self.set_navigation(has_prev, has_next, next_label)

    def set_quiz_score(self, score: int | None) -> None:
        """Обновляет кнопку необязательного теста после урока."""
        has_quiz = self.lesson is not None and self.lesson.quiz is not None
        self.quiz_button.setVisible(has_quiz)
        if not has_quiz:
            return
        if score is None:
            self.quiz_button.setText(f"Пройти тест · {self.lesson.quiz.max_score} вопроса")
            self.quiz_button.setToolTip("Необязательная короткая проверка знаний по этому уроку")
        else:
            self.quiz_button.setText(f"Повторить тест · лучший результат {score}%")
            self.quiz_button.setToolTip("Тест можно пройти повторно; лучший результат сохранён")

    def set_navigation(self, has_prev: bool, has_next: bool, next_label: str = NEXT_LABEL) -> None:
        """Включает кнопки перехода и подписывает «Следующий» на краю курса."""
        self.prev_button.setEnabled(has_prev)
        self.next_button.setEnabled(has_next)
        self.next_button.setText(next_label)
        self.prev_button.setToolTip("" if has_prev else "Это первый урок курса")
        if not has_next:
            self.next_button.setToolTip("Это последний урок курса")
        elif next_label != NEXT_LABEL:
            self.next_button.setToolTip("После последнего урока открывается итоговый экзамен")
        else:
            self.next_button.setToolTip("")

    def current_theme(self) -> str:
        window = self.window()
        return getattr(window, "theme", "dark")

    def _on_done_toggled(self, checked: bool) -> None:
        if self.lesson:
            self.completed_toggled.emit(self.lesson.key, checked)

    def _render(self) -> str:
        """HTML урока в текущей теме (цвета таблиц задаются инлайново — см. render_lesson)."""
        if not self.lesson:
            return ""
        return render_lesson(self.lesson.body, self.content_root, self.glossary, self.current_theme())

    def apply_theme(self, theme: str) -> None:
        if self.lesson and self.module:
            self.browser.setStyleSheet(lesson_css(theme))
            # Таблицы и врезки окрашены прямо в HTML, поэтому контент перерисовываем,
            # сохраняя позицию прокрутки.
            position = self.browser.verticalScrollBar().value()
            self.browser.setHtml(self._render())
            self.browser.verticalScrollBar().setValue(position)
