"""Проверка SVG-схем курса: валидность, размеры и геометрия ответственных схем.

Схемы генерируются кодом (`tools/make_diagrams.py`), поэтому проверки дешёвые:
валидируем XML, следим, чтобы линии не проходили через центральные панели,
и чтобы схемы в уроках существовали. Ошибку вёрстки ловим до релиза, а не на скриншоте.
"""

from __future__ import annotations

import importlib.util
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "content" / "assets" / "img"
SVG_NS = "{http://www.w3.org/2000/svg}"


def _load_tool(name: str):
    spec = importlib.util.spec_from_file_location(f"tool_{name}", ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def diagrams():
    return _load_tool("make_diagrams")


def _svg_files() -> list[Path]:
    return list(ALL_SVGS)


def _curve_points(d: str) -> list[tuple[float, float]]:
    """Координаты опорных точек кривой (без команд-флагов, как у дуг ``A``)."""
    numbers = [float(value) for value in d.replace(",", " ").split() if _is_number(value)]
    return list(zip(numbers[0::2], numbers[1::2], strict=False))


def _points_inside_panel(d: str, panel: tuple[int, int, int, int]) -> list[tuple[float, float]]:
    """Точки кривой, попадающие внутрь панели (x, y, ширина, высота)."""
    x0, y0, w, h = panel
    return [point for point in _curve_points(d) if x0 <= point[0] <= x0 + w and y0 <= point[1] <= y0 + h]


def test_all_diagrams_exist():
    files = _svg_files()
    assert len(files) == 20, f"ожидалось 20 иллюстраций, найдено {len(files)}"


ALL_SVGS = sorted(IMAGES.glob("*.svg")) if IMAGES.exists() else []


@pytest.mark.parametrize("path", ALL_SVGS, ids=lambda p: p.name)
def test_svg_is_well_formed_xml(path: Path):
    """Каждый SVG — валидный XML (сломанный XML не отрисуется в приложении)."""
    tree = ET.parse(path)
    root = tree.getroot()
    assert root.tag == f"{SVG_NS}svg", f"{path.name}: корневой элемент не <svg>"
    assert root.get("viewBox"), f"{path.name}: нет viewBox — картинка не масштабируется"
    width, height = int(root.get("width", 0)), int(root.get("height", 0))
    assert width >= 600 and height >= 300, f"{path.name}: слишком маленький холст {width}x{height}"


def test_lifecycle_platform(diagrams):
    """Схема жизненного цикла: 8 этапов, все внутри холста, ни одна стрелка не в центре."""
    svg = diagrams.devops_lifecycle()
    markup = "\n".join(svg.parts)

    for title, _subtitle, _color in [
        ("Планирование", "", ""),
        ("Мониторинг", "", ""),
        ("Релиз", "", ""),
    ]:
        assert title in markup, f"на схеме нет этапа «{title}»"

    # Все блоки и подписи внутри холста
    for part in svg.parts:
        if part.startswith("<rect x=") and "fill=\"#0f172a\"" not in part:
            x = float(part.split('x="')[1].split('"')[0])
            y = float(part.split('y="')[1].split('"')[0])
            w = float(part.split('width="')[1].split('"')[0])
            h = float(part.split('height="')[1].split('"')[0])
            assert 0 <= x and x + w <= svg.width, f"блок выходит за холст по X: {part[:60]}"
            assert 0 <= y and y + h <= svg.height, f"блок выходит за холст по Y: {part[:60]}"

    # Ключевая регрессия: стрелки не заходят на центральную панель.
    # Разбираем только кривые (Q/C): у дуговых команд (A) числа включают флаги,
    # и простое чтение пар координат дало бы ложное срабатывание.
    panel = diagrams.LIFECYCLE_PANEL
    arrows = [p for p in svg.parts if p.startswith("<path") and " A " not in p]
    assert len(arrows) >= 8, "на схеме должно быть не меньше восьми стрелок"
    for path in arrows:
        d = path.split('d="')[1].split('"')[0]
        hits = _points_inside_panel(d, panel)
        assert not hits, f"стрелка заходит на центральную панель в {hits}: {d[:80]}"

    track = [p for p in svg.parts if p.startswith("<path") and " A " in p]
    assert track, "нет кольцевой трассы — схема не читается как цикл"
    assert panel[2] > 200 and panel[3] > 60, "панель слишком узкая для текста"


def test_lifecycle_arc_control_points_are_outside_panel(diagrams):
    """Опорные точки дуг лежат на кольце (вне панели) — это и была причина «каши»."""
    cx, cy, rx, ry = diagrams.LIFECYCLE_RING
    steps = 8
    for index in range(steps):
        t_mid = -math.pi / 2 + (index + 0.5) * 2 * math.pi / steps
        x, y = diagrams._ellipse_point(cx, cy, rx, ry, t_mid)
        panel = diagrams.LIFECYCLE_PANEL
        assert not (panel[0] <= x <= panel[0] + panel[2] and panel[1] <= y <= panel[1] + panel[3])


def test_lesson_images_exist_and_are_used(course):
    """Каждая схема подключена хотя бы к одному уроку, а ссылки ведут на реальные файлы."""
    used: set[str] = set()
    for module in course.modules:
        for lesson in module.lessons:
            for line in lesson.body.splitlines():
                if "assets/img/" in line and "](" in line:
                    target = line.split("](")[1].split(")")[0]
                    used.add(target.split("/")[-1])
    assert used, "ни одна схема не используется в уроках"
    for name in used:
        assert (IMAGES / name).exists(), f"урок ссылается на отсутствующий файл {name}"
    unused = {path.name for path in _svg_files()} - used
    assert not unused, f"схемы объявлены, но не используются в уроках: {sorted(unused)}"


def _is_number(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def test_panel_checker_catches_old_bug(diagrams):
    """Проверка-регрессия сама должна ловить прежнюю ошибку.

    Старая схема строила дуги с опорной точкой в центре (450, 340) — именно из-за
    этого линии шли сквозь панель. Если проверка перестанет это замечать, она
    бесполезна, поэтому тестируем её на заведомо плохой кривой.
    """
    panel = diagrams.LIFECYCLE_PANEL
    bad_path = "M 450 192 Q 450 340 613 224"
    assert _points_inside_panel(bad_path, panel), "проверка не увидела старую ошибку"

    good_path = "M 550 158 Q 577 156 594 166"
    assert not _points_inside_panel(good_path, panel)
