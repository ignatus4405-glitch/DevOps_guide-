"""Уведомление о новой версии: описание релиза, загрузка и установка."""

from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..markdown_renderer import render_plain
from ..theme import lesson_css
from ..updater import DownloadWorker, UpdateInfo, install_update, release_notes_markdown


class UpdateDialog(QDialog):
    """Диалог обновления. Умеет: скачать, установить, отложить, пропустить версию."""

    def __init__(self, info: UpdateInfo, theme: str = "dark", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.info = info
        self.theme = theme
        self.worker: DownloadWorker | None = None
        self.snoozed = False
        self.skipped = False
        self.installer_started = False
        self._close_when_worker_stops = False
        self._download_path: str | None = None
        self._download_error: str | None = None

        self.setWindowTitle(f"Доступна новая версия {info.version}")
        self.resize(760, 600)

        title = QLabel(f"🚀 Вышла новая версия {info.version}")
        title.setObjectName("Title")
        subtitle = QLabel(f"Хотите установить обновление? Тег релиза: {info.tag}")
        subtitle.setObjectName("Subtitle")

        self.notes = QTextBrowser(self)
        self.notes.setObjectName("Lesson")
        self.notes.setHtml(render_plain(release_notes_markdown(info), theme))
        self.notes.setStyleSheet(lesson_css(theme))

        self.progress = QProgressBar(self)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)

        self.status = QLabel("", self)
        self.status.setObjectName("Subtitle")

        if info.installer_asset() is not None:
            install_label = "⬇ Скачать и установить"
        elif info.archive_asset() is not None:
            install_label = "⬇ Скачать архив (установка вручную)"
        else:
            install_label = "Нет сборки для этой платформы"
        self.install_button = QPushButton(install_label, self)
        self.install_button.setObjectName("Primary")
        self.install_button.setEnabled(info.installer_asset() is not None or info.archive_asset() is not None)
        self.install_button.clicked.connect(self._download)
        if not self.install_button.isEnabled():
            self.status.setText("Автоматическая установка для этой ОС/архитектуры не поддерживается. Откройте страницу релиза.")
        self.page_button = QPushButton("Открыть страницу релиза", self)
        self.page_button.clicked.connect(self._open_page)
        self.later_button = QPushButton("Позже", self)
        self.later_button.clicked.connect(self._later)
        self.skip_button = QPushButton("Пропустить эту версию", self)
        self.skip_button.clicked.connect(self._skip)

        buttons = QHBoxLayout()
        buttons.addWidget(self.install_button)
        buttons.addWidget(self.page_button)
        buttons.addStretch(1)
        buttons.addWidget(self.skip_button)
        buttons.addWidget(self.later_button)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.notes, 1)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        layout.addLayout(buttons)

    # ------------------------------------------------------------------
    def _open_page(self) -> None:
        if self.info.html_url:
            QDesktopServices.openUrl(QUrl(self.info.html_url))

    def _later(self) -> None:
        self.snoozed = True
        self.accept()

    def _skip(self) -> None:
        self.skipped = True
        self.accept()

    def _download(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        self.install_button.setEnabled(False)
        self.later_button.setEnabled(False)
        self.skip_button.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self._download_path = None
        self._download_error = None
        self.status.setText("Скачиваем обновление и проверяем обязательную SHA-256-сумму…")
        self.worker = DownloadWorker(self.info, self)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.finished_file.connect(self._downloaded)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()

    def _downloaded(self, path: str) -> None:
        # Сигнал приходит до QThread.finished: не закрываем диалог, пока поток жив.
        self._download_path = path

    def _failed(self, message: str) -> None:
        self._download_error = message

    def _worker_finished(self) -> None:
        if self._close_when_worker_stops:
            self._close_when_worker_stops = False
            self.reject()
            return
        if self._download_error:
            self.install_button.setEnabled(True)
            self.later_button.setEnabled(True)
            self.skip_button.setEnabled(True)
            self.progress.setVisible(False)
            self.status.setText(f"❌ {self._download_error}. Проверьте страницу релиза.")
            return
        if not self._download_path:
            return

        ok, message = install_update(self._download_path)
        if ok:
            self.status.setText("✅ " + message)
            self.installer_started = True
            self.accept()
            return
        if message.startswith("Архив скачан:"):
            self.status.setText("ℹ️ " + message)
            self.install_button.setText("Архив сохранён")
            self.progress.setVisible(False)
            self.later_button.setEnabled(True)
            self.skip_button.setEnabled(True)
            return
        self.status.setText("❌ " + message)
        self.install_button.setEnabled(True)
        self.later_button.setEnabled(True)
        self.skip_button.setEnabled(True)
        self.progress.setVisible(False)

    def _defer_close_for_worker(self) -> bool:
        if self.worker is None or not self.worker.isRunning():
            return False
        self._close_when_worker_stops = True
        self.worker.requestInterruption()
        self.install_button.setEnabled(False)
        self.later_button.setEnabled(False)
        self.skip_button.setEnabled(False)
        self.status.setText("Останавливаем загрузку перед закрытием…")
        return True

    def reject(self) -> None:
        # Escape вызывает reject(), минуя closeEvent; тоже безопасно ждём QThread.
        if self._defer_close_for_worker():
            return
        super().reject()

    def accept(self) -> None:
        # Защита от закрытия диалога кнопкой/внешним вызовом во время загрузки.
        if self.worker is not None and self.worker.isRunning():
            return
        super().accept()

    def closeEvent(self, event) -> None:  # noqa: N802 - API Qt
        if self._defer_close_for_worker():
            event.ignore()
            return
        super().closeEvent(event)
