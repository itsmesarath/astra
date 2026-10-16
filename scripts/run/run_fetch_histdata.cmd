@echo off
rem Download free histdata.com 1-minute bars (2021 .. Jun 2026) for 8 instruments into data\raw\dukascopy.
cd /d "%~dp0..\.."
if not exist logs\histdata_fetch_1 mkdir logs\histdata_fetch_1
set LOG=logs\histdata_fetch_1\run.log
echo Started %DATE% %TIME% > %LOG%
.venv\Scripts\python.exe scripts\data\fetch_histdata_minutes.py >> %LOG% 2>&1
echo Finished %DATE% %TIME% >> %LOG%
