---
id: autoscaling
title: Автомасштабирование: HPA, VPA, KEDA и кластер
minutes: 32
---

# Автомасштабирование: HPA, VPA, KEDA и кластер

Автомасштабирование звучит как «добавить подов, когда нагрузка выросла». На
деле это несколько независимых контуров, и они конфликтуют, если их не
согласовать.

## HPA: горизонтальное

HorizontalPodAutoscaler меняет число реплик по метрике:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
spec:
  scaleTargetRef: {apiVersion: apps/v1, kind: Deployment, name: api}
  minReplicas: 2
  maxReplicas: 20
  metrics:
    - type: Resource
      resource: {name: cpu, target: {type: Utilization, averageUtilization: 60}}
```

HPA сравнивает текущее значение с целевым и меняет реплики. Важно:

- метрика должна быть доступна через metrics-server/adapters;
- requests должны быть реалистичными (utilization считается от requests);
- есть задержка: поды стартуют не мгновенно.

## Проблема холодного старта

HPA видит нагрузку, когда она уже пришла. Пока поды стартуют, пользователи
ждут. Лечение:

- minReplicas с запасом;
- predictive scaling (KEDA/облако);
- быстрый старт (меньше образ, readiness);
- queue-based scaling.

## VPA: вертикальное

VerticalPodAutoscaler подбирает requests/limits по фактическому потреблению.
Режимы: Off (рекомендации), Initial, Auto.

VPA и HPA по CPU конфликтуют: один меняет requests, другой — replicas. Не
включайте оба на одну метрику.

## KEDA: масштабирование по событиям

KEDA добавляет scaler'ы: длина очереди, lag Kafka, число сообщений в RabbitMQ.

```yaml
triggers:
  - type: kafka
    metadata:
      topic: orders
      lagThreshold: "100"
```

Это точнее CPU: очередь растёт раньше, чем процессор.

## Cluster Autoscaler / Karpenter

HPA создаёт поды, но им нужны узлы. Cluster Autoscaler добавляет узлы в group,
Karpenter подбирает инстансы напрямую.

Важно:

- requests должны соответствовать реальности, иначе узлы неэффиктивны;
- taints/tolerations и affinity влияют на размещение;
- scale-down может убить поды с локальными данными.

## Метрики и стабильность

HPA умеет `behavior`:

```yaml
behavior:
  scaleDown:
    stabilizationWindowSeconds: 300
```

Без стабилизации число реплик «дёргается». Для latency-критичных сервисов
масштабируйтесь по p95/очереди, а не по CPU.

## Стоимость

Автомасштабирование не бесплатно: минимумы, простой, перерасход на пиках.
Считайте unit-экономику: стоимость запроса при разной нагрузке.

## Как проверить себя

1. От чего HPA считает utilization?
2. Почему HPA запаздывает?
3. Чем KEDA лучше HPA для очередей?
4. Почему VPA и HPA конфликтуют?
5. Зачем `stabilizationWindowSeconds`?

!!! tip "Практика"
    Задача «HPA и очередь» в практикуме: выбрать метрику и границы.
