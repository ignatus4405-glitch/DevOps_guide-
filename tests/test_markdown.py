"""Рендер уроков: admonitions, подсветка кода, картинки, термины."""

from __future__ import annotations

import re
from pathlib import Path

from devops_academy.markdown_renderer import render_lesson, render_plain
from devops_academy.theme import palette

CONTENT = Path(__file__).resolve().parents[1] / "content"

SAMPLE_TABLE = "| Задача | Инструмент |\n| --- | --- |\n| код | Git |\n| контейнеры | Docker |\n"


def test_headings_and_tables():
    html = render_lesson("# Заголовок\n\n" + SAMPLE_TABLE, CONTENT, {})
    assert "<h1" in html and "<table " in html


def test_tables_have_borders_and_header_background():
    """Границы и фон заголовка заданы инлайново: иначе Qt рисует таблицу без сетки."""
    for theme in ("dark", "light"):
        html = render_lesson(SAMPLE_TABLE, CONTENT, {}, theme)
        colors = palette(theme)
        table_tag = re.search(r"<table[^>]*>", html).group(0)
        header_tag = re.search(r"<th(?=[\s>])[^>]*>", html).group(0)
        cell_tag = re.search(r"<td(?=[\s>])[^>]*>", html).group(0)

        assert f"border: 1px solid {colors['border']}" in table_tag
        assert "border-collapse: collapse" in table_tag
        assert f"border: 1px solid {colors['border']}" in header_tag
        assert f"background-color: {colors['panel_alt']}" in header_tag
        assert f"border: 1px solid {colors['border']}" in cell_tag
        # Общая ширина и отступы — чтобы колонки не «слипались»
        assert "padding: 7px 10px" in header_tag and "padding: 7px 10px" in cell_tag


def test_table_alignment_from_markdown_is_preserved():
    html = render_lesson("| a | b |\n|:---|---:|\n| 1 | 2 |\n", CONTENT, {})
    headers = re.findall(r"<th(?=[\s>])[^>]*>", html)
    assert "text-align: left" in headers[0]
    assert "text-align: right" in headers[1]
    # Выравнивание не дублируется стилем по умолчанию
    assert headers[0].count("text-align: left") == 1


def test_zebra_rows_do_not_touch_header():
    """Подложка чередуется только в теле таблицы — строка заголовка сохраняет свой фон."""
    html = render_lesson(
        "| h1 | h2 |\n| --- | --- |\n| a | b |\n| c | d |\n| e | f |\n", CONTENT, {}, "dark"
    )
    colors = palette("dark")
    thead = html[html.index("<thead>") : html.index("</thead>")]
    tbody = html[html.index("<tbody>") : html.index("</tbody>")]

    assert f"background-color: {colors['bg_alt']}" not in thead
    assert tbody.count(f"background-color: {colors['bg_alt']}") > 0
    # В теле подложка только у каждой второй строки
    assert tbody.count(f"background-color: {colors['bg_alt']}") < tbody.count("<td")


def test_void_of_tables_is_untouched():
    """HTML без таблиц не меняется — стилизация работает только при их наличии."""
    html = render_lesson("# Только текст\n\nАбзац.\n", CONTENT, {})
    assert "<table" not in html


def test_render_plain_styles_tables_too():
    html = render_plain("| a | b |\n| --- | --- |\n| 1 | 2 |\n", "light")
    assert "<table " in html and "border: 1px solid" in html


def test_code_block_highlighted():
    html = render_lesson("```bash\nsudo systemctl restart nginx\n```\n", CONTENT, {})
    assert "class=\"code bash\"" in html
    assert "k-kw" in html  # sudo подсвечен как ключевое слово


def test_admonition_rendered_with_markdown_inside():
    md = '!!! warning "Важно"\n    Проверь `sudo` и **логи**.\n'
    html = render_lesson(md, CONTENT, {})
    assert 'class="admonition warning"' in html
    assert "<code>sudo</code>" in html
    assert "<strong>логи</strong>" in html


def test_glossary_terms_become_tooltips():
    glossary = {"docker": {"term": "Docker", "definition": "Платформа контейнеризации"}}
    html = render_lesson("Мы используем [[docker]] и [[неизвестное]].", CONTENT, glossary)
    assert "Платформа контейнеризации" in html
    assert "неизвестное" in html  # неизвестный термин остаётся текстом


def test_images_rewritten_to_absolute_file_urls():
    body = "![Схема](assets/img/devops-lifecycle.svg)"
    html = render_lesson(body, CONTENT, {})
    assert "file://" in html and "devops-lifecycle.svg" in html


def test_nested_howto_diagram_is_rendered_from_content():
    target = "assets/img/howto/00-intro--01-what-is-devops.svg"
    assert (CONTENT / target).is_file()
    html = render_lesson(f"![Порядок действий]({target})", CONTENT, {})
    assert "file://" in html and "00-intro--01-what-is-devops.svg" in html


def test_external_images_left_alone():
    body = "![Лого](https://example.com/x.png)"
    html = render_lesson(body, CONTENT, {})
    assert "https://example.com/x.png" in html


def test_all_course_lessons_render(course):
    """Каждый урок рендерится и содержит заголовок."""
    for module in course.modules:
        for lesson in module.lessons:
            html = render_lesson(lesson.body, course.root, course.glossary)
            assert "<h1" in html or "<h2" in html, f"нет заголовка: {lesson.key}"
            assert "None" not in html[:200], f"похоже на ошибку рендера: {lesson.key}"


def test_render_plain_for_explanations():
    html = render_plain("**Жирный** и `код`")
    assert "<strong>" in html and "<code>" in html
