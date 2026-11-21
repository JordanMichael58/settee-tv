@echo off
rem Settee TV: double-click to install. No admin rights needed.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
pause
