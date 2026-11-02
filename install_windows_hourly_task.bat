@echo off
title Install Job Agent Hourly Task
chcp 65001 > nul
echo ========================================================
echo    JOB AGENT - INSTALL HOURLY BACKGROUND TASK (WINDOWS)
echo ========================================================
echo.
echo This script sets up a Windows Task Scheduler job that will
echo automatically run every hour in the background (SILENTLY).
echo.
set "TASK_NAME=JobAgentHourlyAlerts"
set "RUNNER=%~dp0run_silent.vbs"

schtasks /create /tn "%TASK_NAME%" /tr "wscript.exe \"%RUNNER%\"" /sc hourly /mo 1 /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================================
    echo 🎉 SUCCESS! Hourly task '%TASK_NAME%' has been created.
    echo It will check for new Indian jobs every hour 24/7 silently!
    echo Notifications will arrive directly on your Telegram phone app.
    echo ========================================================
) else (
    echo.
    echo ❌ Failed to register scheduled task.
    echo Try right-clicking this batch file and select 'Run as Administrator'.
)
echo.
pause

