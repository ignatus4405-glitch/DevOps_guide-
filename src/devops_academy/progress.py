"""Хранение прогресса пользователя.

Прогресс лежит в QSettings (реестр Windows / plist / ini) плюс дублируется в
JSON-файл в user_data_dir(), чтобы его можно было переносить между версиями и
пересобирать статистику вне GUI.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSettings

from .paths import user_data_dir

ORG = "DevOpsAcademy"
APP = "DevOpsAcademy"
PROGRESS_SCHEMA_VERSION = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class ProgressData:
    """Версионированный снимок прогресса с проверкой схемы при чтении."""

    completed_lessons: set[str] = field(default_factory=set)
    quiz_scores: dict[str, dict] = field(default_factory=dict)
    completed_tasks: set[str] = field(default_factory=set)
    last_lesson: str = ""
    streak_days: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "schema_version": PROGRESS_SCHEMA_VERSION,
            "completed_lessons": sorted(self.completed_lessons),
            "quiz_scores": self.quiz_scores,
            "completed_tasks": sorted(self.completed_tasks),
            "last_lesson": self.last_lesson,
            "streak_days": self.streak_days[-60:],
        }

    @classmethod
    def from_json(cls, data: Any) -> ProgressData:
        if not isinstance(data, dict):
            raise ValueError("корень файла прогресса должен быть JSON-объектом")

        version = data.get("schema_version", 0)  # schema 0 — старый формат без version
        if isinstance(version, bool) or not isinstance(version, int) or not 0 <= version <= PROGRESS_SCHEMA_VERSION:
            raise ValueError(f"неподдерживаемая schema_version: {version!r}")

        def string_list(name: str) -> list[str]:
            value = data.get(name, [])
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                raise ValueError(f"поле {name} должно быть списком строк")
            return value

        def non_negative_int(value: Any, field_name: str) -> int:
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"поле quiz_scores.{field_name} должно быть неотрицательным целым")
            return value

        raw_scores = data.get("quiz_scores", {})
        if not isinstance(raw_scores, dict):
            raise ValueError("поле quiz_scores должно быть объектом")
        quiz_scores: dict[str, dict] = {}
        for module_id, raw_score in raw_scores.items():
            if not isinstance(module_id, str) or not isinstance(raw_score, dict):
                raise ValueError("quiz_scores должен содержать объекты результатов по строковым id модулей")
            correct = non_negative_int(raw_score.get("correct", 0), "correct")
            total = non_negative_int(raw_score.get("total", 0), "total")
            percent = non_negative_int(raw_score.get("percent", 0), "percent")
            attempts = non_negative_int(raw_score.get("attempts", 0), "attempts")
            passed = raw_score.get("passed", False)
            updated = raw_score.get("updated", "")
            if percent > 100 or correct > total or not isinstance(passed, bool) or not isinstance(updated, str):
                raise ValueError(f"некорректная запись результата теста для {module_id}")
            quiz_scores[module_id] = {
                "correct": correct,
                "total": total,
                "percent": percent,
                "passed": passed,
                "attempts": attempts,
                "updated": updated,
            }

        last_lesson = data.get("last_lesson", "")
        if not isinstance(last_lesson, str):
            raise ValueError("поле last_lesson должно быть строкой")
        return cls(
            completed_lessons=set(string_list("completed_lessons")),
            quiz_scores=quiz_scores,
            completed_tasks=set(string_list("completed_tasks")),
            last_lesson=last_lesson,
            streak_days=string_list("streak_days")[-60:],
        )


class ProgressStore:
    """Фасад над QSettings + JSON-зеркалом."""

    def __init__(self, settings: QSettings | None = None) -> None:
        self.settings = settings or QSettings(ORG, APP)
        self.recovery_warning = ""
        self.recovery_source = ""
        self.data = self._load_data()

    # --- низкоуровневое -------------------------------------------------
    @staticmethod
    def _parse_candidate(raw: Any) -> ProgressData:
        if isinstance(raw, str | bytes | bytearray):
            raw = json.loads(raw)
        return ProgressData.from_json(raw)

    def _load_data(self) -> ProgressData:
        errors: list[str] = []
        raw_settings = self.settings.value("progress/json", "")
        if raw_settings not in (None, ""):
            try:
                self.recovery_source = "QSettings"
                return self._parse_candidate(raw_settings)
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                errors.append(f"QSettings: {error}")

        mirror = user_data_dir() / "progress.json"
        if mirror.exists():
            try:
                self.recovery_source = "резервная копия progress.json"
                data = self._parse_candidate(mirror.read_text(encoding="utf-8"))
                if errors:
                    self.recovery_warning = "Основной файл прогресса повреждён; данные восстановлены из резервной копии."
                return data
            except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
                errors.append(f"progress.json: {error}")

        if errors:
            self.recovery_warning = (
                "Не удалось прочитать сохранённый прогресс или его резервную копию. "
                "Приложение запущено с пустым прогрессом; исходные файлы не удалены."
            )
        self.recovery_source = "новый прогресс" if not errors else "пустой после ошибки чтения"
        return ProgressData()

    @staticmethod
    def _atomic_write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, path)
        except Exception:
            Path(temporary_name).unlink(missing_ok=True)
            raise

    def save(self) -> None:
        payload = json.dumps(self.data.to_json(), ensure_ascii=False, separators=(",", ":"))
        self.settings.setValue("progress/json", payload)
        self.settings.sync()
        try:
            mirror_payload = json.dumps(self.data.to_json(), ensure_ascii=False, indent=2) + "\n"
            self._atomic_write(user_data_dir() / "progress.json", mirror_payload)
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
        lesson_keys = {lesson.key for lesson in course.all_lessons()}
        task_keys = {
            f"{module.module_id}/{task.tid}"
            for module in course.modules
            if module.practice is not None
            for task in module.practice.tasks
        }
        module_quiz_keys = {
            module.module_id for module in course.modules if module.quiz and module.quiz.questions
        }
        lesson_quiz_keys = {
            lesson.quiz.module_id for lesson in course.all_lessons() if lesson.quiz and lesson.quiz.questions
        }
        quiz_keys = module_quiz_keys | lesson_quiz_keys
        lessons_total = len(lesson_keys)
        tasks_total = len(task_keys)
        quizzes_total = len(quiz_keys)
        lessons_done = len(self.data.completed_lessons & lesson_keys)
        tasks_done = len(self.data.completed_tasks & task_keys)
        quizzes_passed = sum(
            1 for quiz_id in quiz_keys if self.data.quiz_scores.get(quiz_id, {}).get("passed")
        )
        lesson_quizzes_passed = sum(
            1 for quiz_id in lesson_quiz_keys if self.data.quiz_scores.get(quiz_id, {}).get("passed")
        )
        overall = 0
        if lessons_total or tasks_total or quizzes_total:
            overall = round(
                (
                    (lessons_done / lessons_total if lessons_total else 0)
                    + (tasks_done / tasks_total if tasks_total else 0)
                    + (quizzes_passed / quizzes_total if quizzes_total else 0)
                )
                / 3
                * 100
            )
        return {
            "lessons_done": lessons_done,
            "lessons_total": lessons_total,
            "tasks_done": tasks_done,
            "tasks_total": tasks_total,
            "quizzes_passed": quizzes_passed,
            "quizzes_total": quizzes_total,
            "lesson_quizzes_passed": lesson_quizzes_passed,
            "lesson_quizzes_total": len(lesson_quiz_keys),
            "modules_total": len(module_quiz_keys),
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
            f"- Тестов сдано: {summary['quizzes_passed']} из {summary['quizzes_total']}",
            f"- Дней занятий: {summary['days_active']}",
            "",
            "## Модули",
            "",
            "| Модуль | Уроки | Тесты уроков | Практика | Тест модуля |",
            "| --- | --- | --- | --- | --- |",
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
            lesson_quizzes = [lesson.quiz for lesson in module.lessons if lesson.quiz]
            lesson_quizzes_passed = sum(1 for quiz in lesson_quizzes if self.quiz_passed(quiz.module_id))
            percent = self.quiz_percent(module.module_id)
            lines.append(
                f"| {module.title} | {lessons_done}/{module.lesson_count} | "
                f"{lesson_quizzes_passed}/{len(lesson_quizzes)} | {tasks_done}/{module.task_count} | {percent}% |"
            )
        return "\n".join(lines) + "\n"

    # --- настройки приложения -------------------------------------------
    def get(self, key: str, default=None):
        return self.settings.value(key, default)

    def set(self, key: str, value) -> None:
        self.settings.setValue(key, value)
        self.settings.sync()
