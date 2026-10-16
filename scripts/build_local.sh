#!/usr/bin/env bash
# Локальная сборка приложения (без CI). Требуется Python 3.10+ и интернет.
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"
VENV="${VENV:-.venv}"

if [ ! -d "$VENV" ]; then
    "$PYTHON" -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

pip install --quiet --upgrade pip
pip install --quiet -r requirements-dev.txt

echo "== проверки =="
ruff check .
pytest -q
python tools/validate_content.py

echo "== подготовка версии =="
VERSION="$(cat VERSION | tr -d ' \r\n')"
python tools/generate_version.py --version "$VERSION" --build "local-$(date +%H%M)"

echo "== сборка =="
pyinstaller --noconfirm --clean packaging/devops_academy.spec

echo "== результат =="
ls -la dist/DevOpsAcademy | head
echo "Запуск: ./dist/DevOpsAcademy/DevOpsAcademy --self-test"
