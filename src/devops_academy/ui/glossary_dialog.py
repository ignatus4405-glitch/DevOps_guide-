"""Окно глоссария: поиск по терминам курса."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


class GlossaryDialog(QDialog):
    def __init__(self, glossary: dict[str, dict], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Глоссарий DevOps")
        self.resize(880, 560)
        self.glossary = glossary

        title = QLabel("Глоссарий")
        title.setObjectName("Title")
        subtitle = QLabel(f"{len(glossary)} терминов курса — ищите по названию или определению")
        subtitle.setObjectName("Subtitle")

        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Поиск: kubernetes, CI/CD, IaC ...")
        self.search.textChanged.connect(self._filter)

        self.list = QListWidget(self)
        self.list.setMaximumWidth(300)
        self.list.currentRowChanged.connect(self._show_entry)

        self.details = QTextBrowser(self)
        self.details.setObjectName("Lesson")

        body = QHBoxLayout()
        body.addWidget(self.list)
        body.addWidget(self.details, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.search)
        layout.addLayout(body, 1)

        self._filter("")

    def _filter(self, text: str) -> None:
        query = text.strip().lower()
        self.list.clear()
        for term, entry in sorted(self.glossary.items()):
            haystack = f"{term} {entry.get('definition', '')}".lower()
            if query and query not in haystack:
                continue
            item = QListWidgetItem(entry.get("term", term))
            item.setData(Qt.UserRole, term)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            self.details.setHtml("<p>Ничего не найдено — попробуйте другой запрос.</p>")

    def _show_entry(self, row: int) -> None:
        if row < 0:
            return
        item = self.list.item(row)
        entry = self.glossary.get(item.data(Qt.UserRole), {})
        related = entry.get("see_also", [])
        links = ", ".join(f"<b>{r}</b>" for r in related) if related else "—"
        self.details.setHtml(
            f"<h2>{entry.get('term', '')}</h2>"
            f"<p>{entry.get('definition', '')}</p>"
            f"<p><b>Смотрите также:</b> {links}</p>"
            f"<p style='color:#888'><b>Где применяется:</b> {entry.get('where', '—')}</p>"
        )
