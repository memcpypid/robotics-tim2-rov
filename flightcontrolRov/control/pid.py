"""
Generic PID Controller untuk stabilisasi ROV.

Digunakan oleh CustomMotionController untuk menstabilkan
Roll, Pitch, dan Yaw ROV secara independen.

Fitur:
- Anti-windup pada integral term (integral clamping)
- Output limiting (clamp output ke rentang yang aman)
- Dead-band untuk menghindari osilasi kecil
- Reset state
"""

import time


class PIDController:
    """
    Controller PID dengan anti-windup dan output limiting.

    Cara penggunaan:
        pid = PIDController(kp=1.0, ki=0.1, kd=0.05, output_limit=1.0)
        correction = pid.compute(setpoint=0.0, measurement=current_roll, dt=0.05)
    """

    def __init__(
        self,
        kp: float,
        ki: float,
        kd: float,
        output_limit: float = 1.0,
        integral_limit: float = None,
        deadband: float = 0.0,
    ):
        """
        :param kp:             Gain proporsional
        :param ki:             Gain integral
        :param kd:             Gain derivatif
        :param output_limit:   Batas maksimum output (clamp ke [-limit, +limit])
        :param integral_limit: Batas maksimum akumulasi integral (anti-windup).
                               Jika None, menggunakan output_limit / ki (jika ki > 0).
        :param deadband:       Error di bawah nilai ini dianggap 0 (mencegah osilasi kecil).
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_limit = abs(output_limit)
        self.deadband = abs(deadband)

        # Tentukan batas integral untuk anti-windup
        if integral_limit is not None:
            self._integral_limit = abs(integral_limit)
        elif ki > 0:
            self._integral_limit = self.output_limit / ki
        else:
            self._integral_limit = self.output_limit

        # State internal
        self._integral: float = 0.0
        self._prev_error: float = 0.0
        self._prev_time: float = None
        self._initialized: bool = False

    # ─────────────────────────────────────────────
    # Fungsi Utama
    # ─────────────────────────────────────────────

    def compute(self, setpoint: float, measurement: float, dt: float = None) -> float:
        """
        Hitung output PID berdasarkan setpoint dan measurement terkini.

        :param setpoint:    Target yang diinginkan (contoh: 0.0 untuk roll = datar)
        :param measurement: Nilai sensor terkini (contoh: roll aktual dalam derajat)
        :param dt:          Delta waktu dalam detik. Jika None, dihitung otomatis dari wallclock.
        :return:            Koreksi kontrol dalam rentang [-output_limit, +output_limit]
        """
        now = time.monotonic()

        # Hitung dt otomatis dari wallclock jika tidak diberikan
        if dt is None:
            if self._prev_time is None:
                dt = 0.0
            else:
                dt = now - self._prev_time
        self._prev_time = now

        # Hitung error
        error = setpoint - measurement

        # Dead-band: error kecil dianggap nol → mencegah getaran/osilasi halus
        if abs(error) < self.deadband:
            error = 0.0

        # ── Proporsional ──
        p_term = self.kp * error

        # ── Integral (dengan anti-windup via clamping) ──
        if dt > 0.0:
            self._integral += error * dt
            # Clamp integral untuk mencegah windup
            self._integral = max(-self._integral_limit, min(self._integral_limit, self._integral))
        i_term = self.ki * self._integral

        # ── Derivatif (berdasarkan delta error, bukan delta measurement) ──
        if dt > 0.0 and self._initialized:
            d_term = self.kd * (error - self._prev_error) / dt
        else:
            d_term = 0.0
        self._prev_error = error
        self._initialized = True

        # Total output
        output = p_term + i_term + d_term

        # Clamp output ke batas aman
        output = max(-self.output_limit, min(self.output_limit, output))

        return output

    def reset(self):
        """
        Reset state internal PID (integral accumulator, previous error, timer).
        Panggil ini saat mode berubah atau ROV baru di-arm agar tidak ada integral kickstart.
        """
        self._integral = 0.0
        self._prev_error = 0.0
        self._prev_time = None
        self._initialized = False

    def tune(self, kp: float = None, ki: float = None, kd: float = None):
        """
        Update gains PID secara dinamis (berguna untuk tuning di lapangan via parameter).
        Reset state secara otomatis setelah perubahan gains.
        """
        if kp is not None:
            self.kp = kp
        if ki is not None:
            self.ki = ki
        if kd is not None:
            self.kd = kd
        self.reset()

    # ─────────────────────────────────────────────
    # Debug
    # ─────────────────────────────────────────────

    def __repr__(self):
        return (
            f"PIDController(kp={self.kp}, ki={self.ki}, kd={self.kd}, "
            f"output_limit={self.output_limit}, integral={self._integral:.4f})"
        )
