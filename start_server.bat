@echo off
echo Starting RCLA Orchestrator inside WSL...
wsl -d Ubuntu bash -c "cd /home/msr/rcla_project_map && pkill -9 -f orchestrator.py 2>/dev/null; nohup /home/msr/venv/bin/python3 orchestrator.py > orchestrator.log 2>&1 &"
echo Starting Windows localhost proxy...
start /min python %~dp0win_forwarder.py
echo Server and proxy ready at http://localhost:8000

