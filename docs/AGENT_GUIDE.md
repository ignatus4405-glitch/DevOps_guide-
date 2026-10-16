# Инструкция для агентов и контрибьюторов

Этот документ — входная точка для любого, кто продолжает работу (человек или ИИ-агент).
Цель: изменения должны быть безопасными, воспроизводимыми и задокументированными.

## Правила работы

1. **Одна задача — одна ветка.** Имя: `feature/...`, `fix/...`, `content/...`, `ci/...`.
2. **Никогда не коммитьте секреты** — `.env`, ключи, токены. Перед коммитом:
   `gitleaks detect --source . --redact` (или pre-commit).
3. **Контент — только данные.** Правите `content/**` — запускайте
   `python tools/validate_content.py` и `python tools/generate_version.py`.
4. **Код приложения** — маленькие модули в `src/devops_academy/**`; любой новый
   функционал сопровождается тестом в `tests/`.
5. **Изменения в UI/контенте** проверяйте offscreen-тестом:
   `QT_QPA_PLATFORM=offscreen python tools/smoke_test.py`.
6. **Коммиты** — по Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`, `ci:`.
   Это влияет на автоматический подъём версии (feat → minor, BREAKING → major).
7. **Документируйте каждое изменение**: обновляйте `CHANGELOG.md` (в разделе
   «Unreleased» или прямо в новом релизе), `README.md` при изменениях интерфейса,
   `docs/*` при архитектурных решениях.
8. **Проверки перед PR:**

```bash
ruff check .
pytest -q
python tools/validate_content.py
QT_QPA_PLATFORM=offscreen python tools/smoke_test.py
python tools/generate_version.py --version "$(cat VERSION)" --build local   # если менялся content/
```

## Куда что класть

| Что меняете | Файлы | Что обязательно обновить |
| --- | --- | --- |
| Уроки, тесты, задачи | `content/modules/**` | `content_index.json`, `CHANGELOG.md` |
| Иллюстрации | `tools/make_diagrams.py` (код схемы) | перегенерировать SVG командой |
| Интерфейс | `src/devops_academy/ui/**` | тест в `tests/test_ui_smoke.py` |
| Модель контента | `src/devops_academy/content.py` | `tools/validate_content.py`, тесты |
| Обновления | `src/devops_academy/updater.py` | `tests/test_updater.py`, `docs/RELEASING.md` |
| CI/CD | `.github/workflows/**` | `docs/RELEASING.md`, проверить `python -c "import yaml,glob; yaml.safe_load(open(f))"` |
| Версии и релизы | `tools/next_version.py`, `tools/release_notes.py`, `tools/make_update_manifest.py` | `tests/test_release_tools.py`, `tests/test_release_notes.py` |
| Сборка | `packaging/**` | `docs/RELEASING.md`, проверить локальную сборку |

## Локальное окружение

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest -q                                            # 79 тестов
```

В headless-средах (сервер, контейнер) Qt требует библиотек; используйте
`QT_QPA_PLATFORM=offscreen`. Если не хватает системных библиотек (`libGL`, `libEGL`,
`libxkbcommon`), в CI они не нужны — там используется ubuntu-latest с установленными
зависимостями Qt.

## Как выпускается версия

Автоматически, см. `docs/RELEASING.md`. Вручную — Actions → **Build & Release** →
Run workflow (выбор bump). Отдельно тег ставить не нужно: релизный job делает тег сам.

## Если упал CI

1. `gh run list` → `gh run view <id>` — видно, какой шаг упал.
2. Логи скачиваются не всегда; сводка провала есть в аннотациях:
   `gh api repos/<owner>/<repo>/check-runs/<id>/annotations --jq '.[].message'`.
   Шаг pytest сам оставляет там последние строки вывода (`tools/ci_annotate.py`).
3. Полный лог — в артефакте `reports-<os>-<python>` (`reports/pytest.log`).
4. Перед пушем воспроизведите локально те же команды, что в workflow:
   `ruff check . && pytest -q && python tools/validate_content.py && python run.py --self-test`.
5. Особенности ОС (всё это уже ловили в CI, не повторяйте ошибок):
   - **Windows + CRLF**: git может выложить файлы с CRLF, поэтому хеши контента
     считаются от LF-версии (не читайте байты без `normalize_bytes`);
   - **Windows + кодировка**: стандартный вывод в cp1252 — печать русского текста
     падает с `UnicodeEncodeError`. В workflow заданы `PYTHONIOENCODING: utf-8` и
     `PYTHONUTF8: "1"`, а собственные скрипты вызывают `sys.stdout.reconfigure(encoding="utf-8")`;
   - **Windows + `Path.home()`**: игнорирует `HOME`, читает реальный профиль.
     Тесты обязаны изолировать данные (`monkeypatch.setattr(progress, "user_data_dir", ...)`
     и переменные `USERPROFILE`/`LOCALAPPDATA`/`APPDATA`), иначе прогресс «протекает» между тестами;
   - **Windows + вложенный pytest**: дочерний прогон без явных `--rootdir` и `--basetemp`
     уходит искать конфигурацию вверх по диску и спотыкается о `C:\Documents and Settings`
     (`PermissionError`); для тестов обёрток используйте подменяемый модуль pytest
     (`--pytest-module stub_pytest`);
   - **Ubuntu + Qt**: без `libgl1 libegl1 libxkbcommon0 libdbus-1-3` PySide6 не импортируется
     даже с `QT_QPA_PLATFORM=offscreen` (эти пакеты ставятся в обоих workflow);
   - **Ubuntu + bash шагов**: GitHub запускает bash с `-e`, поэтому проверки вида
     «запустить и обработать провал» пишите через `if ! command; then ...; fi`
     или запускайте из Python (`tools/run_tests.py`).

## Подводные камни

| Симптом | Причина | Решение |
| --- | --- | --- |
| Тест `test_solution_matches_own_patterns` падает | эталонное решение не проходит свои же regex | обновите `solution` или `patterns` |
| `content_index.json` помечен как изменённый в CI | контент правили без регенерации | `python tools/generate_version.py --version "$(cat VERSION)"` |
| GUI-тесты падают с ошибкой платформы | нет `QT_QPA_PLATFORM=offscreen` | выставьте переменную окружения |
| Сборка exe не находит контент | контент не попал в `datas` | проверьте `packaging/devops_academy.spec` |
| Обновление не приходит | репозиторий приватный или нет релиза | проверьте `releases/latest` в браузере |
| Версия не поднялась | в коммитах нет `feat:`/`BREAKING` | используйте Conventional Commits |

## Что уже сделано и что дальше

Актуальный статус — в `CHANGELOG.md` и `README.md`. Идеи развития:

- локализация интерфейса (i18n) и английская версия курса;
- режим проверки знаний с интервальным повторением (spaced repetition);
- импорт/экспорт прогресса для нескольких устройств;
- сборка для macOS (dmg) и AppImage для Linux-appimage;
- автотест контраста тем и доступности (a11y) в CI.
