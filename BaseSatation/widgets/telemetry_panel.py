from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QGroupBox, QProgressBar
)
from PySide6.QtCore import Qt


class TelemetryPanel(QWidget):
    """
    Panel Telemetri Digital Base Station ROV (Kedalaman, Baterai, Status Mode & Arming).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 1. Groupbox Status Utama (Mode & Armed status)
        status_group = QGroupBox("FLIGHT & ARM STATUS")
        status_layout = QHBoxLayout(status_group)

        self.lbl_mode = QLabel("MANUAL")
        self.lbl_mode.setAlignment(Qt.AlignCenter)
        self.lbl_mode.setStyleSheet("background-color: #202d42; border: 1px solid #00e5ff; border-radius: 6px; font-size: 16px; font-weight: bold; padding: 6px; color: #00e5ff;")

        self.lbl_armed = QLabel("DISARMED")
        self.lbl_armed.setAlignment(Qt.AlignCenter)
        self.lbl_armed.setStyleSheet("background-color: #2e1a1a; border: 1px solid #ff4d4d; border-radius: 6px; font-size: 16px; font-weight: bold; padding: 6px; color: #ff4d4d;")

        status_layout.addWidget(self.lbl_mode)
        status_layout.addWidget(self.lbl_armed)
        main_layout.addWidget(status_group)

        # 2. Groupbox Baterai & Kedalaman
        sensors_group = QGroupBox("ENVIRONMENT & POWER")
        sensors_layout = QVBoxLayout(sensors_group)

        # Depth
        depth_layout = QHBoxLayout()
        lbl_depth_title = QLabel("Kedalaman (Depth):")
        self.lbl_depth_val = QLabel("0.00 m")
        self.lbl_depth_val.setObjectName("value_label")
        depth_layout.addWidget(lbl_depth_title)
        depth_layout.addStretch()
        depth_layout.addWidget(self.lbl_depth_val)
        sensors_layout.addLayout(depth_layout)

        # Battery
        bat_layout = QHBoxLayout()
        lbl_bat_title = QLabel("Tegangan Baterai:")
        self.lbl_bat_val = QLabel("0.0 V")
        self.lbl_bat_val.setObjectName("value_label")
        bat_layout.addWidget(lbl_bat_title)
        bat_layout.addStretch()
        bat_layout.addWidget(self.lbl_bat_val)
        sensors_layout.addLayout(bat_layout)

        self.bar_battery = QProgressBar()
        self.bar_battery.setRange(0, 100)
        self.bar_battery.setValue(0)
        self.bar_battery.setFormat("%p%")
        sensors_layout.addWidget(self.bar_battery)

        main_layout.addWidget(sensors_group)

        # 3. Groupbox RPY Detail (Roll Pitch Yaw)
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
            self.lbl_armed.setStyleSheet("background-color: #1a2e1e; border: 1px solid #40bf6a; border-radius: 6px; font-size: 16px; font-weight: bold; padding: 6px; color: #40bf6a;")
        else:
            self.lbl_armed.setText("DISARMED")
            self.lbl_armed.setStyleSheet("background-color: #2e1a1a; border: 1px solid #ff4d4d; border-radius: 6px; font-size: 16px; font-weight: bold; padding: 6px; color: #ff4d4d;")

        # Depth & Battery
        self.lbl_depth_val.setText(f"{state.depth_m:.2f} m")
        self.lbl_bat_val.setText(f"{state.battery_voltage:.1f} V")
        bat_pct = max(0, min(100, int(state.battery_percent))) if state.battery_percent >= 0 else 0
        self.bar_battery.setValue(bat_pct)

        # RPY
        self.lbl_roll.setText(f"{state.roll:+.1f}°")
        self.lbl_pitch.setText(f"{state.pitch:+.1f}°")
        self.lbl_yaw.setText(f"{state.yaw:.1f}°")
