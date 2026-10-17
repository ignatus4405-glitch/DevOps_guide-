#!/usr/bin/env python3
"""Генерация src/devops_academy/version.py и content/content_index.json.

Запускается в CI перед сборкой:

    python tools/generate_version.py --version 1.4.0 --build 42 --date 2025-01-31

Значения BUILD_NUMBER и BUILD_DATE подставляются из переменных окружения
GITHUB_RUN_NUMBER / текущей даты, чтобы в окне «О программе» была видна
конкретная сборка.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"
PY_VERSION_FILE = ROOT / "src" / "devops_academy" / "version.py"
INDEX_FILE = ROOT / "content" / "content_index.json"

TEMPLATE = '''"""Сгенерировано tools/generate_version.py — правки будут перезаписаны."""

APP_NAME = "DevOps Academy"
APP_ID = "DevOpsAcademy"
APP_VERSION = "{version}"
BUILD_NUMBER = "{build}"
BUILD_DATE = "{date}"
GITHUB_REPO = "{repo}"
GITHUB_RELEASES_URL = f"https://github.com/{{GITHUB_REPO}}/releases"
RELEASES_API_URL = f"https://api.github.com/repos/{{GITHUB_REPO}}/releases/latest"


def version_tuple(value: str) -> tuple:
    """Преобразует строку версии в кортеж чисел для сравнения."""
    parts = []
    for chunk in str(value).strip().lstrip("vV").split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:4])


def is_newer(candidate: str, current: str) -> bool:
    """True, если candidate новее current."""
    return version_tuple(candidate) > version_tuple(current)
'''

VERSION_ALIAS = '''

# Обратная совместимость с ранними сборками, где версия называлась __version__.
__version__ = APP_VERSION
'''


def normalize_bytes(data: bytes) -> bytes:
    """Содержимое без привязки к переводам строк.

    Хеши контента считаются от LF-версии, поэтому индекс, собранный на Linux,
    совпадает с проверками на Windows (где git может выложить файлы с CRLF).
    """
    return data.replace(b"\r\n", b"\n")


def file_digest(path: Path) -> tuple[str, int]:
    """Возвращает (короткий sha256, размер нормализованного содержимого)."""
    data = normalize_bytes(path.read_bytes())
    return hashlib.sha256(data).hexdigest()[:16], len(data)


def build_content_index() -> dict:
    """Хеши файлов контента — для проверки целостности и диагностики сборки."""
    content_dir = ROOT / "content"
    files: dict[str, str] = {}
    total_bytes = 0
    for path in sorted(content_dir.rglob("*")):
        if not path.is_file() or path.name == "content_index.json":
            continue
        digest, size = file_digest(path)
        total_bytes += size
        files[str(path.relative_to(content_dir)).replace("\\", "/")] = digest
    generated = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    if INDEX_FILE.exists():
        try:
            previous = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
            content_unchanged = (
                previous.get("files") == len(files)
                and previous.get("total_bytes") == total_bytes
                and previous.get("hashes") == files
            )
            if content_unchanged and isinstance(previous.get("generated"), str):
                generated = previous["generated"]
        except (OSError, TypeError, ValueError):
            pass
    return {
        "generated": generated,
        "files": len(files),
        "total_bytes": total_bytes,
        "hashes": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Обновить version.py и content_index.json")
    parser.add_argument("--version", default="", help="версия (по умолчанию из файла VERSION)")
    parser.add_argument("--build", default="local", help="номер сборки")
    parser.add_argument("--date", default="", help="дата сборки (ISO)")
    parser.add_argument("--repo", default="ignatus4405-glitch/DevOps_guide-", help="owner/repo")
    args = parser.parse_args()

    version = args.version.strip() or VERSION_FILE.read_text(encoding="utf-8").strip()
    version = version.lstrip("vV")
    build = args.build.strip() or "local"
    date = args.date.strip() or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")

    PY_VERSION_FILE.write_text(
        TEMPLATE.format(version=version, build=build, date=date, repo=args.repo) + VERSION_ALIAS,
        encoding="utf-8",
    )
    VERSION_FILE.write_text(f"{version}\n", encoding="utf-8")

    index = build_content_index()
    INDEX_FILE.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"версия: {version} (build {build}, {date})")
    print(f"файлов контента: {index['files']}, суммарно {index['total_bytes'] / 1024:.1f} КиБ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
