#!/usr/bin/env python3
"""Точка входа для PyInstaller.

Почему отдельный файл: `src/devops_academy/main.py` рассчитан на запуск внутри пакета
(относительные импорты). Точка входа вне пакета использует абсолютный импорт, поэтому
собранное приложение гарантированно стартует в one-dir сборке.

Дополнительно: в windowed-сборке (console=False) потоки вывода могут отсутствовать,
поэтому перед печатью подставляем заглушку, чтобы `--self-test` не падал.
"""

from __future__ import annotations

import sys


class _NullStream:
    """Заглушка для stdout/stderr в сборке без консоли (console=False)."""

    def write(self, text: str) -> int:  # pragma: no cover - просто проглатывает вывод
        return len(text)

    def flush(self) -> None:  # pragma: no cover
        return None

    def isatty(self) -> bool:  # pragma: no cover
        return False


def main() -> int:
    if sys.stdout is None:
        sys.stdout = _NullStream()  # type: ignore[assignment]
    if sys.stderr is None:
        sys.stderr = _NullStream()  # type: ignore[assignment]

    from devops_academy.main import run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
