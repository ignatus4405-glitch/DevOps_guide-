#!/usr/bin/env python3
"""Генерирует SVG-карточки по шагам, описанным в самих уроках.

Источник истины — раздел «Пошаговый сценарий» в Markdown. Запуск:
    python tools/generate_lesson_diagrams.py
Проверка соответствия уже созданных SVG:
    python tools/generate_lesson_diagrams.py --check
"""

from __future__ import annotations

import argparse
import html
import re
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
GUIDE_RE = re.compile(
    r"(?ms)^## Пошаговый сценарий\s*\n(.*?)(?=^#{1,6}\s|\Z)"
)
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
STEP_RE = re.compile(r"(?m)^\s*\d+\.\s+(.+)$")
TITLE_RE = re.compile(r"(?m)^title:\s*(.+)$")


def _wrap_step(text: str) -> list[str]:
    """Разбивает короткий шаг на строки, помещающиеся в SVG-карточку."""
    return textwrap.wrap(text, width=24, break_long_words=True, break_on_hyphens=False) or [text]


def render_diagram(title: str, steps: list[str]) -> str:
    """Создаёт доступную SVG-схему из четырёх текстовых шагов."""
    svg: list[str] = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="280" viewBox="0 0 960 280" role="img" aria-labelledby="title desc">',
        f"  <title id=\"title\">Порядок действий: {html.escape(title)}</title>",
        f"  <desc id=\"desc\">{html.escape(' → '.join(steps))}</desc>",
        "  <defs>",
        '    <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">',
        '      <path d="M 0 0 L 10 5 L 0 10 z" fill="#5584bd"/>',
        "    </marker>",
        "  </defs>",
        '  <text x="480" y="36" text-anchor="middle" font-family="sans-serif" font-size="20" font-weight="700" fill="#26364a">Порядок действий</text>',
    ]
    xs = [15, 255, 495, 735]
    for index, (x, step) in enumerate(zip(xs, steps, strict=True), start=1):
        svg.extend(
            [
                f'  <rect x="{x}" y="66" width="210" height="174" rx="16" fill="#f4f8fd" stroke="#5b84b6" stroke-width="2"/>',
                f'  <circle cx="{x + 28}" cy="94" r="16" fill="#3d70aa"/>',
                f'  <text x="{x + 28}" y="100" text-anchor="middle" font-family="sans-serif" font-size="16" font-weight="700" fill="#ffffff">{index}</text>',
            ]
        )
        lines = _wrap_step(step)
        start_y = 128 if len(lines) <= 4 else 119
        svg.append(
            f'  <text x="{x + 112}" y="{start_y}" text-anchor="middle" font-family="sans-serif" font-size="14" fill="#1f2937">'
        )
        for line_no, line in enumerate(lines[:6]):
            dy = "0" if line_no == 0 else "19"
            svg.append(f'    <tspan x="{x + 112}" dy="{dy}">{html.escape(line)}</tspan>')
        svg.append("  </text>")
    for x in (225, 465, 705):
        svg.append(
            f'  <line x1="{x}" y1="153" x2="{x + 25}" y2="153" stroke="#5584bd" stroke-width="3" marker-end="url(#arrow)"/>'
        )
    svg.append("</svg>")
    return "\n".join(svg) + "\n"


def _lesson_title(text: str) -> str:
    front_matter = re.match(r"(?s)^---\s*\n(.*?)\n---\s*\n", text)
    match = TITLE_RE.search(front_matter.group(1)) if front_matter else None
    return match.group(1).strip().strip('"').strip("'") if match else "Учебный сценарий"


def generate(*, check: bool = False) -> int:
    processed = 0
    errors: list[str] = []
    for lesson_path in sorted((CONTENT / "modules").glob("*/lessons/*.md")):
        text = lesson_path.read_text(encoding="utf-8")
        guide = GUIDE_RE.search(text)
        if not guide:
            continue
        section = guide.group(1)
        steps = STEP_RE.findall(section)
        image = IMAGE_RE.search(section)
        if len(steps) != 4:
            errors.append(f"{lesson_path.relative_to(ROOT)}: ожидаются ровно 4 шага, найдено {len(steps)}")
            continue
        if image is None:
            errors.append(f"{lesson_path.relative_to(ROOT)}: в сценарии нет ссылки на диаграмму")
            continue
        relative_image = Path(image.group(2))
        if relative_image.is_absolute() or ".." in relative_image.parts:
            errors.append(f"{lesson_path.relative_to(ROOT)}: небезопасный путь изображения {image.group(2)}")
            continue
        image_path = CONTENT.joinpath(*relative_image.parts)
        if image_path.parent.name != "howto":
            errors.append(f"{lesson_path.relative_to(ROOT)}: диаграммы должны быть в assets/img/howto/")
            continue
        expected = render_diagram(_lesson_title(text), steps)
        if check:
            if not image_path.exists() or image_path.read_text(encoding="utf-8") != expected:
                errors.append(f"{image_path.relative_to(ROOT)}: диаграмма отсутствует или устарела")
        else:
            image_path.parent.mkdir(parents=True, exist_ok=True)
            if not image_path.exists() or image_path.read_text(encoding="utf-8") != expected:
                image_path.write_text(expected, encoding="utf-8")
        processed += 1

    if errors:
        print("\n".join(errors))
        return 1
    verb = "Проверено" if check else "Создано/обновлено"
    print(f"{verb} диаграмм: {processed}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Генерация SVG-схем по шагам уроков")
    parser.add_argument("--check", action="store_true", help="проверить SVG, не записывая файлы")
    args = parser.parse_args()
    return generate(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
