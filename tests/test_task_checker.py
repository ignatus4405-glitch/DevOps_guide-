"""Автопроверка практических задач: типы проверок и корректность вердиктов."""

from __future__ import annotations

from devops_academy.content import Task
from devops_academy.ui.practice_widget import TaskChecker


def make_task(check_type: str, patterns: list[str]) -> Task:
    return Task(
        tid="t1",
        title="Тестовая задача",
        goal="Проверить логику",
        level="easy",
        instructions=[],
        hints=[],
        solution="",
        check_type=check_type,
        patterns=patterns,
        feedback="Готово",
    )


def test_regex_all_requires_every_pattern():
    task = make_task("regex_all", ["git\\s+init", "git\\s+commit"])
    ok, _ = TaskChecker.check(task, "git init\nad\n")
    assert not ok
    ok, _ = TaskChecker.check(task, "git init && git commit -m 'x'")
    assert ok


def test_regex_any_accepts_one_of():
    task = make_task("regex_any", ["minikube\\s+start", "kind\\s+create"])
    assert TaskChecker.check(task, "kind create cluster")[0]
    assert not TaskChecker.check(task, "docker run nginx")[0]


def test_equals_is_case_and_space_insensitive():
    task = make_task("equals", ["/etc", " Systemctl  "])
    assert TaskChecker.check(task, "  /ETC ")[0]


def test_empty_answer_rejected():
    task = make_task("regex_all", ["git"])
    ok, message = TaskChecker.check(task, "   ")
    assert not ok and "Введите" in message


def test_manual_check_always_passes():
    task = make_task("manual", ["никогда-не-совпадет"])
    assert TaskChecker.check(task, "любой текст")[0]


def test_multiline_answers_supported():
    task = make_task("regex_all", ["^sudo", "chmod\\s+640"])
    assert TaskChecker.check(task, "sudo chown deploy:devs f\nsudo chmod 640 f")[0]
