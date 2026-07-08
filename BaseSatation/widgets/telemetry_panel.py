from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QGroupBox, QProgressBar
)
from PySide6.QtCore import Qt


class TelemetryPanel(QWidget):
    """
    Panel Telemetri Digital Base Station ROV (Kedalaman dari permukaan, Ketinggian dari dasar kolam, Baterai, Status Mode & Arming).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        # 1. Groupbox Status Utama (Mode & Armed status)
        status_group = QGroupBox("FLIGHT & ARM STATUS")
        status_layout = QHBoxLayout(status_group)

        self.lbl_mode = QLabel("MANUAL")
        self.lbl_mode.setAlignment(Qt.AlignCenter)
        self.lbl_mode.setStyleSheet("background-color: #202d42; border: 1px solid #00e5ff; border-radius: 6px; font-size: 15px; font-weight: bold; padding: 6px; color: #00e5ff;")

        self.lbl_armed = QLabel("DISARMED")
        self.lbl_armed.setAlignment(Qt.AlignCenter)
        self.lbl_armed.setStyleSheet("background-color: #2e1a1a; border: 1px solid #ff4d4d; border-radius: 6px; font-size: 15px; font-weight: bold; padding: 6px; color: #ff4d4d;")

        status_layout.addWidget(self.lbl_mode)
        status_layout.addWidget(self.lbl_armed)
        main_layout.addWidget(status_group)

        # 2. Groupbox Kedalaman & Ketinggian Dasar Kolam (Bottom Clearance)
        depth_group = QGroupBox("DEPTH & BOTTOM CLEARANCE (ALTIMETER)")
        depth_layout = QVBoxLayout(depth_group)
        depth_layout.setSpacing(6)

        # Kedalaman dari Permukaan
        row_depth = QHBoxLayout()
        row_depth.addWidget(QLabel("Kedalaman Permukaan:"))
        row_depth.addStretch()
        self.lbl_depth_val = QLabel("0.00 m")
        self.lbl_depth_val.setObjectName("value_label")
        row_depth.addWidget(self.lbl_depth_val)
        depth_layout.addLayout(row_depth)

        # Ketinggian dari Dasar Kolam (Bottom Altimeter)
        row_alt = QHBoxLayout()
        row_alt.addWidget(QLabel("Tinggi dari Dasar Kolam:"))
        row_alt.addStretch()
        self.lbl_alt_val = QLabel("0.00 m")
        self.lbl_alt_val.setObjectName("value_label")
        self.lbl_alt_val.setStyleSheet("color: #40bf6a; font-weight: bold; font-size: 18px;")
        row_alt.addWidget(self.lbl_alt_val)
        depth_layout.addLayout(row_alt)

        self.bar_alt = QProgressBar()
        self.bar_alt.setRange(0, 300)  # max 300 cm / 3 m clearance
        self.bar_alt.setValue(0)
        self.bar_alt.setFormat("Altimeter Clearance: %v cm")
        self.bar_alt.setStyleSheet("""
            QProgressBar { background-color: #121824; border: 1px solid #2d3e5c; border-radius: 5px; text-align: center; color: #ffffff; font-size: 11px; }
            QProgressBar::chunk { background-color: #40bf6a; border-radius: 4px; }
        """)
        depth_layout.addWidget(self.bar_alt)

        main_layout.addWidget(depth_group)

        # 3. Groupbox Baterai & Daya
        power_group = QGroupBox("POWER & BATTERY STATUS")
        power_layout = QVBoxLayout(power_group)

        bat_layout = QHBoxLayout()
        bat_layout.addWidget(QLabel("Tegangan Baterai:"))
        bat_layout.addStretch()
        self.lbl_bat_val = QLabel("0.0 V")
        self.lbl_bat_val.setObjectName("value_label")
        bat_layout.addWidget(self.lbl_bat_val)
        power_layout.addLayout(bat_layout)

        self.bar_battery = QProgressBar()
        self.bar_battery.setRange(0, 100)
        self.bar_battery.setValue(0)
        self.bar_battery.setFormat("Baterai: %p%")
        power_layout.addWidget(self.bar_battery)

        main_layout.addWidget(power_group)

        # 4. Groupbox RPY Detail (Roll Pitch Yaw)
        rpy_group = QGroupBox("ATTITUDE VECTOR (6-DOF)")
        rpy_layout = QGridLayout(rpy_group)

        rpy_layout.addWidget(QLabel("Roll:"), 0, 0)
        self.lbl_roll = QLabel("0.0°")
        self.lbl_roll.setObjectName("value_label")
        rpy_layout.addWidget(self.lbl_roll, 0, 1)

        rpy_layout.addWidget(QLabel("Pitch:"), 1, 0)
        self.lbl_pitch = QLabel("0.0°")
        self.lbl_pitch.setObjectName("value_label")
        rpy_layout.addWidget(self.lbl_pitch, 1, 1)

        rpy_layout.addWidget(QLabel("Yaw:"), 2, 0)
        self.lbl_yaw = QLabel("0.0°")
        self.lbl_yaw.setObjectName("value_label")
        rpy_layout.addWidget(self.lbl_yaw, 2, 1)

        main_layout.addWidget(rpy_group)
        main_layout.addStretch()

    def update_telemetry(self, state):
        """Memperbarui UI panel dengan data dari object ROVState."""
        # Mode & Armed
        self.lbl_mode.setText(str(state.mode).upper())
        if state.armed:
            self.lbl_armed.setText("ARMED")
            self.lbl_armed.setStyleSheet("background-color: #1a2e1e; border: 1px solid #40bf6a; border-radius: 6px; font-size: 15px; font-weight: bold; padding: 6px; color: #40bf6a;")
        else:
            self.lbl_armed.setText("DISARMED")
            self.lbl_armed.setStyleSheet("background-color: #2e1a1a; border: 1px solid #ff4d4d; border-radius: 6px; font-size: 15px; font-weight: bold; padding: 6px; color: #ff4d4d;")

        # Depth & Altitude (Dasar Kolam)
        self.lbl_depth_val.setText(f"{state.depth_m:.2f} m")
        self.lbl_alt_val.setText(f"{state.altitude_m:.2f} m")
        
        alt_cm = int(max(0, state.altitude_m * 100))
        self.bar_alt.setValue(min(300, alt_cm))
        if 0 < state.altitude_m < 0.3:
            # Peringatan dekat dasar kolam
            self.lbl_alt_val.setStyleSheet("color: #ff3b30; font-weight: bold; font-size: 18px;")
            self.bar_alt.setStyleSheet("""
                QProgressBar { background-color: #2e1212; border: 1px solid #ff3b30; border-radius: 5px; text-align: center; color: #ffffff; font-size: 11px; }
                QProgressBar::chunk { background-color: #ff3b30; border-radius: 4px; }
            """)
        else:
            self.lbl_alt_val.setStyleSheet("color: #40bf6a; font-weight: bold; font-size: 18px;")
            self.bar_alt.setStyleSheet("""
                QProgressBar { background-color: #121824; border: 1px solid #2d3e5c; border-radius: 5px; text-align: center; color: #ffffff; font-size: 11px; }
                QProgressBar::chunk { background-color: #40bf6a; border-radius: 4px; }
            """)

        # Battery
        self.lbl_bat_val.setText(f"{state.battery_voltage:.1f} V")
        bat_pct = max(0, min(100, int(state.battery_percent))) if state.battery_percent >= 0 else 0
        self.bar_battery.setValue(bat_pct)

        # RPY
        self.lbl_roll.setText(f"{state.roll:+.1f}°")
        self.lbl_pitch.setText(f"{state.pitch:+.1f}°")
        self.lbl_yaw.setText(f"{state.yaw:.1f}°")
