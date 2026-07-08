"""
Telemetry Sensor Listener untuk ROV (ArduSub / Pixhawk).
Membaca pesan MAVLink dari dispatcher dan mengupdate StateManager.
"""
import math
from typing import Any
from models.state import StateManager
from connection.dispatcher import MessageDispatcher

class ROVTelemetrySensor:
    def __init__(self, dispatcher: MessageDispatcher):
        """
        Inisialisasi sensor telemetry yang menghubungkan dispatcher pesan ke StateManager.
        """
        self.state_mgr = StateManager.get_instance()
        self.dispatcher = dispatcher

        # Daftarkan callback ke pesan-pesan MAVLink penting
        self.dispatcher.subscribe("HEARTBEAT", self._on_heartbeat)
        self.dispatcher.subscribe("ATTITUDE", self._on_attitude)
        self.dispatcher.subscribe("SYS_STATUS", self._on_sys_status)
        self.dispatcher.subscribe("VFR_HUD", self._on_vfr_hud)
        self.dispatcher.subscribe("SCALED_PRESSURE", self._on_scaled_pressure)
        self.dispatcher.subscribe("SCALED_PRESSURE2", self._on_scaled_pressure2)
        self.dispatcher.subscribe("STATUSTEXT", self._on_statustext)

    def _on_heartbeat(self, msg: Any):
        """
        Menangani pesan HEARTBEAT untuk mengetahui status koneksi, mode flight, dan status arming.
        """
        # Bit 128 (0x80) pada base_mode menandakan ARMED
        is_armed = bool(msg.base_mode & 0x80)
        
        # Mapping nama mode (jika dimuat di master, jika tidak kita ambil dari custom_mode sementara)
        # Pada ArduSub/ROV biasa: custom mode 0 = MANUAL, 1 = STABILIZE, 2 = DEPTH_HOLD, dsb.
        mode_names = {
            0: "STABILIZE",
            1: "ACRO",
            2: "ALT_HOLD",
            3: "AUTO",
            4: "GUIDED",
            7: "CIRCLE",
            9: "SURFACE",
            16: "POSHOLD",
            19: "MANUAL"
        }
        mode_str = mode_names.get(msg.custom_mode, f"MODE_{msg.custom_mode}")

        self.state_mgr.update(
            connected=True,
            armed=is_armed,
            mode=mode_str,
            system_id=msg.get_srcSystem(),
            component_id=msg.get_srcComponent()
        )

    def _on_attitude(self, msg: Any):
        """Menangani pembacaan kemiringan (Roll, Pitch, Yaw) dari IMU Pixhawk."""
        self.state_mgr.update(
            roll=math.degrees(msg.roll),
            pitch=math.degrees(msg.pitch),
            yaw=math.degrees(msg.yaw)
        )

    def _on_sys_status(self, msg: Any):
        """Menangani pembacaan voltase baterai dan sisa daya."""
        self.state_mgr.update(
            battery_voltage=msg.voltage_battery / 1000.0,  # millivolt ke volt
            battery_current=msg.current_battery / 100.0,   # 10 * milliamperes ke ampere
            battery_percent=msg.battery_remaining          # 0 - 100 %
        )

    def _on_vfr_hud(self, msg: Any):
        """
        Menangani pembacaan dari VFR_HUD. Pada ROV, alt di sini biasanya adalah kedalaman (atau negatif altitude).
        """
        self.state_mgr.update(
            depth_m=abs(msg.alt)  # Mengubah altitude menjadi depth positif (meter)
        )

    def _on_scaled_pressure(self, msg: Any):
        """Pembacaan sensor tekanan barometer internal Pixhawk."""
        self.state_mgr.update(
            pressure_press_abs=msg.press_abs
        )

    def _on_scaled_pressure2(self, msg: Any):
        """
        Pembacaan sensor tekanan air eksternal (misal Bar02 / Bar30 eksternal ROV).
        Suhu air dan tekanan eksternal biasanya ada di pesan ini.
        """
        self.state_mgr.update(
            pressure_press_abs=msg.press_abs,
            water_temperature_c=msg.temperature / 100.0
        )

    def _on_statustext(self, msg: Any):
        """Mendeteksi pesan teks dari Pixhawk, termasuk peringatan kebocoran (Leak Detector)."""
        text = getattr(msg, 'text', '')
        if isinstance(text, bytes):
            text = text.decode('utf-8', errors='ignore')
        
        if "leak" in text.lower():
            print(f"[ALERT - ROV LEAK DETECTED!] {text}")
            self.state_mgr.update(leak_detected=True)
