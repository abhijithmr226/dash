@echo off
title Job Agent - Scan and Alert
chcp 65001 > nul
echo ========================================================
echo    JOB AGENT - SCANNING JOB BOARDS AND ALERTING
echo ========================================================
echo.
python main.py --alerts --live
echo.
pause

