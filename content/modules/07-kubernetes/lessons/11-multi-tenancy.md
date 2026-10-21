---
id: multi-tenancy
title: Мультитенантность: изоляция команд в кластере
minutes: 30
---

# Мультитенантность: изоляция команд в кластере

Один кластер на всех дешевле, но требует границ: чтобы команда A не съела
ресурсы B, не увидела чужие секреты и не сломала соседей. Изоляция бывает
разной силы.

## Уровни изоляции

| Уровень | Механизм | Сила |
| --- | --- | --- |
| Логическая | namespaces, RBAC, quotas | слабая, общее ядро |
| Сетевая | NetworkPolicy | средняя |
| Ресурсная | ResourceQuota, LimitRange | защита от шумного соседа |
| Узловая | node pools, taints | сильнее |
| Кластерная | отдельный кластер | максимальная |

Для регулируемых данных и сильных команд часто нужен отдельный кластер
(или vcluster), а не namespace.

## Namespace как граница

Namespace изолирует имена, но не сеть и не ядро. По умолчанию поды из разных
namespace могут общаться. Значит нужны NetworkPolicy.

RBAC привязан к namespace через Role/RoleBinding. Давайте права группе, а не
человеку, и через GitOps.

## Квоты

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-a
spec:
  hard:
    requests.cpu: "20"
    requests.memory: 40Gi
    limits.cpu: "40"
    pods: "100"
```

LimitRange задаёт дефолтные requests/limits, чтобы поды без них не проходили.

Без квот один Deployment с replicas: 1000 съест кластер.

## Шумный сосед

Даже с квотами CPU может страдать: limits не гарантируют CPU, throttling
влияет на latency. Помогают:

- requests = limits для критичных сервисов;
- отдельные node pools;
- priority classes;
- topology spread.

## Сеть и DNS

- default-deny NetworkPolicy в namespace;
- разрешить только нужные egress;
- DNS всё ещё общий — рассмотрите отдельные зоны при строгой изоляции.

## Секреты и образы

- RBAC на чтение Secret — минимальный;
- encryption at rest;
- внешний vault вместо Secret;
- admission-политика: только образы из доверенного registry и с подписью.

## Политики

Pod Security Admission на namespace:

```yaml
metadata:
  labels:
    pod-security.kubernetes.io/enforce: restricted
```

Плюс Kyverno/Gatekeeper для своих правил: обязательные labels, запрет
privileged, ограничение registry.

## Стоимость и справедливость

- quota считает requests, а не факт;
- неиспользованная квота простаивает;
- chargeback по namespace требует метрик и тегов.

Мультитенантность — это баланс между плотностью и риском. Записывайте решение
в ADR: почему namespace, а не кластер.

## Как проверить себя

1. Что namespace не изолирует?
2. Зачем LimitRange рядом с ResourceQuota?
3. Как защититься от шумного соседа по CPU?
4. Почему NetworkPolicy обязательна при мультитенантности?
5. Когда нужен отдельный кластер?

!!! tip "Практика"
    Задача «Квоты команды» в практикуме: настроить квоту и проверить отказ.

## Подробный разбор темы

Namespace помогает организовать объекты, но не является полной границей безопасности сам по себе. Для изоляции команд объединяйте RBAC, ResourceQuota, LimitRange, NetworkPolicy и admission policies. Сначала определите модель доверия: могут ли tenants запускать произвольный код, общие ли узлы и какие ресурсы доступны через cloud identity.

Проверьте default-настройки нового namespace: запрет привилегированных Pod, лимиты CPU/памяти, DNS egress, доступ к metadata service и отдельный ServiceAccount. NetworkPolicy работает только при поддержке со стороны CNI и должна проверяться фактическим тестом связи. Для сильной изоляции рассмотрите отдельные node pools или кластеры, учитывая стоимость и операционную сложность.
