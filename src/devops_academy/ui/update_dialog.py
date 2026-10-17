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

        self.install_button = QPushButton("⬇ Скачать и установить", self)
        self.install_button.setObjectName("Primary")
        self.install_button.clicked.connect(self._download)
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
        self.install_button.setEnabled(False)
        self.progress.setVisible(True)
        self.status.setText("Скачиваем обновление…")
        self.worker = DownloadWorker(self.info, self)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.finished_file.connect(self._downloaded)
        self.worker.failed.connect(self._failed)
        self.worker.start()

    def _downloaded(self, path: str) -> None:
        self.status.setText("Файл получен, проверяем контрольную сумму и запускаем установку…")
        ok, message = install_update(path)
        self.status.setText(("✅ " if ok else "❌ ") + message)
        if ok:
            self.installer_started = self.info.installer_asset() is not None
            self.accept()

    def _failed(self, message: str) -> None:
        self.install_button.setEnabled(True)
        self.progress.setVisible(False)
        self.status.setText(f"❌ {message}. Скачайте установщик со страницы релиза.")
