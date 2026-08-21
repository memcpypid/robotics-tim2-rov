from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QGroupBox, QProgressBar
)
from PySide6.QtCore import Qt


class TelemetryPanel(QWidget):
    """
    Panel Telemetri Digital Base Station ROV (Kedalaman, Altimeter, Baterai, & Attitude 6-DOF).
    Disatukan dalam 1 Panel Utama yang Rapi & Estetis.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Single Unified GroupBox
        group = QGroupBox("ROV TELEMETRY, DEPTH & POWER STATUS")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 16, 10, 10)
        layout.setSpacing(8)

        # Grid Atas: Depth, Altimeter & Battery
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(4)

        # Row 0: Depth & Battery Voltage
        grid.addWidget(QLabel("Kedalaman:"), 0, 0)
        self.lbl_depth_val = QLabel("0.00 m")
        self.lbl_depth_val.setStyleSheet("color: #00e5ff; font-weight: bold; font-size: 16px;")
        grid.addWidget(self.lbl_depth_val, 0, 1)

        grid.addWidget(QLabel("Tegangan Baterai:"), 0, 2)
        self.lbl_bat_val = QLabel("0.0 V")
        self.lbl_bat_val.setStyleSheet("color: #ffd54f; font-weight: bold; font-size: 16px;")
        grid.addWidget(self.lbl_bat_val, 0, 3)

        # Row 1: Altimeter & Battery Progress Bar
        grid.addWidget(QLabel("Tinggi Dasar:"), 1, 0)
        self.lbl_alt_val = QLabel("0.00 m")
        self.lbl_alt_val.setStyleSheet("color: #40bf6a; font-weight: bold; font-size: 16px;")
        grid.addWidget(self.lbl_alt_val, 1, 1)

        self.bar_battery = QProgressBar()
        self.bar_battery.setRange(0, 100)
        self.bar_battery.setValue(0)
        self.bar_battery.setFixedHeight(18)
        self.bar_battery.setFormat("Baterai: %p%")
        self.bar_battery.setStyleSheet("""
            QProgressBar { background-color: #121824; border: 1px solid #2d3e5c; border-radius: 4px; text-align: center; color: #ffffff; font-size: 10px; font-weight: bold; }
            QProgressBar::chunk { background-color: #ffd54f; border-radius: 3px; }
        """)
        grid.addWidget(self.bar_battery, 1, 2, 1, 2)

        # Row 2: Altimeter Clearance Bar
        self.bar_alt = QProgressBar()
        self.bar_alt.setRange(0, 300)  # max 300 cm / 3 m clearance
        self.bar_alt.setValue(0)
        self.bar_alt.setFixedHeight(18)
        self.bar_alt.setFormat("Altimeter Clearance: %v cm")
        self.bar_alt.setStyleSheet("""
            QProgressBar { background-color: #121824; border: 1px solid #2d3e5c; border-radius: 4px; text-align: center; color: #ffffff; font-size: 10px; font-weight: bold; }
            QProgressBar::chunk { background-color: #40bf6a; border-radius: 3px; }
        """)
        grid.addWidget(self.bar_alt, 2, 0, 1, 4)

        layout.addLayout(grid)

        # Baris Bawah: Attitude RPY 6-DOF
        rpy_box = QHBoxLayout()
        rpy_box.setContentsMargins(0, 4, 0, 0)
        rpy_box.setSpacing(12)

        lbl_rpy_title = QLabel("ATTITUDE 6-DOF:")
        lbl_rpy_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #899cb8;")
        rpy_box.addWidget(lbl_rpy_title)

        self.lbl_roll = QLabel("Roll: +0.0°")
        self.lbl_roll.setStyleSheet("color: #00e5ff; font-weight: bold; font-size: 12px;")
        rpy_box.addWidget(self.lbl_roll)

        self.lbl_pitch = QLabel("Pitch: +0.0°")
        self.lbl_pitch.setStyleSheet("color: #00e5ff; font-weight: bold; font-size: 12px;")
        rpy_box.addWidget(self.lbl_pitch)

        self.lbl_yaw = QLabel("Yaw: 0.0°")
        self.lbl_yaw.setStyleSheet("color: #40bf6a; font-weight: bold; font-size: 12px;")
        rpy_box.addWidget(self.lbl_yaw)

        rpy_box.addStretch()
        layout.addLayout(rpy_box)

        main_layout.addWidget(group)

    def update_telemetry(self, state):
        """Memperbarui UI panel dengan data dari object ROVState."""
        # Depth & Altitude (Dasar Kolam)
        self.lbl_depth_val.setText(f"{state.depth_m:.2f} m")
        self.lbl_alt_val.setText(f"{state.altitude_m:.2f} m")
        
        alt_cm = int(max(0, state.altitude_m * 100))
        self.bar_alt.setValue(min(300, alt_cm))
        if 0 < state.altitude_m < 0.3:
            # Peringatan dekat dasar kolam
            self.lbl_alt_val.setStyleSheet("color: #ff3b30; font-weight: bold; font-size: 16px;")
            self.bar_alt.setStyleSheet("""
                QProgressBar { background-color: #2e1212; border: 1px solid #ff3b30; border-radius: 4px; text-align: center; color: #ffffff; font-size: 10px; font-weight: bold; }
                QProgressBar::chunk { background-color: #ff3b30; border-radius: 3px; }
            """)
        else:
            self.lbl_alt_val.setStyleSheet("color: #40bf6a; font-weight: bold; font-size: 16px;")
            self.bar_alt.setStyleSheet("""
                QProgressBar { background-color: #121824; border: 1px solid #2d3e5c; border-radius: 4px; text-align: center; color: #ffffff; font-size: 10px; font-weight: bold; }
                QProgressBar::chunk { background-color: #40bf6a; border-radius: 3px; }
            """)

        # Battery
        self.lbl_bat_val.setText(f"{state.battery_voltage:.1f} V")
        bat_pct = max(0, min(100, int(state.battery_percent))) if state.battery_percent >= 0 else 0
        self.bar_battery.setValue(bat_pct)

        # RPY
        self.lbl_roll.setText(f"Roll: {state.roll:+.1f}°")
        self.lbl_pitch.setText(f"Pitch: {state.pitch:+.1f}°")
        self.lbl_yaw.setText(f"Yaw: {state.yaw:.1f}°")


