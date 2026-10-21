---
id: prometheus
title: Prometheus и PromQL: метрики, которые отвечают на вопросы
minutes: 32
---

# Prometheus и PromQL: метрики, которые отвечают на вопросы

Prometheus — стандарт метрик в облаке: pull-модель, многомерные данные, свой язык
запросов. Его сила — не в сборе, а в возможности ответить на вопрос «почему».

## Модель данных

Метрика = имя + набор меток + значение + время.

```
http_requests_total{job="api", status="500", method="POST"} 42
http_request_duration_seconds_bucket{job="api", le="0.5"} 1203
```

Типы:

| Тип | Использование | Пример |
| --- | --- | --- |
| counter | только растёт | `requests_total` |
| gauge | может расти и падать | `memory_usage_bytes` |
| histogram | распределение | `request_duration_seconds` |
| summary | квантили на клиенте | редко, дорого |

В PromQL для counter всегда используют `rate()`/`increase()`, иначе значение
бессмысленно.

## Pull-модель

Prometheus сам опрашивает цели (`/metrics`). Это даёт:

- контроль: цель недоступна — видно сразу (`up == 0`);
- отсутствие агента на каждом сервисе;
- простое обнаружение через Kubernetes SD.

```yaml
scrape_configs:
  - job_name: kubernetes-pods
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: "true"
```

## PromQL: минимум, который нужен

```promql
# запросы в секунду
sum(rate(http_requests_total[5m]))

# доля ошибок
sum(rate(http_requests_total{status=~"5.."}[5m]))
  / sum(rate(http_requests_total[5m]))

# p95 latency по histogram
histogram_quantile(0.95,
  sum by (le) (rate(http_request_duration_seconds_bucket[5m])))

# память пода
container_memory_working_set_bytes{pod="api-1"}

# топ-5 по CPU
topk(5, sum by (pod) (rate(container_cpu_usage_seconds_total[5m])))
```

Операторы `by`/`without` группируют, `rate` считает скорость, `increase` — прирост
за период, `histogram_quantile` — квантиль по бакетам.

## Частые ошибки

1. **Высокая кардинальность.** Метка `user_id` или `request_id` создаёт миллионы
   серий и убивает Prometheus. Метки — только ограниченные множества.
2. **`rate` на коротком окне** (меньше 4 скрапов) даёт шум. Окно — минимум 4×
   интервал сбора.
3. **Средние вместо квантилей.** Средняя latency скрывает хвост, который чувствуют
   пользователи.
4. **Отсутствие `up`-алерта.** Цель может упасть, и вы узнаете об этом от
   пользователей.

## Кардинальность

| Метка | Кардинальность | Можно? |
| --- | --- | --- |
| status | 5–10 | да |
| method | 5 | да |
| path (нормализованный) | 20–50 | да |
| user_id | миллионы | нет |
| request_id | уникальный | нет |
| raw URL с query | тысячи | нет |

Решение: нормализуйте путь (`/users/{id}` вместо `/users/42`), вынесите
высококардинальные данные в логи или трейсы.

## Recording rules

Тяжёлые запросы считают заранее:

```yaml
groups:
  - name: api
    interval: 30s
    rules:
      - record: job:http_requests:rate5m
        expr: sum by (job) (rate(http_requests_total[5m]))
      - record: job:error_ratio:rate5m
        expr: |
          sum by (job) (rate(http_requests_total{status=~"5.."}[5m]))
          / sum by (job) (rate(http_requests_total[5m]))
```

Дашборды и алерты используют recording rules — быстрее и консистентнее.

## Alerting rules

```yaml
- alert: HighErrorRate
  expr: job:error_ratio:rate5m > 0.05
  for: 5m
  labels:
    severity: page
  annotations:
    summary: "Ошибки > 5% на {{ $labels.job }}"
    runbook_url: "https://wiki/runbooks/high-error-rate"
```

`for` обязателен: без него алерт срабатывает на всплеск. `runbook_url` — чтобы
дежурный не искал, что делать.

## Как устроена TSDB

Prometheus хранит временные ряды блоками по 2 часа, затем компактит в большие
блоки. Внутри — инвертированный индекс по меткам и чанки значений со сжатием.
Это объясняет ограничения:

- высокая кардинальность раздувает индекс и память;
- удаление рядов не мгновенное;
- retention ограничен локальным диском.

### WAL и надёжность

Свежие данные пишутся в WAL, поэтому падение процесса не теряет последние
минуты. При старте WAL воспроизводится. Если диск медленный, WAL становится
узким местом.

### Pull и staleness

Prometheus опрашивает цели. Если цель пропала, ряд помечается stale, а `up`
становится 0. Это не то же самое, что «значение 0»: отличайте отсутствие данных
от нулевого значения.

### Remote write

Для долгого хранения и глобальных запросов используют remote write в
Thanos/Mimir/VictoriaMetrics. Важно: не все метрики нужно отправлять, а
кардинальность надо контролировать до отправки.

### Recording rules

Дорогие запросы лучше считать заранее:

```yaml
groups:
  - name: slo
    interval: 30s
    rules:
      - record: job:request_error_ratio:5m
        expr: sum by (job) (rate(http_requests_total{status=~"5.."}[5m])) / sum by (job) (rate(http_requests_total[5m]))
```

Recording rules упрощают дашборды и алерты, но добавляют ряды. Именуйте
последовательно и документируйте.

### Алерты

Алерт — это вопрос к метрике, а не к человеку. Хороший алерт:

- про симптом (пользователь страдает);
- с порогом и `for`;
- со ссылкой на runbook;
- без дублей (grouping, inhibition).

## Подробный разбор темы

Prometheus собирает метрики pull-запросами и индексирует временные ряды по имени и labels. Каждая новая комбинация labels создаёт новый series, поэтому `user_id`, request ID и произвольный URL могут взорвать cardinality. Для счётчика применяйте `rate()` к окну, достаточному для scrape interval; для gauge используйте текущую величину, не вычисляя rate.

Histogram хранит bucket counts и позволяет оценивать latency по группам наблюдений; summary вычисляет quantile на стороне клиента, что труднее агрегировать между replica. Проверяйте target health, scrape errors, пропуски данных и правила recording/alerting. Запрос PromQL должен отвечать на конкретный вопрос, а не только визуально выглядеть сложным.

## Пошаговый сценарий

![Порядок действий: Prometheus и PromQL: метрики, которые отвечают на вопросы](assets/img/howto/10-observability--03-prometheus.svg)

1. Настройте scrape target и проверьте его статус в targets.
2. Проверьте метрики, labels и ожидаемый тип серии.
3. Напишите PromQL для сигнала и оцените cardinality запроса.
4. Создайте recording/alert rule и проверьте его с реальным окном данных.

## Проверьте себя

1. Почему для counter используют rate, а не сырое значение?
2. Что такое кардинальность и почему `user_id` в метке — плохо?
3. Зачем нужны recording rules?
4. Что даёт `for: 5m` в алерте?

!!! tip "Практика"
    Задача «Метрики и PromQL» в практикуме: поднять Prometheus, собрать метрики
    приложения и написать три запроса.
