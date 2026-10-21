---
id: images-and-containers
title: Образы, контейнеры и слои
minutes: 40
---

# Образы, контейнеры и слои

**Контейнер — это процесс (или группа процессов) Linux, изолированный пространствами
имён (namespaces) и ограниченный cgroups.** Никакой «лёгкой виртуальной машины»
внутри нет: ядро общее, поэтому контейнер стартует за миллисекунды.

![Слои образа](assets/img/docker-layers.svg)

## Три сущности, которые важно различать

| Термин | Что это | Аналогия |
| --- | --- | --- |
| Образ (image) | неизменяемый набор слоёв (файловая система) | класс |
| Контейнер | запущенный экземпляр образа + writable layer | объект |
| Реестр (registry) | хранилище образов (Docker Hub, GHCR, ECR) | репозиторий пакетов |

```bash
docker pull nginx:1.27-alpine           # скачать образ
docker images                           # что есть локально
docker run -d --name web -p 8080:80 nginx:1.27-alpine
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
docker exec -it web sh                  # зайти внутрь (для nginx-alpine это sh)
docker logs -f web                      # логи процесса
docker inspect web | jq '.[0].State'    # состояние и параметры
docker stats --no-stream                # потребление ресурсов
docker stop web && docker rm web        # остановить и удалить
docker rmi nginx:1.27-alpine            # удалить образ
```

!!! note "Что общего у контейнера и процесса"
    Первый процесс в контейнере (PID 1) обязан корректно обрабатывать сигналы. Если
    в Dockerfile написано `CMD python app.py` (shell-форма), PID 1 — это `sh`,
    который не пробросит SIGTERM приложению, и контейнер будет ждать 10 секунд до
    SIGKILL. Поэтому используйте **exec-форму**: `CMD ["python", "app.py"]`.

## Внутреннее устройство: namespaces и cgroups

| Механизм | Что изолирует/ограничивает |
| --- | --- |
| namespaces | PID, сеть, монтирования, UTS (hostname), IPC, пользователи |
| cgroups | CPU, память, дисковый I/O, количество процессов |
| overlayfs | слоистая файловая система с copy-on-write |
| capabilities | набор привилегий вместо всемогущего root |

Отсюда практические выводы: у контейнера **своя сеть** (порты надо публиковать),
**своя файловая система** (изменения исчезают вместе с контейнером, нужны тома) и
**лимиты** (иначе контейнер может «съесть» хост).

## Слои и кэш сборки

Каждая инструкция `RUN`/`COPY`/`ADD` создаёт слой. Docker кэширует слои: если
изменился слой, все последующие пересобираются.

```dockerfile
# Плохо: любое изменение кода переустанавливает зависимости
COPY . /app
RUN pip install -r requirements.txt

# Хорошо: сначала зависимости, потом код
COPY requirements.txt /app/
RUN pip install -r /app/requirements.txt
COPY app/ /app/app/
```

## Dockerfile: производственная версия

```dockerfile
# ---------- этап сборки ----------
FROM python:3.12-slim AS build
WORKDIR /build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
COPY requirements.txt .
RUN python -m venv /venv && /venv/bin/pip install -r requirements.txt

# ---------- финальный этап ----------
FROM python:3.12-slim
LABEL org.opencontainers.image.title="api" \
      org.opencontainers.image.source="https://github.com/org/api"

# Непривилегированный пользователь
RUN groupadd -r app && useradd -r -g app -d /app app
WORKDIR /app
COPY --from=build /venv /venv
COPY --chown=app:app app/ /app/app/

ENV PATH="/venv/bin:$PATH" PYTHONUNBUFFERED=1
USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=2).status==200 else 1)"

CMD ["python", "-m", "app"]
```

Что здесь важно и почему:

| Решение | Зачем |
| --- | --- |
| multi-stage build | в финальный образ не попадают компиляторы и тесты: размер меньше в 3–10 раз |
| `slim`-базовый образ | меньше CVE и меньше поверхность атаки |
| порядок COPY | максимальное использование кэша слоёв |
| `USER app` | запуск не от root — требование безопасности |
| exec-форма CMD | корректная обработка сигналов, быстрая остановка |
| HEALTHCHECK | оркестратор видит реальное состояние приложения |
| `PYTHONUNBUFFERED` | логи появляются сразу, а не по буферу |

```bash
docker build -t api:local .
docker history api:local               # размер каждого слоя
docker image inspect api:local --format '{{.Size}}'
```

!!! danger "Осторожно"
    Никогда не кладите секреты в `ENV`/`COPY`: они остаются в слоях образа и видны
    через `docker history`. Секреты передают в рантайме (переменные окружения из
    Secret, `--mount=type=secret` при сборке) или запрашивают из vault.

## Сети и порты

```bash
docker network create app-net
docker run -d --name db --network app-net -e POSTGRES_PASSWORD=dev postgres:16
docker run -d --name api --network app-net -p 8000:8000 myapi:local
docker exec api getent hosts db        # внутри сети контейнеры видят друг друга по имени
docker network inspect app-net --format '{{range .Containers}}{{.Name}} {{end}}'
```

Публикация (`-p 8000:8000`) нужна только для доступа **снаружи**. Внутри одной
пользовательской сети контейнеры общаются по именам через встроенный DNS Docker.

## Тома: где живут данные

```bash
docker volume create app-data
docker run -d --name db -v app-data:/var/lib/postgresql/data postgres:16   # именованный том
docker run --rm -v "$PWD/conf:/etc/nginx/conf.d:ro" nginx:1.27-alpine      # bind-mount
docker volume ls && docker volume inspect app-data
```

| Тип | Когда использовать |
| --- | --- |
| named volume | данные БД, состояние, которое должно пережить контейнер |
| bind mount | конфиги для локальной разработки, `-v .:/app` |
| tmpfs | временные данные в памяти |

## Диагностика контейнеров

```bash
docker logs --tail 100 --since 10m api
docker inspect api --format '{{.State.ExitCode}} {{.State.OOMKilled}}'
docker exec -it api sh -c 'ps aux; netstat -tulpn 2>/dev/null || ss -tulpn'
docker stats api
docker events --filter container=api        # события в реальном времени
docker run --rm -it --entrypoint sh api:local   # зайти в образ, который падает
```

Частые причины «контейнер сразу завершается»: опечатка в `CMD`, приложение
завершилось (это не сервис), неверный рабочий каталог, отсутствующий конфиг,
`OOMKilled=true` (не хватило памяти).

## Как устроен контейнер

Контейнер — это процесс, запущенный с изолированными пространствами имён
(namespaces) и ограничениями cgroups. Ядро у всех общее, поэтому контейнер легче
ВМ, но и изоляция слабее.

| Namespace | Что изолирует |
| --- | --- |
| pid | процессы (в контейнере PID 1 — ваше приложение) |
| net | сетевые интерфейсы и порты |
| mnt | точки монтирования |
| uts | hostname |
| ipc | разделяемая память |
| user | uid/gid (rootless) |

Проверить изоляцию:

```bash
docker run --rm alpine ps aux
docker run --rm alpine ip addr
docker run --rm --pid=host alpine ps aux   # видит процессы хоста (опасно)
```

`--pid=host`, `--privileged`, `--network=host` ломают изоляцию. Их используют
осознанно и не в продакшене.

## Registry: где живут образы

```bash
docker login ghcr.io
docker tag app:local ghcr.io/org/app:1.4.2
docker push ghcr.io/org/app:1.4.2
docker pull ghcr.io/org/app:1.4.2
```

Тег — человекочитаемое имя, digest — неизменяемый идентификатор:

```bash
docker inspect --format='{{index .RepoDigests 0}}' app:1.4.2
```

Для продакшена лучше деплоить по digest: тег можно перезаписать, digest — нет.

## Очистка места

Образы и слои занимают гигабайты:

```bash
docker system df
docker image prune -f
docker system prune -af --volumes   # осторожно: удалит неиспользуемые volumes
```

На CI-раннерах очистка обязательна: диск 50 ГБ забивается за несколько недель.

## Короткое резюме

- Контейнер — изолированный процесс; образ — неизменяемые слои.
- Порядок инструкций в Dockerfile определяет эффективность кэша и размер образа.
- Секреты не хранят в образе; процессы запускают не от root, `CMD` — в exec-форме.
- Данные живут в томах, диагностика — через logs/inspect/exec/stats.

## Подробный разбор темы

Образ состоит из неизменяемых слоёв и метаданных запуска; контейнер добавляет тонкий writable layer. Изменение данных внутри контейнера не обновляет образ и обычно исчезает при удалении контейнера. Поэтому runtime-файлы конфигурации и постоянные данные нужно размещать осознанно — в volume, bind mount или внешнем сервисе.

Тег вроде `latest` удобен для эксперимента, но может указывать на разный образ в разные дни. Для повторяемого выката фиксируйте версию и digest, а в release manifest связывайте их с commit. Перед публикацией проверьте архитектуру образа, entrypoint, пользователя и наличие ожидаемых файлов; успешная сборка не доказывает, что контейнер корректно стартует в production.

## Пошаговый сценарий

![Порядок действий: Образы, контейнеры и слои](assets/img/howto/06-docker--01-images-containers.svg)

1. Определите базовый образ, версию и архитектуру целевого runtime.
2. Соберите образ и проверьте слои, пользователя и entrypoint.
3. Запустите контейнер с временным тестовым вводом и нужными ресурсами.
4. Проверьте логи, порт и поведение данных после удаления контейнера.

## Пошаговое объяснение для новичка

Сначала выполните упражнение в учебной среде или на примере из урока. Если действие меняет реальные файлы, сервер или облако, сначала проверьте цель и подготовьте откат. После каждого шага сравните результат с проверкой ниже; при неожиданном результате остановитесь.

### Шаг 1

**Что сделать.** Выберите официальный базовый образ и конкретный tag; запишите CPU архитектуру, на которой образ будет запущен.

**Как проверить.** Образ не использует случайный `latest`, а платформа соответствует тестовой машине или production.

### Шаг 2

**Что сделать.** Соберите образ и выполните `docker image inspect имя:tag`; посмотрите размер и команду запуска.

**Как проверить.** Известно, каким пользователем и какой командой стартует контейнер; в образ не попали файлы с хоста.

### Шаг 3

**Что сделать.** Запустите учебный контейнер с `docker run --rm` и ограниченным портом/ресурсами.

**Как проверить.** Приложение отвечает, а после выхода временный контейнер удалён; хостовые данные не затронуты.

### Шаг 4

**Что сделать.** Посмотрите `docker logs` и проверьте, что данные, которые должны жить дольше контейнера, сохранены в volume.

**Как проверить.** После удаления контейнера логи доступны, а постоянные данные переживают пересоздание только в ожидаемом томе.

## Проверьте себя

1. Почему `CMD python app.py` мешает быстрой остановке контейнера?
2. Как multi-stage build уменьшает размер образа?
3. Где окажутся данные, если не подключить том, и почему это опасно?
