#!/usr/bin/env python3
"""Точка входа для PyInstaller.

Почему отдельный файл: `src/devops_academy/main.py` рассчитан на запуск внутри пакета
(относительные импорты). Точка входа вне пакета использует абсолютный импорт, поэтому
собранное приложение гарантированно стартует в one-dir сборке.

Дополнительно решаются проблемы windowed-сборки (``console=False``):

* потоки вывода могут отсутствовать — подставляем заглушку, чтобы ``print`` не падал;
* любое исключение записывается в файл-журнал (путь можно задать переменной окружения
  ``DEVOPS_ACADEMY_LOG``), иначе в GUI-сборке ошибку не увидеть;
* код возврата сохраняется, поэтому ``DevOpsAcademy.exe --self-test`` годится для CI.
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


class _NullStream:
    """Заглушка для stdout/stderr в сборке без консоли (console=False)."""

    def write(self, text: str) -> int:  # pragma: no cover - просто проглатывает вывод
        return len(text)

    def flush(self) -> None:  # pragma: no cover
        return None

    def isatty(self) -> bool:  # pragma: no cover
        return False


def log_path() -> Path | None:
    """Куда писать журнал: переменная окружения или каталог рядом с приложением."""
    custom = os.environ.get("DEVOPS_ACADEMY_LOG")
    if custom:
        return Path(custom)
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent / "dist"
    return base / "devops_academy.log"


def write_log(text: str) -> None:
    """Пишет журнал, молча игнорируя проблемы доступа (Program Files и т.п.)."""
    target = log_path()
    if target is None:
        return
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(text)
            if not text.endswith("\n"):
                handle.write("\n")
    except OSError:  # pragma: no cover - защита от прав доступа
        pass


def ensure_streams() -> None:
    """Гарантирует наличие stdout/stderr и подсказку про кодировку."""
    for name in ("stdout", "stderr"):
        if getattr(sys, name, None) is None:
            setattr(sys, name, _NullStream())
    if hasattr(sys.stdout, "reconfigure"):
        try:  # чтобы русский текст не падал в cp1252 на Windows
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):  # pragma: no cover
            pass


def main() -> int:
    ensure_streams()
    try:
        from devops_academy.main import run

        return run()
    except SystemExit:
        raise
    except BaseException:  # noqa: BLE001 - любая ошибка должна попасть в журнал
        text = traceback.format_exc()
        print(text, file=sys.stderr)
        write_log("DevOps Academy: необработанная ошибка\n" + text)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
