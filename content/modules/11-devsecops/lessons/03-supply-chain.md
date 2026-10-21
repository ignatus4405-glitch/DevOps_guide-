---
id: supply-chain
title: Supply chain: SBOM, подписи, SLSA
minutes: 28
---

# Supply chain: SBOM, подписи, SLSA

Современное приложение на 90 % состоит из чужих зависимостей. Атака на цепочку
поставки — это не взлом вашего кода, а подмена библиотеки, образа или пайплайна.
Защита строится на трёх вещах: знать состав, проверять целостность, ограничить
доверие.

## SBOM: состав продукта

Software Bill of Materials — список компонентов и версий.

```bash
syft ghcr.io/org/app:1.4.2 -o spdx-json > sbom.json
grype sbom:sbom.json
```

Форматы: SPDX и CycloneDX. SBOM нужен, чтобы за минуты ответить: «подвержены ли
мы CVE-2026-1234?» — без него это дни ручной работы.

Где хранить: как артефакт релиза и/или в registry рядом с образом.

## Подписи и attestations

```bash
cosign generate-key-pair
cosign sign --key cosign.key ghcr.io/org/app@sha256:...
cosign attest --predicate sbom.json --type spdxjson ghcr.io/org/app@sha256:...
cosign verify ghcr.io/org/app@sha256:... --key cosign.pub
```

Keyless-подпись через OIDC GitHub Actions привязывает образ к конкретному
workflow и коммиту:

```bash
cosign verify ghcr.io/org/app@sha256:... \
  --certificate-identity-regexp 'https://github.com/org/repo/.github/workflows/build.yml@.*' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

Подпись без проверки бесполезна. В кластере проверку делает admission controller
(Kyverno, Sigstore policy-controller, Connaisseur).

## Происхождение сборки: SLSA

SLSA (Supply chain Levels for Software Artifacts) описывает уровни гарантий:

| Уровень | Что требует |
| --- | --- |
| 1 | документированный процесс сборки |
| 2 | хостингуемый CI, подписанные provenance |
| 3 | изолированная сборка, невозможность подмены |
| 4 | воспроизводимость, hermetic build |

Для большинства команд практичная цель — уровень 3: сборка в CI, provenance
attestation, запрет локальных сборок в прод.

## Зависимости

- lock-файлы обязательны;
- Dependabot/Renovate обновляют по расписанию;
- `npm audit`/`pip-audit`/`govulncheck` в CI;
- приватный registry с прокси и проверкой;
- запрет `latest` и непиненных версий;
- review для новых зависимостей (typosquatting, заброшенные пакеты).

Атаки на пакеты часто выглядят как «похожее имя» (`reqeusts`) или захват
заброшенного пакета. Автоматическая проверка имён и популярности помогает.

## Пайплайн

```yaml
- run: syft dir:. -o spdx-json > sbom.json
- run: grype sbom:sbom.json --fail-on critical
- run: cosign sign --key env://COSIGN_KEY ghcr.io/org/app@${{ steps.build.outputs.digest }}
- uses: actions/upload-artifact@v4
  with: { name: sbom, path: sbom.json }
```

## Подробный разбор темы

SBOM — список компонентов конкретного артефакта, а не доказательство его безопасности. Связывайте SBOM с image digest и build metadata, иначе нельзя понять, к какому именно бинарнику относится документ. После публикации CVE ищите уязвимую версию в SBOM, проверяйте достижимость и выпускайте новый артефакт, а не переписывайте старый тег.

Подпись подтверждает, что артефакт подписан ключом, которому доверяет политика; она не подтверждает корректность исходного кода. Включайте provenance, фиксируйте builder и зависимости, проверяйте подпись на deployment boundary. Для зависимости оценивайте источник, частоту обновлений, license и риск typosquatting; pinning должен сопровождаться планом регулярного обновления.

## Пошаговый сценарий

![Порядок действий: Supply chain: SBOM, подписи, SLSA](assets/img/howto/11-devsecops--03-supply-chain.svg)

1. Зафиксируйте источники зависимостей, сборки и публикации артефактов.
2. Соберите SBOM, digest и provenance для релизного образа.
3. Проверьте подпись и policy до продвижения по средам.
4. Отрепетируйте отзыв уязвимой зависимости и блокировку артефакта.

## Проверьте себя

1. Зачем нужен SBOM и что он позволяет сделать за минуты?
2. Почему подпись без проверки не даёт защиты?
3. Что означает уровень SLSA 3?
4. Какие атаки на зависимости типичны?

!!! tip "Практика"
    Задача «SBOM и подпись» в практикуме: сгенерировать SBOM, подписать образ и
    проверить подпись.
