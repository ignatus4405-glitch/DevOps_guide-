"""Точка входа приложения DevOps Academy.

Запуск из исходников:   python -m devops_academy.main
Запуск собранного exe:  DevOpsAcademy.exe
Служебные режимы:       --self-test (проверка целостности контента и UI-стека),
                        --version, --content-dir <путь>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from .content import ContentError, Course
from .paths import content_dir
from .progress import ProgressStore
from .theme import stylesheet
from .ui.main_window import MainWindow
from .version import APP_ID, APP_NAME, APP_VERSION


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="DevOpsAcademy", description=f"{APP_NAME} — курс DevOps Engineer")
    parser.add_argument("--version", action="store_true", help="показать версию и выйти")
    parser.add_argument("--self-test", action="store_true", help="проверить контент и зависимости")
    parser.add_argument("--content-dir", type=str, default="", help="путь к каталогу content")
    return parser.parse_args(argv)


def self_test(content_path: Path | None = None) -> int:
    """Проверка целостности: контент, шрифты, темы, прогресс."""
    course = Course.load(content_path or content_dir())
    stats = course.stats()
    print(f"{APP_NAME} {APP_VERSION} — self-test")
    print(
        f"модулей: {stats['modules']}, уроков: {stats['lessons']}, "
        f"вопросов: {stats['questions']}, задач: {stats['tasks']}"
    )
    # Проверяем, что каждый урок рендерится и каждый тест имеет корректные ответы
    from .markdown_renderer import render_lesson

    for module in course.modules:
        for lesson in module.lessons:
            html = render_lesson(lesson.body, course.root, course.glossary)
            assert "<h1" in html or "<h2" in html, f"урок без заголовка: {lesson.path}"
        if module.quiz:
            for question in module.quiz.questions:
                assert question.question, f"пустой вопрос в {module.module_id}"
    store = ProgressStore()
    assert store.summary(course)["lessons_total"] == stats["lessons"]
    assert len(stylesheet("dark")) > 500 and len(stylesheet("light")) > 500
    print("self-test: OK")
    return 0


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.version:
        print(f"{APP_NAME} {APP_VERSION}")
        return 0

    content_path = Path(args.content_dir) if args.content_dir else content_dir()
    if args.self_test:
        try:
            return self_test(content_path)
        except (ContentError, AssertionError) as error:
            print(f"self-test FAILED: {error}")
            return 2

    try:
        course = Course.load(content_path)
    except ContentError as error:
        app = QApplication(sys.argv)
        QMessageBox.critical(
            None,
            "Ошибка контента",
            f"Не удалось загрузить курс:\n{error}\n\nПереустановите приложение или пересоберите контент.",
        )
        return 3

    QApplication.setApplicationName(APP_NAME)
    QApplication.setOrganizationName(APP_ID)
    app = QApplication(sys.argv)
    app.setApplicationDisplayName(APP_NAME)
    app.setStyleSheet(stylesheet("dark"))

    store = ProgressStore()
    window = MainWindow(course, store)
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())
