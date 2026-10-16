"""DevOps Academy — офлайн-курс по DevOps Engineer с тестами и практикой.

Пакет намеренно разбит на небольшие модули, чтобы любой агент/разработчик мог
продолжить работу: модель контента (content.py), рендер markdown
(markdown_renderer.py), прогресс (progress.py), обновления (updater.py),
интерфейс (ui/*).
"""

from .version import APP_NAME, APP_VERSION, GITHUB_REPO

__all__ = ["APP_NAME", "APP_VERSION", "GITHUB_REPO"]
