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
    def __init__(self, rov_controller, client_ip: str = "127.0.0.1", telemetry_port: int = 9000, command_port: int = 9001):
        self.rov = rov_controller
        # Selalu gunakan IP langsung (direct unicast), BUKAN broadcast
        self.client_ip = client_ip if client_ip and client_ip.upper() != "AUTO" else "127.0.0.1"
        self.telemetry_port = telemetry_port
        self.command_port = command_port

        self.state_mgr = StateManager.get_instance()
        
        # Socket UDP standar (unicast langsung ke IP tujuan, bukan broadcast)
        self._telemetry_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._telemetry_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
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
        print(f"[LANServer] Telemetry Stream -> {self.client_ip}:{self.telemetry_port} (20 Hz, Direct UDP)")
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
        """Loop pengirim telemetri 20Hz ke IP Base Station secara langsung (direct unicast)."""
        last_debug = 0
        while self._running:
            try:
                if self.client_ip and self.client_ip.upper() != "AUTO":
                    state_dict = self.state_mgr.to_dict()
                    packet = {
                        "type": "TELEMETRY",
                        "timestamp": time.time(),
                        "data": state_dict
                    }
                    payload = json.dumps(packet).encode("utf-8")
                    self._telemetry_sock.sendto(payload, (self.client_ip, self.telemetry_port))
                    
                    # Print debug setiap 2 detik
                    if time.time() - last_debug > 2.0:
                        last_debug = time.time()
                        print(f"[LANServer DEBUG] Mengirim telemetri ke {self.client_ip}:{self.telemetry_port} | R: {state_dict.get('roll', 0):.1f}° P: {state_dict.get('pitch', 0):.1f}° Y: {state_dict.get('yaw', 0):.1f}°")
            except Exception as e:
                if time.time() - last_debug > 2.0:
                    last_debug = time.time()
                    print(f"[LANServer ERROR] Gagal mengirim telemetri UDP ke {self.client_ip}:{self.telemetry_port}: {e}")
            
            time.sleep(0.02)  # 20 Hz

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
        # print(f"[LANServer] Perintah diterima dari GUI: {cmd}")

        if cmd in ["PING", "PING_STREAM"]:
            return {"status": "OK", "cmd": "PONG", "timestamp": time.time()}

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

            elif cmd == "SET_AUTO":
                print("[LANServer] Mengaktifkan Mode AUTONOMOUS (Vision Controlled)")
                # Ubah mode FC ke GUIDED atau STABILIZE (dengan penguncian input manual)
                success = self.rov.set_mode("GUIDED") or self.rov.set_mode("STABILIZE")
                return {"status": "OK" if success else "ERROR", "cmd": "SET_AUTO", "success": success}
                
            elif cmd == "TOGGLE_LIGHTS":
                if hasattr(self.rov, 'toggle_lights'):
                    self.rov.toggle_lights()
                    return {"status": "OK", "cmd": "TOGGLE_LIGHTS"}
                return {"status": "ERROR", "message": "Fungsi toggle_lights tidak tersedia di ROVController"}

            elif cmd == "SET_MANUAL":
                print("[LANServer] Mengembalikan Mode ke MANUAL JOYSTICK")
                success = self.rov.set_mode("STABILIZE") or self.rov.set_mode("MANUAL")
                return {"status": "OK" if success else "ERROR", "cmd": "SET_MANUAL", "success": success}


            elif cmd == "MOVE":
                x = int(cmd_json.get("x", 0))
                y = int(cmd_json.get("y", 0))
                z = int(cmd_json.get("z", 500))
                r = int(cmd_json.get("r", 0))
                buttons = int(cmd_json.get("buttons", 0))
                
                success = self.rov.move(x, y, z, r, buttons)
                return {"status": "OK" if success else "ERROR", "cmd": "MOVE", "success": success}

            elif cmd == "DIVE":
                # Menyelam atau naik.
                # depth_rate: -1000 = naik penuh, 0 = hover, +1000 = turun/menyelam penuh
                depth_rate = int(cmd_json.get("depth_rate", 0))
                success = self.rov.dive(depth_rate)
                return {"status": "OK" if success else "ERROR", "cmd": "DIVE",
                        "depth_rate": depth_rate, "success": success}

            elif cmd == "STOP":
                # Hentikan semua gerak (hover di tempat)
                success = self.rov.stop()
                return {"status": "OK" if success else "ERROR", "cmd": "STOP", "success": success}

            elif cmd == "MOTOR_TEST":
                channel = int(cmd_json.get("channel", 0))
                thrust = float(cmd_json.get("thrust", 0.0))
                success = False
                return {"status": "OK" if success else "ERROR", "cmd": "MOTOR_TEST", "success": success}

            elif cmd == "SET_SERVO":
                pin = int(cmd_json.get("pin", 9))
                pwm = int(cmd_json.get("pwm", 1500))
                success = self.rov.set_servo(pin, pwm)
                return {"status": "OK" if success else "ERROR", "cmd": "SET_SERVO", "pin": pin, "pwm": pwm, "success": success}

            else:
                return {"status": "ERROR", "message": f"Perintah tidak dikenali: {cmd}"}

        except Exception as e:
            return {"status": "ERROR", "message": str(e)}
