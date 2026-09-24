import socket
import subprocess
import threading
import re
import sys
import os

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

WSL_IP = None
WSL_IP_LOCK = threading.Lock()

def get_wsl_ip(force_refresh=False):
    global WSL_IP
    with WSL_IP_LOCK:
        if WSL_IP and not force_refresh:
            return WSL_IP
        try:
            # Run from C:\ so WSL doesn't try to translate network/UNC drives (e.g. Z:\)
            out = subprocess.check_output(
                ["wsl", "-d", "Ubuntu", "ip", "-4", "addr", "show", "eth0"],
                text=True,
                cwd="C:\\",
                stderr=subprocess.DEVNULL,
                timeout=5
            )
            m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", out)
            if m:
                WSL_IP = m.group(1)
                return WSL_IP
        except Exception as e:
            if not WSL_IP:
                print("Error resolving WSL IP:", e, flush=True)
        return WSL_IP or "127.0.0.1"

def forward(src, dst):
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except Exception:
        pass
    finally:
        try: src.close()
        except Exception: pass
        try: dst.close()
        except Exception: pass

def handle_client(client_sock, port):
    wsl_sock = None
    try:
        ip = get_wsl_ip(force_refresh=False)
        wsl_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        wsl_sock.settimeout(5)
        try:
            wsl_sock.connect((ip, port))
        except (socket.error, OSError):
            # If connection to cached IP fails, refresh IP and retry once
            ip = get_wsl_ip(force_refresh=True)
            try: wsl_sock.close()
            except Exception: pass
            wsl_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            wsl_sock.settimeout(5)
            wsl_sock.connect((ip, port))

        wsl_sock.settimeout(None)
        threading.Thread(target=forward, args=(client_sock, wsl_sock), daemon=True).start()
        threading.Thread(target=forward, args=(wsl_sock, client_sock), daemon=True).start()
    except Exception:
        if client_sock:
            try: client_sock.close()
            except Exception: pass
        if wsl_sock:
            try: wsl_sock.close()
            except Exception: pass

def main():
    port = 8000
    initial_ip = get_wsl_ip(force_refresh=True)
    print(f"Forwarding Windows localhost:{port} -> current WSL address {initial_ip}:{port}...", flush=True)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", port))
    server.listen(128)
    print(f"Listening on 0.0.0.0:{port} (accessible via http://localhost:{port})", flush=True)

    while True:
        try:
            client, addr = server.accept()
            threading.Thread(target=handle_client, args=(client, port), daemon=True).start()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print("Accept error:", e, flush=True)

if __name__ == "__main__":
    main()
