#!/bin/bash
echo "Stopping RCLA Project Map Server..."
tmux kill-session -t orchestrator 2>/dev/null || true
pkill -9 -f orchestrator.py 2>/dev/null || true
echo "RCLA Project Map Server is stopped."

