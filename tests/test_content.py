"""Проверки модели контента: структура, ссылки, качество материалов."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"


def test_course_loads(course):
    stats = course.stats()
    assert stats["modules"] >= 12, "в курсе должно быть не меньше 12 модулей"
    assert stats["lessons"] >= 26
    assert stats["questions"] >= 120
    assert stats["tasks"] >= 48
    assert stats["minutes"] >= 1200, "курс должен быть объёмным (>= 20 часов)"


def test_modules_have_required_files():
    for module_dir in sorted((CONTENT / "modules").iterdir()):
        if not module_dir.is_dir():
            continue
        for name in ("module.json", "quiz.json", "practice.json"):
            assert (module_dir / name).exists(), f"{module_dir.name}: нет {name}"


def test_module_metadata_is_complete(course):
    for module in course.modules:
        assert module.title
        assert module.summary
        assert module.objectives, f"{module.module_id}: нет целей обучения"
        assert module.tags, f"{module.module_id}: нет тегов"
        assert module.estimated_minutes > 0


def test_lesson_images_exist(course):
    pattern = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
    for lesson in course.all_lessons():
        for target in pattern.findall(lesson.body):
            if target.startswith(("http://", "https://")):
                continue
            assert (CONTENT / target).exists(), f"{lesson.key}: нет файла {target}"


def test_lessons_have_front_matter_and_body(course):
    for lesson in course.all_lessons():
        assert lesson.raw.startswith("---"), f"{lesson.key}: нет front matter"
        assert len(lesson.body) > 1800, f"{lesson.key}: урок слишком короткий"
        assert lesson.minutes > 0


def test_quiz_answers_are_valid(course):
    for module in course.modules:
        assert module.quiz is not None
        assert 0 < module.quiz.pass_score <= 100
        for question in module.quiz.questions:
            assert question.explanation, f"{module.module_id}/{question.qid}: нет пояснения"
            if question.qtype in ("single", "multiple"):
                assert len(question.options) >= 3
                assert question.answer, "нет правильных вариантов"
                assert all(0 <= index < len(question.options) for index in question.answer)
            else:
                assert question.answer_text, "нет допустимых текстовых ответов"


def test_single_choice_questions_have_exactly_one_answer(course):
    for module in course.modules:
        for question in module.quiz.questions:
            if question.qtype == "single":
                assert len(question.answer) == 1, f"{module.module_id}/{question.qid}: должен быть один ответ"


def test_practice_patterns_compile(course):
    for module in course.modules:
        for task in module.practice.tasks:
            assert task.goal and task.solution
            if task.check_type != "manual":
                assert task.patterns, f"{module.module_id}/{task.tid}: нет шаблонов проверки"
            for pattern in task.patterns:
                re.compile(pattern)  # бросит re.error, если шаблон плохой


def test_solution_matches_own_patterns(course):
    """Эталонное решение обязано проходить собственную проверку задачи."""
    from devops_academy.ui.practice_widget import TaskChecker

    for module in course.modules:
        for task in module.practice.tasks:
            if task.check_type == "manual":
                continue
            ok, message = TaskChecker.check(task, task.solution)
            assert ok, f"{module.module_id}/{task.tid}: решение не проходит проверку ({message})"


def test_glossary_terms_are_complete(course):
    assert len(course.glossary) >= 60, "глоссарий должен содержать 60+ терминов"
    for term, entry in course.glossary.items():
        assert entry.get("definition"), f"{term}: нет определения"
        assert len(entry["definition"]) > 30, f"{term}: определение слишком короткое"


def test_glossary_json_is_valid():
    data = json.loads((CONTENT / "glossary.json").read_text(encoding="utf-8"))
    assert data["terms"]
    for item in data["terms"]:
        assert item["term"] and item["definition"]


def test_minimum_questions_and_tasks_per_module(course):
    for module in course.modules:
        assert module.question_count >= 8, f"{module.module_id}: мало вопросов"
        assert module.task_count >= 3, f"{module.module_id}: мало задач"


def test_content_index_is_fresh(course):
    """content_index.json должен соответствовать текущему контенту."""
    index_file = CONTENT / "content_index.json"
    assert index_file.exists(), "нет content/content_index.json (запустите tools/generate_version.py)"
    hashes = json.loads(index_file.read_text(encoding="utf-8"))["hashes"]
    for relative, digest in list(hashes.items())[:20]:
        path = CONTENT / relative
        assert path.exists(), f"в индексе есть несуществующий файл {relative}"
        import hashlib

        # Хеш считается от содержимого с LF — проверка не зависит от переводов строк.
        data = path.read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(data).hexdigest()[:16] == digest, f"{relative}: хеш не совпадает"
