"""Рендер уроков: admonitions, подсветка кода, картинки, термины."""

from __future__ import annotations

from pathlib import Path

from devops_academy.markdown_renderer import render_lesson, render_plain

CONTENT = Path(__file__).resolve().parents[1] / "content"


def test_headings_and_tables():
    html = render_lesson("# Заголовок\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n", CONTENT, {})
    assert "<h1" in html and "<table>" in html


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
