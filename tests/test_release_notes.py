"""Тесты генератора release notes и записей в CHANGELOG."""

from __future__ import annotations

import importlib.util
import subprocess
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
def notes_tool():
    return _load_tool("release_notes")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    )


def test_classify_groups(notes_tool):
    commits = [
        ("aaa1111", "feat: добавили модуль про Kubernetes"),
        ("bbb2222", "fix: поправили опечатку в уроке"),
        ("ccc3333", "docs: обновили README"),
        ("ddd4444", "ci: ускорили сборку"),
        ("eee5555", "странный коммит без префикса"),
    ]
    grouped = notes_tool.classify(commits)
    assert grouped["Добавлено"] == ["Добавили модуль про Kubernetes"]
    assert grouped["Исправлено"] == ["Поправили опечатку в уроке"]
    assert grouped["Документация"] == ["Обновили README"]
    assert grouped["Инфраструктура и тесты"] == ["Ускорили сборку"]
    assert grouped["Прочее"] == ["Странный коммит без префикса"]  # первая буква приводится к заглавной


def test_classify_breaking_changes(notes_tool):
    grouped = notes_tool.classify(
        [
            ("a1", "feat!: новый формат прогресса"),
            ("b2", "refactor: переписали загрузчик\n\nBREAKING CHANGE: старый формат больше не читается"),
        ]
    )
    assert grouped["Ломающие изменения"] == [
        "Новый формат прогресса",
        "Переписали загрузчик",
    ]
    assert grouped["Изменено"] == []


def test_changelog_section_has_groups(notes_tool):
    grouped = notes_tool.classify([("a1", "feat: новая тема"), ("b2", "fix: баг в тесте")])
    section = notes_tool.changelog_section("1.4.0", "2026-05-01", grouped)
    assert section.startswith("## [1.4.0] — 2026-05-01")
    assert "### Добавлено\n- Новая тема" in section
    assert "### Исправлено\n- Баг в тесте" in section


def test_changelog_section_for_empty_release(notes_tool):
    section = notes_tool.changelog_section("1.0.1", "2026-05-01", notes_tool.classify([]))
    assert "Служебный релиз без заметных изменений" in section


def test_update_changelog_inserts_after_header(notes_tool, tmp_path):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# История изменений\n\n## [0.1.0] — 2026-01-01\n\n- Первый релиз\n", encoding="utf-8")
    notes_tool.update_changelog(changelog, "## [0.2.0] — 2026-02-01\n\n### Добавлено\n- Модуль\n", "0.2.0")

    text = changelog.read_text(encoding="utf-8")
    assert text.startswith("# История изменений\n\n## [0.2.0]")
    assert text.index("## [0.2.0]") < text.index("## [0.1.0]")
    assert "- Первый релиз" in text


def test_update_changelog_skips_duplicate(notes_tool, tmp_path, capsys):
    changelog = tmp_path / "CHANGELOG.md"
    original = "# История изменений\n\n## [0.2.0] — 2026-02-01\n\n- Уже есть\n"
    changelog.write_text(original, encoding="utf-8")
    notes_tool.update_changelog(changelog, "## [0.2.0] — 2026-02-01\n\n- Дубль\n", "0.2.0")

    assert changelog.read_text(encoding="utf-8") == original
    assert "пропускаем" in capsys.readouterr().out


def test_release_notes_contains_installation(notes_tool):
    grouped = notes_tool.classify([("a1", "feat: что-то новое")])
    text = notes_tool.release_notes("2.0.0", grouped, [("a1", "feat: что-то новое")])
    assert "## Что изменилось в 2.0.0" in text
    assert "DevOpsAcademy-Setup-2.0.0.exe" in text
    assert "SHA256SUMS.txt" in text
    assert "коммитов в релизе: 1" in text


def test_main_writes_notes_and_changelog(notes_tool, tmp_path, monkeypatch):
    """Полный прогон инструмента на временном git-репозитории."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "VERSION").write_text("0.5.0\n", encoding="utf-8")
    (repo / "CHANGELOG.md").write_text("# История изменений\n", encoding="utf-8")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "feat: первый публичный набор уроков")
    (repo / "extra.md").write_text("материал\n", encoding="utf-8")
    _git(repo, "add", "extra.md")
    _git(repo, "commit", "-q", "-m", "fix: уточнили формулировку задания")

    monkeypatch.chdir(tmp_path)
    code = notes_tool.main(
        [
            "--version",
            "0.5.0",
            "--repo",
            "owner/repo",
            "--repo-dir",
            str(repo),
            "--notes-file",
            str(tmp_path / "release_notes.md"),
            "--changelog",
            str(repo / "CHANGELOG.md"),
            "--date",
            "2026-03-03",
        ]
    )
    assert code == 0
    notes = (tmp_path / "release_notes.md").read_text(encoding="utf-8")
    assert "Первый публичный набор уроков" in notes
    assert "Уточнили формулировку задания" in notes

    changelog = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [0.5.0] — 2026-03-03" in changelog
    assert "### Добавлено" in changelog and "### Исправлено" in changelog
