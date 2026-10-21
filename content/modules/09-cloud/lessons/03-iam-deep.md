---
id: iam-deep
title: IAM: роли, политики, least privilege
minutes: 30
---

# IAM: роли, политики, least privilege

Большинство облачных инцидентов — не утечка данных через приложение, а
скомпрометированные ключи с широкими правами. IAM — первый рубеж, и его нужно
проектировать, а не «выдавать AdministratorAccess, чтобы заработало».

## Кто, что, где

| Понятие | AWS | GCP | Azure |
| --- | --- | --- | --- |
| Идентичность | IAM user/role | service account | managed identity |
| Политика | policy JSON | role binding | role assignment |
| Границы | account | project | subscription |
| Временные креды | STS | Workload Identity | federated credentials |

Общая идея: субъект получает роль, роль содержит разрешения, разрешения
ограничены ресурсом и условиями.

## Политика: из чего состоит

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::app-uploads/*",
      "Condition": {
        "StringEquals": {"aws:PrincipalTag/team": "backend"}
      }
    }
  ]
}
```

- `Action` — конкретные операции, не `*`;
- `Resource` — конкретный ARN, не `*`;
- `Condition` — ограничение по тегам, IP, времени, MFA.

`"Action": "*", "Resource": "*"` — это admin. Такая политика почти всегда
появляется из-за того, что «не хватало прав и мы добавили всё».

## Роли вместо ключей

```bash
# плохо: статический ключ
aws configure   # access key + secret

# хорошо: роль и временные креды
aws sts assume-role --role-arn arn:aws:iam::123:role/app --role-session-name ci
```

В Kubernetes — IRSA (EKS) или Workload Identity (GKE): под получает токен
ServiceAccount, облако обменивает его на временные креды. Ключи не хранятся
вообще.

## Least privilege на практике

1. Начните с `ReadOnlyAccess` и добавляйте по одной операции.
2. Используйте `Access Analyzer` / `Policy Simulator`, чтобы проверить, что
   реально нужно.
3. Ограничивайте по ресурсу и тегам, а не только по действию.
4. Разделяйте роли: сборка, деплой, чтение логов — разные.
5. Ревью политик при каждом изменении.

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123:role/app \
  --action-names s3:PutObject
```

## Опасные разрешения

| Разрешение | Почему опасно |
| --- | --- |
| `iam:PassRole` + `ec2:RunInstances` | запуск инстанса с чужой ролью |
| `s3:*` | чтение и удаление всех данных |
| `kms:Decrypt` на все ключи | расшифровка всех секретов |
| `sts:AssumeRole` на `*` | эскалация прав |
| `organizations:*` | управление всеми аккаунтами |

`iam:PassRole` — классический путь эскалации: роль с правами admin передаётся
новому ресурсу, к которому есть доступ.

## Аудит

```bash
aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=DeleteBucket
aws iam get-account-authorization-details
```

CloudTrail (или аналог) должен быть включён во всех регионах и защищён от
удаления. Без логов инцидент нельзя расследовать.

## Политика: как читать и проверять

IAM-политика — JSON с `Effect`, `Action`, `Resource`, `Condition`. Читать её
нужно справа налево: что разрешено, на что, при каких условиях.

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["s3:GetObject"],
    "Resource": "arn:aws:s3:::reports/*",
    "Condition": {"Bool": {"aws:SecureTransport": "true"}}
  }]
}
```

Здесь доступ ограничен бакетом, префиксом и только HTTPS.

Проверка перед выкаткой:

```bash
aws iam simulate-principal-policy   --policy-source-arn arn:aws:iam::123:role/app   --action-names s3:GetObject   --resource-arns arn:aws:s3:::reports/a.csv
```

`simulate-principal-policy` отвечает «allowed/denied» до продакшена — дешевле,
чем выяснять это инцидентом.

## Признаки плохой политики

- `Action: "*"` вместе с `Resource: "*"`;
- условия на `aws:SourceIp`, которые ломаются за NAT;
- политика на пользователя вместо роли;
- отсутствие границ (`Permissions boundary`) для делегирования.

## Подробный разбор темы

IAM policy обычно состоит из principal, action, resource и conditions. Эффективное разрешение зависит от нескольких слоёв: identity policy, resource policy, organization guardrail и explicit deny. Поэтому отсутствие allow не всегда единственная причина отказа; диагностика должна показывать, какой policy evaluation остановил запрос.

Используйте роли и STS вместо долгоживущих ключей, разделяйте read и write задачи и сужайте resource ARN и condition по account, region или tag, если это безопасно. Проверьте права через policy simulator или тестовую identity, затем изучите audit log. Периодически удаляйте неиспользуемые permissions, но начинайте с наблюдения и постепенного rollout, чтобы не сломать скрытую автоматизацию.

## Проверьте себя

1. Почему `Action: "*"` почти всегда ошибка?
2. Чем роль лучше статического ключа?
3. Что делает `iam:PassRole` и почему это риск?
4. Как проверить, какие права реально нужны сервису?

!!! tip "Практика"
    Задача «Минимальные права» в практикуме: сузить политику до конкретного
    bucket и action.
