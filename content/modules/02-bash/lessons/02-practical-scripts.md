---
id: practical-scripts
title: Рабочие скрипты: бэкап, проверка сервиса, ротация логов
minutes: 40
---

# Рабочие скрипты: бэкап, проверка сервиса, ротация логов

Три задачи, которые DevOps-инженер пишет в первый месяц: **бэкап**, **health-check**,
**ротация и уборка**. Ниже — рабочие версии с объяснением решений.

## Бэкап с проверкой и ротацией

```bash
#!/usr/bin/env bash
# backup.sh — делает архив каталога, проверяет целостность и хранит 7 дней
set -euo pipefail

SRC="${1:?укажите каталог для бэкапа}"
DEST="${BACKUP_DIR:-/backup}"
KEEP_DAYS="${KEEP_DAYS:-7}"
STAMP="$(date +%Y%m%d-%H%M%S)"
ARCHIVE="$DEST/$(basename "$SRC")-$STAMP.tar.gz"

[[ -d "$SRC" ]] || { echo "нет каталога $SRC" >&2; exit 1; }
mkdir -p "$DEST"

# 1. Архив. -C меняем каталог, чтобы в архиве были относительные пути
tar czf "$ARCHIVE" -C "$(dirname "$SRC")" "$(basename "$SRC")"

# 2. Проверка целостности — без неё бэкап это вера, а не факт
tar tzf "$ARCHIVE" >/dev/null || { echo "архив битый: $ARCHIVE" >&2; exit 2; }

# 3. Проверка места: не даём бэкапам забить диск
size_mb=$(( $(stat -c%s "$ARCHIVE") / 1024 / 1024 ))
avail_mb=$(( $(df --output=avail -m "$DEST" | tail -1) ))
echo "создан $ARCHIVE (${size_mb} МБ), свободно ${avail_mb} МБ"
[[ "$avail_mb" -gt 500 ]] || echo "ВНИМАНИЕ: мало места в $DEST" >&2

# 4. Ротация старых архивов
find "$DEST" -name '*.tar.gz' -type f -mtime "+$KEEP_DAYS" -delete

echo "OK"
```

Разбор решений: `set -euo pipefail` останавливает при первой ошибке; проверка
`tar tzf` подтверждает, что архив читается; ротация через `find -mtime +N` не требует
ручного учёта файлов.

!!! danger "Осторожно"
    Правило трёх копий: **три копии на двух носителях, одна — вне площадки** (3-2-1).
    Бэкап на том же диске, что и данные, — не бэкап. И проверяйте восстановление:
    непроверенный бэкап равен отсутствию бэкапа.

## Health-check с уведомлением

```bash
#!/usr/bin/env bash
# healthcheck.sh — проверяет HTTP-эндпоинты и пишет в системный журнал
set -uo pipefail     # ВАЖНО: без -e, скрипт должен проверить ВСЕ эндпоинты
IFS=$'\n'
ENDPOINTS=(
  "https://api.example.com/health|200"
  "https://api.example.com/ready|200"
)

failures=0
for item in "${ENDPOINTS[@]}"; do
    url="${item%|*}"; expected="${item#*|}"
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$url" || echo 000)"
    if [[ "$code" != "$expected" ]]; then
        logger -t healthcheck "FAIL $url -> $code (ожидался $expected)"
        failures=$((failures + 1))
    fi
done

if [[ "$failures" -gt 0 ]]; then
    echo "проблемных проверок: $failures" >&2
    exit 1
fi
logger -t healthcheck "все эндпоинты отвечают корректно"
```

Ключевое: **здесь нет `set -e`** — при сбое одной проверки мы хотим выполнить
остальные и вернуть итог. Это осознанный исключение из правила.

## Ротация логов без logrotate

```bash
#!/usr/bin/env bash
# rotate.sh — сжимает логи старше суток, удаляет старше 30 дней
set -euo pipefail
LOG_DIR="${1:-/var/log/myapp}"
COMPRESS_AFTER_DAYS=1
DELETE_AFTER_DAYS=30

mapfile -t old_logs < <(find "$LOG_DIR" -type f -name '*.log' -mtime "+$COMPRESS_AFTER_DAYS")
for log in "${old_logs[@]}"; do
    gzip -9 "$log" || true
done

find "$LOG_DIR" -type f -name '*.gz' -mtime "+$DELETE_AFTER_DAYS" -delete
echo "обработано логов: ${#old_logs[@]}"
```

Но в реальной системе сначала смотрите `logrotate`: он умеет то же самое, плюс
сигналы сервису для переоткрытия файла:

```ini
# /etc/logrotate.d/myapp
/var/log/myapp/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0640 appsvc appsvc
    sharedscripts
    postrotate
        systemctl reload myapp >/dev/null 2>&1 || true
    endscript
}
```

**Почему это важно:** без `postrotate` приложение продолжит писать в удалённый файл,
и место на диске не освободится (тот самый инцидент с `lsof +L1`).

## Регулярный запуск: cron и systemd timers

```bash
# crontab -e
# ┌ минута (0-59)
# │ ┌ час (0-23)
# │ │ ┌ день месяца (1-31)
# │ │ │ ┌ месяц (1-12)
# │ │ │ │ ┌ день недели (0-7, 0 и 7 = воскресенье)
# │ │ │ │ │
  30 2 * * *  /opt/scripts/backup.sh /opt/app/data >> /var/log/backup.log 2>&1
  */5 * * * * /opt/scripts/healthcheck.sh
```

В modern-системах предпочтительнее **systemd timer**: он логируется в journald,
умеет зависимости, случайную задержку и «catch up» после выключения.

```ini
# /etc/systemd/system/backup.service
[Unit]
Description=Ночной бэкап
[Service]
Type=oneshot
User=backup
ExecStart=/opt/scripts/backup.sh /opt/app/data
```

```ini
# /etc/systemd/system/backup.timer
[Unit]
Description=Запуск бэкапа ежедневно в 02:30
[Timer]
OnCalendar=*-*-* 02:30:00
Persistent=true
RandomizedDelaySec=10m
[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now backup.timer
systemctl list-timers backup.timer
journalctl -u backup.service -n 20
```

## Проверка перед публикацией: чек-лист

Даже короткий скрипт проходит одни и те же проверки:

1. `bash -n script.sh` — синтаксис.
2. `shellcheck script.sh` — типичные ошибки.
3. Запуск с пустыми аргументами — понятное сообщение, код 2.
4. Запуск с неверным путём — падение до изменения данных.
5. Повторный запуск — идемпотентность.
6. `set -x` на тестовом окружении — видно, какие команды реально выполняются.

## Как не потерять пароль в логах

```bash
set +x                     # отключить трассировку перед секретом
export TOKEN=$(cat /run/secrets/token)
set -x                     # включить обратно
curl -H "Authorization: Bearer $TOKEN" ...
```

Даже с отключённой трассировкой не передавайте секреты аргументом: они видны в
`ps aux`. Используйте файл (`--config`), stdin или переменную окружения, читаемую
приложением.

В GitHub Actions секрет, выведенный в лог, маскируется, но только если совпадает
целиком. Часть строки (например, первые 8 символов) попадёт в лог открытой.
Поэтому `echo "$TOKEN"` недопустим даже для отладки.

## Скрипт как контракт

Хороший скрипт документирует себя: `--help`, коды возврата и понятные сообщения
об ошибках. Договоритесь о кодах:

| Код | Значение |
| --- | --- |
| 0 | успех |
| 1 | общая ошибка выполнения |
| 2 | неверные аргументы |
| 3 | не найдена зависимость |
| 4 | ошибка внешнего сервиса |

По коду возврата CI и мониторинг понимают, что произошло, без разбора текста лога.
Это делает автоматизацию надёжнее, чем «скрипт вернул 1, иди читай».

## Короткое резюме

- Любой скрипт: проверки входа → основная работа → проверка результата → понятный exit-код.
- Бэкап обязан проверяться (`tar tzf`) и ротироваться; храните копию вне хоста.
- Health-check собирает все проблемы и только потом возвращает ошибку (без `set -e`).
- Для расписания используйте logrotate + systemd timers, а не самодельные решения.

## Проверьте себя

1. Почему в health-check намеренно не используется `set -e`?
2. Зачем в logrotate нужен `postrotate` с reload сервиса?
3. Чем systemd timer лучше cron для бэкапов на сервере?
