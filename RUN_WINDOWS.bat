@echo off
setlocal
cd /d "%~dp0"

if not exist ".env" (
    echo .env file was not found.
    if exist ".env.windows.example" copy /Y ".env.windows.example" ".env" >nul
    echo Open .env and paste your OpenAI API key after OPENAI_API_KEY=, then save it.
    pause
)

if not exist ".venv\Scripts\python.exe" goto FIRST_START

".venv\Scripts\python.exe" -m streamlit run app.py
if errorlevel 1 goto RUN_ERROR
exit /b 0

:FIRST_START
echo First run is required.
echo Please run START_WINDOWS.bat first.
pause
exit /b 1

:RUN_ERROR
echo.
echo ERROR: The application could not start.
echo Copy the error text from this window and send it to ChatGPT.
pause
exit /b 1
