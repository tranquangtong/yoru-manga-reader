@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "scripts\update-site.py"
) else (
  where python >nul 2>nul
  if %errorlevel%==0 (
    python "scripts\update-site.py"
  ) else if exist "%LOCALAPPDATA%\Python\bin\python.exe" (
    "%LOCALAPPDATA%\Python\bin\python.exe" "scripts\update-site.py"
  ) else (
    echo KHONG TIM THAY PYTHON. Hay cai Python 3 roi chay lai.
  )
)

echo.
pause
endlocal
