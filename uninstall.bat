@echo off
rem Settee TV: removes the program, its shortcuts and its own Python. Your settings stay.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -Uninstall %*
pause
