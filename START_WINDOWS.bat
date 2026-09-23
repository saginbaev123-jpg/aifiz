@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo AI Physics KZ - first start
echo ========================================

if not exist ".env" (
    echo [SETUP] .env file was not found. Creating it...
    if exist ".env.windows.example" (
        copy /Y ".env.windows.example" ".env" >nul
    ) else (
        echo APP_MODE=production> .env
        echo ALLOW_USER_API_KEY=false>> .env
        echo OPENAI_API_KEY=>> .env
        echo OPENAI_MODEL=gpt-5.6-luna>> .env
    )
    echo.
    echo IMPORTANT: Open the .env file and paste your OpenAI API key after:
    echo OPENAI_API_KEY=
    echo Then save the file. You can continue now and add the key later.
    echo.
)

if exist ".venv\Scripts\python.exe" goto INSTALL

echo [1/3] Creating virtual environment...
where py >nul 2>nul
if not errorlevel 1 goto USE_PY

where python >nul 2>nul
if not errorlevel 1 goto USE_PYTHON

echo.
echo ERROR: Python was not found.
echo Install Python 3.11 or 3.12 from python.org and enable "Add Python to PATH".
pause
exit /b 1

:USE_PY
py -3 -m venv .venv
if errorlevel 1 goto VENV_ERROR
goto INSTALL

:USE_PYTHON
python -m venv .venv
if errorlevel 1 goto VENV_ERROR
goto INSTALL

:VENV_ERROR
echo.
echo ERROR: Could not create the virtual environment.
echo Check your Python installation and try again.
pause
exit /b 1

:INSTALL
echo [2/3] Installing required packages...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto PIP_ERROR
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto PIP_ERROR

echo [3/3] Starting AI Physics KZ...
".venv\Scripts\python.exe" -m streamlit run app.py
if errorlevel 1 goto RUN_ERROR
exit /b 0

:PIP_ERROR
echo.
echo ERROR: Package installation failed.
echo Check your internet connection and the messages above.
pause
exit /b 1

:RUN_ERROR
echo.
echo ERROR: The application could not start.
echo Copy the error text from this window and send it to ChatGPT.
pause
exit /b 1
