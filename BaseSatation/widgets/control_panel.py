from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QGroupBox, QPushButton, QComboBox, QLineEdit
)
from PySide6.QtCore import Qt, Signal


class ControlPanel(QWidget):
    """
    Panel Kontrol Operasional ROV (Koneksi LAN/WiFi Jetson Nano, Arming/Disarming, Mode Flight).
    """
    sig_connect_requested = Signal(str, int)  # (ip_address, baudrate_placeholder=0)
    sig_disconnect_requested = Signal()
    sig_arm_requested = Signal(bool)          # True untuk Arm, False untuk Disarm
    sig_mode_requested = Signal(str)          # ("MANUAL", "STABILIZE", "DEPTH_HOLD")
    sig_joystick_enable_toggled = Signal(bool)# True untuk enable joystick, False untuk disable
    sig_auto_mode_toggled = Signal(bool)     # True = Autonomous Mode, False = Manual

    def __init__(self, parent=None):
        super().__init__(parent)
        self._auto_mode = False
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(10)

        # 0. Groupbox Status Utama (Mode & Armed status)
        status_group = QGroupBox("FLIGHT & ARM STATUS")
        status_layout = QHBoxLayout(status_group)
        status_layout.setContentsMargins(12, 18, 12, 12)
        status_layout.setSpacing(10)

        self.lbl_mode = QLabel("MANUAL")
        self.lbl_mode.setAlignment(Qt.AlignCenter)
        self.lbl_mode.setStyleSheet("background-color: #202d42; border: 1px solid #00e5ff; border-radius: 6px; font-size: 15px; font-weight: bold; padding: 6px; color: #00e5ff;")

        self.lbl_armed = QLabel("DISARMED")
        self.lbl_armed.setAlignment(Qt.AlignCenter)
        self.lbl_armed.setStyleSheet("background-color: #2e1a1a; border: 1px solid #ff4d4d; border-radius: 6px; font-size: 15px; font-weight: bold; padding: 6px; color: #ff4d4d;")

        status_layout.addWidget(self.lbl_mode)
        status_layout.addWidget(self.lbl_armed)
        main_layout.addWidget(status_group)

        # 1. Groupbox Autonomous Control Toggle
        auto_group = QGroupBox("AUTONOMOUS / VISION CONTROL")
        auto_layout = QVBoxLayout(auto_group)
        auto_layout.setContentsMargins(12, 18, 12, 12)
        auto_layout.setSpacing(8)

        self.btn_auto_toggle = QPushButton("MODE MANUAL (JOYSTICK)")
        self.btn_auto_toggle.setCheckable(True)
        self.btn_auto_toggle.setStyleSheet("""
            QPushButton { background-color: #1a2736; color: #00e5ff; font-weight: bold; padding: 8px; border: 1px solid #00e5ff; border-radius: 5px; }
            QPushButton:checked { background-color: #d35400; color: #ffffff; border: 1px solid #e67e22; }
        """)
        self.btn_auto_toggle.clicked.connect(self._on_auto_toggled)
        auto_layout.addWidget(self.btn_auto_toggle)

        self.lbl_auto_mode = QLabel(" Status Kendali: MANUAL JOYSTICK")
        self.lbl_auto_mode.setStyleSheet("font-size: 11px; color: #40bf6a; font-weight: bold;")
        auto_layout.addWidget(self.lbl_auto_mode)
        main_layout.addWidget(auto_group)

        # 2. Groupbox Arming & Safety
        arm_group = QGroupBox("THRUSTER ARMING")
        arm_layout = QVBoxLayout(arm_group)
        arm_layout.setContentsMargins(12, 18, 12, 12)

        self.btn_arm = QPushButton("DISARMED (CLICK TO ARM)")
        self.btn_arm.setObjectName("btn_arm")
        self.btn_arm.setCheckable(True)
        self.btn_arm.setEnabled(False)  # Baru aktif setelah koneksi tersambung
        self.btn_arm.clicked.connect(self._on_arm_toggled)
        arm_layout.addWidget(self.btn_arm)

        main_layout.addWidget(arm_group)

        # 3. Groupbox Flight Modes
        mode_group = QGroupBox("FLIGHT MODES")
        mode_layout = QGridLayout(mode_group)
        mode_layout.setContentsMargins(12, 18, 12, 12)
        mode_layout.setSpacing(8)

        self.btn_mode_manual = QPushButton("MANUAL")
        self.btn_mode_manual.clicked.connect(lambda: self.sig_mode_requested.emit("MANUAL"))
        
        self.btn_mode_stab = QPushButton("STABILIZE")
        self.btn_mode_stab.clicked.connect(lambda: self.sig_mode_requested.emit("STABILIZE"))
        
        self.btn_mode_depth = QPushButton("DEPTH HOLD")
        self.btn_mode_depth.clicked.connect(lambda: self.sig_mode_requested.emit("DEPTH_HOLD"))

        mode_layout.addWidget(self.btn_mode_manual, 0, 0)
        mode_layout.addWidget(self.btn_mode_stab, 0, 1)
        mode_layout.addWidget(self.btn_mode_depth, 1, 0, 1, 2)

        for btn in [self.btn_mode_manual, self.btn_mode_stab, self.btn_mode_depth]:
            btn.setEnabled(False)
        self._mode_buttons = [self.btn_mode_manual, self.btn_mode_stab, self.btn_mode_depth]

        main_layout.addWidget(mode_group)


        # 4. Groupbox USB Joystick / Gamepad Control
        joy_group = QGroupBox("USB JOYSTICK / GAMEPAD MANUAL CONTROL")
        joy_layout = QVBoxLayout(joy_group)
        joy_layout.setContentsMargins(12, 18, 12, 12)
        joy_layout.setSpacing(8)

        self.lbl_joystick_status = QLabel(" Status: Tidak Ada Joystick USB Tercolok")
        self.lbl_joystick_status.setStyleSheet("font-size: 11px; color: #899cb8; font-weight: bold;")
        joy_layout.addWidget(self.lbl_joystick_status)

        self.btn_joystick_toggle = QPushButton("ENABLE JOYSTICK CONTROL")
        self.btn_joystick_toggle.setCheckable(True)
        self.btn_joystick_toggle.setChecked(True) # Aktif secara default saat dicolok
        self.btn_joystick_toggle.setStyleSheet("padding: 6px; font-weight: bold;")
        self.btn_joystick_toggle.clicked.connect(lambda checked: self.sig_joystick_enable_toggled.emit(checked))
        joy_layout.addWidget(self.btn_joystick_toggle)

        self.lbl_joystick_axes = QLabel("Kendali Live: X: 0 | Y: 0 | Z: 500 (Hover) | R: 0")
        self.lbl_joystick_axes.setStyleSheet("font-size: 11px; color: #00e5ff; font-family: Consolas, monospace;")
        joy_layout.addWidget(self.lbl_joystick_axes)

        main_layout.addWidget(joy_group)

    def set_joystick_status(self, connected: bool, device_name: str):
        if connected:
            self.lbl_joystick_status.setText(f" Aktif: {device_name}")
            self.lbl_joystick_status.setStyleSheet("font-size: 11px; color: #40bf6a; font-weight: bold;")
            self.btn_joystick_toggle.setEnabled(True)
        else:
            self.lbl_joystick_status.setText(" Status: Tidak Ada Joystick USB Tercolok")
            self.lbl_joystick_status.setStyleSheet("font-size: 11px; color: #e55039; font-weight: bold;")
            self.lbl_joystick_axes.setText("Kendali Live: X: 0 | Y: 0 | Z: 500 (Hover) | R: 0")

    def update_joystick_display(self, x: int, y: int, z: int, r: int):
        self.lbl_joystick_axes.setText(f"Kendali Live: X:{x:+4d} | Y:{y:+4d} | Z:{z:4d} | R:{r:+4d}")

    def _on_auto_toggled(self, checked: bool):
        self.set_auto_mode_state(checked)
        self.sig_auto_mode_toggled.emit(checked)

    def set_auto_mode_state(self, is_auto: bool):
        self._auto_mode = is_auto
        self.btn_auto_toggle.setChecked(is_auto)
        if is_auto:
            self.btn_auto_toggle.setText("MODE AUTONOMOUS (VISION)")
            self.lbl_auto_mode.setText(" Status Kendali: AUTONOMOUS / VISION")
            self.lbl_auto_mode.setStyleSheet("font-size: 11px; color: #e67e22; font-weight: bold;")
        else:
            self.btn_auto_toggle.setText("MODE MANUAL (JOYSTICK)")
            self.lbl_auto_mode.setText(" Status Kendali: MANUAL JOYSTICK")
            self.lbl_auto_mode.setStyleSheet("font-size: 11px; color: #40bf6a; font-weight: bold;")

    def _on_arm_toggled(self, checked):
        if checked:
            self.btn_arm.setText("SENDING ARM...")
            self.sig_arm_requested.emit(True)
        else:
            self.btn_arm.setText("SENDING DISARM...")
            self.sig_arm_requested.emit(False)

    def set_connected_state(self, connected: bool):
        if connected:
            self.btn_arm.setEnabled(True)
            for btn in self._mode_buttons:
                btn.setEnabled(True)
        else:
            self.btn_arm.setChecked(False)
            self.btn_arm.setText("DISARMED (CLICK TO ARM)")
            self.btn_arm.setEnabled(False)
            for btn in self._mode_buttons:
                btn.setEnabled(False)


    def set_armed_state(self, armed: bool):
        self.btn_arm.setChecked(armed)
        if armed:
            self.btn_arm.setText(" ARMED (THRUSTERS LIVE) ")
            self.lbl_armed.setText("ARMED")
            self.lbl_armed.setStyleSheet("background-color: #1a2e1e; border: 1px solid #40bf6a; border-radius: 6px; font-size: 15px; font-weight: bold; padding: 6px; color: #40bf6a;")
        else:
            self.btn_arm.setText("DISARMED (CLICK TO ARM)")
            self.lbl_armed.setText("DISARMED")
            self.lbl_armed.setStyleSheet("background-color: #2e1a1a; border: 1px solid #ff4d4d; border-radius: 6px; font-size: 15px; font-weight: bold; padding: 6px; color: #ff4d4d;")

    def update_status(self, mode: str, armed: bool):
        self.lbl_mode.setText(str(mode).upper())
        self.set_armed_state(armed)
