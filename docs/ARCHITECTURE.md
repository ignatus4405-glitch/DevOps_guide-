# Архитектура приложения

## Общая схема

```
┌──────────────────────── DevOpsAcademy (PySide6) ────────────────────────┐
│  ui/main_window.py        навигация, баннер обновления, экзамен         │
│  ui/dashboard.py          прогресс и дорожная карта                     │
│  ui/lesson_view.py        просмотр урока (QTextBrowser + CSS)           │
│  ui/quiz_widget.py        тест: вопросы, проверка, разбор               │
│  ui/practice_widget.py    интерфейс практики                            │
│  ui/glossary_dialog.py    глоссарий с поиском                           │
│  ui/update_dialog.py      уведомление о новой версии                    │
├─────────────────────────────────────────────────────────────────────────┤
│  content.py      модель курса: Course → Module → Lesson/Quiz/Practice    │
│  practice_checker.py проверка regex и argv-команд без исполнения          │
│  markdown_renderer.py  markdown → HTML (+admonitions, подсветка, [[терм]])│
│  progress.py     прогресс: schema, backup, atomic JSON, отчёты            │
│  updater.py      GitHub Releases: fail-closed SHA-256, .part, установка  │
│  theme.py        QSS-темы (dark/light) и CSS для урока                    │
│  paths.py        пути checkout, wheel и собранного exe                    │
│  version.py      версия (генерируется tools/generate_version.py)          │
└─────────────────────────────────────────────────────────────────────────┘
        ▲                                     ▲
        │ читает                              │ использует
┌───────┴────────────────┐          ┌─────────┴───────────────────────────┐
│ content/               │          │ tools/                              │
│  modules/NN-slug/      │          │  validate_content.py  проверка схемы│
│   module.json          │          │  generate_version.py  версия+index  │
│   lessons/*.md         │          │  next_version.py      номер релиза  │
│   quiz.json            │          │  release_notes.py     notes+CHANGELOG│
│   practice.json        │          │  make_update_manifest.py update.json │
│                        │          │  make_diagrams.py     SVG-схемы      │
│                        │          │  smoke_test.py        дымовой тест   │
│                        │          │  run_tests.py         тесты в CI      │
│                        │          │  ci_annotate.py       аннотации CI   │
│                        │          └─────────────────────────────────────┘
│  glossary.json         │
│  assets/img/*.svg      │
│  content_index.json    │  хеши файлов (для диагностики сборки)
└────────────────────────┘
```

## Поток данных

1. **Запуск** → `main.run()` → `Course.load(content_dir)`.
   Ошибка контента показывается диалогом, приложение не падает молча.
2. **Модуль** → `Module` c уроками, тестом и практикой; сортировка по `order`.
3. **Навигация по урокам** → кнопки «Следующий/Предыдущий» (`LessonView.set_navigation`)
   листают уроки сплошной лентой: границы модулей прозрачны, конец курса предлагает
   экзамен. `MainWindow.navigate_lesson()` сам переключает модуль и синхронизирует
   боковую панель.
4. **Урок** → `markdown_renderer.render_lesson()` превращает markdown в HTML,
   подставляя абсолютные пути к `content/assets/img/*.svg` (Qt сам рендерит SVG)
   и стилизуя таблицы инлайновыми стилями текущей темы (см. ниже).
5. **Тест** → `Question.is_correct()` сравнивает ответы; результат уходит в
   `ProgressStore.save_quiz_result()` и в дашборд.
6. **Практика** → `practice_checker.TaskChecker.check()` разбирает ответ по правилам задачи
   (для `commands` — argv-токены без выполнения shell), `ProgressStore.set_task_done()` фиксирует выполнение.
7. **Обновление** → `UpdateChecker` (QThread) опрашивает GitHub API; найденный релиз
   остаётся доступен из баннера. `DownloadWorker` требует SHA-256, пишет `.part` и
   атомарно публикует файл только после совпадения digest.

## Ключевые решения и почему так

| Решение | Причина |
| --- | --- |
| Контент — данные (JSON + markdown) | контент меняется без правки кода, легко ревьюить |
| Свой парсер front matter (без PyYAML) | меньше зависимостей в сборке |
| Своя подсветка кода (без Pygments) | компактный exe, предсказуемый результат |
| QTextBrowser вместо WebEngine | не тянет 150 МБ Chromium, офлайн-надёжность |
| Стили таблиц — инлайново в HTML, а не в QSS | QSS Qt не применяет границы к содержимому `QTextBrowser`; проверено рендером (`theme.lesson_css` + `markdown_renderer.style_tables`) |
| QSettings + versioned JSON-зеркало | восстановление из валидной копии; атомарная запись и статистика только по ключам курса |
| PyInstaller one-dir | быстрый старт, простая замена файлов при обновлении |
| Обновление через GitHub Releases API | не нужен свой сервер, публичный репозиторий — без токена |
| Wheel хранит `content/` как package data | `pip install` запускается вне checkout и остаётся офлайн |

## Тестирование

| Уровень | Файл | Что проверяет |
| --- | --- | --- |
| Контент | `tests/test_content.py` | структура, ссылки, решения проходят свои проверки |
| Рендер | `tests/test_markdown.py` | admonitions, подсветка, картинки, термины |
| Прогресс | `tests/test_progress.py` | сохранение, лучший результат, повреждённые данные |
| Проверка задач | `tests/test_task_checker.py` | типы проверок, командные токены и ложные совпадения |
| Обновления | `tests/test_updater.py`, `tests/test_updater_integrity.py` | версии, платформы, fail-closed SHA-256, атомарная загрузка |
| Инструменты | `tests/test_version_tooling.py` | генерация версии, индекс контента, независимость хешей от CRLF |
| Релиз | `tests/test_release_tools.py`, `tests/test_content_examples.py` | расчёт bump, YAML-практики, единый commit SHA |
| Wheel | `tests/test_packaging.py` + CI packaging job | версия metadata, ресурсы вне checkout |
| Заметки | `tests/test_release_notes.py` | группировка коммитов, запись в CHANGELOG |
| Запуск | `tests/test_launcher.py` | `run.py --version/--self-test/--help` |
| CI-обвязка | `tests/test_run_tests.py` | экранирование аннотаций, сводка упавших тестов |
| Сборка | `tests/test_entry_point.py` | журнал ошибок, потоки вывода, коды возврата, содержимое spec |
| Схемы | `tests/test_diagrams.py` | валидность SVG, все схемы используются в уроках, стрелки не заходят на панель |
| GUI | `tests/test_ui_smoke.py` | окно, все уроки, навигация сквозь темы, тесты, практика, экзамен, темы |

GUI-тесты работают в offscreen-режиме (`QT_QPA_PLATFORM=offscreen`) — их можно
запускать на сервере и в CI без дисплея.

## Расширение

- **Новый модуль** — см. `docs/CONTENT_GUIDE.md`.
- **Новый тип задания** — добавьте обработку в `practice_checker.TaskChecker.check()`
  и тест в `tests/test_task_checker.py`.
- **Новый источник обновлений** — замените `fetch_latest_release()` в `updater.py`.
- **Новая тема оформления** — словарь в `theme.py` + тест на контраст.
