"""Тесты инструментов версии: индекс контента не зависит от переводов строк."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_tool(name: str):
    """Загружает модуль из tools/ (там нет пакета — импортируем по пути)."""
    path = ROOT / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"tool_{name}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def generate_version():
    return _load_tool("generate_version")


def test_digest_is_line_ending_independent(generate_version, tmp_path):
    """Хеш файла с CRLF совпадает с хешем того же файла с LF (важно для Windows)."""
    lf_file = tmp_path / "sample.md"
    crlf_file = tmp_path / "sample_crlf.md"
    lf_file.write_bytes("# Заголовок\n\nстрока\n".encode() * 5)
    crlf_file.write_bytes(lf_file.read_bytes().replace(b"\n", b"\r\n"))

    assert generate_version.file_digest(lf_file) == generate_version.file_digest(crlf_file)


def test_normalize_bytes_keeps_lone_lf(generate_version):
    data = b"a\nb\n"
    assert generate_version.normalize_bytes(data) == data
    assert generate_version.normalize_bytes(b"a\r\nb\r\n") == b"a\nb\n"


def test_content_index_matches_disk(generate_version):
    """Индекс, посчитанный заново, совпадает с закоммиченным content_index.json."""
    import json

    index_file = ROOT / "content" / "content_index.json"
    stored = json.loads(index_file.read_text(encoding="utf-8"))
    fresh = generate_version.build_content_index()

    assert fresh["files"] == stored["files"], "число файлов в индексе расходится"
    assert fresh["hashes"] == stored["hashes"], "индекс устарел — запустите tools/generate_version.py"


def test_version_module_is_generated(generate_version):
    """version.py содержит сгенерированные константы, версия совпадает с VERSION."""
    version_py = ROOT / "src" / "devops_academy" / "version.py"
    text = version_py.read_text(encoding="utf-8")
    assert "Сгенерировано tools/generate_version.py" in text
    declared = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert f'APP_VERSION = "{declared}"' in text
