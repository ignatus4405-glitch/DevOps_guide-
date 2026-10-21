---
id: volumes
title: Данные контейнера: volumes, bind mounts, state
minutes: 26
---

# Данные контейнера: volumes, bind mounts, state

Контейнер эфемерен: удалили — файловая система исчезла. Всё, что нужно сохранить,
должно лежать вне слоя контейнера. Это не деталь, а архитектурное решение.

## Три способа хранения

| Способ | Где живёт | Управление | Когда |
| --- | --- | --- | --- |
| volume | `/var/lib/docker/volumes` | Docker | данные приложений, БД |
| bind mount | любой путь хоста | вы | конфиги, разработка |
| tmpfs | память | Docker | кэш, секреты на время |

```bash
docker volume create pgdata
docker run -d --name db -v pgdata:/var/lib/postgresql/data postgres:16

docker run -d -v "$(pwd)/nginx.conf:/etc/nginx/nginx.conf:ro" nginx
docker run --tmpfs /tmp:rw,size=64m app
```

Named volume предпочтителен для данных: Docker управляет правами, его можно
бэкапить и переносить. Bind mount удобен для разработки (правки сразу видны), но
зависит от структуры хоста.

## Почему нельзя писать в слой контейнера

1. Данные исчезнут при `docker rm`.
2. Слой растёт и замедляет запуск.
3. В Kubernetes слой пода уничтожается при пересоздании.
4. Нельзя сделать бэкап независимо от контейнера.

Правило: **контейнер — stateless, состояние — снаружи**. Даже для логов: писать
в stdout, а собирать драйвером/log-агентом.

## Права и владельцы

Классическая ошибка: volume смонтирован, но приложение не может писать.

```
Permission denied: '/var/lib/postgresql/data'
```

Причины:

- volume создан с правами root, а контейнер работает от uid 1000;
- bind mount сохраняет uid хоста;
- SELinux блокирует доступ (нужен суффикс `:z`).

Решения:

```bash
docker run --user 1000:1000 -v data:/data app
# или заранее выставить владельца
docker run --rm -v data:/data busybox chown -R 1000:1000 /data
```

## Бэкап и восстановление

```bash
# бэкап тома через временный контейнер
docker run --rm -v pgdata:/data -v "$(pwd)":/backup \
  busybox tar czf /backup/pgdata.tar.gz -C /data .

# восстановление
docker run --rm -v pgdata:/data -v "$(pwd)":/backup \
  busybox tar xzf /backup/pgdata.tar.gz -C /data
```

Для баз данных файловый бэкап тома — не лучший вариант: нужен консистентный дамп
(`pg_dump`, `mysqldump`) или снапшот ФС. Копирование работающей БД может дать
битую копию.

## Volume в Compose

```yaml
services:
  db:
    image: postgres:16
    volumes:
      - pgdata:/var/lib/postgresql/data
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    secrets: [db_password]

volumes:
  pgdata:

secrets:
  db_password:
    file: ./secrets/db_password.txt
```

`docker compose down` удаляет контейнеры и сети, но **не** volumes. `down -v`
удаляет и данные — используйте осознанно.

## Данные в Kubernetes

Аналог named volume — PersistentVolumeClaim:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: pgdata
spec:
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 10Gi
```

Под монтирует claim; жизненный цикл данных не зависит от пода. Для баз используют
StatefulSet с `volumeClaimTemplates`, чтобы у каждого пода был свой том.

## Подробный разбор темы

Bind mount подключает конкретный путь хоста, а named volume управляется Docker и удобнее для переносимого runtime-хранилища. Оба варианта требуют решения по владельцу и правам: приложение внутри контейнера может иметь UID, который не совпадает с владельцем каталога на хосте. Проверьте mount mode и права до старта, особенно если используется read-only mount.

Контейнерный volume не является резервной копией. Определите согласованный snapshot, хранение вне узла и регулярное тестовое восстановление. Для базы данных учитывайте application-consistent backup и версию формата. Изменение образа не должно стирать данные, а удаление volume должно быть отдельным осознанным действием с подтверждением и планом восстановления.

## Пошаговый сценарий

![Порядок действий: Данные контейнера: volumes, bind mounts, state](assets/img/howto/06-docker--05-volumes.svg)

1. Разделите эфемерные данные, конфигурацию и постоянное хранилище.
2. Выберите named volume или bind mount с нужными правами.
3. Сделайте backup вне контейнера и подготовьте тестовое восстановление.
4. Проверьте данные после пересоздания контейнера и аварийного перезапуска.

## Проверьте себя

1. Чем named volume отличается от bind mount и что выбрать для БД?
2. Почему данные не должны жить в слое контейнера?
3. Как сделать бэкап тома?
4. Почему файловый бэкап работающей БД рискован?

!!! tip "Практика"
    Задача «Сохранить данные» в практикуме: поднять Postgres с named volume,
    пересоздать контейнер и убедиться, что данные на месте.
