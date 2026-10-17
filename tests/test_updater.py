"""Логика обновлений: сравнение версий, разбор релиза, плановые проверки."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from PySide6.QtCore import QSettings

from devops_academy.progress import ProgressStore
from devops_academy.updater import (
    ReleaseAsset,
    UpdateInfo,
    _to_update_info,
    check_for_update,
    mark_checked,
    release_notes_markdown,
    should_check,
    skip_version,
    skipped_version,
    snooze,
)
from devops_academy.version import is_newer, version_tuple


def test_version_tuple_parsing():
    assert version_tuple("1.4.2") == (1, 4, 2)
    assert version_tuple("v0.10.0") == (0, 10, 0)
    assert version_tuple("1.0") == (1, 0, 0)
    assert version_tuple("мусор") == (0, 0, 0)


def test_is_newer_semantics():
    assert is_newer("1.0.1", "1.0.0")
    assert is_newer("1.10.0", "1.9.9")
    assert not is_newer("1.0.0", "1.0.0")
    assert not is_newer("0.9.0", "1.0.0")


def test_release_info_from_github_payload():
    payload = {
        "tag_name": "v1.2.0",
        "name": "DevOps Academy 1.2.0",
        "body": "## Что нового\n- Новый модуль",
        "published_at": "2025-01-31T10:00:00Z",
        "html_url": "https://github.com/org/repo/releases/tag/v1.2.0",
        "assets": [
            {"name": "DevOpsAcademy-1.2.0-Setup.exe", "browser_download_url": "https://x/installer.exe", "size": 1048576},
            {"name": "SHA256SUMS.txt", "browser_download_url": "https://x/SHA256SUMS.txt", "size": 200},
            {"name": "DevOpsAcademy-1.2.0-windows.zip", "browser_download_url": "https://x/win.zip", "size": 2097152},
        ],
    }
    info = _to_update_info(payload)
    assert info.version == "1.2.0"
    assert info.tag == "v1.2.0"
    assert info.asset(r"SHA256SUMS") is not None
    assert is_newer(info.version, "1.1.0")
    notes = release_notes_markdown(info)
    assert "Что нового" in notes and "SHA256SUMS.txt" in notes


def test_asset_lookup_helpers():
    info = UpdateInfo(
        version="2.0.0",
        tag="v2.0.0",
        title="t",
        notes="n",
        published_at="",
        html_url="",
        assets=[
            ReleaseAsset("App-2.0.0-Setup.exe", "https://x/a.exe", 10),
            ReleaseAsset("App-windows.zip", "https://x/w.zip", 20),
            ReleaseAsset("SHA256SUMS.txt", "https://x/s.txt", 30),
        ],
    )
    assert info.manifest_asset().name == "SHA256SUMS.txt"
    assert info.asset(r"^$") is None


def test_check_for_update_uses_network(monkeypatch):
    payload = _to_update_info({"tag_name": "v9.9.9", "name": "", "body": "", "assets": []})
    monkeypatch.setattr("devops_academy.updater.fetch_latest_release", lambda *a, **k: payload)
    assert check_for_update("0.1.0").version == "9.9.9"
    assert check_for_update("10.0.0") is None


def test_check_for_update_handles_no_releases(monkeypatch):
    monkeypatch.setattr("devops_academy.updater.fetch_latest_release", lambda *a, **k: None)
    assert check_for_update("0.1.0") is None


def make_store(tmp_path) -> ProgressStore:
    return ProgressStore(QSettings(str(tmp_path / "u.ini"), QSettings.IniFormat))


def test_should_check_respects_interval(tmp_path):
    store = make_store(tmp_path)
    assert should_check(store) is True
    mark_checked(store)
    assert should_check(store) is False
    # имитируем старую проверку (25 часов назад)
    old = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(timespec="seconds")
    store.set("updates/last_check", old)
    assert should_check(store) is True


def test_auto_check_can_be_disabled(tmp_path):
    store = make_store(tmp_path)
    store.set("updates/auto_check", "false")
    assert should_check(store) is False


def test_startup_check_ignores_daily_interval_but_respects_setting(tmp_path):
    store = make_store(tmp_path)
    mark_checked(store)
    assert should_check(store) is False
    assert should_check(store, on_startup=True) is True

    store.set("updates/auto_check", "false")
    assert should_check(store, on_startup=True) is False


def test_skip_version_and_snooze(tmp_path):
    store = make_store(tmp_path)
    skip_version(store, "1.5.0")
    assert skipped_version(store) == "1.5.0"
    snooze(store)
    assert should_check(store) is False
