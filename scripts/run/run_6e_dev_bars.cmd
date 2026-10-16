@echo off
rem Decode Mar 2025 - Jun 2026 MBO days into 1-minute bars (Jul-Sep 2026 lockbox stays sealed).
cd /d "%~dp0..\.."
set PYTHONPATH=%CD%\src
if not exist logs\six_e_dev_bars_1 mkdir logs\six_e_dev_bars_1
set LOG=logs\six_e_dev_bars_1\run.log
echo Started %DATE% %TIME% > %LOG%
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests\test_six_e_horizon_census.py >> %LOG% 2>&1
if errorlevel 1 (echo TESTS FAILED >> %LOG% & echo Tests failed - see %LOG% & pause & exit /b 1)
.venv\Scripts\python.exe -m ai_trader.research.six_e_horizon_census bars >> %LOG% 2>&1
.venv\Scripts\python.exe -m ai_trader.research.six_e_horizon_census census >> %LOG% 2>&1
echo Finished %DATE% %TIME% >> %LOG%
