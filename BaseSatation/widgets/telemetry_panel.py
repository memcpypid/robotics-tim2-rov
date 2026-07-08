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
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)

        # 1. Left column: depth_group
        depth_group = QGroupBox("DEPTH & ALTIMETER")
        depth_layout = QVBoxLayout(depth_group)
        depth_layout.setContentsMargins(12, 18, 12, 12)
        depth_layout.setSpacing(10)

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
        self.lbl_alt_val.setStyleSheet("color: #40bf6a; font-weight: bold; font-size: 13px;")
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

        main_layout.addWidget(depth_group, stretch=1)

        # 2. Right column stacked: power_group & rpy_group
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        power_group = QGroupBox("BATTERY & POWER")
        power_layout = QVBoxLayout(power_group)
        power_layout.setContentsMargins(12, 18, 12, 12)
        power_layout.setSpacing(10)

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

        right_layout.addWidget(power_group)

        rpy_group = QGroupBox("ATTITUDE (6-DOF)")
        rpy_layout = QGridLayout(rpy_group)
        rpy_layout.setContentsMargins(12, 18, 12, 12)
        rpy_layout.setSpacing(10)

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

        right_layout.addWidget(rpy_group)
        main_layout.addLayout(right_layout, stretch=1)

    def update_telemetry(self, state):
        """Memperbarui UI panel dengan data dari object ROVState."""
        # Depth & Altitude (Dasar Kolam)
        self.lbl_depth_val.setText(f"{state.depth_m:.2f} m")
        self.lbl_alt_val.setText(f"{state.altitude_m:.2f} m")
        
        alt_cm = int(max(0, state.altitude_m * 100))
        self.bar_alt.setValue(min(300, alt_cm))
        if 0 < state.altitude_m < 0.3:
            # Peringatan dekat dasar kolam
            self.lbl_alt_val.setStyleSheet("color: #ff3b30; font-weight: bold; font-size: 13px;")
            self.bar_alt.setStyleSheet("""
                QProgressBar { background-color: #2e1212; border: 1px solid #ff3b30; border-radius: 5px; text-align: center; color: #ffffff; font-size: 11px; }
                QProgressBar::chunk { background-color: #ff3b30; border-radius: 4px; }
            """)
        else:
            self.lbl_alt_val.setStyleSheet("color: #40bf6a; font-weight: bold; font-size: 13px;")
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
