---
id: cgroups-v2
title: cgroups v2: как ядро делит ресурсы
minutes: 30
---

# cgroups v2: как ядро делит ресурсы

Контейнеры, systemd-сервисы и Kubernetes-поды ограничены cgroups. Если не
понимать модель, лимиты выглядят случайными: под с `limits` не получает CPU,
а сервис с `MemoryMax` внезапно убит.

## Иерархия

cgroups v2 — единое дерево в `/sys/fs/cgroup`. Каждая группа получает
контроллеры (cpu, memory, io, pids) от родителя. Ограничение действует вниз по
дереву.

```text
/sys/fs/cgroup
├── system.slice
│   ├── ssh.service
│   └── myapp.service
└── user.slice
```

systemd создаёт slice'ы автоматически: `system.slice` для сервисов,
`user.slice` для сессий, `machine.slice` для ВМ/контейнеров.

## CPU

Два разных механизма:

- **cpu.weight** (1–10000) — относительная доля при конкуренции;
- **cpu.max** (`quota period`) — жёсткий потолок, вызывает throttling.

`cpu.weight` не ограничивает: если CPU свободен, процесс возьмёт больше.
`cpu.max` ограничивает даже при простое. Для latency-критичных сервисов
жёсткий лимит опасен: всплеск упирается в throttling и p99 растёт.

Проверка:

```bash
cat /sys/fs/cgroup/system.slice/myapp.service/cpu.max
cat /sys/fs/cgroup/system.slice/myapp.service/cpu.stat
```

`nr_throttled` и `throttled_usec` показывают, сколько раз и как долго сервис
стоял в throttling.

## Память

- `memory.max` — жёсткий лимит, при превышении OOM внутри группы;
- `memory.high` — мягкий порог, ядро начинает вытеснять;
- `memory.current` — текущее потребление;
- `memory.stat` — анонимная память, page cache, swap.

Важно: page cache учитывается в `memory.current`. Приложение, читающее файлы,
может выглядеть «прожорливым», хотя кэш вытесняемый.

## I/O и PIDs

`io.max` задаёт IOPS/полосу на устройство, `io.weight` — относительный
приоритет. `pids.max` защищает от fork-бомб.

## Pressure Stall Information

PSI — лучший сигнал перегрузки:

```bash
cat /sys/fs/cgroup/system.slice/myapp.service/cpu.pressure
some avg10=12.4 total=...
```

`some` — доля времени, когда хотя бы одна задача ждала ресурс. Это честнее
`load average`: показывает давление, а не число процессов.

## systemd и лимиты

```ini
[Service]
CPUWeight=200
MemoryMax=1G
IOWeight=100
TasksMax=512
```

`systemctl set-property myapp MemoryMax=2G` меняет на ходу. `systemd-cgtop`
показывает потребление по группам.

## Kubernetes

Kubernetes переводит requests/limits в cgroup:

- CPU request → `cpu.weight` (пропорционально);
- CPU limit → `cpu.max`;
- memory request → планирование;
- memory limit → `memory.max`.

Поэтому CPU limit в Kubernetes — это throttling, а memory limit — OOM.
Для многих сервисов лучше не ставить CPU limit, а задавать request.

## Как проверить себя

1. Чем `cpu.weight` отличается от `cpu.max`?
2. Почему memory limit приводит к OOM?
3. Что показывает `throttled_usec`?
4. Зачем PSI, если есть load average?
5. Во что Kubernetes превращает requests и limits?

!!! tip "Практика"
    Задача «Лимиты cgroup» в практикуме: объяснить throttling по метрикам.

## Подробный разбор темы

В cgroups v2 ограничения применяются к группе процессов и наследуются по иерархии. Сервис может казаться «в порядке» по общесистемному `free`, но быть ограничен локальным `memory.max`; аналогично квота CPU может давать throttling даже при свободных ядрах. Проверяйте путь процесса в `/proc/<pid>/cgroup`, затем `cpu.max`, `memory.current`, `memory.max` и `memory.events`.

Сопоставляйте лимит с профилем нагрузки и соседними группами: слишком высокий предел создаёт риск для узла, слишком низкий — задержки и рестарты. `cpu.weight` распределяет долю при конкуренции, тогда как `cpu.max` задаёт потолок; это разные механизмы. При расследовании контейнера учитывайте весь путь: runtime, systemd slice и Kubernetes resource requests/limits.
