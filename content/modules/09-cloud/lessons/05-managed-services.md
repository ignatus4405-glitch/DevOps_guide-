---
id: managed-services
title: Managed-сервисы: RDS, S3, очереди, кэш
minutes: 28
---

# Managed-сервисы: RDS, S3, очереди, кэш

Облако даёт не только виртуальные машины. Managed-сервисы снимают с команды
обслуживание ПО, но добавляют свои ограничения и счёт. Разберём основные классы.

## Когда брать managed

| Критерий | Managed | Своими руками |
| --- | --- | --- |
| Нужна экспертиза DBA | берём | если она есть в команде |
| Регуляторные требования | проверить | возможно, только on-prem |
| Стоимость на больших объёмах | выше | ниже |
| Скорость запуска | минуты | дни |
| Контроль настроек | ограничен | полный |

Правило: если сервис не является вашим конкурентным преимуществом, его лучше
отдать провайдеру.

## Базы данных

**RDS / Aurora / Cloud SQL** дают бэкапы, patching, реплики, failover.

Что важно настроить:

- Multi-AZ для продакшена (failover за минуты);
- automated backups с проверкой восстановления;
- encryption at rest;
- параметры (max_connections, slow_query_log);
- мониторинг (Performance Insights, slow queries);
- отдельная подсеть и security group.

Чего нет или что дороже:

- полный доступ к ОС и `superuser`;
- сложные расширения;
- дешёвые большие инстансы.

```hcl
resource "aws_db_instance" "app" {
  engine              = "postgres"
  engine_version      = "16.3"
  instance_class      = "db.t3.medium"
  allocated_storage   = 100
  multi_az            = true
  backup_retention_period = 14
  storage_encrypted   = true
  deletion_protection = true
}
```

`deletion_protection` и `backup_retention_period` — обязательные для продакшена.
Без них `terraform destroy` удалит базу вместе с бэкапами.

## Object storage (S3/GCS/Blob)

Для файлов, бэкапов, артефактов, статики.

Правила:

- приватность по умолчанию (block public access);
- шифрование (SSE-S3/SSE-KMS);
- версионирование для критичных данных;
- lifecycle-политики (переход в холодное хранилище, удаление);
- политика доступа через IAM, а не ACL.

```bash
aws s3api put-bucket-versioning --bucket app-data --versioning-configuration Status=Enabled
aws s3api put-public-access-block --bucket app-data \
  --public-access-block-configuration BlockPublicAcls=true,BlockPublicPolicy=true
```

Public bucket — одна из самых частых утечек. Проверяйте автоматически
(`checkov`, `prowler`).

## Очереди и события

| Сервис | Модель | Когда |
| --- | --- | --- |
| SQS | очередь | разгрузка, retry, буфер |
| SNS | pub/sub | уведомления, fan-out |
| EventBridge | шина событий | интеграция сервисов |
| Kafka (MSK) | поток | высокая пропускная способность |

Очередь нужна, когда обработка может подождать: загрузка файла, отправка письма,
генерация отчёта. Она же даёт retry и DLQ (dead letter queue) для «отравленных»
сообщений.

```python
# идемпотентная обработка
if processed.exists(message.id):
    return
handle(message)
processed.add(message.id)
```

Очередь гарантирует «хотя бы один раз», поэтому обработчик должен быть
идемпотентным.

## Кэш

Redis/Memcached управляемые. Использовать для:

- сессий;
- результатов тяжёлых запросов;
- rate limiting;
- распределённых блокировок (осторожно).

Кэш без TTL и стратегии инвалидции — источник устаревших данных. Всегда
определяйте, что произойдёт при потере кэша.

## Секреты и параметры

- Secrets Manager / SSM Parameter Store / Secret Manager;
- ротация паролей БД автоматически;
- приложение получает секрет по роли, а не по ключу в коде.

## Проверьте себя

1. Когда managed-база лучше своей и когда дороже?
2. Почему public bucket — критическая ошибка?
3. Что такое DLQ и зачем она нужна?
4. Почему обработчик очереди должен быть идемпотентным?

!!! tip "Практика"
    Задача «Managed-сервисы» в практикуме: поднять RDS с Multi-AZ и бэкапами,
    положить секрет в Secrets Manager.
