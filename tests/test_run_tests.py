"""Тесты обёртки запуска pytest (tools/run_tests.py)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_tool(name: str):
    spec = importlib.util.spec_from_file_location(f"tool_{name}", ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def runner():
    return _load_tool("run_tests")


def test_escape_annotation(runner):
    assert runner.escape_annotation("a\nb") == "a%0Ab"
    assert runner.escape_annotation("100%") == "100%25"
    assert runner.escape_annotation("a\r\nb") == "a%0Ab"


def test_tail_strips_ansi_and_limits(runner):
    noisy = "заголовок\n" + "строка\n" * 500 + "\x1b[31mFAILED\x1b[0m tests/test_x.py::test_y\n"
    tail = runner.tail_for_annotation(noisy, limit=120)
    assert "\x1b" not in tail
    assert len(tail) <= 120
    assert "FAILED" in runner.tail_for_annotation(noisy)  # хвост содержит сводку


def test_failed_tests_extracts_summary(runner):
    output = (
        "=========================== short test summary info ============================\n"
        "FAILED tests/test_a.py::test_one - AssertionError: упало\n"
        "ERROR tests/test_b.py - ImportError\n"
        "1 failed, 1 error in 0.5s\n"
    )
    assert runner.failed_tests(output) == [
        "FAILED tests/test_a.py::test_one - AssertionError: упало",
        "ERROR tests/test_b.py - ImportError",
    ]


def test_failed_tests_deduplicates(runner):
    duplicated = "FAILED tests/test_a.py::test_one\nFAILED tests/test_a.py::test_one\n"
    assert runner.failed_tests(duplicated) == ["FAILED tests/test_a.py::test_one"]


def test_build_command_uses_current_interpreter(runner, tmp_path):
    command = runner.build_command("-q tests", tmp_path / "pytest.xml")
    assert command[0] == sys.executable
    assert command[1:3] == ["-m", "pytest"]
    assert "-q" in command and "tests" in command
    assert any(arg.startswith("--junitxml=") for arg in command)


def test_main_passes_on_green_suite(runner, tmp_path, capsys):
    """На зелёном файле тестов инструмент возвращает 0 и пишет лог."""
    test_file = tmp_path / "test_ok.py"
    test_file.write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    code = runner.main(
        [
            "--pytest-args",
            f"{test_file} -q",
            "--junitxml",
            str(tmp_path / "pytest.xml"),
            "--log",
            str(tmp_path / "pytest.log"),
        ]
    )
    assert code == 0
    assert (tmp_path / "pytest.log").exists()
    assert "1 passed" in (tmp_path / "pytest.log").read_text(encoding="utf-8")
    assert "::error" not in capsys.readouterr().out


def test_main_reports_failure_with_annotation(runner, tmp_path, capsys):
    """На красном файле — код 1 и аннотация с именем упавшего теста."""
    test_file = tmp_path / "test_bad.py"
    test_file.write_text("def test_bad():\n    assert False, 'нарочно'\n", encoding="utf-8")
    code = runner.main(
        [
            "--pytest-args",
            f"{test_file} -q",
            "--junitxml",
            str(tmp_path / "pytest.xml"),
            "--log",
            str(tmp_path / "pytest.log"),
        ]
    )
    output = capsys.readouterr().out
    assert code == 1
    assert "::error title=Провал тестов" in output
    assert "test_bad" in output
    assert (tmp_path / "pytest.xml").exists()


def test_main_no_annotate_flag(runner, tmp_path, capsys):
    test_file = tmp_path / "test_bad2.py"
    test_file.write_text("def test_bad2():\n    assert False\n", encoding="utf-8")
    code = runner.main(
        [
            "--pytest-args",
            f"{test_file} -q",
            "--no-annotate",
            "--log",
            str(tmp_path / "pytest.log"),
            "--junitxml",
            str(tmp_path / "pytest.xml"),
        ]
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "::error" not in out


def test_tool_is_runnable_as_script():
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "run_tests.py"), "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0
    assert "--no-annotate" in result.stdout
