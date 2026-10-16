#!/usr/bin/env bash
# Запуск приложения из исходников (для разработки).
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"
VENV="${VENV:-.venv}"
if [ ! -d "$VENV" ]; then
    "$PYTHON" -m venv "$VENV"
    "$VENV/bin/pip" install --quiet -r requirements.txt
fi

export PYTHONPATH="src:${PYTHONPATH:-}"
exec "$VENV/bin/python" -m devops_academy.main "$@"
