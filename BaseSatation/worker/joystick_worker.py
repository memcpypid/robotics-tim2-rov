import time
from typing import Optional
from PySide6.QtCore import QObject, Signal, QTimer

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False


class JoystickWorker(QObject):
    """
    Background Worker untuk mendeteksi dan membaca input dari USB Joystick / Gamepad
    (Logitech, Xbox, PlayStation, USB Controller) menggunakan Pygame.
    
    Pemetaan Kendali ROV (6-DOF):
    - Left Stick Vertical   : Maju / Mundur (x: -1000 s/d 1000)
    - Left Stick Horizontal : Geser Kiri / Kanan (y: -1000 s/d 1000)
    - Right Stick Horizontal: Putar Yaw Kiri / Kanan (r: -1000 s/d 1000)
    - Right Stick Vertical / D-Pad Up-Down / R1-L1: Naik / Turun Kedalaman (z: 0 s/d 1000, 500 netral)
    """
    sig_joystick_status = Signal(bool, str)          # (is_connected, device_name)
    sig_manual_control = Signal(int, int, int, int, int) # (x, y, z, r, buttons)
    sig_log = Signal(str, str)                       # (message, level)
    sig_arm_toggled = Signal()                       # Tombol khusus untuk Arm
    sig_disarm_toggled = Signal()                    # Tombol khusus untuk Disarm

    def __init__(self, parent=None):
        super().__init__(parent)
        self._connected = False
        self._joystick: Optional[Any] = None
        self._timer = QTimer(self)
        self._timer.setInterval(50)  # Polling 20 Hz
        self._timer.timeout.connect(self._poll_joystick)
        
        self._last_log_time = 0.0
        self._prev_buttons = []
        self._enabled = True

    def start(self):
        """Memulai pemantauan input USB Joystick."""
        if not PYGAME_AVAILABLE:
            self.sig_log.emit("[USB Joystick WARNING] Modul pygame tidak ditemukan. Fitur joystick USB nonaktif.", "WARN")
            return

        try:
            pygame.init()
            pygame.joystick.init()
            self._timer.start()
            self.sig_log.emit("[USB Joystick] Siap mendeteksi controller USB yang dicolokkan...", "INFO")
        except Exception as e:
            self.sig_log.emit(f"[USB Joystick ERROR] Gagal inisialisasi pygame joystick: {e}", "ERROR")

    def stop(self):
        """Menghentikan polling joystick."""
        self._timer.stop()
        if self._connected and self._joystick:
            try:
                self._joystick.quit()
            except Exception:
                pass
            self._joystick = None
            self._connected = False
            self.sig_joystick_status.emit(False, "Joystick Ditutup")

    def set_enabled(self, enabled: bool):
        """Aktifkan / nonaktifkan pengiriman sinyal kendali dari joystick ke ROV."""
        self._enabled = enabled
        if not enabled:
            # Kirim sinyal netral (hover / berhenti) saat joystick dinonaktifkan
            self.sig_manual_control.emit(0, 0, 500, 0, 0)
            self.sig_log.emit("[USB Joystick] Kendali manual joystick dinonaktifkan.", "INFO")
        else:
            self.sig_log.emit("[USB Joystick] Kendali manual joystick diaktifkan.", "INFO")

    def _apply_deadzone(self, value: float, threshold: float = 0.08) -> float:
        """Menghilangkan drift kecil ketika stik berada di tengah."""
        if abs(value) < threshold:
            return 0.0
        return value

    def _poll_joystick(self):
        if not PYGAME_AVAILABLE:
            return

        try:
            # Pompa event agar pygame membaca status perangkat USB terkini tanpa window GUI pygame
            pygame.event.pump()
            
            count = pygame.joystick.get_count()
            if count > 0:
                if not self._connected:
                    # Ambil joystick pertama yang dicolokkan
                    self._joystick = pygame.joystick.Joystick(0)
                    self._joystick.init()
                    self._connected = True
                    device_name = self._joystick.get_name()
                    self.sig_joystick_status.emit(True, device_name)
                    self.sig_log.emit(f"[USB Joystick SUCCESS] Joystick Terdeteksi & Aktif: {device_name}", "SUCCESS")
                    self._prev_buttons = [0] * self._joystick.get_numbuttons()
            else:
                if self._connected:
                    self._connected = False
                    self._joystick = None
                    self.sig_joystick_status.emit(False, "Tidak Ada Joystick USB Tercolok")
                    self.sig_log.emit("[USB Joystick WARNING] Joystick USB terputus / dicabut.", "WARN")
                    # Kirim berhenti ke ROV demi keamanan
                    self.sig_manual_control.emit(0, 0, 500, 0, 0)
                return

            if not self._connected or not self._joystick or not self._enabled:
                return

            # --- PEMBACAAN AXIS JOYSTICK ---
            num_axes = self._joystick.get_numaxes()
            
            # 1. Axis 1: Left Stick Vertical (Maju / Mundur -> x)
            # Pada joystick, dorong ke depan bernilai negatif (-1.0), tarik ke belakang positif (+1.0)
            raw_y_left = self._apply_deadzone(self._joystick.get_axis(1)) if num_axes > 1 else 0.0
            x = int(-raw_y_left * 1000)

            # 2. Axis 0: Left Stick Horizontal (Geser Kiri / Kanan -> y)
            # Dorong kanan positif (+1.0), kiri negatif (-1.0)
            raw_x_left = self._apply_deadzone(self._joystick.get_axis(0)) if num_axes > 0 else 0.0
            y = int(raw_x_left * 1000)

            # 3. Axis 3 / Axis 2: Right Stick Horizontal (Putar Yaw -> r)
            # Pada beberapa gamepad (Xbox/DualShock), axis kanan X ada di index 3, atau index 2
            axis_r_idx = 3 if num_axes > 3 else (2 if num_axes > 2 else -1)
            raw_x_right = self._apply_deadzone(self._joystick.get_axis(axis_r_idx)) if axis_r_idx >= 0 else 0.0
            r = int(raw_x_right * 1000)

            # 4. Axis 4 / Axis 3: Kedalaman / Throttle (Naik / Turun -> z)
            # Default netral / hover = 500. Naik = > 500 (sampai 1000), Turun = < 500 (sampai 0)
            axis_z_idx = 4 if num_axes > 4 else (3 if num_axes > 3 and axis_r_idx != 3 else -1)
            raw_y_right = self._apply_deadzone(self._joystick.get_axis(axis_z_idx)) if axis_z_idx >= 0 else 0.0
            
            # Mapping axis vertical stik kanan ke 0-1000
            z = int(-raw_y_right * 500 + 500)

            # --- KENDALI TAMBAHAN KEDALAMAN (D-PAD / HAT & SHOULDER BUTTONS) ---
            num_hats = self._joystick.get_numhats()
            if num_hats > 0:
                hat = self._joystick.get_hat(0)
                if hat[1] > 0:    # D-Pad UP ditekankan -> Naik
                    z = 850
                elif hat[1] < 0:  # D-Pad DOWN ditekankan -> Turun (Dive)
                    z = 150

            # --- PEMBACAAN TOMBOL & BITMASK ---
            num_buttons = self._joystick.get_numbuttons()
            current_buttons = [self._joystick.get_button(i) for i in range(num_buttons)]
            
            # Override R1 (biasanya button index 5 atau 4) untuk naik, L1 (button 4 atau 3) untuk turun
            if num_buttons > 5:
                if current_buttons[5]:  # R1 / RB
                    z = max(z, 800)
                if current_buttons[4]:  # L1 / LB
                    z = min(z, 200)

            # Pastikan batas rentang x, y, z, r aman
            x = max(-1000, min(1000, x))
            y = max(-1000, min(1000, y))
            z = max(0, min(1000, z))
            r = max(-1000, min(1000, r))

            # Bitmask tombol untuk dikirim ke ROV
            buttons_mask = 0
            for idx, btn_state in enumerate(current_buttons):
                if btn_state:
                    buttons_mask |= (1 << idx)

            # Deteksi tombol khusus Arm / Disarm (contoh: Tombol Start / Select pada Gamepad)
            # Biasanya tombol 7 (Start) / tombol 6 (Select) pada stik standar USB / Xbox / PS
            if len(self._prev_buttons) == num_buttons:
                for idx in range(num_buttons):
                    if current_buttons[idx] and not self._prev_buttons[idx]:
                        # Tombol baru ditekankan (single press event)
                        if idx == 7 or idx == 9:  # Tombol START / OPTIONS
                            self.sig_arm_toggled.emit()
                        elif idx == 6 or idx == 8:  # Tombol SELECT / SHARE
                            self.sig_disarm_toggled.emit()

            self._prev_buttons = current_buttons

            # Kirim sinyal kendali manual
            self.sig_manual_control.emit(x, y, z, r, buttons_mask)

        except Exception:
            pass
