import socket
import json
import threading
import time
from typing import Optional, Dict, Any

from models.state import StateManager


class ROVLANServer:
    """
    Protocol Bridge Server (JSON over UDP/TCP) untuk menghubungkan ROVController
    di Jetson Nano dengan Base Station GUI di Laptop melalui jaringan LAN / Ethernet.
    
    Arsitektur:
    1. Telemetry UDP Streamer (Port 9000): Mengirim data sensor ROVState secara realtime (20Hz)
       ke IP Base Station (atau Broadcast LAN).
    2. Command Receiver (Port 9001): Menerima perintah kontrol (ARM, DISARM, SET_MODE, MOVE)
       dari GUI Base Station dalam format JSON dan mengeksekusinya di ROVController.
    """
    def __init__(self, rov_controller, client_ip: Optional[str] = "AUTO", telemetry_port: int = 9000, command_port: int = 9001):
        self.rov = rov_controller
        self.client_ip = "AUTO" if not client_ip or client_ip.upper() == "AUTO" else client_ip
        self.telemetry_port = telemetry_port
        self.command_port = command_port

        self.state_mgr = StateManager.get_instance()
        
        # Sockets
        self._telemetry_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._telemetry_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        self._cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._cmd_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        self._running = False
        self._telemetry_thread: Optional[threading.Thread] = None
        self._command_thread: Optional[threading.Thread] = None

    def start(self):
        """Memulai streaming telemetri dan mendengarkan perintah kontrol."""
        if self._running:
            return
            
        self._running = True
        print(f"[LANServer] Memulai layanan LAN Bridge...")
        if self.client_ip == "AUTO":
            print(f"[LANServer] Telemetry Stream -> [AUTO-DISCOVERY] Menunggu paket PING/koneksi pertama dari Base Station...")
        else:
            print(f"[LANServer] Telemetry Stream -> {self.client_ip}:{self.telemetry_port} (20 Hz)")
        print(f"[LANServer] Command Listener binding pada port {self.command_port}")

        # Bind Command Socket
        try:
            self._cmd_sock.bind(("0.0.0.0", self.command_port))
        except Exception as e:
            print(f"[LANServer ERROR] Gagal bind port command {self.command_port}: {e}")
            return

        # Start background threads
        self._telemetry_thread = threading.Thread(target=self._telemetry_loop, name="LANTelemetryLoop", daemon=True)
        self._command_thread = threading.Thread(target=self._command_loop, name="LANCommandLoop", daemon=True)

        self._telemetry_thread.start()
        self._command_thread.start()
        print("[LANServer] LAN Bridge Server Aktif!")

    def stop(self):
        """Menghentikan layanan LAN Bridge."""
        print("[LANServer] Menghentikan LAN Bridge...")
        self._running = False
        if self._cmd_sock:
            try:
                self._cmd_sock.close()
            except Exception:
                pass
        if self._telemetry_sock:
            try:
                self._telemetry_sock.close()
            except Exception:
                pass

    def set_client_ip(self, ip: str):
        """Mengubah IP tujuan Base Station secara dinamis saat terdeteksi perintah/PING dari IP baru."""
        if self.client_ip != ip:
            self.client_ip = ip
            print(f"[LANServer AUTO-DISCOVERY] IP Base Station terdeteksi! Mengalihkan stream telemetri ke: {ip}:{self.telemetry_port}")

    def _telemetry_loop(self):
        """Loop pengirim telemetri 20Hz (setiap 50ms)."""
        while self._running:
            try:
                if self.client_ip != "AUTO" and self.client_ip is not None:
                    state_dict = self.state_mgr.to_dict()
                    packet = {
                        "type": "TELEMETRY",
                        "timestamp": time.time(),
                        "data": state_dict
                    }
                    payload = json.dumps(packet).encode("utf-8")
                    self._telemetry_sock.sendto(payload, (self.client_ip, self.telemetry_port))
            except Exception as e:
                pass
            
            time.sleep(0.05)  # 20 Hz

    def _command_loop(self):
        """Loop penerima perintah kontrol dari GUI Base Station."""
        while self._running:
            try:
                data, addr = self._cmd_sock.recvfrom(4096)
                client_ip = addr[0]
                # Otomatis catat IP pengirim sebagai target stream telemetri jika berubah
                self.set_client_ip(client_ip)

                cmd_json = json.loads(data.decode("utf-8"))
                response = self._handle_command(cmd_json)

                # Kirim balik respons/ack ke GUI
                resp_payload = json.dumps(response).encode("utf-8")
                self._cmd_sock.sendto(resp_payload, addr)

            except OSError:
                break  # Socket ditutup saat stop()
            except json.JSONDecodeError:
                print("[LANServer WARNING] Menerima paket tidak valid (bukan JSON)")
            except Exception as e:
                if self._running:
                    print(f"[LANServer ERROR] Command processing error: {e}")

    def _handle_command(self, cmd_json: Dict[str, Any]) -> Dict[str, Any]:
        """Memproses perintah JSON dan memanggil fungsi di ROVController."""
        cmd = cmd_json.get("cmd", "").upper()
        print(f"[LANServer] Perintah diterima dari GUI: {cmd}")

        if not self.rov or not self.rov.is_connected():
            return {"status": "ERROR", "message": "ROV belum terhubung ke Pixhawk flight controller!"}

        try:
            if cmd == "ARM":
                force = cmd_json.get("force", False)
                success = self.rov.arm(force=force)
                return {"status": "OK" if success else "ERROR", "cmd": "ARM", "success": success}

            elif cmd == "DISARM":
                success = self.rov.disarm()
                return {"status": "OK" if success else "ERROR", "cmd": "DISARM", "success": success}

            elif cmd == "SET_MODE":
                mode_name = cmd_json.get("mode", "MANUAL")
                success = self.rov.set_mode(mode_name)
                return {"status": "OK" if success else "ERROR", "cmd": "SET_MODE", "mode": mode_name, "success": success}

            elif cmd == "MOVE":
                x = int(cmd_json.get("x", 0))
                y = int(cmd_json.get("y", 0))
                z = int(cmd_json.get("z", 500))
                r = int(cmd_json.get("r", 0))
                buttons = int(cmd_json.get("buttons", 0))
                success = self.rov.move(x, y, z, r, buttons)
                return {"status": "OK" if success else "ERROR", "cmd": "MOVE", "success": success}

            elif cmd == "PING":
                return {"status": "OK", "cmd": "PONG", "timestamp": time.time()}

            else:
                return {"status": "ERROR", "message": f"Perintah tidak dikenali: {cmd}"}

        except Exception as e:
            return {"status": "ERROR", "message": str(e)}
