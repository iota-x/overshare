@echo off
REM Start overshare on Windows. First run sets up a virtualenv and installs deps.
cd /d "%~dp0"

if not exist ".venv" (
  echo First run: creating virtualenv and installing dependencies...
  python -m venv .venv
  .venv\Scripts\python -m pip install --quiet --upgrade pip
  .venv\Scripts\pip install --quiet -r requirements.txt
)

if not exist ".env" (
  echo No .env found - copied .env.example to .env. Edit it, then run again.
  copy .env.example .env >nul
  exit /b 1
)

.venv\Scripts\pythonw -m overshare.app_win
