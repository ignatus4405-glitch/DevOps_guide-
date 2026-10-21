---
id: terraform-state
title: Terraform state: backend, locking, drift
minutes: 30
---

# Terraform state: backend, locking, drift

![Код, состояние и реальная инфраструктура](assets/img/terraform-state.svg)

State — главная особенность Terraform и главный источник проблем. Он сопоставляет
ресурсы в облаке с кодом. Если state потерян или повреждён, Terraform перестаёт
понимать, что уже создано.

## Что лежит в state

- адреса ресурсов (`aws_instance.web`);
- идентификаторы в облаке (`i-0abc...`);
- атрибуты (IP, ARN, теги);
- зависимости между ресурсами.

State и сохранённый plan могут содержать секреты **в открытом виде** — например,
пароли БД, токены и приватные ключи. Поэтому относитесь к ним как к секретным
файлам: не коммитьте в Git, ограничивайте IAM-доступ и защищайте резервные копии.

`sensitive = true` только маскирует значение в CLI/UI; оно не шифрует и не
удаляет его из state или plan. Шифрование backend (например, SSE-KMS в S3)
защищает данные при хранении, но не заменяет контроль доступа. В Terraform 1.10+
`ephemeral = true` позволяет не сохранять поддерживаемые значения в plan/state;
write-only аргументы ресурсов, появившиеся в Terraform 1.11+, позволяют передать
значение провайдеру, не записывая его в state. Эти механизмы доступны только для
поддерживаемых переменных, ресурсов и аргументов.

## Local state и его проблемы

По умолчанию `terraform.tfstate` лежит рядом с кодом. Это работает одному
человеку на ноутбуке и ломается в команде:

- два инженера применяют одновременно — state перезаписывается;
- state в git — конфликты и утечки;
- потеря ноутбука — потеря управления ресурсами.

## Remote backend

```hcl
terraform {
  required_version = ">= 1.10.0"
  backend "s3" {
    bucket       = "org-tfstate"
    key          = "prod/network/terraform.tfstate"
    region       = "eu-west-1"
    encrypt      = true
    use_lockfile = true
  }
}
```

Для S3 используйте встроенную блокировку `use_lockfile` (Terraform 1.10+).
Старый параметр `dynamodb_table` пока поддерживается для совместимости, но
объявлен устаревшим; планируйте миграцию вместо того, чтобы вводить его в новые
backend-конфигурации.

| Backend | Locking | Комментарий |
| --- | --- | --- |
| S3 | `use_lockfile` | нативная блокировка, Terraform 1.10+ |
| S3 + DynamoDB | да, legacy | поддерживается для миграции, параметр deprecated |
| GCS | да | нативный для GCP |
| Azure Storage | да | нативный для Azure |
| Terraform Cloud | да | плюс UI и политики |
| Postgres | да | self-hosted |

Locking не даёт двум `apply` работать одновременно. Без него возможно
повреждение state и дублирование ресурсов. При переходе существующего backend
с `dynamodb_table` сохраните резервную копию, добавьте `use_lockfile = true` и
выполните `terraform init -migrate-state`; не удаляйте DynamoDB-таблицу, пока
все workspace не мигрированы и старые процессы не остановлены.

### IAM для S3 backend

Выдавайте доступ только к нужному bucket/prefix и конкретному state key:

- `s3:ListBucket` — на bucket, с условием по нужному prefix;
- `s3:GetObject` и `s3:PutObject` — на объект state;
- `s3:GetObject`, `s3:PutObject` и `s3:DeleteObject` — на соответствующий объект
  `<key>.tflock` (Terraform удаляет lock-файл после завершения операции);
- при SSE-KMS — минимальные `kms:Encrypt`, `kms:Decrypt` и `kms:GenerateDataKey`
  на используемый ключ.

Не выдавайте `s3:DeleteObject` на сам state без отдельной необходимости. Включите
версионирование bucket для восстановления предыдущего state, блокируйте публичный
доступ и требуйте TLS. `encrypt = true` включает шифрование S3; для customer-managed
KMS key дополнительно настройте `kms_key_id` и IAM выше.

## Команды работы со state

```bash
terraform state list
terraform state show aws_instance.web
terraform state mv aws_instance.web module.app.aws_instance.web
terraform state rm aws_instance.web        # перестать управлять, не удаляя
terraform import aws_instance.web i-0abc   # начать управлять существующим
```

`state mv` — при рефакторинге модулей. Без него Terraform удалит старый ресурс и
создаст новый.

`import` — для ресурсов, созданных вручную. В Terraform 1.5+ есть блок `import`
в конфигурации, что позволяет делать это декларативно и с plan.

## Drift: расхождение кода и реальности

Drift — когда кто-то изменил ресурс в консоли. Terraform узнаёт об этом на
`plan` и предлагает вернуть к коду (или принять изменение).

```bash
terraform plan -detailed-exitcode
# 0 — изменений нет
# 2 — есть drift
# 1 — ошибка
```

Политика:

- ручные изменения запрещены (или только через break-glass);
- `plan` в CI на расписании ловит drift;
- при обнаружении — либо код обновляют, либо ресурс возвращают.

## Секреты в state

Пароль, созданный Terraform, хранится в state. Меры:

- шифрование backend (SSE, KMS);
- ограничение доступа к bucket;
- `sensitive = true` в переменных (скрывает вывод, но не state);
- для секретов — внешний менеджер, а в Terraform — ссылка.

## Разделение state

Не держите всё в одном state:

| Стек | Почему отдельно |
| --- | --- |
| network | меняется редко, нужен всем |
| data (RDS, buckets) | жизненный цикл дольше приложений |
| app | меняется часто |
| monitoring | отдельные права |

Плюсы: меньше blast radius, быстрее plan, разные команды не блокируют друг друга.
Связь между стеками — через `data`-источники или outputs.

```hcl
data "terraform_remote_state" "network" {
  backend = "s3"
  config = {
    bucket = "org-tfstate"
    key    = "prod/network/terraform.tfstate"
    region = "eu-west-1"
  }
}
```

## Переезд state без пересоздания

Когда модуль переименовывают или ресурс переносят, Terraform видит «удалить
старое, создать новое». Чтобы этого избежать:

```bash
terraform state list
terraform state mv aws_instance.old aws_instance.new
terraform plan
```

Для массового переноса между state-файлами:

```bash
terraform state pull > backup.tfstate
terraform state mv -state-out=other.tfstate module.a.aws_s3_bucket.b module.b.aws_s3_bucket.b
```

Всегда делайте резервную копию state перед `mv` и `rm`. `state rm` не удаляет
ресурс в облаке — он лишь перестаёт им управлять, и это нужно понимать перед
применением.

## Подробный разбор темы

State связывает адрес Terraform-ресурса с реальным объектом провайдера и хранит метаданные, необходимые для планирования. Потеря state не удаляет ресурс автоматически, но заставляет Terraform считать его неизвестным; импорт и восстановление требуют сверки фактической инфраструктуры. Не храните state в Git: там могут находиться секретные поля и данные о ресурсах.

Remote backend должен обеспечивать locking и резервное копирование. Lock предотвращает параллельное изменение одного state, но не заменяет review плана. Drift выявляется сравнением с API provider; выясните, была ли ручная правка аварийной, затем решите — импортировать её в код или вернуть желаемое состояние. Не используйте `force-unlock`, пока не установлено, что держатель lock действительно завершился.

## Проверьте себя

1. Зачем нужен remote backend и что даёт locking?
2. Что делает `terraform state rm` и чем отличается от удаления ресурса?
3. Как обнаружить drift в CI?
4. Почему state стоит разделять на стеки?

!!! tip "Практика"
    Задача «Remote state» в практикуме: перенести state в S3 с блокировкой и
    проверить параллельный apply.
