@echo off
title Job Agent - Telegram Bot Listener
chcp 65001 > nul
echo ========================================================
echo    JOB AGENT - TELEGRAM BOT INTERACTIVE DAEMON
echo ========================================================
echo Bot: @Jobmailer3629bot
echo Direct Link: https://t.me/Jobmailer3629bot
echo.
echo Make sure to open Telegram and send /start to @Jobmailer3629bot!
echo Starting interactive bot listener...
echo.
python main.py --bot
pause

