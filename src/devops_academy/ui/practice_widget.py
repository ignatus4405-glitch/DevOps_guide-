"""Практика: пошаговые задания, безопасный симулятор и проверка результата.

Симулятор хранит ответ только в памяти и никогда не запускает shell-команды на
машине пользователя. Выполненные критерии сверяются с practice.json.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
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
from ..practice_simulator import PracticeSandbox
from ..theme import lesson_css


class PracticeWidget(QWidget):
    """Список задач модуля, шаги выполнения и проверка в виртуальном стенде."""

    task_solved = Signal(str, bool)  # task_key, solved
    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.module: Module | None = None
        self.task: Task | None = None
        self.hints_shown = 0
        self._guide_markdown = ""
        self.sandbox = PracticeSandbox()

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
        self.instructions.setMinimumHeight(170)

        self.answer = QPlainTextEdit(self)
        self.answer.setObjectName("CodeInput")
        self.answer.setPlaceholderText(
            "Введите команды, конфигурацию, скрипт или отчёт. Тренажёр не запускает их в вашей ОС."
        )
        self.answer.setFixedHeight(90)
        self.answer.textChanged.connect(self._answer_changed)

        self.manual_confirm = QCheckBox(
            "Я выполнил задание и проверил результат в своей учебной среде",
            self,
        )
        self.manual_confirm.setVisible(False)

        self.lab_output = QPlainTextEdit(self)
        self.lab_output.setObjectName("CodeInput")
        self.lab_output.setReadOnly(True)
        self.lab_output.setPlaceholderText("Результат учебного стенда появится здесь.")
        self.lab_output.setFixedHeight(110)

        self.feedback = QLabel("", self)
        self.feedback.setWordWrap(True)

        self.run_button = QPushButton("▶ Запустить в тренажёре", self)
        self.run_button.setObjectName("Primary")
        self.run_button.clicked.connect(self._run)

        self.check_button = QPushButton("Проверить результат", self)
        self.check_button.setObjectName("Success")
        self.check_button.setEnabled(False)
        self.check_button.clicked.connect(self._verify)

        self.hint_button = QPushButton("Показать подсказку", self)
        self.hint_button.clicked.connect(self._show_hint)
        self.solution_button = QPushButton("Показать решение", self)
        self.solution_button.clicked.connect(self._show_solution)
        self.back_button = QPushButton("← К урокам", self)
        self.back_button.clicked.connect(self.back_requested.emit)

        execution_buttons = QHBoxLayout()
        execution_buttons.addWidget(self.run_button)
        execution_buttons.addWidget(self.check_button)
        execution_buttons.addStretch(1)
        execution_buttons.addWidget(self.back_button)

        help_buttons = QHBoxLayout()
        help_buttons.addWidget(self.hint_button)
        help_buttons.addWidget(self.solution_button)
        help_buttons.addStretch(1)

        right = QVBoxLayout()
        right.addWidget(self.goal)
        right.addWidget(self.instructions, 1)
        right.addWidget(QLabel("Ваше решение / команды / отчёт:", self))
        right.addWidget(self.answer)
        right.addWidget(self.manual_confirm)
        right.addWidget(QLabel("Результат учебного стенда:", self))
        right.addWidget(self.lab_output)
        right.addWidget(self.feedback)
        right.addLayout(execution_buttons)
        right.addLayout(help_buttons)

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
        self.task = None
        self.sandbox.clear()
        solved = solved_keys or set()
        self.title_label.setText(f"Практика: {module.title}")
        self.subtitle.setText(
            f"{module.task_count} задач · пошаговые инструкции · симуляция и проверка результата "
            "без запуска команд на вашем компьютере"
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
        else:
            self.instructions.clear()
            self.goal.clear()
            self.answer.clear()
            self.lab_output.clear()
            self.manual_confirm.setVisible(False)
            self.run_button.setEnabled(False)
            self.check_button.setEnabled(False)
            self.hint_button.setEnabled(False)
            self.solution_button.setEnabled(False)

    def _select_task(self, row: int) -> None:
        if self.module is None or self.module.practice is None or row < 0:
            return
        tasks = self.module.practice.tasks
        if row >= len(tasks):
            return
        self.task = tasks[row]
        self.sandbox.discard(self.task.tid)
        self.hints_shown = 0
        self.goal.setText(f"<b>Цель:</b> {render_plain(self.task.goal, self.current_theme())}")
        self.goal.setTextFormat(Qt.RichText)

        steps = "\n".join(f"{index}. {item}" for index, item in enumerate(self.task.instructions, start=1))
        expected_result = self.task.validation_hint or "Сверьте результат с целью задания и обратной связью тренажёра."
        self._guide_markdown = (
            f"## Как выполнить задание\n\n{steps}\n\n"
            f"## Как проверить результат\n\n{expected_result}\n\n"
            "## Безопасность тренажёра\n\n"
            "Решение проверяется в виртуальном пространстве. Команды не выполняются, "
            "а реальные файлы и настройки компьютера не меняются."
        )
        self.instructions.setHtml(render_plain(self._guide_markdown, self.current_theme()))
        self.instructions.setStyleSheet(lesson_css(self.current_theme()))
        self.answer.clear()
        self.lab_output.clear()
        self.feedback.clear()
        self.manual_confirm.setChecked(False)
        self.manual_confirm.setVisible(self.task.check_type == "manual")
        self.run_button.setEnabled(True)
        self.check_button.setEnabled(False)
        self.hint_button.setEnabled(bool(self.task.hints))
        self.hint_button.setText(f"Показать подсказку ({len(self.task.hints)})" if self.task.hints else "Подсказок нет")
        self.solution_button.setEnabled(bool(self.task.solution))

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
    def _answer_changed(self) -> None:
        if self.task is None:
            return
        self.sandbox.discard(self.task.tid)
        self.check_button.setEnabled(False)
        self.manual_confirm.setChecked(False)
        if self.lab_output.toPlainText():
            self.lab_output.setPlainText("Ответ изменён. Запустите тренажёр ещё раз перед проверкой.")

    def _run(self) -> None:
        if self.task is None:
            return
        report = self.sandbox.run(self.task, self.answer.toPlainText())
        self.lab_output.setPlainText(report.output)
        self.check_button.setEnabled(report.status == "ready")
        self._set_feedback(
            "Ответ отправлен в безопасный тренажёр." if report.status == "ready" else report.output,
            success=report.status == "ready",
        )

    def _verify(self) -> None:
        if self.task is None or self.module is None:
            return
        report = self.sandbox.verify(self.task, manual_confirmed=self.manual_confirm.isChecked())
        self.lab_output.appendPlainText("\n" + report.output)
        if report.status == "passed":
            self._set_feedback("Результат проверен в тренажёре.", success=True)
            self.task_solved.emit(f"{self.module.module_id}/{self.task.tid}", True)
        elif report.status == "manual_confirmation":
            self._set_feedback("Проверьте критерий вручную и подтвердите его флажком.", success=False)
        else:
            self._set_feedback("Проверка не пройдена. Исправьте ответ и запустите тренажёр повторно.", success=False)

    def _set_feedback(self, message: str, *, success: bool) -> None:
        self.feedback.setText(("✅ " if success else "ℹ️ ") + message)
        self.feedback.setObjectName("FeedbackOk" if success else "FeedbackBad")
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)

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

    def _show_solution(self) -> None:
        if not self.task:
            return
        self.instructions.setHtml(
            render_plain(
                f"{self._guide_markdown}\n\n---\n\n"
                f"## Эталонное решение\n\n```bash\n{self.task.solution}\n```\n\n"
                f"**Пояснение:** {self.task.feedback}",
                self.current_theme(),
            )
        )
        self.instructions.setStyleSheet(lesson_css(self.current_theme()))
