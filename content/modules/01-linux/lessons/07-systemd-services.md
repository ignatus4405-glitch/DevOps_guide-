---
id: systemd-services
title: systemd: юниты, зависимости и journald
minutes: 30
---

# systemd: юниты, зависимости и journald

systemd — не «ещё одна инициализация», а менеджер служб и ресурсов: он запускает
процессы, следит за ними, собирает логи, управляет таймерами и ограничивает
ресурсы. В Kubernetes и контейнерах те же идеи (декларация желаемого состояния и
перезапуск при сбое) реализованы иначе, но понимание systemd остаётся базой для
любого Linux-хоста.

## Анатомия юнита

Юнит — файл с декларацией. Типы: `service`, `timer`, `socket`, `mount`, `target`,
`path`. Основные секции сервиса:

```ini
[Unit]
Description=Backend API
After=network-online.target postgresql.service
Wants=network-online.target

[Service]
Type=simple
User=app
WorkingDirectory=/opt/app
EnvironmentFile=/etc/app/app.env
ExecStart=/opt/app/bin/server --port 8080
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=3
TimeoutStopSec=20

[Install]
WantedBy=multi-user.target
```

Разбор ключевых строк:

- **`After`** — порядок запуска, но не гарантия, что зависимость *запустится*.
  Для «запусти вместе» нужен `Wants` или `Requires`.
- **`Type=simple`** — systemd считает сервис запущенным сразу после `ExecStart`.
  Если приложение долго инициализируется, используйте `Type=notify` (приложение
  сообщает о готовности) или `Type=exec`.
- **`Restart=on-failure`** — перезапуск только при ненулевом коде или сигнале.
  `always` перезапустит и после корректного выхода — это может скрыть ошибку.
- **`EnvironmentFile`** — секреты и настройки вне юнита, с правами `600`.

## Куда класть файлы

| Каталог | Назначение |
| --- | --- |
| `/etc/systemd/system/*.service` | локальные юниты администратора |
| `/usr/lib/systemd/system/` | юниты из пакетов |
| `/etc/systemd/system/<unit>.d/*.conf` | drop-in дополнения |

Drop-in — правильный способ изменить чужой юнит, не редактируя файл пакета:

```bash
sudo systemctl edit app.service      # создаёт override.conf
sudo systemctl daemon-reload
```

Команда `systemctl edit` открывает редактор и сама создаёт нужный каталог.
`daemon-reload` обязателен после изменения юнитов, иначе systemd продолжит
использовать старую версию.

## Управление и диагностика

```bash
systemctl status app            # состояние, последние строки лога
systemctl start|stop|restart app
systemctl enable --now app      # автозапуск + запуск сейчас
systemctl is-enabled app
systemctl list-units --failed
systemctl list-dependencies app
```

Если сервис не стартует:

1. `systemctl status app` — код выхода и причина.
2. `journalctl -u app -n 100 --no-pager` — логи.
3. `systemd-analyze verify /etc/systemd/system/app.service` — проверка синтаксиса.
4. `journalctl -b -p err` — все ошибки с момента загрузки.

## journald: логи без файлов

systemd собирает stdout/stderr сервисов в журнал. Его не нужно ротировать
вручную, но нужно ограничивать:

```ini
# /etc/systemd/journald.conf
SystemMaxUse=2G
MaxRetentionSec=30day
```

Полезные запросы:

```bash
journalctl -u app --since "1 hour ago"
journalctl -u app -f                     # аналог tail -f
journalctl -p err -b                     # ошибки текущей загрузки
journalctl --disk-usage
journalctl -o json-pretty -n 1           # структурированная запись
```

`journalctl` умеет фильтровать по полям: `_PID`, `_SYSTEMD_UNIT`, `PRIORITY`.
Это удобнее grep по тексту, но требует структурированных логов от приложения.

## Таймеры вместо cron

systemd-таймер — современная замена cron с логами и зависимостями.

```ini
# /etc/systemd/system/backup.timer
[Unit]
Description=Ночной бэкап

[Timer]
OnCalendar=*-*-* 03:30:00
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
```

```ini
# /etc/systemd/system/backup.service
[Unit]
Description=Бэкап базы

[Service]
Type=oneshot
ExecStart=/opt/scripts/backup.sh
```

`Persistent=true` догоняет пропущенный запуск после выключения машины,
`RandomizedDelaySec` размазывает нагрузку. Проверка:

```bash
systemctl list-timers --all
systemd-analyze calendar "*-*-* 03:30:00"
```

## Ресурсные ограничения юнита

```ini
[Service]
MemoryMax=512M
CPUQuota=50%
TasksMax=256
ProtectSystem=strict
PrivateTmp=true
NoNewPrivileges=true
```

Это те же cgroups, что использует Kubernetes. `ProtectSystem=strict` делает
файловую систему только для чтения, кроме явно разрешённых путей
(`ReadWritePaths=`). Даже без контейнера сервис можно изолировать почти так же.

## Подробный разбор темы

В unit-файле разделяйте порядок и зависимость. `After=` задаёт порядок запуска, но не подтягивает другую службу; `Wants=` и `Requires=` задают зависимости с разной строгостью. Поэтому приложение, которому нужна сеть, часто требует `After=network-online.target` и корректного ожидания готовности, а не только факта, что интерфейс поднят.

После редактирования файла выполните `systemctl daemon-reload`, проверьте итоговую конфигурацию через `systemctl cat` и `systemd-analyze verify`, затем смотрите `systemctl show` и `journalctl -u`. Избегайте бесконечного рестарта: задайте разумные `RestartSec` и лимит стартов, а причину падения устраните. Для логов учитывайте ротацию и объём: journald тоже потребляет диск, если retention не настроен.

## Пошаговый сценарий

![Порядок действий: systemd: юниты, зависимости и journald](assets/img/howto/01-linux--07-systemd-services.svg)

1. Посмотрите итоговый unit, пользователя, команды запуска и зависимости.
2. Проверьте синтаксис и связь порядка с реальными зависимостями.
3. После изменения выполните daemon-reload и безопасно перезапустите unit.
4. Сверьте status, exit code и свежие записи journald.

## Проверьте себя

1. Чем `After` отличается от `Wants`?
2. Зачем нужен `daemon-reload` и когда его забывают?
3. Как посмотреть логи только одного сервиса за последний час?
4. Что даёт `Persistent=true` в таймере и когда это опасно?

!!! tip "Практика"
    Задача «Сервис под systemd» в практикуме: написать юнит с автоперезапуском,
    ограничением памяти и проверкой через `systemctl status`.
