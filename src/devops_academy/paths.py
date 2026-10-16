"""Пути к ресурсам: работают и из исходников, и из собранного .exe."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    """Корень приложения (папка с exe для сборки PyInstaller или корень репо)."""
    if _frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


def resource_path(*parts: str) -> Path:
    """Путь к ресурсу внутри поставки (только чтение)."""
    return app_root().joinpath(*parts)


def content_dir() -> Path:
    return resource_path("content")


def user_data_dir() -> Path:
    """Каталог для пользовательских данных (прогресс, кэш обновлений)."""
    if _frozen():
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
        path = Path(base) / "DevOpsAcademy"
    else:
        path = Path.home() / ".devops_academy"
    path.mkdir(parents=True, exist_ok=True)
    return path


def bundle_manifest_path() -> Path:
    return resource_path("content", "content_index.json")
