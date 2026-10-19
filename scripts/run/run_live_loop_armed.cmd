@echo off
cd /d %~dp0..\..
if not exist logs\live mkdir logs\live
echo ARMED %date% %time% >> logs\live\loop.log
.venv\Scripts\python.exe -u -m ai_trader.live.live_loop --arm --transport file --cfd-symbols XAUUSD >> logs\live\loop.log 2>&1
