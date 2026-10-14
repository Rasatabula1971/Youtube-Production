@echo off
rem Scheduled-task entry point (D-114): the research continuation, then a radar tick.
rem Task Scheduler starts in the Windows system folder, and modules are
rem started with `python -m` from the project root, so change there first.
rem Usage: run_scheduled_tick.cmd "C:\path\to\python.exe"
setlocal
cd /d "%~dp0.."
set "PYTHON_EXE=%~1"
if "%PYTHON_EXE%"=="" set "PYTHON_EXE=python"
"%PYTHON_EXE%" -m opportunity_engine.scheduled_tick
exit /b %ERRORLEVEL%
