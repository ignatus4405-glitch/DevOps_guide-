---
id: k8s-manifests
title: Манифесты: Deployment, Service, Ingress, конфигурация
minutes: 45
---

# Манифесты: Deployment, Service, Ingress, конфигурация

## Deployment и Service

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: prod
  labels: { app: api }
spec:
  replicas: 3
  revisionHistoryLimit: 5
  strategy:
    type: RollingUpdate
    rollingUpdate: { maxSurge: 1, maxUnavailable: 0 }   # без потери доступности
  selector:
    matchLabels: { app: api }                            # ДОЛЖЕН совпадать с шаблоном
  template:
    metadata:
      labels: { app: api }
    spec:
      securityContext: { runAsNonRoot: true, runAsUser: 10001, fsGroup: 10001 }
      containers:
        - name: api
          image: ghcr.io/org/api@sha256:9f0c...          # digest вместо тега
          ports: [{ containerPort: 8000, name: http }]
          envFrom:
            - configMapRef: { name: api-config }
            - secretRef: { name: api-secrets }
          resources:
            requests: { cpu: 100m, memory: 128Mi }
            limits:   { cpu: 500m, memory: 512Mi }
          readinessProbe:
            httpGet: { path: /ready, port: http }
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet: { path: /health, port: http }
            initialDelaySeconds: 20
            periodSeconds: 20
          startupProbe:                     # для медленно стартующих приложений
            httpGet: { path: /health, port: http }
            failureThreshold: 30
            periodSeconds: 5
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: ["ALL"] }
          volumeMounts:
            - { name: tmp, mountPath: /tmp }
      volumes:
        - name: tmp
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata: { name: api, namespace: prod }
spec:
  selector: { app: api }            # совпадает с labels pod'ов
  ports:
    - { name: http, port: 80, targetPort: http }
```

## Три типа проверок — и почему их три

| Проверка | Что делает при провале | Для чего нужна |
| --- | --- | --- |
| livenessProbe | перезапускает контейнер | приложение зависло (deadlock) |
| readinessProbe | убирает pod из Service | приложение не готово принимать трафик |
| startupProbe | ждёт успешного старта, отключая остальные | медленный старт (JIT, миграции) |

!!! danger "Осторожно"
    Классическая ошибка: **liveness проверяет доступность базы данных**. Кратковременный
    сбой БД → все pod'ы перезапускаются одновременно → лавина перезапусков. Liveness
    должен проверять сам процесс; зависимости — в readiness (или вообще отдельно).

## ConfigMap и Secret

```yaml
apiVersion: v1
kind: ConfigMap
metadata: { name: api-config, namespace: prod }
data:
  LOG_LEVEL: info
  FEATURE_NEW_UI: "false"
---
apiVersion: v1
kind: Secret
metadata: { name: api-secrets, namespace: prod }
type: Opaque
stringData:                       # удобно, но небезопасно в Git
  DATABASE_URL: postgresql://app:pass@db:5432/shop
```

```bash
kubectl -n prod create secret generic api-secrets \
  --from-literal=DATABASE_URL='postgresql://...' \
  --dry-run=client -o yaml > secret.yaml        # НЕ коммитить в Git
```

Правильно хранить секреты: sealed-secrets, External Secrets Operator (подтягивает из
Vault/AWS Secrets Manager), SOPS. ConfigMap для несекретных настроек — норма для Git.

## Ingress и TLS

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api
  namespace: prod
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/proxy-body-size: "10m"
spec:
  ingressClassName: nginx
  tls:
    - hosts: [api.example.com]
      secretName: api-tls
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: api
                port: { name: http }
```

Ingress-контроллер (nginx-ingress, Traefik, ALB) реализует правила: смотрит на объекты
Ingress и настраивает себя. cert-manager автоматически получает и обновляет сертификаты.

## Автомасштабирование и доступность

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata: { name: api, namespace: prod }
spec:
  scaleTargetRef: { apiVersion: apps/v1, kind: Deployment, name: api }
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource: { name: cpu, target: { type: Utilization, averageUtilization: 70 } }
  behavior:
    scaleDown: { stabilizationWindowSeconds: 300 }   # не «дёргать» масштаб
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata: { name: api, namespace: prod }
spec:
  minAvailable: 2
  selector: { matchLabels: { app: api } }
```

PDB гарантирует, что при обновлении узлов или вытеснении часть реплик останется
работать. Без PDB плановое обслуживание узла может унести весь сервис.

## Полезные команды

```bash
kubectl apply -f manifests/          # применить
kubectl diff -f manifests/           # что изменится (безопасно)
kubectl rollout status deploy/api -n prod
kubectl rollout history deploy/api -n prod
kubectl rollout undo deploy/api -n prod
kubectl -n prod scale deploy/api --replicas=5
kubectl -n prod get pods -o wide --sort-by=.status.startTime
kubectl -n prod get events --sort-by=.lastTimestamp | tail -20
kubectl -n prod top pods
kubectl kustomize overlays/prod | kubectl diff -f -   # рендер kustomize
```

## Selector и labels: как связываются объекты

Все связи в Kubernetes — через метки:

- Service → Pods по `selector`;
- Deployment → ReplicaSet → Pods по `matchLabels`;
- NetworkPolicy — по меткам;
- PodDisruptionBudget — по меткам.

```yaml
metadata:
  labels:
    app: api
    version: v2
    team: payments
spec:
  selector:
    matchLabels:
      app: api
```

Ошибка в одной букве метки — сервис без endpoints. Проверка:

```bash
kubectl get pods --show-labels
kubectl get svc api -o jsonpath='{.spec.selector}'
```

## Deployment, ReplicaSet, StatefulSet, DaemonSet

| Объект | Для чего | Особенность |
| --- | --- | --- |
| Deployment | stateless-сервисы | rolling update, ReplicaSet |
| StatefulSet | БД, кластеры | стабильные имена и тома |
| DaemonSet | агенты на каждой ноде | по одному поду на ноду |
| Job | одноразовые задачи | до успешного завершения |
| CronJob | расписание | создаёт Job по cron |

Deployment не подходит для БД: поды взаимозаменяемы, имена случайны, тома общие
только через PVC.

## Стратегии обновления

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1
    maxUnavailable: 0
```

`maxUnavailable: 0` — без простоя, но требует свободных ресурсов.
`Recreate` — сначала убить все поды, потом создать новые (простой, но чисто).

```bash
kubectl rollout status deploy/api
kubectl rollout undo deploy/api
kubectl rollout history deploy/api --revision=2
```

## Namespaces и квоты

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-quota
  namespace: payments
spec:
  hard:
    requests.cpu: "10"
    requests.memory: 20Gi
    pods: "30"
```

Квоты не дают одной команде занять весь кластер. LimitRange задаёт дефолтные
requests/limits для подов, где они не указаны.

## Короткое резюме

- Deployment описывает pod'ы и стратегию обновления; Service — стабильный адрес по меткам.
- liveness перезапускает, readiness выводит из балансировки, startup ждёт медленный старт.
- Конфигурация через ConfigMap/Secret, секреты — из внешнего хранилища.
- HPA масштабирует, PDB сохраняет доступность, `kubectl diff` показывает последствия.

## Путь манифеста через API

`kubectl apply` отправляет объект в API-сервер. До записи в etcd он проходит:

1. **аутентификацию** (кто вы);
2. **авторизацию** (RBAC: можно ли);
3. **mutating admission** — плагины могут изменить объект (sidecar, defaults);
4. **валидацию схемы** — типы и обязательные поля;
5. **validating admission** — политики (запрет privileged, проверка registry);
6. **запись в etcd**.

Понимание порядка объясняет, почему объект «есть», но под не создаётся:
например, mutating-webhook добавил неверный toleration, или validating-webhook
отклонил.

### Defaults и неявное поведение

Kubernetes подставляет значения: `restartPolicy: Always`, `terminationGracePeriod:
30`, `imagePullPolicy`, resource limits из LimitRange. Неявные defaults — частая
причина расхождений между окружениями. Фиксируйте важные поля явно.

### Server-side apply

`kubectl apply` хранит последнюю конфигурацию в аннотации. Проблемы: конфликты
при нескольких владельцах, раздутые аннотации. Server-side apply переносит
расчёт diff на сервер и отслеживает field ownership:

```bash
kubectl apply --server-side -f app.yaml
kubectl diff -f app.yaml
```

`kubectl diff` — обязательная привычка: сначала посмотреть, что изменится.

### Схемы и версии API

`apiVersion` меняется при эволюции. Deprecated-версии перестают работать после
обновления кластера. Проверяйте `kubectl api-resources` и `kubectl explain`.
Инструмент `pluto`/`kube-no-trouble` находит устаревшие API до апгрейда.

### Валидация

Схема ловит типы, но не смысл. `replicas: -1` может пройти схему и упасть в
контроллере. Валидируйте бизнес-правила политиками и тестами манифестов
(kubeconform, conftest).

## Подробный разбор темы

Kubernetes связывает объекты по labels и selectors, а не по именам файлов. Если selector Deployment не совпадает с labels Pod template или selector Service, объект будет валиден, но трафик не дойдёт до приложения. Перед выкладкой проверьте rendered manifest, namespace, selectors, image digest, probes и resource requests/limits.

Liveness отвечает, нужно ли перезапустить контейнер; readiness — можно ли направлять на него трафик; startup probe даёт медленно стартующему процессу время подняться. Неправильная liveness может создать цикл рестартов во время перегрузки. Ingress направляет HTTP(S) трафик только при наличии контроллера и корректного DNS/TLS; объект Ingress сам по себе не создаёт внешний балансировщик.

## Пошаговый сценарий

![Порядок действий: Манифесты: Deployment, Service, Ingress, конфигурация](assets/img/howto/07-kubernetes--02-manifests.svg)

1. Проверьте namespace, labels и selectors между Deployment и Service.
2. Проверьте image digest, requests, limits и конфигурацию.
3. Разведите readiness, liveness и startup probes по назначению.
4. Отрендерите manifest и проверьте его в тестовом namespace.

## Проверьте себя

1. Почему liveness не должен проверять внешние зависимости?
2. Что произойдёт, если selector Deployment не совпадает с labels шаблона?
3. Зачем PDB, если у Deployment уже несколько реплик?
