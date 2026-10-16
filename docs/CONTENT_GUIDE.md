# Как добавлять контент

Весь курс — это данные в `content/`. Код приложения трогать не нужно.

## Структура модуля

```
content/modules/NN-slug/
├── module.json      описание модуля (id, order, title, level, summary, objectives, tags)
├── lessons/         уроки, порядок = имя файла (01-*.md, 02-*.md ...)
│   └── 01-name.md
├── quiz.json        тест модуля
└── practice.json    практические задачи
```

`NN` (например `06-docker`) задаёт папку, а порядок в приложении — поле `order`
в `module.json`. Требования проверяет `tools/validate_content.py` и CI.

## module.json

```json
{
  "id": "docker",
  "order": 7,
  "title": "Docker и контейнеры",
  "level": "intermediate",
  "summary": "Одно-два предложения для дашборда.",
  "estimated_minutes": 220,
  "objectives": ["Чему научится студент — 3–5 пунктов"],
  "tags": ["docker", "контейнеры"]
}
```

## Урок

```markdown
---
id: unique-lesson-id
title: Заголовок урока
minutes: 40
---

# Заголовок

Текст с `командами`, таблицами, списками.

![Подпись](assets/img/docker-layers.svg)

!!! warning "Важно"
    Врезки: note / tip / warning / danger. Внутри поддерживается markdown и код.

```bash
docker build -t api:local .
```

## Проверьте себя

1. Вопрос для самопроверки.
```

Правила:
- минимум 1800 символов основного текста (проверяется CI);
- каждая картинка обязана существовать в `content/assets/img`;
- термины можно оборачивать в `[[docker]]` — они получат подсказку из глоссария;
- ключевые команды даются в блоках с указанием языка (`bash`, `yaml`, `json`, `ini`, `dockerfile`, `powershell`, `python`).

## quiz.json

```json
{
  "title": "Тест модуля 7: Docker",
  "pass_score": 75,
  "questions": [
    {
      "id": "q1",
      "type": "single",
      "question": "Текст вопроса",
      "options": ["A", "B", "C"],
      "answer": [1],
      "explanation": "Почему это верно и что не так с остальными.",
      "tags": ["containers"]
    },
    {
      "id": "q2",
      "type": "text",
      "question": "Введите ответ одним словом",
      "answer": ["sbom", "software bill of materials"],
      "explanation": "Пояснение."
    }
  ]
}
```

- `type`: `single` (ровно один ответ), `multiple` (несколько), `text` (текстовый).
- Ответы для `single`/`multiple` — **индексы** вариантов, начиная с нуля.
- Для `text` перечисляйте все допустимые формы ответа (регистр и лишние пробелы не важны).
- Пояснение обязательно: без него тест не проверяется в CI.

## practice.json

```json
{
  "title": "Практика модуля 7",
  "tasks": [
    {
      "id": "first-dockerfile",
      "title": "Написать безопасный Dockerfile",
      "level": "medium",
      "goal": "Что должно получиться и зачем это нужно.",
      "instructions": ["Шаг 1", "Шаг 2"],
      "hints": ["Подсказка, которая не выдаёт решение сразу"],
      "solution": "FROM python:3.12-slim\n...",
      "check": {
        "type": "regex_all",
        "patterns": ["FROM python", "USER\\s+app"],
        "feedback": "Что именно проверялось и почему это важно."
      },
      "validation_hint": "Как студент сам проверит результат: docker run --rm id"
    }
  ]
}
```

Типы проверки:
- `regex_all` — в ответе должны встретиться все шаблоны (регистр не учитывается);
- `regex_any` — достаточно одного из шаблонов;
- `equals` — ответ совпадает с одним из шаблонов (например `/etc`);
- `manual` — задача на самопроверку, обязательно заполните `validation_hint`.

**Главное требование:** эталонное решение должно проходить собственную проверку —
это тестируется (`tests/test_content.py::test_solution_matches_own_patterns`) и валидируется
в CI. Проверяйте локально:

```bash
python tools/validate_content.py
pytest tests/test_content.py -q
```

## Глоссарий

`content/glossary.json` — плоский список терминов:

```json
{"term": "Pod", "definition": "Минимальная единица запуска в Kubernetes...", "see_also": ["Deployment"], "where": "Модуль Kubernetes"}
```

## Иллюстрации

Схемы рисуются кодом, а не «руками», — так их проще править:

```bash
python tools/make_diagrams.py            # перегенерировать все SVG
```

Добавляя новую схему, используйте хелперы класса `Svg` (`box`, `label`, `arrow`, `path`),
затем проверьте результат: `xmllint` или тест `tests/test_content.py`.

## Чек-лист добавления контента

- [ ] `module.json` заполнен (порядок, цели, теги)
- [ ] уроки: front matter, 1800+ символов, картинки существуют
- [ ] вопросы: объяснение у каждого, ответы в диапазоне, 8+ вопросов
- [ ] задачи: решение, шаблоны проверки, подсказки, `validation_hint`, 3+ задач
- [ ] решение проходит автопроверку
- [ ] `python tools/generate_version.py --version "$(cat VERSION)"` (обновить index)
- [ ] `python tools/validate_content.py` и `pytest -q` — зелёные
