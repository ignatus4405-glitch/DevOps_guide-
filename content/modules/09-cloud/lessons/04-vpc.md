---
id: vpc
title: VPC: подсети, маршруты, NAT, security groups
minutes: 32
---

# VPC: подсети, маршруты, NAT, security groups

Сеть в облаке — фундамент: ошибка здесь ломает всё остальное и стоит дорого.
Разберём минимальную рабочую схему и типичные ловушки.

## Базовая схема

```
VPC 10.0.0.0/16
├── public-a  10.0.1.0/24   (ALB, NAT)
├── public-b  10.0.2.0/24
├── private-a 10.0.11.0/24  (app, db)
└── private-b 10.0.12.0/24
```

- **public** — есть маршрут в Internet Gateway;
- **private** — выхода нет, только через NAT;
- минимум две зоны доступности для отказоустойчивости.

## Компоненты

| Компонент | Назначение |
| --- | --- |
| Internet Gateway | вход/выход в интернет для public-подсетей |
| NAT Gateway | исходящий трафик из private (платный!) |
| Route Table | куда отправлять пакеты |
| Security Group | stateful-фаервол на уровне ресурса |
| Network ACL | stateless-фаервол на уровне подсети |

Security Group помнит соединения: разрешили входящий 443 — ответный уйдёт сам.
NACL не помнит, поэтому нужны правила в обе стороны.

## Маршруты

```
Destination      Target
10.0.0.0/16      local
0.0.0.0/0        igw-xxx        # public
0.0.0.0/0        nat-xxx        # private
```

Если private-подсеть не имеет маршрута в NAT, у неё не будет доступа к интернету
для обновлений — типичная причина «пакеты не ставятся».

## Security Group: минимально

```hcl
resource "aws_security_group" "alb" {
  name   = "alb"
  vpc_id = aws_vpc.main.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "app" {
  ingress {
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
}
```

`security_groups` вместо CIDR — правильный способ: доступ только от
балансировщика, а не от всей подсети. SSH в интернет (`22` на `0.0.0.0/0`) —
находка любого аудита.

## Подсети и адреса

AWS резервирует 5 адресов в каждой подсети: network, router, DNS×2, broadcast.
`/24` = 256 адресов, доступно 251.

Планируйте с запасом:

- не пересекайтесь с on-premise (иначе VPN не поднимется);
- оставляйте место для роста и новых зон;
- используйте `/20`–`/24` для подсетей, `/16` для VPC.

## Диагностика

```bash
aws ec2 describe-route-tables --filters Name=vpc-id,Values=vpc-123
aws ec2 describe-security-groups --group-ids sg-123
```

Внутри инстанса:

```bash
ip route
curl -v https://example.com      # проверка NAT
ss -lntp
```

Порядок: SG → NACL → route table → NAT/IGW → DNS. Чаще всего проблема в SG,
который не разрешает трафик от нужного источника.

## Стоимость

- NAT Gateway — почасово + за трафик; в dev можно обойтись NAT instance;
- публичные IP — платные;
- межзональный трафик — платный;
- VPC peering/transit gateway — платные.

Сеть — одна из главных статей счёта, и её проектирование влияет на бюджет.

## Подробный разбор темы

Subnet получает маршрут из route table; «public» subnet обычно имеет маршрут к internet gateway, а не волшебный флаг открытости. Частная подсеть может выходить наружу через NAT, но входящее соединение по умолчанию не становится доступным. Security group обычно stateful и привязана к интерфейсу; network ACL часто stateless и действует на subnet, поэтому обратный ephemeral port тоже нужно разрешить.

Проверьте полный путь: DNS, route table, security group, NACL, NAT/IGW и локальный firewall. Убедитесь, что база не имеет публичного адреса, а административный доступ идёт через контролируемый bastion/VPN/SSM-путь. Сегментируйте сервисы по необходимым связям, а не по привычным CIDR-копиям.

## Пошаговый сценарий

![Порядок действий: VPC: подсети, маршруты, NAT, security groups](assets/img/howto/09-cloud--04-vpc.svg)

1. Нарисуйте CIDR, subnet, route table и границы доступности.
2. Проверьте путь пакета через security groups, ACL, NAT и gateway.
3. Включите DNS, flow logs и контролируемый egress.
4. Проверьте частное и публичное соединение с обеих сторон.

## Проверьте себя

1. Чем public-подсеть отличается от private?
2. Почему Security Group называют stateful?
3. Зачем private-подсети NAT?
4. Почему нельзя брать 10.0.0.0/16, не проверив on-premise?

!!! tip "Практика"
    Задача «VPC с двумя зонами» в практикуме: описать сеть в Terraform и
    проверить маршруты.
