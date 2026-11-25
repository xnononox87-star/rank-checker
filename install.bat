@echo off
cd /d "%~dp0"
echo [1/3] Checking Python...
python -c "import sys; assert sys.version_info >= (3,10)" >nul 2>nul
if errorlevel 1 (
  echo.
  echo Python 3.10+ is not installed. Please install it first - see the guide.
  pause
  exit /b
)
echo [2/3] Creating program environment...
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
echo [3/3] Installing packages - this takes a few minutes...
pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Install failed. Take a screenshot of this window and send it to Claude.
  pause
  exit /b
)
echo Installing optional screenshot-reading (OCR) packages...
pip install -r requirements-ocr.txt
if errorlevel 1 echo OCR packages failed - the program still works, only screenshot reading is off.
echo.
echo ===== DONE! Double-click run.bat to start. =====
pause
