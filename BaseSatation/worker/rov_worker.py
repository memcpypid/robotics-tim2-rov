import os
import sys
from PySide6.QtCore import QObject, Signal, QTimer

# Tambahkan path root agar bisa mengimpor flightcontrolRov
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

try:
    from flightcontrolRov.main import ROVController
except ImportError as e:
    ROVController = None

from .lan_client import LANClientWorker


class ROVWorker(QObject):
    """
    Background Worker untuk menangani komunikasi MAVLink dengan ROVController (mode lokal)
    maupun dengan LAN Bridge Server di Jetson Nano (mode LAN JSON-UDP).
    """
    sig_log = Signal(str, str)          # (message, level)
    sig_connected = Signal(bool)        # True jika sukses connect, False jika terputus
    sig_state_updated = Signal(object)  # ROVState object

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rov = None
        self.lan_client: Optional[LANClientWorker] = None
        self._timer = QTimer(self)
        self._timer.setInterval(100)  # 10 Hz telemetry polling
        self._timer.timeout.connect(self._poll_telemetry)

    def connect_rov(self, connection_str: str, baudrate: int):
        # 1. Mode LAN / WiFi (IP Address langsung, contoh: 192.168.2.2 atau lan:192.168.2.2)
        # Jika bukan prefix udp: / dev/, maka dianggap sebagai alamat IP Jetson Nano (LAN/WiFi UDP)
        if connection_str.lower().startswith("lan:") or not (connection_str.lower().startswith("udp:") or connection_str.startswith("/dev/")):
            if connection_str.lower().startswith("lan:"):
                raw_ip = connection_str.split(":", 1)[1].split(" ")[0].strip()
            else:
                raw_ip = connection_str.split(" ")[0].strip()
                
            if not self.lan_client:
                self.lan_client = LANClientWorker(self)
                self.lan_client.sig_log.connect(self.sig_log)
                self.lan_client.sig_connected.connect(self.sig_connected)
                self.lan_client.sig_state_updated.connect(self.sig_state_updated)
            
            self.lan_client.connect_lan(rov_ip=raw_ip, telemetry_port=9000, command_port=9001)
            return

        # 2. Jika memilih mode Direct MAVLink lokal (contoh: udp:127.0.0.1:14550 atau /dev/ttyACM0)
        if ROVController is None:
            self.sig_log.emit("Gagal mengimpor ROVController dari flightcontrolRov! Pastikan struktur folder benar.", "ERROR")
            self.sig_connected.emit(False)
            return

        self.sig_log.emit(f"Mencoba terhubung ke ROV melalui {connection_str} (Baud: {baudrate})...", "INFO")
        try:
            self.rov = ROVController(connection_str=connection_str, baudrate=baudrate)
            if self.rov.connect(timeout=8.0):
                self.sig_log.emit(f"Koneksi berhasil terhubung ke {connection_str}!", "SUCCESS")
                self.sig_connected.emit(True)
                self._timer.start()
            else:
                self.sig_log.emit(f"Gagal terhubung ke {connection_str} (Timeout). Pastikan ROV / SITL aktif.", "ERROR")
                self.sig_connected.emit(False)
        except Exception as e:
            self.sig_log.emit(f"Error saat membuka koneksi: {str(e)}", "ERROR")
            self.sig_connected.emit(False)

    def disconnect_rov(self):
        self._timer.stop()
        if self.lan_client:
            self.lan_client.disconnect_lan()
        if self.rov:
            try:
                self.rov.disconnect()
            except Exception as e:
                self.sig_log.emit(f"Warning saat menutup koneksi: {str(e)}", "WARN")
            self.rov = None
        self.sig_log.emit("Koneksi ke ROV telah ditutup.", "INFO")
        self.sig_connected.emit(False)

    def set_armed(self, arm: bool):
        if self.lan_client and self.lan_client._running:
            self.lan_client.set_armed(arm)
            return

        if not self.rov or not self.rov.is_connected():
            self.sig_log.emit("Perintah Arm/Disarm gagal: ROV belum terhubung!", "WARN")
            return
        
        try:
            if arm:
                success = self.rov.arm()
                if success:
                    self.sig_log.emit("Perintah ARM berhasil dikirim ke ROV.", "SUCCESS")
                else:
                    self.sig_log.emit("ROV menolak perintah ARM (cek safety/sensor calibrasi).", "WARN")
            else:
                success = self.rov.disarm()
                if success:
                    self.sig_log.emit("Perintah DISARM berhasil dikirim ke ROV.", "INFO")
                else:
                    self.sig_log.emit("Gagal mengirim perintah DISARM.", "ERROR")
        except Exception as e:
            self.sig_log.emit(f"Error saat eksekusi Arm/Disarm: {str(e)}", "ERROR")

    def set_mode(self, mode_name: str):
        if self.lan_client and self.lan_client._running:
            self.lan_client.set_mode(mode_name)
            return

        if not self.rov or not self.rov.is_connected():
            self.sig_log.emit(f"Perintah mode {mode_name} gagal: ROV belum terhubung!", "WARN")
            return
        
        try:
            success = self.rov.set_mode(mode_name)
            if success:
                self.sig_log.emit(f"Mode flight diubah ke: {mode_name}", "SUCCESS")
            else:
                self.sig_log.emit(f"Gagal mengubah mode flight ke {mode_name}.", "WARN")
        except Exception as e:
            self.sig_log.emit(f"Error saat mengubah mode: {str(e)}", "ERROR")

    def send_manual_control(self, x: int, y: int, z: int, r: int, buttons: int = 0):
        if self.lan_client and self.lan_client._running:
            self.lan_client.send_manual_control(x, y, z, r, buttons)
            return

        if self.rov and self.rov.is_connected():
            try:
                self.rov.move(x, y, z, r, buttons)
            except Exception:
                pass

    def _poll_telemetry(self):
        if self.rov and self.rov.is_connected():
            try:
                state = self.rov.get_state()
                if state:
                    self.sig_state_updated.emit(state)
            except Exception as e:
                self.sig_log.emit(f"Error polling telemetri: {str(e)}", "DEBUG")
