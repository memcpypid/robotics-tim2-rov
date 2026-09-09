import time
import threading
from models.state import StateManager
from control.pid import PIDController
from control.motion import ROVMotionControl

class MS5803DepthHoldControl(threading.Thread):
    """
    Sistem Kontrol Depth Hold menggunakan sensor GY-MS5803-01BA I2C.
    Berjalan di background thread secara independen.
    """
    def __init__(self, motion: ROVMotionControl):
        super().__init__(name="MS5803_DepthHold_Thread", daemon=True)
        self.motion = motion
        self.state_mgr = StateManager.get_instance()
        
        self.running = False
        self.active = False
        
        # PID (Kp, Ki, Kd) - default tunings (bisa disesuaikan)
        self.pid = PIDController(kp=100.0, ki=10.0, kd=5.0, output_limit=1000.0, deadband=0.05)
        
        # Target kedalaman (meter)
        self.target_depth = 0.0

    def set_pid(self, kp: float, ki: float, kd: float):
        """Update parameter PID"""
        self.pid.tune(kp=kp, ki=ki, kd=kd)
        print(f"[DepthHold] PID diupdate: P={kp}, I={ki}, D={kd}")

    def set_target_depth(self, target: float):
        """Ubah target kedalaman (meter)"""
        self.target_depth = max(0.0, target)  # Tidak boleh negatif
        print(f"[DepthHold] Target Depth diupdate: {self.target_depth:.2f} m")

    def enable(self):
        """Aktifkan Depth Hold PID loop"""
        if not self.active:
            # Jadikan kedalaman saat ini sebagai target jika baru diaktifkan dan target belum diset
            current_depth = self.state_mgr.get_state().ms5803_depth
            if self.target_depth == 0.0:
                self.target_depth = current_depth
            self.pid.reset()
            self.active = True
            print(f"[DepthHold] AKTIF. Target: {self.target_depth:.2f}m")

    def disable(self):
        """Nonaktifkan Depth Hold"""
        if self.active:
            self.active = False
            # Reset motion (berhenti dive otomatis)
            self.motion.dive(0)
            print("[DepthHold] NONAKTIF.")

    def stop(self):
        """Hentikan thread"""
        self.running = False
        self.disable()

    def run(self):
        self.running = True
        while self.running:
            if self.active:
                state = self.state_mgr.get_state()
                current_depth = state.ms5803_depth
                
                # Hitung koreksi PID
                # Setpoint = target_depth, Measurement = current_depth
                # Jika target > current, artinya ROV harus menyelam (dive +) -> butuh output positif
                # Karena PID default: error = setpoint - measurement, 
                # target (1m) - current (0.5m) = 0.5 error -> output positif -> dive(+), ini benar.
                correction = self.pid.compute(setpoint=self.target_depth, measurement=current_depth)
                
                # Kirim ke ROV (menggunakan dive() yang menerima -1000 s/d 1000)
                # Karena sebelumnya motor berputar ke arah yang salah (terbalik), kita inverting output PID-nya
                self.motion.dive(int(-correction))
                
            time.sleep(0.05)  # Loop pada ~20Hz
