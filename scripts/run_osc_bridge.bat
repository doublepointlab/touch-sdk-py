@echo off
REM Touch SDK OSC Bridge - Windows launcher
REM
REM Usage:
REM   run_osc_bridge.bat                     - Connect to any watch
REM   run_osc_bridge.bat --name-filter "My Watch"  - Connect to a specific watch by name
REM
REM All arguments are passed through to osc_client_server.py
REM Other useful flags:
REM   --verbose           Show debug output
REM   --client-port 6666  Port to send OSC to (default: 6666)
REM   --server-port 6667  Port to receive OSC on (default: 6667)
REM   --test              Test mode: send random OSC data without a watch

cd /d "%~dp0\.."

if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment not found. Running setup first...
    powershell -ExecutionPolicy Bypass -File "%~dp0oneshot_setup.ps1"
    if errorlevel 1 (
        echo Setup failed.
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate.bat

echo Starting OSC Bridge...
echo Tip: Use --name-filter "Watch Name" to connect to a specific watch
echo.

python examples\osc_client_server.py %*
