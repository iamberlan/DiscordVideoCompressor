@echo off
rem run.bat - Launch Discord Video Compressor on Windows
cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel% equ 0 (
    python run.py %*
    goto :eof
)

where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3 run.py %*
    goto :eof
)

echo [ERROR] Python was not found on your PATH.
echo Please install Python 3 or ensure it is added to your environment variables.
pause

