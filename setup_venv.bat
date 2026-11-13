@echo off
setlocal
py -m venv .venv
if errorlevel 1 exit /b 1
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 exit /b 1
python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
echo.
echo Environment ready. Start the game with: .venv\Scripts\python main.py
endlocal
