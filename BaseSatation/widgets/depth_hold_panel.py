from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QDoubleSpinBox, QGroupBox, QFormLayout
)
from PySide6.QtCore import Signal, Qt
from styles import DARK_HUD_THEME

class DepthHoldPanel(QWidget):
    """
    Panel untuk mengontrol dan memonitor Custom Depth Hold GY-MS5803-01BA.
    """
    sig_pid_changed = Signal(float, float, float)
    sig_toggle = Signal(bool)
    sig_calibrate = Signal()
    sig_target_changed = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(DARK_HUD_THEME)
        
        self.is_active = False
        self.current_depth = 0.0
        self.target_depth = 0.0
        
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 1. Status & Monitor Group
        monitor_group = QGroupBox("DEPTH MONITOR (MS5803)")
        monitor_layout = QHBoxLayout(monitor_group)
        
        self.lbl_current_depth = QLabel("Current Depth: 0.00 m")
        self.lbl_current_depth.setStyleSheet("font-size: 24px; font-weight: bold; color: #00e5ff;")
        
        self.lbl_target_depth = QLabel("Target Depth: 0.00 m")
        self.lbl_target_depth.setStyleSheet("font-size: 24px; font-weight: bold; color: #ff3366;")
        
        monitor_layout.addWidget(self.lbl_current_depth)
        monitor_layout.addWidget(self.lbl_target_depth)
        
        # 2. Control & Calibration Group
        control_group = QGroupBox("CONTROLS")
        control_layout = QHBoxLayout(control_group)
        
        self.btn_toggle = QPushButton("ENABLE DEPTH HOLD")
        self.btn_toggle.setStyleSheet("background-color: #333333; color: white; padding: 10px; font-weight: bold;")
        self.btn_toggle.clicked.connect(self._on_toggle_clicked)
        
        self.btn_calibrate = QPushButton("CALIBRATE SENSOR")
        self.btn_calibrate.setStyleSheet("background-color: #d98cb3; color: black; padding: 10px; font-weight: bold;")
        self.btn_calibrate.clicked.connect(self.sig_calibrate.emit)
        
        control_layout.addWidget(self.btn_toggle)
        control_layout.addWidget(self.btn_calibrate)
        
        # 3. PID Tuning Group
        pid_group = QGroupBox("PID TUNING")
        pid_layout = QFormLayout(pid_group)
        
        self.spin_p = QDoubleSpinBox()
        self.spin_p.setRange(0, 1000)
        self.spin_p.setValue(100.0)
        
        self.spin_i = QDoubleSpinBox()
        self.spin_i.setRange(0, 1000)
        self.spin_i.setValue(10.0)
        
        self.spin_d = QDoubleSpinBox()
        self.spin_d.setRange(0, 1000)
        self.spin_d.setValue(5.0)
        
        self.btn_apply_pid = QPushButton("APPLY PID")
        self.btn_apply_pid.setStyleSheet("background-color: #4CAF50; color: white;")
        self.btn_apply_pid.clicked.connect(self._on_apply_pid)
        
        pid_layout.addRow("Kp (Proportional):", self.spin_p)
        pid_layout.addRow("Ki (Integral):", self.spin_i)
        pid_layout.addRow("Kd (Derivative):", self.spin_d)
        pid_layout.addRow("", self.btn_apply_pid)
        
        # Combine
        main_layout.addWidget(monitor_group)
        main_layout.addWidget(control_group)
        main_layout.addWidget(pid_group)
        main_layout.addStretch()

    def _on_toggle_clicked(self):
        self.is_active = not self.is_active
        if self.is_active:
            self.btn_toggle.setText("DISABLE DEPTH HOLD")
            self.btn_toggle.setStyleSheet("background-color: #ff3366; color: white; padding: 10px; font-weight: bold;")
            # Set target depth to current immediately
            self.target_depth = self.current_depth
            self.sig_target_changed.emit(self.target_depth)
            self._update_labels()
        else:
            self.btn_toggle.setText("ENABLE DEPTH HOLD")
            self.btn_toggle.setStyleSheet("background-color: #333333; color: white; padding: 10px; font-weight: bold;")
        self.sig_toggle.emit(self.is_active)

    def _on_apply_pid(self):
        self.sig_pid_changed.emit(self.spin_p.value(), self.spin_i.value(), self.spin_d.value())

    def update_depth(self, current_depth: float):
        """Called frequently by state update to update the UI."""
        self.current_depth = current_depth
        self._update_labels()

    def set_target_depth(self, target: float):
        """Called if joystick adjusts the target depth."""
        self.target_depth = target
        self._update_labels()
        self.sig_target_changed.emit(self.target_depth)

    def _update_labels(self):
        self.lbl_current_depth.setText(f"Current Depth: {self.current_depth:.2f} m")
        self.lbl_target_depth.setText(f"Target Depth: {self.target_depth:.2f} m")
