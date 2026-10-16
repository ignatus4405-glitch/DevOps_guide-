---
id: compose-and-security
title: Compose, безопасность и оптимизация
minutes: 40
---

# Compose, безопасность и оптимизация

## Docker Compose: несколько сервисов одной командой

```yaml
# compose.yaml
name: shop
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
    image: ghcr.io/org/shop-api:${TAG:-dev}
    environment:
      DATABASE_URL: postgresql://app:${DB_PASSWORD:?нужен пароль}@db:5432/shop
      LOG_LEVEL: ${LOG_LEVEL:-info}
    depends_on:
      db:
        condition: service_healthy     # ждать готовности, а не просто старт
    ports:
      - "127.0.0.1:8000:8000"          # публикуем только локально
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health')"]
      interval: 15s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits: { cpus: "1.0", memory: 512M }
    restart: unless-stopped

  worker:
    build: .
    command: ["python", "-m", "app.worker"]
    depends_on: { api: { condition: service_started } }

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD:?нужен пароль}
      POSTGRES_DB: shop
    volumes:
      - db-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d shop"]
      interval: 10s
      retries: 6
    restart: unless-stopped

volumes:
  db-data:
```

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f api
docker compose exec db psql -U app -d shop -c '\dt'
docker compose down                # остановить; -v удалит тома (данные!)
```

| Директива | Зачем |
| --- | --- |
| `depends_on: condition: service_healthy` | не стартовать API до готовности БД |
| `healthcheck` | основа для conditions и оркестраторов |
| `restart: unless-stopped` | самовосстановление после сбоя |
| `deploy.resources.limits` | защита хоста от «прожорливого» сервиса |
| `${VAR:?сообщение}` | падать, если переменная не задана — защита от пустой конфигурации |

!!! tip "Совет"
    В продакшене Compose применим на одной-двух машинах и для внутренних сервисов.
    Дальше — Kubernetes или managed-платформа. Важно, что приложение, упакованное в
    образ, переносится между ними без изменений.

## Безопасность контейнера: чек-лист

| Практика | Как делается | Почему |
| --- | --- | --- |
| Не запускать от root | `USER app`, `--user 1000:1000` | взлом контейнера не даёт root на хост |
| Read-only ФС | `--read-only --tmpfs /tmp` | изменение файлов атакующим невозможно |
| Убрать лишние capabilities | `--cap-drop ALL --cap-add NET_BIND_SERVICE` | минимум привилегий |
| Не давать доступ к docker.sock | не монтировать `/var/run/docker.sock` | это root на хосте |
| Ограничить ресурсы | `--memory`, `--cpus`, `--pids-limit` | защита от fork-bomb и утечек |
| Сканировать образы | `trivy image api:local` | CVE в базовом слое |
| Пинить версии базового образа | `python:3.12-slim` вместо `latest` | воспроизводимость |
| Отдельная сеть для БД | `docker network` + `internal: true` | БД недоступна из интернета |

```bash
# Безопасный запуск с лимитами и минимумом прав
docker run -d --name api \
  --read-only --tmpfs /tmp \
  --cap-drop ALL \
  --user 10001:10001 \
  --memory 512m --cpus 1 --pids-limit 256 \
  -p 127.0.0.1:8000:8000 \
  ghcr.io/org/shop-api:1.4.0

# Сканирование уязвимостей и проверка Dockerfile
trivy image --severity HIGH,CRITICAL ghcr.io/org/shop-api:1.4.0
hadolint Dockerfile
```

## Оптимизация размера и скорости

1. **Multi-stage build** — не тащить в прод компиляторы и dev-зависимости.
2. **Alpine/distroless** — маленькая база (но проверьте совместимость glibc/musl).
3. **`.dockerignore`** — исключить `.git`, `venv`, `node_modules`, `dist`, тестовые данные:

```gitignore
.git
.venv/
__pycache__/
*.pyc
tests/
docs/
*.log
.env
node_modules/
```

4. **Объединение RUN** с очисткой кэша пакетов в том же слое:

```dockerfile
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*
```

5. **Порядок слоёв** по частоте изменений: зависимости → код.

Результат измеряется, а не угадывается:

```bash
docker history --no-trunc api:local | head -20
docker images --format '{{.Repository}}:{{.Tag}} {{.Size}}'
```

## Образы и реестры в пайплайне

```yaml
# фрагмент GitHub Actions
      - name: Сборка multi-arch образа
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: ghcr.io/${{ github.repository }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          provenance: true          # аттестация сборки (supply chain)
```

Тегирование: **конкретный SHA коммита** (уникальный, неизменяемый), **semver-тег** для
релиза, `latest` — только для удобства людей, никогда для деплоя. В манифестах
деплоя используйте digest.

## Короткое резюме

- Compose описывает несколько сервисов, их зависимости, health-check и лимиты.
- Безопасность: не root, read-only, минимальные capabilities, лимиты, сканирование.
- Размер образа сокращается multi-stage, минимальной базой, `.dockerignore` и порядком слоёв.
- Для деплоя используйте неизменяемые теги (SHA/digest), а не `latest`.

## Проверьте себя

1. Почему монтирование `/var/run/docker.sock` в контейнер фактически даёт root на хост?
2. Что даёт `--read-only` и какие каталоги всё же нужно оставить записываемыми?
3. Чем плох тег `latest` в манифесте деплоя?
