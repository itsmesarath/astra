@echo off
rem Rebuild the 6E order book from MBO and write minute-level book features (Mar 2025 - Jun 2026).
cd /d "%~dp0..\.."
set PYTHONPATH=%CD%\src
if not exist logs\six_e_book_minutes_1 mkdir logs\six_e_book_minutes_1
set LOG=logs\six_e_book_minutes_1\run.log
echo Started %DATE% %TIME% > %LOG%
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests\test_six_e_book_minutes.py >> %LOG% 2>&1
if errorlevel 1 (echo TESTS FAILED >> %LOG% & echo Tests failed - see %LOG% & pause & exit /b 1)
.venv\Scripts\python.exe -m ai_trader.research.six_e_book_minutes >> %LOG% 2>&1
echo Finished %DATE% %TIME% >> %LOG%
