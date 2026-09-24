#!/bin/bash
cd /home/msr/rcla_project_map
tmux kill-session -t orchestrator 2>/dev/null || true
pkill -9 -f orchestrator.py 2>/dev/null || true
tmux new-session -d -s orchestrator 'cd /home/msr/rcla_project_map && /home/msr/venv/bin/python3 orchestrator.py'
echo "Started orchestrator in persistent tmux session 'orchestrator'."

# Ensure Windows port 8000 forwarder is running so http://localhost:8000 works seamlessly on Windows
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "
  Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -like '*win_forwarder.py*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force -ErrorAction SilentlyContinue }
  Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = 'pythonw.exe \"\\\\wsl.localhost\\Ubuntu\\home\\msr\\rcla_project_map\\win_forwarder.py\"' }
" >/dev/null 2>&1 || true

echo "Access in browser at: http://localhost:8000 (or http://127.0.0.1:8000)"
echo "To view live logs: tmux attach -t orchestrator (press Ctrl+B then D to detach)"
