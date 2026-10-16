"""Прогресс: сохранение, сводка, отчёт, устойчивость к повреждённым данным."""

from __future__ import annotations

import json

from PySide6.QtCore import QSettings

from devops_academy.progress import ProgressData, ProgressStore


def isolate_user_data(tmp_path, monkeypatch) -> None:
    """Переносит пользовательские данные в tmp: на Windows это LOCALAPPDATA/APPDATA,
    на Linux/macOS — HOME. Без подмены всех переменных тест может прочитать
    реальный файл прогресса и упасть (так и случилось в CI на Windows)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))


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
    assert summary["modules_total"] == len(course.modules)
    assert summary["overall_percent"] == 0
    for lesson in course.all_lessons():
        store.set_lesson_done(lesson.key, True)
    summary = store.summary(course)
    assert summary["lessons_done"] == summary["lessons_total"]
    assert 0 < summary["overall_percent"] <= 100


def test_export_markdown_report(course, tmp_path, monkeypatch):
    store = make_store(tmp_path, monkeypatch)
    store.set_lesson_done(course.modules[0].lessons[0].key, True)
    report = store.export_markdown(course)
    assert "DevOps Academy" in report
    assert "| Модуль |" in report
    assert report.count("|") > 20  # таблица по модулям


def test_progress_round_trip(course, tmp_path, monkeypatch):
    store = make_store(tmp_path, monkeypatch)
    store.set_lesson_done(course.modules[1].lessons[0].key, True)
    store.set_task_done(f"{course.modules[0].module_id}/plan", True)
    store.save()

    same_settings = QSettings(str(tmp_path / "settings.ini"), QSettings.IniFormat)
    restored = ProgressStore(same_settings)
    assert restored.is_lesson_done(course.modules[1].lessons[0].key)
    assert restored.is_task_done(f"{course.modules[0].module_id}/plan")


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
