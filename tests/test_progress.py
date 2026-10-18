"""Прогресс: сохранение, сводка, отчёт, устойчивость к повреждённым данным."""

from __future__ import annotations

import json

import pytest
from PySide6.QtCore import QSettings

from devops_academy import progress
from devops_academy.progress import ProgressData, ProgressStore


def isolate_user_data(tmp_path, monkeypatch) -> None:
    """Переносит пользовательские данные в tmp-каталог.

    Подменяем и переменные окружения, и саму функцию пути: ``Path.home()`` на Windows
    игнорирует ``HOME`` и читает реальный профиль пользователя, из-за чего тесты
    видели чужой прогресс (падение в CI на Windows).
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(progress, "user_data_dir", lambda: tmp_path)


def make_store(tmp_path, monkeypatch) -> ProgressStore:
    """Store на временных данных, чтобы не трогать реальные настройки."""
    isolate_user_data(tmp_path, monkeypatch)
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.IniFormat)
    return ProgressStore(settings)


def test_lesson_and_task_flags(course, tmp_path, monkeypatch):
    store = make_store(tmp_path, monkeypatch)
    key = course.modules[0].lessons[0].key
    assert not store.is_lesson_done(key)
    store.set_lesson_done(key, True)
    assert store.is_lesson_done(key)
    assert store.toggle_lesson(key) is False
    assert not store.is_lesson_done(key)

    module = next(m for m in course.modules if m.practice)
    task_key = f"{module.module_id}/{module.practice.tasks[0].tid}"
    store.set_task_done(task_key, True)
    assert store.is_task_done(task_key)


def test_quiz_results_keep_best_score(course, tmp_path, monkeypatch):
    store = make_store(tmp_path, monkeypatch)
    module_id = course.modules[0].module_id
    store.save_quiz_result(module_id, 5, 10, False)
    assert store.quiz_percent(module_id) == 50
    assert not store.quiz_passed(module_id)
    store.save_quiz_result(module_id, 9, 10, True)
    assert store.quiz_percent(module_id) == 90
    assert store.quiz_passed(module_id)
    # худший повторный результат не должен портить лучший
    store.save_quiz_result(module_id, 1, 10, False)
    assert store.quiz_percent(module_id) == 90
    assert store.data.quiz_scores[module_id]["attempts"] == 3


def test_summary_counts(course, tmp_path, monkeypatch):
    store = make_store(tmp_path, monkeypatch)
    summary = store.summary(course)
    assert summary["lessons_total"] == len(course.all_lessons())
    assert summary["tasks_total"] == len(course.all_tasks())
    module_quiz_count = sum(1 for module in course.modules if module.quiz and module.quiz.questions)
    lesson_quiz_count = len(course.all_lessons())
    assert summary["modules_total"] == module_quiz_count
    assert summary["lesson_quizzes_total"] == lesson_quiz_count
    assert summary["quizzes_total"] == module_quiz_count + lesson_quiz_count
    assert summary["overall_percent"] == 0
    for lesson in course.all_lessons():
        store.set_lesson_done(lesson.key, True)
    summary = store.summary(course)
    assert summary["lessons_done"] == summary["lessons_total"]
    assert 0 < summary["overall_percent"] <= 100


def test_lesson_quiz_results_are_counted_and_exported(course, tmp_path, monkeypatch):
    store = make_store(tmp_path, monkeypatch)
    lesson = course.modules[0].lessons[0]
    assert lesson.quiz is not None
    store.save_quiz_result(lesson.quiz.module_id, 2, 3, True)

    summary = store.summary(course)
    assert summary["lesson_quizzes_passed"] == 1
    assert summary["quizzes_passed"] == 1
    assert summary["quizzes_total"] == len(course.modules) + len(course.all_lessons())
    report = store.export_markdown(course)
    assert "Тесты уроков" in report
    assert "1/6" in report


def test_export_markdown_report(course, tmp_path, monkeypatch):
    store = make_store(tmp_path, monkeypatch)
    store.set_lesson_done(course.modules[0].lessons[0].key, True)
    report = store.export_markdown(course)
    assert "DevOps Academy" in report
    assert "| Модуль |" in report
    assert report.count("|") > 20  # таблица по модулям


def test_progress_round_trip(course, tmp_path, monkeypatch):
    store = make_store(tmp_path, monkeypatch)
    lesson = course.modules[1].lessons[0]
    store.set_lesson_done(lesson.key, True)
    store.set_task_done(f"{course.modules[0].module_id}/plan", True)
    assert lesson.quiz is not None
    store.save_quiz_result(lesson.quiz.module_id, 2, 3, True)
    store.save()

    same_settings = QSettings(str(tmp_path / "settings.ini"), QSettings.IniFormat)
    restored = ProgressStore(same_settings)
    assert restored.is_lesson_done(lesson.key)
    assert restored.is_task_done(f"{course.modules[0].module_id}/plan")
    assert restored.quiz_passed(lesson.quiz.module_id)
    assert restored.quiz_percent(lesson.quiz.module_id) == 67


def test_corrupted_progress_does_not_crash(tmp_path, monkeypatch):
    isolate_user_data(tmp_path, monkeypatch)
    settings = QSettings(str(tmp_path / "broken.ini"), QSettings.IniFormat)
    settings.setValue("progress/json", "{ это не json")
    store = ProgressStore(settings)
    assert store.data.completed_lessons == set()
    store.set_lesson_done("intro/what-is-devops", True)
    assert store.is_lesson_done("intro/what-is-devops")


def test_progress_data_serialisation():
    data = ProgressData(completed_lessons={"a/b"}, streak_days=["2025-01-31"])
    restored = ProgressData.from_json(json.loads(json.dumps(data.to_json())))
    assert restored.completed_lessons == {"a/b"}
    assert restored.streak_days == ["2025-01-31"]
    assert data.to_json()["schema_version"] == 1


def test_invalid_progress_schema_falls_back_without_crashing(tmp_path, monkeypatch):
    isolate_user_data(tmp_path, monkeypatch)
    settings = QSettings(str(tmp_path / "schema.ini"), QSettings.IniFormat)
    settings.setValue("progress/json", json.dumps({"schema_version": 99, "completed_lessons": []}))
    store = ProgressStore(settings)
    assert store.data.completed_lessons == set()
    assert "не удалось прочитать" in store.recovery_warning.lower()


def test_corrupt_settings_recover_from_valid_mirror(tmp_path, monkeypatch):
    isolate_user_data(tmp_path, monkeypatch)
    settings = QSettings(str(tmp_path / "recover.ini"), QSettings.IniFormat)
    settings.setValue("progress/json", "not-json")
    (tmp_path / "progress.json").write_text(
        json.dumps({"completed_lessons": ["intro/lesson-1"], "completed_tasks": [], "quiz_scores": {}}),
        encoding="utf-8",
    )
    store = ProgressStore(settings)
    assert store.data.completed_lessons == {"intro/lesson-1"}
    assert "резервной копии" in store.recovery_warning.lower()


def test_invalid_progress_field_types_are_rejected():
    with pytest.raises(ValueError, match="списком строк"):
        ProgressData.from_json({"completed_lessons": "not-a-list"})
    with pytest.raises(ValueError, match="quiz_scores"):
        ProgressData.from_json({"quiz_scores": ["not-an-object"]})


def test_streak_data_is_bounded_on_load():
    days = [f"2026-01-{day:02d}" for day in range(1, 101)]
    restored = ProgressData.from_json({"streak_days": days})
    assert len(restored.streak_days) == 60
    assert restored.streak_days == days[-60:]


def test_summary_ignores_stale_keys(course, tmp_path, monkeypatch):
    store = make_store(tmp_path, monkeypatch)
    store.data.completed_lessons.add("removed-module/removed-lesson")
    store.data.completed_tasks.add("removed-module/removed-task")
    store.data.quiz_scores["removed-module"] = {
        "correct": 1,
        "total": 1,
        "percent": 100,
        "passed": True,
        "attempts": 1,
        "updated": "2026-01-01T00:00:00+00:00",
    }
    summary = store.summary(course)
    assert summary["lessons_done"] == 0
    assert summary["tasks_done"] == 0
    assert summary["quizzes_passed"] == 0
    assert summary["overall_percent"] == 0


def test_progress_mirror_is_atomically_saved(tmp_path, monkeypatch):
    store = make_store(tmp_path, monkeypatch)
    store.set_lesson_done("intro/lesson-1", True)
    mirror = tmp_path / "progress.json"
    payload = json.loads(mirror.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["completed_lessons"] == ["intro/lesson-1"]
    assert not list(tmp_path.glob(".progress.json.*.tmp"))
