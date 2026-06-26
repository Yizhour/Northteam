#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -r requirements.txt

export ENABLE_SCHEDULER="${ENABLE_SCHEDULER:-1}"
exec gunicorn -w "${WEB_CONCURRENCY:-1}" -b "${BIND:-0.0.0.0:8000}" wsgi:app
