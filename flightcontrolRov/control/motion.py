"""
Kontrol Gerakan Thruster dan Orientasi ROV (ArduSub).
Menyediakan perintah kontrol gerak sumbu 6-DOF dan kontrol servo/lampu via PWM atau Tombol Joystick.
"""
from typing import List, Optional
from connection.mav_client import MAVClient
from pymavlink import mavutil

class ROVMotionControl:
    def __init__(self, client: MAVClient):
        self.client = client
        self._last_x = 0
        self._last_y = 0
        self._last_z = 500
        self._last_r = 0
        self._last_buttons = 0

    def send_manual_control(self, x: int = 0, y: int = 0, z: int = 500, r: int = 0, buttons: int = 0):
        if not self.client.is_connected():
            return False

        # Pastikan nilai batas tetap aman (clamping)
        self._last_x = max(-1000, min(1000, int(x)))
        self._last_y = max(-1000, min(1000, int(y)))
        self._last_z = max(0, min(1000, int(z)))
        self._last_r = max(-1000, min(1000, int(r)))
        self._last_buttons = buttons

        with self.client._lock:
            try:
                self.client.master.mav.manual_control_send(
                    self.client.master.target_system,
                    self._last_x, self._last_y, self._last_z, self._last_r, self._last_buttons
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

    def dive(self, depth_rate: int = 0) -> bool:
        """
        Mengirimkan perintah naik/turun (heave) secara mudah tanpa harus ingat
        konversi nilai z-axis MANUAL_CONTROL.

        Cara kerja ArduSub MANUAL_CONTROL z-axis:
          - z = 500 : Netral (diam di kedalaman saat ini)
          - z = 0   : Naik penuh (ascend)
          - z = 1000: Turun penuh / menyelam (descend)

        Parameter depth_rate ini (nilai intuitif):
          -1000 = naik penuh
              0 = diam (hover)
          +1000 = turun / menyelam penuh

        :param depth_rate: Kecepatan naik/turun, rentang -1000 sampai +1000
        :return: True jika perintah berhasil dikirim
        """
        depth_rate = max(-1000, min(1000, int(depth_rate)))
        # Konversi ke z-axis MANUAL_CONTROL: 500 + (depth_rate / 2)
        # depth_rate= 0    -> z=500  (hover)
        # depth_rate= 1000 -> z=1000 (turun penuh)
        # depth_rate=-1000 -> z=0    (naik penuh)
        z = int(500 + (depth_rate / 2.0))
        z = max(0, min(1000, z))
        return self.send_manual_control(x=self._last_x, y=self._last_y, z=z, r=self._last_r, buttons=self._last_buttons)

    def stop(self) -> bool:
        """
        Menghentikan semua gerak ROV (x=0, y=0, z=500 hover, r=0).
        Berguna sebagai emergency stop / jeda sejenak.
        """
        return self.send_manual_control(x=0, y=0, z=500, r=0)

    def release_all_rc(self):
        """Melepaskan semua override RC kembali ke kendali normal / Flight Controller."""
        self.send_rc_override([65535] * 8)

    def set_servo(self, pin: int, pwm: int) -> bool:
        """
        Mengontrol servo secara spesifik di pin tertentu (biasanya AUX 1-6 / Servo 9-14).
        
        :param pin: Nomor servo (1-16, di ArduSub AUX 1 = 9)
        :param pwm: Nilai PWM (biasanya 1000 - 2200)
        """
        if not self.client.is_connected():
            return False

        # Pastikan batas wajar PWM (500 - 2500 adalah standar untuk servo 180/270 derajat)
        # pwm = max(500, min(2500, int(pwm)))
        # pin = max(1, min(16, int(pin)))

        with self.client._lock:
            try:
                self.client.master.mav.command_long_send(
                    self.client.master.target_system,
                    self.client.master.target_component,
                    mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
                    0,            # confirmation
                    pin,          # param1: nomor servo
                    pwm,          # param2: nilai PWM
                    0, 0, 0, 0, 0 # param3-7 unused
                )
                return True
            except Exception as e:
                print(f"[ROVMotionControl Error] Gagal mengatur servo {pin}: {e}")
                return False

    def set_relay(self, relay_num: int, state: bool) -> bool:
        """
        Mengontrol relay di Pixhawk (MAV_CMD_DO_SET_RELAY).
        :param relay_num: Nomor relay (biasanya 0, 1, 2, 3)
        :param state: True untuk ON (1), False untuk OFF (0)
        """
        if not self.client.is_connected():
            return False

        with self.client._lock:
            try:
                self.client.master.mav.command_long_send(
                    self.client.master.target_system,
                    self.client.master.target_component,
                    mavutil.mavlink.MAV_CMD_DO_SET_RELAY,
                    0,            # confirmation
                    relay_num,    # param1: relay number
                    1 if state else 0, # param2: 1=on, 0=off
                    0, 0, 0, 0, 0 # param3-7 unused
                )
                return True
            except Exception as e:
                print(f"[ROVMotionControl Error] Gagal mengatur relay {relay_num}: {e}")
                return False
