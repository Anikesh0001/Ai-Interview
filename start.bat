@echo off
rem Double-click to set up and start InterviewForge on Windows. Extra arguments are passed to run.py
rem (for example: start.bat install, start.bat test).
setlocal
cd /d "%~dp0"

rem Prefer the Python launcher with a version that has prebuilt packages for every dependency.
for %%V in (3.13 3.12 3.14 3.11) do (
  py -%%V -c "import sys" >nul 2>nul && (
    py -%%V run.py %*
    goto done
  )
)
python -c "import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] <= (3, 14) else 1)" >nul 2>nul && (
  python run.py %*
  goto done
)
echo.
echo   Python 3.11 - 3.14 was not found.
echo   Install Python 3.13 from https://www.python.org/downloads/
echo   and tick "Add python.exe to PATH" in the installer, then run this file again.
echo.

:done
echo.
pause
