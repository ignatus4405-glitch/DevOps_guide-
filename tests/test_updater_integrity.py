"""Безопасная загрузка релизов: обязательный digest и атомарная публикация."""

from __future__ import annotations

import hashlib
from pathlib import Path

import requests

import devops_academy.updater as updater
from devops_academy.updater import DownloadWorker, ReleaseAsset, UpdateInfo


class FakeResponse:
    def __init__(self, *, text: str = "", payload: bytes = b"") -> None:
        self.text = text
        self.payload = payload
        self.headers = {"Content-Length": str(len(payload))}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size: int):
        for offset in range(0, len(self.payload), max(1, chunk_size // 4)):
            yield self.payload[offset : offset + max(1, chunk_size // 4)]


def make_info(*, manifest_url: str = "https://releases.example/SHA256SUMS.txt") -> UpdateInfo:
    return UpdateInfo(
        version="0.7.0",
        tag="v0.7.0",
        title="DevOps Academy 0.7.0",
        notes="",
        published_at="",
        html_url="https://example/releases/v0.7.0",
        assets=[
            ReleaseAsset("DevOpsAcademy-0.7.0-linux-x64.tar.gz", "https://releases.example/course.tar.gz", 100),
            ReleaseAsset("SHA256SUMS.txt", manifest_url, 200),
        ],
    )


def prepare_platform(monkeypatch, tmp_path):
    monkeypatch.setattr(updater.sys, "platform", "linux")
    monkeypatch.setattr(updater.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(updater, "user_data_dir", lambda: tmp_path)


def run_worker(monkeypatch, tmp_path, info, manifest_response, download_response):
    prepare_platform(monkeypatch, tmp_path)
    worker = DownloadWorker(info)
    successes: list[str] = []
    failures: list[str] = []
    worker.finished_file.connect(successes.append)
    worker.failed.connect(failures.append)
    responses = {info.manifest_asset().url: manifest_response}
    if download_response is not None:
        responses[info.archive_asset().url] = download_response

    def fake_get(url, **kwargs):
        value = responses[url]
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(updater.requests, "get", fake_get)
    worker.run()
    return worker, successes, failures


def test_download_requires_matching_sha256_and_publishes_atomically(tmp_path, monkeypatch):
    prepare_platform(monkeypatch, tmp_path)
    payload = b"verified release contents\n"
    digest = hashlib.sha256(payload).hexdigest()
    info = make_info()
    manifest = FakeResponse(text=f"{digest}  {info.archive_asset().name}\n")
    _, successes, failures = run_worker(monkeypatch, tmp_path, info, manifest, FakeResponse(payload=payload))

    target = tmp_path / "updates" / info.archive_asset().name
    assert failures == []
    assert successes == [str(target)]
    assert target.read_bytes() == payload
    assert not target.with_name(target.name + ".part").exists()


def test_missing_manifest_fails_closed_without_creating_target(tmp_path, monkeypatch):
    prepare_platform(monkeypatch, tmp_path)
    info = make_info()
    info.assets = [info.archive_asset()]
    worker = DownloadWorker(info)
    failures: list[str] = []
    worker.failed.connect(failures.append)
    worker.run()
    assert failures and "SHA256SUMS.txt" in failures[0]
    assert not (tmp_path / "updates").exists()


def test_unavailable_manifest_fails_closed(tmp_path, monkeypatch):
    info = make_info()
    _, successes, failures = run_worker(
        monkeypatch,
        tmp_path,
        info,
        requests.Timeout("manifest timeout"),
        FakeResponse(payload=b"not installed"),
    )
    assert not successes
    assert failures and "Не удалось получить SHA256SUMS.txt" in failures[0]
    if (tmp_path / "updates").exists():
        assert not list((tmp_path / "updates").glob("*.part"))


def test_malformed_or_missing_entry_fails_closed_and_preserves_old_file(tmp_path, monkeypatch):
    prepare_platform(monkeypatch, tmp_path)
    info = make_info()
    target_dir = tmp_path / "updates"
    target_dir.mkdir()
    target = target_dir / info.archive_asset().name
    target.write_bytes(b"previous valid download")
    _, successes, failures = run_worker(
        monkeypatch,
        tmp_path,
        info,
        FakeResponse(text="not a sha256 manifest\n"),
        FakeResponse(payload=b"new unverified bytes"),
    )
    assert not successes
    assert failures and "нет корректной SHA-256 записи" in failures[0]
    assert target.read_bytes() == b"previous valid download"
    assert not target.with_name(target.name + ".part").exists()


def test_digest_mismatch_discards_part_and_preserves_existing_target(tmp_path, monkeypatch):
    prepare_platform(monkeypatch, tmp_path)
    info = make_info()
    target_dir = tmp_path / "updates"
    target_dir.mkdir()
    target = target_dir / info.archive_asset().name
    target.write_bytes(b"keep this old file")
    payload = b"tampered download"
    wrong_digest = hashlib.sha256(b"different bytes").hexdigest()
    _, successes, failures = run_worker(
        monkeypatch,
        tmp_path,
        info,
        FakeResponse(text=f"{wrong_digest}  {info.archive_asset().name}\n"),
        FakeResponse(payload=payload),
    )
    assert not successes
    assert failures and "не совпала" in failures[0]
    assert target.read_bytes() == b"keep this old file"
    assert not target.with_name(target.name + ".part").exists()


def test_sha256_manifest_requires_hex_digest_and_exact_filename(tmp_path, monkeypatch):
    prepare_platform(monkeypatch, tmp_path)
    info = make_info()
    payload = b"release"
    valid = hashlib.sha256(payload).hexdigest()
    _, successes, failures = run_worker(
        monkeypatch,
        tmp_path,
        info,
        FakeResponse(text=f"{valid[:63]}  other-{info.archive_asset().name}\n"),
        FakeResponse(payload=payload),
    )
    assert not successes
    assert failures and "нет корректной SHA-256 записи" in failures[0]


def test_platform_assets_are_os_and_architecture_gated(monkeypatch):
    info = make_info()
    info.assets.extend(
        [
            ReleaseAsset("DevOpsAcademy-Setup-0.7.0.exe", "https://releases.example/setup.exe"),
            ReleaseAsset("DevOpsAcademy-0.7.0-windows-x64.zip", "https://releases.example/windows.zip"),
        ]
    )
    monkeypatch.setattr(updater.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(updater.sys, "platform", "linux")
    assert info.installer_asset() is None
    assert info.archive_asset().name.endswith("linux-x64.tar.gz")

    monkeypatch.setattr(updater.sys, "platform", "win32")
    monkeypatch.setattr(updater.platform, "machine", lambda: "AMD64")
    assert info.installer_asset().name.endswith("Setup-0.7.0.exe")
    assert info.archive_asset().name.endswith("windows-x64.zip")

    monkeypatch.setattr(updater.sys, "platform", "darwin")
    assert info.installer_asset() is None
    assert info.archive_asset() is None

    monkeypatch.setattr(updater.sys, "platform", "linux")
    monkeypatch.setattr(updater.platform, "machine", lambda: "aarch64")
    assert info.archive_asset() is None


def test_linux_archive_is_not_reported_as_installed(tmp_path, monkeypatch):
    monkeypatch.setattr(updater.sys, "platform", "linux")
    monkeypatch.setattr(updater.platform, "machine", lambda: "x86_64")
    archive = tmp_path / "DevOpsAcademy-0.7.0-linux-x64.tar.gz"
    archive.write_bytes(b"verified test artifact")
    success, message = updater.install_update(str(archive))
    assert not success
    assert "Автоматическая установка" in message
    assert "скачан" in message


def test_windows_update_launches_installer_and_reports_relaunch(tmp_path, monkeypatch):
    installer = tmp_path / "DevOpsAcademy-Setup-0.7.1.exe"
    installer.write_bytes(b"verified installer")
    monkeypatch.setattr(updater.sys, "platform", "win32")
    monkeypatch.setattr(updater, "_is_x64_host", lambda: True)
    launched = {}

    def fake_popen(command, **kwargs):
        launched["command"] = command
        launched["kwargs"] = kwargs

    monkeypatch.setattr(updater.subprocess, "Popen", fake_popen)
    success, message = updater.install_update(str(installer))

    assert success
    assert launched["command"] == [
        str(installer),
        "/SILENT",
        "/SUPPRESSMSGBOXES",
        "/NOCANCEL",
        "/RESTARTAPPLICATIONS",
    ]
    assert launched["kwargs"] == {"close_fds": True}
    assert "откроется после установки" in message


def test_inno_installer_runs_app_after_silent_update():
    installer_script = Path(__file__).resolve().parents[1] / "packaging" / "installer.iss"
    script = installer_script.read_text(encoding="utf-8")
    run_section = script.split("[Run]", 1)[1].split("[UninstallDelete]", 1)[0]
    run_entry = next(line for line in run_section.splitlines() if line.strip().startswith("Filename:"))
    assert "postinstall" in run_entry
    assert "skipifsilent" not in run_entry.casefold()
