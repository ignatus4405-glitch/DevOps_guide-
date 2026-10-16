---
id: cd-and-deploy
title: CD: деплой, окружения и стратегии выката
minutes: 40
---

# CD: деплой, окружения и стратегии выката

CI отвечает на вопрос «изменение корректно?». CD — на вопрос «как безопасно
доставить его пользователям?».

## Окружения и промоушен

```
feature-ветка → preview (опционально) → staging (авто) → prod (ручной approval)
```

| Окружение | Назначение | Данные | Деплой |
| --- | --- | --- | --- |
| dev/preview | быстрая проверка фичи | синтетика | автоматически на PR |
| staging | репетиция прода, e2e | обезличенная копия прода | автоматически после merge |
| prod | пользователи | реальные | approval + стратегия выката |

Промоушен — продвижение **одного и того же артефакта**, а не пересборка. Для
Docker-образов это означает: `image: ghcr.io/org/app@sha256:...` (digest вместо тега —
тег `latest` может измениться и сломать воспроизводимость).

```yaml
  deploy-staging:
    needs: build
    environment: staging
    if: github.ref == 'refs/heads/main'
    steps:
      - run: ./scripts/deploy.sh --env staging --image "$IMAGE@$DIGEST"
      - run: ./scripts/smoke-test.sh https://staging.example.com

  deploy-prod:
    needs: deploy-staging
    environment: production        # правило approval в настройках репозитория
    steps:
      - run: ./scripts/deploy.sh --env prod --image "$IMAGE@$DIGEST"
      - run: ./scripts/verify-release.sh https://api.example.com 5m
```

## Миграции базы данных

Порядок «expand → migrate → contract» позволяет деплоить без простоя:

1. **Expand:** добавить новую колонку/таблицу, старый код продолжает работать.
2. **Deploy:** приложение пишет в старое и новое поле, читает по возможности.
3. **Migrate:** перенести данные (batch-задача).
4. **Contract:** убрать старое поле, когда все версии кода обновлены.

!!! warning "Важно"
    Никогда не полагайтесь на авто-миграции при старте каждого контейнера: при
    масштабировании 20 реплик попытаются применить миграцию одновременно. Миграция —
    отдельный шаг пайплайна с блокировкой (например, Alembic + advisory lock).

## Стратегии выката

![Стратегии деплоя](assets/img/deployment-strategies.svg)

| Стратегия | Как работает | Плюсы | Минусы |
| --- | --- | --- | --- |
| Rolling | pod'ы заменяются постепенно | просто, простой ≈ 0 | версии смешаны на короткое время |
| Blue/Green | два окружения, переключение трафика | мгновенный откат | двойные ресурсы |
| Canary | 5 % → 25 % → 100 % с проверкой метрик | ранний сигнал проблем | нужна развитая наблюдаемость |
| Feature flags | код в проде, включение по группам | тестирование на живых | нужен менеджмент флагов |

```bash
# Canary в Kubernetes: 1 из 10 pod'ов на новой версии
kubectl set image deployment/app app=ghcr.io/org/app:v2.1.0 --record
kubectl rollout status deployment/app
kubectl get pods -l app=app -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.spec.containers[0].image}{"\n"}{end}'
kubectl rollout undo deployment/app          # откат одной командой
```

## Проверка после деплоя

Деплой не заканчивается на «зелёном» пайплайне. Нужны **smoke-тесты** и контроль
бизнес-метрик:

```bash
#!/usr/bin/env bash
# verify-release.sh — проверяет, что релиз здоров
set -euo pipefail
URL="${1:?url}"; DURATION="${2:-5m}"
for i in {1..10}; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$URL/health" || echo 000)
  [[ "$code" == "200" ]] || { echo "healthcheck вернул $code" >&2; exit 1; }
  sleep 5
done
# Дополнительно: сравнить error rate до и после релиза по метрикам Prometheus
echo "релиз стабилен в течение $DURATION"
```

Правило: **если после выката ухудшились SLI (ошибки, задержка) — автоматический
откат**, а не героическое «сейчас поправим вперёд».

## GitOps: доставка через Git

В GitOps желаемое состояние кластера описано в Git, а агент (Argo CD, Flux)
постоянно приводит реальность к нему. Полезные свойства: аудит изменений,
откат = `git revert`, отсутствие «ручных kubectl apply», дрейф конфигурации виден.

```yaml
# Argo CD Application (упрощённо)
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata: { name: api, namespace: argocd }
spec:
  source: { repoURL: https://github.com/org/k8s-manifests, path: apps/api, targetRevision: main }
  destination: { server: https://kubernetes.default.svc, namespace: prod }
  syncPolicy: { automated: { prune: true, selfHeal: true } }
```

## Короткое резюме

- CD доставляет тот же артефакт через окружения; prod — под approval.
- Миграции делаются в пайплайне и в порядке expand/contract.
- Стратегия выката (rolling/blue-green/canary/flags) выбирается по риску и возможностям наблюдаемости.
- После релиза обязательны smoke-тесты и автоматический откат по плохим метрикам.

## Проверьте себя

1. Почему «пересобрать образ для прода» ломает воспроизводимость?
2. Как деплоить миграции, чтобы они не выполнялись 20 репликами одновременно?
3. Когда canary выгоднее blue/green, а когда — наоборот?
