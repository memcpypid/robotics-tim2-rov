import json
import os
from typing import Optional, Any, Dict

from PySide6.QtCore import QObject, Signal, QTimer

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False


CONFIG_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "joystick_config.json")
)
SERVO_CONFIG_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "servo_config.json")
)


class JoystickWorker(QObject):
    """
    Background Worker untuk mendeteksi dan membaca input dari USB Joystick.
    Seluruh pemetaan axis dan tombol dibaca dari joystick_config.json.
    """
    sig_joystick_status  = Signal(bool, str)
    sig_manual_control   = Signal(int, int, int, int, int)
    sig_log              = Signal(str, str)
    sig_arm_toggled      = Signal()
    sig_disarm_toggled   = Signal()
    sig_set_servo        = Signal(int, int)
    sig_mode_changed     = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._connected = False
        self._joystick: Optional[Any] = None
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._poll_joystick)

        self._prev_buttons: list = []
        self._enabled = True

        self._axes_map: Dict[str, dict] = {}
        self._buttons_map: Dict[str, int] = {}
        self._hat_depth = True

        self.servo_config: list = []
        self.servo_states: dict = {}

        self.reload_joystick_config()
        self.reload_servo_config()

    # ──────────────────────────────────────────
    # Config Reload
    # ──────────────────────────────────────────
    def reload_joystick_config(self, config_dict: dict = None):
        """Load konfigurasi joystick dari file JSON atau dict langsung (dari GUI Mapper)."""
        if config_dict is not None:
            data = config_dict
        else:
            try:
                if os.path.exists(CONFIG_PATH):
                    with open(CONFIG_PATH, "r") as f:
                        data = json.load(f)
                else:
                    data = {}
            except Exception:
                data = {}

        self._axes_map    = data.get("axes", {})
        self._buttons_map = data.get("buttons", {})
        self._hat_depth   = data.get("hat_depth", True)

    def reload_servo_config(self):
        """Load konfigurasi servo dari servo_config.json."""
        try:
            if os.path.exists(SERVO_CONFIG_PATH):
                with open(SERVO_CONFIG_PATH, "r") as f:
                    data = json.load(f)
                    self.servo_config = data.get("servos", [])
                    for s in self.servo_config:
                        pin = s["pin"]
                        if pin not in self.servo_states:
                            self.servo_states[pin] = s.get("trim_pwm", 1500)
        except Exception:
            pass

    # ──────────────────────────────────────────
    # Start / Stop
    # ──────────────────────────────────────────
    def start(self):
        if not PYGAME_AVAILABLE:
            self.sig_log.emit("[Joystick] pygame tidak ditemukan — fitur joystick nonaktif.", "WARN")
            return
        try:
            if not pygame.get_init():
                pygame.init()
            if not pygame.joystick.get_init():
                pygame.joystick.init()
            self._timer.start()
            self.sig_log.emit("[Joystick] Siap mendeteksi controller USB...", "INFO")
        except Exception as e:
            self.sig_log.emit(f"[Joystick ERROR] Gagal init: {e}", "ERROR")

    def stop(self):
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
        self._enabled = enabled
        if not enabled:
            self.sig_manual_control.emit(0, 0, 500, 0, 0)
            self.sig_log.emit("[Joystick] Kendali manual dinonaktifkan.", "INFO")
        else:
            self.sig_log.emit("[Joystick] Kendali manual diaktifkan.", "INFO")

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────
    def _apply_deadzone(self, value: float, threshold: float = 0.08) -> float:
        return 0.0 if abs(value) < threshold else value

    def _get_axis(self, func_key: str, num_axes: int) -> float:
        """Baca axis sesuai konfigurasi, terapkan deadzone, invert, scale."""
        cfg = self._axes_map.get(func_key)
        if not cfg:
            return 0.0
        idx = cfg.get("axis", -1)
        if idx < 0 or idx >= num_axes:
            return 0.0
        raw = self._joystick.get_axis(idx)
        raw = self._apply_deadzone(raw, cfg.get("deadzone", 0.08))
        if cfg.get("invert", False):
            raw = -raw
        return raw * cfg.get("scale", 1.0)

    def _btn_idx(self, func_key: str) -> int:
        return int(self._buttons_map.get(func_key, -1))

    # ──────────────────────────────────────────
    # Main Poll Loop
    # ──────────────────────────────────────────
    def _poll_joystick(self):
        if not PYGAME_AVAILABLE:
            return
        try:
            pygame.event.pump()
            count = pygame.joystick.get_count()

            if count > 0:
                if not self._connected:
                    self._joystick = pygame.joystick.Joystick(0)
                    self._joystick.init()
                    self._connected = True
                    name = self._joystick.get_name()
                    self.sig_joystick_status.emit(True, name)
                    self.sig_log.emit(f"[Joystick] Terdeteksi: {name}", "SUCCESS")
                    self._prev_buttons = [0] * self._joystick.get_numbuttons()
            else:
                if self._connected:
                    self._connected = False
                    self._joystick = None
                    self.sig_joystick_status.emit(False, "Tidak Ada Joystick")
                    self.sig_log.emit("[Joystick] Controller dicabut.", "WARN")
                    self.sig_manual_control.emit(0, 0, 500, 0, 0)
                return

            if not self._connected or not self._joystick or not self._enabled:
                return

            num_axes    = self._joystick.get_numaxes()
            num_buttons = self._joystick.get_numbuttons()
            num_hats    = self._joystick.get_numhats()

            # ── Baca axis dari config ──
            x = int(self._get_axis("forward_x", num_axes) * 1000)
            y = int(self._get_axis("strafe_y",  num_axes) * 1000)
            r = int(self._get_axis("yaw_r",     num_axes) * 1000)
            z_raw = self._get_axis("depth_z", num_axes)
            z = int(-z_raw * 500 + 500)

            # ── D-Pad untuk depth ──
            if self._hat_depth and num_hats > 0:
                hat = self._joystick.get_hat(0)
                if hat[1] > 0:
                    z = 850
                elif hat[1] < 0:
                    z = 150

            current_buttons = [self._joystick.get_button(i) for i in range(num_buttons)]

            # ── Tombol depth override ──
            bi_up   = self._btn_idx("depth_up")
            bi_down = self._btn_idx("depth_down")
            if 0 <= bi_up < num_buttons and current_buttons[bi_up]:
                z = max(z, 800)
            if 0 <= bi_down < num_buttons and current_buttons[bi_down]:
                z = min(z, 200)

            # Clamp
            x = max(-1000, min(1000, x))
            y = max(-1000, min(1000, y))
            z = max(0,    min(1000, z))
            r = max(-1000, min(1000, r))

            # Bitmask
            buttons_mask = 0
            for idx, s in enumerate(current_buttons):
                if s:
                    buttons_mask |= (1 << idx)

            # ── Single-press events ──
            if len(self._prev_buttons) == num_buttons:
                for idx in range(num_buttons):
                    if current_buttons[idx] and not self._prev_buttons[idx]:
                        self._handle_button_press(idx)

            # ── Servo logic ──
            if self.servo_config and len(self._prev_buttons) == num_buttons:
                for s in self.servo_config:
                    pin     = s["pin"]
                    mode    = s.get("mode", "toggle")
                    min_pwm = s.get("min_pwm", 1000)
                    max_pwm = s.get("max_pwm", 2000)
                    step    = s.get("step", 20)
                    b1      = s.get("btn_1", -1)
                    b2      = s.get("btn_2", -1)

                    old_pwm = self.servo_states.get(pin, s.get("trim_pwm", 1500))
                    new_pwm = old_pwm

                    if mode == "toggle":
                        if 0 <= b1 < num_buttons and current_buttons[b1] and not self._prev_buttons[b1]:
                            new_pwm = min_pwm if old_pwm >= max_pwm else max_pwm
                    elif mode == "incremental":
                        if 0 <= b1 < num_buttons and current_buttons[b1]:
                            new_pwm += step
                        if 0 <= b2 < num_buttons and current_buttons[b2]:
                            new_pwm -= step

                    new_pwm = max(min_pwm, min(max_pwm, new_pwm))
                    if new_pwm != old_pwm:
                        self.servo_states[pin] = new_pwm
                        self.sig_set_servo.emit(pin, new_pwm)

            self._prev_buttons = current_buttons
            self.sig_manual_control.emit(x, y, z, r, buttons_mask)

        except Exception:
            pass

    def _handle_button_press(self, idx: int):
        """Tangani single-press event berdasarkan config buttons."""
        for func_key, btn_idx in self._buttons_map.items():
            if btn_idx == idx:
                if func_key == "arm":
                    self.sig_arm_toggled.emit()
                elif func_key == "disarm":
                    self.sig_disarm_toggled.emit()
                elif func_key in ("mode_manual", "mode_stabilize", "mode_depth_hold"):
                    mode_name = func_key.replace("mode_", "").upper().replace("_", " ")
                    self.sig_mode_changed.emit(mode_name)
