@echo off
rem Roadmap 8.1: 6E horizon feasibility census on 2025 data only (reserved 2026 untouched).
cd /d "%~dp0..\.."
set PYTHONPATH=%CD%\src
if not exist logs\six_e_horizon_census_1 mkdir logs\six_e_horizon_census_1
set LOG=logs\six_e_horizon_census_1\run.log
echo Started %DATE% %TIME% > %LOG%
echo [1/3] Unit tests >> %LOG%
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests\test_six_e_horizon_census.py tests\test_platform_capture.py >> %LOG% 2>&1
if errorlevel 1 (echo TESTS FAILED >> %LOG% & echo Tests failed - see %LOG% & pause & exit /b 1)
echo [2/3] Decode 2025 MBO days into 1-minute bars >> %LOG%
.venv\Scripts\python.exe -m ai_trader.research.six_e_horizon_census bars >> %LOG% 2>&1
echo [3/3] Census >> %LOG%
.venv\Scripts\python.exe -m ai_trader.research.six_e_horizon_census census >> %LOG% 2>&1
echo Finished %DATE% %TIME% >> %LOG%
echo Done - see %LOG%
