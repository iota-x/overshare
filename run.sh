#!/usr/bin/env bash
# Start in-detail. First run sets up a virtualenv and installs deps.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "First run: creating virtualenv and installing dependencies…"
  python3 -m venv .venv
  ./.venv/bin/pip install --quiet --upgrade pip
  ./.venv/bin/pip install --quiet -r requirements.txt
fi

if [ ! -f ".env" ]; then
  echo "No .env found — copying .env.example to .env. Edit it, then rerun."
  cp .env.example .env
  exit 1
fi

exec ./.venv/bin/python -m in_detail.app
