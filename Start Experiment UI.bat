@echo off
setlocal
cd /d "%~dp0"
title YouTube Production - Experiment Control
echo Starting Experiment Control UI...
echo.
python ".\experiment_ui\server.py"
if errorlevel 1 (
  echo.
  echo The Experiment Control UI stopped with an error.
  pause
)
