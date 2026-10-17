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

State **не** содержит секретов в открытом виде, но может содержать
чувствительные значения (пароли БД, ключи). Поэтому он хранится в защищённом
backend и не коммитится в git.

## Local state и его проблемы

По умолчанию `terraform.tfstate` лежит рядом с кодом. Это работает одному
человеку на ноутбуке и ломается в команде:

- два инженера применяют одновременно — state перезаписывается;
- state в git — конфликты и утечки;
- потеря ноутбука — потеря управления ресурсами.

## Remote backend

```hcl
terraform {
  backend "s3" {
    bucket         = "org-tfstate"
    key            = "prod/network/terraform.tfstate"
    region         = "eu-west-1"
    dynamodb_table = "tf-locks"
    encrypt        = true
  }
}
```

| Backend | Locking | Комментарий |
| --- | --- | --- |
| S3 + DynamoDB | да | классика AWS |
| GCS | да | нативный для GCP |
| Azure Storage | да | нативный для Azure |
| Terraform Cloud | да | плюс UI и политики |
| Postgres | да | self-hosted |

Locking не даёт двум `apply` работать одновременно. Без него возможно
повреждение state и дублирование ресурсов.

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

## Проверьте себя

1. Зачем нужен remote backend и что даёт locking?
2. Что делает `terraform state rm` и чем отличается от удаления ресурса?
3. Как обнаружить drift в CI?
4. Почему state стоит разделять на стеки?

!!! tip "Практика"
    Задача «Remote state» в практикуме: перенести state в S3 с блокировкой и
    проверить параллельный apply.
