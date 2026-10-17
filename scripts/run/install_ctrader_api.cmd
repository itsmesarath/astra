@echo off
rem Install the cTrader Open API message definitions into the project venv.
cd /d "%~dp0..\.."
.venv\Scripts\python.exe -m pip install ctrader-open-api
.venv\Scripts\python.exe -c "from ctrader_open_api.messages import OpenApiMessages_pb2; print(\"ctrader-open-api OK\")"
pause
