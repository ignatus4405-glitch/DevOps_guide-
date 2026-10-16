"""Тесты релизных инструментов: расчёт версии и манифест обновления."""

from __future__ import annotations

import importlib.util
import json
import shutil
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
def next_version():
    return _load_tool("next_version")


@pytest.fixture(scope="module")
def manifest_tool():
    return _load_tool("make_update_manifest")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    """Мини-репозиторий с VERSION и одним коммитом."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "VERSION").write_text("1.2.3\n", encoding="utf-8")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "VERSION")
    _git(repo, "commit", "-q", "-m", "chore: начальная версия")
    return repo


def test_detect_bump(next_version):
    assert next_version.detect_bump(["feat: новый модуль курса"]) == "minor"
    assert next_version.detect_bump(["feat(ui): баннер обновления"]) == "minor"
    assert next_version.detect_bump(["fix: падение на Windows"]) == "patch"
    assert next_version.detect_bump(["docs: правки README"]) == "patch"
    assert next_version.detect_bump(["feat!: новая схема прогресса"]) == "major"
    assert next_version.detect_bump(["fix: мелочь\n\nBREAKING CHANGE: убрали старый формат"]) == "major"
    assert next_version.detect_bump(["feat: что-то"], requested="patch") == "patch"


def test_bump_version(next_version):
    assert next_version.bump_version("1.2.3", "patch") == "1.2.4"
    assert next_version.bump_version("1.2.3", "minor") == "1.3.0"
    assert next_version.bump_version("1.2.3", "major") == "2.0.0"
    with pytest.raises(ValueError):
        next_version.bump_version("1.2", "patch")
    with pytest.raises(ValueError):
        next_version.bump_version("1.2.3", "иногда")


def test_decide_releases_unreleased_version(next_version, git_repo):
    """Версии нет среди тегов — выпускаем её без подъёма."""
    result = next_version.decide(git_repo, "auto", remote="")
    assert result["release"] == "true"
    assert result["version"] == "1.2.3"


def test_decide_bumps_released_version(next_version, git_repo):
    """Версия уже выпущена (есть тег) + коммит feat → minor."""
    _git(git_repo, "tag", "v1.2.3")
    (git_repo / "README.md").write_text("документация\n", encoding="utf-8")
    _git(git_repo, "add", "README.md")
    _git(git_repo, "commit", "-q", "-m", "feat: добавили документацию")

    result = next_version.decide(git_repo, "auto", remote="")
    assert result == {"release": "true", "version": "1.3.0", "bump": "minor"}


def test_decide_bump_none(next_version, git_repo):
    _git(git_repo, "tag", "v1.2.3")
    result = next_version.decide(git_repo, "none", remote="")
    assert result == {"release": "false", "version": "1.2.3"}


def test_write_outputs_to_github_output(next_version, tmp_path):
    target = tmp_path / "out.txt"
    next_version.write_outputs({"release": "true", "version": "2.0.0"}, str(target))
    assert target.read_text(encoding="utf-8") == "release=true\nversion=2.0.0\n"


def test_build_manifest(manifest_tool, tmp_path):
    for name in [
        "DevOpsAcademy-0.4.1-windows-x64.zip",
        "DevOpsAcademy-Setup-0.4.1.exe",
        "DevOpsAcademy-0.4.1-linux-x64.tar.gz",
    ]:
        (tmp_path / name).write_bytes(b"data")

    manifest = manifest_tool.build_manifest("0.4.1", "owner/repo", "v0.4.1", sorted(p.name for p in tmp_path.iterdir()))
    assert manifest["version"] == "0.4.1"
    assert manifest["tag"] == "v0.4.1"
    assert manifest["installer"] == "DevOpsAcademy-Setup-0.4.1.exe"
    assert manifest["installer_url"].endswith("/releases/download/v0.4.1/DevOpsAcademy-Setup-0.4.1.exe")
    assert manifest["sha256_url"].endswith("/releases/download/v0.4.1/SHA256SUMS.txt")
    assert manifest["notes_url"] == "https://github.com/owner/repo/releases/tag/v0.4.1"
    assert manifest["channel"] == "stable"
    assert manifest["min_supported"] == manifest_tool.MIN_SUPPORTED


def test_manifest_cli_skips_noise_files(manifest_tool, tmp_path, monkeypatch):
    """update.json не попадает в список ассетов и пишется в файл."""
    (tmp_path / "DevOpsAcademy-Setup-1.0.0.exe").write_bytes(b"x")
    (tmp_path / "update.json").write_text("{}", encoding="utf-8")
    (tmp_path / "SHA256SUMS.txt").write_text("", encoding="utf-8")
    (tmp_path / "RELEASE_NOTES.md").write_text("заметки", encoding="utf-8")

    assert manifest_tool.main(["--version", "1.0.0", "--repo", "owner/repo", "--dir", str(tmp_path)]) == 0
    data = json.loads((tmp_path / "update.json").read_text(encoding="utf-8"))
    assert data["assets"] == ["DevOpsAcademy-Setup-1.0.0.exe"]


def test_tools_have_no_unexpected_side_effects_before_main():
    """Инструменты импортируются без запуска и без обращения к git."""
    assert shutil.which("git") is not None
