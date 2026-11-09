@echo off
REM Double-click this, or:  run.cmd -Mock   /   run.cmd -Port 8770
REM Uses -ExecutionPolicy Bypass for this process only, because Windows
REM defaults to "Restricted" which blocks .ps1 files.
setlocal
set "HERE=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%HERE%run.ps1" %*
if errorlevel 1 pause
