"""Тесты запуска приложения: launcher из исходников и режимы CLI."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUN_PY = ROOT / "run.py"


def _run(args: list[str], timeout: int = 180) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env.setdefault("PYTHONPATH", str(ROOT / "src"))
    return subprocess.run(
        [sys.executable, str(RUN_PY), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=ROOT,
        env=env,
        timeout=timeout,
        check=False,
    )


def test_launcher_exists():
    assert RUN_PY.exists(), "нет run.py — скрипт запуска из исходников"


def test_launcher_version():
    """`python run.py --version` печатает версию из VERSION и завершается нулём."""
    expected = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    result = _run(["--version"])
    assert result.returncode == 0, result.stderr
    assert expected in result.stdout


def test_launcher_self_test(course):
    """`python run.py --self-test` проверяет контент и говорит OK."""
    result = _run(["--self-test"])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "self-test: OK" in result.stdout


@pytest.mark.skipif(os.environ.get("CI_SKIP_GUI") == "1", reason="GUI выключен в этом окружении")
def test_launcher_help():
    result = _run(["--help"])
    assert result.returncode == 0
    assert "--self-test" in result.stdout
