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

## Что выбрать: лог, метрика или трейс

| Вопрос | Инструмент | Стоимость |
| --- | --- | --- |
| «Сколько ошибок за час?» | метрика | низкая |
| «Почему упал этот запрос?» | лог | средняя |
| «Где задержка в цепочке?» | трейс | высокая |
| «Что сломается через неделю?» | тренд метрики | низкая |

Метрики агрегируют, логи детализируют, трейсы связывают. Не пытайтесь ответить
на всё одним инструментом.

## Кардинальность и стоимость

Каждая уникальная комбинация меток — отдельная серия. Это главный драйвер
стоимости и проблем производительности.

- нормализуйте URL (`/users/{id}`);
- не добавляйте `user_id`, `request_id`, `email`;
- ограничьте количество значений (status, region, version);
- для деталей — логи и трейсы.

## Наблюдаемость в Kubernetes

```bash
kubectl top pods
kubectl get events --sort-by=.lastTimestamp
kubectl logs deploy/api --since=15m
kubectl describe pod <pod> | tail -20
```

Стандартный стек: kube-prometheus-stack (Prometheus + Grafana + Alertmanager),
Loki для логов, Tempo/Jaeger для трейсов. Устанавливается Helm-чартом.

## Проверка наблюдаемости

Задайте себе три вопроса:

1. Узнаю ли я о проблеме раньше пользователей?
2. Могу ли я за 5 минут понять, какой сервис виноват?
3. Есть ли у дежурного инструкция на каждый алерт?

Если хотя бы один ответ «нет» — наблюдаемость не готова, независимо от количества
дашбордов.

## Короткое резюме

- Метрики (RED/USE), структурированные логи и трассировка отвечают на разные вопросы.
- Prometheus + Grafana — стандарт для метрик и дашбордов; PromQL обязателен в работе.
- Логи должны быть структурированными, без секретов, с trace_id.
- Три столпа связаны: метрика → лог → трасса → причина.

## Подробный разбор темы

Метрика отвечает, насколько часто и насколько сильно происходит событие; лог сохраняет деталь конкретного события; trace связывает работу распределённого запроса через сервисы. Сигналы полезнее вместе: алерт по росту latency указывает на симптом, trace показывает медленный span, а лог содержит причину отказа. Для связи используйте request/trace ID, не помещая в labels уникальный ID каждого запроса.

Сначала определите пользовательский вопрос, затем выберите сигнал и его разрешение. Метрики удобны для агрегации и трендов, логи — для контекста, трассы — для причинности и времени по hop. Любой сигнал имеет цену хранения и обработки; задайте retention, sampling и права доступа. Наблюдаемость — это способность принять действие, а не число установленных агентов.

## Проверьте себя

1. Чем counter отличается от gauge и какой тип выбирать для времени ответа?
2. Какие поля обязаны быть в структурированном логе?
3. Как из алерта по метрике добраться до конкретной строки в базе за минуты?
