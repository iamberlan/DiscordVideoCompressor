@echo off
setlocal
cd /d "%~dp0"
python -m PyInstaller --noconfirm --windowed --collect-all tkinterdnd2 run.py
exit /b %errorlevel%
