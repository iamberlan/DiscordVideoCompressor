@echo off
setlocal
cd /d "%~dp0"
python tools\build_release.py
exit /b %errorlevel%
