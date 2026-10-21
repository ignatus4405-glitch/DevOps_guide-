---
id: tracing
title: Трейсинг: OpenTelemetry, span, контекст
minutes: 28
---

# Трейсинг: OpenTelemetry, span, контекст

Метрики говорят «стало медленно», логи — «вот ошибка», трейсы — **где именно**
запрос провёл время. Это единственный способ разобраться в микросервисной
цепочке из десяти вызовов.

## Модель

- **trace** — весь путь запроса, идентификатор `trace_id`;
- **span** — операция внутри (HTTP-вызов, запрос в БД), с длительностью и
  атрибутами;
- **parent/child** — иерархия span'ов;
- **context propagation** — передача `trace_id` через заголовки.

```
GET /checkout                 [================] 480 ms
├── auth.verify               [==]              40 ms
├── db.query orders           [=========]      210 ms
└── stripe.charge             [=======]        180 ms
```

Сразу видно, что 210 мс — база, а не платёжный шлюз.

## OpenTelemetry

Единый SDK и протокол (OTLP) для метрик, логов и трейсов. Не привязан к вендору:
можно отправлять в Jaeger, Tempo, Datadog, Honeycomb.

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("checkout") as span:
    span.set_attribute("order.id", order_id)
    ...
```

Для популярных фреймворков есть автоинструментация:

```bash
opentelemetry-instrument python app.py
```

## Контекст и заголовки

Стандарт W3C Trace Context:

```
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
```

Если сервис не передаёт `traceparent`, трейс обрывается на нём. Проверьте, что
nginx/балансировщик не вырезает заголовок.

## Сэмплирование

Полный сбор всех трейсов дорог. Варианты:

| Стратегия | Что делает | Когда |
| --- | --- | --- |
| head-based | решает в начале | просто, но можно потерять редкие ошибки |
| tail-based | решает после | сохраняет ошибки и медленные, дороже |
| probabilistic | 1–10 % | базовый вариант |
| always-on для ошибок | 100 % при error | обязательно |

Правило: ошибки и медленные запросы сэмплируют полностью, остальное — по
проценту.

## Что смотреть в трейсе

1. **Самый долгий span** — узкое место.
2. **Количество вызовов** — N+1 запросы.
3. **Ошибки** — на каком шаге и с каким кодом.
4. **Атрибуты** — версия сервиса, инстанс, регион.

```bash
# Tempo/Grafana: поиск по trace_id
curl http://tempo:3200/api/traces/4bf92f3577b34da6
```

## Стоимость и объём

Трейсы — самые объёмные данные. Ограничивайте:

- сэмплирование;
- длительность хранения (7–14 дней);
- количество атрибутов (не пишите в span всё тело запроса);
- размер батча и очередь экспортёра.

## Подробный разбор темы

Span описывает одну операцию с началом, концом, статусом и атрибутами; parent-child связи показывают структуру запроса через сервисы. Context propagation передаёт trace ID через HTTP headers или messaging metadata. Если один компонент не прокидывает context, trace распадается на несколько независимых частей, даже когда каждый сервис экспортирует свои spans.

Используйте span для границы операции и измеряйте ключевые этапы, не создавая отдельный span на каждую мелкую функцию. Не помещайте секреты или персональные данные в attributes; контролируйте cardinality и sampling. При анализе смотрите critical path: суммарная длительность вложенных spans не равна wall-clock времени запроса, потому что некоторые операции выполняются параллельно.

## Пошаговый сценарий

![Порядок действий: Трейсинг: OpenTelemetry, span, контекст](assets/img/howto/10-observability--05-tracing.svg)

1. Добавьте context propagation для входящего запроса и downstream вызова.
2. Проверьте trace/span IDs и parent-child связь через все сервисы.
3. Настройте sampling по ошибкам и важности, контролируя объём данных.
4. Пройдите trace end-to-end и найдите узкий участок по span timing.

## Проверьте себя

1. Чем трейс отличается от метрики и лога?
2. Что произойдёт, если сервис не пробрасывает traceparent?
3. Зачем нужно tail-based сэмплирование?
4. Что смотреть в трейсе в первую очередь?

!!! tip "Практика"
    Задача «Трейсинг» в практикуме: добавить OpenTelemetry в два сервиса и
    найти медленный вызов.
