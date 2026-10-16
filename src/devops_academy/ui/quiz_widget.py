"""Прохождение теста по модулю с мгновенной проверкой и разбором ответов."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..content import Module, Question
from ..markdown_renderer import render_plain


class QuestionWidget(QGroupBox):
    """Один вопрос: варианты (radio/checkbox) или текстовое поле."""

    def __init__(self, index: int, question: Question, parent: QWidget | None = None) -> None:
        super().__init__(f"Вопрос {index}", parent)
        self.question = question
        self.controls: list = []
        layout = QVBoxLayout(self)

        text = QLabel(render_plain(question.question))
        text.setTextFormat(Qt.RichText)
        text.setWordWrap(True)
        layout.addWidget(text)

        if question.qtype == "text":
            self.line = QLineEdit(self)
            self.line.setPlaceholderText("Введите ответ одним словом или командой")
            layout.addWidget(self.line)
            self.controls.append(self.line)
        else:
            for option in question.options:
                if question.qtype == "multiple":
                    widget = QCheckBox(option, self)
                else:
                    widget = QCheckBox(option, self)
                    widget.setProperty("exclusive_group", True)
                widget.clicked.connect(self._enforce_exclusive)
                layout.addWidget(widget)
                self.controls.append(widget)

        self.explanation = QLabel("", self)
        self.explanation.setWordWrap(True)
        self.explanation.setTextFormat(Qt.RichText)
        self.explanation.setVisible(False)
        layout.addWidget(self.explanation)

    def _enforce_exclusive(self) -> None:
        """Для одиночного выбора оставляем только один отмеченный вариант."""
        if self.question.qtype != "single":
            return
        sender = self.sender()
        for widget in self.controls:
            if widget is not sender:
                widget.setChecked(False)

    def answer(self):
        if self.question.qtype == "text":
            return self.controls[0].text()
        return [pos for pos, widget in enumerate(self.controls) if widget.isChecked()]

    def mark(self, correct: bool) -> None:
        for widget in self.controls:
            widget.setEnabled(False)
        self.explanation.setText(
            ("✅ <b>Верно.</b> " if correct else "❌ <b>Ошибка.</b> ")
            + render_plain(self.question.explanation or "Разбор не добавлен.")
        )
        self.explanation.setVisible(True)
        self.setStyleSheet("QGroupBox { border: 1px solid %s; }" % ("#3ecf8e" if correct else "#f2635f"))


class QuizWidget(QWidget):
    """Тест целиком: вопросы, проверка, результат, сохранение прогресса."""

    finished = Signal(str, int, int, bool)  # module_id, correct, total, passed

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.module: Module | None = None
        self.question_widgets: list[QuestionWidget] = []

        self.title_label = QLabel("", self)
        self.title_label.setObjectName("Title")
        self.subtitle = QLabel("", self)
        self.subtitle.setObjectName("Subtitle")

        self.progress = QProgressBar(self)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        self.container = QWidget(self)
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.addStretch(1)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(self.container)

        self.result_label = QLabel("", self)
        self.result_label.setWordWrap(True)
        self.result_label.setTextFormat(Qt.RichText)

        self.check_button = QPushButton("Проверить ответы", self)
        self.check_button.setObjectName("Primary")
        self.check_button.clicked.connect(self.check)
        self.reset_button = QPushButton("Пройти заново", self)
        self.reset_button.clicked.connect(self.reload)

        buttons = QHBoxLayout()
        buttons.addWidget(self.check_button)
        buttons.addWidget(self.reset_button)
        buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle)
        layout.addWidget(self.progress)
        layout.addWidget(scroll, 1)
        layout.addWidget(self.result_label)
        layout.addLayout(buttons)

    def load(self, module: Module) -> None:
        self.module = module
        self.title_label.setText(f"Тест: {module.title}")
        quiz = module.quiz
        if quiz is None:
            self.subtitle.setText("Для модуля не добавлен тест")
            self._clear()
            return
        self.subtitle.setText(
            f"{quiz.max_score} вопросов · порог сдачи {quiz.pass_score}% · "
            "отвечайте без подсказок, разбор появится после проверки"
        )
        self._clear()
        self.question_widgets = []
        for index, question in enumerate(quiz.questions, start=1):
            widget = QuestionWidget(index, question, self.container)
            self.container_layout.insertWidget(self.container_layout.count() - 1, widget)
            self.question_widgets.append(widget)
        self.progress.setValue(0)
        self.result_label.clear()
        self.check_button.setEnabled(True)

    def _clear(self) -> None:
        self.question_widgets = []
        while self.container_layout.count() > 1:
            item = self.container_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def check(self) -> None:
        if self.module is None or self.module.quiz is None:
            return
        quiz = self.module.quiz
        correct = 0
        for widget in self.question_widgets:
            ok = widget.question.is_correct(widget.answer())
            widget.mark(ok)
            correct += 1 if ok else 0
        total = len(self.question_widgets)
        percent = round(correct / total * 100) if total else 0
        passed = percent >= quiz.pass_score
        self.progress.setValue(percent)
        color = "#3ecf8e" if passed else "#f2635f"
        verdict = "Тест сдан" if passed else "Пока не сдано"
        self.result_label.setText(
            f"<span style='color:{color}; font-size:16px; font-weight:700'>"
            f"{verdict}: {correct} из {total} ({percent}%), порог {quiz.pass_score}%</span>"
        )
        self.check_button.setEnabled(False)
        self.finished.emit(self.module.module_id, correct, total, passed)

    def reload(self) -> None:
        if self.module is not None:
            self.load(self.module)
