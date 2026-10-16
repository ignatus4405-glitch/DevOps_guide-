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
    command = runner.build_command("-q tests", tmp_path / "pytest.xml", "custom_pytest")
    assert "custom_pytest" in command
    command = runner.build_command("-q tests", tmp_path / "pytest.xml")
    assert command[0] == sys.executable
    assert command[1:3] == ["-m", "pytest"]
    assert "-q" in command and "tests" in command
    assert any(arg.startswith("--junitxml=") for arg in command)


STUB_MODULE = """
import sys

code = int(__import__("os").environ.get("STUB_EXIT", "0"))
args = sys.argv[1:]
junit = next((a.split("=", 1)[1] for a in args if a.startswith("--junitxml=")), "")
print("stub pytest:", " ".join(args))
if code == 0:
    print("1 passed in 0.01s")
else:
    print("=========================== short test summary info ============================")
    print("FAILED tests/test_stub.py::test_нарочно - AssertionError: сломано")
    print("1 failed in 0.01s")
if junit:
    open(junit, "w", encoding="utf-8").write("<testsuite/>")
sys.exit(code)
"""


@pytest.fixture()
def stub_pytest(tmp_path, monkeypatch) -> Path:
    """Заглушка pytest: герметично проверяем логику инструментальной обёртки."""
    module_dir = tmp_path / "stub"
    module_dir.mkdir()
    (module_dir / "stub_pytest.py").write_text(STUB_MODULE, encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(module_dir))
    return module_dir


def test_main_passes_on_green_suite(runner, tmp_path, stub_pytest, monkeypatch, capsys):
    """Зелёный прогон: код 0, лог и junit-xml созданы, аннотации нет."""
    monkeypatch.setenv("STUB_EXIT", "0")
    log = tmp_path / "pytest.log"
    junit = tmp_path / "pytest.xml"
    code = runner.main(["--pytest-module", "stub_pytest", "--junitxml", str(junit), "--log", str(log)])
    captured = capsys.readouterr().out

    assert code == 0, captured
    assert log.exists() and "1 passed" in log.read_text(encoding="utf-8")
    assert junit.exists()
    assert "::error" not in captured


def test_main_reports_failure_with_annotation(runner, tmp_path, stub_pytest, monkeypatch, capsys):
    """Красный прогон: код 1 и аннотация с именем упавшего теста."""
    monkeypatch.setenv("STUB_EXIT", "1")
    log = tmp_path / "pytest.log"
    junit = tmp_path / "pytest.xml"
    code = runner.main(["--pytest-module", "stub_pytest", "--junitxml", str(junit), "--log", str(log)])
    output = capsys.readouterr().out

    assert code == 1
    assert "::error title=Провал тестов" in output
    assert "test_нарочно" in output
    assert "FAILED" in output


def test_real_pytest_end_to_end(runner, tmp_path):
    r"""Настоящий pytest на настоящем файле: инструмент должен вернуть 0.

    Явно задаём rootdir и basetemp: без этого на Windows pytest уходит искать
    конфигурацию вверх по диску и спотыкается о служебные каталоги (`C:\Documents and Settings`).
    """
    workdir = tmp_path / "e2e"
    workdir.mkdir()
    (workdir / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    code = runner.main(
        [
            "--pytest-args",
            f"{workdir} -q --rootdir {workdir} -p no:cacheprovider --basetemp {workdir / 'tmp'}",
            "--junitxml",
            str(workdir / "pytest.xml"),
            "--log",
            str(workdir / "pytest.log"),
            "--no-annotate",
        ]
    )
    log_text = (workdir / "pytest.log").read_text(encoding="utf-8")
    assert code == 0, log_text
    assert "1 passed" in log_text


def test_main_no_annotate_flag(runner, tmp_path, stub_pytest, monkeypatch, capsys):
    monkeypatch.setenv("STUB_EXIT", "3")
    code = runner.main(
        [
            "--pytest-module",
            "stub_pytest",
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
    assert "tests: FAILED" in out


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


def test_utf8_output_helpers(runner):
    """Вывод принудительно UTF-8: иначе на Windows падает кириллица."""
    runner.use_utf8_output()
    env = runner.child_env()
    assert env["PYTHONIOENCODING"] == "utf-8"
    assert env["PYTHONUTF8"] == "1"
    print("проверка кириллицы: ✓")  # если кодировка не настроена, тест упадёт
