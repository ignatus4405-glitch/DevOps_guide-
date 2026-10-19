"""Безопасный симулятор практики без запуска команд на компьютере пользователя.

Решение сохраняется только в памяти учебного стенда. Проверка применяет правила
из practice.json к отправленному артефакту; она не подтверждает состояние реальной
ОС, облака или кластера.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .content import Task
from .practice_checker import TaskChecker

MAX_SUBMISSION_CHARS = 100_000
ReportStatus = Literal["ready", "passed", "failed", "manual_confirmation"]


@dataclass(frozen=True)
class SimulationReport:
    """Результат шага безопасного учебного стенда."""

    status: ReportStatus
    output: str


class PracticeSandbox:
    """Хранит отправленные артефакты в памяти и проверяет их по правилам задачи."""

    def __init__(self) -> None:
        self._workspace: dict[str, str] = {}

    def clear(self) -> None:
        """Сбрасывает виртуальное рабочее пространство при смене модуля."""
        self._workspace.clear()

    def discard(self, task_id: str) -> None:
        """Удаляет незапущенный/устаревший результат при выборе другой задачи."""
        self._workspace.pop(task_id, None)

    def run(self, task: Task, submission: str) -> SimulationReport:
        """Создаёт виртуальный артефакт; пользовательский текст не исполняется."""
        if not submission.strip():
            return SimulationReport("failed", "Введите решение или команды перед запуском стенда.")
        if len(submission) > MAX_SUBMISSION_CHARS:
            return SimulationReport(
                "failed",
                f"Ответ слишком большой: максимум {MAX_SUBMISSION_CHARS:,} символов.",
            )

        self._workspace[task.tid] = submission
        line_count = len(submission.splitlines())
        return SimulationReport(
            "ready",
            "🧪 Учебный стенд запущен.\n"
            f"В виртуальном каталоге создан артефакт задачи «{task.title}».\n"
            f"Получено строк: {line_count}; символов: {len(submission)}.\n"
            "Команды не запускаются на компьютере, файлы и настройки ОС не меняются.\n"
            "Нажмите «Проверить результат», чтобы выполнить критерии задачи.",
        )

    def verify(self, task: Task, *, manual_confirmed: bool = False) -> SimulationReport:
        """Проверяет виртуальный артефакт или запрашивает самооценку для manual-задач."""
        submission = self._workspace.get(task.tid)
        if submission is None:
            return SimulationReport("failed", "Сначала запустите задачу в учебном стенде.")

        if task.check_type == "manual":
            if not manual_confirmed:
                hint = task.validation_hint or "сверьтесь с целью и инструкциями задачи"
                return SimulationReport(
                    "manual_confirmation",
                    "Для этой задачи автоматического критерия нет.\n"
                    f"Проверьте результат самостоятельно: {hint}\n"
                    "После проверки подтвердите выполнение флажком и нажмите кнопку ещё раз.",
                )
            return SimulationReport(
                "passed",
                "✅ Ручная проверка подтверждена.\n"
                f"Критерий для реальной среды: {task.validation_hint or task.goal}\n"
                "Стенд сохранил только отчёт; команды не выполнялись.",
            )

        passed, message = TaskChecker.check(task, submission)
        if not passed:
            expected = f"\nОриентир проверки результата: {task.validation_hint}" if task.validation_hint else ""
            return SimulationReport("failed", f"❌ Проверка не пройдена.\n{message}{expected}")

        lines = ["✅ Проверка результата: PASS.", message]
        if task.validation_hint:
            lines.append(f"Для проверки на реальном стенде: {task.validation_hint}")
        lines.append("Это учебная симуляция: фактическое состояние вашей системы не проверялось и не менялось.")
        return SimulationReport("passed", "\n".join(lines))
