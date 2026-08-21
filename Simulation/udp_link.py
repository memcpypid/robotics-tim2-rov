import socket
import json
import threading
import time

class UDPLink:
    """
    Meniru lan_server.py yang berjalan di Jetson Nano.
    Simulator ini bertindak sebagai "Server" yang mendengarkan perintah dari Base Station.
    """
    def __init__(self, command_port=9001, telemetry_port=9000):
        self.command_port = command_port
        self.telemetry_port = telemetry_port
        self.client_ip = None  # Akan di-set otomatis saat ada paket masuk

        # Socket penerima perintah (Command)
        self.cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.cmd_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.cmd_sock.bind(("0.0.0.0", self.command_port))
        # Set non-blocking agar tidak hang
        self.cmd_sock.settimeout(0.01) 

        # Socket pengirim telemetri (Telemetry)
        self.telemetry_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.telemetry_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Variabel kontrol (x, y, z, r)
        self.cmd_x = 0
        self.cmd_y = 0
        self.cmd_z = 500  # Nilai tengah/netral untuk z
        self.cmd_r = 0

    def update(self):
        """Dipanggil setiap frame di Ursina (60 FPS) untuk membaca antrean paket."""
        try:
            # Baca semua paket di buffer
            while True:
                data, addr = self.cmd_sock.recvfrom(4096)
                self.client_ip = addr[0]  # Tangkap IP Base Station
                
                try:
                    packet = json.loads(data.decode("utf-8"))
                    cmd = packet.get("cmd", "").upper()
                    
                    if cmd == "MOVE":
                        self.cmd_x = packet.get("x", 0)
                        self.cmd_y = packet.get("y", 0)
                        self.cmd_z = packet.get("z", 0)
                        self.cmd_r = packet.get("r", 0)
                        
                        # Kirim ACK
                        resp = {"status": "OK", "cmd": "MOVE", "success": True}
                        self.cmd_sock.sendto(json.dumps(resp).encode(), addr)
                        
                except json.JSONDecodeError:
                    pass
        except socket.timeout:
            pass # Tidak ada data, biarkan saja
        except Exception as e:
            pass

    def send_telemetry(self, pos_x, pos_y, pos_z, pitch, roll, yaw):
        """Mengirimkan posisi terkini kembali ke Base Station (20Hz biasanya)."""
        if not self.client_ip:
            return # Belum ada Base Station yang terhubung
            
        state_dict = {
            "pos_x": pos_x,
            "pos_y": pos_y,
            "pos_z": pos_z,
            "pitch": pitch,
            "roll": roll,
            "yaw": yaw,
            "depth": pos_z,
            "mode": "MANUAL",
            "armed": True
        }
        
        packet = {
            "type": "TELEMETRY",
            "timestamp": time.time(),
            "data": state_dict
        }
        
        try:
            payload = json.dumps(packet).encode("utf-8")
            self.telemetry_sock.sendto(payload, (self.client_ip, self.telemetry_port))
        except Exception as e:
            pass

