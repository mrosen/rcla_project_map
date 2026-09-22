#!/bin/bash
cd /home/msr/rcla_project_map
pkill -9 -f orchestrator.py 2>/dev/null || true
sleep 1
nohup /home/msr/venv/bin/python3 orchestrator.py > orchestrator.log 2>&1 &
echo "Started orchestrator (PID: $!)"

