"""Пути к курсу и версия wheel для обычной pip-установки."""

from __future__ import annotations

from pathlib import Path

import tomllib

from devops_academy import paths

ROOT = Path(__file__).resolve().parents[1]


def test_content_dir_prefers_course_embedded_in_installed_package(tmp_path, monkeypatch):
    package_dir = tmp_path / "site-packages" / "devops_academy"
    packaged_content = package_dir / "content"
    packaged_content.mkdir(parents=True)
    monkeypatch.setattr(paths, "__file__", str(package_dir / "paths.py"))
    monkeypatch.setattr(paths, "_frozen", lambda: False)

    assert paths.content_dir() == packaged_content


def test_checkout_content_dir_fallback():
    assert paths.content_dir() == ROOT / "content"


def test_package_version_is_read_from_canonical_version_file():
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "version" in config["project"]["dynamic"]
    assert config["tool"]["setuptools"]["dynamic"]["version"]["file"] == "VERSION"
    from devops_academy.version import APP_VERSION

    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == APP_VERSION
