@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Scripts\run.ps1" -Mode Open
if errorlevel 1 pause
