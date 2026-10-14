@echo off
setlocal
cd /d "%~dp0"
title YouTube Production - Experiment Control
echo Starting Experiment Control UI...
echo.
python -m experiment_ui.server
if errorlevel 1 (
  echo.
  echo The Experiment Control UI stopped with an error.
  pause
)
