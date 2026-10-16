#!/usr/bin/env python3
"""Запуск DevOps Academy из исходников:  python run.py [--self-test|--version] [--content-dir DIR]

Почему отдельный файл: `src/devops_academy/main.py` использует относительные импорты
(он же — точка входа PyInstaller), поэтому запускать его нужно как модуль пакета.
Этот скрипт добавляет `src` в путь импорта и вызывает пакет — работает на любой ОС:

    python run.py                 # запуск приложения
    python run.py --version       # печать версии
    python run.py --self-test     # проверка контента и зависимостей
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from devops_academy.main import run  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run())
