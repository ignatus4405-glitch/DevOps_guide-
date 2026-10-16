---
id: k8s-architecture
title: Архитектура кластера Kubernetes
minutes: 40
---

# Архитектура кластера Kubernetes

**Kubernetes — система, которая приводит реальное состояние кластера к желаемому,
описанному в манифестах.** Это ключевая идея: вы не запускаете контейнеры командами,
вы объявляете «хочу 3 реплики этого образа» — контроллеры обеспечивают результат.

![Архитектура Kubernetes](assets/img/k8s-architecture.svg)

## Компоненты control plane

| Компонент | Роль | Что будет при сбое |
| --- | --- | --- |
| kube-apiserver | точка входа API, валидация, авторизация | всё управление недоступно, приложения работают |
| etcd | хранилище состояния (только apiserver пишет в него) | потеря данных о кластере — критично, нужны бэкапы |
| scheduler | выбирает узел для нового pod | новые pod'ы не появляются |
| controller-manager | приводит состояние к желаемому (реплики, endpoints) | реплики не восстанавливаются |
| cloud-controller-manager | интеграция с облаком (LB, диски) | не создаются балансировщики и тома |

## Компоненты узла (worker)

| Компонент | Роль |
| --- | --- |
| kubelet | запускает и следит за pod'ами на узле |
| container runtime (containerd) | запускает контейнеры |
| kube-proxy | правила маршрутизации Service (iptables/IPVS) |
| CNI-плагин (Calico, Cilium, Flannel) | сеть pod'ов |
| csi (диски), device plugins | тома и специализированное оборудование |

## Pod: минимальная единица

Pod — это один или несколько контейнеров, которые всегда вместе: общая сеть
(один IP), общие тома, общий жизненный цикл. Sidecar-контейнеры (прокси, сбор логов,
адаптеры) живут в том же pod.

```bash
kubectl get nodes -o wide
kubectl get pods -A                       # все pod'ы во всех namespace
kubectl describe node worker-1 | head -40 # ресурсы, метки, taints, размещения
kubectl get pods -n kube-system
```

## Объекты верхнего уровня

```
Deployment  → ReplicaSet → Pod (обычный сценарий без состояния)
StatefulSet → стабильные имена и диски (БД, брокеры)
DaemonSet   → по одному pod на каждом узле (агенты, мониторинг)
Job / CronJob → одноразовые и периодические задачи
Service     → стабильный адрес для группы pod
Ingress     → HTTP-маршрутизация по домену и пути
ConfigMap/Secret → конфигурация и секреты
HPA         → автомасштабирование по метрикам
PDB         → гарантии доступности при обновлениях
```

## Service: стабильная точка входа

| Тип | Для чего |
| --- | --- |
| ClusterIP | внутренний адрес внутри кластера (по умолчанию) |
| NodePort | порт на каждом узле (для тестов) |
| LoadBalancer | внешний балансировщик облака |
| Headless (clusterIP: None) | прямая адресация pod'ов (StatefulSet) |

Service находит pod'ы по **селектору меток** (`spec.selector`) и подставляет только
готовые (`readinessProbe`) endpoint'ы. Если селектор не совпадает с labels pod'ов —
у Service нет endpoints, и трафик «никуда не идёт»: самая частая ошибка новичка.

```bash
kubectl get endpoints my-service      # пусто → проверяйте labels и readiness
kubectl get endpointslices -n prod
```

## Планирование: requests, limits, taints

| Параметр | Смысл | Последствие ошибки |
| --- | --- | --- |
| requests.cpu/memory | гарантия ресурсов, влияет на размещение | занижен → pod'ы «душат» друг друга |
| limits.cpu | жёсткое ограничение CPU (throttling) | приложение отвечает медленнее |
| limits.memory | превышение → OOMKill | pod перезапускается с кодом 137 |
| taints/tolerations | «не размещай здесь, кроме разрешённых» | pod'ы уходят на нужные узлы |
| nodeSelector/affinity | требования к узлам | размещение по GPU/зонам |

QoS-классы (Guaranteed > Burstable > BestEffort) определяют, кого выселят первым
при нехватке ресурсов. Для критичных сервисов задавайте requests = limits по памяти.

## Namespace и RBAC

```bash
kubectl get ns
kubectl create ns staging
kubectl -n staging get pods,svc,ingress
kubectl auth can-i delete pods -n prod          # проверка прав
kubectl get role,rolebinding -n staging
```

Namespace — не просто «папка»: это граница RBAC, квот (ResourceQuota) и лимитов
(LimitRange). В командах принято разделять: `dev`, `staging`, `prod`, `monitoring`,
`ingress`, а для каждого сервиса — свой namespace или префикс имён.

## Короткое резюме

- Kubernetes — декларативная система: желаемое состояние описывается, контроллеры его поддерживают.
- Control plane управляет, узлы запускают pod'ы; при потере apiserver приложения продолжают работать.
- Pod — минимальная единица; Service даёт стабильный адрес по селектору меток.
- requests/limits, namespace и RBAC определяют предсказуемость и изоляцию.

## Проверьте себя

1. Что произойдёт с работающими приложениями при падении kube-apiserver?
2. Почему у Service может не быть endpoints и как это проверить?
3. Что случится с pod'ом при превышении limits.memory?
