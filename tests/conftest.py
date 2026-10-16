"""Общие фикстуры тестов: курс, временный прогресс, offscreen Qt."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("XDG_RUNTIME_DIR", "/tmp")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from devops_academy.content import Course  # noqa: E402


@pytest.fixture(scope="session")
def course() -> Course:
    return Course.load(ROOT / "content")


@pytest.fixture()
def qapp():
    """Приложение Qt для GUI-тестов (единый экземпляр на процесс)."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
