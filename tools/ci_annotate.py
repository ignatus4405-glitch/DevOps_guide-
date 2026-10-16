#!/usr/bin/env python3
"""Превращает хвост лога в аннотацию GitHub Actions.

Зачем: логи workflow скачиваются отдельным сервисом, а аннотации доступны через API
(и видны прямо в списке проверок). Поэтому при провале шага мы дублируем суть в аннотацию.

Использование:
    python tools/ci_annotate.py reports/pytest.log --title "Провал тестов" --tail 1200
"""

from __future__ import annotations

import argparse
import os
import pathlib


def escape(text: str) -> str:
    """Экранирует переводы строк и служебные символы для workflow-команды GitHub."""
    text = text.replace("%", "%25")  # процент экранируем первым, иначе съест свои же %0A
    return text.replace("\r", "").replace("\n", "%0A")


def main() -> int:
    parser = argparse.ArgumentParser(description="Аннотация GitHub Actions из файла лога")
    parser.add_argument("log", help="путь к файлу с логом")
    parser.add_argument("--title", default="Провал шага")
    parser.add_argument("--tail", type=int, default=1500, help="сколько символов из конца лога показать")
    args = parser.parse_args()

    path = pathlib.Path(args.log)
    text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else "(лог не найден)"
    tail = escape(text[-args.tail :])
    runner = os.environ.get("RUNNER_OS", "unknown")
    job = os.environ.get("GITHUB_JOB", "job")
    print(f"::error title={args.title} [{runner}/{job}]::{tail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
