"""Модель и загрузчик контента курса.

Схема (валидируется в CI скриптом tools/validate_content.py):

content/
  glossary.json                     {"terms": [{"term","definition","see_also"}]}
  modules/NN-slug/module.json       описание модуля
  modules/NN-slug/lessons/*.md      уроки (front matter + markdown)
  modules/NN-slug/quiz.json         вопросы теста модуля
  modules/NN-slug/lesson_quizzes.json тесты после уроков
  modules/NN-slug/practice.json    практические задачи
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
    quiz: Quiz | None = None

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


def _load_question(raw_question: dict, index: int, path: Path) -> Question:
    if not isinstance(raw_question, dict):
        raise ContentError(f"{path}: вопрос {index} должен быть объектом")
    qtype = str(raw_question.get("type", "single"))
    if qtype not in {"single", "multiple", "text"}:
        raise ContentError(f"{path}: неизвестный тип вопроса {qtype!r}")
    options = list(raw_question.get("options", []))
    answer = raw_question.get("answer", [])
    answer = answer if isinstance(answer, list) else [answer]
    if qtype in {"single", "multiple"}:
        try:
            answer = [int(option) for option in answer]
        except (TypeError, ValueError) as error:
            raise ContentError(f"{path}: некорректный индекс ответа у {raw_question.get('id', index)}") from error
        question_id = raw_question.get("id", index)
        if not options or not answer:
            raise ContentError(f"{path}: вопрос {question_id} без вариантов/ответа")
        if qtype == "single" and len(answer) != 1:
            raise ContentError(f"{path}: single-вопрос {question_id} должен иметь один правильный ответ")
        if any(option < 0 or option >= len(options) for option in answer):
            raise ContentError(f"{path}: индекс ответа вне диапазона у {question_id}")
    elif not answer:
        raise ContentError(f"{path}: text-вопрос {raw_question.get('id', index)} без ответа")
    return Question(
        qid=str(raw_question.get("id") or f"q{index}"),
        qtype=qtype,
        question=str(raw_question.get("question", "")).strip(),
        options=options,
        answer=answer if qtype != "text" else [],
        answer_text=[str(item) for item in answer] if qtype == "text" else [],
        explanation=str(raw_question.get("explanation", "")).strip(),
        tags=list(raw_question.get("tags", [])),
    )


def _quiz_from_data(module_id: str, data: dict, path: Path) -> Quiz:
    raw_questions = data.get("questions", [])
    if not isinstance(raw_questions, list):
        raise ContentError(f"{path}: questions должен быть списком")
    questions = [_load_question(raw_question, index, path) for index, raw_question in enumerate(raw_questions, start=1)]
    if not questions:
        raise ContentError(f"{path}: нет вопросов")
    ids = [question.qid for question in questions]
    if len(ids) != len(set(ids)):
        raise ContentError(f"{path}: повторяются id вопросов")
    try:
        pass_score = int(data.get("pass_score", 80))
    except (TypeError, ValueError) as error:
        raise ContentError(f"{path}: pass_score должен быть целым числом") from error
    if not 0 < pass_score <= 100:
        raise ContentError(f"{path}: pass_score должен быть от 1 до 100")
    return Quiz(
        module_id=module_id,
        title=str(data.get("title", module_id)),
        pass_score=pass_score,
        questions=questions,
    )


def _load_quiz(module_id: str, path: Path) -> Quiz:
    return _quiz_from_data(module_id, _read_json(path), path)


def _load_lesson_quizzes(
    module_id: str,
    path: Path,
    lessons: list[Lesson],
    module_quiz: Quiz,
) -> dict[str, Quiz]:
    data = _read_json(path)
    raw_lessons = data.get("lessons", {})
    if not isinstance(raw_lessons, dict):
        raise ContentError(f"{path}: lessons должен быть объектом")
    expected_ids = {lesson.lesson_id for lesson in lessons}
    if set(raw_lessons) != expected_ids:
        missing = sorted(expected_ids - set(raw_lessons))
        extra = sorted(set(raw_lessons) - expected_ids)
        raise ContentError(f"{path}: несоответствие уроков (нет {missing}, лишние {extra})")

    try:
        default_pass_score = int(data.get("pass_score", 67))
    except (TypeError, ValueError) as error:
        raise ContentError(f"{path}: pass_score должен быть целым числом") from error
    question_bank = {question.qid: question for question in module_quiz.questions}
    result: dict[str, Quiz] = {}
    for lesson in lessons:
        raw_quiz = raw_lessons[lesson.lesson_id]
        if not isinstance(raw_quiz, dict):
            raise ContentError(f"{path}: тест урока {lesson.lesson_id} должен быть объектом")
        question_ids = raw_quiz.get("question_ids", [])
        raw_extra = raw_quiz.get("questions", [])
        if not isinstance(question_ids, list) or any(not isinstance(item, str) for item in question_ids):
            raise ContentError(f"{path}: question_ids для {lesson.lesson_id} должен быть списком строк")
        if not isinstance(raw_extra, list):
            raise ContentError(f"{path}: questions для {lesson.lesson_id} должен быть списком")
        questions: list[Question] = []
        for question_id in question_ids:
            question = question_bank.get(question_id)
            if question is None:
                raise ContentError(f"{path}: неизвестный вопрос {question_id!r} в тесте {lesson.lesson_id}")
            questions.append(question)
        questions.extend(
            _load_question(raw_question, index, path)
            for index, raw_question in enumerate(raw_extra, start=1)
        )
        if len(questions) != 3:
            raise ContentError(f"{path}: тест {lesson.lesson_id} должен содержать ровно 3 вопроса")
        ids = [question.qid for question in questions]
        if len(ids) != len(set(ids)):
            raise ContentError(f"{path}: повторяются вопросы в тесте {lesson.lesson_id}")
        try:
            pass_score = int(raw_quiz.get("pass_score", default_pass_score))
        except (TypeError, ValueError) as error:
            raise ContentError(f"{path}: pass_score для {lesson.lesson_id} должен быть целым числом") from error
        if not 0 < pass_score <= 100:
            raise ContentError(f"{path}: pass_score для {lesson.lesson_id} должен быть от 1 до 100")
        quiz_id = f"lesson:{module_id}/{lesson.lesson_id}"
        result[lesson.lesson_id] = Quiz(
            module_id=quiz_id,
            title=str(raw_quiz.get("title", lesson.title)),
            pass_score=pass_score,
            questions=questions,
        )
    return result


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
            lesson_quizzes_file = module_dir / "lesson_quizzes.json"
            practice_file = module_dir / "practice.json"
            module_quiz = _load_quiz(meta["id"], quiz_file) if quiz_file.exists() else None
            if module_quiz is None:
                raise ContentError(f"{module_dir}: нет quiz.json")
            if not lesson_quizzes_file.exists():
                raise ContentError(f"{module_dir}: нет lesson_quizzes.json")
            lesson_quizzes = _load_lesson_quizzes(meta["id"], lesson_quizzes_file, lessons, module_quiz)
            for lesson in lessons:
                lesson.quiz = lesson_quizzes[lesson.lesson_id]
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
                    quiz=module_quiz,
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
        """Вопросы больших модульных тестов (используются в итоговом экзамене)."""
        return [q for module in self.modules if module.quiz for q in module.quiz.questions]

    def all_lesson_questions(self) -> list[Question]:
        """Вопросы коротких проверок после уроков."""
        return [q for lesson in self.all_lessons() if lesson.quiz for q in lesson.quiz.questions]

    def all_tasks(self) -> list[Task]:
        return [t for module in self.modules if module.practice for t in module.practice.tasks]

    def stats(self) -> dict[str, int]:
        module_questions = len(self.all_questions())
        lesson_questions = len(self.all_lesson_questions())
        return {
            "modules": len(self.modules),
            "lessons": len(self.all_lessons()),
            "questions": module_questions + lesson_questions,
            "module_questions": module_questions,
            "lesson_questions": lesson_questions,
            "tasks": len(self.all_tasks()),
            "minutes": sum(m.total_minutes for m in self.modules),
        }
