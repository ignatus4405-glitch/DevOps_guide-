"""Хранение прогресса пользователя.

Прогресс лежит в QSettings (реестр Windows / plist / ini) плюс дублируется в
JSON-файл в user_data_dir(), чтобы его можно было переносить между версиями и
пересобирать статистику вне GUI.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from PySide6.QtCore import QSettings

from .paths import user_data_dir

ORG = "DevOpsAcademy"
APP = "DevOpsAcademy"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class ProgressData:
    """Срез прогресса, пригодный для сериализации и для тестов."""

    completed_lessons: set[str] = field(default_factory=set)
    quiz_scores: dict[str, dict] = field(default_factory=dict)
    completed_tasks: set[str] = field(default_factory=set)
    last_lesson: str = ""
    streak_days: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "completed_lessons": sorted(self.completed_lessons),
            "quiz_scores": self.quiz_scores,
            "completed_tasks": sorted(self.completed_tasks),
            "last_lesson": self.last_lesson,
            "streak_days": self.streak_days[-60:],
        }

    @classmethod
    def from_json(cls, data: dict) -> ProgressData:
        return cls(
            completed_lessons=set(data.get("completed_lessons", [])),
            quiz_scores=dict(data.get("quiz_scores", {})),
            completed_tasks=set(data.get("completed_tasks", [])),
            last_lesson=str(data.get("last_lesson", "")),
            streak_days=list(data.get("streak_days", [])),
        )


class ProgressStore:
    """Фасад над QSettings + JSON-зеркалом."""

    def __init__(self, settings: QSettings | None = None) -> None:
        self.settings = settings or QSettings(ORG, APP)
        self.data = ProgressData.from_json(self._load_raw())

    # --- низкоуровневое -------------------------------------------------
    def _load_raw(self) -> dict:
        raw = self.settings.value("progress/json", "")
        if raw:
            try:
                return json.loads(raw)
            except (TypeError, ValueError):
                pass
        mirror = user_data_dir() / "progress.json"
        if mirror.exists():
            try:
                return json.loads(mirror.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return {}
        return {}

    def save(self) -> None:
        payload = json.dumps(self.data.to_json(), ensure_ascii=False)
        self.settings.setValue("progress/json", payload)
        self.settings.sync()
        try:
            (user_data_dir() / "progress.json").write_text(
                json.dumps(self.data.to_json(), ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError:
            pass

    def _touch_day(self) -> None:
        today = datetime.now(timezone.utc).date().isoformat()
        if today not in self.data.streak_days:
            self.data.streak_days.append(today)

    # --- уроки ----------------------------------------------------------
    def is_lesson_done(self, key: str) -> bool:
        return key in self.data.completed_lessons

    def set_lesson_done(self, key: str, done: bool = True) -> None:
        if done:
            self.data.completed_lessons.add(key)
            self._touch_day()
        else:
            self.data.completed_lessons.discard(key)
        self.save()

    def toggle_lesson(self, key: str) -> bool:
        new_state = not self.is_lesson_done(key)
        self.set_lesson_done(key, new_state)
        return new_state

    def set_last_lesson(self, key: str) -> None:
        self.data.last_lesson = key
        self.save()

    # --- практика -------------------------------------------------------
    def is_task_done(self, task_key: str) -> bool:
        return task_key in self.data.completed_tasks

    def set_task_done(self, task_key: str, done: bool = True) -> None:
        if done:
            self.data.completed_tasks.add(task_key)
            self._touch_day()
        else:
            self.data.completed_tasks.discard(task_key)
        self.save()

    # --- тесты ----------------------------------------------------------
    def save_quiz_result(self, module_id: str, correct: int, total: int, passed: bool) -> None:
        best = self.data.quiz_scores.get(module_id, {})
        percent = round(correct / total * 100) if total else 0
        if percent >= int(best.get("percent", -1)):
            self.data.quiz_scores[module_id] = {
                "correct": correct,
                "total": total,
                "percent": percent,
                "passed": passed,
                "attempts": int(best.get("attempts", 0)) + 1,
                "updated": _now(),
            }
        else:
            best["attempts"] = int(best.get("attempts", 0)) + 1
            best["updated"] = _now()
            self.data.quiz_scores[module_id] = best
        self._touch_day()
        self.save()

    def quiz_percent(self, module_id: str) -> int:
        return int(self.data.quiz_scores.get(module_id, {}).get("percent", 0))

    def quiz_passed(self, module_id: str) -> bool:
        return bool(self.data.quiz_scores.get(module_id, {}).get("passed", False))

    # --- сводка ---------------------------------------------------------
    def reset(self) -> None:
        self.data = ProgressData()
        self.save()

    def summary(self, course) -> dict:
        lessons_total = len(course.all_lessons())
        tasks_total = len(course.all_tasks())
        modules_total = len(course.modules)
        lessons_done = len(self.data.completed_lessons)
        tasks_done = len(self.data.completed_tasks)
        quizzes_passed = sum(1 for m in course.modules if self.quiz_passed(m.module_id))
        overall = 0
        if lessons_total or tasks_total or modules_total:
            overall = round(
                (
                    (lessons_done / lessons_total if lessons_total else 0)
                    + (tasks_done / tasks_total if tasks_total else 0)
                    + (quizzes_passed / modules_total if modules_total else 0)
                )
                / 3
                * 100
            )
        return {
            "lessons_done": min(lessons_done, lessons_total),
            "lessons_total": lessons_total,
            "tasks_done": min(tasks_done, tasks_total),
            "tasks_total": tasks_total,
            "quizzes_passed": quizzes_passed,
            "modules_total": modules_total,
            "overall_percent": overall,
            "days_active": len(self.data.streak_days),
        }

    def export_markdown(self, course) -> str:
        """Выгрузка отчёта «что пройдено» — удобно приложить к резюме."""
        summary = self.summary(course)
        lines = [
            "# DevOps Academy — отчёт о прохождении курса",
            "",
            f"- Общий прогресс: **{summary['overall_percent']}%**",
            f"- Уроков пройдено: {summary['lessons_done']} из {summary['lessons_total']}",
            f"- Практических задач решено: {summary['tasks_done']} из {summary['tasks_total']}",
            f"- Тестов сдано: {summary['quizzes_passed']} из {summary['modules_total']}",
            f"- Дней занятий: {summary['days_active']}",
            "",
            "## Модули",
            "",
            "| Модуль | Уроки | Практика | Тест |",
            "| --- | --- | --- | --- |",
        ]
        for module in course.modules:
            lessons_done = sum(
                1 for lesson in module.lessons if self.is_lesson_done(lesson.key)
            )
            tasks_done = 0
            if module.practice:
                tasks_done = sum(
                    1
                    for task in module.practice.tasks
                    if self.is_task_done(f"{module.module_id}/{task.tid}")
                )
            percent = self.quiz_percent(module.module_id)
            lines.append(
                f"| {module.title} | {lessons_done}/{module.lesson_count} | "
                f"{tasks_done}/{module.task_count} | {percent}% |"
            )
        return "\n".join(lines) + "\n"

    # --- настройки приложения -------------------------------------------
    def get(self, key: str, default=None):
        return self.settings.value(key, default)

    def set(self, key: str, value) -> None:
        self.settings.setValue(key, value)
        self.settings.sync()
