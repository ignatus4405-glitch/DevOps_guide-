"""Pure checker for practice answers; it tokenizes input but never executes shell commands."""

from __future__ import annotations

import re
import shlex

from .content import Task


class TaskChecker:
    """Проверяет текстовый ответ, regex-шаблоны или argv-команды без их исполнения."""

    @staticmethod
    def normalise(text: str) -> str:
        text = text.strip().lower()
        text = text.replace("«", '"').replace("»", '"')
        return re.sub(r"\s+", " ", text)

    @staticmethod
    def _command_segments(answer: str) -> list[list[str]]:
        """Разбирает строки shell лексически и отбрасывает комментарии без исполнения."""
        segments: list[list[str]] = []
        answer = answer.replace("\\\n", " ")
        for line in answer.splitlines():
            lexer = shlex.shlex(line, posix=True, punctuation_chars=";&|")
            lexer.whitespace_split = True
            lexer.commenters = "#"
            try:
                tokens = list(lexer)
            except ValueError as error:
                raise ValueError(f"незакрытая кавычка: {error}") from error
            current: list[str] = []
            for token in tokens:
                if token in {";", "&&", "||", "&", "|"}:
                    if current:
                        segments.append(current)
                        current = []
                else:
                    current.append(token)
            if current:
                segments.append(current)
        return segments

    @staticmethod
    def _executable(tokens: list[str]) -> tuple[str, list[str]]:
        """Возвращает команду и аргументы, учитывая распространённую обёртку sudo."""
        index = 0
        if tokens and tokens[0] in {"sudo", "doas"}:
            index = 1
            options_with_value = {"-u", "--user", "-g", "--group", "-h", "--host", "-p", "--prompt"}
            while index < len(tokens):
                token = tokens[index]
                if token == "--":
                    index += 1
                    break
                if token in options_with_value:
                    index += 2
                elif token.startswith("-"):
                    index += 1
                else:
                    break
        if index >= len(tokens):
            return "", []
        return tokens[index].rsplit("/", 1)[-1], tokens[index + 1 :]

    @staticmethod
    def _contains_args(actual: list[str], required: list[str]) -> bool:
        """Проверяет обязательный упорядоченный набор argv-токенов."""
        if not required:
            return True
        required_index = 0
        for token in actual:
            if token == required[required_index]:
                required_index += 1
                if required_index == len(required):
                    return True
        return False

    @classmethod
    def _check_commands(cls, task: Task, answer: str) -> tuple[bool, str]:
        try:
            segments = cls._command_segments(answer)
        except ValueError as error:
            return False, f"Не удалось разобрать команды: {error}"
        parsed = [cls._executable(segment) for segment in segments]
        missing = [
            requirement.name
            for requirement in task.commands
            if not any(
                executable == requirement.name and cls._contains_args(arguments, requirement.args)
                for executable, arguments in parsed
            )
        ]
        if missing:
            return False, "Не найдены команды с обязательными аргументами: " + ", ".join(missing)
        return True, task.feedback or "Все требуемые команды и аргументы найдены."

    @classmethod
    def check(cls, task: Task, answer: str) -> tuple[bool, str]:
        if not answer.strip():
            return False, "Введите команду или ответ"
        if task.check_type == "manual":
            return True, task.feedback or "Задача на самопроверку — сверьтесь с эталоном ниже."
        if task.check_type == "commands":
            if not task.commands:
                return False, "Для этой задачи не настроены требования к командам."
            return cls._check_commands(task, answer)
        value = cls.normalise(answer)
        if task.check_type == "equals":
            allowed = {cls.normalise(pattern) for pattern in task.patterns}
            if value in allowed:
                return True, task.feedback or "Верно."
            return False, "Ответ не совпал с эталоном. Проверьте синтаксис и порядок аргументов."
        if task.check_type == "regex_any":
            for pattern in task.patterns:
                if re.search(pattern, answer, re.IGNORECASE | re.MULTILINE):
                    return True, task.feedback or "Верно."
            return False, "Ни одно из ожидаемых решений не найдено. Перечитайте подсказки."
        # По умолчанию regex_all.
        missing = [
            pattern
            for pattern in task.patterns
            if not re.search(pattern, answer, re.IGNORECASE | re.MULTILINE)
        ]
        if not missing:
            return True, task.feedback or "Верно."
        return (
            False,
            f"Не хватает {len(missing)} элемента(ов) из {len(task.patterns)}. "
            "Подсказка: включите нужные ключи и параметры.",
        )
