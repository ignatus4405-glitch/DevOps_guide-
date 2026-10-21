---
id: tls-deep
title: TLS: рукопожатие, сертификаты, Let's Encrypt
minutes: 30
---

# TLS: рукопожатие, сертификаты, Let's Encrypt

TLS шифрует трафик и подтверждает, что сервер — тот, за кого себя выдаёт. Ошибки
TLS выглядят пугающе (`certificate verify failed`), но сводятся к нескольким
причинам.

## Что происходит при подключении

1. **ClientHello** — клиент предлагает версии TLS, шифры, SNI (имя хоста).
2. **ServerHello + сертификат** — сервер выбирает параметры и присылает цепочку.
3. **Проверка цепочки** — клиент проверяет подпись, срок, домен и доверие к CA.
4. **Обмен ключами** — ECDHE создаёт общий секрет.
5. **Завершение** — обе стороны проверяют handshake MAC.

Только после этого передаются данные. Поэтому ошибка сертификата означает, что
приложение вообще не получило HTTP-ответ.

## Цепочка доверия

```bash
openssl s_client -connect api.example.com:443 -servername api.example.com -showcerts
```

Сервер должен отдавать **полную цепочку**: leaf (ваш сертификат) + intermediate.
Корневой сертификат в цепочке не нужен — он уже в хранилище клиента. Если
intermediate не отдан, браузер может дотянуть его сам (AIА), а `curl`/Python —
нет, и вы получите ошибку.

Проверка:

```bash
openssl s_client -connect api.example.com:443 -servername api.example.com </dev/null 2>/dev/null | openssl x509 -noout -dates -subject -issuer
curl -vI https://api.example.com 2>&1 | grep -E 'subject|issuer|expire'
```

## Срок действия и мониторинг

Сертификаты Let's Encrypt живут 90 дней. Просроченный сертификат — одна из самых
обидных аварий: всё работает, но клиенты видят предупреждение.

Мониторинг:

```bash
echo | openssl s_client -connect api.example.com:443 -servername api.example.com 2>/dev/null \
  | openssl x509 -noout -enddate
```

Алерт за 21 и 7 дней до истечения. Автоматическое продление через certbot:

```bash
sudo certbot renew --dry-run
systemctl list-timers | grep certbot
```

`--dry-run` проверяет продление без изменения сертификатов — обязательный шаг
после настройки.

## Let's Encrypt: как работает выдача

ACME-протокол подтверждает контроль над доменом:

| Challenge | Как проверяется | Когда удобен |
| --- | --- | --- |
| HTTP-01 | файл на `http://domain/.well-known/acme-challenge/` | есть открытый 80 порт |
| DNS-01 | TXT-запись `_acme-challenge` | wildcard, нет 80 порта |
| TLS-ALPN-01 | специальный TLS-сертификат на 443 | только TLS |

Для wildcard (`*.example.com`) обязателен DNS-01. В Kubernetes это делает
cert-manager с провайдером DNS.

## Типичные ошибки

| Ошибка | Причина | Лечение |
| --- | --- | --- |
| `certificate has expired` | не продлили | certbot renew, автопродление |
| `unable to get local issuer certificate` | не отдана цепочка | добавить intermediate |
| `certificate is valid for other name` | не тот домен/SNI | проверить SAN и SNI |
| `self-signed certificate` | внутренний CA не в trust store | добавить CA |
| `SSL_ERROR_RX_RECORD_TOO_LONG` | HTTPS на HTTP-порт | проверить порт и протокол |
| `handshake failure` | нет общего шифра/версии | обновить TLS-политику |

## TLS в Kubernetes и ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api
spec:
  tls:
    - hosts: [api.example.com]
      secretName: api-tls
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: api
                port:
                  number: 80
```

Сертификат хранится в Secret типа `kubernetes.io/tls` (`tls.crt`, `tls.key`).
cert-manager создаёт его автоматически из Issuer/ClusterIssuer.

## Подробный разбор темы

TLS-сертификат проверяется относительно имени, цепочки доверия, срока действия и назначения. Сертификат может быть действительным, но не подходить hostname из-за отсутствующего SAN; wildcard покрывает только один уровень поддомена. SNI сообщает серверу имя до начала HTTP, поэтому при нескольких доменах на IP тест без правильного SNI может показать чужой сертификат.

Проверяйте цепочку, SAN и даты, а затем тестируйте путь обновления, включая reload процесса и срок действия после автоматической выдачи ACME. Не отключайте верификацию сертификата как постоянное решение: это маскирует ошибку и открывает возможность MITM. Если proxy и backend используют TLS независимо, проверяйте оба соединения и соответствующие trust store.

## Проверьте себя

1. Почему сервер должен отдавать intermediate-сертификат?
2. Чем DNS-01 отличается от HTTP-01 и когда он обязателен?
3. Какая команда покажет дату истечения сертификата?
4. Почему просроченный сертификат — это авария, а не косметика?

!!! tip "Практика"
    Задача «TLS-проверка» в практикуме: проверить цепочку и срок действия
    сертификата через openssl.
