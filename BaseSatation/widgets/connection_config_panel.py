from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QGroupBox, QPushButton, QComboBox, QLineEdit, QFrame
)
from PySide6.QtCore import Qt, Signal


class ConnectionConfigPanel(QWidget):
    """
    Panel Halaman Konfigurasi Koneksi Sistem (Jetson Nano, Image Processing, & Mode Autonomous).
    """
    sig_connect_requested = Signal(str, int)     # (ip_address, baudrate=0)
    sig_disconnect_requested = Signal()
    sig_auto_mode_toggled = Signal(bool)         # True = Autonomous Mode, False = Manual Joystick Mode

    def __init__(self, parent=None):
        super().__init__(parent)
        self._auto_mode = False
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # ── Title & Intro ──
        lbl_title = QLabel("SYSTEM CONNECTION & AUTONOMOUS CONTROL CONFIGURATION")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #00e5ff;")
        main_layout.addWidget(lbl_title)

        grid_layout = QGridLayout()
        grid_layout.setSpacing(16)

        # ── 1. Groupbox Network Connection (Flight Control / Jetson Nano) ──
        conn_group = QGroupBox("KONEKSI JETSON NANO / FLIGHT CONTROL (UDP PORT 9000/9001)")
        conn_layout = QVBoxLayout(conn_group)
        conn_layout.setContentsMargins(16, 22, 16, 16)
        conn_layout.setSpacing(12)

        lbl_desc1 = QLabel("Pengaturan IP Address tujuan untuk telemetry stream (Port 9000) dan command control (Port 9001).")
        lbl_desc1.setWordWrap(True)
        lbl_desc1.setStyleSheet("color: #899cb8; font-size: 12px;")
        conn_layout.addWidget(lbl_desc1)

        row_ip = QHBoxLayout()
        row_ip.addWidget(QLabel("IP Address Target:"))
        self.combo_target = QComboBox()
        self.combo_target.addItems([
            "127.0.0.1",         # Localhost
            "192.168.2.2",       # BlueROV Default
            "192.168.1.100",
            "192.168.43.149",
            "10.0.0.2"
        ])
        self.combo_target.setEditable(True)
        self.combo_target.setStyleSheet("padding: 6px; font-weight: bold;")
        row_ip.addWidget(self.combo_target, stretch=1)
        conn_layout.addLayout(row_ip)

        self.btn_connect = QPushButton("CONNECT TO JETSON NANO")
        self.btn_connect.setStyleSheet("background-color: #1565c0; color: white; font-weight: bold; padding: 10px; font-size: 13px;")
        self.btn_connect.setCheckable(True)
        self.btn_connect.clicked.connect(self._on_connect_toggled)
        conn_layout.addWidget(self.btn_connect)

        self.lbl_conn_status = QLabel("Status Koneksi: TERPUTUS")
        self.lbl_conn_status.setStyleSheet("color: #ff4d4d; font-weight: bold;")
        conn_layout.addWidget(self.lbl_conn_status)

        grid_layout.addWidget(conn_group, 0, 0)

        # ── 2. Groupbox Mode Kontrol (Manual vs Autonomous) ──
        auto_group = QGroupBox("AUTONOMOUS MODE CONTROL")
        auto_layout = QVBoxLayout(auto_group)
        auto_layout.setContentsMargins(16, 22, 16, 16)
        auto_layout.setSpacing(12)

        lbl_desc2 = QLabel("Sakelar utama peralihan mode. Mode Autonomous akan menyerahkan kendali gerakan (X,Y,Z,R) ke modul Vision / ImageProcessing.")
        lbl_desc2.setWordWrap(True)
        lbl_desc2.setStyleSheet("color: #899cb8; font-size: 12px;")
        auto_layout.addWidget(lbl_desc2)

        self.btn_auto_toggle = QPushButton(" Mode Manual Active (Click to Activate Autonomous)")
        self.btn_auto_toggle.setCheckable(True)
        self.btn_auto_toggle.setStyleSheet("""
            QPushButton { background-color: #1f2c40; color: #00e5ff; font-weight: bold; padding: 12px; font-size: 14px; border: 2px solid #00e5ff; border-radius: 6px; }
            QPushButton:checked { background-color: #d35400; color: #ffffff; border: 2px solid #e67e22; }
        """)
        self.btn_auto_toggle.clicked.connect(self._on_auto_toggled)
        auto_layout.addWidget(self.btn_auto_toggle)

        self.lbl_auto_status = QLabel(" Mode Aktif: MANUAL (Joystick Memegang Kendali)")
        self.lbl_auto_status.setStyleSheet("color: #40bf6a; font-weight: bold; font-size: 13px;")
        auto_layout.addWidget(self.lbl_auto_status)

        grid_layout.addWidget(auto_group, 0, 1)

        main_layout.addLayout(grid_layout)
        main_layout.addStretch()

    def set_connected_state(self, connected: bool):
        if connected:
            self.btn_connect.setChecked(True)
            self.btn_connect.setText("DISCONNECT FROM JETSON NANO")
            self.btn_connect.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; padding: 10px; font-size: 13px;")
            self.lbl_conn_status.setText("Status Koneksi: TERHUBUNG REALTIME")
            self.lbl_conn_status.setStyleSheet("color: #40bf6a; font-weight: bold;")
        else:
            self.btn_connect.setChecked(False)
            self.btn_connect.setText("CONNECT TO JETSON NANO")
            self.btn_connect.setStyleSheet("background-color: #1565c0; color: white; font-weight: bold; padding: 10px; font-size: 13px;")
            self.lbl_conn_status.setText("Status Koneksi: TERPUTUS")
            self.lbl_conn_status.setStyleSheet("color: #ff4d4d; font-weight: bold;")

    def set_auto_mode_state(self, is_auto: bool):
        self._auto_mode = is_auto
        self.btn_auto_toggle.setChecked(is_auto)
        if is_auto:
            self.btn_auto_toggle.setText("AUTONOMOUS MODE ACTIVE (Click to Switch to Manual)")
            self.lbl_auto_status.setText(" Mode Aktif: AUTONOMOUS (Vision / ImageProcessing Memegang Kendali)")
            self.lbl_auto_status.setStyleSheet("color: #e67e22; font-weight: bold; font-size: 13px;")
        else:
            self.btn_auto_toggle.setText(" Mode Manual Active (Click to Activate Autonomous)")
            self.lbl_auto_status.setText(" Mode Aktif: MANUAL (Joystick Memegang Kendali)")
            self.lbl_auto_status.setStyleSheet("color: #40bf6a; font-weight: bold; font-size: 13px;")

    def _on_connect_toggled(self, checked: bool):
        if checked:
            raw_text = self.combo_target.currentText().strip()
            ip_str = raw_text.split(" ")[0].strip()
            self.sig_connect_requested.emit(ip_str, 0)
        else:
            self.sig_disconnect_requested.emit()

    def _on_auto_toggled(self, checked: bool):
        self.set_auto_mode_state(checked)
        self.sig_auto_mode_toggled.emit(checked)
