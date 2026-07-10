from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QGroupBox, QTabWidget, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, QThread, QTimer, QDateTime
from PySide6.QtGui import QIcon

from widgets import (
    AttitudeIndicator, CompassIndicator, TelemetryPanel,
    ControlPanel, VideoPanel, LogPanel, QRPanel,
    TrajectoryPanel, DesignROVPanel
)
from worker import ROVWorker, DualVideoReceiverManager, JoystickWorker
from styles import DARK_HUD_THEME


class MainWindow(QMainWindow):
    """
    Jendela Utama (Cockpit Dashboard) GUI Base Station ROV.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BASE STATION ROV - COMMAND & CONTROL COCKPIT v2.0")
        self.setMinimumSize(1350, 820)
        self.setStyleSheet(DARK_HUD_THEME)

        self._init_ui()
        self._init_worker()
        self._init_clock()

    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # === TOP HEADER BAR ===
        header_layout = QHBoxLayout()
        
        self.lbl_title = QLabel(" BASE STATION ROV // COMMAND COCKPIT")
        self.lbl_title.setObjectName("header_label")
        
        # Banner Nama TIM & Perguruan Tinggi
        self.lbl_team = QLabel("ROBOTIKA TIM 2 ROV | UNIVERSITAS MUHAMMADIYAH MALANG")
        self.lbl_team.setObjectName("header_team")
        self.lbl_team.setToolTip("Bosku bisa mengedit/menyesuaikan nama tim & kampus ini.")
        
        # Waktu Lengkap (Hari, Tanggal Bulan Tahun | Jam:Menit:Detik)
        self.lbl_clock = QLabel(" WAKTU: Menghubungkan jam...")
        self.lbl_clock.setStyleSheet("font-size: 13px; font-weight: bold; color: #00e5ff; background-color: #171f2e; padding: 6px 14px; border: 1px solid #28354d; border-radius: 5px;")

        header_layout.addWidget(self.lbl_title, alignment=Qt.AlignVCenter)
        header_layout.addStretch()
        header_layout.addWidget(self.lbl_team, alignment=Qt.AlignVCenter)
        header_layout.addStretch()
        header_layout.addWidget(self.lbl_clock, alignment=Qt.AlignVCenter)
        main_layout.addLayout(header_layout, 0)

        # === MAIN SPLITTER (LEFT / CENTER / RIGHT) ===
        main_splitter = QSplitter(Qt.Horizontal)

        # 1. LEFT COLUMN: Kontrol & Status (Tanpa scroll area)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        
        self.control_panel = ControlPanel()
        left_layout.addWidget(self.control_panel)
        
        left_widget.setMinimumWidth(340)
        left_widget.setMaximumWidth(420)
        main_splitter.addWidget(left_widget)

        # 2. CENTER COLUMN: Multi-Tab Dashboard (Dual Camera, Trajectory Map, 3D Design)
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)

        self.center_tabs = QTabWidget()
        self.center_tabs.setTabPosition(QTabWidget.North)

        # TAB 1: Dual Display Camera + HUD Instruments & Telemetry
        tab_cam_widget = QWidget()
        tab_cam_layout = QVBoxLayout(tab_cam_widget)
        tab_cam_layout.setContentsMargins(4, 8, 4, 4)
        tab_cam_layout.setSpacing(8)

        self.video_panel = VideoPanel()  # 2 Display Camera
        tab_cam_layout.addWidget(self.video_panel, stretch=3)

        self.telemetry_panel = TelemetryPanel()

        # HUD Group with constrained height
        hud_group = QGroupBox("NAVIGATION HUD (6-DOF)")
        hud_layout = QHBoxLayout(hud_group)
        hud_layout.setContentsMargins(8, 18, 8, 8)
        hud_layout.setSpacing(20)

        self.attitude_indicator = AttitudeIndicator()
        self.attitude_indicator.setMaximumSize(180, 180)

        self.compass_indicator = CompassIndicator()
        self.compass_indicator.setMaximumSize(180, 180)

        hud_layout.addStretch()
        hud_layout.addWidget(self.attitude_indicator)
        hud_layout.addWidget(self.compass_indicator)
        hud_layout.addStretch()

        # Bottom dashboard as a widget with fixed max height
        bottom_dashboard_widget = QWidget()
        bottom_dashboard_widget.setMaximumHeight(230)
        bottom_dashboard_layout = QHBoxLayout(bottom_dashboard_widget)
        bottom_dashboard_layout.setContentsMargins(0, 0, 0, 0)
        bottom_dashboard_layout.setSpacing(10)

        bottom_dashboard_layout.addWidget(hud_group, stretch=2)
        bottom_dashboard_layout.addWidget(self.telemetry_panel, stretch=5)

        tab_cam_layout.addWidget(bottom_dashboard_widget)
        self.center_tabs.addTab(tab_cam_widget, " 2 CH CAMERA FEED & HUD")

        # TAB 2: Trajectory Tracker
        self.trajectory_panel = TrajectoryPanel()
        self.center_tabs.addTab(self.trajectory_panel, " TRAJECTORY TRACKER")

        # TAB 3: Gambar Design ROV (Nanti saja placeholder)
        self.design_panel = DesignROVPanel()
        self.center_tabs.addTab(self.design_panel, " GAMBAR DESIGN ROV (PLACEHOLDER)")

        center_layout.addWidget(self.center_tabs)
        main_splitter.addWidget(center_widget)

        # 3. RIGHT COLUMN: QR Code Decoder & Log Console
        right_splitter = QSplitter(Qt.Vertical)
        
        self.qr_panel = QRPanel()
        self.log_panel = LogPanel()
        
        right_splitter.addWidget(self.qr_panel)
        right_splitter.addWidget(self.log_panel)
        right_splitter.setSizes([320, 360])
        
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(right_splitter)
        right_widget.setMinimumWidth(320)
        right_widget.setMaximumWidth(420)
        main_splitter.addWidget(right_widget)

        # Proporsi awal splitter kanan-kiri
        main_splitter.setSizes([360, 640, 350])
        main_layout.addWidget(main_splitter, 1)

    def _init_worker(self):
        self.worker = ROVWorker()
        self.worker_thread = QThread(self)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.start()

        # Connect UI signals ke Worker methods
        self.control_panel.sig_connect_requested.connect(self.worker.connect_rov)
        self.control_panel.sig_disconnect_requested.connect(self.worker.disconnect_rov)
        self.control_panel.sig_arm_requested.connect(self.worker.set_armed)
        self.control_panel.sig_mode_requested.connect(self.worker.set_mode)

        # Connect Worker signals ke UI updates
        self.worker.sig_log.connect(self.log_panel.append_log)
        self.worker.sig_connected.connect(self._on_connection_changed)
        self.worker.sig_state_updated.connect(self._on_state_updated)

        # Inisialisasi & Start UDP Video Stream Receiver (CAM 1, CAM 2, & QR Crop)
        self.video_receivers = DualVideoReceiverManager(port_cam1=9002, port_cam2=9003, port_qr=9004, parent=self)
        self.worker.sig_target_ip_changed.connect(self.video_receivers.set_target_ip)
        self.video_receivers.sig_frame_cam1.connect(self.video_panel.update_cam1_frame)
        self.video_receivers.sig_frame_cam2.connect(self.video_panel.update_cam2_frame)
        self.video_receivers.sig_frame_qr.connect(self.qr_panel.set_qr_image)
        self.video_receivers.sig_log.connect(self.log_panel.append_log)
        self.video_receivers.start_all()

        # Inisialisasi & Start USB Joystick Worker
        self.joystick_worker = JoystickWorker(self)
        self.joystick_worker.sig_log.connect(self.log_panel.append_log)
        self.joystick_worker.sig_joystick_status.connect(self.control_panel.set_joystick_status)
        self.joystick_worker.sig_manual_control.connect(self._on_joystick_control)
        self.joystick_worker.sig_arm_toggled.connect(lambda: self.worker.set_armed(True))
        self.joystick_worker.sig_disarm_toggled.connect(lambda: self.worker.set_armed(False))
        self.control_panel.sig_joystick_enable_toggled.connect(self.joystick_worker.set_enabled)
        self.joystick_worker.start()

        self.log_panel.append_log("Cockpit GUI v2.0 siap. Dual Camera, QR Decoder, & USB Joystick siap.", "INFO")

    def _init_clock(self):
        self.clock_timer = QTimer(self)
        self.clock_timer.setInterval(1000)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start()
        self._update_clock()

    def _update_clock(self):
        dt = QDateTime.currentDateTime()
        days = ["Minggu", "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"]
        months = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
        
        day_name = days[dt.date().dayOfWeek() % 7]
        month_name = months[dt.date().month() - 1]
        
        formatted = f"{day_name}, {dt.date().day():02d} {month_name} {dt.date().year()} | {dt.time().toString('HH:mm:ss')} WIB"
        self.lbl_clock.setText(f" {formatted}")

    def _on_connection_changed(self, connected: bool):
        self.control_panel.set_connected_state(connected)
        self.video_panel.set_streaming_state(connected)

    def _on_state_updated(self, state):
        # Update Telemetri & Altimeter Dasar Kolam
        self.telemetry_panel.update_telemetry(state)
        self.control_panel.update_status(state.mode, state.armed)

        # Update HUD Instruments (Roll, Pitch, Yaw)
        self.attitude_indicator.set_attitude(state.roll, state.pitch)
        self.compass_indicator.set_yaw(state.yaw)

        # Update Trajectory Path Tracker
        self.trajectory_panel.update_trajectory(state)

        # Update QR Code hasil pembacaan jika ada QR baru
        if getattr(state, 'qr_last_code', ''):
            import time
            import base64
            from PySide6.QtGui import QPixmap
            time_str = ""
            if getattr(state, 'qr_last_time', 0.0) > 0:
                time_str = time.strftime('%H:%M:%S', time.localtime(state.qr_last_time))
            
            pixmap = None
            qr_img_str = getattr(state, 'qr_last_image', '')
            if qr_img_str:
                try:
                    img_data = base64.b64decode(qr_img_str)
                    pix = QPixmap()
                    if pix.loadFromData(img_data):
                        pixmap = pix
                except Exception as e:
                    print(f"[MainWindow WARNING] Gagal decode base64 QR Image: {e}")

            cam_name = getattr(state, 'qr_last_cam', '')
            self.qr_panel.update_qr_data(state.qr_last_code, time_str, cam_name, pixmap)

    def _on_joystick_control(self, x: int, y: int, z: int, r: int, buttons: int):
        self.control_panel.update_joystick_display(x, y, z, r)
        self.worker.send_manual_control(x, y, z, r, buttons)

    def closeEvent(self, event):
        """Clean up threads & MAVLink connection saat aplikasi ditutup."""
        if hasattr(self, 'joystick_worker'):
            self.joystick_worker.stop()
        self.video_receivers.stop_all()
        self.worker.disconnect_rov()
        if self.worker_thread.isRunning():
            self.worker_thread.quit()
            self.worker_thread.wait(1000)
        event.accept()
