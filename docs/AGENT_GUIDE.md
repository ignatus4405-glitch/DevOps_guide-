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
| CI/CD | `.github/workflows/**` | `docs/RELEASING.md` |
| Сборка | `packaging/**` | `docs/RELEASING.md`, проверить локальную сборку |

## Локальное окружение

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest -q                                            # 58 тестов
```

В headless-средах (сервер, контейнер) Qt требует библиотек; используйте
`QT_QPA_PLATFORM=offscreen`. Если не хватает системных библиотек (`libGL`, `libEGL`,
`libxkbcommon`), в CI они не нужны — там используется ubuntu-latest с установленными
зависимостями Qt.

## Как выпускается версия

Автоматически, см. `docs/RELEASING.md`. Вручную — Actions → **Build & Release** →
Run workflow (выбор bump). Отдельно тег ставить не нужно: релизный job делает тег сам.

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
