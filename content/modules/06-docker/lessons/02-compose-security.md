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

## Docker Compose: типичные ошибки

| Ошибка | Симптом | Решение |
| --- | --- | --- |
| `localhost` вместо имени сервиса | connection refused | использовать `db:5432` |
| нет healthcheck | приложение падает при старте | depends_on + condition |
| `.env` не в той директории | пустые переменные | `docker compose config` |
| порт занят | bind: address already in use | сменить `-p` или остановить процесс |
| volume с правами root | permission denied | `--user` или chown тома |

## Размер образа: что реально помогает

- multistage build;
- `--no-cache-dir` для pip, `npm ci --omit=dev`;
- удаление кэшей и документации в том же `RUN`;
- `.dockerignore`;
- distroless/slim-база;
- меньше слоёв (не «squash», а нормальная структура).

Проверка:

```bash
docker history --human app:latest
dive app:latest
```

`dive` показывает содержимое каждого слоя и помогает найти «мусор», добавленный
и не удалённый в следующем слое.

## Короткое резюме

- Compose описывает несколько сервисов, их зависимости, health-check и лимиты.
- Безопасность: не root, read-only, минимальные capabilities, лимиты, сканирование.
- Размер образа сокращается multi-stage, минимальной базой, `.dockerignore` и порядком слоёв.
- Для деплоя используйте неизменяемые теги (SHA/digest), а не `latest`.

## Подробный разбор темы

Compose описывает набор сервисов и их связи, но каждый сервис сохраняет собственную границу конфигурации, сети и секретов. Не передавайте секрет через обычный `environment`, если он окажется в inspect output или логе; используйте поддерживаемый механизм secret и ограничьте, какие сервисы его монтируют. Публикуйте на host только нужные порты, а внутренние компоненты оставляйте во внутренней сети.

Оптимизация должна исходить из профиля: минимизируйте build context через `.dockerignore`, используйте cache mounts там, где это помогает, и не устанавливайте отладочные инструменты в production image. В Compose можно включить dev-профиль отдельно от минимального runtime. Проверьте итоговую конфигурацию через `docker compose config` и убедитесь, что секреты не попали в вывод.

## Пошаговый сценарий

![Порядок действий: Compose, безопасность и оптимизация](assets/img/howto/06-docker--02-compose-security.svg)

1. Разделите сервисы, внутренние сети и опубликованные наружу порты.
2. Уберите secrets из environment, исходников и build context.
3. Ограничьте права и размер runtime-образа.
4. Проверьте итоговый Compose config и доступ только нужным компонентам.

## Пошаговое объяснение для новичка

Сначала выполните упражнение в учебной среде или на примере из урока. Если действие меняет реальные файлы, сервер или облако, сначала проверьте цель и подготовьте откат. После каждого шага сравните результат с проверкой ниже; при неожиданном результате остановитесь.

### Шаг 1

**Что сделать.** Откройте `compose.yaml` и отметьте, какие сервисы должны общаться внутри и какие порты нужны пользователю.

**Как проверить.** Наружу опубликован только нужный сервис; база данных не получила публичный порт без необходимости.

### Шаг 2

**Что сделать.** Выполните `docker compose config` и проверьте, что пароль не прописан прямо в YAML или env-файле, который попадёт в Git.

**Как проверить.** Конфигурация собрана корректно, а реальные secrets поступают из безопасного источника.

### Шаг 3

**Что сделать.** Запускайте контейнер не от root и выдавайте только необходимые права и каталоги.

**Как проверить.** Внутри контейнера процесс имеет минимальные права; ему не открыт весь диск хоста.

### Шаг 4

**Что сделать.** Проверьте сеть и конфигурацию командой `docker compose config` и запросом только к разрешённому сервису.

**Как проверить.** Контейнеры видят нужные друг друга, а ненужные порты снаружи закрыты.

## Проверьте себя

1. Почему монтирование `/var/run/docker.sock` в контейнер фактически даёт root на хост?
2. Что даёт `--read-only` и какие каталоги всё же нужно оставить записываемыми?
3. Чем плох тег `latest` в манифесте деплоя?
