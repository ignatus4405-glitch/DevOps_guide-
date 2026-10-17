---
id: policy-as-code
title: Policy as Code: guardrails вместо запретов
minutes: 30
---

# Policy as Code: guardrails вместо запретов

Правила «не создавай публичный бакет» работают, пока о них помнят. Policy as
Code превращает договорённости в проверяемые автоматически условия.

## Где применять

- **CI** — проверить Terraform plan до apply;
- **admission** — отклонить опасный манифест в кластере;
- **cloud** — SCP/organization policies;
- **registry** — политики подписи и сканирования.

Чем раньше проверка, тем дешевле исправление.

## OPA и Rego

Open Policy Agent — универсальный движок политик. Пример: запретить тег latest.

```rego
package kubernetes.admission

deny[msg] {
  input.request.kind.kind == "Pod"
  image := input.request.object.spec.containers[_].image
  endswith(image, ":latest")
  msg := sprintf("образ %s использует latest", [image])
}
```

Conftest проверяет YAML/JSON в CI тем же языком.

## Kyverno

Kyverno — политики на YAML, без отдельного языка:

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata: {name: require-labels}
spec:
  validationFailureAction: Enforce
  rules:
    - name: check-owner
      match: {resources: {kinds: [Deployment]}}
      validate:
        message: "нужен label owner"
        pattern:
          metadata:
            labels:
              owner: "?*"
```

Плюс: читается без изучения Rego. Минус: сложные условия всё равно требуют
выразительности.

## Terraform

- `tflint` — ошибки провайдера;
- `checkov`/`tfsec` — безопасность;
- `conftest` — свои правила по plan JSON;
- Sentinel (Terraform Cloud) — политики в платформе.

```bash
terraform show -json plan.out > plan.json
conftest test plan.json -p policy/
```

## Как внедрять

1. Начните с аудита (warn), не с блокировки.
2. Соберите нарушения, объясните командам.
3. Включите enforce для критичных правил.
4. Дайте исключения с владельцем и сроком.
5. Удаляйте правила, которые не работают.

Политика без объяснения воспринимается как препятствие. Сообщение об ошибке
должно говорить, что делать, а не только «denied».

## Антипаттерны

- сотни правил «на всякий случай»;
- блокировка без пути обхода (break-glass);
- политики вне Git;
- отсутствие тестов на политики.

## Как проверить себя

1. Где можно применять policy as code?
2. Чем Rego отличается от Kyverno?
3. Почему начинать с audit?
4. Что должно быть в сообщении об отказе?
5. Зачем тестировать политики?

!!! tip "Практика"
    Задача «Политика тегов» в практикуме: написать и проверить правило.
