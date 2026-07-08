"""
MAVClient untuk mengelola koneksi fisik (Serial/UDP/TCP) ke Pixhawk (ArduSub/ROV).
Menyediakan loop pembacaan background thread-safe dan pengiriman perintah MAVLink.
"""
import time
import threading
from typing import Optional
from pymavlink import mavutil
from .dispatcher import MessageDispatcher

class MAVClient:
    def __init__(self, connection_str: str = "udp:127.0.0.1:14550", baudrate: int = 115200):
        """
        Inisialisasi MAVClient.
        :param connection_str: String koneksi MAVLink (contoh: '/dev/ttyACM0' atau 'udp:127.0.0.1:14550')
        :param baudrate: Baud rate jika menggunakan koneksi serial USB/UART (default: 115200)
        """
        self.connection_str = connection_str
        self.baudrate = baudrate
        self.master: Optional[mavutil.mavlink_connection] = None
        self.dispatcher = MessageDispatcher()
        
        self._running = False
        self._read_thread: Optional[threading.Thread] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()  # Mutex lock untuk pengiriman data (write lock)

    def connect(self, timeout: float = 15.0) -> bool:
        """
        Membuka koneksi ke Pixhawk dan menunggu detak jantung (heartbeat) pertama.
        """
        print(f"[MAVClient] Membuka koneksi ke {self.connection_str} (Baud: {self.baudrate})...")
        try:
            self.master = mavutil.mavlink_connection(self.connection_str, baud=self.baudrate)
        except Exception as e:
            print(f"[MAVClient Error] Gagal membuka port koneksi: {e}")
            return False

        print(f"[MAVClient] Menunggu heartbeat dari Flight Controller (Timeout: {timeout}s)...")
        start_time = time.time()
        heartbeat = None
        while time.time() - start_time < timeout:
            heartbeat = self.master.wait_heartbeat(timeout=1.0)
            if heartbeat is not None:
                break

        if not heartbeat:
            print("[MAVClient Error] Timeout! Tidak menerima heartbeat dari Pixhawk.")
            return False

        print(f"[MAVClient] Berhasil Terhubung! Target System ID: {self.master.target_system}, Component ID: {self.master.target_component}")

        self._running = True
        
        # Mulai loop pembaca pesan (background thread)
        self._read_thread = threading.Thread(target=self._listen_loop, name="MAVReadLoop", daemon=True)
        self._read_thread.start()

        # Minta stream telemetri secara terus menerus (misal 10Hz)
        self.request_data_stream(rate_hz=10)

        # Mulai thread penghantar heartbeat (keep-alive) dari base station ke ROV
        self._heartbeat_thread = threading.Thread(target=self._send_heartbeat_loop, name="MAVHeartbeatLoop", daemon=True)
        self._heartbeat_thread.start()

        return True

    def disconnect(self):
        """Menutup koneksi MAVLink dan menghentikan loop background."""
        print("[MAVClient] Menutup koneksi...")
        self._running = False
        if self._read_thread and self._read_thread.is_alive():
            self._read_thread.join(timeout=1.5)
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=1.5)
        if self.master:
            try:
                self.master.close()
            except Exception:
                pass
            self.master = None
        print("[MAVClient] Koneksi ditutup.")

    def is_connected(self) -> bool:
        return self._running and self.master is not None

    def request_data_stream(self, rate_hz: int = 10):
        """
        Meminta Flight Controller mengirimkan seluruh stream data sensor (Attitude, GPS, Status, RC, dsb.)
        dengan frekuensi rate_hz (contoh: 10 Hz).
        """
        if not self.is_connected():
            return
        print(f"[MAVClient] Meminta data stream dari Pixhawk pada frekuensi {rate_hz} Hz...")
        with self._lock:
            try:
                self.master.mav.request_data_stream_send(
                    self.master.target_system,
                    self.master.target_component,
                    mavutil.mavlink.MAV_DATA_STREAM_ALL,
                    rate_hz,
                    1  # 1 = Start stream
                )
            except Exception as e:
                print(f"[MAVClient Error] Gagal meminta data stream: {e}")

    def _listen_loop(self):
        """Loop internal untuk membaca pesan MAVLink yang masuk dan mendistribusikannya via dispatcher."""
        while self._running and self.master:
            try:
                msg = self.master.recv_match(blocking=True, timeout=0.5)
                if msg and msg.get_type() != 'BAD_DATA':
                    self.dispatcher.dispatch(msg)
            except Exception as e:
                if self._running:
                    print(f"[MAVClient Read Loop Error] {e}")
                time.sleep(0.1)

    def _send_heartbeat_loop(self):
        """Mengirimkan heartbeat periodik (setiap 1 detik) ke Pixhawk agar koneksi tetap terjaga."""
        while self._running and self.master:
            try:
                with self._lock:
                    self.master.mav.heartbeat_send(
                        mavutil.mavlink.MAV_TYPE_GCS,              # Tipe: Ground Control Station / Base Station
                        mavutil.mavlink.MAV_AUTOPILOT_INVALID,     # Autopilot: Invalid (karena kita adalah GCS)
                        0, 0, 0                                    # Base mode, custom mode, system status
                    )
            except Exception as e:
                if self._running:
                    print(f"[MAVClient Heartbeat Send Error] {e}")
            time.sleep(1.0)

    def send_command_long(self, command: int, param1=0, param2=0, param3=0, param4=0, param5=0, param6=0, param7=0):
        """
        Mengirimkan MAV_CMD (COMMAND_LONG) secara thread-safe ke Pixhawk.
        """
        if not self.is_connected():
            print("[MAVClient Warning] Tidak dapat mengirim perintah: ROV belum terhubung.")
            return False

        with self._lock:
            try:
                self.master.mav.command_long_send(
                    self.master.target_system,
                    self.master.target_component,
                    command,
                    0,  # Confirmation
                    float(param1), float(param2), float(param3), float(param4),
                    float(param5), float(param6), float(param7)
                )
                return True
            except Exception as e:
                print(f"[MAVClient Error] Gagal mengirim COMMAND_LONG {command}: {e}")
                return False
