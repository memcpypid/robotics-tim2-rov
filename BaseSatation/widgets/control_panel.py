from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QGroupBox, QPushButton, QComboBox, QLineEdit, QSpinBox
)
from PySide6.QtCore import Qt, Signal


class ControlPanel(QWidget):
    """
    Panel Kontrol Operasional ROV (Koneksi, Arming/Disarming, Pengaturan Mode, Thruster).
    """
    sig_connect_requested = Signal(str, int)  # (connection_string, baudrate)
    sig_disconnect_requested = Signal()
    sig_arm_requested = Signal(bool)          # True untuk Arm, False untuk Disarm
    sig_mode_requested = Signal(str)          # ("MANUAL", "STABILIZE", "DEPTH_HOLD")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 1. Groupbox Koneksi MAVLink
        conn_group = QGroupBox("CONNECTION SETTINGS")
        conn_layout = QVBoxLayout(conn_group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Target / Port:"))
        self.combo_target = QComboBox()
        self.combo_target.addItems([
            "lan:127.0.0.1 (Local JSON Bridge)",
            "lan:192.168.2.2 (Jetson Nano LAN)",
            "udp:127.0.0.1:14550",
            "/dev/ttyACM0",
            "/dev/ttyUSB0"
        ])
        self.combo_target.setEditable(True)
        row1.addWidget(self.combo_target)
        conn_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Baudrate:"))
        self.spin_baud = QComboBox()
        self.spin_baud.addItems(["115200", "57600", "9600", "921600"])
        row2.addWidget(self.spin_baud)
        conn_layout.addLayout(row2)

        self.btn_connect = QPushButton("CONNECT ROV")
        self.btn_connect.setObjectName("btn_connect")
        self.btn_connect.setCheckable(True)
        self.btn_connect.clicked.connect(self._on_connect_toggled)
        conn_layout.addWidget(self.btn_connect)

        main_layout.addWidget(conn_group)

        # 2. Groupbox Arming & Safety
        arm_group = QGroupBox("THRUSTER ARMING")
        arm_layout = QVBoxLayout(arm_group)

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
        main_layout.addStretch()

    def _on_connect_toggled(self, checked):
        if checked:
            conn_str = self.combo_target.currentText().strip()
            baud = int(self.spin_baud.currentText().strip())
            self.btn_connect.setText("CONNECTING...")
            self.sig_connect_requested.emit(conn_str, baud)
        else:
            self.sig_disconnect_requested.emit()

    def _on_arm_toggled(self, checked):
        if checked:
            self.btn_arm.setText("SENDING ARM...")
            self.sig_arm_requested.emit(True)
        else:
            self.btn_arm.setText("SENDING DISARM...")
            self.sig_arm_requested.emit(False)

    def set_connected_state(self, connected: bool):
        if connected:
            self.btn_connect.setChecked(True)
            self.btn_connect.setText("DISCONNECT ROV")
            self.btn_arm.setEnabled(True)
            for btn in self._mode_buttons:
                btn.setEnabled(True)
        else:
            self.btn_connect.setChecked(False)
            self.btn_connect.setText("CONNECT ROV")
            self.btn_arm.setChecked(False)
            self.btn_arm.setText("DISARMED (CLICK TO ARM)")
            self.btn_arm.setEnabled(False)
            for btn in self._mode_buttons:
                btn.setEnabled(False)

    def set_armed_state(self, armed: bool):
        self.btn_arm.setChecked(armed)
        if armed:
            self.btn_arm.setText("⚡ ARMED (THRUSTERS LIVE) ⚡")
        else:
            self.btn_arm.setText("DISARMED (CLICK TO ARM)")
