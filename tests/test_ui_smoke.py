"""GUI-тесты в offscreen-режиме: окно, уроки, тест, практика, экзамен."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSettings

from devops_academy.progress import ProgressStore
from devops_academy.ui.main_window import MainWindow, build_exam_module


@pytest.fixture()
def window(course, qapp, tmp_path):
    store = ProgressStore(QSettings(str(tmp_path / "ui.ini"), QSettings.IniFormat))
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


def test_progress_bar_updates(course, window):
    window.store.save_quiz_result(course.modules[0].module_id, 10, 10, True)
    window.dashboard.refresh()
    assert window.dashboard.progress.value() > 0
