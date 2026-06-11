@echo off
rem One-click launcher for OCR Compare (fallback for machines that block the
rem unsigned OCR-Compare.exe). All logic lives in bootstrap.ps1.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap.ps1" %*
if errorlevel 1 pause
