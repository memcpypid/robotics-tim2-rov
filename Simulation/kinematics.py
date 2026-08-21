class ROVKinematics:
    """
    Menghitung fisika dasar (kinematika visual) dari ROV dan
    memetakan input (x, y, z, r) ke konfigurasi 6 Thruster Vectored.
    """
    def __init__(self):
        # Kecepatan maksimal translasi (meter/detik) dan rotasi (derajat/detik)
        self.max_speed = 1.0  # m/s
        self.max_turn_rate = 60.0  # deg/s

        # Thruster output (PWM buatan) dari -1.0 sampai 1.0
        self.thrusters = [0.0] * 6

    def map_to_thrusters(self, x, y, z, r):
        """
        Pemetaan (Control Allocation Matrix) untuk 6-Thruster BlueROV2:
        T1 (Depan Kanan)  = Surge - Sway + Yaw
        T2 (Depan Kiri)   = Surge + Sway - Yaw
        T3 (Belakang Kanan) = Surge + Sway + Yaw
        T4 (Belakang Kiri)  = Surge - Sway - Yaw
        T5 (Vertikal Kanan) = Heave
        T6 (Vertikal Kiri)  = Heave
        """
        # Normalisasi input joystick
        # x, y, r rentangnya -1000 s/d 1000 (netral 0)
        # z rentangnya 0 s/d 1000 (netral 500)
        norm_x = x / 1000.0
        norm_y = y / 1000.0
        norm_z = (z - 500) / 500.0
        norm_r = r / 1000.0

        # Matriks mixing sederhana
        t1 = norm_x - norm_y + norm_r
        t2 = norm_x + norm_y - norm_r
        t3 = norm_x + norm_y + norm_r
        t4 = norm_x - norm_y - norm_r
        t5 = norm_z
        t6 = norm_z

        # Clamp nilai antara -1.0 sampai 1.0
        self.thrusters[0] = max(-1.0, min(1.0, t1))
        self.thrusters[1] = max(-1.0, min(1.0, t2))
        self.thrusters[2] = max(-1.0, min(1.0, t3))
        self.thrusters[3] = max(-1.0, min(1.0, t4))
        self.thrusters[4] = max(-1.0, min(1.0, t5))
        self.thrusters[5] = max(-1.0, min(1.0, t6))

    def calculate_velocity(self, dt):
        """
        Menghitung pergerakan global (X, Y, Z, Rotasi) berdasarkan output thruster.
        Ini murni visual/kinematik, tanpa gesekan fluida.
        """
        # Dari vektor 6-thruster kembali ke arah gerak dominan
        # (Inverse kinematics secara sederhana)
        surge = (self.thrusters[0] + self.thrusters[1] + self.thrusters[2] + self.thrusters[3]) / 4.0
        sway = (-self.thrusters[0] + self.thrusters[1] + self.thrusters[2] - self.thrusters[3]) / 4.0
        yaw_rate = (self.thrusters[0] - self.thrusters[1] + self.thrusters[2] - self.thrusters[3]) / 4.0
        heave = (self.thrusters[4] + self.thrusters[5]) / 2.0

        # Hitung kecepatan linear dan angular
        v_surge = surge * self.max_speed * dt
        v_sway = sway * self.max_speed * dt
        v_heave = heave * self.max_speed * dt
        v_yaw = yaw_rate * self.max_turn_rate * dt

        return v_surge, v_sway, v_heave, v_yaw
