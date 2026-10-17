"""Модель и загрузчик контента курса.

Схема (валидируется в CI скриптом tools/validate_content.py):

content/
  glossary.json                     {"terms": [{"term","definition","see_also"}]}
  modules/NN-slug/module.json       описание модуля
  modules/NN-slug/lessons/*.md      уроки (front matter + markdown)
  modules/NN-slug/quiz.json         вопросы теста
  modules/NN-slug/practice.json     практические задачи
  assets/img/*.svg                  иллюстрации (векторные, лёгкие)

Все структуры — dataclass'ы без внешних зависимостей, чтобы легко писать тесты.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class Lesson:
    """Один урок: markdown-файл с front matter."""

    module_id: str
    lesson_id: str
    title: str
    minutes: int
    order: int
    path: Path
    raw: str

    @property
    def body(self) -> str:
        """Markdown без front matter."""
        match = FRONT_MATTER_RE.match(self.raw)
        return self.raw[match.end():] if match else self.raw

    @property
    def key(self) -> str:
        """Уникальный ключ прогресса: module/lesson."""
        return f"{self.module_id}/{self.lesson_id}"


@dataclass
class Question:
    """Вопрос теста.

    type: single | multiple | text
    answer: индекс(ы) правильных вариантов либо список допустимых строк (text)
    """

    qid: str
    qtype: str
    question: str
    options: list[str] = field(default_factory=list)
    answer: list[int] = field(default_factory=list)
    answer_text: list[str] = field(default_factory=list)
    explanation: str = ""
    tags: list[str] = field(default_factory=list)

    def is_correct(self, given: Iterable[int] | str) -> bool:
        if self.qtype == "text":
            text = str(given).strip().lower()
            text = re.sub(r"\s+", " ", text)
            return text in {a.strip().lower() for a in self.answer_text}
        if isinstance(given, str):
            chosen = {int(x) for x in re.findall(r"\d+", given)}
        else:
            chosen = {int(x) for x in given}
        return chosen == set(self.answer)


@dataclass
class Quiz:
    module_id: str
    title: str
    pass_score: int
    questions: list[Question]

    @property
    def max_score(self) -> int:
        return len(self.questions)


@dataclass(frozen=True)
class CommandRequirement:
    """Команда и обязательные последовательные аргументы для проверки практики."""

    name: str
    args: list[str] = field(default_factory=list)


@dataclass
class Task:
    """Практическая задача с автопроверкой введённых команд/ответов."""

    tid: str
    title: str
    goal: str
    level: str
    instructions: list[str]
    hints: list[str]
    solution: str
    check_type: str
    patterns: list[str]
    feedback: str
    validation_hint: str = ""
    commands: list[CommandRequirement] = field(default_factory=list)


@dataclass
class Practice:
    module_id: str
    title: str
    tasks: list[Task]


@dataclass
class Module:
    module_id: str
    order: int
    title: str
    level: str
    summary: str
    estimated_minutes: int
    objectives: list[str]
    tags: list[str]
    path: Path
    lessons: list[Lesson] = field(default_factory=list)
    quiz: Quiz | None = None
    practice: Practice | None = None

    @property
    def slug(self) -> str:
        return self.path.name

    @property
    def lesson_count(self) -> int:
        return len(self.lessons)

    @property
    def task_count(self) -> int:
        return len(self.practice.tasks) if self.practice else 0

    @property
    def question_count(self) -> int:
        return self.quiz.max_score if self.quiz else 0

    @property
    def total_minutes(self) -> int:
        """Оценка времени: уроки + практика + тест."""
        base = sum(lesson.minutes for lesson in self.lessons)
        return base + self.task_count * 10 + self.question_count * 2

    def lesson(self, lesson_id: str) -> Lesson | None:
        for lesson in self.lessons:
            if lesson.lesson_id == lesson_id:
                return lesson
        return None


class ContentError(RuntimeError):
    """Ошибка структуры контента — ловится в CI и показывается в UI."""


def _parse_front_matter(text: str) -> dict[str, str]:
    """Минимальный парсер front matter (key: value), без PyYAML."""
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}
    data: dict[str, str] = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def _load_lesson(module_id: str, path: Path, order: int) -> Lesson:
    raw = path.read_text(encoding="utf-8")
    meta = _parse_front_matter(raw)
    lesson_id = meta.get("id") or path.stem
    body = raw[FRONT_MATTER_RE.match(raw).end():] if FRONT_MATTER_RE.match(raw) else raw
    if len(body.strip()) < 200:
        raise ContentError(f"Урок {path} слишком короткий ({len(body.strip())} символов)")
    title = meta.get("title") or path.stem
    try:
        minutes = int(meta.get("minutes", "20"))
    except ValueError:
        minutes = 20
    return Lesson(
        module_id=module_id,
        lesson_id=lesson_id,
        title=title,
        minutes=minutes,
        order=order,
        path=path,
        raw=raw,
    )


def _load_quiz(module_id: str, path: Path) -> Quiz:
    data = _read_json(path)
    questions: list[Question] = []
    for index, raw_q in enumerate(data.get("questions", []), start=1):
        qtype = raw_q.get("type", "single")
        options = list(raw_q.get("options", []))
        answer = raw_q.get("answer", [])
        answer = answer if isinstance(answer, list) else [answer]
        if qtype in ("single", "multiple"):
            answer = [int(a) for a in answer]
            if not options or not answer:
                raise ContentError(f"{path}: вопрос {raw_q.get('id', index)} без вариантов/ответа")
            if any(a < 0 or a >= len(options) for a in answer):
                raise ContentError(f"{path}: индекс ответа вне диапазона у {raw_q.get('id')}")
        questions.append(
            Question(
                qid=str(raw_q.get("id") or f"q{index}"),
                qtype=qtype,
                question=str(raw_q.get("question", "")).strip(),
                options=options,
                answer=answer if qtype != "text" else [],
                answer_text=[str(a) for a in answer] if qtype == "text" else [],
                explanation=str(raw_q.get("explanation", "")).strip(),
                tags=list(raw_q.get("tags", [])),
            )
        )
    if not questions:
        raise ContentError(f"{path}: нет вопросов")
    return Quiz(
        module_id=module_id,
        title=str(data.get("title", module_id)),
        pass_score=int(data.get("pass_score", 80)),
        questions=questions,
    )


def _load_practice(module_id: str, path: Path) -> Practice:
    data = _read_json(path)
    tasks: list[Task] = []
    for index, raw_t in enumerate(data.get("tasks", []), start=1):
        check = raw_t.get("check", {}) or {}
        if not isinstance(check, dict):
            raise ContentError(f"{path}: check для задачи {raw_t.get('id', index)} должен быть объектом")
        raw_commands = check.get("commands", [])
        if not isinstance(raw_commands, list):
            raise ContentError(f"{path}: check.commands для задачи {raw_t.get('id', index)} должен быть списком")
        commands = []
        for raw_command in raw_commands:
            if not isinstance(raw_command, dict) or not isinstance(raw_command.get("args", []), list):
                raise ContentError(f"{path}: некорректная команда в задаче {raw_t.get('id', index)}")
            commands.append(
                CommandRequirement(
                    name=str(raw_command.get("name", "")).strip(),
                    args=[str(argument) for argument in raw_command.get("args", [])],
                )
            )
        tasks.append(
            Task(
                tid=str(raw_t.get("id") or f"t{index}"),
                title=str(raw_t.get("title", "")).strip(),
                goal=str(raw_t.get("goal", "")).strip(),
                level=str(raw_t.get("level", "easy")),
                instructions=list(raw_t.get("instructions", [])),
                hints=list(raw_t.get("hints", [])),
                solution=str(raw_t.get("solution", "")).strip(),
                check_type=str(check.get("type", "regex_all")),
                patterns=[str(p) for p in check.get("patterns", [])],
                feedback=str(check.get("feedback", "")),
                validation_hint=str(raw_t.get("validation_hint", "")),
                commands=commands,
            )
        )
    if not tasks:
        raise ContentError(f"{path}: нет задач")
    return Practice(module_id=module_id, title=str(data.get("title", module_id)), tasks=tasks)


class Course:
    """Курс целиком: модули, уроки, тесты, практика, глоссарий."""

    def __init__(self, modules: list[Module], glossary: dict[str, dict], root: Path) -> None:
        self.modules = modules
        self.glossary = glossary
        self.root = root

    # --- загрузка -------------------------------------------------------
    @classmethod
    def load(cls, content_dir: Path) -> Course:
        if not content_dir.exists():
            raise ContentError(f"Каталог контента не найден: {content_dir}")
        glossary: dict[str, dict] = {}
        glossary_file = content_dir / "glossary.json"
        if glossary_file.exists():
            for item in _read_json(glossary_file).get("terms", []):
                glossary[item["term"].lower()] = item

        modules: list[Module] = []
        for module_dir in sorted((content_dir / "modules").iterdir()):
            if not module_dir.is_dir():
                continue
            meta = _read_json(module_dir / "module.json")
            lessons = [
                _load_lesson(meta["id"], path, order)
                for order, path in enumerate(sorted((module_dir / "lessons").glob("*.md")), start=1)
            ]
            if not lessons:
                raise ContentError(f"{module_dir}: нет уроков")
            quiz_file = module_dir / "quiz.json"
            practice_file = module_dir / "practice.json"
            modules.append(
                Module(
                    module_id=meta["id"],
                    order=int(meta.get("order", 999)),
                    title=meta["title"],
                    level=meta.get("level", "beginner"),
                    summary=meta.get("summary", ""),
                    estimated_minutes=int(meta.get("estimated_minutes", 0)),
                    objectives=list(meta.get("objectives", [])),
                    tags=list(meta.get("tags", [])),
                    path=module_dir,
                    lessons=lessons,
                    quiz=_load_quiz(meta["id"], quiz_file) if quiz_file.exists() else None,
                    practice=_load_practice(meta["id"], practice_file) if practice_file.exists() else None,
                )
            )
        modules.sort(key=lambda m: (m.order, m.module_id))
        return cls(modules, glossary, content_dir)

    # --- доступ ---------------------------------------------------------
    def module(self, module_id: str) -> Module | None:
        for module in self.modules:
            if module.module_id == module_id:
                return module
        return None

    def lesson(self, module_id: str, lesson_id: str) -> Lesson | None:
        module = self.module(module_id)
        return module.lesson(lesson_id) if module else None

    def all_lessons(self) -> list[Lesson]:
        return [lesson for module in self.modules for lesson in module.lessons]

    def all_questions(self) -> list[Question]:
        return [q for module in self.modules if module.quiz for q in module.quiz.questions]

    def all_tasks(self) -> list[Task]:
        return [t for module in self.modules if module.practice for t in module.practice.tasks]

    def stats(self) -> dict[str, int]:
        return {
            "modules": len(self.modules),
            "lessons": len(self.all_lessons()),
            "questions": len(self.all_questions()),
            "tasks": len(self.all_tasks()),
            "minutes": sum(m.total_minutes for m in self.modules),
        }
