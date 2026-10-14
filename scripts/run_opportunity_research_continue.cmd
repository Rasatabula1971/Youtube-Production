@echo off
rem Scheduled-task entry point for Opportunity Research continuation (D-114).
rem Task Scheduler starts in the Windows system folder, and modules are
rem started with `python -m` from the project root, so change there first.
rem Usage: run_opportunity_research_continue.cmd "C:\path\to\python.exe"
setlocal
cd /d "%~dp0.."
set "PYTHON_EXE=%~1"
if "%PYTHON_EXE%"=="" set "PYTHON_EXE=python"
"%PYTHON_EXE%" -m experiment_01_discovery.opportunity_research --mode continue
exit /b %ERRORLEVEL%
