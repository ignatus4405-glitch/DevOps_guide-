"""Рендер уроков: markdown -> HTML для QTextBrowser.

Возможности поверх стандартного markdown:
  * admonition-блоки  !!! note "Заголовок"  (note/tip/warning/danger);
  * подсветка кода для bash/sh/yaml/json/ini/dockerfile/powershell (без Pygments);
  * автоссылки-термины [[термин]] -> подсказка из глоссария;
  * переписывание относительных путей картинок на абсолютные (assets/img/...);
  * таблицы: границы, отступы и фон заголовка вписываются прямо в HTML, потому что
    Qt рисует содержимое QTextBrowser по своим правилам и границы из QSS не применяет.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

import markdown

from .theme import palette

EXTENSIONS = ["fenced_code", "tables", "sane_lists", "attr_list", "nl2br"]

MD = markdown.Markdown(extensions=EXTENSIONS, output_format="html")
# Отдельный экземпляр для вложенного markdown внутри admonition-блоков.
MD_INNER = markdown.Markdown(extensions=EXTENSIONS, output_format="html")

ADMONITION_START = re.compile(r'^!!!\s+(note|tip|warning|danger|info)\s*(?:"([^"]*)")?\s*$')
ADMONITION_TITLES = {
    "note": "ℹ️ Заметка",
    "info": "ℹ️ Заметка",
    "tip": "✅ Совет",
    "warning": "⚠️ Важно",
    "danger": "⛔ Осторожно",
}

BASH_KEYWORDS = (
    "if|then|else|elif|fi|for|while|do|done|case|esac|function|in|export|source|"
    "sudo|echo|exit|return|local|set|read|printf"
)
YAML_KEYWORDS = "true|false|null|yes|no"


def _highlight_code(code: str, lang: str) -> str:
    """Простая подсветка: сначала экранируем, затем красим токены."""
    text = html.escape(code)
    lang = (lang or "").lower()

    def wrap(cls: str, value: str) -> str:
        return f'<span class="{cls}">{value}</span>'

    if lang in ("bash", "sh", "shell", "console", "zsh"):
        text = re.sub(r"(#[^\n]*)", lambda m: wrap("k-cmt", m.group(1)), text)
        text = re.sub(
            rf"^(\s*)({BASH_KEYWORDS})\b", lambda m: m.group(1) + wrap("k-kw", m.group(2)), text, flags=re.M
        )
        text = re.sub(r"(\$\{?\w+\}?)", lambda m: wrap("k-var", m.group(1)), text)
        text = re.sub(r"(\s)(--?[A-Za-z][\w-]*)", lambda m: m.group(1) + wrap("k-fn", m.group(2)), text)
    elif lang in ("yaml", "yml"):
        text = re.sub(r"(#[^\n]*)", lambda m: wrap("k-cmt", m.group(1)), text)
        text = re.sub(r"^(\s*)([\w.\-/]+)(:)", lambda m: m.group(1) + wrap("k-var", m.group(2)) + m.group(3), text, flags=re.M)
        text = re.sub(rf"\b({YAML_KEYWORDS})\b", lambda m: wrap("k-num", m.group(1)), text)
    elif lang in ("json", "jsonc"):
        text = re.sub(r"(&quot;[^&]*?&quot;)(\s*:)?", lambda m: wrap("k-str", m.group(1)) + (m.group(2) or ""), text)
        text = re.sub(r"\b(-?\d+\.?\d*)\b", lambda m: wrap("k-num", m.group(1)), text)
    elif lang in ("ini", "toml", "properties", "conf"):
        text = re.sub(r"^(\s*)([#;][^\n]*)", lambda m: m.group(1) + wrap("k-cmt", m.group(2)), text, flags=re.M)
        text = re.sub(r"^(\s*)(\[[^\]]+\])", lambda m: m.group(1) + wrap("k-kw", m.group(2)), text, flags=re.M)
        text = re.sub(r"^(\s*)([\w.\-\s]+)(=)", lambda m: m.group(1) + wrap("k-var", m.group(2)) + m.group(3), text, flags=re.M)
    elif lang in ("dockerfile", "docker"):
        text = re.sub(r"(#[^\n]*)", lambda m: wrap("k-cmt", m.group(1)), text)
        text = re.sub(
            r"^(\s*)(FROM|RUN|CMD|ENTRYPOINT|COPY|ADD|WORKDIR|ENV|ARG|EXPOSE|USER|VOLUME|LABEL|HEALTHCHECK)",
            lambda m: m.group(1) + wrap("k-kw", m.group(2)),
            text,
            flags=re.M | re.I,
        )
    elif lang in ("powershell", "ps1", "ps"):
        text = re.sub(r"(#[^\n]*)", lambda m: wrap("k-cmt", m.group(1)), text)
        text = re.sub(r"(\$\w+)", lambda m: wrap("k-var", m.group(1)), text)
        text = re.sub(r"\b(Get|Set|New|Remove|Start|Stop|Test|Install|Write|Select)-\w+",
                      lambda m: wrap("k-fn", m.group(0)), text)
    elif lang in ("python", "py"):
        text = re.sub(r"(#[^\n]*)", lambda m: wrap("k-cmt", m.group(1)), text)
        text = re.sub(
            r"\b(import|from|def|class|return|if|elif|else|for|while|try|except|with|as|lambda|None|True|False|not|and|or)\b",
            lambda m: wrap("k-kw", m.group(0)),
            text,
        )
        text = re.sub(r"(&quot;[^&]*?&quot;)", lambda m: wrap("k-str", m.group(1)), text)
    return f'<pre class="code {lang}"><code>{text}</code></pre>'


def _render_admonitions(text: str) -> str:
    """!!! note "Title" + отступ 4 пробела -> div.admonition."""
    lines = text.split("\n")
    out: list[str] = []
    index = 0
    while index < len(lines):
        match = ADMONITION_START.match(lines[index])
        if not match:
            out.append(lines[index])
            index += 1
            continue
        kind = match.group(1)
        title = match.group(2) or ADMONITION_TITLES.get(kind, kind)
        index += 1
        body: list[str] = []
        while index < len(lines):
            line = lines[index]
            if line.strip() == "" or line.startswith("    ") or line.startswith("\t"):
                body.append(line[4:] if line.startswith("    ") else line.lstrip("\t"))
                index += 1
            else:
                break
        inner = "\n".join(body).strip()
        MD_INNER.reset()
        inner_html = MD_INNER.convert(inner)
        out.append(
            f'<div class="admonition {kind}"><p class="adm-title">{title}</p>\n{inner_html}\n</div>'
        )
    return "\n".join(out)


def _render_terms(text: str, glossary: dict[str, dict]) -> str:
    """[[docker]] -> span с подсказкой из глоссария."""
    if not glossary:
        return text

    def repl(match: re.Match) -> str:
        term = match.group(1)
        entry = glossary.get(term.lower())
        if not entry:
            return term
        definition = html.escape(entry.get("definition", ""), quote=True)
        return f'<span class="term" title="{definition}">{html.escape(term)}</span>'

    return re.sub(r"\[\[([^\]]+)\]\]", repl, text)


def _rewrite_images(text: str, content_root: Path) -> str:
    """Относительные ссылки assets/... -> абсолютный file:// путь."""

    def repl(match: re.Match) -> str:
        target = match.group(2)
        if target.startswith(("http://", "https://", "file://", "data:")):
            return match.group(0)
        candidate = (content_root / target.lstrip("/")).resolve()
        if candidate.exists():
            return f"]({candidate.as_uri()})"
        return match.group(0)

    return re.sub(r"(\]\(|src=\")([^)\"]+)(\)|\")", repl, text)


TABLE_RE = re.compile(r"<table(?=[\s>])(\s[^>]*)?>", re.IGNORECASE)
TH_RE = re.compile(r"<th(?=[\s>])(\s[^>]*)?>", re.IGNORECASE)
TD_RE = re.compile(r"<td(?=[\s>])(\s[^>]*)?>", re.IGNORECASE)
STYLE_ATTR_RE = re.compile(r'style="([^"]*)"', re.IGNORECASE)


def _merge_style(tag_html: str, extra: str) -> str:
    """Добавляет CSS к тегу, сохраняя уже существующий style="...".

    Qt понимает только инлайновые стили для границ таблиц, поэтому базовые
    свойства (границы, отступы, фон) вписываем прямо в теги.
    """
    match = STYLE_ATTR_RE.search(tag_html)
    if match:
        existing = match.group(1).strip().rstrip(";")
        merged = f"{existing}; {extra}" if existing else extra
        return tag_html[: match.start()] + f'style="{merged}"' + tag_html[match.end() :]
    return tag_html[:-1] + f' style="{extra}">' if tag_html.endswith(">") else tag_html


def style_tables(html_body: str, theme: str = "dark") -> str:
    """Оформляет таблицы: границы, отступы, фон и разделение строк.

    QSS из ``lesson_css`` Qt применяет не ко всему содержимому документа, поэтому
    границы таблиц задаются инлайново (иначе таблица выглядит «слипшейся»).
    """
    if "<table" not in html_body:
        return html_body

    c = palette(theme)
    table_style = f"border-collapse: collapse; border: 1px solid {c['border']}; margin: 12px 0; width: 100%;"
    # text-align сюда не входит: markdown сам добавляет выравнивание из разметки,
    # а продублированное свойство в style= перекрыло бы его (последнее значение важнее).
    th_style = (
        f"border: 1px solid {c['border']}; background-color: {c['panel_alt']}; color: {c['text']};"
        " padding: 7px 10px; font-weight: 700;"
    )
    td_style = f"border: 1px solid {c['border']}; padding: 7px 10px; vertical-align: top;"

    def style_header(match: re.Match) -> str:
        """Заголовок: выравнивание из markdown важнее стиля по умолчанию."""
        tag_html = match.group(0)
        extra = th_style if "text-align" in tag_html.lower() else f"text-align: left; {th_style}"
        return _merge_style(tag_html, extra)

    html_body = TABLE_RE.sub(lambda m: _merge_style(m.group(0), table_style), html_body)
    html_body = TH_RE.sub(style_header, html_body)
    html_body = TD_RE.sub(lambda m: _merge_style(m.group(0), td_style), html_body)
    return _zebra_rows(html_body, c)


ROW_RE = re.compile(r"<tr(?=[\s>])(\s[^>]*)?>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
CELL_RE = re.compile(r"<td(?=[\s>])(\s[^>]*)?>", re.IGNORECASE)


def _zebra_rows(html_body: str, colours: dict) -> str:
    """Чередует фон строк тела таблицы — так таблицы читаются построчно."""
    def style_row(match: re.Match) -> str:
        row_html = match.group(0)
        if "<th" in row_html.lower():
            return row_html  # строку заголовка не трогаем
        return CELL_RE.sub(
            lambda m: _merge_style(m.group(0), f"background-color: {colours['bg_alt']};"), row_html
        )

    # Чётные строки (индекс 1, 3, ... в каждом tbody) получают подложку
    def style_tbody(match: re.Match) -> str:
        counter = {"index": 0}

        def replace(row: re.Match) -> str:
            counter["index"] += 1
            return style_row(row) if counter["index"] % 2 == 0 else row.group(0)

        return ROW_RE.sub(replace, match.group(0))

    return re.sub(r"<tbody>.*?</tbody>", style_tbody, html_body, flags=re.IGNORECASE | re.DOTALL)


def render_lesson(
    body: str,
    content_root: Path,
    glossary: dict[str, dict] | None = None,
    theme: str = "dark",
) -> str:
    """Главная функция: markdown урока -> безопасный HTML для QTextBrowser."""
    prepared = _render_admonitions(body)
    prepared = _rewrite_images(prepared, content_root)
    prepared = _render_terms(prepared, glossary or {})
    MD.reset()
    html_body = MD.convert(prepared)
    html_body = _postprocess_code_blocks(html_body)
    html_body = style_tables(html_body, theme)
    return html_body


CODE_BLOCK_RE = re.compile(r'<pre><code(?:\s+class="language-([\w+-]+)")?>(.*?)</code></pre>', re.DOTALL)


def _postprocess_code_blocks(html_body: str) -> str:
    """Заменяем обычные <pre><code> на подсвеченные."""

    def repl(match: re.Match) -> str:
        lang = match.group(1) or ""
        code = html.unescape(match.group(2))
        return _highlight_code(code, lang)

    return CODE_BLOCK_RE.sub(repl, html_body)


def render_plain(text: str, theme: str = "dark") -> str:
    """Рендер без глоссария/путей — для пояснений к тестам и задач."""
    MD.reset()
    return style_tables(MD.convert(text), theme)
