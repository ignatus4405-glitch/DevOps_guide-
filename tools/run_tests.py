#!/usr/bin/env python3
"""Запуск pytest в CI: лог, junit-xml и аннотация провалов — всё через Python.

Почему не просто `pytest` в шаге workflow:
  * GitHub запускает bash со `-e`, поэтому падение pytest прерывает шаг раньше,
    чем успевает выполниться любой обработчик;
  * на Windows путь к `python`/`pytest` в разных оболочках отличается;
  * логи скачиваются не всегда (сервис логов недоступен, ограничения CI).

Поэтому тесты запускает этот скрипт: он пишет `reports/pytest.log` и
`reports/pytest.xml`, а при провале печатает аннотацию GitHub Actions —
её видно прямо в списке проверок и через API.

Использование:
    python tools/run_tests.py                 # все тесты
    python tools/run_tests.py --pytest-args "tests/test_ui_smoke.py -q"
    python tools/run_tests.py --no-annotate   # локально, без служебного вывода
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import subprocess
import sys

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
MAX_ANNOTATION = 1500


def escape_annotation(text: str) -> str:
    """Экранирует текст для workflow-команды GitHub (% и переводы строк)."""
    text = text.replace("%", "%25")
    text = text.replace("\r", "")
    return text.replace("\n", "%0A")


def tail_for_annotation(text: str, limit: int = MAX_ANNOTATION) -> str:
    """Готовит хвост вывода для аннотации: без ANSI-кодов и с жёстким лимитом.

    Обрезаем по строкам уже экранированного текста, чтобы не порвать
    последовательность ``%0A`` и уложиться в лимит аннотации.
    """
    escaped = escape_annotation(ANSI_RE.sub("", text))
    parts = escaped.split("%0A")
    while len(parts) > 1 and len("%0A".join(parts)) > limit:
        parts.pop(0)
    return "%0A".join(parts)[-limit:]


def failed_tests(text: str, limit: int = 12) -> list[str]:
    """Строки с упавшими тестами из итоговой сводки pytest."""
    collected: list[str] = []
    for line in ANSI_RE.sub("", text).splitlines():
        stripped = line.strip()
        if stripped.startswith(("FAILED", "ERROR")) and stripped not in collected:
            collected.append(stripped[:200])
        if len(collected) >= limit:
            break
    return collected


def build_command(pytest_args: str, junit: pathlib.Path) -> list[str]:
    """Команда запуска pytest через текущий интерпретатор (одинаково на всех ОС)."""
    return [sys.executable, "-m", "pytest", *pytest_args.split(), f"--junitxml={junit}"]


def use_utf8_output() -> None:
    """Переводит вывод на UTF-8: на Windows по умолчанию cp1252 и кириллица ломается.

    Без этого любой print с русским текстом падает с UnicodeEncodeError, и шаг CI
    завершается ошибкой без внятного сообщения.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):  # pragma: no cover - экзотические потоки
                pass


def child_env() -> dict[str, str]:
    """Окружение для pytest: тоже UTF-8, иначе тесты упадут на Windows."""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Запуск тестов с логом и аннотацией")
    parser.add_argument("--pytest-args", default="-q", help="аргументы pytest")
    parser.add_argument("--junitxml", default="reports/pytest.xml")
    parser.add_argument("--log", default="reports/pytest.log")
    parser.add_argument("--no-annotate", action="store_true", help="не печатать аннотацию при провале")
    args = parser.parse_args(argv)

    use_utf8_output()
    junit = pathlib.Path(args.junitxml)
    log_path = pathlib.Path(args.log)
    junit.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    command = build_command(args.pytest_args, junit)
    print(f"$ {' '.join(command)}", flush=True)
    result = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", errors="replace", env=child_env()
    )
    output = (result.stdout or "") + (result.stderr or "")
    log_path.write_text(output, encoding="utf-8")
    print(output, flush=True)

    if result.returncode == 0:
        print(f"tests: OK (лог: {log_path})")
        return 0

    summary = failed_tests(output)
    runner = os.environ.get("RUNNER_OS", "local")
    body = "\n".join(summary) if summary else "(сводка не распознана)"
    message = tail_for_annotation(body + "\n\n" + output)
    if not args.no_annotate:
        print(f"::error title=Провал тестов [{runner}]::{message}", flush=True)
    print(f"tests: FAILED (лог: {log_path})", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
