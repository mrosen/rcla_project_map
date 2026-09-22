import socket
import subprocess
import threading
import re
import sys

def get_wsl_ip():
    try:
        out = subprocess.check_output(["wsl", "ip", "addr", "show", "eth0"], text=True)
        m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", out)
        if m:
            return m.group(1)
    except Exception as e:
        print("Error getting WSL IP:", e, flush=True)
    return "127.0.0.1"

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
        except: pass
        try: dst.close()
        except: pass

def handle_client(client_sock, wsl_ip, port):
    try:
        wsl_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        wsl_sock.connect((wsl_ip, port))
        threading.Thread(target=forward, args=(client_sock, wsl_sock), daemon=True).start()
        threading.Thread(target=forward, args=(wsl_sock, client_sock), daemon=True).start()
    except Exception:
        client_sock.close()

def main():
    port = 8000
    wsl_ip = get_wsl_ip()
    print(f"Forwarding Windows localhost:{port} -> WSL {wsl_ip}:{port}...", flush=True)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", port))
    server.listen(128)
    print(f"Listening on 0.0.0.0:{port} (accessible via http://localhost:{port})", flush=True)

    while True:
        try:
            client, addr = server.accept()
            threading.Thread(target=handle_client, args=(client, wsl_ip, port), daemon=True).start()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print("Accept error:", e, flush=True)

if __name__ == "__main__":
    main()
