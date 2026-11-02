@echo off
title Job Agent - Statistics
chcp 65001 > nul
echo ========================================================
echo    JOB AGENT - APPLICATION TRACKER METRICS
echo ========================================================
echo.
python main.py --stats
echo.
pause

