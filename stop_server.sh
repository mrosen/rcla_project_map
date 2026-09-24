#!/bin/bash
echo "Stopping RCLA Project Map Server..."
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "
  Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -like '*win_forwarder.py*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force -ErrorAction SilentlyContinue }
" 2>/dev/null || true
tmux kill-session -t orchestrator 2>/dev/null || true
pkill -9 -f orchestrator.py 2>/dev/null || true
echo "RCLA Project Map Server is stopped."
