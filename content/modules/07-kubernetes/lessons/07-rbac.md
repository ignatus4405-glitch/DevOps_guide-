---
id: k8s-rbac
title: RBAC и безопасность кластера
minutes: 28
---

# RBAC и безопасность кластера

По умолчанию под в Kubernetes получает токен ServiceAccount и может обращаться к
API. Если у этого токена широкие права, компрометация пода означает компрометацию
кластера.

## Четыре объекта RBAC

| Объект | Что задаёт |
| --- | --- |
| Role | права в namespace |
| ClusterRole | права на весь кластер |
| RoleBinding | привязка Role к субъекту в namespace |
| ClusterRoleBinding | привязка ClusterRole на весь кластер |

Субъекты: `User`, `Group`, `ServiceAccount`.

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: app
  name: pod-reader
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/log"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  namespace: app
  name: read-pods
subjects:
  - kind: ServiceAccount
    name: ci-deploy
    namespace: app
roleRef:
  kind: Role
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
```

## Проверка прав

```bash
kubectl auth can-i get pods -n app
kubectl auth can-i --list -n app
kubectl auth can-i create deployments --as=system:serviceaccount:app:ci-deploy -n app
kubectl auth reconcile -f rbac.yaml
```

`--as` позволяет проверить права от имени другого субъекта — незаменимо при
отладке «почему CI не может задеплоить».

## ServiceAccount для приложения

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: app
automountServiceAccountToken: false
```

Если приложению не нужен API Kubernetes, токен монтировать не надо. Это убирает
целый класс атак: украденный токен ничего не даёт.

Если нужен — минимальные права:

```yaml
rules:
  - apiGroups: [""]
    resources: ["configmaps"]
    resourceNames: ["app-config"]
    verbs: ["get"]
```

`resourceNames` ограничивает конкретным объектом. Без него — доступ ко всем
configmaps namespace.

## Опасные права

| Право | Почему опасно |
| --- | --- |
| `create pods` | можно запустить привилегированный под и выйти на ноду |
| `get secrets` | читает все секреты namespace |
| `patch deployments` | подмена образа |
| `create clusterrolebindings` | эскалация до cluster-admin |
| `impersonate` | действовать от имени другого |

`cluster-admin` для CI — красный флаг. CI должен уметь деплоить в конкретный
namespace, а не управлять кластером.

## Pod Security

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop: ["ALL"]
```

На уровне namespace — Pod Security Admission:

```yaml
metadata:
  labels:
    pod-security.kubernetes.io/enforce: restricted
```

Уровни: `privileged`, `baseline`, `restricted`. Начинайте с `baseline` в
существующих namespace, иначе сломаете текущие приложения.

## Аудит и сеть

```bash
kubectl get events -A --sort-by=.lastTimestamp | tail
kubectl logs -n kube-system -l component=kube-apiserver | grep audit
```

NetworkPolicy ограничивает сеть, RBAC — API. Это разные слои, нужны оба.

## Подробный разбор темы

Role ограничивает разрешения namespace, ClusterRole действует шире; binding связывает правила с User, Group или ServiceAccount. Правила Kubernetes обычно добавляют разрешения, поэтому случайный широкий ClusterRole может дать доступ сразу во всём кластере. Начинайте с запроса, который должен выполнить workload, и выдавайте только нужные verbs и resources.

Проверьте доступ через `kubectl auth can-i` с нужной identity и namespace, а не только просмотром YAML. Не используйте `default` ServiceAccount с широкими правами. Разделяйте права человека, CI и runtime-приложения; аудитируйте impersonation и binding изменения. Если приложению нужен доступ к API, ограничьте токен и срок его действия, а не кладите kubeconfig администратора в контейнер.

## Пошаговый сценарий

![Порядок действий: RBAC и безопасность кластера](assets/img/howto/07-kubernetes--07-rbac.svg)

1. Назовите identity и API действия, которые нужны workload.
2. Выберите Role или ClusterRole с минимальными resources и verbs.
3. Привяжите роль к отдельному ServiceAccount в нужном namespace.
4. Проверьте can-i и audit log для разрешённых и запрещённых операций.

## Проверьте себя

1. Чем Role отличается от ClusterRole?
2. Почему `create pods` — фактически root на ноде?
3. Зачем `automountServiceAccountToken: false`?
4. Как проверить права CI-аккаунта, не запуская пайплайн?

!!! tip "Практика"
    Задача «Минимальные права» в практикуме: создать ServiceAccount, который
    умеет только обновлять образ в своём namespace.
