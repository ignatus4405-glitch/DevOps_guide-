"""Сгенерировано tools/generate_version.py — правки будут перезаписаны."""

APP_NAME = "DevOps Academy"
APP_ID = "DevOpsAcademy"
APP_VERSION = "0.7.0"
BUILD_NUMBER = "15"
BUILD_DATE = "2026-10-18"
GITHUB_REPO = "ignatus4405-glitch/DevOps_guide-"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases"
RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


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


# Обратная совместимость с ранними сборками, где версия называлась __version__.
__version__ = APP_VERSION
