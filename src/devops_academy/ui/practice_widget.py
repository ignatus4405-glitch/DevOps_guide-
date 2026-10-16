"""Практические задачи с автопроверкой введённых команд/ответов.

Проверка намеренно «мягкая»: приложение не запускает команды на машине
пользователя, а анализирует введённый текст по правилам из practice.json
(типы: regex_all, regex_any, equals, manual). Для каждой задачи есть подсказки,
эталонное решение и способ проверить результат руками.
"""

from __future__ import annotations

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..content import Module, Task
from ..markdown_renderer import render_plain
from ..theme import lesson_css


class TaskChecker:
    """Логика проверки ответа — вынесена отдельно, чтобы покрывать тестами."""

    @staticmethod
    def normalise(text: str) -> str:
        text = text.strip().lower()
        text = text.replace("«", '"').replace("»", '"')
        return re.sub(r"\s+", " ", text)

    @classmethod
    def check(cls, task: Task, answer: str) -> tuple[bool, str]:
        if not answer.strip():
            return False, "Введите команду или ответ"
        if task.check_type == "manual":
            return True, task.feedback or "Задача на самопроверку — сверьтесь с эталоном ниже."
        value = cls.normalise(answer)
        if task.check_type == "equals":
            allowed = {cls.normalise(p) for p in task.patterns}
            if value in allowed:
                return True, task.feedback or "Верно."
            return False, "Ответ не совпал с эталоном. Проверьте синтаксис и порядок аргументов."
        if task.check_type == "regex_any":
            for pattern in task.patterns:
                if re.search(pattern, answer, re.IGNORECASE | re.MULTILINE):
                    return True, task.feedback or "Верно."
            return False, "Ни одно из ожидаемых решений не найдено. Перечитайте подсказки."
        # по умолчанию regex_all
        missing = [
            pattern
            for pattern in task.patterns
            if not re.search(pattern, answer, re.IGNORECASE | re.MULTILINE)
        ]
        if not missing:
            return True, task.feedback or "Верно."
        return (
            False,
            f"Не хватает {len(missing)} элемента(ов) из {len(task.patterns)}. "
            "Подсказка: включите нужные ключи и параметры.",
        )


class PracticeWidget(QWidget):
    """Список задач модуля + форма ответа + проверка."""

    task_solved = Signal(str, bool)  # task_key, solved

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.module: Module | None = None
        self.task: Task | None = None
        self.hints_shown = 0

        self.title_label = QLabel("", self)
        self.title_label.setObjectName("Title")
        self.subtitle = QLabel("", self)
        self.subtitle.setObjectName("Subtitle")

        self.task_list = QListWidget(self)
        self.task_list.setMaximumWidth(320)
        self.task_list.currentRowChanged.connect(self._select_task)

        self.goal = QLabel("", self)
        self.goal.setWordWrap(True)

        self.instructions = QTextBrowser(self)
        self.instructions.setObjectName("Lesson")
        self.instructions.setMinimumHeight(200)

        self.answer = QPlainTextEdit(self)
        self.answer.setObjectName("CodeInput")
        self.answer.setPlaceholderText("Введите команду(ы) — например: sudo chmod 644 /etc/hosts")
        self.answer.setFixedHeight(90)

        self.feedback = QLabel("", self)
        self.feedback.setWordWrap(True)

        self.hint_button = QPushButton("Показать подсказку", self)
        self.hint_button.clicked.connect(self._show_hint)
        self.check_button = QPushButton("Проверить", self)
        self.check_button.setObjectName("Primary")
        self.check_button.clicked.connect(self._check)
        self.solution_button = QPushButton("Показать решение", self)
        self.solution_button.clicked.connect(self._show_solution)
        self.done_button = QPushButton("Отметить как выполненную", self)
        self.done_button.setObjectName("Success")
        self.done_button.clicked.connect(self._mark_done)

        buttons = QHBoxLayout()
        buttons.addWidget(self.check_button)
        buttons.addWidget(self.hint_button)
        buttons.addWidget(self.solution_button)
        buttons.addStretch(1)
        buttons.addWidget(self.done_button)

        right = QVBoxLayout()
        right.addWidget(self.goal)
        right.addWidget(self.instructions, 1)
        right.addWidget(QLabel("Ваш ответ / команда:", self))
        right.addWidget(self.answer)
        right.addWidget(self.feedback)
        right.addLayout(buttons)

        body = QHBoxLayout()
        body.addWidget(self.task_list)
        body.addLayout(right, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle)
        layout.addLayout(body, 1)

    # ------------------------------------------------------------------
    def load(self, module: Module, solved_keys: set[str] | None = None) -> None:
        self.module = module
        solved = solved_keys or set()
        self.title_label.setText(f"Практика: {module.title}")
        self.subtitle.setText(
            f"{module.task_count} задач · проверяйте команды прямо здесь, "
            "подсказки и эталонные решения приложены"
        )
        self.task_list.clear()
        for index, task in enumerate(module.practice.tasks if module.practice else [], start=1):
            key = f"{module.module_id}/{task.tid}"
            mark = "✅ " if key in solved else ""
            item = QListWidgetItem(f"{mark}{index}. {task.title}\n   сложность: {task.level}")
            item.setData(Qt.UserRole, task.tid)
            self.task_list.addItem(item)
        if self.task_list.count():
            self.task_list.setCurrentRow(0)

    def _select_task(self, row: int) -> None:
        if self.module is None or self.module.practice is None or row < 0:
            return
        tasks = self.module.practice.tasks
        if row >= len(tasks):
            return
        self.task = tasks[row]
        self.hints_shown = 0
        self.goal.setText(f"<b>Цель:</b> {render_plain(self.task.goal)}")
        self.goal.setTextFormat(Qt.RichText)
        bullets = "\n".join(f"- {item}" for item in self.task.instructions)
        checks = f"\n\n**Как проверить результат:** {self.task.validation_hint}" if self.task.validation_hint else ""
        self.instructions.setHtml(render_plain(f"{bullets}{checks}"))
        self.instructions.setStyleSheet(lesson_css(self.current_theme()))
        self.answer.clear()
        self.feedback.clear()
        self.hint_button.setEnabled(bool(self.task.hints))
        self.hint_button.setText(f"Показать подсказку ({len(self.task.hints)})" if self.task.hints else "Подсказок нет")
        self.done_button.setEnabled(True)

    def mark_solved(self, task_key: str, solved: bool = True) -> None:
        """Обновить галочку у задачи, не перезагружая список (сохраняет фидбэк)."""
        if self.module is None or self.module.practice is None:
            return
        for index, task in enumerate(self.module.practice.tasks):
            if f"{self.module.module_id}/{task.tid}" != task_key:
                continue
            item = self.task_list.item(index)
            if item is None:
                return
            text = item.text().lstrip("✅ ").strip()
            item.setText(f"✅ {text}" if solved else text)
            return

    def current_theme(self) -> str:
        return getattr(self.window(), "theme", "dark")

    def apply_theme(self, theme: str) -> None:
        self.instructions.setStyleSheet(lesson_css(theme))

    # ------------------------------------------------------------------
    def _show_hint(self) -> None:
        if not self.task or not self.task.hints:
            return
        index = min(self.hints_shown, len(self.task.hints) - 1)
        self.feedback.setText(f"💡 <b>Подсказка {index + 1}:</b> {self.task.hints[index]}")
        self.hints_shown = min(self.hints_shown + 1, len(self.task.hints))
        self.hint_button.setText(
            f"Показать подсказку ({len(self.task.hints) - self.hints_shown})"
            if self.hints_shown < len(self.task.hints)
            else "Все подсказки показаны"
        )

    def _check(self) -> None:
        if not self.task or self.module is None:
            return
        ok, message = TaskChecker.check(self.task, self.answer.toPlainText())
        prefix = "✅" if ok else "❌"
        self.feedback.setText(f"{prefix} {message}")
        self.feedback.setObjectName("FeedbackOk" if ok else "FeedbackBad")
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)
        if ok:
            self.task_solved.emit(f"{self.module.module_id}/{self.task.tid}", True)

    def _show_solution(self) -> None:
        if not self.task:
            return
        self.instructions.setHtml(
            render_plain(
                f"**Эталонное решение:**\n\n```bash\n{self.task.solution}\n```\n\n"
                f"**Пояснение:** {self.task.feedback}"
            )
        )
        self.instructions.setStyleSheet(lesson_css(self.current_theme()))

    def _mark_done(self) -> None:
        if not self.task or self.module is None:
            return
        self.task_solved.emit(f"{self.module.module_id}/{self.task.tid}", True)
        self.feedback.setText("✅ Задача отмечена как выполненная — прогресс сохранён.")
        self.feedback.setObjectName("FeedbackOk")
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)
