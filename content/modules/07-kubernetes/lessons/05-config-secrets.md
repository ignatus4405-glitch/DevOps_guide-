---
id: k8s-config-secrets
title: Конфигурация: ConfigMap, Secret, внешние хранилища
minutes: 28
---

# Конфигурация: ConfigMap, Secret, внешние хранилища

Приложение должно быть одинаковым во всех окружениях, а различаться только
конфигурацией. В Kubernetes для этого есть ConfigMap и Secret, но у них есть
границы, которые важно понимать заранее.

## ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  LOG_LEVEL: info
  APP_MODE: production
  nginx.conf: |
    server {
      listen 8080;
      location / { return 200 'ok'; }
    }
```

Использование:

```yaml
containers:
  - name: app
    envFrom:
      - configMapRef:
          name: app-config
    volumeMounts:
      - name: config
        mountPath: /etc/nginx
volumes:
  - name: config
    configMap:
      name: app-config
```

Разница: `envFrom` читает переменные один раз при старте; volume обновляется
автоматически (с задержкой до минуты), но приложение должно перечитывать файл.

## Secret

```bash
kubectl create secret generic db-creds \
  --from-literal=username=app \
  --from-literal=password='s3cr3t'
```

```yaml
env:
  - name: DB_PASSWORD
    valueFrom:
      secretKeyRef:
        name: db-creds
        key: password
```

Важно: Secret по умолчанию хранится в etcd в base64 — это **не шифрование**.
Нужно:

- включить encryption at rest в etcd;
- ограничить RBAC на чтение секретов;
- использовать внешнее хранилище (Vault, External Secrets, CSI driver).

```bash
kubectl get secret db-creds -o jsonpath='{.data.password}' | base64 -d
```

Любой, у кого есть `get secrets` в namespace, прочитает значение. Поэтому
`secrets` — привилегированный ресурс.

## Внешние хранилища

| Решение | Как работает |
| --- | --- |
| External Secrets Operator | синхронизирует секреты из Vault/AWS SM в Kubernetes Secret |
| Secrets Store CSI | монтирует секреты напрямую в под |
| Vault Agent Injector | sidecar/init-контейнер достаёт секрет |
| SOPS + GitOps | зашифрованные секреты в git |

Для продакшена предпочтительнее внешнее хранилище: секреты не лежат в etcd и
централизованно ротируются.

## Обновление конфигурации

Два подхода:

1. **Hot reload** — приложение следит за файлом или получает SIGHUP.
2. **Recreate pods** — конфигурация читается только при старте.

Во втором случае нужно менять аннотацию в pod template, чтобы rollout
перезапустил поды:

```yaml
spec:
  template:
    metadata:
      annotations:
        config/hash: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
```

Helm делает это через checksum/config. Без этого ConfigMap обновится, а поды
продолжат работать со старыми значениями.

## Проверка и типичные ошибки

```bash
kubectl get configmap app-config -o yaml
kubectl exec deploy/app -- env | grep LOG_LEVEL
kubectl exec deploy/app -- cat /etc/nginx/nginx.conf
```

| Ошибка | Симптом |
| --- | --- |
| ConfigMap не существует | Pod в `CreateContainerConfigError` |
| неверный ключ | `couldn't find key` |
| Secret в другом namespace | не находится |
| пробелы/переводы строк в Secret | приложение не может подключиться |

## Практика безопасности

- не храните секреты в ConfigMap;
- не выводите env в логи;
- ограничьте RBAC (`get secrets` — только нужным SA);
- используйте `automountServiceAccountToken: false`, если токен не нужен;
- ротируйте секреты и перезапускайте поды.

## Проверьте себя

1. Почему base64 в Secret не является защитой?
2. Чем envFrom отличается от монтирования volume?
3. Почему ConfigMap может обновиться, а приложение — нет?
4. Какие права нужны, чтобы прочитать секрет?

!!! tip "Практика"
    Задача «Конфигурация и секреты» в практикуме: вынести настройки в ConfigMap,
    а пароль — во внешний Secret.
