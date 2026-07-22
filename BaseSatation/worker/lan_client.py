import socket
import json
import threading
import time
from typing import Optional, Dict, Any
from PySide6.QtCore import QObject, Signal

import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

try:
    from flightcontrolRov.models.state import ROVState
except ImportError:
    ROVState = None


class LANClientWorker(QObject):
    """
    Klien GUI Base Station untuk menerima streaming telemetri JSON (UDP Port 9000)
    dan mengirim perintah kontrol JSON (UDP Port 9001) ke ROVLANServer di Jetson Nano/Backend.
    """
    sig_log = Signal(str, str)          # (message, level)
    sig_connected = Signal(bool)        # True jika terhubung, False jika terputus
    sig_state_updated = Signal(object)  # ROVState object

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rov_ip = "127.0.0.1"
        self.telemetry_port = 9000
        self.command_port = 9001
        
        self._telemetry_sock: Optional[socket.socket] = None
        self._cmd_sock: Optional[socket.socket] = None
        
        self._running = False
        self._listen_thread: Optional[threading.Thread] = None
        self._last_packet_time = 0.0

    def start_receiver(self, telemetry_port: int = 9000):
        """Membuka socket UDP di port 9000 secara otomatis saat aplikasi berjalan untuk menerima QR & telemetri."""
        if self._running and self._telemetry_sock:
            return
        self.telemetry_port = telemetry_port
        try:
            self._telemetry_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._telemetry_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._telemetry_sock.bind(("0.0.0.0", self.telemetry_port))
            self._telemetry_sock.settimeout(1.0)

            self._cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._running = True
            self._listen_thread = threading.Thread(target=self._listen_telemetry_loop, name="LANClientListenLoop", daemon=True)
            self._listen_thread.start()
            self.sig_log.emit(f"[LAN Client] Auto-listening telemetri & QR live di port UDP {self.telemetry_port}", "INFO")
        except Exception as e:
            self.sig_log.emit(f"[LAN Client ERROR] Gagal bind port UDP {self.telemetry_port}: {e}", "ERROR")

    def connect_lan(self, rov_ip: str = "127.0.0.1", telemetry_port: int = 9000, command_port: int = 9001):
        self.rov_ip = rov_ip
        self.telemetry_port = telemetry_port
        self.command_port = command_port

        self.sig_log.emit(f"[LAN Client] Menghubungkan target perintah ke {self.rov_ip}...", "INFO")

        try:
            if not self._running or not self._telemetry_sock:
                self.start_receiver(telemetry_port)

            # Kirim paket PING awal untuk registrasi IP kita di ROVLANServer (port 9001)
            self.send_command({"cmd": "PING"})
            
            # Kirim juga paket PING ke ImageProcessing (port 9005) agar stream kamera CAM 1, CAM 2, & QR langsung mengarah ke IP kita
            try:
                if self._cmd_sock:
                    ping_stream = json.dumps({"cmd": "PING_STREAM"}).encode("utf-8")
                    self._cmd_sock.sendto(ping_stream, (self.rov_ip, 9005))
            except Exception:
                pass

            # Mulai thread Heartbeat (auto-discovery pinger setiap 1.5 detik) agar Jetson selalu tahu IP Base Station
            if not hasattr(self, '_heartbeat_thread') or not self._heartbeat_thread or not self._heartbeat_thread.is_alive():
                self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, name="LANHeartbeatLoop", daemon=True)
                self._heartbeat_thread.start()

            self.sig_connected.emit(True)
            self.sig_log.emit(f"[LAN Client] Berhasil tersambung ke LAN Bridge & Camera Stream di {self.rov_ip}!", "SUCCESS")

        except Exception as e:
            self.sig_log.emit(f"[LAN Client ERROR] Gagal menghubungkan LAN: {e}", "ERROR")
            self.sig_connected.emit(False)

    def _heartbeat_loop(self):
        while self._running and hasattr(self, 'rov_ip') and self.rov_ip:
            try:
                self.send_command({"cmd": "PING"})
                if self._cmd_sock:
                    ping_stream = json.dumps({"cmd": "PING_STREAM"}).encode("utf-8")
                    self._cmd_sock.sendto(ping_stream, (self.rov_ip, 9005))
            except Exception:
                pass
            time.sleep(1.5)

    def disconnect_lan(self):
        self._running = False
        if self._telemetry_sock:
            try:
                self._telemetry_sock.close()
            except Exception:
                pass
        if self._cmd_sock:
            try:
                self._cmd_sock.close()
            except Exception:
                pass
        self.sig_log.emit("[LAN Client] Koneksi LAN diputus.", "INFO")
        self.sig_connected.emit(False)

    def send_command(self, payload: Dict[str, Any]) -> bool:
        """Mengirim perintah JSON ke ROVLANServer port 9001."""
        if not self._cmd_sock or not self._running:
            return False
        try:
            data = json.dumps(payload).encode("utf-8")
            self._cmd_sock.sendto(data, (self.rov_ip, self.command_port))
            return True
        except Exception as e:
            self.sig_log.emit(f"[LAN Client] Gagal mengirim perintah: {e}", "ERROR")
            return False

    def set_armed(self, arm: bool):
        cmd = "ARM" if arm else "DISARM"
        self.send_command({"cmd": cmd, "force": True})

    def set_mode(self, mode_name: str):
        self.send_command({"cmd": "SET_MODE", "mode": mode_name})

    def send_manual_control(self, x: int, y: int, z: int, r: int, buttons: int = 0):
        self.send_command({"cmd": "MOVE", "x": x, "y": y, "z": z, "r": r, "buttons": buttons})

    def _listen_telemetry_loop(self):
        """Mendengarkan paket telemetri JSON dari Jetson Nano."""
        while self._running:
            try:
                data, addr = self._telemetry_sock.recvfrom(65535)
                packet = json.loads(data.decode("utf-8"))
                if packet.get("type") == "TELEMETRY" and "data" in packet:
                    self._last_packet_time = time.time()
                    state_dict = packet["data"]
                    if ROVState:
                        state_obj = ROVState()
                        for k, v in state_dict.items():
                            if hasattr(state_obj, k):
                                setattr(state_obj, k, v)
                        self.sig_state_updated.emit(state_obj)
            except socket.timeout:
                # Cek jika tidak ada paket masuk selama > 3 detik
                if self._last_packet_time > 0 and (time.time() - self._last_packet_time > 3.0):
                    self.sig_log.emit("[LAN Client WARNING] Telemetri terputus (Timeout > 3s)!", "WARN")
                    self._last_packet_time = 0.0
            except json.JSONDecodeError:
                pass
            except OSError:
                break
            except Exception as e:
                if self._running:
                    print(f"[LANClient Error] {e}")
