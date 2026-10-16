---
id: metrics-logs-traces
title: Три столпа наблюдаемости
minutes: 45
---

# Три столпа наблюдаемости

**Наблюдаемость (observability) — способность понять, что происходит внутри системы,
по её внешним сигналам.** Мониторинг отвечает на вопрос «работает ли сервис»,
наблюдаемость — «почему именно так».

![Наблюдаемость](assets/img/observability.svg)

## Метрики: числа во времени

Метрика = имя + метки + значение + время. В Prometheus формат текстовый:

```
http_requests_total{job="api",method="GET",status="200"} 15432
http_request_duration_seconds_bucket{job="api",le="0.5"} 9210
```

| Тип | Смысл | Пример |
| --- | --- | --- |
| Counter | только растёт | количество запросов, ошибок |
| Gauge | может расти и падать | память, соединения, размер очереди |
| Histogram | распределение значений | время ответа (квантили) |
| Summary | квантили на клиенте | редко нужен вместо histogram |

**RED-метод** для сервисов: **Rate** (запросов в секунду), **Errors** (доля ошибок),
**Duration** (время ответа). **USE-метод** для ресурсов: **Utilization**,
**Saturation**, **Errors**.

Четыре «золотых сигнала» (Google SRE): задержка, трафик, ошибки, насыщение.

## Prometheus и Grafana на практике

```yaml
# prometheus.yml — минимальная конфигурация
global:
  scrape_interval: 15s
  evaluation_interval: 15s
rule_files: [alerts.yml]
scrape_configs:
  - job_name: api
    metrics_path: /metrics
    static_configs:
      - targets: ["api-1:8000", "api-2:8000"]
  - job_name: node
    static_configs:
      - targets: ["node-exporter:9100"]
```

```bash
# Проверка целей и мгновенные запросы
curl -s http://localhost:9090/api/v1/targets | jq -r '.data.activeTargets[] | "\(.labels.job)\t\(.health)"'
curl -sG http://localhost:9090/api/v1/query --data-urlencode 'query=rate(http_requests_total[5m])' | jq '.data.result[0].value'
```

Типовые PromQL-запросы, которые нужны в работе:

```promql
# RPS по сервисам
sum by (job) (rate(http_requests_total[5m]))

# Доля ошибок 5xx
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))

# p95 времени ответа
histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))

# Загрузка CPU по узлам
100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Свободное место на диске (в процентах)
100 * (node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"} / node_filesystem_size_bytes)

# Память контейнера относительно лимита
container_memory_working_set_bytes / on (container) kube_pod_container_resource_limits{resource="memory"}
```

!!! tip "Совет"
    Дашборд не должен «показывать всё». Правильный порядок: сначала 4 золотых сигнала,
    затем разбивка по сервисам, только потом глубокая диагностика по узлам и очередям.
    Дашборд, в котором 60 графиков, никто не читает во время инцидента.

## Логи: что и как писать

Хороший лог — **структурированный** (JSON), с уровнями, идентификатором запроса и
контекстом:

```json
{"ts":"2025-01-31T10:15:03Z","level":"error","service":"api","msg":"payment failed",
 "trace_id":"7f3c9a","user_id":"u-128","provider":"stripe","code":"card_declined","latency_ms":412}
```

Правила логирования:

1. **Уровни осмысленно**: `debug` (выключен в проде), `info` (событий), `warn` (аномалия, но работаем), `error` (сломанный путь для пользователя).
2. **Никогда не логируйте секреты**, токены, номера карт, персональные данные.
3. **trace_id** во всех сообщениях одного запроса — это то, что позволяет сложить картину.
4. **Согласованные имена полей** по всем сервисам: `service`, `env`, `level`, `trace_id`.
5. **Без «шума»**: логи уровня info на каждый health-check превращают журнал в мусор.

```bash
# Примеры запросов в Loki (LogQL)
{app="api", env="prod"} |= "error" | json | line_format "{{.msg}} {{.code}}"
sum by (service) (count_over_time({env="prod"} |= "timeout" [5m]))
```

## Трассировка: путь одного запроса

```python
# Автоинструментация OpenTelemetry (фрагмент)
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint="http://otel-collector:4317")))
trace.set_tracer_provider(provider)
FastAPIInstrumentor.instrument_app(app)  # трассировка входящих запросов
```

Трассы показывают, **где именно ушло время**: 800 мс в шлюзе, 50 мс в сервисе оплаты,
2,3 с в запросе к БД без индекса. Без трассировки такие находки превращаются в дни догадок.

## Связь трёх столпов

```
Метрика: p95 выросла до 2,5 с (алерт)
   ↓ (по времени и метке сервиса)
Лог: массовые «timeout», trace_id ...
   ↓ (по trace_id)
Трасса: 2,3 с в SQL-запросе к таблице orders
   ↓
Причина: пропал индекс после миграции
```

Это и есть практическая ценность: от сигнала к причине за минуты, а не часы.

## Короткое резюме

- Метрики (RED/USE), структурированные логи и трассировка отвечают на разные вопросы.
- Prometheus + Grafana — стандарт для метрик и дашбордов; PromQL обязателен в работе.
- Логи должны быть структурированными, без секретов, с trace_id.
- Три столпа связаны: метрика → лог → трасса → причина.

## Проверьте себя

1. Чем counter отличается от gauge и какой тип выбирать для времени ответа?
2. Какие поля обязаны быть в структурированном логе?
3. Как из алерта по метрике добраться до конкретной строки в базе за минуты?
