#!/usr/bin/env python3
"""Собирает release/update.json — манифест обновления для клиента.

Приложение читает этот файл (или GitHub Releases API) и показывает баннер
«Доступна новая версия». Формат держим простым и стабильным:

{
  "version": "0.2.0",
  "tag": "v0.2.0",
  "channel": "stable",
  "released_at": "2026-01-31T10:00:00+00:00",
  "assets": ["DevOpsAcademy-Setup-0.2.0.exe", ...],
  "notes_url": "https://github.com/<owner>/<repo>/releases/tag/v0.2.0",
  "installer": "DevOpsAcademy-Setup-0.2.0.exe",
  "sha256_url": "https://github.com/<owner>/<repo>/releases/download/v0.2.0/SHA256SUMS.txt",
  "min_supported": "0.1.0"
}

Использование:  python tools/make_update_manifest.py --version 0.2.0 --repo owner/name --dir release
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

MIN_SUPPORTED = "0.1.0"


def build_manifest(version: str, repo: str, tag: str, files: list[str], channel: str = "stable") -> dict:
    """Формирует словарь манифеста обновления."""
    base = f"https://github.com/{repo}/releases/download/{tag}"
    installer = next((name for name in files if "Setup" in name and name.endswith(".exe")), "")
    portable = next((name for name in files if name.endswith(".zip")), "")
    return {
        "version": version,
        "tag": tag,
        "channel": channel,
        "released_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "assets": sorted(files),
        "notes_url": f"https://github.com/{repo}/releases/tag/{tag}",
        "installer": installer,
        "installer_url": f"{base}/{installer}" if installer else "",
        "portable": portable,
        "sha256_url": f"{base}/SHA256SUMS.txt",
        "min_supported": MIN_SUPPORTED,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Сборка update.json для релиза")
    parser.add_argument("--version", required=True)
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument("--dir", default="release", help="каталог с файлами релиза")
    parser.add_argument("--channel", default="stable")
    args = parser.parse_args(argv)

    directory = Path(args.dir)
    directory.mkdir(parents=True, exist_ok=True)
    tag = f"v{args.version}"
    files = [
        path.name
        for path in sorted(directory.iterdir())
        if path.is_file() and path.name not in {"update.json", "SHA256SUMS.txt", "RELEASE_NOTES.md"}
    ]
    manifest = build_manifest(args.version, args.repo, tag, files, args.channel)
    target = directory / "update.json"
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"update.json: версия {manifest['version']}, файлов {len(manifest['assets'])}")
    for name in manifest["assets"]:
        print(f"  - {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
