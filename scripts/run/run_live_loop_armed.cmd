@echo off
rem ARMED live loop: places 0.01-lot DEMO bracket orders through the AiTraderFileBridge cBot (demo-only guard inside the cBot). Kill switch: create Documents\cAlgo\Data\cBots\AiTraderFileBridge\KILL
cd /d "%~dp0..\.."
set PYTHONPATH=%CD%\src
if not exist logs\live mkdir logs\live
echo ARMED %DATE% %TIME% >> logs\live\loop.log
.venv\Scripts\python.exe -u -m ai_trader.live.live_loop --arm --transport file >> logs\live\loop.log 2>&1
pause
