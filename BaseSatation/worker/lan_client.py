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

from dataclasses import dataclass, field

try:
    from flightcontrolRov.models.state import ROVState
except ImportError:
    try:
        from models.state import ROVState
    except ImportError:
        @dataclass
        class ROVState:
            connected: bool = False
            armed: bool = False
            mode: str = "UNKNOWN"
            system_id: int = 0
            component_id: int = 0
            roll: float = 0.0
            pitch: float = 0.0
            yaw: float = 0.0
            depth_m: float = 0.0
            altitude_m: float = 0.0
            pressure_press_abs: float = 0.0
            water_temperature_c: float = 0.0
            pos_x: float = 0.0
            pos_y: float = 0.0
            pos_z: float = 0.0
            battery_voltage: float = 0.0
            battery_current: float = 0.0
            battery_percent: int = 0
            leak_detected: bool = False
            qr_last_code: str = ""
            qr_last_time: float = 0.0
            qr_last_cam: str = ""
            qr_last_image: str = ""
            ms5803_pressure: float = 0.0
            ms5803_temp: float = 0.0
            ms5803_depth: float = 0.0
            pwm_outputs: list = field(default_factory=list)


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
        self._lan_connected = False   # True hanya setelah connect_lan() berhasil dipanggil
        self._listen_thread: Optional[threading.Thread] = None
        self._last_packet_time = 0.0

    @property
    def is_lan_connected(self) -> bool:
        """True jika user sudah memanggil connect_lan() ke IP tertentu."""
        return self._lan_connected

    def start_receiver(self, telemetry_port: int = 9000):
        """Membuka socket UDP di port 9000 secara otomatis saat aplikasi berjalan untuk menerima QR & telemetri."""
        if self._running and self._telemetry_sock:
            return
        self.telemetry_port = telemetry_port
        try:
            self._telemetry_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Jangan gunakan SO_REUSEADDR agar jika ada zombie process yang memakai port 9000,
            # Windows langsung memberi tahu error 10048 (Address in use) bukannya membuang paket.
            self._telemetry_sock.bind(("0.0.0.0", self.telemetry_port))
            self._telemetry_sock.settimeout(1.0)

            self._cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._running = True
            self._listen_thread = threading.Thread(target=self._listen_telemetry_loop, name="LANClientListenLoop", daemon=True)
            self._listen_thread.start()
            self.sig_log.emit(f"[LAN Client] Auto-listening telemetri & QR live di port UDP {self.telemetry_port}", "INFO")
        except OSError as e:
            msg = f"[LAN Client ERROR] Port UDP {self.telemetry_port} gagal dibuka! Pastikan tidak ada aplikasi Python lain yang berjalan. Error: {e}"
            print(msg)
            self.sig_log.emit(msg, "ERROR")
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

            self._lan_connected = True
            self.sig_connected.emit(True)
            self.sig_log.emit(f"[LAN Client] Berhasil tersambung ke LAN Bridge & Camera Stream di {self.rov_ip}!", "SUCCESS")

        except Exception as e:
            self.sig_log.emit(f"[LAN Client ERROR] Gagal menghubungkan LAN: {e}", "ERROR")
            self._lan_connected = False
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
        self._lan_connected = False
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

    def set_auto_mode(self, is_auto: bool):
        cmd = "SET_AUTO" if is_auto else "SET_MANUAL"
        self.send_command({"cmd": cmd})

    def send_manual_control(self, x: int, y: int, z: int, r: int, buttons: int = 0):

        self.send_command({"cmd": "MOVE", "x": x, "y": y, "z": z, "r": r, "buttons": buttons})

    def send_motor_test(self, channel: int, thrust: float):
        self.send_command({"cmd": "MOTOR_TEST", "channel": channel, "thrust": thrust * 100.0})

    def send_set_servo(self, pin: int, pwm: int):
        self.send_command({"cmd": "SET_SERVO", "pin": pin, "pwm": pwm})

    def send_toggle_lights(self):
        self.send_command({"cmd": "TOGGLE_LIGHTS"})

    def send_shutdown(self):
        self.send_command({"cmd": "SHUTDOWN"})

    def send_depth_hold_toggle(self, active: bool):
        self.send_command({"cmd": "DEPTH_HOLD_TOGGLE", "active": active})

    def send_depth_hold_target(self, target: float):
        self.send_command({"cmd": "DEPTH_HOLD_TARGET", "target": target})

    def send_depth_hold_pid(self, kp: float, ki: float, kd: float):
        self.send_command({"cmd": "DEPTH_HOLD_PID", "kp": kp, "ki": ki, "kd": kd})

    def send_calibrate_ms5803(self):
        self.send_command({"cmd": "CALIBRATE_MS5803"})

    def _listen_telemetry_loop(self):
        """Mendengarkan paket telemetri JSON dari Jetson Nano / ROV Backend."""
        if not self._telemetry_sock:
            print("[LANClient DEBUG ERROR] _telemetry_sock is None!")
            return
        print(f"[LANClient DEBUG] _listen_telemetry_loop BERJALAN di port UDP {self.telemetry_port}...")
        self._telemetry_sock.settimeout(0.5)
        last_debug = 0
        while self._running:
            try:
                data, addr = self._telemetry_sock.recvfrom(65535)
                if data:
                    packet = json.loads(data.decode("utf-8"))
                    if packet.get("type") == "TELEMETRY" and "data" in packet:
                        self._last_packet_time = time.time()
                        state_dict = packet["data"]
                        state_obj = ROVState()
                        for k, v in state_dict.items():
                            if hasattr(state_obj, k):
                                setattr(state_obj, k, v)
                        self.sig_state_updated.emit(state_obj)
                        
                        if time.time() - last_debug > 2.0:
                            last_debug = time.time()
                            print(f"[LANClient DEBUG] Telemetri DITERIMA dari {addr} | R:{state_obj.roll:.1f}° P:{state_obj.pitch:.1f}° Y:{state_obj.yaw:.1f}°")
            except (socket.timeout, BlockingIOError):
                continue
            except Exception as e:
                if not self._running:
                    break
                print(f"[LANClient DEBUG ERROR] Exception in loop: {e}")
                time.sleep(0.05)
