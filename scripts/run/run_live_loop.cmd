@echo off
rem London-window live loop: capture -> rule -> DEMO bracket orders (only with --arm and config\ctrader_demo.json). Unarmed by default: logs would-place decisions.
cd /d "%~dp0..\.."
set PYTHONPATH=%CD%\src
if not exist logs\live mkdir logs\live
.venv\Scripts\python.exe -u -m ai_trader.live.live_loop %* >> logs\live\loop.log 2>&1
