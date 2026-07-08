"""
Kontrol Gerakan Thruster dan Orientasi ROV (ArduSub).
Menyediakan perintah kontrol gerak sumbu 6-DOF dan kontrol servo/lampu via PWM atau Tombol Joystick.
"""
from typing import List, Optional
from connection.mav_client import MAVClient

class ROVMotionControl:
    def __init__(self, client: MAVClient):
        self.client = client

    def send_manual_control(self, x: int = 0, y: int = 0, z: int = 500, r: int = 0, buttons: int = 0):
        """
        Mengirimkan perintah gerakan joystick 6-DOF (MANUAL_CONTROL) yang paling direkomendasikan untuk ROV/ArduSub.
        
        :param x: Maju/Mundur (Pitch/Surge) -> Rentang: -1000 sampai 1000
        :param y: Kiri/Kanan (Strafe/Sway) -> Rentang: -1000 sampai 1000
        :param z: Naik/Turun (Depth/Heave)   -> Rentang: 0 sampai 1000 (500 adalah nilai netral / diam)
        :param r: Putar Kiri/Kanan (Yaw)     -> Rentang: -1000 sampai 1000
        :param buttons: Bitmask untuk tombol aktif joystick (misalnya tombol 1, 2, lampu, gripper)
        """
        if not self.client.is_connected():
            return False

        # Pastikan nilai batas tetap aman (clamping)
        x = max(-1000, min(1000, int(x)))
        y = max(-1000, min(1000, int(y)))
        z = max(0, min(1000, int(z)))
        r = max(-1000, min(1000, int(r)))

        with self.client._lock:
            try:
                self.client.master.mav.manual_control_send(
                    self.client.master.target_system,
                    x, y, z, r, buttons
                )
                return True
            except Exception as e:
                print(f"[ROVMotionControl Error] Gagal mengirim manual_control: {e}")
                return False

    def send_rc_override(self, channels: List[int]):
        """
        Mengirimkan perintah overide sinyal PWM RC per channel (RC_CHANNELS_OVERRIDE).
        Berguna untuk pengetesan individual motor thruster atau aktuator (gripper, kamera tilt, lampu).
        
        :param channels: List berisi nilai PWM (1000-2000) untuk maksimum 8 channel (1500 netral, 65535 abaikan/release).
        """
        if not self.client.is_connected():
            return False

        # Lengkapi list channel sampai 8 channel dengan nilai 65535 (abaikan)
        padded_channels = list(channels)
        while len(padded_channels) < 8:
            padded_channels.append(65535)

        with self.client._lock:
            try:
                self.client.master.mav.rc_channels_override_send(
                    self.client.master.target_system,
                    self.client.master.target_component,
                    *padded_channels[:8]
                )
                return True
            except Exception as e:
                print(f"[ROVMotionControl Error] Gagal mengirim rc_override: {e}")
                return False

    def release_all_rc(self):
        """Melepaskan semua override RC kembali ke kendali normal / Flight Controller."""
        self.send_rc_override([65535] * 8)
