@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Scripts\run.ps1" -Mode Play
if errorlevel 1 pause
