@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo First run: installing the pinned Python dependencies. Internet is required once.
  py -3.12 -m venv .venv
  if errorlevel 1 goto failed
)
if not exist ".venv\deps-ready" (
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 goto failed
  type nul > .venv\deps-ready
)
.venv\Scripts\python.exe run_gui.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo Failed. Install Python 3.12 x64, then follow README.md. No media files were uploaded.
pause
exit /b 1
