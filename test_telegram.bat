@echo off
title Job Agent - Telegram Test
chcp 65001 > nul
echo ========================================================
echo    JOB AGENT - TEST TELEGRAM NOTIFICATIONS
echo ========================================================
echo.
python main.py --test-telegram
echo.
pause

