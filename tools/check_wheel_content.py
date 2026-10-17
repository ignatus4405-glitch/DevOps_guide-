#!/usr/bin/env python3
"""Проверяет, что wheel содержит весь курс и согласованную версию."""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from email.parser import Parser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check_wheel(wheel_path: Path) -> None:
    expected_version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    runtime_version = (ROOT / "src/devops_academy/version.py").read_text(encoding="utf-8")
    match = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', runtime_version, re.MULTILINE)
    if match is None or match.group(1) != expected_version:
        raise ValueError("VERSION и src/devops_academy/version.py расходятся")

    with zipfile.ZipFile(wheel_path) as wheel:
        names = set(wheel.namelist())
        metadata_name = next((name for name in names if name.endswith(".dist-info/METADATA")), None)
        if metadata_name is None:
            raise ValueError("в wheel отсутствует .dist-info/METADATA")
        metadata = Parser().parsestr(wheel.read(metadata_name).decode("utf-8"))
        if metadata.get("Version") != expected_version:
            raise ValueError(f"версия wheel {metadata.get('Version')!r} != VERSION {expected_version!r}")

        expected_files = {
            f"devops_academy/content/{path.relative_to(ROOT / 'content').as_posix()}"
            for path in (ROOT / "content").rglob("*")
            if path.is_file()
        }
        missing = sorted(expected_files - names)
        if missing:
            raise ValueError("wheel не содержит файлы курса:\n  " + "\n  ".join(missing[:30]))

    print(f"wheel OK: {wheel_path.name}, version {expected_version}, {len(expected_files)} content files")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args(argv)
    try:
        check_wheel(args.wheel)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print(f"wheel check FAILED: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
