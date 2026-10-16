"""Тесты точки входа сборки (packaging/entry.py): журнал ошибок и потоки вывода."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def entry():
    spec = importlib.util.spec_from_file_location("entry_point", ROOT / "packaging" / "entry.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_log_path_honours_env(entry, monkeypatch, tmp_path):
    target = tmp_path / "custom.log"
    monkeypatch.setenv("DEVOPS_ACADEMY_LOG", str(target))
    assert entry.log_path() == target


def test_write_log_creates_file_and_appends(entry, monkeypatch, tmp_path):
    target = tmp_path / "nested" / "run.log"
    monkeypatch.setenv("DEVOPS_ACADEMY_LOG", str(target))
    entry.write_log("первая строка")
    entry.write_log("вторая строка")
    assert target.read_text(encoding="utf-8") == "первая строка\nвторая строка\n"


def test_write_log_survives_unwritable_path(entry, monkeypatch):
    """Проблемы доступа (Program Files) не должны ломать приложение."""
    monkeypatch.setenv("DEVOPS_ACADEMY_LOG", "/proc/невозможный/путь.log")
    entry.write_log("текст")  # не должно бросить исключение


def test_ensure_streams_restores_missing_output(entry, monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    entry.ensure_streams()
    assert sys.stdout is not None and sys.stderr is not None
    sys.stdout.write("проверка кириллицы: ✓\n")


def test_main_returns_error_code_and_logs_on_crash(entry, monkeypatch, tmp_path):
    """Необработанная ошибка: код 1 + запись в журнал (иначе в GUI её не увидеть)."""
    log_file = tmp_path / "crash.log"
    monkeypatch.setenv("DEVOPS_ACADEMY_LOG", str(log_file))

    def boom() -> int:
        raise RuntimeError("сломано нарочно")

    monkeypatch.setattr("devops_academy.main.run", boom)
    assert entry.main() == 1

    text = log_file.read_text(encoding="utf-8")
    assert "необработанная ошибка" in text
    assert "сломано нарочно" in text


def test_main_passes_exit_code_of_run(entry, monkeypatch):
    monkeypatch.setattr("devops_academy.main.run", lambda: 7)
    assert entry.main() == 7


def test_spec_uses_entry_point():
    """Спецификация PyInstaller должна собирать точку входа и включать контент."""
    spec = (ROOT / "packaging" / "devops_academy.spec").read_text(encoding="utf-8")
    assert "packaging" in spec and "entry.py" in spec
    assert '"content"' in spec
    assert 'name="DevOpsAcademy"' in spec
