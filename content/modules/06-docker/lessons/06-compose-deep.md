---
id: compose-deep
title: Compose для локального стека: зависимости, профили, healthcheck
minutes: 28
---

# Compose для локального стека: зависимости, профили, healthcheck

Compose описывает многоконтейнерное приложение одним файлом. Это стандарт для
локальной разработки и небольшого продакшена, но у него есть тонкости, из-за
которых «поднимается не всё».

## Базовая структура

```yaml
services:
  api:
    build:
      context: ./api
      dockerfile: Dockerfile
    env_file: .env
    ports: ["8080:8080"]
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/healthz"]
      interval: 10s
      timeout: 3s
      retries: 5
      start_period: 20s

  db:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD:?set DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      retries: 10

  redis:
    image: redis:7-alpine

volumes:
  pgdata:
```

## depends_on не ждёт готовности

`depends_on` без `condition` гарантирует только **порядок запуска**, а не
готовность. Postgres стартует 2–5 секунд, приложение падает раньше.

Правильно — healthcheck + `condition: service_healthy`. Для приложений, которые
не умеют ждать, добавьте retry в коде или `wait-for-it`/`dockerize`.

## Переменные и .env

```bash
# .env
DB_PASSWORD=secret
API_URL=http://localhost:8080
```

Compose читает `.env` автоматически. `${VAR:?message}` падает с понятной ошибкой,
если переменная не задана, — лучше, чем тихо пустое значение.

Не коммитьте `.env`: добавьте в `.gitignore` и используйте `.env.example` с
описанием переменных.

## Профили

Не все сервисы нужны каждый раз. Профили включают их по требованию:

```yaml
services:
  debug:
    image: busybox
    profiles: [debug]
  mailhog:
    image: mailhog/mailhog
    profiles: [dev]
```

```bash
docker compose --profile debug up
docker compose up            # без debug и mailhog
```

## Compose в CI и на сервере

```bash
docker compose -f compose.yaml -f compose.prod.yaml up -d
docker compose ps
docker compose logs -f api
docker compose down
```

Overrides через несколько `-f` позволяют держать базовую конфигурацию и
окруженческие отличия. Не дублируйте весь файл — переопределяйте только отличия.

## Ограничения ресурсов

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
```

Ограничения важны и локально: один сервис с утечкой памяти иначе «съест» хост.
В Docker Compose (не Swarm) `deploy.resources` частично поддерживается; надёжнее
`mem_limit`/`cpus` в старых версиях, но современный Compose понимает оба варианта.

## Полезные команды

```bash
docker compose config          # проверка и итоговая конфигурация
docker compose up -d --build
docker compose exec api sh
docker compose run --rm api pytest
docker compose top
docker compose pull
```

`docker compose config` — лучший способ увидеть, какие переменные подставились.
Часто «не работает» означает, что `.env` лежит не в той директории.

## Проверьте себя

1. Почему `depends_on` без condition недостаточно?
2. Зачем нужны профили?
3. Что проверяет `docker compose config`?
4. Какая разница между `down` и `down -v`?

!!! tip "Практика"
    Задача «Compose-стек с healthcheck» в практикуме: поднять api+db+redis с
    ожиданием готовности базы.
