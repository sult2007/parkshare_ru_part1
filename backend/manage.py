#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys
from pathlib import Path


def main() -> None:
    """
    Точка входа для manage.py.

    ВАЖНО: добавляем корень репозитория в sys.path, чтобы пакеты
    уровня `accounts`, `parking`, `payments` и т.п. корректно импортировались,
    даже если запускаем `python backend/manage.py ...`.
    """
    current_file = Path(__file__).resolve()
    backend_dir = current_file.parent           # .../parkshare_ru_part1/backend
    project_root = backend_dir.parent           # .../parkshare_ru_part1

    # Гарантируем, что корень проекта в PYTHONPATH
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

    # Если переменная окружения не задана – по умолчанию используем dev-настройки
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings.local")

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Не удалось импортировать Django. Убедись, что виртуальное "
            "окружение активировано и зависимости установлены."
        ) from exc

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
