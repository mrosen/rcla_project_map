@echo off
echo Stopping RCLA Project Map Server...

echo [1/2] Terminating Windows port 8000 forwarder...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /F /PID %%a 2>nul
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*win_forwarder.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force 2>$null }" 2>nul

echo [2/2] Stopping WSL orchestrator session...
wsl -d Ubuntu bash -c "tmux kill-session -t orchestrator 2>/dev/null; pkill -9 -f orchestrator.py 2>/dev/null || true"

echo ========================================================
echo   RCLA Project Map Server is stopped.
echo ========================================================
exit /b 0

