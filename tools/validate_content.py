#!/usr/bin/env python3
"""Проверка целостности контента курса.

Запускается в CI перед тестами и сборкой: если контент сломан, релиз не выйдет.
Проверяет:
  * структуру каталогов и обязательные файлы модулей;
  * корректность JSON (module.json, quiz.json, lesson_quizzes.json, practice.json, glossary.json);
  * уникальность id модулей/уроков/задач;
  * существование всех иллюстраций, на которые ссылаются уроки;
  * длину уроков и наличие front matter;
  * количество вопросов/задач и корректность ответов (индексы в диапазоне);
  * корректность regex-шаблонов в практике;
  * итоговую статистику курса.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from devops_academy.content import ContentError, Course  # noqa: E402

IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
REQUIRED_MODULE_FILES = ("module.json", "quiz.json", "lesson_quizzes.json", "practice.json")
MIN_LESSON_CHARS = 1800
MIN_QUESTIONS = 8
MIN_TASKS = 3


def check(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    content_dir = ROOT / "content"
    errors: list[str] = []
    warnings: list[str] = []

    if not content_dir.exists():
        print("ОШИБКА: нет каталога content")
        return 2
    if not (content_dir / "glossary.json").exists():
        warnings.append("нет content/glossary.json — подсказки терминов не будут работать")

    # 1. Структура и JSON
    module_dirs = sorted(p for p in (content_dir / "modules").iterdir() if p.is_dir())
    check(errors, bool(module_dirs), "не найдено ни одного модуля")
    for module_dir in module_dirs:
        for name in REQUIRED_MODULE_FILES:
            check(errors, (module_dir / name).exists(), f"{module_dir.name}: нет {name}")
        lessons = sorted((module_dir / "lessons").glob("*.md"))
        check(errors, bool(lessons), f"{module_dir.name}: нет уроков")
        for path in (
            module_dir / "module.json",
            module_dir / "quiz.json",
            module_dir / "lesson_quizzes.json",
            module_dir / "practice.json",
        ):
            if not path.exists():
                continue
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as error:
                errors.append(f"{path.relative_to(ROOT)}: некорректный JSON — {error}")

    # 2. Загрузка модели
    try:
        course = Course.load(content_dir)
    except ContentError as error:
        print(f"ОШИБКА загрузки курса: {error}")
        return 2

    # 3. Уникальность идентификаторов
    module_ids = [m.module_id for m in course.modules]
    check(errors, len(module_ids) == len(set(module_ids)), "дубли id модулей")
    lesson_keys = [lesson.key for lesson in course.all_lessons()]
    check(errors, len(lesson_keys) == len(set(lesson_keys)), "дубли id уроков")
    task_ids = [f"{m.module_id}/{t.tid}" for m in course.modules if m.practice for t in m.practice.tasks]
    check(errors, len(task_ids) == len(set(task_ids)), "дубли id задач")
    question_ids = [f"{m.module_id}/{q.qid}" for m in course.modules if m.quiz for q in m.quiz.questions]
    check(errors, len(question_ids) == len(set(question_ids)), "дубли id вопросов")

    # 4. Модули: уроки, картинки, объём
    for module in course.modules:
        check(
            errors,
            module.question_count >= MIN_QUESTIONS,
            f"{module.module_id}: вопросов {module.question_count} < {MIN_QUESTIONS}",
        )
        check(
            errors,
            module.task_count >= MIN_TASKS,
            f"{module.module_id}: задач {module.task_count} < {MIN_TASKS}",
        )
        for lesson in module.lessons:
            check(errors, len(lesson.body) >= MIN_LESSON_CHARS,
                  f"{lesson.key}: урок короче {MIN_LESSON_CHARS} символов ({len(lesson.body)})")
            headings = list(re.finditer(
                r"(?im)^#{2,6}\s+[^\n]*(?:проверьте себя|проверить себя|самопровер)[^\n]*$",
                lesson.body,
            ))
            question_counts = []
            for heading in headings:
                rest = lesson.body[heading.end():]
                next_heading = re.search(r"(?m)^#{1,6}\s+", rest)
                section = rest[:next_heading.start()] if next_heading else rest
                question_counts.append(len(re.findall(r"(?m)^\s*\d+\.\s+", section)))
            check(errors, bool(headings), f"{lesson.key}: нет текстового раздела самопроверки")
            check(errors, max(question_counts, default=0) >= 3,
                  f"{lesson.key}: в самопроверке {max(question_counts, default=0)} текстовых вопросов, нужно не меньше 3")
            for target in IMG_RE.findall(lesson.body):
                path = (content_dir / target).resolve()
                check(errors, path.exists(), f"{lesson.key}: нет иллюстрации {target}")
        # 5. Практика: regex-шаблоны компилируются
        if module.practice:
            for task in module.practice.tasks:
                check(errors, bool(task.goal), f"{module.module_id}/{task.tid}: пустая цель")
                check(errors, bool(task.solution), f"{module.module_id}/{task.tid}: нет решения")
                if task.check_type == "manual":
                    check(errors, bool(task.validation_hint),
                          f"{module.module_id}/{task.tid}: manual-задача без validation_hint")
                elif task.check_type == "commands":
                    check(errors, bool(task.commands),
                          f"{module.module_id}/{task.tid}: нет требований check.commands")
                    for command in task.commands:
                        check(errors, bool(command.name),
                              f"{module.module_id}/{task.tid}: пустое имя команды")
                        check(errors, all(isinstance(arg, str) and arg for arg in command.args),
                              f"{module.module_id}/{task.tid}: аргументы команд должны быть непустыми строками")
                else:
                    check(errors, task.check_type in {"regex_all", "regex_any", "equals"},
                          f"{module.module_id}/{task.tid}: неизвестный тип проверки {task.check_type}")
                    check(errors, bool(task.patterns),
                          f"{module.module_id}/{task.tid}: нет шаблонов автопроверки")
                for pattern in task.patterns:
                    try:
                        re.compile(pattern)
                    except re.error as error:
                        errors.append(f"{module.module_id}/{task.tid}: плохой regex '{pattern}': {error}")
        # 6. Тесты: объяснение у каждого вопроса
        if module.quiz:
            check(errors, 0 < module.quiz.pass_score <= 100, f"{module.module_id}: некорректный pass_score")
            for question in module.quiz.questions:
                check(errors, bool(question.explanation),
                      f"{module.module_id}/{question.qid}: нет пояснения")
                if question.qtype in ("single", "multiple"):
                    check(errors, len(question.options) >= 3,
                          f"{module.module_id}/{question.qid}: меньше 3 вариантов")
                elif question.qtype == "text":
                    check(errors, bool(question.answer_text),
                          f"{module.module_id}/{question.qid}: нет допустимых ответов")
        # 7. Короткий тест после каждого урока — ровно три автопроверяемых вопроса.
        for lesson in module.lessons:
            quiz = lesson.quiz
            check(errors, quiz is not None, f"{lesson.key}: нет теста после урока")
            if quiz is None:
                continue
            check(errors, len(quiz.questions) == 3,
                  f"{lesson.key}: в тесте {len(quiz.questions)} вопросов, нужно ровно 3")
            check(errors, 0 < quiz.pass_score <= 100,
                  f"{lesson.key}: некорректный порог теста")
            for question in quiz.questions:
                check(errors, bool(question.explanation),
                      f"{lesson.key}/{question.qid}: нет пояснения")
                if question.qtype in ("single", "multiple"):
                    check(errors, len(question.options) >= 3,
                          f"{lesson.key}/{question.qid}: меньше 3 вариантов")
                elif question.qtype == "text":
                    check(errors, bool(question.answer_text),
                          f"{lesson.key}/{question.qid}: нет допустимых ответов")

    # 8. Итоги
    stats = course.stats()
    print("Контент: ", ", ".join(f"{k}={v}" for k, v in stats.items()))
    for module in course.modules:
        print(f"  {module.order:2d}. {module.title} — уроков {module.lesson_count}, "
              f"вопросов {module.question_count}, задач {module.task_count}")
    for warning in warnings:
        print(f"ПРЕДУПРЕЖДЕНИЕ: {warning}")
    if errors:
        print(f"\nНайдено ошибок: {len(errors)}")
        for error in errors:
            print(f"  ✗ {error}")
        return 1
    print("\nКонтент прошёл проверку ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
