"""Безопасное выполнение практики в памяти и проверка виртуального результата."""

from __future__ import annotations

from pathlib import Path

from devops_academy.content import CommandRequirement, Task
from devops_academy.practice_simulator import PracticeSandbox


def make_task(
    check_type: str = "regex_all",
    *,
    patterns: list[str] | None = None,
    commands: list[CommandRequirement] | None = None,
) -> Task:
    return Task(
        tid="demo-task",
        title="Учебная задача",
        goal="Создать корректный артефакт",
        level="easy",
        instructions=["Создайте решение"],
        hints=[],
        solution="FROM python:3.12-slim",
        check_type=check_type,
        patterns=patterns or ["FROM python", "USER\\s+app"],
        feedback="Критерии задачи выполнены.",
        validation_hint="Проверьте ожидаемый результат в изолированной учебной среде.",
        commands=commands or [],
    )


def test_simulator_stores_answer_and_checks_result():
    task = make_task()
    sandbox = PracticeSandbox()

    run_report = sandbox.run(task, "FROM python:3.12-slim\nUSER app")
    assert run_report.status == "ready"
    assert "виртуальном каталоге" in run_report.output
    assert "не запускаются" in run_report.output

    verify_report = sandbox.verify(task)
    assert verify_report.status == "passed"
    assert "PASS" in verify_report.output
    assert task.validation_hint in verify_report.output


def test_failed_criteria_can_be_fixed_and_rerun():
    task = make_task()
    sandbox = PracticeSandbox()

    sandbox.run(task, "FROM python:3.12-slim")
    failed = sandbox.verify(task)
    assert failed.status == "failed"
    assert "Не хватает" in failed.output

    sandbox.run(task, "FROM python:3.12-slim\nUSER app")
    assert sandbox.verify(task).status == "passed"


def test_manual_task_requires_user_confirmation():
    task = make_task("manual", patterns=[])
    sandbox = PracticeSandbox()
    assert sandbox.run(task, "Метрики сняты, результат проверен").status == "ready"

    needs_confirmation = sandbox.verify(task)
    assert needs_confirmation.status == "manual_confirmation"
    assert task.validation_hint in needs_confirmation.output

    confirmed = sandbox.verify(task, manual_confirmed=True)
    assert confirmed.status == "passed"
    assert "подтверждена" in confirmed.output


def test_command_simulation_never_creates_real_files(tmp_path: Path):
    target = tmp_path / "would-be-created.txt"
    task = make_task(
        "commands",
        patterns=[],
        commands=[CommandRequirement("touch", [str(target)])],
    )
    sandbox = PracticeSandbox()

    assert sandbox.run(task, f"touch {target}").status == "ready"
    assert sandbox.verify(task).status == "passed"
    assert not target.exists()


def test_sandbox_requires_submission_and_limits_size():
    task = make_task()
    sandbox = PracticeSandbox()
    assert sandbox.run(task, "   ").status == "failed"
    assert sandbox.run(task, "x" * 100_001).status == "failed"
    assert sandbox.verify(task).status == "failed"
