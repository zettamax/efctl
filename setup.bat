@echo off
echo Setting up efctl...
echo.
python -m venv .venv
.venv\Scripts\pip install --upgrade pip
.venv\Scripts\pip install .
echo.
echo Setup complete! Double-click run.bat to start.
pause
