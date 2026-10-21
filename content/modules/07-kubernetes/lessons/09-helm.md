---
id: helm
title: Helm, Kustomize и операторы
minutes: 28
---

# Helm, Kustomize и операторы

Манифесты быстро становятся неудобными: для staging и prod отличаются теги,
реплики и ресурсы, а копировать YAML вручную — источник расхождений. Для управления
этим есть три подхода.

## Kustomize: патчи без шаблонов

Базовая конфигурация + overlays:

```
base/
  deployment.yaml
  service.yaml
  kustomization.yaml
overlays/
  staging/
    kustomization.yaml
  prod/
    kustomization.yaml
```

```yaml
# overlays/prod/kustomization.yaml
resources:
  - ../../base
images:
  - name: app
    newTag: 1.4.2
replicas:
  - name: app
    count: 5
patches:
  - path: resources.yaml
```

```bash
kubectl apply -k overlays/prod
kustomize build overlays/prod | kubectl diff -f -
```

Плюсы: чистый YAML, встроен в kubectl (`-k`), легко читать diff.
Минусы: нет управления версиями пакетов и зависимостями.

## Helm: пакетный менеджер

Chart — набор шаблонов с параметрами.

```
mychart/
  Chart.yaml
  values.yaml
  templates/
    deployment.yaml
    service.yaml
    _helpers.tpl
```

```yaml
# templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "mychart.fullname" . }}
spec:
  replicas: {{ .Values.replicaCount }}
  template:
    spec:
      containers:
        - name: app
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
```

```bash
helm install app ./mychart -f values-prod.yaml
helm upgrade app ./mychart -f values-prod.yaml --atomic --timeout 5m
helm rollback app 1
helm history app
helm template . -f values-prod.yaml | kubectl diff -f -
```

`--atomic` откатывает релиз при неудаче. `helm template` + `kubectl diff` —
способ увидеть изменения до применения.

## Helm: правила, которые спасают

1. **Не редактируйте ресурсы, созданные Helm, вручную** — следующая установка
   перезапишет.
2. **Пиньте версии chart'ов** (`--version 12.3.1`), иначе обновление может
   принести breaking changes.
3. **Храните values в git**, секреты — через External Secrets/Sealed Secrets.
4. **Используйте `--atomic` и `--wait`** для продакшена.
5. **Проверяйте `helm template` в CI**, а не только при деплое.

## Сравнение

| | Kustomize | Helm |
| --- | --- | --- |
| Подход | патчи | шаблоны + пакеты |
| Зависимости | нет | есть (subcharts) |
| Секреты | внешние | values + внешние |
| Diff | нативный | через template |
| Когда | свои приложения | сторонние пакеты |

Часто используют вместе: Helm для сторонних компонентов (ingress-nginx,
prometheus-operator), Kustomize для своих сервисов.

## Операторы

Оператор — контроллер, который управляет приложением через CRD. Вместо «создать
StatefulSet, Service, PVC» вы создаёте один объект:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: db
spec:
  instances: 3
  storage:
    size: 20Gi
```

Оператор сам делает бэкапы, failover, обновления. Популярные: CloudNativePG,
Prometheus Operator, cert-manager, Strimzi (Kafka).

Цена: оператор — ещё один компонент с правами в кластере. Проверяйте его RBAC и
обновления.

## GitOps

Argo CD или Flux следят за git-репозиторием и приводят кластер к описанному
состоянию. Деплой = merge PR.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: app
spec:
  source:
    repoURL: https://github.com/org/deploy
    path: overlays/prod
  destination:
    server: https://kubernetes.default.svc
    namespace: app
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

Плюсы: аудит изменений, дрейф исправляется автоматически, откат — revert коммита.

## Как устроен чарт

```text
mychart/
  Chart.yaml
  values.yaml
  templates/
    deployment.yaml
    service.yaml
    _helpers.tpl
```

`Chart.yaml` задаёт имя и версию. `values.yaml` — значения по умолчанию.
Шаблоны используют `{{ .Values.image.tag }}` и хелперы из `_helpers.tpl`.

Проверка перед установкой:

```bash
helm lint mychart
helm template mychart --values prod.yaml > rendered.yaml
helm install api mychart -f prod.yaml --dry-run=server
```

`helm template` полезен в ревью: видно итоговые манифесты, а не шаблоны.
`--dry-run=server` проверяет ещё и API-валидацию.

## Обновление и откат

```bash
helm upgrade api mychart -f prod.yaml --atomic --timeout 5m
helm history api
helm rollback api 3
```

`--atomic` автоматически откатывает релиз, если что-то не встало. Без него
неудачный upgrade оставляет кластер в промежуточном состоянии.

## Частые ошибки

- значения prod лежат в `values.yaml` и попадают в dev;
- секреты в values вместо внешнего хранилища;
- версия чарта не обновляется при изменении шаблонов;
- `helm upgrade` без `--history-max` раздувает историю.

## Подробный разбор темы

Helm рендерит chart templates с values и ведёт release history; Kustomize накладывает patches на базовые ресурсы без собственного template language. Первый удобен для параметризуемого продукта и версионирования chart, второй — для overlay окружений и декларативных различий. В обоих случаях проверяйте конечный YAML, который уйдёт в API server.

CRD расширяет Kubernetes API, а controller/operator реализует поведение для нового объекта. Удаление CRD может затронуть все созданные им ресурсы, поэтому проверяйте миграцию и порядок удаления. Для релиза храните зафиксированные values, версию chart и manifest; rollback Helm не откатывает автоматически внешние данные и необратимые изменения схемы.

## Пошаговый сценарий

![Порядок действий: Helm, Kustomize и операторы](assets/img/howto/07-kubernetes--09-helm.svg)

1. Зафиксируйте chart, values и версию релиза.
2. Отрендерите YAML и проверьте selectors, secrets и CRDs.
3. Примените изменение в тестовом namespace и дождитесь readiness.
4. Проверьте rollback, учитывая, что данные и CRD не всегда откатываются.

## Пошаговое объяснение для новичка

Сначала выполните упражнение в учебной среде или на примере из урока. Если действие меняет реальные файлы, сервер или облако, сначала проверьте цель и подготовьте откат. После каждого шага сравните результат с проверкой ниже; при неожиданном результате остановитесь.

### Шаг 1

**Что сделать.** Выберите chart и версию, затем сохраните используемый values-файл.

**Как проверить.** Можно повторить конкретный релиз, а не полагаться на «последний chart».

### Шаг 2

**Что сделать.** Запустите `helm template релиз chart -f values.yaml` и прочитайте полученные YAML до применения.

**Как проверить.** Проверены namespace, selectors, образы и отсутствие секрета в открытом выводе.

### Шаг 3

**Что сделать.** Сначала установите chart в тестовый namespace и дождитесь rollout.

**Как проверить.** Все ресурсы созданы, Pod ready и тестовый запрос проходит.

### Шаг 4

**Что сделать.** Проверьте `helm history` и тестовый rollback; отдельно убедитесь, что данные не считаются автоматически обратимыми.

**Как проверить.** Версию приложения можно откатить, а миграции/volume имеют отдельный план восстановления.

## Проверьте себя

1. Чем Kustomize отличается от Helm?
2. Что делает `helm upgrade --atomic`?
3. Почему нельзя править ресурсы Helm вручную?
4. Какую проблему решает GitOps?

!!! tip "Практика"
    Задача «Helm-чарт» в практикуме: параметризовать манифесты и отрендерить
    их для двух окружений.
