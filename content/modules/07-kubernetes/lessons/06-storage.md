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

## Проверьте себя

1. Чем PV отличается от PVC?
2. Что произойдёт с данными при `reclaimPolicy: Delete`?
3. Почему `WaitForFirstConsumer` важен для облачных дисков?
4. Почему Deployment с RWO-томом и 3 репликами не работает?

!!! warning "Важно"
    `kubectl delete pvc` с reclaimPolicy Delete уничтожает данные. Проверяйте
    политику до удаления и делайте бэкап.
