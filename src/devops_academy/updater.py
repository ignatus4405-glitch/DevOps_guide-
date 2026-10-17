"""Проверка и установка обновлений через GitHub Releases.

Как это работает
----------------
1. При каждом запуске приложение запрашивает последний релиз репозитория в фоне
   через публичный GitHub API — токен не нужен, репозиторий публичный.
2. Если версия тега новее текущей APP_VERSION, приложение спрашивает пользователя
   об установке обновления и показывает описание изменений (release notes).
3. Пользователь может скачать установщик прямо из приложения: файл проверяется по
   SHA-256 из ассета ``SHA256SUMS.txt``, затем запускается тихая установка
   (Inno Setup ``/VERYSILENT``), а приложение закрывается.
4. Если установщика нет (например, портативная сборка), клиент скачивает ZIP и
   распаковывает его в %LOCALAPPDATA%.DevOpsAcademy/updates и предлагает
   обновить файлы скриптом замены после выхода.

Все сетевые ошибки глушатся: офлайн-режим не должен мешать учёбе.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import requests
from PySide6.QtCore import QObject, QThread, Signal

from .paths import user_data_dir
from .version import GITHUB_REPO, RELEASES_API_URL, is_newer

REQUEST_TIMEOUT = 10
USER_AGENT = "DevOpsAcademy-Updater"


@dataclass
class ReleaseAsset:
    name: str
    url: str
    size: int = 0


@dataclass
class UpdateInfo:
    version: str
    tag: str
    title: str
    notes: str
    published_at: str
    html_url: str
    assets: list[ReleaseAsset] = field(default_factory=list)

    def asset(self, pattern: str) -> ReleaseAsset | None:
        regex = re.compile(pattern, re.IGNORECASE)
        for item in self.assets:
            if regex.search(item.name):
                return item
        return None

    def manifest_asset(self) -> ReleaseAsset | None:
        return self.asset(r"SHA256SUMS.*\.txt$")

    def installer_asset(self) -> ReleaseAsset | None:
        if sys.platform.startswith("win"):
            return self.asset(r"Setup[-_.].*\.exe$") or self.asset(r".*-Setup.*\.exe$")
        return None

    def archive_asset(self) -> ReleaseAsset | None:
        if sys.platform.startswith("win"):
            return self.asset(r"windows.*\.zip$") or self.asset(r".*Windows.*\.zip$")
        return self.asset(r".*(Linux|AppImage).*\.(zip|tar\.gz|AppImage)$")


def fetch_latest_release(include_prerelease: bool = False) -> UpdateInfo | None:
    """Возвращает последний релиз или None, если релизов ещё нет/нет сети."""
    url = RELEASES_API_URL
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if response.status_code == 403 and include_prerelease:
            return None
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return None
    return _to_update_info(data)


def _to_update_info(data: dict) -> UpdateInfo:
    assets = [
        ReleaseAsset(name=item.get("name", ""), url=item.get("browser_download_url", ""), size=item.get("size", 0))
        for item in data.get("assets", [])
    ]
    return UpdateInfo(
        version=str(data.get("tag_name", "")).lstrip("vV"),
        tag=str(data.get("tag_name", "")),
        title=str(data.get("name") or data.get("tag_name", "")),
        notes=str(data.get("body") or ""),
        published_at=str(data.get("published_at", "")),
        html_url=str(data.get("html_url", "")),
        assets=assets,
    )


def check_for_update(current_version: str, include_prerelease: bool = False) -> UpdateInfo | None:
    """Возвращает UpdateInfo, если есть версия новее текущей."""
    info = fetch_latest_release(include_prerelease)
    if info and info.version and is_newer(info.version, current_version):
        return info
    return None


class UpdateChecker(QThread):
    """Фоновая проверка обновлений, чтобы не блокировать интерфейс."""

    found = Signal(object)
    checked = Signal(object)  # None, если обновлений нет
    failed = Signal(str)

    def __init__(self, current_version: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.current_version = current_version

    def run(self) -> None:  # pragma: no cover - сетевой код
        info = fetch_latest_release()
        if info is None:
            self.failed.emit("Не удалось получить данные о релизах GitHub")
            return
        if info.version and is_newer(info.version, self.current_version):
            self.found.emit(info)
        else:
            self.checked.emit(None)


class DownloadWorker(QThread):
    """Скачивание файла обновления с проверкой SHA-256."""

    progress = Signal(int)
    finished_file = Signal(str)
    failed = Signal(str)

    def __init__(self, info: UpdateInfo, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.info = info

    def run(self) -> None:  # pragma: no cover - сетевой код
        try:
            asset = self.info.installer_asset() or self.info.archive_asset()
            if asset is None:
                self.failed.emit("В релизе нет подходящего файла для этой платформы")
                return
            target_dir = user_data_dir() / "updates"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / asset.name
            expected = self._expected_hash(asset.name)
            digest = hashlib.sha256()
            with requests.get(
                asset.url, stream=True, timeout=REQUEST_TIMEOUT * 6, headers={"User-Agent": USER_AGENT}
            ) as response:
                response.raise_for_status()
                total = int(response.headers.get("Content-Length", 0)) or asset.size or 1
                done = 0
                with open(target, "wb") as handle:
                    for chunk in response.iter_content(chunk_size=262_144):
                        handle.write(chunk)
                        digest.update(chunk)
                        done += len(chunk)
                        self.progress.emit(min(100, int(done * 100 / total)))
            if expected and digest.hexdigest().lower() != expected.lower():
                target.unlink(missing_ok=True)
                self.failed.emit("Контрольная сумма не совпала — загрузка отменена")
                return
            self.finished_file.emit(str(target))
        except (requests.RequestException, OSError) as error:  # pragma: no cover
            self.failed.emit(f"Ошибка загрузки: {error}")

    def _expected_hash(self, filename: str) -> str:
        manifest = self.info.manifest_asset()
        if manifest is None:
            return ""
        try:
            text = requests.get(
                manifest.url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT}
            ).text
        except requests.RequestException:
            return ""
        for line in text.splitlines():
            parts = line.split()
            if len(parts) >= 2 and Path(parts[-1].lstrip("*")).name == Path(filename).name:
                return parts[0]
        return ""


def install_update(path: str) -> tuple[bool, str]:
    """Запускает установку скачанного файла. Возвращает (успех, сообщение)."""
    target = Path(path)
    if not target.exists():
        return False, "Файл обновления не найден"
    try:
        if target.suffix.lower() == ".exe" and sys.platform.startswith("win"):
            subprocess.Popen(  # noqa: S603,S607 - запускаем только проверенный установщик
                [str(target), "/SILENT", "/SUPPRESSMSGBOXES", "/NOCANCEL", "/RESTARTAPPLICATIONS"],
                close_fds=True,
            )
            return True, "Установщик запущен — приложение сейчас закроется"
        return True, f"Файл обновления сохранён: {target}"
    except OSError as error:  # pragma: no cover
        return False, f"Не удалось запустить установку: {error}"


def should_check(store, min_interval_hours: int = 24, *, on_startup: bool = False) -> bool:
    """Разрешает автопроверку, не чаще интервала, кроме проверки при запуске."""
    if str(store.get("updates/auto_check", "true")).lower() not in ("true", "1"):
        return False
    if on_startup:
        return True
    last = str(store.get("updates/last_check", ""))
    if not last:
        return True
    try:
        moment = datetime.fromisoformat(last)
    except ValueError:
        return True
    delta = datetime.now(timezone.utc) - moment
    return delta.total_seconds() >= min_interval_hours * 3600


def mark_checked(store) -> None:
    store.set("updates/last_check", datetime.now(timezone.utc).isoformat(timespec="seconds"))


def skipped_version(store) -> str:
    return str(store.get("updates/skipped_version", ""))


def skip_version(store, version: str) -> None:
    store.set("updates/skipped_version", version)


def snooze(store) -> None:
    """«Напомнить позже» — сбрасываем время проверки на сейчас."""
    store.set("updates/last_check", datetime.now(timezone.utc).isoformat(timespec="seconds"))


def release_notes_markdown(info: UpdateInfo) -> str:
    """Release notes -> markdown для отображения в диалоге."""
    published = info.published_at[:10] if info.published_at else "—"
    assets = "\n".join(
        f"- `{a.name}` ({a.size / 1048576:.1f} МБ)" for a in info.assets if a.size
    ) or "- файлы появятся после завершения сборки"
    return (
        f"# {info.title or info.tag}\n\n"
        f"**Версия:** {info.version}  |  **Опубликовано:** {published}\n\n"
        f"[Страница релиза на GitHub]({info.html_url})\n\n"
        f"## Что нового\n\n{info.notes or '_Описание не заполнено_'}\n\n"
        f"## Файлы релиза\n\n{assets}\n"
    )


def update_script_path() -> Path:
    return tempfile.gettempdir() / "devops_academy_update.txt"


def current_platform_key() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def repo_slug() -> str:
    return GITHUB_REPO


def env_proxy_note() -> str:  # pragma: no cover - диагностика
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    return f"HTTPS_PROXY={proxy}" if proxy else "прокси не задан"
