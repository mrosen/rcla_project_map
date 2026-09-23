#!/bin/bash
cd /home/msr/rcla_project_map
tmux kill-session -t orchestrator 2>/dev/null || true
pkill -9 -f orchestrator.py 2>/dev/null || true
tmux new-session -d -s orchestrator 'cd /home/msr/rcla_project_map && /home/msr/venv/bin/python3 orchestrator.py'
echo "Started orchestrator in persistent tmux session 'orchestrator'."
echo "Access in browser at: http://localhost:8000 (or http://127.0.0.1:8000)"
echo "To view live logs: tmux attach -t orchestrator (press Ctrl+B then D to detach)"


