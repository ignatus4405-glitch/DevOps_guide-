---
id: cloud-architecture
title: Архитектура облачного контура и IAM
minutes: 45
---

# Архитектура облачного контура и IAM

Облако — это API для инфраструктуры. Всё, что вы делаете в консоли, должно быть
воспроизводимо кодом (Terraform), иначе окружение станет неповторяемым.

![Архитектура в AWS](assets/img/aws-architecture.svg)

## Базовая сеть: VPC, подсети, шлюзы

```
VPC 10.0.0.0/16
├── public subnet  10.0.1.0/24 (AZ-a) ── Internet Gateway ── Интернет
├── public subnet  10.0.2.0/24 (AZ-b) ── NAT Gateway ── исходящий трафик приватных подсетей
├── private subnet 10.0.11.0/24 (AZ-a) — приложения, БД
└── private subnet 10.0.12.0/24 (AZ-b)
```

| Элемент | Роль | Типичная ошибка |
| --- | --- | --- |
| VPC | изолированная сеть | слишком маленький CIDR, «нет адресов» |
| Публичная подсеть | доступ к интернету через IGW | приложения прямо в публичной подсети |
| Приватная подсеть | безопасное размещение приложений и БД | нет NAT → нет установки пакетов |
| NAT Gateway | исходящий трафик из приватных подсетей | один NAT в одной AZ — дорого и не отказоустойчиво |
| Security Group | stateful-фильтр трафика | `0.0.0.0/0` на порт БД |
| Route Table | маршрутизация | путают локальные и внешние маршруты |

**Правило:** приложения и данные живут в приватных подсетях, публичными остаются
только балансировщик и bastion (или вообще только SSM Session Manager).

```bash
aws ec2 describe-subnets --filters Name=vpc-id,Values=vpc-123 \
  --query 'Subnets[].{id:SubnetId,cidr:CidrBlock,az:AvailabilityZone,public:MapPublicIpOnLaunch}' --output table
aws ec2 describe-security-groups --group-ids sg-123 --query 'SecurityGroups[].IpPermissions'
```

## Вычисления: что выбрать

| Сервис | Когда выбирать | Особенности |
| --- | --- | --- |
| EC2 (ВМ) | полный контроль, специфичные требования | вы отвечаете за ОС и патчи |
| ASG (группа ВМ) | горизонтальное масштабирование | нужно сделать серверы «одноразовыми» |
| ECS/EKS | контейнерные приложения | баланс контроля и удобства |
| Lambda/Functions | событийные короткие задачи | ограничения по времени и памяти |
| Spot / прерываемые | некритичные пакетные задачи | экономия до 70–90 %, могут пропасть |

Принцип «одноразовых серверов» (cattle, not pets): сервер можно удалить и создать
заново из образа и Ansible-ролей. Тогда сбой узла — не авария, а обычная замена.

## IAM: кто и что может делать

| Сущность | Что это | Где применять |
| --- | --- | --- |
| Root | владелец аккаунта | не использовать, включить MFA, ключи удалить |
| User | человек (или legacy-скрипт) | только там, где нет роли |
| Group | набор пользователей с политиками | права команды |
| Role | права для сервиса/федерации | EC2, Lambda, CI (веб-федерация) |
| Policy | документ разрешений | разрешения и условия |
| STS-токены | временные креды | CI/CD, cross-account доступ |

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadObjectsOnly",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": ["arn:aws:s3:::org-artifacts", "arn:aws:s3:::org-artifacts/*"],
      "Condition": { "StringEquals": { "aws:PrincipalTag/team": "backend" } }
    }
  ]
}
```

Принципы:

1. **Наименьшие привилегии**: начинайте с минимума и добавляйте по факту необходимости.
2. **Роли вместо ключей**: долгоживущие ключи в коде — источник утечек. В CI используйте
   OIDC/веб-федерацию, на ВМ — instance profile.
3. **Условия**: ограничивайте по сети, тегам, времени, MFA.
4. **Аудит**: CloudTrail включён в каждом аккаунте, алерты на чувствительные действия.
5. **Разделение аккаунтов** по средам (prod/staging/dev) — лучшая изоляция.

```bash
aws sts get-caller-identity            # кто я сейчас
aws iam get-account-summary | head -30
aws iam simulate-principal-policy --policy-source-arn arn:aws:iam::123:role/app \
  --action-names s3:PutObject --resource-arns arn:aws:s3:::org-artifacts/x
```

!!! danger "Осторожно"
    Никогда не коммитьте `~/.aws/credentials` и не публикуйте Access Keys. Если ключ
    всё же утёк: немедленно деактивировать в IAM (`aws iam update-access-key
    --status Inactive`), проверить CloudTrail на использование, ротировать связанные
    секреты. Сканеры GitHub Secrets Scanning находят ключи AWS в течение минут.

## Хранилища и данные

| Сервис | Тип | Применение |
| --- | --- | --- |
| S3 | объектное | артефакты, бэкапы, статика, логи |
| EBS | блочное (диск ВМ) | ФС сервера, снапшоты |
| EFS | сетевой FS | общие каталоги между ВМ |
| RDS/Managed SQL | БД | продовые данные, Multi-AZ, бэкапы |
| ElastiCache/Redis | кэш | сессии, очереди, счётчики |

```bash
# Правила для бакетов: шифрование, версии, запрет публичного доступа
aws s3api put-bucket-encryption --bucket org-artifacts \
  --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
aws s3api put-public-access-block --bucket org-artifacts \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-versioning --bucket org-artifacts --versioning-configuration Status=Enabled
aws s3 ls s3://org-artifacts --recursive --human-readable | head
```

Жизненный цикл данных снижает стоимость: перевод в холодные классы через 30 дней,
удаление через 365. Версии объектов обязательны, если данные критичны (защита от
случайного `aws s3 rm --recursive`).

## Короткое резюме

- VPC делится на публичные и приватные подсети; приложения и БД — в приватных.
- IAM строится на ролях, временных кредах и наименьших привилегиях; ключи — исключение.
- Сервисы вычислений выбирают по задаче: ВМ, ASG, контейнеры, serverless, spot.
- Для S3 обязательны шифрование, запрет публичного доступа, версии и lifecycle.

## Проверьте себя

1. Почему база данных не должна находиться в публичной подсети?
2. Чем IAM-роль лучше долгоживущего ключа доступа в CI?
3. Какие четыре вещи нужно включить у бакета S3, чтобы он «по умолчанию» был безопасным?
