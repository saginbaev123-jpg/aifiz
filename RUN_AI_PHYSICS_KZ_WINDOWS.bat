@echo off
setlocal
cd /d "%~dp0"

echo AI Physics KZ 8.1.0 - Agentic Tools + PISA

echo [1/4] Cleaning Python cache...
for /d /r %%D in (__pycache__) do @if exist "%%D" rd /s /q "%%D"
for /r %%F in (*.pyc) do @if exist "%%F" del /q "%%F"

echo [2/4] Selecting ONE Python environment...
set "PYTHON=python"
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"
if exist "venv\Scripts\python.exe" set "PYTHON=venv\Scripts\python.exe"
if exist "env\Scripts\python.exe" set "PYTHON=env\Scripts\python.exe"
echo Using: %PYTHON%

echo [3/4] Checking project and dependencies...
"%PYTHON%" CHECK_VISUAL_ENGINE.py
if errorlevel 1 (
  echo Project file check failed.
  pause
  exit /b 1
)
"%PYTHON%" -c "import streamlit, pandas, openai" >nul 2>&1
if errorlevel 1 (
  echo Required Python packages are missing in THIS environment.
  echo Installing requirements...
  "%PYTHON%" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Dependency installation failed. Check Internet access and Python installation.
    pause
    exit /b 1
  )
)

echo [4/4] Starting AI Physics KZ with the same Python environment...
"%PYTHON%" -m streamlit run app.py

endlocal
