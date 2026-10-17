# DevOps Academy

**Windows-приложение с полным курсом по профессии DevOps Engineer: уроки с иллюстрациями,
практические задачи с автопроверкой, тесты по модулям и итоговый экзамен.**

Всё работает офлайн: контент лежит внутри приложения, интернет нужен только для
проверки обновлений (и её можно отключить).

[![CI](https://github.com/ignatus4405-glitch/DevOps_guide-/actions/workflows/ci.yml/badge.svg)](../../actions/workflows/ci.yml)
[![Build & Release](https://github.com/ignatus4405-glitch/DevOps_guide-/actions/workflows/build.yml/badge.svg)](../../actions/workflows/build.yml)
[![Последний релиз](https://img.shields.io/github/v/release/ignatus4405-glitch/DevOps_guide-?label=release)](../../releases/latest)

## Что внутри курса

| # | Модуль | Уроки | Вопросы | Задачи |
| --- | --- | --- | --- | --- |
| 1 | Введение в DevOps | 3 | 12 | 4 |
| 2 | Linux для DevOps | 4 | 14 | 5 |
| 3 | Bash и автоматизация | 2 | 12 | 4 |
| 4 | Git и совместная работа | 2 | 10 | 4 |
| 5 | Сети для DevOps | 2 | 10 | 3 |
| 6 | CI/CD и GitHub Actions | 2 | 10 | 4 |
| 7 | Docker и контейнеры | 2 | 10 | 4 |
| 8 | Kubernetes | 3 | 10 | 4 |
| 9 | IaC: Terraform и Ansible | 2 | 10 | 4 |
| 10 | Облако: AWS, сети, IAM и стоимость | 2 | 10 | 4 |
| 11 | Наблюдаемость: метрики, логи, алерты | 2 | 10 | 4 |
| 12 | DevSecOps: безопасность в конвейере | 2 | 10 | 4 |
| 13 | Финальный проект и выход на работу | 2 | 10 | 4 |
| | **Итого** | **30** | **138** | **52** |

Плюс: глоссарий из 83 терминов, 15 векторных иллюстраций, итоговый экзамен
(случайные вопросы из всех модулей) и экспорт отчёта о прохождении в Markdown.

## Возможности приложения

- 📚 **Уроки** — markdown с подсветкой команд, таблицами (сетка и подложка строк
  подстраиваются под тему), врезками и схемами.
- 🧪 **Тесты** — одиночный/множественный выбор и текстовые ответы, разбор каждого ответа,
  порог сдачи по модулю, сохранение лучшего результата.
- 🛠 **Практика** — 52 задачи с автопроверкой введённых команд, подсказками по шагам
  и эталонными решениями; отметка «выполнено» в прогрессе.
- 📈 **Дашборд** — прогресс по урокам, задачам и тестам, дорожная карта модулей,
  серия дней занятий, экспорт отчёта в Markdown.
- 🎓 **Экзамен** — 20 случайных вопросов из всего курса, порог 80 %.
- 🌓 **Темы** — тёмная и светлая, масштабируемое окно, горячие клавиши
  (`Ctrl+G` глоссарий, `Ctrl+E` экзамен, `Ctrl+T` тема).
- 🔄 **Автообновление** — приложение проверяет GitHub Releases, показывает баннер
  и диалог с описанием изменений, скачивает установщик, проверяет SHA-256 и запускает
  тихую установку.

## Установка

1. Откройте [последний релиз](../../releases/latest).
2. Скачайте `DevOpsAcademy-Setup-<версия>.exe` и запустите (тихая установка:
   `/SILENT /SUPPRESSMSGBOXES /NOCREATEAPPDIR` при необходимости).
3. Портативный вариант — `DevOpsAcademy-<версия>-windows-x64.zip`.

Альтернатива: запуск из исходников — `bash scripts/run_dev.sh` (Linux/macOS/WSL)
или `python run.py` (нужен Python 3.10+: `pip install -r requirements.txt`, затем `python run.py --self-test`).

## Как выходят версии

Полностью автоматически через GitHub Actions (`.github/workflows/build.yml`):

1. push в `main` → прогон линтера, тестов и проверки контента;
2. версия поднимается по истории коммитов (`feat` → minor, `BREAKING CHANGE` → major,
   иначе patch); если версия ещё не выпускалась — выпускается как есть;
3. сборка: Windows (exe + ZIP + установщик Inno Setup) и Linux (tar.gz);
4. публикация GitHub Release с `SHA256SUMS.txt`, `update.json` и release notes;
5. клиенты получают уведомление о новой версии при следующем запуске.

Ручной выпуск: Actions → **Build & Release** → Run workflow (можно выбрать bump).

## Документация для разработки

| Документ | О чём |
| --- | --- |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | устройство приложения, слои, точки расширения |
| [docs/CONTENT_GUIDE.md](docs/CONTENT_GUIDE.md) | как добавить модуль, урок, вопрос, задачу |
| [docs/AGENT_GUIDE.md](docs/AGENT_GUIDE.md) | правила работы для ИИ-агентов и контрибьюторов |
| [docs/RELEASING.md](docs/RELEASING.md) | как устроены версии, релизы и автообновление |
| [CHANGELOG.md](CHANGELOG.md) | история изменений (обновляется в каждом релизе) |

## Локальная разработка

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
ruff check .                  # линтер
pytest -q                     # 127 тестов: контент, прогресс, рендер, GUI, обновления, релиз
python tools/validate_content.py     # структура курса
python tools/smoke_test.py           # дымовой тест GUI в offscreen
python run.py --self-test            # проверка контента и зависимостей
bash scripts/build_local.sh          # полная сборка PyInstaller
```

Служебные инструменты (`tools/`):

| Файл | Назначение |
| --- | --- |
| `validate_content.py` | проверка структуры курса (модули, уроки, тесты, задачи) |
| `generate_version.py` | `version.py` + `content/content_index.json` |
| `next_version.py` | расчёт следующей версии релиза по Conventional Commits |
| `release_notes.py` | release notes и автоматическая запись в `CHANGELOG.md` |
| `make_update_manifest.py` | `update.json` для автообновления |
| `make_diagrams.py` | генерация SVG-иллюстраций курса |
| `smoke_test.py` | дымовой тест GUI в offscreen-режиме |
| `run_tests.py` | запуск pytest в CI: лог, junit-xml и аннотация провалов |
| `ci_annotate.py` | сводка ошибок CI в аннотацию проверки |

## Ссылки

- Лицензия: MIT (см. [LICENSE](LICENSE))
- Вопросы и идеи: [Issues](../../issues) (шаблоны прилагаются)
