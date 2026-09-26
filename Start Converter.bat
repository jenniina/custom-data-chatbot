@echo off
cd /d "%~dp0"
echo The converter is part of the chatbot: open http://127.0.0.1:8501/admin/convert/
echo If the chatbot is already running, use that address in your browser.
call "Start Chatbot.bat"
