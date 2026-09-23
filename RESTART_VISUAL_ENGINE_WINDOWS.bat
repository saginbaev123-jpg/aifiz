@echo off
setlocal
cd /d "%~dp0"
echo [1/4] Cleaning Python cache...
for /d /r %%D in (__pycache__) do @if exist "%%D" rd /s /q "%%D"
for /r %%F in (*.pyc) do @if exist "%%F" del /q "%%F"

echo [2/4] Checking Visual Engine files...
python CHECK_VISUAL_ENGINE.py
if errorlevel 1 (
  echo.
  echo Visual Engine check FAILED. Do not start Streamlit until the missing files above are fixed.
  pause
  exit /b 1
)

echo [3/4] Checking Streamlit...
python -c "import streamlit" >nul 2>&1
if errorlevel 1 (
  echo Streamlit is not available in this Python environment.
  echo Activate the project's virtual environment, then run this file again.
  pause
  exit /b 1
)

echo [4/4] Starting AI Physics KZ...
python -m streamlit run app.py
endlocal
