@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 goto failure
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failure
".venv\Scripts\python.exe" manage.py migrate --noinput
if errorlevel 1 goto failure
".venv\Scripts\python.exe" manage.py sync_admin
if errorlevel 1 goto failure
echo Setup complete. Set your private .env values, then open Start Chatbot.bat.
echo Visit http://127.0.0.1:8501 and sign in as admin.
pause
exit /b 0
:failure
echo Setup failed. Check Python 3.11 or newer, your configuration and internet connection.
pause
exit /b 1
