---
id: runtime-security
title: Безопасность Kubernetes и runtime
minutes: 28
---

# Безопасность Kubernetes и runtime

Кластер — это API, через который можно создать процесс на любой ноде. Поэтому
безопасность Kubernetes — это прежде всего ограничение того, что можно создать, и
того, что может делать созданное.

## Модель угроз

1. Скомпрометированный под с токеном SA получает доступ к API.
2. Под с `privileged: true` или `hostPath` выходит на ноду.
3. Уязвимость в ingress/приложении даёт RCE.
4. Слабый RBAC позволяет эскалацию.
5. Незащищённый etcd раскрывает все секреты.

## Уровни защиты

| Уровень | Инструмент |
| --- | --- |
| API | RBAC, admission, audit |
| Под | securityContext, Pod Security Admission |
| Сеть | NetworkPolicy, service mesh |
| Образ | подпись, скан, distroless |
| Нода | минимальная ОС, обновления, отключение docker.sock |
| Runtime | Falco, Tetragon, seccomp |

## Pod Security Admission

```yaml
metadata:
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

`restricted` требует non-root, запрет privilege escalation, seccomp, сброс
capabilities. Вводите сначала `warn`, потом `enforce` — иначе сломаете существующие
приложения.

## seccomp

```yaml
securityContext:
  seccompProfile:
    type: RuntimeDefault
```

Профиль ограничивает системные вызовы. `RuntimeDefault` — безопасный минимум,
`Unconfined` — фактически без ограничений (плохо).

## NetworkPolicy

```yaml
policyTypes: [Ingress, Egress]
ingress:
  - from:
      - namespaceSelector:
          matchLabels: { kubernetes.io/metadata.name: ingress-nginx }
```

По умолчанию весь трафик разрешён. Начните с default-deny в новом namespace и
открывайте только нужное.

## Runtime-детект

Falco отслеживает подозрительные события:

- shell внутри контейнера;
- чтение `/etc/shadow`;
- запуск пакетного менеджера в проде;
- исходящее соединение на необычный порт;
- запись в `/usr/bin`.

```yaml
- rule: Shell in container
  desc: Процесс shell в контейнере
  condition: spawned_process and container and proc.name in (bash, sh)
  output: "Shell в контейнере %container.name (%proc.cmdline)"
  priority: WARNING
```

Детект не блокирует, но даёт сигнал. Для блокировки — Tetragon или admission.

## Секреты и SA

- `automountServiceAccountToken: false` по умолчанию;
- отдельный SA на приложение;
- короткоживущие токены (BoundServiceAccountTokenVolume включён по умолчанию);
- внешние секреты вместо Kubernetes Secret;
- аудит доступа к секретам.

## Обновления

Кластер без обновлений — набор известных уязвимостей. Практика:

- минорные обновления раз в квартал;
- проверка deprecated API (`kubectl deprecations`, `pluto`);
- тестовый кластер для обкатки;
- автоматическое обновление нод (managed node groups).

## Механизмы изоляции Linux

Контейнер — процесс с ограничениями. Чем больше ограничений, тем меньше ущерб
при эксплуатации уязвимости.

### Capabilities

Root в контейнере — не полный root хоста: capabilities урезаны. Но
`--privileged` возвращает почти всё. Практика:

```yaml
securityContext:
  capabilities:
    drop: ["ALL"]
    add: ["NET_BIND_SERVICE"]
```

Приложению обычно не нужны никакие capabilities.

### seccomp

Фильтр системных вызовов. Профиль `RuntimeDefault` блокирует опасные вызовы
(`mount`, `ptrace`, `reboot`). Кастомный профиль сужает ещё сильнее, но требует
тестирования.

### AppArmor и SELinux

Мандатный доступ: какие файлы, сокеты и операции разрешены процессу, даже если
он root. В Kubernetes задаётся аннотацией/полем `appArmorProfile`.

### User namespace

Root внутри контейнера может быть обычным uid снаружи. Rootless-контейнеры
снижают риск побега. В Kubernetes это пока не всегда просто, но тренд явный.

### Read-only root filesystem

`readOnlyRootFilesystem: true` запрещает запись в слой контейнера. Приложение
пишет в volume или tmpfs. Это ломает многие «удобные» практики и заодно
предотвращает подмену бинарей.

### Runtime-детект

Статическая конфигурация не видит атаку в процессе. Runtime-инструменты
(Falco, Tetragon) отслеживают:

- запуск shell в контейнере;
- чтение `/etc/shadow`;
- исходящие соединения на неизвестные адреса;
- монтирование.

Алерт без контекста шумит; настройте исключения и владельцев.

## Подробный разбор темы

Runtime security дополняет image scanning: она наблюдает фактическое поведение процесса, системные вызовы, сетевые соединения и попытки доступа к чувствительным файлам. В Kubernetes ограничивайте привилегированные Pod, hostPath, hostNetwork и capabilities, используйте admission policy и минимальный ServiceAccount. Контейнер, запущенный как root, расширяет последствия ошибок приложения.

Сформулируйте ожидаемое поведение workload — какие процессы, порты и файлы ему нужны — и анализируйте отклонения. При срабатывании сохраняйте context, Pod identity и временные метки; не автоматически убивайте каждый необычный процесс без понимания риска, если это разрушит доказательства. Проверяйте policy в audit/dry-run перед блокирующим rollout.

## Проверьте себя

1. Почему `privileged: true` — фактически root на ноде?
2. Что проверяет Pod Security Admission?
3. Чем Falco отличается от NetworkPolicy?
4. Зачем отключать automount токена SA?

!!! warning "Важно"
    Admission-контроллер (Kyverno/OPA Gatekeeper) может запрещать создание
    небезопасных подов. Но политика без тестов заблокирует и легитимные
    workload'ы — проверяйте на staging.
