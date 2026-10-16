"""Дашборд: сводка прогресса, дорожная карта модулей и быстрые действия."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..content import Course


def _card(title: str, value: str, hint: str = "") -> QFrame:
    frame = QFrame()
    frame.setFrameShape(QFrame.StyledPanel)
    frame.setStyleSheet(
        "QFrame { border: 1px solid rgba(127,127,127,0.35); border-radius: 12px; padding: 10px; }"
    )
    layout = QVBoxLayout(frame)
    value_label = QLabel(value)
    value_label.setStyleSheet("font-size: 26px; font-weight: 700;")
    title_label = QLabel(title)
    title_label.setObjectName("Subtitle")
    layout.addWidget(value_label)
    layout.addWidget(title_label)
    if hint:
        hint_label = QLabel(hint)
        hint_label.setObjectName("Badge")
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)
    return frame


class DashboardView(QWidget):
    """Главный экран: что уже сделано и куда двигаться дальше."""

    open_module = Signal(str)
    continue_learning = Signal()
    export_report = Signal()
    reset_progress = Signal()

    def __init__(self, course: Course, store, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.course = course
        self.store = store

        title = QLabel("Ваш прогресс")
        title.setObjectName("Title")
        subtitle = QLabel(
            f"{course.stats()['modules']} модулей · {course.stats()['lessons']} уроков · "
            f"{course.stats()['tasks']} практических задач · {course.stats()['questions']} вопросов тестов"
        )
        subtitle.setObjectName("Subtitle")

        self.cards = QGridLayout()
        self.cards.setSpacing(12)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setFormat("Общий прогресс: %p%")
        self.progress.setFixedHeight(22)

        self.modules_box = QVBoxLayout()
        self.modules_box.setSpacing(8)

        container = QWidget()
        inner = QVBoxLayout(container)
        inner.addWidget(title)
        inner.addWidget(subtitle)
        inner.addLayout(self.cards)
        inner.addWidget(self.progress)
        header = QLabel("Дорожная карта")
        header.setStyleSheet("font-size: 18px; font-weight: 700; margin-top: 8px;")
        inner.addWidget(header)
        inner.addLayout(self.modules_box)
        inner.addStretch(1)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(container)

        continue_button = QPushButton("▶ Продолжить обучение")
        continue_button.setObjectName("Primary")
        continue_button.clicked.connect(self.continue_learning.emit)
        export_button = QPushButton("📄 Экспорт отчёта")
        export_button.clicked.connect(self.export_report.emit)
        reset_button = QPushButton("Сбросить прогресс")
        reset_button.clicked.connect(self.reset_progress.emit)

        buttons = QHBoxLayout()
        buttons.addWidget(continue_button)
        buttons.addWidget(export_button)
        buttons.addStretch(1)
        buttons.addWidget(reset_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.addWidget(scroll, 1)
        layout.addLayout(buttons)

        self.refresh()

    def refresh(self) -> None:
        summary = self.store.summary(self.course)
        while self.cards.count():
            item = self.cards.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.cards.addWidget(_card("Уроков пройдено", f"{summary['lessons_done']}/{summary['lessons_total']}"), 0, 0)
        self.cards.addWidget(_card("Задач решено", f"{summary['tasks_done']}/{summary['tasks_total']}"), 0, 1)
        self.cards.addWidget(_card("Тестов сдано", f"{summary['quizzes_passed']}/{summary['modules_total']}"), 0, 2)
        self.cards.addWidget(_card("Дней занятий", str(summary["days_active"])), 0, 3)
        self.progress.setValue(summary["overall_percent"])

        while self.modules_box.count():
            item = self.modules_box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for module in self.course.modules:
            done_lessons = sum(1 for lesson in module.lessons if self.store.is_lesson_done(lesson.key))
            done_tasks = 0
            if module.practice:
                done_tasks = sum(
                    1
                    for task in module.practice.tasks
                    if self.store.is_task_done(f"{module.module_id}/{task.tid}")
                )
            percent = self.store.quiz_percent(module.module_id)
            status = "🏆 пройден" if self.store.quiz_passed(module.module_id) else "в работе"
            row = QFrame()
            row.setFrameShape(QFrame.StyledPanel)
            row.setStyleSheet(
                "QFrame { border: 1px solid rgba(127,127,127,0.28); border-radius: 10px; padding: 8px; }"
            )
            row_layout = QHBoxLayout(row)
            text = QLabel(
                f"<b>{module.order}. {module.title}</b> <span style='color:#888'>· {status}</span><br>"
                f"<span style='color:#888'>уроки {done_lessons}/{module.lesson_count} · "
                f"практика {done_tasks}/{module.task_count} · тест {percent}%</span>"
            )
            text.setTextFormat(Qt.RichText)
            button = QPushButton("Открыть")
            button.clicked.connect(lambda _=False, mid=module.module_id: self.open_module.emit(mid))
            row_layout.addWidget(text, 1)
            row_layout.addWidget(button)
            self.modules_box.addWidget(row)
