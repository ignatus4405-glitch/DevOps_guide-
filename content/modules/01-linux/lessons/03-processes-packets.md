---
id: processes-packets
title: Процессы, systemd, пакеты и логи
minutes: 45
---

# Процессы, systemd, пакеты и логи

Сервер живёт не файлами, а **процессами**. DevOps-инженер должен уметь ответить на
три вопроса: какой процесс ест ресурсы, кто его запустил, и почему он перезапустился.

## Процессы: наблюдение и управление

```bash
ps aux                      # все процессы с CPU/памятью
ps aux --sort=-%mem | head  # топ по памяти
top / htop                  # интерактивный монитор (htop удобнее)
pgrep -a nginx              # PID процессов по имени
pidof nginx                 # только PID
pstree -p                   # дерево процессов
kill -15 1234               # вежливое завершение (SIGTERM)
kill -9 1234                # жёсткое убийство (SIGKILL, без уборки ресурсов)
```

| Сигнал | Номер | Когда использовать |
| --- | --- | --- |
| SIGTERM | 15 | По умолчанию: процесс завершится корректно |
| SIGKILL | 9 | Процесс завис и не реагирует на 15 |
| SIGHUP | 1 | Перечитать конфигурацию (nginx, sshd) |
| SIGINT | 2 | Как Ctrl+C в терминале |

!!! warning "Важно"
    `kill -9` не даёт процессу закрыть соединения и сохранить данные. Если приложение
    не завершается по `SIGTERM` — это баг приложения: правильный обработчик должен
    закрывать пул соединений и только потом выходить. В Kubernetes такое поведение
    приводит к обрывам запросов при деплое.

## systemd: управление сервисами

`systemd` — система инициализации: именно она запускает сервисы при старте системы
и следит за ними. Юнит-файл описывает, что запускать:

```ini
# /etc/systemd/system/myapp.service
[Unit]
Description=MyApp API
After=network-online.target

[Service]
User=appsvc
WorkingDirectory=/opt/app
EnvironmentFile=/etc/myapp/myapp.env
ExecStart=/opt/app/venv/bin/python -m myapp
Restart=on-failure
RestartSec=3
# Ограничения — залог безопасности
NoNewPrivileges=true
ProtectSystem=strict

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload        # после правки юнит-файла
sudo systemctl enable --now myapp   # автозапуск при загрузке + старт сейчас
systemctl status myapp              # состояние, PID, последние строки лога
sudo systemctl restart myapp        # перезапуск
sudo systemctl stop myapp
systemctl list-units --type=service --state=running
systemctl list-unit-files --state=enabled | wc -l
journalctl -u myapp -f              # следить за логом сервиса
journalctl -u myapp --since "1 hour ago" --no-pager
journalctl -p err -b                # ошибки текущей загрузки
journalctl --disk-usage             # сколько занимает журнал
```

!!! tip "Совет"
    `systemctl status` показывает не только «active», но и время запуска, PID и
    последние 10 строк лога — этого обычно достаточно для первой диагностики.
    Если сервис «падает по кругу», смотрите `journalctl -u <сервис> -n 100`.

## Пакеты: apt и dnf

| Действие | Debian/Ubuntu | RHEL/CentOS/Fedora |
| --- | --- | --- |
| Обновить индекс | `sudo apt update` | `sudo dnf check-update` |
| Установить | `sudo apt install nginx` | `sudo dnf install nginx` |
| Обновить всё | `sudo apt upgrade -y` | `sudo dnf update -y` |
| Удалить | `sudo apt remove nginx` | `sudo dnf remove nginx` |
| Найти пакет | `apt search nginx` | `dnf search nginx` |
| Показать файлы пакета | `dpkg -L nginx` | `rpm -ql nginx` |
| Какому пакету принадлежит файл | `dpkg -S /usr/sbin/nginx` | `rpm -qf /usr/sbin/nginx` |
| Показать зависимости | `apt-cache depends nginx` | `dnf repoquery --requires nginx` |

Обновления безопасности — регулярная задача. На десятках серверов её автоматизируют
(Ansible, unattended-upgrades), но **никогда не применяют на прод без staging**:
обновление ядра может потребовать перезагрузки, а новая версия nginx — правки конфига.

## Ресурсы: диск, память, нагрузка

```bash
df -h                          # место на ФС
du -sh /var/log/*              # кто занимает место
find / -xdev -size +1G -type f 2>/dev/null   # большие файлы (без сетевых ФС)
lsof +L1                       # удалённые файлы, удерживаемые процессом (частая причина «диск полон»)
free -h                        # память и swap
vmstat 1 5                     # нагрузка, контексты, swap на лету
uptime                         # load average за 1/5/15 мин
iostat -xz 1 3                 # утилизация дисков (пакет sysstat)
ss -tulpn                      # кто слушает какие порты
```

**Load average** — среднее число процессов в очереди на CPU и в ожидании диска.
Важно сравнивать его с количеством ядер (`nproc`): load 8 на 4 ядрах — перегрузка.

!!! note "Частый инцидент: «диск полон, но du не находит файлов»"
    Классика: приложение удалило лог, но процесс продолжает писать в открытый файл —
    место не освобождается. `lsof +L1` покажет такой файл. Лечение: `truncate -s 0 /proc/<pid>/fd/<fd>`
    или корректный reload приложения. Постоянное решение — ротация логов (logrotate).

## Логи: где смотреть и что искать

| Источник | Где лежит | Как читать |
| --- | --- | --- |
| Systemd-сервисы | journald | `journalctl -u svc -f` |
| Syslog | `/var/log/syslog` (Debian) | `less`, `grep` |
| Приложение | `/var/log/<app>/` | `tail -f`, `grep` |
| Краш-логи ядра | `/var/log/kern.log`, `dmesg` | `dmesg -T \| tail` |
| Аудит | `/var/log/auth.log` | `grep "Failed password"` |

```bash
journalctl -u myapp --since "10 min ago" | grep -i error | tail -50
tail -F /var/log/nginx/error.log          # -F следит даже за пересозданным файлом
zgrep "500 " /var/log/nginx/access.log.*.gz   # поиск в архивах rotation
```

## Реальный сценарий диагностики

> Пользователи жалуются: сайт не открывается. Действия по шагам.

```bash
# 1. Сервис вообще запущен?
systemctl status nginx

# 2. Если упал — почему? Читаем лог.
journalctl -u nginx -n 50 --no-pager

# 3. Слушает ли порт?
ss -tulpn | grep ':80\|:443'

# 4. Что на файловой системе? Иногда «диск полон» ломает запись логов.
df -h /var

# 5. Есть ли конфликт на порту (другой процесс занял 80)?
sudo lsof -i :80

# 6. Ошибки конфигурации проверяем ДО рестарта:
sudo nginx -t && sudo systemctl reload nginx
```

Порядок важен: **сначала факты, потом гипотезы**. Опытные инженеры не рестартуют
сервис «на всякий случай» — рестарт уничтожает улики.

## Короткое резюме

- Процессы управляются сигналами: `SIGTERM` корректно, `SIGKILL` — принудительно.
- `systemd` запускает сервисы и хранит их логи в journald.
- Пакеты ставятся через `apt`/`dnf`, обновления не применяют на прод без staging.
- Диагностика идёт по порядку: сервис → лог → порт → диск → конфликты.

## Проверьте себя

1. Почему `kill -9` считается «последним средством»?
2. Как посмотреть логи сервиса за последние 30 минут?
3. Что означает load average 12 при 4 ядрах и что это говорит о сервере?
