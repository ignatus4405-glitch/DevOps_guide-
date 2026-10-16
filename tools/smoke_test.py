#!/usr/bin/env python3
"""Дымовой тест собранного приложения.

Запускается в CI на собранном артефакте (--frozen) или на исходниках.
Проверяет: контент загружается, GUI создаётся, урок рендерится, тест и
практика открываются, счётчики прогресса работают.

Запуск: QT_QPA_PLATFORM=offscreen python tools/smoke_test.py
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Дымовой тест DevOps Academy")
    parser.add_argument("--content-dir", default="", help="путь к каталогу content")
    args = parser.parse_args()

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("XDG_RUNTIME_DIR", "/tmp")

    from PySide6.QtWidgets import QApplication

    from devops_academy.content import Course
    from devops_academy.paths import content_dir
    from devops_academy.progress import ProgressStore
    from devops_academy.ui.main_window import MainWindow, build_exam_module
    from devops_academy.version import APP_VERSION

    content_path = Path(args.content_dir) if args.content_dir else content_dir()
    QApplication([])  # обязателен для создания виджетов
    course = Course.load(content_path)
    stats = course.stats()
    print(f"версия {APP_VERSION}: модулей {stats['modules']}, уроков {stats['lessons']}, "
          f"вопросов {stats['questions']}, задач {stats['tasks']}")

    store = ProgressStore()
    window = MainWindow(course, store)
    window.show()

    # 1. Открыть первый урок каждого модуля
    for module in course.modules:
        window.open_module(module.module_id)
        assert window.lesson_view.lesson is not None, f"урок не открылся: {module.module_id}"
        html = window.lesson_view.browser.toHtml()
        assert len(html) > 500, f"пустой HTML урока: {module.module_id}"

    # 2. Тест первого модуля: пройти и проверить результат
    first = course.modules[0]
    window.open_module(first.module_id, mode="quiz")
    quiz = window.quiz_view
    assert quiz.module is not None and quiz.question_widgets, "тест не загрузился"
    for widget in quiz.question_widgets:
        question = widget.question
        if question.qtype == "text":
            widget.controls[0].setText(question.answer_text[0] if question.answer_text else "нет")
        else:
            for index, control in enumerate(widget.controls):
                control.setChecked(index in question.answer)
    quiz.check()
    assert "%" in window.quiz_view.result_label.text(), "нет результата теста"

    # 3. Практика: проверка верного и неверного ответа
    module_with_tasks = next(m for m in course.modules if m.practice)
    window.open_module(module_with_tasks.module_id, mode="practice")
    task = window.practice_view.task
    assert task is not None, "задача не загрузилась"
    from devops_academy.ui.practice_widget import TaskChecker

    ok, _ = TaskChecker.check(task, task.solution)
    assert ok, f"эталонное решение не проходит проверку: {task.tid}"
    bad, _ = TaskChecker.check(task, "заведомо неправильный ответ")
    assert not bad or task.check_type == "manual", "неверный ответ принят как верный"

    # 4. Экзамен собирается
    exam = build_exam_module(course, 10)
    assert len(exam.quiz.questions) == 10, "экзамен собран неверно"

    # 5. Прогресс сохраняется и читается
    key = course.modules[0].lessons[0].key
    store.set_lesson_done(key, True)
    assert store.is_lesson_done(key), "прогресс не сохранён"
    summary = store.summary(course)
    assert summary["lessons_total"] == stats["lessons"], "неверный подсчёт уроков"
    store.set_lesson_done(key, False)

    window.close()
    print("smoke-test: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
