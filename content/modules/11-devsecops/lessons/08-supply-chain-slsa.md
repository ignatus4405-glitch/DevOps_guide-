---
id: supply-chain-slsa
title: Supply chain: SLSA, provenance и подпись артефактов
minutes: 32
---

# Supply chain: SLSA, provenance и подпись артефактов

Атака на цепочку поставок компрометирует не ваш код, а сборку. Log4Shell,
подменённые npm-пакеты и взломанные CI-токены показали, что доверять артефакту
без доказательств нельзя.

## Что такое SLSA

SLSA (Supply-chain Levels for Software Artifacts) — уровни гарантий:

| Уровень | Что требует |
| --- | --- |
| 1 | документированная сборка, provenance |
| 2 | сборка на хостинге, подписанный provenance |
| 3 | изолированная сборка, защита от подмены |
| 4 | воспроизводимость и строгая изоляция |

Provenance — машиночитаемое описание: кто, из какого коммита, каким builder'ом
и с какими зависимостями собрал артефакт.

## Подпись

Cosign (Sigstore) подписывает образ ключом или keyless через OIDC:

```bash
cosign sign --yes ghcr.io/org/app@sha256:...
cosign verify ghcr.io/org/app@sha256:... \
  --certificate-identity-regexp '.*github.*' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

Keyless удобен: приватный ключ не хранится, доверие строится на identity
CI-системы. Но нужно проверять issuer и identity, иначе подпись бесполезна.

## Admission-контроль

Подпись важна только если кластер её проверяет. Пример с Kyverno:

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata: {name: verify-images}
spec:
  rules:
    - name: check-signature
      match: {resources: {kinds: [Pod]}}
      verifyImages:
        - imageReferences: ["ghcr.io/org/*"]
          attestors:
            - entries: [{keyless: {issuer: "https://token.actions.githubusercontent.com"}}]
```

Без проверки в admission подпись — украшение.

## SBOM

SBOM перечисляет компоненты и версии. Форматы: SPDX, CycloneDX.

```bash
syft ghcr.io/org/app:1.0 -o spdx-json > sbom.json
grype sbom:sbom.json
```

SBOM позволяет за минуты найти, кто затронут новой CVE, вместо опроса команд.

## Зависимости

- lock-файлы обязательны;
- приватный registry с прокси и сканированием;
- запрет `latest` в проде;
- dependency confusion: scope для внутренних пакетов;
- review обновлений, а не автомерж всего.

## CI как цель

CI видит секреты и может подписывать артефакты. Защита:

- OIDC вместо статических ключей;
- минимальные permissions;
- защита веток и окружений;
- pinning действий по SHA;
- отдельные runner'ы для релиза.

## Как проверить себя

1. Что описывает provenance?
2. Чем keyless-подпись отличается от ключевой?
3. Зачем проверять подпись в admission?
4. Что даёт SBOM при новой CVE?
5. Почему CI — привлекательная цель?

!!! tip "Практика"
    Задача «Подпись и проверка» в практикуме: подписать образ и проверить.

## Подробный разбор темы

SLSA описывает уровни гарантий вокруг build process, source и provenance. Provenance должна связывать артефакт с commit, builder, параметрами и зависимостями; подпись позволяет проверить, что запись не подменена. Для потребителя важно валидировать claims и доверенный builder, а не просто наличие JSON-файла рядом с образом.

Изолируйте build от недоверенных pull request, ограничивайте доступ к signing key и исключайте возможность подмены артефакта между сборкой и публикацией. Reproducible build помогает сравнить результат независимых сборщиков, но требует зафиксированных входов и инструментов. Планируйте ротацию ключей, аудит подписей и политику отказа от артефактов без подтверждённого происхождения.

## Пошаговый сценарий

![Порядок действий: Supply chain: SLSA, provenance и подпись артефактов](assets/img/howto/11-devsecops--08-supply-chain-slsa.svg)

1. Определите source, builder, изолированность и доверенные identities.
2. Сгенерируйте provenance для сборки с закреплёнными входами.
3. Проверьте подпись и соответствие policy при продвижении артефакта.
4. Проверьте, что потребитель может независимо сверить digest и происхождение.
