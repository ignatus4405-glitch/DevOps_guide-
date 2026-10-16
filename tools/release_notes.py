#!/usr/bin/env python3
"""Готовит текст релиза и запись в CHANGELOG.

Зачем: каждое изменение должно быть задокументировано, поэтому запись в CHANGELOG.md
и release notes формируются автоматически из истории коммитов (Conventional Commits).

Использование (в CI):
    python tools/release_notes.py --version 0.2.0 --repo owner/name \
        --notes-file release_notes.md --changelog CHANGELOG.md
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Группы changelog: заголовок -> префиксы Conventional Commits
GROUPS: list[tuple[str, tuple[str, ...]]] = [
    ("Добавлено", ("feat",)),
    ("Исправлено", ("fix",)),
    ("Изменено", ("refactor", "perf", "style", "revert")),
    ("Документация", ("docs",)),
    ("Инфраструктура и тесты", ("chore", "ci", "build", "test", "deps")),
]

BREAKING_RE = re.compile(r"BREAKING CHANGE|^[a-z]+(\([^)]*\))?!:")

# Служебные коммиты, которые не должны попадать в описание релиза
NOISE_RE = re.compile(r"^(chore\(release\)|Merge |Release )|\[skip ci\]")
SUBJECT_RE = re.compile(r"^(?P<type>[a-z]+)(?:\([^)]*\))?(?P<breaking>!)?:\s*(?P<text>.+)$")


def git_log(repo: Path, previous: str) -> list[tuple[str, str]]:
    """Список (hash, subject) с последнего тега (или последние 50 коммитов)."""
    # --no-merges: сообщения «Merge pull request #N» не несут смысла для пользователя
    args = ["log", "--no-merges", "--pretty=%h%x09%s"] + ([f"{previous}..HEAD"] if previous else ["-50"])
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    commits: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        if "\t" not in line:
            continue
        short_hash, subject = line.split("\t", 1)
        commits.append((short_hash.strip(), subject.strip()))
    return commits


def previous_tag(repo: Path, exclude: str = "") -> str:
    """Ближайший тег, кроме выпускаемого."""
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    tag = result.stdout.strip()
    return "" if tag == exclude else tag


def classify(commits: list[tuple[str, str]]) -> dict[str, list[str]]:
    """Раскладывает коммиты по группам changelog.

    Учитывается только первая строка (тема коммита); ломающие изменения
    определяются и по теме (``feat!:``), и по телу коммита (``BREAKING CHANGE:``).
    """
    grouped: dict[str, list[str]] = {title: [] for title, _ in GROUPS}
    grouped["Ломающие изменения"] = []
    grouped["Прочее"] = []

    for _short, raw in commits:
        lines = raw.splitlines()
        summary = lines[0].strip() if lines else ""
        if NOISE_RE.search(summary):
            continue  # релизные и merge-коммиты не описываем пользователю
        body = "\n".join(lines[1:])
        match = SUBJECT_RE.match(summary)
        text = match.group("text") if match else summary
        entry = (text[:1].upper() + text[1:]).strip() if text else summary

        if BREAKING_RE.search(summary) or BREAKING_RE.search(body):
            grouped["Ломающие изменения"].append(entry)
            continue
        if not match:
            grouped["Прочее"].append(entry)
            continue
        prefix = match.group("type")
        for title, prefixes in GROUPS:
            if prefix in prefixes:
                grouped[title].append(entry)
                break
        else:
            grouped["Прочее"].append(entry)
    return grouped


def ordered_groups(grouped: dict[str, list[str]]) -> list[tuple[str, list[str]]]:
    """Группы в порядке вывода: сначала ломающие изменения, затем обычные."""
    order = ["Ломающие изменения", *[title for title, _ in GROUPS], "Прочее"]
    return [(title, grouped.get(title) or []) for title in order]


def changelog_section(version: str, date: str, grouped: dict[str, list[str]]) -> str:
    """Формирует блок для CHANGELOG.md."""
    lines = [f"## [{version}] — {date}", ""]
    for title, items in ordered_groups(grouped):
        if not items:
            continue
        heading = f"### ⚠️ {title}" if title == "Ломающие изменения" else f"### {title}"
        lines.extend([heading, *[f"- {item}" for item in items], ""])
    if not any(items for _, items in ordered_groups(grouped)):
        lines.extend(["- Служебный релиз без заметных изменений", ""])
    return "\n".join(lines).rstrip() + "\n"


def release_notes(version: str, grouped: dict[str, list[str]], commits: list[tuple[str, str]]) -> str:
    """Формирует текст GitHub Release."""
    lines = [f"## Что изменилось в {version}", ""]
    shown = False
    for title, items in ordered_groups(grouped):
        if not items:
            continue
        shown = True
        lines.append(f"### {title}")
        lines.extend(f"- {item}" for item in items)
        lines.append("")
    if not shown:
        lines.extend(["- Служебный релиз без заметных изменений", ""])

    lines.extend(
        [
            "## Установка",
            f"1. Скачайте `DevOpsAcademy-Setup-{version}.exe` и запустите установку.",
            "2. Приложение само показывает уведомление о новых версиях.",
            "",
            "## Контроль целостности",
            "SHA-256 всех файлов — в `SHA256SUMS.txt`; приложение проверяет хеш перед установкой.",
            "",
            f"<sub>Всего коммитов в релизе: {len(commits)}</sub>",
        ]
    )
    return "\n".join(lines) + "\n"


def update_changelog(path: Path, section: str, version: str) -> None:
    """Вставляет новую версию в CHANGELOG.md сразу после заголовка файла."""
    header = "# История изменений"
    text = path.read_text(encoding="utf-8") if path.exists() else header + "\n"
    if f"## [{version}]" in text:
        print(f"CHANGELOG.md уже содержит версию {version} — пропускаем")
        return

    lines = text.splitlines()
    insert_at = 1
    for index, line in enumerate(lines):
        if line.startswith("# "):
            insert_at = index + 1
            break
    head = [*lines[:insert_at], "", *section.rstrip().splitlines(), ""]
    tail = lines[insert_at:]
    while tail and not tail[0].strip():
        tail.pop(0)
    path.write_text("\n".join([*head, *tail]).rstrip() + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Release notes и запись в CHANGELOG")
    parser.add_argument("--version", required=True)
    parser.add_argument("--repo", default="ignatus4405-glitch/DevOps_guide-", help="owner/name")
    parser.add_argument("--previous", default="", help="тег предыдущего релиза (по умолчанию — ближайший)")
    parser.add_argument("--notes-file", default="release_notes.md")
    parser.add_argument("--changelog", default="CHANGELOG.md")
    parser.add_argument("--date", default=dt.date.today().isoformat())
    parser.add_argument("--repo-dir", default=str(ROOT))
    parser.add_argument("--no-changelog", action="store_true", help="не трогать CHANGELOG.md")
    args = parser.parse_args(argv)

    repo = Path(args.repo_dir).resolve()
    previous = args.previous or previous_tag(repo, exclude=f"v{args.version}")
    if previous == f"v{args.version}":
        previous = ""
    commits = git_log(repo, previous)
    grouped = classify(commits)

    Path(args.notes_file).write_text(release_notes(args.version, grouped, commits), encoding="utf-8")
    if not args.no_changelog:
        update_changelog(Path(args.changelog), changelog_section(args.version, args.date, grouped), args.version)

    print(f"release notes: версия {args.version}, коммитов {len(commits)}, предыдущий тег: {previous or '—'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
