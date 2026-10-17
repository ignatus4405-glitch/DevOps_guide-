---
id: terraform
title: Terraform: описание инфраструктуры кодом
minutes: 50
---

# Terraform: описание инфраструктуры кодом

**Terraform описывает желаемое состояние инфраструктуры в файлах и приводит к нему
реальность.** Ключевое отличие от скриптов: вы описываете «что должно быть», а не
«какие команды выполнить».

![Поток IaC](assets/img/iac-flow.svg)

## Минимальный проект

```hcl
# versions.tf
terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.60" }
  }
  backend "s3" {                       # состояние в общем хранилище, а не локально
    bucket         = "org-tfstate"
    key            = "prod/network/terraform.tfstate"
    region         = "eu-central-1"
    dynamodb_table = "tf-locks"        # блокировка: двое не применят одновременно
    encrypt        = true
  }
}

# variables.tf
variable "project" { type = string }
variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

# main.tf
provider "aws" { region = "eu-central-1" }

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  tags = { Name = "${var.project}-vpc", Project = var.project, ManagedBy = "terraform" }
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id          # ссылка вместо «магического» id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true
  tags = { Name = "${var.project}-public-${count.index}" }
}

data "aws_availability_zones" "available" { state = "available" }

# outputs.tf
output "vpc_id" { value = aws_vpc.main.id }
output "subnet_ids" { value = aws_subnet.public[*].id }
```

```bash
terraform init          # скачать провайдеры, настроить backend
terraform fmt -recursive
terraform validate
terraform plan -out=tfplan     # показать, что изменится; сохранить план
terraform apply tfplan         # применить ровно то, что в плане
terraform output -json
terraform destroy              # удалить всё (осторожно!)
```

## State: почему это главное, что нужно понять

State — файл, где Terraform хранит соответствие «ресурс в коде ↔ реальный объект в облаке».

| Проблема | Последствие | Решение |
| --- | --- | --- |
| State только локально | коллеги «создают дубли» ресурсов | remote backend (S3+GCS+TF Cloud) |
| Нет блокировки | два apply одновременно → битое состояние | DynamoDB/блокировка в backend |
| State в открытом репозитории | утечка паролей и идентификаторов | S3 с шифрованием + запрет публичного доступа |
| State удалён вручную | Terraform «забыл» ресурсы | бэкапы state, `terraform import` |

```bash
terraform state list                          # какие ресурсы в state
terraform state show aws_vpc.main
terraform import aws_s3_bucket.logs org-logs-bucket   # принять существующий ресурс под управление
terraform state mv aws_instance.web aws_instance.api  # переименование без пересоздания
```

!!! danger "Осторожно"
    `terraform destroy` и удаление state необратимы. Перед разрушительными операциями:
    `terraform plan -destroy`, бэкап state, проверка, что нет `prevent_destroy`-защит
    на критичных ресурсах (базы, диски с данными).

## Модули и повторное использование

```hcl
module "web_asg" {
  source = "./modules/asg-web"

  project       = var.project
  instance_type = "t3.small"
  min_size      = 2
  max_size      = 6
  subnet_ids    = aws_subnet.public[*].id
  ami_id        = data.aws_ami.ubuntu.id

  tags = { Env = "prod" }
}
```

Правила хорошего модуля: понятный интерфейс (`variables` с типами и описаниями),
минимум обязательных входов, предсказуемые `outputs`, версионирование
(`source = "git::https://...//modules/vpc?ref=v1.3.0"`), пример использования в README.

## Воркспейсы и окружения

```bash
terraform workspace list
terraform workspace new staging
terraform workspace select prod
```

Воркспейсы подходят для небольших различий между средами. Для прод/стейдж с разными
правилами чаще используют **отдельные каталоги и отдельные state** (`envs/prod`,
`envs/staging`) — так меньше риска случайно применить прод-план к стейджу.

## Проверки в пайплайне

```yaml
# .github/workflows/terraform.yml (фрагмент)
      - run: terraform fmt -check -recursive
      - run: terraform init -backend-config=backend.hcl
      - run: terraform validate
      - run: tflint --recursive
      - run: terraform plan -out=tfplan -lock-timeout=5m
      - run: terraform apply -auto-approve tfplan      # только для ветки main / тега
        if: github.ref == 'refs/heads/main'
```

Для ревью публикуйте план как комментарий к PR: ревьюер видит «+3, −1, изменить 2»
до применения. Инструмент для этого — `terraform plan` + `github-script` или специализированные
сервисы (Atlantis, Spacelift).

## Частые ошибки

| Ошибка | Что происходит | Как избежать |
| --- | --- | --- |
| Правки в консоли облака | дрейф: next plan «вернёт как было» | всё через код, ручное — только в аварию с последующей фиксацией |
| Секреты в `.tf` | утечка в Git и state | переменные окружения, `TF_VAR_`, vault |
| Один state на всё | долгий plan, высокий риск | разделение по слоям (сеть, данные, приложения) |
| `-auto-approve` в CI без ревью | случайное удаление прода | план → approve → apply |
| Игнорирование дрейфа | «почему-то всё пересоздаётся» | регулярный `plan` по расписанию и алерт на изменения |

## HCL: основы, которых достаточно

```hcl
# переменные
variable "instance_type" {
  type    = string
  default = "t3.micro"
}

# локальные значения
locals {
  name = "${var.project}-${var.environment}"
  tags = { Project = var.project, Environment = var.environment }
}

# ресурс
resource "aws_instance" "web" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = var.instance_type
  tags          = local.tags
}

# output
output "ip" { value = aws_instance.web.public_ip }
```

`data` — чтение существующего, `resource` — управление созданием. Разница важна:
`data` не создаёт и не удаляет.

## План и применение

```bash
terraform init          # скачать провайдеры, настроить backend
terraform fmt -recursive
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
terraform destroy
```

`plan` показывает `+` создать, `~` изменить, `-` удалить, `-/+` заменить.
Замена ресурса — часто неожиданная потеря данных: читайте план, а не только
«apply прошёл».

## Зависимости

Terraform строит граф по ссылкам. Явная зависимость:

```hcl
resource "aws_iam_role_policy" "app" {
  depends_on = [aws_iam_role.app]
}
```

`depends_on` нужен редко — обычно ссылки достаточно. Он замедляет plan и скрывает
реальную связь.

## Почему Terraform, а не ручная консоль

- воспроизводимость: одинаковое окружение из кода;
- ревью: изменения видны в PR;
- откат: revert коммита + apply;
- документация: код — источник правды;
- аудит: кто и когда менял.

Консоль остаётся для экспериментов и аварийного доступа, но изменения нужно
возвращать в код, иначе появится drift.

## Короткое резюме

- Terraform декларативен: `plan` показывает, `apply` приводит к желаемому состоянию.
- State — критичный артефакт: remote backend, блокировки, шифрование, бэкапы.
- Модули и отдельные state по окружениям дают повторное использование и снижают риск.
- Всё проходит через ревью и пайплайн: fmt, validate, tflint, plan, apply.

## Проверьте себя

1. Почему state нельзя хранить локально в командной работе?
2. Что случится, если изменить ресурс в консоли облака, не меняя код?
3. Как организовать отдельные окружения prod и staging в Terraform?
