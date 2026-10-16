#!/usr/bin/env python3
"""Определяет, выпускать ли релиз и с какой версией (для workflow Build & Release).

Правила:
  * версия ещё не выпускалась (нет тега v<версия>) -> выпускаем её как есть;
  * версия уже выпущена                         -> поднимаем по истории коммитов:
        BREAKING CHANGE / "!:"  -> major
        feat:                   -> minor
        всё остальное           -> patch

Использование в CI (пишет outputs в $GITHUB_OUTPUT):
    python tools/next_version.py --bump auto --remote origin >> "$GITHUB_OUTPUT"

Локальная проверка:
    python tools/next_version.py --bump auto --print
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"
TAG_PREFIX = "v"


def git(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    """Запускает git и возвращает stdout (без падения на пустом выводе)."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd or ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} завершился с кодом {result.returncode}: {result.stderr.strip()}")
    return result.stdout.strip()


def current_version(repo: Path) -> str:
    return (repo / "VERSION").read_text(encoding="utf-8").strip()


def tag_exists(repo: Path, tag: str, remote: str) -> bool:
    """Проверяет тег: сначала через remote (ls-remote), затем локально."""
    if remote:
        try:
            if git("ls-remote", "--tags", remote, f"refs/tags/{tag}", cwd=repo, check=False):
                return True
        except (RuntimeError, FileNotFoundError):  # pragma: no cover - git отсутствует
            pass
    return bool(git("tag", "--list", tag, cwd=repo, check=False))


def last_tag(repo: Path, prefix: str = TAG_PREFIX) -> str:
    """Ближайший достижимый тег (пустая строка, если тегов нет)."""
    return git("describe", "--tags", "--abbrev=0", "--match", f"{prefix}*", cwd=repo, check=False)


def commit_messages(repo: Path, since: str) -> list[str]:
    args = ["log", "--pretty=%B"] + ([f"{since}..HEAD"] if since else ["-50"])
    output = git(*args, cwd=repo, check=False)
    return [block for block in output.split("\n\n") if block.strip()]


def detect_bump(messages: list[str], requested: str = "auto") -> str:
    """Определяет тип изменения по сообщениям коммитов."""
    if requested != "auto":
        return requested
    joined = "\n".join(messages)
    if re.search(r"BREAKING CHANGE|!: ", joined) or re.search(r"^[a-z]+(\([^)]*\))?!:", joined, re.MULTILINE):
        return "major"
    if re.search(r"^feat(\([^)]*\))?!?:", joined, re.MULTILINE):
        return "minor"
    return "patch"


def bump_version(version: str, bump: str) -> str:
    """Поднимает semver-версию на один шаг."""
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version.strip())
    if not match:
        raise ValueError(f"версия не в формате semver: {version!r}")
    major, minor, patch = (int(part) for part in match.groups())
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"неизвестный тип подъёма версии: {bump}")


def decide(repo: Path, requested_bump: str, remote: str) -> dict[str, str]:
    current = current_version(repo)
    if not tag_exists(repo, f"{TAG_PREFIX}{current}", remote):
        return {"release": "true", "version": current}

    if requested_bump == "none":
        return {"release": "false", "version": current}

    messages = commit_messages(repo, last_tag(repo))
    bump = detect_bump(messages, requested_bump)
    return {"release": "true", "version": bump_version(current, bump), "bump": bump}


def write_outputs(result: dict[str, str], to_file: str | None) -> None:
    lines = [f"{key}={value}" for key, value in result.items()]
    if to_file:
        with open(to_file, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    else:
        print("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Расчёт следующей версии релиза")
    parser.add_argument("--bump", default="auto", choices=["auto", "none", "patch", "minor", "major"])
    parser.add_argument("--repo", default=str(ROOT), help="путь к git-репозиторию")
    parser.add_argument("--remote", default="", help="имя remote для проверки тегов (например origin)")
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT", ""))
    parser.add_argument("--print", dest="print_only", action="store_true", help="печатать результат в stdout")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    result = decide(repo, args.bump, args.remote)
    if args.print_only or not args.github_output:
        write_outputs(result, None)
    else:
        write_outputs(result, args.github_output)
        print(f"release={result['release']}, version={result['version']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
