"""GUI-тесты в offscreen-режиме: окно, уроки, тест, практика, экзамен."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QDialog

from devops_academy.progress import ProgressStore
from devops_academy.ui.main_window import MainWindow, build_exam_module
from devops_academy.ui.quiz_widget import QuizWidget


def _wait_until(qtest, condition, timeout_ms: int = 1000) -> bool:
    """Ждёт асинхронный Qt-переход, регулярно прокачивая event loop."""
    for _ in range(timeout_ms // 10):
        if condition():
            return True
        qtest.qWait(10)
    return condition()


@pytest.fixture()
def window(course, qapp, tmp_path):
    store = ProgressStore(QSettings(str(tmp_path / "ui.ini"), QSettings.IniFormat))
    store.set("updates/auto_check", "false")
    win = MainWindow(course, store)
    yield win
    win.close()


def test_window_builds(course, window):
    assert window.sidebar.count() == len(course.modules) + 1  # +1 дашборд
    assert window.stack.count() >= 4


def test_open_every_module_lesson(course, window):
    for module in course.modules:
        window.open_module(module.module_id)
        assert window.lesson_view.lesson is not None
        assert len(window.lesson_view.browser.toPlainText()) > 500


def test_lesson_navigation_and_completion(course, window):
    module = course.modules[0]
    window.open_module(module.module_id)
    window.navigate_lesson(1)
    assert window.current_lesson_index == 1
    lesson = module.lessons[1]
    window.lesson_view.done_box.setChecked(True)
    assert window.store.is_lesson_done(lesson.key)
    window.lesson_view.done_box.setChecked(False)
    assert not window.store.is_lesson_done(lesson.key)


def test_optional_lesson_quiz_saves_result_without_blocking_next_lesson(course, window, qapp):
    module = course.modules[0]
    window.open_module(module.module_id)
    lesson = module.lessons[0]
    assert lesson.quiz is not None
    assert not window.lesson_view.quiz_button.isHidden()
    assert window.lesson_view.next_button.isEnabled()

    result = {}

    def finish_quiz():
        dialogs = [
            widget
            for widget in qapp.topLevelWidgets()
            if isinstance(widget, QDialog)
            and widget.isVisible()
            and widget.windowTitle().startswith("Тест после урока:")
        ]
        if not dialogs:
            result["error"] = "lesson quiz dialog was not opened"
            return
        dialog = dialogs[-1]
        quiz_view = dialog.findChild(QuizWidget)
        if quiz_view is None:
            result["error"] = "lesson quiz widget was not found"
            dialog.reject()
            return
        result["question_count"] = len(quiz_view.question_widgets)
        for question_widget in quiz_view.question_widgets:
            question = question_widget.question
            if question.qtype == "text":
                question_widget.controls[0].setText(question.answer_text[0])
            else:
                for index, control in enumerate(question_widget.controls):
                    control.setChecked(index in question.answer)
        quiz_view.check()
        dialog.accept()

    QTimer.singleShot(0, finish_quiz)
    window.lesson_view.quiz_button.click()
    assert result.get("error") is None, result.get("error")
    assert result["question_count"] == 3

    assert window.store.quiz_percent(lesson.quiz.module_id) == 100
    assert window.store.quiz_passed(lesson.quiz.module_id)
    assert "100%" in window.lesson_view.quiz_button.text()
    assert window.lesson_view.next_button.isEnabled()
    window.navigate_lesson(1)
    assert window.current_lesson_index == 1


def test_quiz_flow_saves_result(course, window):
    module = course.modules[0]
    window.open_module(module.module_id, mode="quiz")
    quiz = window.quiz_view
    assert len(quiz.question_widgets) == module.question_count
    for widget in quiz.question_widgets:
        question = widget.question
        if question.qtype == "text":
            widget.controls[0].setText(question.answer_text[0])
        else:
            for index, control in enumerate(widget.controls):
                control.setChecked(index in question.answer)
    quiz.check()
    assert window.store.quiz_percent(module.module_id) == 100
    assert window.store.quiz_passed(module.module_id)
    assert "100%" in quiz.result_label.text()


def test_wrong_answers_are_detected(course, window):
    module = course.modules[1]
    window.open_module(module.module_id, mode="quiz")
    quiz = window.quiz_view
    for widget in quiz.question_widgets:
        if widget.question.qtype == "text":
            widget.controls[0].setText("заведомо неверно")
        else:
            wrong = [i for i in range(len(widget.controls)) if i not in widget.question.answer]
            widget.controls[wrong[0]].setChecked(True)
    quiz.check()
    assert window.store.quiz_percent(module.module_id) < 100


def test_practice_shows_tasks_and_checks_solution(course, window):
    module = next(m for m in course.modules if m.practice)
    window.open_module(module.module_id, mode="practice")
    view = window.practice_view
    assert view.task_list.count() == module.task_count
    task = view.task
    view.answer.setPlainText(task.solution)
    view.check_button.click()
    assert "✅" in view.feedback.text()
    assert window.store.is_task_done(f"{module.module_id}/{task.tid}")


def test_dashboard_reflects_progress(course, window):
    summary_before = window.store.summary(course)["overall_percent"]
    window.store.set_lesson_done(course.modules[0].lessons[0].key, True)
    window.dashboard.refresh()
    assert window.store.summary(course)["overall_percent"] >= summary_before
    assert window.dashboard.progress.value() >= 0


def test_exam_module_built_from_all_modules(course):
    exam = build_exam_module(course, 15)
    assert exam.question_count == 15
    ids = {q.qid for q in exam.quiz.questions}
    assert ids  # вопросы собраны


def test_glossary_dialog_lists_terms(course, qapp):
    from devops_academy.ui.glossary_dialog import GlossaryDialog

    dialog = GlossaryDialog(course.glossary)
    assert dialog.list.count() == len(course.glossary)
    dialog.search.setText("kubernetes")
    assert dialog.list.count() >= 1
    dialog.close()


def test_theme_toggle_persists(window):
    window.apply_theme("light")
    assert window.store.get("ui/theme") == "light"
    window.apply_theme("dark")
    assert window.store.get("ui/theme") == "dark"


def test_lesson_repaints_tables_on_theme_switch(course, window):
    """При смене темы таблицы перерисовываются: цвета заданы инлайново в HTML."""
    from devops_academy.theme import palette

    module = next(m for m in course.modules if m.module_id == "intro")
    window.open_module(module.module_id)
    window.navigate_lesson(2)  # урок «Карта инструментов» — с таблицами

    window.apply_theme("dark")
    dark_html = window.lesson_view.browser.toHtml()
    window.apply_theme("light")
    light_html = window.lesson_view.browser.toHtml()

    assert palette("dark")["border"] in dark_html
    assert palette("light")["border"] in light_html
    assert palette("light")["border"] != palette("dark")["border"]
    # Содержимое урока не потерялось и таблица на месте
    assert "Управление кодом" in window.lesson_view.browser.toPlainText()


def test_every_lesson_table_is_styled(course):
    """Во всех уроках курса таблицы получают границы (иначе Qt рисует их без сетки)."""
    import re

    from devops_academy.markdown_renderer import render_lesson

    checked_tables = 0
    for module in course.modules:
        for lesson in module.lessons:
            html = render_lesson(lesson.body, course.root, course.glossary, "dark")
            tables = re.findall(r"<table(?=[\s>])[^>]*>", html)
            if not tables:
                continue
            checked_tables += len(tables)
            for tag in tables:
                assert "border-collapse: collapse" in tag and "border: 1px solid" in tag, tag
            for tag in re.findall(r"<t[hd](?=[\s>])[^>]*>", html):
                assert "border: 1px solid" in tag, f"ячейка без границы: {tag}"
    assert checked_tables >= 20, f"ожидались таблицы в уроках, найдено {checked_tables}"


def test_progress_bar_updates(course, window):
    window.store.save_quiz_result(course.modules[0].module_id, 10, 10, True)
    window.dashboard.refresh()
    assert window.dashboard.progress.value() > 0


def test_next_button_finishes_module_and_opens_next_topic(course, window):
    """На последнем уроке темы «Следующий» ведёт в следующий модуль.

    Раньше кнопка там просто блокировалась, и курс обрывался на каждой теме.
    """
    first, second = course.modules[0], course.modules[1]
    window.open_module(first.module_id)
    window.open_lesson(first, first.lesson_count - 1)

    assert window.lesson_view.next_button.isEnabled()
    window.lesson_view.next_button.click()

    assert window.current_module.module_id == second.module_id
    assert window.current_lesson_index == 0
    assert window.sidebar.currentRow() == course.modules.index(second) + 1


def test_prev_button_returns_to_previous_topic_end(course, window):
    first, second = course.modules[0], course.modules[1]
    window.open_module(second.module_id)

    assert window.lesson_view.prev_button.isEnabled()
    window.lesson_view.prev_button.click()

    assert window.current_module.module_id == first.module_id
    assert window.current_lesson_index == first.lesson_count - 1
    assert window.sidebar.currentRow() == course.modules.index(first) + 1


def test_first_lesson_has_no_previous_step(course, window):
    window.open_module(course.modules[0].module_id)
    assert not window.lesson_view.prev_button.isEnabled()

    window.navigate_lesson(-1)
    assert window.current_module.module_id == course.modules[0].module_id
    assert window.current_lesson_index == 0


def test_last_lesson_of_course_offers_final_exam(course, window):
    last_module = course.modules[-1]
    window.open_module(last_module.module_id)
    window.open_lesson(last_module, last_module.lesson_count - 1)

    assert window.lesson_view.next_button.isEnabled()
    assert "экзамен" in window.lesson_view.next_button.text().lower()

    window.lesson_view.next_button.click()
    assert window.current_mode == "exam"
    assert window.stack.currentWidget() is window.quiz_view


def test_every_module_boundary_is_crossable(course, window):
    """Сквозной проход по всем урокам: «Следующий» не блокируется нигде."""
    window.open_module(course.modules[0].module_id)
    visited = []
    while window.current_mode == "lesson":
        visited.append((window.current_module.module_id, window.current_lesson_index))
        assert window.lesson_view.next_button.isEnabled(), visited[-1]
        window.lesson_view.next_button.click()
    assert len(visited) == sum(module.lesson_count for module in course.modules)
    assert len({module_id for module_id, _ in visited}) == len(course.modules)
    assert window.current_mode == "exam"


def test_found_update_prompts_automatically_and_keeps_banner_action(window, monkeypatch):
    """Автопроверка открывает диалог, а после «Позже» диалог доступен из баннера."""
    import devops_academy.ui.main_window as main_window
    from devops_academy.updater import UpdateInfo

    info = UpdateInfo(
        version="0.6.0",
        tag="v0.6.0",
        title="DevOps Academy 0.6.0",
        notes="Улучшения",
        published_at="2026-10-17T10:00:00Z",
        html_url="https://github.com/example/repo/releases/tag/v0.6.0",
    )
    prompted = []

    class LaterDialog:
        snoozed = True
        skipped = False
        installer_started = False

        def __init__(self, update, theme, parent):
            prompted.append(update)

        def exec(self):
            return 0

    monkeypatch.setattr(main_window, "UpdateDialog", LaterDialog)

    window.notify_update(info, manual=False)

    assert prompted == [info]
    assert window.pending_update is info
    assert not window.update_banner.isHidden()
    assert window.store.get("updates/last_check")

    # После «Позже» UpdateInfo сохраняется и диалог можно открыть повторно.
    window.update_details_button.click()
    assert prompted == [info, info]
    assert window.pending_update is info
    assert not window.update_banner.isHidden()


def test_closing_update_dialog_keeps_banner_reopenable(window, monkeypatch):
    import devops_academy.ui.main_window as main_window
    from devops_academy.updater import UpdateInfo

    info = UpdateInfo(
        version="0.7.0",
        tag="v0.7.0",
        title="DevOps Academy 0.7.0",
        notes="",
        published_at="",
        html_url="https://github.com/example/repo/releases/tag/v0.7.0",
    )
    opened = []

    class ClosedDialog:
        snoozed = False
        skipped = False
        installer_started = False

        def __init__(self, update, theme, parent):
            opened.append(update)

        def exec(self):
            return 0  # пользователь закрыл окно крестиком

    monkeypatch.setattr(main_window, "UpdateDialog", ClosedDialog)
    window.notify_update(info, manual=False)
    assert opened == [info]
    assert window.pending_update is info
    assert not window.update_banner.isHidden()

    window.update_details_button.click()
    assert opened == [info, info]
    assert window.pending_update is info


def test_main_window_waits_for_update_checker_before_closing(window, monkeypatch, qapp):
    from PySide6.QtCore import QThread, Signal
    from PySide6.QtTest import QTest

    import devops_academy.ui.main_window as main_window

    class BlockingChecker(QThread):
        found = Signal(object)
        checked = Signal(object)
        failed = Signal(str)

        def __init__(self, current_version, parent=None):
            super().__init__(parent)

        def run(self):
            while not self.isInterruptionRequested():
                self.msleep(5)

    monkeypatch.setattr(main_window, "UpdateChecker", BlockingChecker)
    window.show()
    window.check_updates_silent(manual=True)
    checker = window.checker
    assert checker is not None
    QTest.qWait(20)
    assert checker.isRunning()

    window.close()
    assert window._close_after_checker
    assert _wait_until(QTest, lambda: not checker.isRunning()), "update checker did not stop"
    assert _wait_until(QTest, lambda: not window.isVisible()), "main window stayed visible after close"


def test_stale_update_checker_finish_cannot_close_window_for_new_checker(window):
    stale_checker = object()
    active_checker = object()
    window.checker = active_checker
    window._close_after_checker = True

    window._update_checker_finished(stale_checker)

    assert window._close_after_checker
    assert window.checker is active_checker
    window.checker = None
    window._close_after_checker = False


def test_update_dialog_waits_for_download_worker_on_close(monkeypatch, qapp):
    from PySide6.QtCore import QThread, Signal
    from PySide6.QtTest import QTest

    import devops_academy.ui.update_dialog as update_dialog
    from devops_academy.updater import ReleaseAsset, UpdateInfo

    class BlockingDownloadWorker(QThread):
        progress = Signal(int)
        finished_file = Signal(str)
        failed = Signal(str)

        def __init__(self, info, parent=None):
            super().__init__(parent)

        def run(self):
            while not self.isInterruptionRequested():
                self.msleep(5)

    monkeypatch.setattr(update_dialog, "DownloadWorker", BlockingDownloadWorker)
    info = UpdateInfo(
        version="0.7.0",
        tag="v0.7.0",
        title="DevOps Academy 0.7.0",
        notes="",
        published_at="",
        html_url="https://example/releases/v0.7.0",
        assets=[ReleaseAsset("DevOpsAcademy-0.7.0-linux-x64.tar.gz", "https://example/course.tar.gz")],
    )
    monkeypatch.setattr(info, "installer_asset", lambda: None)
    monkeypatch.setattr(info, "archive_asset", lambda: info.assets[0])
    dialog = update_dialog.UpdateDialog(info)
    assert dialog.install_button.isEnabled()
    dialog.show()
    dialog.install_button.click()
    worker = dialog.worker
    assert worker is not None
    QTest.qWait(20)
    assert worker.isRunning()

    dialog.close()
    assert dialog._close_when_worker_stops
    assert _wait_until(QTest, lambda: not worker.isRunning()), "download worker did not stop"
    assert _wait_until(QTest, lambda: not dialog.isVisible()), "update dialog stayed visible after close"
