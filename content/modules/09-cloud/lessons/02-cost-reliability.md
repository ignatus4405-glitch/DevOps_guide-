---
id: cloud-cost-reliability
title: Надёжность и стоимость облака (FinOps)
minutes: 40
---

# Надёжность и стоимость облака (FinOps)

Облако удобно тем, что ресурсы создаются мгновенно. Именно поэтому счёт может вырасти
в разы за месяц, а инфраструктура — остаться непроверенной на отказ. DevOps-инженер
отвечает и за надёжность, и за бюджет.

## Надёжность: как проектируют отказоустойчивость

| Понятие | Смысл | Как реализуется |
| --- | --- | --- |
| AZ (зона доступности) | независимый ЦОД в регионе | реплики в ≥2 AZ |
| Region | географический регион | DR-регион для критичных систем |
| RTO | целевое время восстановления | автоскейл, тёплый резерв, playbook |
| RPO | допустимая потеря данных | частота бэкапов, репликация |
| SPOF | единая точка отказа | убирается балансировкой и репликами |

```bash
# Проверка: распределены ли инстансы по зонам?
aws ec2 describe-instances --filters Name=instance-state-name,Values=running \
  --query 'Reservations[].Instances[].{id:InstanceId,az:Placement.AvailabilityZone}' --output table

# Мульти-AZ у БД
aws rds describe-db-instances --query 'DBInstances[].{id:DBInstanceIdentifier,multiAZ:MultiAZ,class:DBInstanceClass}'
```

Типовые проверки надёжности, которые стоит провести на своём проекте:

1. **Убей один инстанс** — сервис должен продолжать работать.
2. **Зайди в приватную подсеть без NAT** — пойми, что именно сломается (обновления, внешние API).
3. **Восстанови бэкап БД** на отдельный инстанс и проверь данные (это и есть проверка бэкапа).
4. **Проверь алерты**: отключи один узел — придёт ли уведомление в течение 5 минут?
5. **Игра «погаси AZ»**: что произойдёт, если целая зона недоступна?

!!! note "Про бэкапы"
    Наличие снапшотов ≠ восстановление. Регулярно (раз в квартал) восстанавливайте
    бэкап и фиксируйте время: это и есть ваш реальный RTO. Незапланированный «тест
    восстановления во время аварии» — это уже катастрофа.

## FinOps: где обычно теряются деньги

| Потеря | Как выглядит | Что делать |
| --- | --- | --- |
| Переразмеренные инстансы | CPU 3 % месяца | rightsizing по метрикам CloudWatch |
| Простаивающие ресурсы | выключенные, но живые ВМ и диски | автостоп dev-среды по расписанию, удаление «сирот» |
| Неиспользуемые EBS-снапшоты | гигабайты за годы | политики retention, lifecycle |
| Один NAT Gateway на все AZ | простои и лишний кросс-AZ трафик | NAT в каждой AZ, либо VPC endpoints |
| Публичный трафик S3/CloudFront | дорогой egress | CDN, кэш, VPC endpoint |
| Отсутствие тегов | «непонятно, чей ресурс» | обязательные теги: Owner, Project, Env |
| On-demand для стабильной нагрузки | переплата 30–60 % | savings plans / reserved (только для стабильной части) |
| Spot не используется | переплата за пакетные задачи | spot для batch, CI-раннеров |

```bash
# Топ-5 самых дорогих сервисов в аккаунте за месяц (через Cost Explorer CLI)
aws ce get-cost-and-usage --time-period Start=$(date -d '30 days ago' +%F),End=$(date +%F) \
  --granularity MONTHLY --metrics UnblendedCost \
  --group-by Type=DIMENSION,Key=SERVICE \
  --query 'ResultsByTime[].Groups[].{service:Keys[0],cost:Total.UnblendedCost.Amount}' --output table

# Поиск «сирот»: незакреплённые тома
aws ec2 describe-volumes --filters Name=status,Values=available \
  --query 'Volumes[].{id:VolumeId,size:Size,created:CreateTime}' --output table
```

Практические правила FinOps:

1. **Теги обязательны** и проверяются политикой (Terraform-провайдер может их добавлять автоматически).
2. **Бюджет и алерты**: budget с уведомлением на 50/80/100 % прогноза.
3. **Dev-окружения по расписанию**: старт в 9:00, стоп в 20:00 — экономия почти 50 %.
4. **Смотрите egress-трафик**: часто это неожиданно самая дорогая строка.
5. **Раз в месяц — ревизия**: все ресурсы без владельца сносятся или получают владельца.

## Infrastructure as Code как основа предсказуемости

```hcl
# Автостоп dev-инстансов по расписанию (экономия бюджета)
resource "aws_autoscaling_schedule" "stop_night" {
  scheduled_action_name  = "stop-at-night"
  autoscaling_group_name = aws_autoscaling_group.dev.name
  min_size               = 0
  max_size               = 0
  desired_capacity       = 0
  recurrence             = "0 20 * * MON-FRI"   # 20:00 по будням
  time_zone              = "Europe/Amsterdam"
}

resource "aws_budgets_budget" "monthly" {
  name              = "monthly-budget"
  budget_type       = "COST"
  limit_amount      = "1500"
  limit_unit        = "USD"
  time_period_end   = "2100-01-01_00:00"
  time_period_start = "2024-01-01_00:00"
  time_unit         = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = ["finops@example.com"]
  }
}
```

## Мультиоблако и когда оно нужно

Мультиоблако реально требуется в трёх случаях: регуляторные требования, поглощение
компаний, специализированные сервисы (например, ML или CDN у конкретного вендора).
Во всех остальных случаях второе облако удваивает сложность, стоимость и количество
экспертизы. Начинать нужно с одного облака, IaC и переносимых практик (Kubernetes,
Terraform, OpenTelemetry) — это даёт вариантность без преждевременной сложности.

## Короткое резюме

- Надёжность строится на мульти-AZ, отсутствии SPOF, проверенных бэкапах и алертах.
- RTO/RPO нужно измерять фактами (тест восстановления), а не предполагать.
- Стоимость зависит от прав: rightsizing, автостоп, spot, savings plans, теги и бюджет-алерты.
- Мультиоблако — под требования, а не «на всякий случай».

## Проверьте себя

1. Как проверить реальный RTO базы данных?
2. Какие три шага дают самый быстрый эффект на счёт облака?
3. Почему egress-трафик часто становится неожиданной статьёй расходов?
