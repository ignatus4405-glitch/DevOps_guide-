"""Главное окно: навигация по курсу, уроки, практика, тесты, экзамен, обновления."""

from __future__ import annotations

import random
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..content import Course, Module, Quiz
from ..paths import content_dir
from ..progress import ProgressStore
from ..theme import stylesheet
from ..updater import (
    UpdateChecker,
    UpdateInfo,
    mark_checked,
    should_check,
    skip_version,
    skipped_version,
    snooze,
)
from ..version import APP_NAME, APP_VERSION, BUILD_NUMBER, GITHUB_RELEASES_URL
from .dashboard import DashboardView
from .glossary_dialog import GlossaryDialog
from .lesson_view import LessonView
from .practice_widget import PracticeWidget
from .quiz_widget import QuizWidget
from .update_dialog import UpdateDialog

MODE_LESSON = "lesson"
MODE_PRACTICE = "practice"
MODE_QUIZ = "quiz"
MODE_EXAM = "exam"


def build_exam_module(course: Course, question_count: int = 20) -> Module:
    """Собирает экзамен: случайные вопросы из всех модулей курса."""
    pool = course.all_questions()
    random.shuffle(pool)
    selected = pool[:question_count]
    return Module(
        module_id="exam",
        order=999,
        title="Итоговый экзамен",
        level="все уровни",
        summary="Случайные вопросы из всех модулей курса",
        estimated_minutes=30,
        objectives=["Проверить знания по всему курсу"],
        tags=["exam"],
        path=Path("."),
        lessons=[],
        quiz=Quiz(module_id="exam", title="Итоговый экзамен", pass_score=80, questions=selected),
        practice=None,
    )


class MainWindow(QMainWindow):
    def __init__(self, course: Course, store: ProgressStore | None = None) -> None:
        super().__init__()
        self.course = course
        self.store = store or ProgressStore()
        self.theme = str(self.store.get("ui/theme", "dark"))
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION} — полный курс DevOps Engineer")
        self.resize(1360, 880)

        self.sidebar = QListWidget(self)
        self.sidebar.setObjectName("Sidebar")

        self.stack = QStackedWidget(self)
        self.dashboard = DashboardView(course, self.store, self)
        self.lesson_view = LessonView(course.root, course.glossary, self)
        self.practice_view = PracticeWidget(self)
        self.quiz_view = QuizWidget(self)
        for widget in (self.dashboard, self.lesson_view, self.practice_view, self.quiz_view):
            self.stack.addWidget(widget)

        self.current_module: Module | None = None
        self.current_lesson_index = 0
        self.current_mode = ""

        self._build_sidebar()
        self._build_toolbar()
        self._build_statusbar()
        self._connect_signals()

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(self.sidebar)
        splitter.addWidget(self.stack)
        splitter.setSizes([340, 1020])

        # Баннер уведомления об обновлении живёт над основным содержимым окна.
        self.update_banner = self._build_update_banner()
        container = QWidget(self)
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self.update_banner)
        outer.addWidget(splitter, 1)
        self.setCentralWidget(container)

        self.apply_theme(self.theme, save=False)
        self.sidebar.setCurrentRow(0)  # дашборд

        geometry = self.store.get("ui/geometry")
        if geometry:
            self.restoreGeometry(geometry)
        if str(self.store.get("updates/auto_check", "true")).lower() in ("true", "1"):
            QTimer.singleShot(2500, self.check_updates_silent)

    # ------------------------------------------------------------------
    # Построение интерфейса
    # ------------------------------------------------------------------
    def _build_sidebar(self) -> None:
        header = QLabel(f"{APP_NAME}  ·  сборка {BUILD_NUMBER}")
        header.setObjectName("BrandSub")
        self.sidebar_header = header

        dashboard_item = QListWidgetItem("🏠 Обзор и прогресс")
        dashboard_item.setData(Qt.UserRole, ("dashboard", "", ""))
        self.sidebar.addItem(dashboard_item)

        for module in self.course.modules:
            item = QListWidgetItem(f"{module.order}. {module.title}")
            item.setData(Qt.UserRole, ("module", module.module_id, ""))
            self.sidebar.addItem(item)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Основные действия", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        glossary = QAction("📚 Глоссарий", self)
        glossary.setShortcut(QKeySequence("Ctrl+G"))
        glossary.triggered.connect(self.show_glossary)
        toolbar.addAction(glossary)

        exam = QAction("🎓 Экзамен", self)
        exam.setShortcut(QKeySequence("Ctrl+E"))
        exam.triggered.connect(self.start_exam)
        toolbar.addAction(exam)

        check = QAction("🔄 Проверить обновления", self)
        check.triggered.connect(lambda: self.check_updates_silent(manual=True))
        toolbar.addAction(check)

        theme = QAction("🌓 Сменить тему", self)
        theme.setShortcut(QKeySequence("Ctrl+T"))
        theme.triggered.connect(self.toggle_theme)
        toolbar.addAction(theme)

        settings = QAction("⚙ Настройки", self)
        settings.triggered.connect(self.show_settings)
        toolbar.addAction(settings)

        about = QAction("ℹ О программе", self)
        about.triggered.connect(self.show_about)
        toolbar.addAction(about)

    def _build_statusbar(self) -> None:
        bar = QStatusBar(self)
        self.setStatusBar(bar)
        self.status_progress = QLabel("", self)
        self.status_version = QLabel(f"версия {APP_VERSION}", self)
        bar.addWidget(self.status_progress, 1)
        bar.addPermanentWidget(self.status_version)
        self.refresh_status()

    def _build_update_banner(self) -> QFrame:
        """Панель «доступна новая версия» — показывается, когда проверка нашла релиз."""
        banner = QFrame(self)
        banner.setVisible(False)
        banner.setStyleSheet(
            "QFrame { background: rgba(79,156,249,0.18); border: 1px solid #4f9cf9;"
            " border-radius: 10px; margin: 6px 12px; padding: 6px; }"
        )
        label = QLabel("", banner)
        label.setWordWrap(True)
        details = QPushButton("Подробнее и установить", banner)
        details.setObjectName("Primary")
        details.clicked.connect(self.show_pending_update)
        later = QPushButton("Позже", banner)
        later.clicked.connect(lambda: banner.setVisible(False))

        row = QHBoxLayout(banner)
        row.addWidget(label, 1)
        row.addWidget(details)
        row.addWidget(later)

        self.banner_label = label
        self.pending_update: UpdateInfo | None = None
        return banner

    def _connect_signals(self) -> None:
        self.sidebar.currentRowChanged.connect(self.on_sidebar_changed)
        self.dashboard.open_module.connect(self.open_module)
        self.dashboard.continue_learning.connect(self.continue_learning)
        self.dashboard.export_report.connect(self.export_report)
        self.dashboard.reset_progress.connect(self.reset_progress)
        self.lesson_view.completed_toggled.connect(self.on_lesson_toggled)
        self.lesson_view.navigate.connect(self.navigate_lesson)
        self.practice_view.task_solved.connect(self.on_task_solved)
        self.quiz_view.finished.connect(self.on_quiz_finished)

    # ------------------------------------------------------------------
    # Навигация
    # ------------------------------------------------------------------
    def on_sidebar_changed(self, row: int) -> None:
        if row <= 0:
            self.show_dashboard()
            return
        index = row - 1
        if 0 <= index < len(self.course.modules):
            self.open_module(self.course.modules[index].module_id)

    def show_dashboard(self) -> None:
        self.dashboard.refresh()
        self.stack.setCurrentWidget(self.dashboard)

    def open_module(self, module_id: str, mode: str = MODE_LESSON, lesson_id: str = "") -> None:
        module = self.course.module(module_id)
        if module is None:
            return
        self.current_module = module
        if mode == MODE_PRACTICE:
            solved = {
                f"{module.module_id}/{task.tid}"
                for task in (module.practice.tasks if module.practice else [])
                if self.store.is_task_done(f"{module.module_id}/{task.tid}")
            }
            self.practice_view.load(module, solved)
            self.stack.setCurrentWidget(self.practice_view)
            self.current_mode = MODE_PRACTICE
        elif mode == MODE_QUIZ:
            self.quiz_view.load(module)
            self.stack.setCurrentWidget(self.quiz_view)
            self.current_mode = MODE_QUIZ
        else:
            index = 0
            if lesson_id:
                found = next(
                    (i for i, lesson in enumerate(module.lessons) if lesson.lesson_id == lesson_id), 0
                )
                index = found
            self.open_lesson(module, index)
        self.refresh_status()

    def open_lesson(self, module: Module, index: int) -> None:
        index = max(0, min(index, module.lesson_count - 1))
        lesson = module.lessons[index]
        self.current_lesson_index = index
        self.lesson_view.load(
            module, lesson, self.store.is_lesson_done(lesson.key), position=index
        )
        self.store.set_last_lesson(lesson.key)
        self.stack.setCurrentWidget(self.lesson_view)
        self.current_mode = MODE_LESSON
        self._sync_sidebar(module)
        self.refresh_status()

    def navigate_lesson(self, delta: int) -> None:
        if self.current_module is None:
            return
        self.open_lesson(self.current_module, self.current_lesson_index + delta)

    def continue_learning(self) -> None:
        """Продолжить с последнего открытого урока, иначе — с первого модуля."""
        last = self.store.data.last_lesson
        if last and "/" in last:
            module_id, lesson_id = last.split("/", 1)
            if self.course.module(module_id):
                self.open_module(module_id, MODE_LESSON, lesson_id)
                return
        if self.course.modules:
            self.open_module(self.course.modules[0].module_id)

    def _sync_sidebar(self, module: Module) -> None:
        index = self.course.modules.index(module)
        self.sidebar.blockSignals(True)
        self.sidebar.setCurrentRow(index + 1)
        self.sidebar.blockSignals(False)

    def start_exam(self) -> None:
        module = build_exam_module(self.course)
        self.current_module = module
        self.quiz_view.load(module)
        self.stack.setCurrentWidget(self.quiz_view)
        self.current_mode = MODE_EXAM
        self.statusBar().showMessage(
            f"Экзамен: {module.question_count} случайных вопросов, порог 80%", 8000
        )

    # ------------------------------------------------------------------
    # Реакции на события
    # ------------------------------------------------------------------
    def on_lesson_toggled(self, key: str, done: bool) -> None:
        self.store.set_lesson_done(key, done)
        self.refresh_status()
        self.dashboard.refresh()
        self.statusBar().showMessage(
            f"{'Урок отмечен пройденным' if done else 'Отметка снята'}: {key}", 4000
        )

    def on_task_solved(self, task_key: str, solved: bool) -> None:
        self.store.set_task_done(task_key, solved)
        self.practice_view.mark_solved(task_key, solved)
        self.refresh_status()
        self.dashboard.refresh()

    def on_quiz_finished(self, module_id: str, correct: int, total: int, passed: bool) -> None:
        if module_id != "exam":
            self.store.save_quiz_result(module_id, correct, total, passed)
        else:
            QMessageBox.information(
                self,
                "Результат экзамена",
                f"Правильных ответов: {correct} из {total} "
                f"({round(correct / total * 100) if total else 0}%).",
            )
        self.refresh_status()
        self.dashboard.refresh()

    def refresh_status(self) -> None:
        summary = self.store.summary(self.course)
        self.status_progress.setText(
            f"Прогресс: {summary['overall_percent']}% · уроки {summary['lessons_done']}/"
            f"{summary['lessons_total']} · задачи {summary['tasks_done']}/{summary['tasks_total']} · "
            f"тесты {summary['quizzes_passed']}/{summary['modules_total']}"
        )

    # ------------------------------------------------------------------
    # Темы, глоссарий, отчёты
    # ------------------------------------------------------------------
    def apply_theme(self, theme: str, save: bool = True) -> None:
        self.theme = theme
        application = QApplication.instance()
        if application is not None:
            application.setStyleSheet(stylesheet(theme))
        self.lesson_view.apply_theme(theme)
        self.practice_view.apply_theme(theme)
        if save:
            self.store.set("ui/theme", theme)

    def toggle_theme(self) -> None:
        self.apply_theme("light" if self.theme == "dark" else "dark")

    def show_glossary(self) -> None:
        GlossaryDialog(self.course.glossary, self).exec()

    def export_report(self) -> None:
        default = str(Path.home() / "devops-academy-report.md")
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить отчёт", default, "Markdown (*.md)")
        if not path:
            return
        Path(path).write_text(self.store.export_markdown(self.course), encoding="utf-8")
        self.statusBar().showMessage(f"Отчёт сохранён: {path}", 6000)

    def reset_progress(self) -> None:
        answer = QMessageBox.question(
            self,
            "Сбросить прогресс?",
            "Будут удалены отметки об уроках, решения задач и результаты тестов. Продолжить?",
        )
        if answer == QMessageBox.Yes:
            self.store.reset()
            self.dashboard.refresh()
            self.refresh_status()

    def show_settings(self) -> None:
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Настройки")
        auto = str(self.store.get("updates/auto_check", "true")).lower() in ("true", "1")
        dialog.setText(
            "DevOps Academy\n\n"
            f"Автопроверка обновлений: {'включена' if auto else 'выключена'}\n"
            f"Тема: {'тёмная' if self.theme == 'dark' else 'светлая'}\n"
            f"Контент: {self.course.root}\n\n"
            "Кнопка «Переключить автообновление» меняет режим проверки релизов на GitHub."
        )
        dialog.addButton("Переключить автообновление", QMessageBox.ActionRole)
        dialog.addButton("Проверить обновления", QMessageBox.ActionRole)
        dialog.addButton("Закрыть", QMessageBox.RejectRole)
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked and clicked.text() == "Переключить автообновление":
            self.store.set("updates/auto_check", "false" if auto else "true")
            self.statusBar().showMessage(f"Автообновление {'выключено' if auto else 'включено'}", 5000)
        elif clicked and clicked.text() == "Проверить обновления":
            self.check_updates_silent(manual=True)

    def show_about(self) -> None:
        QMessageBox.information(
            self,
            "О программе",
            f"<b>{APP_NAME}</b> {APP_VERSION}<br>"
            f"Сборка: {BUILD_NUMBER}<br><br>"
            "Офлайн-курс: уроки, практика с автопроверкой, тесты и экзамен.<br>"
            f"Релизы и обновления: <a href='{GITHUB_RELEASES_URL}'>{GITHUB_RELEASES_URL}</a><br><br>"
            "Обновление версий выполняется автоматически через GitHub Actions: "
            "каждая сборка на ветке main создаёт новый релиз, а приложение сообщает о новой версии.",
        )

    # ------------------------------------------------------------------
    # Обновления
    # ------------------------------------------------------------------
    def check_updates_silent(self, manual: bool = False) -> None:
        if not manual and not should_check(self.store):
            return
        if manual:
            self.statusBar().showMessage("Проверяем обновления на GitHub…", 5000)
        self.checker = UpdateChecker(APP_VERSION, self)
        self.checker.found.connect(lambda info: self.notify_update(info, manual))
        self.checker.checked.connect(lambda _: self.on_no_updates(manual))
        self.checker.failed.connect(lambda message: self.on_check_failed(message, manual))
        self.checker.start()

    def on_no_updates(self, manual: bool) -> None:
        mark_checked(self.store)
        if manual:
            QMessageBox.information(
                self, "Обновления", f"У вас последняя версия — {APP_VERSION}."
            )

    def on_check_failed(self, message: str, manual: bool) -> None:
        mark_checked(self.store)
        if manual:
            QMessageBox.warning(
                self,
                "Не удалось проверить обновления",
                f"{message}.\nПроверьте подключение к интернету и повторите позже.",
            )

    def notify_update(self, info: UpdateInfo, manual: bool) -> None:
        mark_checked(self.store)
        if info.version == skipped_version(self.store) and not manual:
            return
        self.pending_update = info
        self.banner_label.setText(
            f"🚀 Доступна новая версия {info.version} (текущая {APP_VERSION}). "
            "Нажмите «Подробнее и установить», чтобы обновиться."
        )
        self.update_banner.setVisible(True)
        self.status_version.setText(f"версия {APP_VERSION} → доступна {info.version}")
        if manual:
            self.show_pending_update()

    def show_pending_update(self) -> None:
        if self.pending_update is None:
            return
        dialog = UpdateDialog(self.pending_update, self.theme, self)
        dialog.exec()
        if dialog.skipped:
            skip_version(self.store, self.pending_update.version)
            self.update_banner.setVisible(False)
            self.statusBar().showMessage("Эта версия пропущена до следующего обновления", 5000)
        elif dialog.snoozed:
            snooze(self.store)
        self.pending_update = None

    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802 - API Qt
        self.store.set("ui/geometry", self.saveGeometry())
        self.store.save()
        super().closeEvent(event)


def load_course(content_path: Path | None = None) -> Course:
    return Course.load(content_path or content_dir())
