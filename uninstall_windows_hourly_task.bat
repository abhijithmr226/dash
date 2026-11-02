@echo off
title Uninstall Job Agent Hourly Task
chcp 65001 > nul
echo ========================================================
echo    JOB AGENT - REMOVE HOURLY BACKGROUND TASK
echo ========================================================
echo.
schtasks /delete /tn "JobAgentHourlyAlerts" /f
echo.
echo Task removed successfully.
pause

