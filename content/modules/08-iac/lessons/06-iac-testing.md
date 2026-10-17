---
id: iac-testing
title: Тестирование IaC: lint, plan, policy, terratest
minutes: 28
---

# Тестирование IaC: lint, plan, policy, terratest

Инфраструктурный код ошибается дороже приложения: ошибка в Terraform может удалить
базу. Проверки делятся на четыре уровня — от дешёвых к дорогим.

## Уровень 1: форматирование и линт

```bash
terraform fmt -check -recursive
terraform validate
tflint
checkov -d .
ansible-lint
yamllint .
```

`validate` проверяет синтаксис и ссылки, но не обращается к облаку. `tflint`
ловит неверные типы инстансов и устаревшие параметры. `checkov` — политики
безопасности (публичный S3, открытый security group).

## Уровень 2: plan как тест

```bash
terraform init -backend=false
terraform plan -out=tfplan
terraform show -json tfplan > plan.json
```

Plan в CI на pull request — обязательный шаг. Он показывает, что изменится, до
применения. Для ревью — комментарий с diff.

Опасные изменения, которые должны требовать отдельного ревью:

- удаление ресурса (`destroy`);
- замена (`replace`) базы или диска;
- изменение IAM-политики;
- открытие порта в интернет.

## Уровень 3: policy as code

Open Policy Agent (OPA) или Sentinel проверяют plan на правила:

```rego
package terraform

deny contains msg if {
  resource := input.resource_changes[_]
  resource.type == "aws_security_group_rule"
  resource.change.after.cidr_blocks[_] == "0.0.0.0/0"
  resource.change.after.from_port == 22
  msg := sprintf("SSH открыт в интернет: %s", [resource.address])
}
```

```bash
conftest test plan.json --policy policy/ --namespace terraform
```

Namespace должен совпадать с `package` (либо используйте `package main` и
`--namespace main`). Синтаксис `deny contains msg if { ... }` — формат Rego v1;
старый `deny[msg] { ... }` требует режима совместимости и не работает как есть
во всех современных версиях OPA/Conftest.

В репозитории есть два проверочных примера в
`content/modules/08-iac/examples/policy/`: безопасный план и план с публичным
SSH. Запускайте команды из корня репозитория. Первая должна пройти, вторая —
завершиться ненулевым кодом:

```bash
conftest test content/modules/08-iac/examples/policy/plan-safe.json \
  --policy content/modules/08-iac/examples/policy/ --namespace terraform
if conftest test content/modules/08-iac/examples/policy/plan-public-ssh.json \
  --policy content/modules/08-iac/examples/policy/ --namespace terraform; then
  echo "ОШИБКА: политика пропустила публичный SSH" >&2
  exit 1
fi
```

Политики версионируются вместе с инфраструктурой. Это единственный способ
масштабировать безопасность: ревьюер может забыть, политика — нет.

## Уровень 4: интеграционные тесты

Terratest (Go) создаёт реальную инфраструктуру и проверяет её:

```go
func TestVpc(t *testing.T) {
    opts := &terraform.Options{
        TerraformDir: "../modules/network",
        Vars: map[string]interface{}{"name": "test"},
    }
    defer terraform.Destroy(t, opts)
    terraform.InitAndApply(t, opts)
    cidr := terraform.Output(t, opts, "cidr_block")
    assert.Equal(t, "10.20.0.0/16", cidr)
}
```

Для Ansible — Molecule: создаёт контейнер/ВМ, применяет роль, проверяет результат
и идемпотентность (второй прогон не должен менять).

```bash
molecule test
```

Интеграционные тесты дорогие, поэтому запускаются на модули, а не на каждый PR.

## Что тестировать в первую очередь

| Что | Почему |
| --- | --- |
| сеть и IAM | ошибка затрагивает всё |
| удаление/замена ресурсов | необратимые потери |
| публичный доступ | безопасность |
| идемпотентность Ansible | дрейф и ложные изменения |

## Пайплайн IaC

```yaml
- run: terraform fmt -check
- run: terraform init
- run: terraform validate
- run: tflint
- run: terraform plan -out=tfplan
- run: terraform show -json tfplan > plan.json
- run: conftest test plan.json
- run: terraform apply tfplan     # только на main, после approval
```

## Тестовая пирамида для инфраструктуры

```text
        много:  lint + fmt + validate  (секунды)
     средне:  plan / check --diff     (минуты)
   немного:  integration в песочнице (десятки минут)
        редко: end-to-end в staging  (часы)
```

Перевёрнутая пирамида — частая ошибка: дорогие e2e-тесты на каждый PR
замедляют команду и начинают отключаться.

## Проверка дрейфа

Дрейф — расхождение между кодом и реальностью. Обнаруживается регулярным
`terraform plan` в режиме только чтения:

```bash
terraform plan -detailed-exitcode
# 0 — изменений нет
# 2 — дрейф есть
# 1 — ошибка
```

В CI такой шаг запускают по расписанию, а результат отправляют владельцу
модуля. Иначе кто-то «поправил руками», и об этом узнают в момент аварии.

## Проверьте себя

1. Чем `terraform validate` отличается от `tflint`?
2. Почему plan в PR обязателен?
3. Что проверяет policy as code?
4. Зачем Molecule запускает роль дважды?

!!! tip "Практика"
    Задача «Политика для IaC» в практикуме: написать правило, запрещающее
    открытый SSH, и прогнать его на плане.
