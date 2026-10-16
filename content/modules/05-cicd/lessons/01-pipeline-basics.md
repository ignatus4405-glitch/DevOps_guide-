---
id: pipeline-basics
title: Как устроен CI/CD-пайплайн
minutes: 40
---

# Как устроен CI/CD-пайплайн

**Непрерывная интеграция (CI)** — каждое изменение автоматически проверяется:
собирается, тестируется, сканируется. **Непрерывная доставка (CD)** — проверенное
изменение автоматически попадает в окружение (staging, затем prod).

![Конвейер поставки](assets/img/cicd-pipeline.svg)

## Задачи, которые решает пайплайн

| Этап | Что делает | Инструменты |
| --- | --- | --- |
| Проверка кода | линтеры, формат, типы | ruff, flake8, shellcheck, hadolint |
| Тесты | unit, integration, e2e | pytest, jest, go test |
| Сборка | артефакт, Docker-образ | buildx, gradle, npm |
| Безопасность | SAST, зависимости, SBOM | semgrep, trivy, dependabot |
| Публикация | реестр образов, релизы | GHCR, ECR, GitLab Registry |
| Деплой | staging/prod, миграции | kubectl, terraform, ansible |
| Наблюдение | проверка после выката | smoke-тесты, метрики |

## GitHub Actions: анатомия workflow

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

concurrency:                      # отменяем устаревшие запуски на той же ветке
  group: ci-${{ github.ref }}
  cancel-in-progress: true

permissions:                      # принцип наименьших привилегий по умолчанию
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false            # не отменять остальные версии при ошибке одной
      matrix:
        python: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python }}
          cache: pip               # кэш зависимостей — самая дешёвая оптимизация
      - name: Установить зависимости
        run: pip install -r requirements-dev.txt
      - name: Линтер
        run: ruff check .
      - name: Тесты
        run: pytest -q
      - name: Загрузить отчёт
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: test-report-${{ matrix.python }}
          path: reports/
```

Ключевые понятия: **workflow** (файл), **job** (блок задач, обычно на своей машине),
**step** (шаг внутри job), **runner** (машина, где выполняется), **trigger**
(`on:` — push, PR, расписание, ручной запуск).

```yaml
on:
  schedule: [{ cron: "0 3 * * 1" }]   # каждый понедельник в 03:00
  workflow_dispatch:                   # кнопка «запустить вручную»
```

## Переменные, секреты, окружения

```yaml
env:
  GLOBAL: значение            # на весь workflow

jobs:
  deploy:
    environment: production   # требует approval-правил из настроек репозитория
    env:
      APP_ENV: production
    steps:
      - run: echo "версия ${{ github.ref_name }}"
      - name: Логин в реестр
        run: echo "${{ secrets.REGISTRY_TOKEN }}" | docker login ghcr.io -u ${{ github.actor }} --password-stdin
```

| Что | Где хранить | Особенности |
| --- | --- | --- |
| Не секрет (URL, регион) | `env` / Variables | видно в логах |
| Секрет | Secrets (или vault) | маскируется в логах, но не в артефактах |
| Разные значения по среде | Environments | approval, отдельные секреты |

!!! danger "Осторожно"
    Секреты из pull request от форков **не передаются** — это защита. Никогда не
    используйте `pull_request_target` с checkout чужого кода и секретами: это прямой
    путь к краже токена. И не печатайте секреты (`echo`), даже «для отладки» —
    маскировка не спасает при передаче в файлы и артефакты.

## Кэш, время сборки, стоимость

1. **Кэшируйте зависимости** (`cache: pip`, `actions/cache` по хешу lock-файла).
2. **Отменяйте устаревшие запуски** (`concurrency.cancel-in-progress`) — экономит минуты.
3. **Разделяйте быстрые и медленные проверки:** линтер (10 с) → unit (1 мин) → e2e (по расписанию).
4. **Параллельность:** независимые job стартуют одновременно; зависимые — через `needs`.
5. **Path-фильтры:** не запускать весь пайплайн, если изменилась только документация.

```yaml
on:
  push:
    paths-ignore: ["docs/**", "*.md"]
```

## Артефакты и релизы

```yaml
  build:
    needs: test                    # сборка только после зелёных тестов
    steps:
      - run: python -m build
      - uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/*
          retention-days: 14
```

Артефакт — это «собранный один раз и проверенный» результат. Правило: **собираем
один раз, деплоим тот же артефакт** во все окружения (никаких пересборок «на прод»).

## Короткое резюме

- CI проверяет каждое изменение, CD доставляет проверенное.
- Workflow = jobs + steps + runners; триггеры — push, PR, расписание, вручную.
- Секреты хранят в Secrets/Environments; PR из форков их не получает.
- Быстрый фидбэк строится на кэше, отмене устаревших запусков и разделении проверок.

## Проверьте себя

1. Почему артефакт собирают один раз, а не заново для каждого окружения?
2. Чем опасен `pull_request_target` с checkout кода из форка?
3. Что даёт `concurrency.cancel-in-progress` и как измерить эффект?
