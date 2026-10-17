# Как контрибьютить

Спасибо за интерес к проекту! Короткая версия правил — ниже, подробная — в
[docs/AGENT_GUIDE.md](docs/AGENT_GUIDE.md).

## Быстрый старт

```bash
git clone https://github.com/ignatus4405-glitch/DevOps_guide-.git
cd DevOps_guide-
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

## Перед pull request

```bash
ruff check .                      # линтер
pytest -q                         # 127 тестов
python tools/validate_content.py  # структура курса
QT_QPA_PLATFORM=offscreen python tools/smoke_test.py
```

Если правили контент — обновите индекс: `python tools/generate_version.py --version "$(cat VERSION)"`.

## Правила

- Ветка на задачу: `feature/...`, `fix/...`, `content/...`, `ci/...`, `docs/...`.
- Коммиты по [Conventional Commits](https://www.conventionalcommits.org/ru/):
  от них зависит автоматический номер версии.
- Никаких секретов в коде и истории.
- Изменения поведения сопровождаются тестами; изменения контента — валидацией.
- Описывайте в PR: что, зачем, как проверить, как откатить.

## Что можно улучшить прямо сейчас

- добавить модуль курса (см. [docs/CONTENT_GUIDE.md](docs/CONTENT_GUIDE.md));
- улучшить иллюстрации в `tools/make_diagrams.py`;
- расширить тесты (`tests/`) — особенно пограничные случаи автопроверки задач;
- улучшить документацию и примеры команд;
- предложить автоматизацию в CI (кэш, ускорение, новые проверки).

## Лицензия

Отправляя PR, вы соглашаетесь на распространение вклада по лицензии MIT (см. [LICENSE](LICENSE)).
