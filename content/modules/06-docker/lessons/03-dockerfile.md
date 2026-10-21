---
id: dockerfile
title: Dockerfile: слои, multistage, кэш
minutes: 30
---

# Dockerfile: слои, multistage, кэш

Dockerfile — это не «инструкция установки», а описание слоёв файловой системы.
Понимание слоёв объясняет размер образа, скорость сборки и утечки секретов.

## Слои и кэш

Каждая инструкция создаёт слой. Слой неизменяем и переиспользуется, если не
изменились входные данные и все предыдущие слои.

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-m", "app"]
```

Порядок критичен:

- `COPY requirements.txt` + `RUN pip install` → слой зависимостей;
- `COPY . .` → слой кода.

Изменили строку в `app.py` — пересобирается только последний слой. Скопировали
весь проект до установки — кэш зависимостей инвалидируется на каждом коммите.

## Multistage: сборка отдельно от запуска

```dockerfile
# --- build ---
FROM golang:1.23 AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /out/app ./cmd/app

# --- runtime ---
FROM gcr.io/distroless/static-debian12
COPY --from=build /out/app /app
USER nonroot:nonroot
ENTRYPOINT ["/app"]
```

Результат — образ в десятки раз меньше, без компилятора и исходников. Для Node:

```dockerfile
FROM node:20 AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
COPY --from=build /app/dist ./dist
COPY --from=build /app/node_modules ./node_modules
USER node
CMD ["node", "dist/server.js"]
```

## Базовые образы: что выбирать

| Образ | Размер | Плюсы | Минусы |
| --- | --- | --- | --- |
| `ubuntu` | ~80 МБ | знакомые утилиты | большая поверхность атак |
| `debian-slim` | ~30 МБ | компромисс | меньше утилит |
| `alpine` | ~5 МБ | маленький | musl, проблемы совместимости |
| `distroless` | ~2–20 МБ | минимальная поверхность | нет shell, сложнее отладка |

Для продакшена — slim/distroless, для отладки — отдельный образ или
`kubectl debug`. Наличие shell в проде — удобство для атакующего.

## Инструкции, которые важно понимать

| Инструкция | Замечание |
| --- | --- |
| `RUN` | выполняется при сборке, создаёт слой |
| `CMD` | команда по умолчанию, переопределяется аргументами |
| `ENTRYPOINT` | фиксированная команда, аргументы добавляются |
| `COPY` | копирует файлы (предпочтительнее `ADD`) |
| `ADD` | умеет tar и URL — редко нужен |
| `ARG` | доступен только при сборке |
| `ENV` | доступен в runtime |
| `HEALTHCHECK` | команда проверки (в Kubernetes чаще probes) |

`ENTRYPOINT ["/app"]` + `CMD ["--port", "8080"]` — правильная комбинация: команда
фиксирована, аргументы можно переопределить.

## .dockerignore

Без него в контекст сборки попадают `.git`, `node_modules`, `.env`, тестовые данные.
Это замедляет сборку и может утащить секреты.

```
.git
.env
node_modules
__pycache__
*.log
tests/
```

Проверка размера контекста: в логе `docker build` строка `transferring context`.
Большой контекст — сигнал, что `COPY . .` тащит лишнее.

## Секреты при сборке

```dockerfile
RUN --mount=type=secret,id=pipconf,target=/etc/pip.conf \
    pip install -r requirements.txt
```

```bash
docker build --secret id=pipconf,src=$HOME/.pip/pip.conf .
```

Секрет не попадает в слой. `ARG TOKEN` + `RUN echo $TOKEN` — утечка: значение
остаётся в истории образа (`docker history`).

## Проверка результата

```bash
docker image ls app
docker history app:latest | head
docker run --rm app:latest sh -c 'id; ls /'
```

Если `id` показывает `uid=0`, образ работает от root — это надо исправлять.
Если в `docker history` видны токены — образ нужно пересобрать.

## Как работает кэш сборки

Каждая инструкция создаёт слой. Docker переиспользует слой, если не изменилась
инструкция и её входные данные. Поэтому порядок важен:

```dockerfile
COPY package*.json ./
RUN npm ci
COPY . .
```

Зависимости ставятся до копирования кода, и слой с `npm ci` переиспользуется,
пока не изменился lock-файл.

### Что ломает кэш

- `COPY . .` в начале — любое изменение кода сбрасывает всё;
- `ARG` с меняющимся значением до тяжёлого шага;
- `apt-get update` без фиксации версий;
- изменяемые метаданные (дата) в слое.

### BuildKit

BuildKit строит граф шагов, кэширует по содержимому и умеет монтировать кэш
пакетных менеджеров:

```dockerfile
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt
```

Кэш не попадает в образ, но ускоряет сборку. `--cache-from`/registry cache
позволяет делить кэш между CI-раннерами.

### Размер и безопасность

- multistage: в финальный образ только runtime;
- `distroless`/`scratch` уменьшают поверхность атаки;
- фиксируйте digest базового образа;
- не копируйте `.git`, тесты и секреты;
- `.dockerignore` обязателен.

### Слои и неизменяемость

Образ неизменяем. Любое изменение — новый слой и новый digest. Тег «latest» —
указатель, который может измениться. Для воспроизводимости деплойте по digest.

## Подробный разбор темы

Слой кэшируется по инструкции и её входам, поэтому сначала копируйте lock-файл и устанавливайте зависимости, а исходный код добавляйте позже. Это ускоряет повторную сборку, но корректность зависит от полного набора входов. Multistage build отделяет компилятор и dev-зависимости от runtime-образа, уменьшая размер и поверхность атаки.

Не копируйте весь рабочий каталог без `.dockerignore`: туда могут попасть `.git`, local secrets и сборочные артефакты. Указывайте непривилегированного пользователя, фиксируйте базовый образ по версии или digest и проверяйте, что приложение получает корректный сигнал завершения через exec-form `CMD`. После изменения Dockerfile сравните размер слоя и просканируйте итоговый образ.

## Пошаговый сценарий

![Порядок действий: Dockerfile: слои, multistage, кэш](assets/img/howto/06-docker--03-dockerfile.svg)

1. Опишите build context и исключите локальные секреты через dockerignore.
2. Разместите стабильные lock-файлы раньше часто меняющегося исходного кода.
3. Соберите runtime stage отдельно от compiler и dev-зависимостей.
4. Проверьте размер, non-root пользователя и запуск итогового образа.

## Проверьте себя

1. Почему порядок COPY влияет на скорость сборки?
2. Что даёт multistage и когда он не нужен?
3. Чем ARG отличается от ENV с точки зрения безопасности?
4. Почему `COPY . .` без `.dockerignore` опасен?

!!! tip "Практика"
    Задача «Оптимизировать Dockerfile» в практикуме: сократить образ и сохранить
    кэш зависимостей.
