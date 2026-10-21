---
id: k8s-storage
title: Storage: PV, PVC, StorageClass, StatefulSet
minutes: 30
---

# Storage: PV, PVC, StorageClass, StatefulSet

В контейнере файловая система исчезает вместе с подом. Для состояния нужен том,
жизненный цикл которого не зависит от пода. В Kubernetes это PV/PVC.

## Три объекта

| Объект | Кто создаёт | Что описывает |
| --- | --- | --- |
| PersistentVolume (PV) | админ или provisioner | реальный диск (EBS, NFS, local) |
| PersistentVolumeClaim (PVC) | разработчик | запрос: «10 ГиБ, ReadWriteOnce» |
| StorageClass | админ | как создавать PV (provisioner, параметры) |

Связывание: PVC находит подходящий PV по размеру, режиму доступа и class.

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: app-data
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: standard
  resources:
    requests:
      storage: 10Gi
```

```yaml
containers:
  - name: app
    volumeMounts:
      - name: data
        mountPath: /var/lib/app
volumes:
  - name: data
    persistentVolumeClaim:
      claimName: app-data
```

## Режимы доступа

| Режим | Значение | Пример |
| --- | --- | --- |
| RWO | один узел на запись | EBS, локальный диск |
| ROX | много узлов только чтение | NFS |
| RWX | много узлов на запись | NFS, EFS, CephFS |
| RWOP | один под | современные CSI |

Ошибка: несколько реплик Deployment с RWO-томом. Второй под не запустится или
получит ошибку монтирования. Для общего состояния нужен RWX или внешняя БД.

## StorageClass и динамическое создание

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  encrypted: "true"
reclaimPolicy: Delete
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
```

- `reclaimPolicy: Delete` — том удаляется вместе с PVC (данные пропадут).
  `Retain` — остаётся, нужно чистить вручную.
- `WaitForFirstConsumer` — том создаётся в зоне, где будет под. Без этого под
  может оказаться в другой зоне и не смонтировать диск.
- `allowVolumeExpansion` — можно увеличить размер без пересоздания.

```bash
kubectl get storageclass
kubectl get pvc
kubectl describe pvc app-data
kubectl get pv
```

PVC в `Pending` — обычно нет подходящего PV или provisioner'а.

## StatefulSet

Для баз данных и кластеров нужны стабильные имена и свои тома:

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: db
spec:
  serviceName: db
  replicas: 3
  selector:
    matchLabels: { app: db }
  template:
    metadata:
      labels: { app: db }
    spec:
      containers:
        - name: postgres
          image: postgres:16
          volumeMounts:
            - name: data
              mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: [ReadWriteOnce]
        resources:
          requests:
            storage: 20Gi
```

Каждый под получает свой PVC (`data-db-0`, `data-db-1`, ...) и стабильное DNS-имя
`db-0.db.default.svc.cluster.local`. Порядок запуска и остановки —
последовательный.

## Бэкапы

Снапшоты CSI:

```yaml
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: db-snapshot
spec:
  volumeSnapshotClassName: csi-snapclass
  source:
    persistentVolumeClaimName: data-db-0
```

Для баз данных снапшот тома — не замена логическому дампу. Нужны оба: снапшот для
быстрого восстановления, дамп для переносимости и проверки целостности.

## Подробный разбор темы

PVC — запрос на хранилище, а PV — предоставленный ресурс; StorageClass определяет динамическое создание и параметры backend. Подходящий размер не гарантирует нужный IOPS, latency или доступность. StatefulSet сохраняет стабильную идентичность Pod и связь с PVC, но не превращает приложение в отказоустойчивое автоматически.

Проверьте access mode и топологию: volume может быть доступен только из одной зоны или одному узлу, что влияет на rescheduling. Для базы данных нужны согласованные backup/restore и тест аварийного переключения. Не удаляйте PVC ради «починки Pending» — сначала изучите events, StorageClass и доступность provisioner; потеря данных может быть необратимой.

## Пошаговый сценарий

![Порядок действий: Storage: PV, PVC, StorageClass, StatefulSet](assets/img/howto/07-kubernetes--06-storage.svg)

1. Сверьте PVC, StorageClass, размер и events provisioner.
2. Проверьте зону, access mode и доступность volume для Pod.
3. Подготовьте backup и восстановите его в изолированное хранилище.
4. Удаляйте или перемещайте PVC только после проверки данных и плана отката.

## Пошаговое объяснение для новичка

Сначала выполните упражнение в учебной среде или на примере из урока. Если действие меняет реальные файлы, сервер или облако, сначала проверьте цель и подготовьте откат. После каждого шага сравните результат с проверкой ниже; при неожиданном результате остановитесь.

### Шаг 1

**Что сделать.** Посмотрите `kubectl get pvc,pv,storageclass` и events; PVC — запрос приложения на диск.

**Как проверить.** Запрос связан с правильным StorageClass и понятна причина, если он Pending.

### Шаг 2

**Что сделать.** Проверьте размер, access mode и зону диска до привязки к Pod.

**Как проверить.** Новый Pod может подключить volume в нужной зоне и с ожидаемым режимом.

### Шаг 3

**Что сделать.** Сделайте backup и восстановите его в новый тестовый PVC.

**Как проверить.** Файл резервной копии можно открыть после восстановления, не затрагивая исходный volume.

### Шаг 4

**Что сделать.** Не удаляйте PVC до проверки политики reclaim и копии данных.

**Как проверить.** Есть доказательство восстановления и понятный план при ошибке удаления.

## Проверьте себя

1. Чем PV отличается от PVC?
2. Что произойдёт с данными при `reclaimPolicy: Delete`?
3. Почему `WaitForFirstConsumer` важен для облачных дисков?
4. Почему Deployment с RWO-томом и 3 репликами не работает?

!!! warning "Важно"
    `kubectl delete pvc` с reclaimPolicy Delete уничтожает данные. Проверяйте
    политику до удаления и делайте бэкап.
