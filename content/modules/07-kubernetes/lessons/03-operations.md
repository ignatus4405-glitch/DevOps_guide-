---
id: k8s-operations
title: Эксплуатация и отладка Kubernetes
minutes: 40
---

# Эксплуатация и отладка Kubernetes

## Диагностика: системный порядок

```bash
# 1. Что вообще происходит с pod'ом
kubectl -n prod get pods -o wide
kubectl -n prod describe pod api-7d9f-abc | sed -n '1,40p;/Events/,$p'

# 2. Логи приложения (включая предыдущий запущенный контейнер)
kubectl -n prod logs api-7d9f-abc --tail=200
kubectl -n prod logs api-7d9f-abc --previous        # почему упал прошлый
kubectl -n prod logs -l app=api --all-containers --prefix

# 3. Зайти внутрь, проверить сеть и файлы
kubectl -n prod exec -it api-7d9f-abc -- sh
# внутри: env | sort; getent hosts api; wget -qO- localhost:8000/health

# 4. События кластера и состояние узлов
kubectl -n prod get events --sort-by=.lastTimestamp | tail -20
kubectl get nodes -o wide
kubectl top pods -n prod && kubectl top nodes

# 5. Проверить, что Service видит pod'ы
kubectl -n prod get endpoints api
kubectl -n prod get endpointslices
```

| Статус pod | Что означает | Куда смотреть |
| --- | --- | --- |
| Pending | нет подходящего узла / ресурсов | `describe pod` → Events |
| ImagePullBackOff | неверный образ/нет прав в реестре | имя образа, imagePullSecrets |
| CrashLoopBackOff | приложение падает | `logs --previous` |
| OOMKilled (137) | превышен limits.memory | `describe`, метрики памяти |
| Evicted | узел под давлением на диск/память | `describe node`, условия узла |
| Terminating (долго) | не отвечает на SIGTERM / finalizer | приложение, gracePeriod |

```bash
# Прямая проверка решения: поднять отладочный pod в кластере
kubectl -n prod run netcheck --rm -it --image=nicolaka/netshoot -- bash
# внутри: nslookup api; curl -sv http://api/health; tcpdump -i any port 80
```

!!! tip "Совет"
    Большинство «не работает» в Kubernetes объясняется тремя вещами: неверный
    namespace, пустые endpoints (не совпал селектор/не прошла readiness) и ошибка в
    образе/портах. Проверяйте их в этом порядке — экономит часы.

## Обновления, откаты и обслуживание

```bash
kubectl -n prod set image deploy/api api=ghcr.io/org/api:v1.5.0
kubectl -n prod rollout status deploy/api --timeout=120s
kubectl -n prod rollout history deploy/api
kubectl -n prod rollout undo deploy/api --to-revision=3

kubectl cordon worker-2          # запретить планирование новых pod
kubectl drain worker-2 --ignore-daemonsets --delete-emptydir-data
# ... обслуживание узла ...
kubectl uncordon worker-2
```

Правила безопасного обновления кластера: сначала control plane, затем узлы по одному,
с проверкой PDB и метрик; обновляйте не «всё сразу», а версию за версией.

## Ресурсы, квоты и стоимость

```bash
kubectl top nodes && kubectl top pods -A --sort-by=memory | head -20
kubectl get hpa -A
kubectl describe quota -n prod
kubectl get limitrange -n prod -o yaml
```

```yaml
apiVersion: v1
kind: ResourceQuota
metadata: { name: prod-quota, namespace: prod }
spec:
  hard:
    requests.cpu: "20"
    requests.memory: 40Gi
    limits.cpu: "40"
    limits.memory: 80Gi
    pods: "100"
```

Зачем: одна команда без лимитов может «съесть» кластер. Квоты и LimitRange ставятся
в каждый namespace как страховка от случайности (и как инструмент контроля бюджета).

## Бэкапы и восстановление

```bash
# etcd — сердце кластера (managed-кластер делает это сам, но проверьте!)
etcdctl snapshot save /backup/etcd-$(date +%F).db \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key
etcdctl snapshot status /backup/etcd-2025-01-31.db -w table
```

Что ещё должно быть в Git и восстанавливаться: манифесты (kustomize/helm),
CRD и операторы, конфигурация ingress, секреты (в хранилище), описания окружений.
**Проверяйте восстановление** на отдельном кластере — иначе это вера, а не бэкап.

## Безопасность в Kubernetes

| Практика | Как |
| --- | --- |
| Не запускать контейнеры от root | `runAsNonRoot`, `runAsUser` |
| Минимум прав | `capabilities.drop: [ALL]`, `readOnlyRootFilesystem` |
| Политики безопасности pod | Pod Security Admission (`restricted`) или Gatekeeper/OPA |
| Сетевые политики | NetworkPolicy: трафик только по необходимости |
| Секреты из внешнего хранилища | External Secrets / sealed-secrets |
| Ограничение RBAC | роли по namespace, без `cluster-admin` для CI |
| Обновления | отслеживать CVE базовых образов и версий кластера |

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: { name: api-allow-ingress, namespace: prod }
spec:
  podSelector: { matchLabels: { app: api } }
  policyTypes: [Ingress]
  ingress:
    - from:
        - namespaceSelector: { matchLabels: { name: ingress-nginx } }
        - podSelector: { matchLabels: { app: api } }   # api ↔ api
      ports: [{ port: 8000, protocol: TCP }]
```

## Короткое резюме

- Отладка идёт по порядку: pod → describe → logs → exec → events → endpoints.
- Обновления выполняются через rollout с контролем статуса и откатом `rollout undo`.
- Квоты, лимиты и top важны не только для стабильности, но и для стоимости.
- Бэкап etcd и манифестов плюс регулярные проверки восстановления — обязательная практика.

## Подробный разбор темы

Перед любым `kubectl` проверьте текущий context и namespace: ошибочная команда в production опаснее неисправного кластера. Используйте `kubectl config current-context`, явно указывайте `-n` и предпочитайте read-only команды до понимания ситуации. `rollout status` подтверждает состояние обновления Deployment, но не гарантирует корректность пользовательского ответа.

Для безопасного изменения применяйте декларативный manifest или GitOps, а не серию ручных `edit`. Перед restart сохраните events и logs — они могут исчезнуть с заменой Pod. Операционный журнал должен содержать объект, время, причину и ссылку на change request. Регулярно проверяйте процедуры обновления узлов, обновления control plane и восстановления из backup etcd.

## Проверьте себя

1. Какие три причины чаще всего объясняют «сервис недоступен» в Kubernetes?
2. Что означает код выхода 137 и что с ним делать?
3. Зачем NetworkPolicy, если pod'ы и так изолированы namespace'ами?
