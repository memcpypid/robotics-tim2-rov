"""
Main Entrypoint untuk Flight Control ROV (Base Station -> Pixhawk ArduSub).

Penggunaan sebagai library/modul di script lain:
--------------------------------------------------
from flightcontrolRov.main import ROVController

rov = ROVController("udp:127.0.0.1:14550")
if rov.connect():
    print(rov.get_state())
    rov.set_mode("MANUAL")
    rov.arm()
    rov.move(x=200, y=0, z=500, r=0) # Maju sedikit
    rov.disconnect()

Penggunaan langsung via terminal:
--------------------------------------------------
python -m flightcontrolRov.main --connect udp:127.0.0.1:14550
atau
python main.py --connect /dev/ttyACM0
"""
import time
import argparse
from typing import Optional

from models.state import ROVState, StateManager
from connection.mav_client import MAVClient
from connection.lan_server import ROVLANServer
from sensor.telemetry import ROVTelemetrySensor
from control.arming import ROVArmingControl
from control.modes import ROVModeControl
from control.motion import ROVMotionControl


class ROVController:
    """
    Kelas utama (Facade) yang menggabungkan seluruh fungsionalitas koneksi,
    pembacaan sensor telemetri, dan kontrol gerak/mode ROV dalam satu antarmuka yang clean & simpel.
    """
    def __init__(self, connection_str: str = "udp:127.0.0.1:14550", baudrate: int = 115200):
        # 1. Inisialisasi Koneksi & Dispatcher
        self.client = MAVClient(connection_str=connection_str, baudrate=baudrate)
        self.lan_server: Optional[ROVLANServer] = None
        
        # 2. Inisialisasi Sensor & State Store
        self.state_mgr = StateManager.get_instance()
        self.telemetry = ROVTelemetrySensor(self.client.dispatcher)
        
        # 3. Inisialisasi Kontrol
        self.arming = ROVArmingControl(self.client)
        self.modes = ROVModeControl(self.client)
        self.motion = ROVMotionControl(self.client)

    def start_lan_server(self, client_ip: str = "127.0.0.1", telemetry_port: int = 9000, command_port: int = 9001):
        """Memulai LAN Bridge Server untuk streaming data & menerima perintah dari GUI Base Station."""
        if not self.lan_server:
            self.lan_server = ROVLANServer(self, client_ip=client_ip, telemetry_port=telemetry_port, command_port=command_port)
        self.lan_server.start()

    def stop_lan_server(self):
        """Menghentikan LAN Bridge Server."""
        if self.lan_server:
            self.lan_server.stop()

    def connect(self, timeout: float = 15.0) -> bool:
        """Membuka koneksi ke Pixhawk ROV."""
        return self.client.connect(timeout=timeout)

    def disconnect(self):
        """Menutup koneksi ROV dan melepaskan kendali."""
        self.stop_lan_server()
        self.client.disconnect()

    def is_connected(self) -> bool:
        return self.client.is_connected()

    def get_state(self) -> ROVState:
        """Mendapatkan state/status sensor terkini dari ROV."""
        return self.state_mgr.get_state()

    def arm(self, force: bool = False) -> bool:
        """Mengaktifkan motor thruster ROV (Arming)."""
        return self.arming.arm(force=force)

    def disarm(self) -> bool:
        """Mematikan motor thruster ROV (Disarming)."""
        return self.arming.disarm()

    def set_mode(self, mode_name: str) -> bool:
        """Mengubah mode flight ROV ('MANUAL', 'STABILIZE', 'DEPTH_HOLD', 'AUTO')."""
        return self.modes.set_mode(mode_name)

    def move(self, x: int = 0, y: int = 0, z: int = 500, r: int = 0, buttons: int = 0) -> bool:
        """
        Mengendalikan thruster 6-DOF ROV dengan joystick/setpoint.
        x: Maju/Mundur (-1000 s/d 1000)
        y: Geser Kiri/Kanan (-1000 s/d 1000)
        z: Naik/Turun Kedalaman (0 s/d 1000, 500 netral)
        r: Putar Yaw (-1000 s/d 1000)
        """
        return self.motion.send_manual_control(x, y, z, r, buttons)

    def set_rc_channels(self, channels_pwm: list) -> bool:
        """Mengirim override PWM manual ke motor/aktuator ROV (1000-2000)."""
        return self.motion.send_rc_override(channels_pwm)


def _main_test_cli():
    parser = argparse.ArgumentParser(description="Basic ROV Flight Control Controller (ArduSub)")
    parser.add_argument("--connect", default="/dev/ttyACM0", help="String koneksi MAVLink (contoh: /dev/ttyACM0 atau udp:127.0.0.1:14550)")
    parser.add_argument("--baud", type=int, default=9600, help="Baudrate serial")
    parser.add_argument("--lan", action="store_true", help="Aktifkan LAN Bridge Server (JSON over UDP) dengan Auto-Discovery")
    parser.add_argument("--client-ip", default="AUTO", help="IP tujuan Base Station GUI (default: AUTO untuk auto-discovery)")
    args = parser.parse_args()

    rov = ROVController(connection_str=args.connect, baudrate=args.baud)
    
    print("=====================================================")
    print("  BASE STATION ROV - BASIC CONTROLLER INTERFACE      ")
    print("=====================================================")
    if not rov.connect(timeout=10.0):
        print("\n[INFO] Tidak dapat terhubung ke Pixhawk.")
        print("[INFO] Pastikan Flight Controller aktif / tercolok ke port serial atau SITL sedang berjalan.")
        return

    if args.lan:
        rov.start_lan_server(client_ip=args.client_ip, telemetry_port=9000, command_port=9001)

    try:
        print("\n[SUCCESS] ROV Terhubung! Memulai pemantauan sensor realtime (tekan Ctrl+C untuk keluar)...\n")
        while True:
            state = rov.get_state()
            print(f"\r[STATUS ROV] Mode: {state.mode:<10} | Armed: {str(state.armed):<5} | Roll: {state.roll:6.1f}° | Pitch: {state.pitch:6.1f}° | Yaw: {state.yaw:6.1f}° | Kedalaman: {state.depth_m:5.2f} m | Baterai: {state.battery_voltage:4.1f} V ({state.battery_percent:3}%)", end="", flush=True)
            # time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n\n[INFO] Dihentikan oleh pengguna. Menutup koneksi...")
    finally:
        rov.disconnect()


if __name__ == "__main__":
    _main_test_cli()
