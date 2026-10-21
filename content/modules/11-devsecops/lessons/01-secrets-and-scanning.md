---
id: secrets-and-scanning
title: Секреты и сканирование в пайплайне
minutes: 45
---

# Секреты и сканирование в пайплайне

**DevSecOps означает, что безопасность встроена в конвейер как проверки, а не
приходит «аудитом в конце квартала».** Принцип: сделать безопасный путь самым
простым, а неудобные обходы — заметными.

![DevSecOps в конвейере](assets/img/devsecops.svg)

## Секреты: где они живут и что делать при утечке

| Плохо | Хорошо |
| --- | --- |
| `.env` в Git | `.env.example` в Git, значения — в менеджере секретов |
| Токен в логах CI | маскирование + запрет печати |
| Долгоживущие ключи у сервиса | короткоживущие токены (STS, OIDC) |
| Один общий секрет на все среды | отдельные секреты для dev/staging/prod |
| Ручная ротация «когда вспомним» | автоматическая ротация по расписанию |

```yaml
# Защита от коммита секретов: pre-commit + gitleaks
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.4
    hooks: [{ id: gitleaks }]
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - { id: detect-private-key }
      - { id: check-added-large-files }
```

```bash
gitleaks detect --source . --redact --report-format sarif --report-path gitleaks.sarif
trufflehog git file://. --only-verified
docker run --rm -v "$PWD:/repo" zricethezav/gitleaks:latest detect -s /repo -v
```

!!! danger "Осторожно"
    Порядок действий при утечке секрета: **1) отозвать/перевыпустить**,
    **2) проверить, что им не воспользовались** (аудит-логи), **3) убрать из истории**
    (`git filter-repo`), **4) уведомить**, **5) добавить проверку**, чтобы не повторилось.
    Перестановка шагов «сначала почистить историю» — самая частая ошибка: ключ уже
    мог быть скопирован за минуты.

Менеджеры секретов: HashiCorp Vault, AWS Secrets Manager, Yandex Lockbox, Doppler,
SOPS + age (для шифрования прямо в Git), External Secrets Operator (Kubernetes).

## Сканирование: четыре уровня проверок

| Уровень | Что ищет | Инструменты | Когда запускать |
| --- | --- | --- | --- |
| Секреты | ключи, токены, пароли | gitleaks, trufflehog | pre-commit, каждый push |
| Зависимости | CVE в библиотеках | dependabot, snyk, osv-scanner | PR + расписание |
| Код (SAST) | уязвимые паттерны | semgrep, bandit, codeql | каждый PR |
| Образы и IaC | CVE в слоях, небезопасные конфиги | trivy, checkov, kics | сборка образа, IaC-PR |

```yaml
# GitHub Actions: минимальный security-пайплайн
name: Security
on: [pull_request]
permissions: { contents: read, security-events: write }
jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }          # нужно для сканирования истории секретов
      - name: Секреты
        uses: gitleaks/gitleaks-action@v2
      - name: Зависимости (OSV)
        uses: google/osv-scanner-action/osv-scanner-action@v1
        with: { scan-args: "-r --skip-git ./" }
      - name: SAST (semgrep)
        run: |
          pip install semgrep
          semgrep --config=p/ci --sarif --output=semgrep.sarif . || true
      - name: IaC (checkov)
        run: pip install checkov && checkov -d infra/ --output sarif --output-file checkov.sarif || true
      - name: Загрузить отчёты в Security tab
        if: always()
        uses: github/codeql-action/upload-sarif@v3
        with: { sarif_file: . }
```

!!! tip "Совет"
    Первое включение сканеров всегда даёт сотни замечаний. Не отключайте их —
    зафиксируйте baseline: исправляйте критичное, остальное добавьте в план и
    постепенно закрывайте. Пайплайн должен падать на **новых** критичных находках.

## Цепочка поставки: SBOM и подписи

```bash
# SBOM: перечень всего, что внутри образа (форматы SPDX или CycloneDX)
syft ghcr.io/org/api:1.4.0 -o spdx-json > sbom.spdx.json

# Сканирование SBOM без запуска контейнера
grype sbom:sbom.spdx.json --fail-on high

# Подпись образа (sigstore cosign) — подтверждение, кто и как собрал
cosign sign --yes ghcr.io/org/api@sha256:9f0c...
cosign verify --certificate-identity-regexp 'github.com/org/repo' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/org/api@sha256:9f0c...
```

Зачем это нужно: если реестр или сборочная система скомпрометированы, подпись и SBOM
позволяют понять, что именно попало в прод и подтвердить происхождение артефакта.
Для критичных систем применяют политики admission control (Kyverno/Gatekeeper):
«запускать только подписанные образы».

## Контейнерная безопасность на практике

```bash
trivy image --scanners vuln,secret,config --severity HIGH,CRITICAL api:local
trivy config ./infra            # проверка IaC на небезопасные настройки
hadolint Dockerfile             # частые ошибки Dockerfile
kubesec scan pod.yaml           # оценка безопасности pod-спеки
```

Типовые находки и лечение: запуск от root (`USER`), отсутствие read-only ФС
(`readOnlyRootFilesystem`), избыточные capabilities (`drop: [ALL]`), отсутствие
лимитов, секреты в слоях образа, устаревшая база (`IMAGE_VERSION`), небезопасный
`docker run --privileged` (никогда в проде).

## Shift left: что это значит на практике

«Сдвинуть безопасность влево» — значит проверять раньше и дешевле:

| Этап | Проверка | Стоимость фикса |
| --- | --- | --- |
| Дизайн | threat modeling | часы |
| Код | SAST, secret scanning | минуты |
| Сборка | SCA, скан образа | минуты |
| Staging | DAST | часы |
| Прод | runtime-детект | дни и репутация |

Ошибка, найденная в дизайне, стоит в десятки раз дешевле, чем в продакшене.

## Секретный менеджмент

| Уровень | Инструмент |
| --- | --- |
| Разработка | .env + dotenv (локально, в .gitignore) |
| CI | secrets хранилище CI |
| Runtime | Vault, Secrets Manager, K8s Secret + внешнее хранилище |
| GitOps | SOPS/Sealed Secrets |

Правило: у каждого секрета есть владелец, срок жизни и процедура ротации.

## Быстрая проверка репозитория

```bash
gitleaks detect --source . --redact
git log -p --all -S 'AKIA' | head
trufflehog git file://. --only-verified
```

Если ключ найден — сначала отозвать, потом чистить историю. Порядок важен.

## Короткое резюме

- Секреты — в менеджере секретов; в Git только шаблоны и зашифрованные значения.
- Сканирование идёт слоями: секреты → зависимости → код → образы/IaC.
- SBOM и подписи делают цепочку поставки проверяемой.
- Сканеры включают с baseline и падают на новых критичных находках.

## Подробный разбор темы

Сканирование секретов должно работать до merge и после него: pre-commit быстро предупреждает автора, CI блокирует утечку, а периодический scan ищет старые случаи. Сканер может выдавать ложные срабатывания и пропускать закодированный секрет, поэтому задайте процедуру triage и проверку истории репозитория. Если ключ попал в Git, удаление строки не отзывает его.

Считайте утечку действительным инцидентом: отзовите credential, проверьте audit log на злоупотребление, выпустите замену и ограничьте её область. Не копируйте secret в issue или общий чат при расследовании. Добавляйте исключение только с обоснованием, владельцем и сроком; используйте тестовые маркеры, чтобы проверить, что правило действительно срабатывает в pipeline.

## Пошаговый сценарий

![Порядок действий: Секреты и сканирование в пайплайне](assets/img/howto/11-devsecops--01-secrets-and-scanning.svg)

1. Определите границы кода, зависимостей, контейнеров и конфигурации для сканирования.
2. Запустите secret, dependency и image scanning на pull request.
3. Проверьте finding, достижимость, приоритет и владельца исправления.
4. Отзовите подтверждённый credential и проверьте повторный scan после фикса.

## Проверьте себя

1. Почему при утечке секрета первым шагом идёт отзыв, а не чистка истории?
2. Чем SBOM отличается от отчёта сканера уязвимостей?
3. Какие четыре типа сканирования стоит включить в CI и на каком этапе?
