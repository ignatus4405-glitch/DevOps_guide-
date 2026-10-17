---
id: github-actions-deep
title: GitHub Actions: workflow, job, matrix, reusable
minutes: 30
---

# GitHub Actions: workflow, job, matrix, reusable

GitHub Actions — самый доступный CI: он уже рядом с кодом и не требует отдельного
сервера. Но у него есть особенности, без которых workflow получаются медленными и
небезопасными.

## Анатомия

| Понятие | Что это |
| --- | --- |
| workflow | YAML-файл в `.github/workflows/` |
| event | триггер (`push`, `pull_request`, `schedule`, `workflow_dispatch`) |
| job | набор шагов на одном раннере |
| step | одна команда или action |
| action | переиспользуемое расширение (`uses:`) |
| runner | машина, где выполняется job |

Job'ы по умолчанию параллельны. `needs` задаёт порядок, `outputs` передаёт данные.

## Триггеры

```yaml
on:
  push:
    branches: [main]
    paths: ['src/**', 'pyproject.toml']
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 6 * * 1'      # каждый понедельник в 06:00 UTC
  workflow_dispatch:
    inputs:
      environment:
        type: choice
        options: [staging, prod]
```

Осторожно с `pull_request_target` — он запускается в контексте базовой ветки с
доступом к секретам. Никогда не делайте checkout кода PR в таком workflow без
явной проверки.

## Кэш и артефакты

```yaml
- uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: pip-${{ hashFiles('requirements*.txt') }}

- uses: actions/upload-artifact@v4
  with:
    name: dist
    path: dist/
    retention-days: 7
```

Кэш ускоряет повторные запуски, артефакт передаёт результат между job'ами.
Срок хранения артефактов влияет на стоимость и на доступность истории.

## Матрица и включения

```yaml
strategy:
  fail-fast: false
  matrix:
    python: ["3.11", "3.12"]
    include:
      - python: "3.12"
        experimental: true
```

`include` добавляет комбинации, `exclude` убирает. Не используйте матрицу для
секретов — они не должны зависеть от параметров.

## Переиспользуемые workflow

Вместо копирования YAML:

```yaml
# .github/workflows/ci.yml
on:
  workflow_call:
    inputs:
      python-version:
        type: string
        default: "3.12"

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ inputs.python-version }}
      - run: pytest -q
```

Вызов:

```yaml
jobs:
  ci:
    uses: ./.github/workflows/ci.yml
    with:
      python-version: "3.12"
```

Для повторяющихся шагов внутри job'а — composite action:

```yaml
# .github/actions/setup/action.yml
runs:
  using: composite
  steps:
    - uses: actions/setup-python@v5
      with:
        python-version: "3.12"
    - run: pip install -r requirements-dev.txt
      shell: bash
```

## Права и безопасность

```yaml
permissions:
  contents: read
  id-token: write
```

Принцип наименьших привилегий: по умолчанию `GITHUB_TOKEN` имеет широкие права.
Ограничьте их на уровне workflow.

Правила:

- пиньте сторонние action'ы по SHA, а не по тегу (`@v4` может измениться);
- не выполняйте скрипты из PR с секретами;
- не логируйте `env`;
- используйте `environment` для prod с обязательным approval;
- включайте Dependabot для action'ов.

## Отладка

```yaml
- run: echo "event=${{ github.event_name }} ref=${{ github.ref }}"
- run: env | sort
```

Если job падает без логов — включите debug-логирование секретами
`ACTIONS_STEP_DEBUG=true` и `ACTIONS_RUNNER_DEBUG=true`.

Локальный запуск: `act` (ограниченная совместимость, но удобен для простых
workflow).

## Проверьте себя

1. Чем `workflow_call` отличается от копирования YAML?
2. Почему `pull_request_target` опасен?
3. Зачем ограничивать `permissions`?
4. Почему сторонние action'ы стоит пинговать по SHA?

!!! tip "Практика"
    Задача «Переиспользуемый workflow» в практикуме: вынести тесты в отдельный
    workflow и вызвать его из CI.
