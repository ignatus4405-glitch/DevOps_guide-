---
id: security-deep
title: Безопасность контейнеров: rootless, capabilities, scanning
minutes: 30
---

# Безопасность контейнеров: rootless, capabilities, scanning

Контейнер — не песочница. Процесс в контейнере — обычный процесс на хосте, просто
с изолированным пространством имён. Если он работает от root и имеет доступ к
docker.sock, это фактически root на хосте.

## Принцип наименьших привилегий

```dockerfile
FROM python:3.12-slim
RUN groupadd -r app && useradd -r -g app app
COPY --chown=app:app . /app
WORKDIR /app
USER app
CMD ["python", "-m", "app"]
```

Проверка:

```bash
docker run --rm app id
```

Если `uid=0(root)` — плохо. В Kubernetes то же самое настраивается через
`securityContext`.

## Capabilities

По умолчанию контейнер получает набор capabilities (включая `NET_RAW`,
`CHOWN`, `SETUID`). Их можно сбросить:

```bash
docker run --cap-drop=ALL --cap-add=NET_BIND_SERVICE app
```

В Kubernetes:

```yaml
securityContext:
  runAsNonRoot: true
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop: ["ALL"]
```

`readOnlyRootFilesystem` ломает приложения, которые пишут в `/tmp` или текущий
каталог. Решение — `emptyDir` для `/tmp` и явные writable-точки.

## Образ: поверхность атаки

| Практика | Почему |
| --- | --- |
| минимальный базовый образ | меньше пакетов — меньше CVE |
| фиксированные версии | `latest` может измениться незаметно |
| без root | снижает последствия эксплуатации |
| без shell и компилятора | усложняет атаку |
| `.dockerignore` | не тащить секреты и `.git` |

Сканирование:

```bash
docker scout cves app:latest
trivy image --severity HIGH,CRITICAL app:latest
grype app:latest
```

В CI — гейт «нет CRITICAL с доступным фиксом». Базы CVE обновляются постоянно,
поэтому скан запускают и по расписанию: образ, собранный месяц назад, может стать
уязвимым сегодня.

## Подписи и целостность

```bash
cosign sign ghcr.io/org/app@sha256:...
cosign verify ghcr.io/org/app@sha256:... \
  --certificate-identity-regexp 'https://github.com/org/.*' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

Подпись привязывает образ к конкретному пайплайну. Без проверки подписи в кластере
подпись бесполезна.

## Runtime-защита

- Seccomp-профиль ограничивает системные вызовы;
- AppArmor/SELinux — мандатный доступ;
- Falco — детект подозрительной активности (shell в поде, чтение `/etc/shadow`);
- NetworkPolicy — ограничение сетевого трафика;
- запрет монтирования `docker.sock`.

Монтирование `docker.sock` в контейнер даёт ему полный контроль над Docker,
фактически root. Для сборки используйте rootless BuildKit или Kaniko.

## Чек-лист безопасного контейнера

- [ ] процесс не root;
- [ ] capabilities сброшены;
- [ ] root filesystem только для чтения;
- [ ] нет `privileged: true`;
- [ ] нет `hostPath` без необходимости;
- [ ] образ подписан и просканирован;
- [ ] секреты не встроены в слои;
- [ ] заданы лимиты CPU/памяти;
- [ ] NetworkPolicy ограничивает трафик.

## Сканирование в конвейере

Образ нужно сканировать дважды: при сборке и перед деплоем. Первое ловит
новые пакеты, второе — уязвимости, появившиеся после публикации базы CVE.

```bash
trivy image --severity HIGH,CRITICAL --exit-code 1 app:${GIT_SHA}
```

Политика по умолчанию: блокировать HIGH и CRITICAL с исправлением, но не
ломать сборку из-за уязвимости без фикса. Иначе пайплайн краснеет на том, что
команда не может исправить, и сканирование отключают.

Полезно фиксировать результат в артефакте: через месяц видно, стало лучше или
хуже. Скан без истории превращается в ритуал.

## Проверьте себя

1. Почему контейнер от root опаснее, чем кажется?
2. Что делает `--cap-drop=ALL` и что придётся вернуть?
3. Зачем сканировать образ повторно, если он не менялся?
4. Почему монтирование docker.sock — риск?

!!! warning "Важно"
    Контейнер не заменяет виртуальную машину в модели угроз. Если вы запускаете
    чужой код, изоляция должна быть сильнее: gVisor, Kata Containers или отдельная
    ВМ.
