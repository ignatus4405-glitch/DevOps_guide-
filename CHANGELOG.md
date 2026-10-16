# История изменений

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
версии — по [Semantic Versioning](https://semver.org/lang/ru/).
Новые записи добавляются автоматически при выпуске релиза (см. `.github/workflows/build.yml`).

## [0.1.0] — 2026-10-16

### Добавлено
- Полный курс DevOps Engineer: 13 модулей, 30 уроков, 138 вопросов, 52 практические задачи (~33 часа).
- Глоссарий из 83 терминов; 15 векторных иллюстраций в `content/assets/img`.
- Приложение на PySide6: дашборд с прогрессом, просмотр уроков с подсветкой кода,
  тесты с разбором ответов, практика с автопроверкой команд, итоговый экзамен,
  тёмная/светлая темы, экспорт отчёта в Markdown.
- Автообновление через GitHub Releases: проверка версии, баннер, диалог с release notes,
  загрузка установщика с проверкой SHA-256 и запуск тихой установки.
- CI/CD на GitHub Actions: проверка контента и тестов на Linux/Windows,
  сборка (PyInstaller) для Windows и Linux, установщик Inno Setup, релиз по тегу,
  автоматический подъём версии по истории коммитов, Dependabot.
- Инструменты: `tools/validate_content.py`, `tools/generate_version.py`,
  `tools/make_diagrams.py`, `tools/smoke_test.py`, `tools/next_version.py`,
  `tools/release_notes.py`, `tools/make_update_manifest.py`, `tools/ci_annotate.py`.
- Документация: архитектура, гайд по контенту, инструкция для агентов, релизный процесс.
- Скрипты разработки: `scripts/run_dev.sh`, `scripts/build_local.sh`; pre-commit
  (gitleaks, ruff, проверка контента) и шаблоны issue/PR.
- Установщик Inno Setup (`packaging/installer.iss`) с поддержкой тихой установки
  и спецификация PyInstaller (`packaging/devops_academy.spec`) с иконкой приложения.

### Исправлено
- Единые переводы строк (`.gitattributes`): хеши контента больше не расходятся
  между Linux и Windows; индекс контента пересчитывается от LF-версии файлов.
- Автопроверка задач: эталонные решения проходят собственные шаблоны (`regex_all`).
- Сборка на Ubuntu: установка системных библиотек Qt (`libgl1`, `libegl1`,
  `libxkbcommon0`, `libdbus-1-3`) — без них PySide6 не импортируется даже offscreen.
- Запуск из исходников через `python run.py` (точка входа PyInstaller вынесена в
  `packaging/entry.py`, чтобы относительные импорты работали в собранном виде).
