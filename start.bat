@echo off
rem Settee TV without installing: runs from this folder. Try it first with: start.bat --demo
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (py -3 -m settee %*) else (python -m settee %*)
