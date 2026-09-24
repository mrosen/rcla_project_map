@echo off
echo [1/3] Cleaning up any existing processes on port 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /F /PID %%a 2>nul
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*win_forwarder.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" 2>nul
wsl -d Ubuntu bash -c "tmux kill-session -t orchestrator 2>/dev/null; pkill -9 -f orchestrator.py 2>/dev/null || true"

echo [2/3] Launching Orchestrator inside persistent WSL session...
wsl -d Ubuntu bash -c "tmux new-session -d -s orchestrator 'cd /home/msr/rcla_project_map && /home/msr/venv/bin/python3 orchestrator.py'"

echo [3/3] Launching Windows localhost proxy...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = 'pythonw.exe \"%~dp0win_forwarder.py\"' }" >nul 2>&1

echo ========================================================
echo   RCLA Project Map Server is Ready!
echo   Open in browser: http://127.0.0.1:8000/
echo   Open in browser: http://localhost:8000/
echo ========================================================
