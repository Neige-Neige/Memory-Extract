@echo off
REM Launcher for Memory Extract.
REM Double-click this file to open the launcher window.
REM Hold Shift while double-clicking to force the launcher even if you've
REM previously checked "skip launcher".

setlocal
cd /d "%~dp0"

REM Prefer pythonw (no console window) but fall back to python.
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "%~dp0launcher.py"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        start "" python "%~dp0launcher.py"
    ) else (
        echo.
        echo Python not found in PATH. Please install Python 3.10+ first.
        echo.
        pause
    )
)

endlocal
