@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\activate.bat (
  echo Please run install.bat first.
  pause
  exit /b
)
call .venv\Scripts\activate.bat
echo Checking for updates...
python updater.py
start "" cmd /c "timeout /t 5 >nul & start http://localhost:8501"
echo The program is running. Keep this window open while you use it.
echo To quit, close this window.
streamlit run app.py
