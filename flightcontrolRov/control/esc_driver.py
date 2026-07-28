"""
SkywalkerESCDriver — Driver sinyal ESC 4-Pin via MAVLink DO_SET_SERVO.

Mendukung ESC dengan 4 pin: VCC, GND, PWM (kecepatan), REVERSE (arah).

Mapping Hardware (Pixhawk Cube Black):
  MAIN OUT 1–6  → Kabel PWM  (kecepatan) tiap thruster
  AUX  OUT 1–6  → Kabel REVERSE (arah) tiap thruster
    AUX1 = Servo #9, AUX2 = #10, ..., AUX6 = #14

Sinyal:
  Kabel PWM  (MAIN OUT):  idle_pwm (default 800µs) = berhenti, 2000µs = full speed
  Kabel REVERSE (AUX OUT): fwd_pwm (default 1300µs) = maju, rev_pwm (default 1700µs) = mundur

Thruster berhenti SELALU pada idle_pwm dengan sinyal arah maju (aman).
"""

import logging
import time
from typing import List, Optional
from pymavlink import mavutil
from connection.mav_client import MAVClient

logger = logging.getLogger("ESCDriver")


# ─────────────────────────────────────────────────────────
# Default konstanta sinyal ESC
# ─────────────────────────────────────────────────────────
ESC_IDLE_PWM    = 800    # µs: Throttle saat motor berhenti
ESC_MAX_PWM     = 2000   # µs: Throttle full speed

DIR_FORWARD_PWM = 1300   # µs: Sinyal REVERSE pin → Maju
DIR_REVERSE_PWM = 1700   # µs: Sinyal REVERSE pin → Mundur

# Cube Black: AUX OUT 1 = Servo #9, AUX OUT 2 = #10, ...
AUX_SERVO_BASE  = 9

# Jumlah thruster (channel)
NUM_THRUSTERS   = 6

# Minimum interval pengiriman per channel (20 Hz = 50ms)
MIN_SEND_INTERVAL = 0.05


class SkywalkerESCDriver:
    """
    Driver ESC Skywalker/4-pin yang mengonversi thrust [-1.0, +1.0]
    menjadi 2 sinyal PWM (throttle + arah) yang dikirim via MAVLink DO_SET_SERVO.

    MAIN OUT (ch 1–6) : Sinyal throttle kabel putih (kecepatan)
    AUX  OUT (ch 9–14): Sinyal arah kabel kuning (maju/mundur)

    Cara penggunaan:
        driver = SkywalkerESCDriver(client)
        driver.set_thrust(channel=1, thrust=0.75)   # 75% forward
        driver.set_thrust(channel=2, thrust=-0.5)   # 50% reverse
        driver.stop_all()
    """

    def __init__(
        self,
        client: MAVClient,
        idle_pwm: int = ESC_IDLE_PWM,
        max_pwm: int = ESC_MAX_PWM,
        fwd_pwm: int = DIR_FORWARD_PWM,
        rev_pwm: int = DIR_REVERSE_PWM,
        num_thrusters: int = NUM_THRUSTERS,
        deadband_threshold: float = 0.01,
    ):
        """
        :param client:            Instance MAVClient yang terhubung ke Pixhawk.
        :param idle_pwm:          PWM throttle saat motor berhenti (µs).
        :param max_pwm:           PWM throttle full speed (µs).
        :param fwd_pwm:           PWM sinyal REVERSE saat maju (µs).
        :param rev_pwm:           PWM sinyal REVERSE saat mundur (µs).
        :param num_thrusters:     Jumlah thruster (default 6).
        :param deadband_threshold: Thrust di bawah nilai ini dianggap 0 (motor berhenti).
        """
        self.client = client
        self.idle_pwm = idle_pwm
        self.max_pwm = max_pwm
        self.fwd_pwm = fwd_pwm
        self.rev_pwm = rev_pwm
        self.num_thrusters = num_thrusters
        self.deadband = deadband_threshold

        # Precomputed range
        self._pwm_range = max_pwm - idle_pwm  # 1200µs

        # Rate limiting per channel: simpan timestamp terakhir pengiriman
        self._last_send: List[float] = [0.0] * (num_thrusters + 1)  # index 1-based

        logger.info(
            f"ESCDriver init: idle={idle_pwm}µs, max={max_pwm}µs, "
            f"fwd={fwd_pwm}µs, rev={rev_pwm}µs, {num_thrusters} thrusters"
        )

    # ─────────────────────────────────────────────
    # API Utama
    # ─────────────────────────────────────────────

    def set_thrust(self, channel: int, thrust: float):
        """
        Mengatur thrust satu thruster dan mengirim sinyal ke Pixhawk.

        :param channel: Nomor thruster (1–6)
        :param thrust:  Nilai thrust [-1.0, +1.0].
                        0.0 = berhenti, +1.0 = full maju, -1.0 = full mundur
        """
        if not (1 <= channel <= self.num_thrusters):
            logger.warning(f"Channel {channel} tidak valid (1–{self.num_thrusters})")
            return

        if not self.client.is_connected():
            return

        # Clamp
        thrust = max(-1.0, min(1.0, float(thrust)))

        # Dead-band: thrust kecil → berhenti
        if abs(thrust) < self.deadband:
            thrust = 0.0

        # Hitung PWM throttle dan sinyal arah
        throttle_pwm, direction_pwm = self._thrust_to_pwm(thrust)

        # Kirim ke hardware
        aux_servo_num = AUX_SERVO_BASE + (channel - 1)  # AUX1=9, AUX2=10, ...

        self._send_servo(channel, throttle_pwm)          # MAIN OUT (kabel PWM)
        self._send_servo(aux_servo_num, direction_pwm)   # AUX OUT  (kabel REVERSE)

        logger.debug(
            f"CH{channel}: thrust={thrust:+.3f} → "
            f"MAIN={throttle_pwm}µs | AUX{channel}(#{aux_servo_num})="
            f"{'FWD' if direction_pwm == self.fwd_pwm else 'REV'}({direction_pwm}µs)"
        )

    def set_all_thrust(self, thrusts: List[float]):
        """
        Mengatur thrust semua thruster sekaligus dari sebuah list.

        :param thrusts: List thrust [-1.0, +1.0] untuk thruster 1–N (index 0 = thruster 1)
        """
        for i, thrust in enumerate(thrusts[:self.num_thrusters]):
            self.set_thrust(channel=i + 1, thrust=thrust)

    def stop_all(self):
        """
        Hentikan semua thruster secara aman:
        - Throttle ke idle_pwm (motor berhenti)
        - REVERSE pin ke fwd_pwm (arah maju, aman setelah berhenti)
        """
        if not self.client.is_connected():
            return

        logger.info(f"ESCDriver: Menghentikan semua {self.num_thrusters} thruster...")
        for ch in range(1, self.num_thrusters + 1):
            aux_num = AUX_SERVO_BASE + (ch - 1)
            self._send_servo(ch, self.idle_pwm)        # Throttle → idle
            self._send_servo(aux_num, self.fwd_pwm)    # REVERSE → maju (aman)
        logger.info("ESCDriver: Semua thruster berhenti.")

    # ─────────────────────────────────────────────
    # Konversi Signal
    # ─────────────────────────────────────────────

    def _thrust_to_pwm(self, thrust: float):
        """
        Konversi thrust [-1.0, +1.0] ke (throttle_pwm, direction_pwm).

        Throttle mapping (linear):
          thrust = 0.0  → idle_pwm  (800µs, motor berhenti)
          thrust = ±1.0 → max_pwm   (2000µs, full speed)

        Direction mapping:
          thrust >= 0  → fwd_pwm (1300µs)
          thrust <  0  → rev_pwm (1700µs)

        :return: (throttle_pwm: int, direction_pwm: int)
        """
        abs_thrust = abs(thrust)

        # Throttle: linear dari idle ke max
        throttle_pwm = int(self.idle_pwm + abs_thrust * self._pwm_range)
        throttle_pwm = max(self.idle_pwm, min(self.max_pwm, throttle_pwm))

        # Arah
        direction_pwm = self.fwd_pwm if thrust >= 0.0 else self.rev_pwm

        return throttle_pwm, direction_pwm

    # ─────────────────────────────────────────────
    # Pengiriman MAVLink
    # ─────────────────────────────────────────────

    def _send_servo(self, servo_num: int, pwm: int):
        """
        Mengirim MAV_CMD_DO_SET_SERVO ke Pixhawk untuk satu output servo.

        :param servo_num: Nomor servo MAVLink (MAIN OUT: 1–8, AUX OUT: 9–14)
        :param pwm:       Nilai PWM dalam µs
        """
        if self.client.master is None:
            return

        # PENTING: Jangan gunakan self.client._lock karena bisa deadlock.
        # Akses master langsung (thread-safe per pymavlink untuk write tunggal).
        try:
            self.client.master.mav.command_long_send(
                self.client.master.target_system,
                self.client.master.target_component,
                mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
                0,                  # Confirmation (tidak butuh ACK)
                float(servo_num),   # param1: Nomor servo
                float(pwm),         # param2: Nilai PWM (µs)
                0, 0, 0, 0, 0
            )
        except Exception as e:
            logger.error(f"Gagal set servo #{servo_num} → {pwm}µs: {e}")

    # ─────────────────────────────────────────────
    # Debug
    # ─────────────────────────────────────────────

    def debug_thrust(self, thrusts: List[float]):
        """Cetak thrust → PWM mapping untuk semua channel (untuk verifikasi)."""
        print("\n=== ESC Thrust → PWM Debug ===")
        for i, thrust in enumerate(thrusts[:self.num_thrusters]):
            ch = i + 1
            thr, dir_pwm = self._thrust_to_pwm(thrust)
            aux = AUX_SERVO_BASE + i
            dir_label = "MAJU  " if dir_pwm == self.fwd_pwm else "MUNDUR"
            print(
                f"  T{ch}: thrust={thrust:+.3f} → "
                f"MAIN_OUT{ch}={thr}µs | AUX{ch}(#{aux})={dir_label}({dir_pwm}µs)"
            )
        print("==============================\n")
