---
id: http-proxy-balancing
title: HTTP, TLS, балансировка и reverse proxy
minutes: 40
---

# HTTP, TLS, балансировка и reverse proxy

## HTTP: что важно знать на практике

| Метод | Идемпотентный? | Применение |
| --- | --- | --- |
| GET | да | чтение, кэшируется |
| POST | нет | создание ресурса |
| PUT | да | полная замена |
| PATCH | нет | частичное изменение |
| DELETE | да | удаление |

Коды ответа по группам: **2xx** успех, **3xx** редирект (`301/302`, `304 Not Modified`),
**4xx** ошибка клиента (`400`, `401`, `403`, `404`, `429 Too Many Requests`),
**5xx** ошибка сервера (`500`, `502 Bad Gateway`, `503`, `504 Gateway Timeout`).

Для диагностики 5xx полезно знать: **502** — прокси не смог получить ответ от
бэкенда (сервис упал/недоступен), **504** — бэкенд не ответил вовремя (таймаут).
Именно эти две ошибки чаще всего означают «приложение не поднялось после деплоя».

```bash
curl -sS -o /dev/null -w "%{http_code} %{time_connect}s %{time_total}s\n" https://api.example.com/health
curl -v -H "Authorization: Bearer $TOKEN" https://api.example.com/v1/users
curl -sS https://api.example.com/metrics | head
```

**Ключевые заголовки**, которые DevOps настраивает и смотрит:
`Host`, `X-Forwarded-For` (реальный IP клиента), `X-Request-ID` (трассировка),
`Cache-Control`, `Retry-After` (429/503), `Content-Type`, `Authorization`.

## TLS: как всё работает и где ломается

```
Клиент → ClientHello (версии, алгоритмы) → Сервер → ServerHello + сертификат
→ Проверка цепочки и имени → Обмен ключами → Зашифрованный канал → HTTP внутри
```

```bash
openssl s_client -connect api.example.com:443 -servername api.example.com </dev/null \
  | openssl x509 -noout -subject -issuer -dates -ext subjectAltName
```

Что проверить при проблемах TLS:

1. **Срок действия** — самая частая авария. Ставьте алерт за 14–30 дней.
2. **SAN должен содержать домен**, к которому идут клиенты (не только CN).
3. **Цепочка** — сервер обязан отдать промежуточные сертификаты (`fullchain.pem`).
4. **Протоколы** — TLS 1.2+; SSLv3/TLS1.0 отключают.
5. **Автоматизация** — certbot/ACME или managed-сертификат в облаке + перезагрузка сервиса.

!!! danger "Осторожно"
    Обновление сертификата без перезагрузки конфигурации nginx (или без reload
    балансировщика) оставляет старый сертификат в памяти процесса. Всегда включайте
    `certbot renew --deploy-hook "systemctl reload nginx"`.

## Reverse proxy: nginx, который делает 80 % работы

```nginx
# /etc/nginx/conf.d/api.conf
upstream api_backend {
    server 10.0.1.10:8080 max_fails=3 fail_timeout=10s;
    server 10.0.1.11:8080 max_fails=3 fail_timeout=10s;
    keepalive 32;
}

server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate     /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    # Корректные адреса клиентов в логах
    set_real_ip_from 10.0.0.0/8;
    real_ip_header X-Forwarded-For;

    location / {
        proxy_pass http://api_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 3s;
        proxy_read_timeout 30s;

        # Перезапрос при проблемах с бэкендом
        proxy_next_upstream error timeout http_502 http_504;
    }
}

server {                       # редирект с http на https
    listen 80;
    server_name api.example.com;
    return 301 https://$host$request_uri;
}
```

```bash
sudo nginx -t                  # ПРОВЕРКА конфига до reload — обязательно
sudo systemctl reload nginx    # плавная перезагрузка без разрыва соединений
```

| Инструмент | Роль | Особенность |
| --- | --- | --- |
| nginx | reverse proxy, `listen 443`, статика, терминация TLS | самый распространённый |
| HAProxy | балансировка L4/L7, высокие нагрузки | гибкие health-check |
| Traefik / Envoy | балансировка в контейнерах, service mesh | автоопределение сервисов |
| Cloud LB (ALB/NLB) | managed-балансировщик | интеграция с IAM, WAF, автоскейл |

### Балансировка: алгоритмы и health-check

| Алгоритм | Когда выбирают |
| --- | --- |
| round-robin | все узлы равны |
| least connections | запросы долгие и неравномерные |
| ip-hash | нужна «липкая» сессия без общей сессионной БД |
| weighted | узлы разной мощности |

Health-check проверяет эндпоинт (`/health`) с интервалом 5–10 с и убирает
недоступный узел из балансировки. **Важно:** `/health` не должен проверять
внешние зависимости слишком строго — иначе кратковременный сбой БД выведет все
узлы из балансировки разом.

## Прокси, CDN и таймауты

- **Forward proxy** — ходит в интернет от имени клиента (корпоративный выход).
- **Reverse proxy** — принимает трафик и распределяет к бэкендам.
- **CDN** — кэширует статику и часть API у границы сети: снижает задержку и нагрузку.
- **Таймауты** должны быть согласованы по всей цепочке: если балансировщик ждёт 30 с,
  а приложение — 60 с, вы получите 504, и логи приложения будут «успешными».

!!! tip "Совет"
    Правило «меньше вверх, больше вниз»: клиентский таймаут < таймаут балансировщика <
    таймаут приложения. Тогда ошибки становятся предсказуемыми и видно, кто виноват.

## Короткое резюме

- HTTP-коды говорят, кто виноват: 4xx — клиент, 5xx — сервер/цепочка.
- TLS ломается по сроку, SAN, цепочке или устаревшим протоколам — проверяйте `openssl`.
- nginx/HAProxy терминируют TLS, маршрутизируют и балансируют; конфиг проверяем `nginx -t`.
- Таймауты и health-check нужно согласовывать между всеми участниками цепочки.

## Проверьте себя

1. Чем 502 отличается от 504 и что это говорит о приложении?
2. Что обязательно проверить при отладке TLS и как это сделать из терминала?
3. Почему «слишком умный» health-check опасен для всего сервиса?
