import threading
from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class ROVState:
    """
    Data model yang merepresentasikan status terkini dari ROV (Remotely Operated Vehicle).
    Menyimpan pembacaan sensor dasar seperti sikap (attitude), kedalaman, baterai, dan status sistem.
    """
    # Status Sistem & Flight Controller
    connected: bool = False
    armed: bool = False
    mode: str = "UNKNOWN"
    system_id: int = 0
    component_id: int = 0

    # Orientasi / Sikap (Attitude dalam derajat)
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0

    # Sensor Kedalaman & Tekanan Air (Khusus ROV / ArduSub)
    depth_m: float = 0.0             # Kedalaman air dari permukaan dalam meter
    altitude_m: float = 0.0          # Ketinggian ROV dari dasar kolam / laut (Acoustic Altimeter / Bottom Proximity)
    pressure_press_abs: float = 0.0  # Tekanan absolut sensor (mbar/hPa)
    water_temperature_c: float = 0.0 # Suhu air dalam Celcius

    # Sensor Eksternal I2C Jetson (GY-MS5803-01BA)
    ms5803_pressure: float = 0.0     # Tekanan dari I2C MS5803 (mbar)
    ms5803_temp: float = 0.0         # Suhu dari I2C MS5803 (C)
    ms5803_depth: float = 0.0        # Kedalaman dari I2C MS5803 (m)

    # Posisi & Trajectory Tracking (Dead Reckoning / Local NED)
    pos_x: float = 0.0               # Koordinat X meter (Forward/North)
    pos_y: float = 0.0               # Koordinat Y meter (Right/East)
    pos_z: float = 0.0               # Koordinat Z meter (Down/Depth)

    # Status Baterai & Daya
    battery_voltage: float = 0.0     # Voltase (V)
    battery_current: float = 0.0     # Arus (A)
    battery_percent: int = 0         # Persentase sisa baterai (0 - 100%)

    # Status Keamanan & QR Code Terakhir
    leak_detected: bool = False      # Indikator kebocoran internal (jika ada sensor leak)
    qr_last_code: str = ""           # Data QR Code terakhir yang terdeteksi
    qr_last_time: float = 0.0        # Waktu deteksi QR Code terakhir
    qr_last_cam: str = ""            # Sumber kamera yang mendeteksi QR Code (CAM 1 / CAM 2)
    qr_last_image: str = ""          # Base64 string gambar crop QR Code hasil capture

    # Output PWM Motor (List of dict [{'main': int, 'aux': int}, ...])
    pwm_outputs: list = field(default_factory=list)


class StateManager:
    """
    Thread-safe Singleton untuk mengelola dan memperbarui status ROVState.
    Dapat diakses oleh modul sensor (untuk menulis data) maupun control/UI (untuk membaca data).
    """
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.state = ROVState()
        self._callbacks = []

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = StateManager()
            return cls._instance

    def update(self, **kwargs):
        """
        Memperbarui field dalam ROVState secara aman terhadap thread.
        Contoh: state_mgr.update(roll=12.5, pitch=-3.2)
        """
        with self._lock:
            updated = False
            for key, value in kwargs.items():
                if hasattr(self.state, key):
                    setattr(self.state, key, value)
                    updated = True
            
            # Jika ada callback/listener (misalnya untuk WebSocket/UI update event)
            if updated and self._callbacks:
                current_state_copy = self.state.__dict__.copy()
                for cb in self._callbacks:
                    try:
                        cb(current_state_copy)
                    except Exception as e:
                        print(f"[StateManager Callback Error] {e}")

    def add_listener(self, callback):
        """Mendaftarkan fungsi callback yang dipanggil sewaktu state diperbarui."""
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def get_state(self) -> ROVState:
        """Mengembalikan referensi state terkini."""
        with self._lock:
            return self.state

    def to_dict(self) -> Dict[str, Any]:
        """Mengembalikan salinan state dalam bentuk dictionary (cocok untuk JSON / API response)."""
        with self._lock:
            return self.state.__dict__.copy()
