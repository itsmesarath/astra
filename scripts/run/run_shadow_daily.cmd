@echo off
rem Daily shadow run: convert all NinjaTrader capture files into the live minute store, then evaluate the candidate rule (no orders).
cd /d "%~dp0..\.."
set PYTHONPATH=%CD%\src
if not exist logs\shadow mkdir logs\shadow
set CAP=%USERPROFILE%\Documents\NinjaTrader 8\ai-trader-captures
set LOG=logs\shadow\daily_%DATE:~-4%%DATE:~-7,2%%DATE:~-10,2%.log
echo Started %DATE% %TIME% > "%LOG%"
dir /b "%CAP%\ninjatrader-*.jsonl" >> "%LOG%" 2>&1
.venv\Scripts\python.exe -m ai_trader.live.capture_minutes "%CAP%\ninjatrader-*.jsonl" --output data\live\6e_minutes >> "%LOG%" 2>&1
.venv\Scripts\python.exe -m ai_trader.live.shadow_signals --warmup-bars data\processed\6e_minute_bars_dev_1 --warmup-book data\processed\6e_book_minutes_dev_1 --since 2026-10-01 >> "%LOG%" 2>&1
echo Finished %DATE% %TIME% >> "%LOG%"
type "%LOG%"
pause
