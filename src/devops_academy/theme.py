"""Тёмная и светлая темы оформления (QSS) и вспомогательные константы."""

from __future__ import annotations

DARK = {
    "bg": "#0f172a",
    "bg_alt": "#111c33",
    "panel": "#16233d",
    "panel_alt": "#1b2a47",
    "border": "#26375c",
    "text": "#e6edf7",
    "text_dim": "#9fb0cc",
    "accent": "#4f9cf9",
    "accent_soft": "#1d3557",
    "success": "#3ecf8e",
    "warning": "#f0b429",
    "danger": "#f2635f",
    "code_bg": "#0b1526",
    "code_text": "#c9e2ff",
}

LIGHT = {
    "bg": "#f6f8fc",
    "bg_alt": "#eef2f9",
    "panel": "#ffffff",
    "panel_alt": "#f2f5fb",
    "border": "#d3ddec",
    "text": "#16233d",
    "text_dim": "#5a6b88",
    "accent": "#1f6feb",
    "accent_soft": "#dce9fd",
    "success": "#1a7f5a",
    "warning": "#a06800",
    "danger": "#c0392b",
    "code_bg": "#0f1a2e",
    "code_text": "#d7e8ff",
}


def palette(theme: str) -> dict:
    return LIGHT if theme == "light" else DARK


def stylesheet(theme: str) -> str:
    """Возвращает QSS для выбранной темы."""
    c = palette(theme)
    return f"""
    QWidget {{
        background: {c['bg']};
        color: {c['text']};
        font-family: "Segoe UI", "Inter", "Noto Sans", sans-serif;
        font-size: 14px;
    }}
    QMainWindow, QDialog {{ background: {c['bg']}; }}
    #Sidebar {{ background: {c['bg_alt']}; border-right: 1px solid {c['border']}; }}
    #SidebarHeader {{ padding: 14px 12px 6px 12px; font-size: 12px;
        text-transform: uppercase; letter-spacing: 1px; color: {c['text_dim']}; }}
    #Brand {{ font-size: 18px; font-weight: 700; color: {c['text']}; padding: 14px 14px 4px 14px; }}
    #BrandSub {{ font-size: 11px; color: {c['text_dim']}; padding: 0 14px 10px 14px; }}
    QListWidget {{ background: transparent; border: none; outline: none; padding: 4px 6px; }}
    QListWidget::item {{ padding: 9px 10px; border-radius: 8px; color: {c['text_dim']}; }}
    QListWidget::item:hover {{ background: {c['panel_alt']}; color: {c['text']}; }}
    QListWidget::item:selected {{ background: {c['accent_soft']}; color: {c['text']}; font-weight: 600; }}
    QTreeWidget {{ background: transparent; border: none; outline: none; }}
    QTreeWidget::item {{ padding: 7px 6px; border-radius: 7px; color: {c['text']}; }}
    QTreeWidget::item:hover {{ background: {c['panel_alt']}; }}
    QTreeWidget::item:selected {{ background: {c['accent_soft']}; }}
    QToolBar {{ background: {c['bg_alt']}; border-bottom: 1px solid {c['border']}; spacing: 6px; padding: 5px; }}
    QToolButton {{ padding: 6px 10px; border-radius: 7px; color: {c['text_dim']}; }}
    QToolButton:hover {{ background: {c['panel_alt']}; color: {c['text']}; }}
    QStatusBar {{ background: {c['bg_alt']}; color: {c['text_dim']}; border-top: 1px solid {c['border']}; }}
    QPushButton {{
        background: {c['panel_alt']}; color: {c['text']}; border: 1px solid {c['border']};
        border-radius: 8px; padding: 8px 14px;
    }}
    QPushButton:hover {{ border-color: {c['accent']}; }}
    QPushButton:disabled {{ color: {c['text_dim']}; border-color: {c['border']}; }}
    QPushButton#Primary {{ background: {c['accent']}; border: none; color: #ffffff; font-weight: 600; }}
    QPushButton#Primary:hover {{ background: {c['accent']}; }}
    QPushButton#Success {{ background: {c['success']}; border: none; color: #06231a; font-weight: 600; }}
    QPushButton#Danger {{ background: {c['danger']}; border: none; color: #ffffff; }}
    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {{
        background: {c['panel']}; color: {c['text']}; border: 1px solid {c['border']};
        border-radius: 8px; padding: 7px 9px; selection-background-color: {c['accent']};
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{ border-color: {c['accent']}; }}
    QPlainTextEdit#CodeInput {{ font-family: "Cascadia Mono", "Consolas", "JetBrains Mono", monospace; }}
    QLabel#Title {{ font-size: 23px; font-weight: 700; }}
    QLabel#Subtitle {{ color: {c['text_dim']}; font-size: 13px; }}
    QLabel#Badge {{ background: {c['panel_alt']}; border: 1px solid {c['border']}; border-radius: 10px;
        padding: 3px 9px; color: {c['text_dim']}; font-size: 11px; }}
    QLabel#FeedbackOk {{ color: {c['success']}; font-weight: 600; }}
    QLabel#FeedbackBad {{ color: {c['danger']}; font-weight: 600; }}
    QTextBrowser, QTextEdit#Lesson {{ background: {c['panel']}; border: 1px solid {c['border']};
        border-radius: 12px; padding: 18px 24px; selection-background-color: {c['accent']}; }}
    QTabWidget::pane {{ border: 1px solid {c['border']}; border-radius: 10px; background: {c['panel']}; }}
    QTabBar::tab {{ background: transparent; color: {c['text_dim']}; padding: 8px 14px; margin-right: 4px; }}
    QTabBar::tab:selected {{ color: {c['text']}; border-bottom: 2px solid {c['accent']}; }}
    QGroupBox {{ border: 1px solid {c['border']}; border-radius: 10px; margin-top: 12px; padding: 12px; }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; color: {c['text_dim']}; }}
    QProgressBar {{ border: 1px solid {c['border']}; border-radius: 8px; text-align: center;
        background: {c['panel']}; color: {c['text']}; height: 16px; }}
    QProgressBar::chunk {{ background: {c['success']}; border-radius: 7px; }}
    QScrollBar:vertical {{ background: transparent; width: 11px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 5px; min-height: 30px; }}
    QScrollBar::handle:vertical:hover {{ background: {c['accent']}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    QRadioButton, QCheckBox {{ padding: 5px 2px; }}
    QRadioButton::indicator, QCheckBox::indicator {{ width: 16px; height: 16px; }}
    QMenu {{ background: {c['panel']}; border: 1px solid {c['border']}; padding: 5px; }}
    QMenu::item {{ padding: 6px 22px 6px 12px; border-radius: 6px; }}
    QMenu::item:selected {{ background: {c['accent_soft']}; }}
    QSplitter::handle {{ background: {c['border']}; width: 1px; }}
    """


def lesson_css(theme: str) -> str:
    """CSS внутри QTextBrowser (Qt поддерживает ограниченное подмножество CSS)."""
    c = palette(theme)
    return f"""
    body {{ color: {c['text']}; font-family: "Segoe UI", "Noto Sans", sans-serif;
           font-size: 15px; line-height: 1.6; }}
    h1 {{ font-size: 26px; color: {c['text']}; margin: 4px 0 14px 0; }}
    h2 {{ font-size: 21px; color: {c['accent']}; margin: 22px 0 10px 0;
          border-bottom: 1px solid {c['border']}; padding-bottom: 5px; }}
    h3 {{ font-size: 17px; color: {c['text']}; margin: 18px 0 8px 0; }}
    p  {{ margin: 9px 0; }}
    a  {{ color: {c['accent']}; text-decoration: none; }}
    ul, ol {{ margin: 8px 0 8px 6px; }}
    li {{ margin: 4px 0; }}
    code {{ background: {c['code_bg']}; color: {c['code_text']};
            font-family: "Cascadia Mono", "Consolas", monospace; font-size: 13px; }}
    pre {{ background: {c['code_bg']}; color: {c['code_text']}; border: 1px solid {c['border']};
           border-radius: 8px; padding: 12px; white-space: pre-wrap;
           font-family: "Cascadia Mono", "Consolas", monospace; font-size: 13px; }}
    table {{ border-collapse: collapse; margin: 12px 0; width: 100%; }}
    th {{ background: {c['panel_alt']}; color: {c['text']}; border: 1px solid {c['border']};
          padding: 7px 9px; text-align: left; }}
    td {{ border: 1px solid {c['border']}; padding: 7px 9px; }}
    blockquote {{ border-left: 3px solid {c['accent']}; margin: 10px 0; padding: 4px 12px;
                  color: {c['text_dim']}; }}
    .admonition {{ border-radius: 8px; padding: 10px 14px; margin: 12px 0;
                   border: 1px solid {c['border']}; background: {c['panel_alt']}; }}
    .admonition .adm-title {{ font-weight: 700; margin-bottom: 4px; }}
    .note .adm-title {{ color: {c['accent']}; }}
    .tip .adm-title {{ color: {c['success']}; }}
    .warning .adm-title {{ color: {c['warning']}; }}
    .danger .adm-title {{ color: {c['danger']}; }}
    .term {{ color: {c['accent']}; border-bottom: 1px dotted {c['accent']}; }}
    .k-kw {{ color: #ff9d76; font-weight: 600; }}
    .k-str {{ color: #9ae6a0; }}
    .k-num {{ color: #ffd479; }}
    .k-cmt {{ color: #7d8fa8; font-style: italic; }}
    .k-var {{ color: #7fd4ff; }}
    .k-fn {{ color: #c6a7ff; }}
    .path {{ color: {c['text_dim']}; }}
    """
