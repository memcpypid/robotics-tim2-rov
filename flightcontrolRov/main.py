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
import logging
from typing import Optional

try:
    import Jetson.GPIO as GPIO
    GPIO_AVAILABLE = True
    print("[GPIO] Jetson.GPIO library loaded.")
except ImportError:
    GPIO_AVAILABLE = False
    print("[GPIO] Jetson.GPIO library NOT found. GPIO features disabled.")

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

        # 4. Inisialisasi GPIO untuk aksesoris (Relay Lampu)
        self.light_pin = 5
        self.light_state = False
        if GPIO_AVAILABLE:
            try:
                # Suppress mode warnings to avoid terminal spam if already set
                GPIO.setwarnings(False)
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(self.light_pin, GPIO.OUT)
                GPIO.output(self.light_pin, GPIO.LOW)
            except Exception as e:
                print(f"[GPIO ERROR] Gagal setup pin {self.light_pin}: {e}")

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
        Mengendalikan thruster 6-DOF ROV dengan joystick/setpoint via MANUAL_CONTROL MAVLink.
        TIDAK melakukan RC_CHANNELS_OVERRIDE — nilai dikontrol penuh oleh mixer ArduSub.

        x: Maju/Mundur (-1000 s/d 1000)
        y: Geser Kiri/Kanan (-1000 s/d 1000)
        z: Naik/Turun Kedalaman (0 s/d 1000, 500 netral/hover)
        r: Putar Yaw (-1000 s/d 1000)
        """
        return self.motion.send_manual_control(x, y, z, r, buttons)

    def dive(self, depth_rate: int = 0) -> bool:
        """
        Perintah menyelam / naik yang mudah digunakan.
        depth_rate: -1000 = naik penuh, 0 = hover/diam, +1000 = turun/menyelam penuh
        """
        return self.motion.dive(depth_rate)

    def stop(self) -> bool:
        """Menghentikan semua gerak ROV (hover di tempat)."""
        return self.motion.stop()

    def set_servo(self, pin: int, pwm: int) -> bool:
        """Menggerakkan servo spesifik (misalnya Gripper di pin 9)."""
        return self.motion.set_servo(pin, pwm)

    def set_rc_channels(self, channels_pwm: list) -> bool:
        """Mengirim override PWM manual ke motor/aktuator ROV (1000-2000)."""
        return self.motion.send_rc_override(channels_pwm)

    def toggle_lights(self):
        """Menyala-matikan lampu lewat modul relay (GPIO 05) dan Pixhawk Relay 0"""
        self.light_state = not self.light_state
        
        # 1. Coba trigger Pixhawk Relay 0 via MAVLink (Default ArduSub)
        success_mavlink = False
        try:
            success_mavlink = self.motion.set_relay(0, self.light_state)
            if success_mavlink:
                print(f"[ROVController] Lampu {'MENYALA' if self.light_state else 'MATI'} (Pixhawk Relay 0).")
        except Exception as e:
            print(f"[ROVController] ERROR Toggle Pixhawk Relay: {e}")
            
        # 2. Coba trigger Jetson GPIO (jika tersedia dan dijalankan di Jetson)
        if GPIO_AVAILABLE:
            try:
                state = GPIO.HIGH if self.light_state else GPIO.LOW
                GPIO.output(self.light_pin, state)
                print(f"[ROVController] Lampu {'MENYALA' if self.light_state else 'MATI'} (Jetson GPIO {self.light_pin}).")
            except Exception as e:
                print(f"[ROVController] ERROR Toggle Lampu GPIO: {e}")
        else:
            if not success_mavlink:
                print(f"[ROVController - SIMULATION] Lampu {'MENYALA' if self.light_state else 'MATI'} (GPIO tidak tersedia, MAVLink gagal).")


def _main_test_cli():
    parser = argparse.ArgumentParser(description="Basic ROV Flight Control Controller (ArduSub)")
    parser.add_argument("--connect", default="/dev/ttyACM0", help="String koneksi MAVLink (contoh: /dev/ttyACM0 atau udp:127.0.0.1:14550)")
    parser.add_argument("--baud", type=int, default=115200, help="Baudrate serial (Cube Black default: 115200)")
    parser.add_argument("--lan", action="store_true", default=True, help="Aktifkan LAN Bridge Server (JSON over UDP)")
    parser.add_argument("--client-ip", default="127.0.0.1", help="IP tujuan Base Station GUI (default: 127.0.0.1 untuk localhost)")
    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

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
            # status = f"\r[STATUS ROV] Mode: {state.mode:<9} | Armed: {str(state.armed):<5} | R: {state.roll:5.1f}° P: {state.pitch:5.1f}° Y: {state.yaw:5.1f}°"
            # Padding untuk overwrite sisa karakter
            # print(status.ljust(120), end="", flush=True)
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n\n[INFO] Dihentikan oleh pengguna. Menutup koneksi...")
    finally:
        rov.disconnect()


if __name__ == "__main__":
    _main_test_cli()
