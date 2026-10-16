@echo off
rem Download free Dukascopy 1-minute candles (2021-01-01 .. 2026-06-30) for 8 instruments into data\raw\dukascopy (polite, single connection).
cd /d "%~dp0..\.."
if not exist logs\dukascopy_fetch_2 mkdir logs\dukascopy_fetch_2
set LOG=logs\dukascopy_fetch_2\run.log
echo Started %DATE% %TIME% > %LOG%
.venv\Scripts\python.exe scripts\data\fetch_dukascopy_minutes.py >> %LOG% 2>&1
echo Finished %DATE% %TIME% >> %LOG%
