import socket
import json
import time

jetson_ip = "192.168.1.11"
cmd_port = 9001
telemetry_port = 9000

print(f"Testing UDP Ping to {jetson_ip}:{cmd_port}...")

# Buat socket sender
sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
payload = json.dumps({"cmd": "PING"}).encode('utf-8')

print("Mengirim paket PING...")
sock_send.sendto(payload, (jetson_ip, cmd_port))

try:
    print("Menunggu balasan PONG dari port command...")
    sock_send.settimeout(3.0)
    data, addr = sock_send.recvfrom(4096)
    print(f"BERHASIL! DITERIMA DARI {addr}: {data.decode('utf-8')}")
except socket.timeout:
    print("TIMEOUT: Tidak ada balasan PONG dari port command 9001 Jetson!")
except Exception as e:
    print(f"ERROR: {e}")

sock_send.close()
