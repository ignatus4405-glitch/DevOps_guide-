---
id: k8s-troubleshooting
title: Отладка: Pending, CrashLoopBackOff, OOMKilled
minutes: 32
---

# Отладка: Pending, CrashLoopBackOff, OOMKilled

Большинство инцидентов в Kubernetes сводится к пяти состояниям. Если знать, что
каждое означает и какие команды смотреть, диагностика занимает минуты.

## Порядок действий

```bash
kubectl get pods -o wide
kubectl describe pod <pod>
kubectl logs <pod> --previous
kubectl get events --sort-by=.lastTimestamp | tail -20
```

`describe` содержит события — часто ответ уже там. `--previous` показывает логи
предыдущего контейнера, что критично для CrashLoopBackOff.

## Pending

Под не может быть размещён. Причины в событиях:

| Событие | Причина | Решение |
| --- | --- | --- |
| `Insufficient cpu/memory` | нет ресурсов на нодах | уменьшить requests или добавить ноды |
| `node(s) had untolerated taint` | taint без toleration | добавить toleration |
| `node affinity/selector` | несовпадение | поправить affinity |
| `unbound PVC` | нет PV | создать PVC/StorageClass |
| `pod anti-affinity` | правила не выполняются | ослабить правило |

```bash
kubectl describe pod <pod> | sed -n '/Events/,$p'
kubectl get nodes -o custom-columns=NAME:.metadata.name,CPU:.status.allocatable.cpu,MEM:.status.allocatable.memory
kubectl describe node <node> | grep -A5 Allocated
```

## ImagePullBackOff

| Причина | Проверка |
| --- | --- |
| неверный тег | `kubectl describe pod` → `manifest unknown` |
| приватный registry | нет imagePullSecret |
| истёк токен | обновить secret |
| нет сети до registry | проверить с ноды |

```bash
kubectl create secret docker-registry regcred \
  --docker-server=ghcr.io --docker-username=user --docker-password=token
```

## CrashLoopBackOff

Контейнер стартует и падает. Смотреть:

```bash
kubectl logs <pod> --previous
kubectl describe pod <pod> | grep -A3 'Last State'
```

Типичные причины:

- ошибка конфигурации (нет переменной, неверный URL);
- нет доступа к БД;
- миграция не применилась;
- приложение не обрабатывает SIGTERM и падает на liveness;
- порт занят/не тот.

Backoff растёт экспоненциально (10s, 20s, 40s... до 5 минут). Если нужно быстрее
отладить — временно `kubectl run` с тем же образом и `sleep`.

## OOMKilled

Код 137 и `Reason: OOMKilled` означают: контейнер превысил memory limit.

```bash
kubectl describe pod <pod> | grep -E 'Limits|Requests|OOM'
kubectl top pod <pod>
```

Решения:

1. Увеличить limit (быстро, но не всегда правильно).
2. Найти утечку памяти.
3. Проверить, что JVM/Node/Python учитывают cgroup-лимиты (`-XX:MaxRAMPercentage`,
   `--max-old-space-size`).
4. Убрать кэш без ограничения размера.

JVM в контейнере без `MaxRAMPercentage` видит память хоста и получает OOM от
ядра — классическая проблема.

## Readiness и liveness

| Проба | Что проверяет | Что делать при провале |
| --- | --- | --- |
| readiness | готов принимать трафик | убрать из endpoints |
| liveness | процесс жив | перезапустить контейнер |
| startup | долгий старт | не убивать до готовности |

Ошибки:

- liveness проверяет БД → при отказе БД перезапускаются все поды (каскад);
- readiness всегда 200 → трафик на неготовые поды;
- слишком короткий `timeoutSeconds` → ложные перезапуски.

## Отладка без shell

Если образ distroless:

```bash
kubectl debug -it <pod> --image=nicolaka/netshoot --target=<container>
kubectl debug node/<node> -it --image=busybox
```

`kubectl debug` создаёт эфемерный контейнер в namespace пода — можно смотреть
процессы и сеть.

## Сервис не отвечает, хотя под Running

1. `kubectl get endpoints <svc>` — есть ли адреса.
2. `kubectl get pod -o wide` — Ready ли под.
3. `kubectl exec` из другого пода: `curl http://svc`.
4. `kubectl describe svc` — правильный ли selector/port.
5. Ingress → Service → Endpoints → Pod.

## Проверьте себя

1. Где искать причину Pending?
2. Что означает код 137 и как отличить OOM от падения приложения?
3. Почему liveness не должна проверять БД?
4. Как отладить distroless-контейнер?

!!! tip "Практика"
    Задача «Разбор CrashLoopBackOff» в практикуме: по событиям и логам найти
    причину и исправить.
