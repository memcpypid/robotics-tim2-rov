from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QGroupBox, QTabWidget, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, QThread, QTimer, QDateTime
from PySide6.QtGui import QIcon

from widgets import (
    AttitudeIndicator, CompassIndicator, TelemetryPanel,
    ControlPanel, VideoPanel, LogPanel, QRPanel,
    TrajectoryPanel, DesignROVPanel, MotorPanel,
    ConnectionConfigPanel
)
from widgets.trajectory_panel import TrajectoryCanvas
from widgets.servo_panel import ServoPanel
from widgets.joystick_mapper import JoystickMapperPanel
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
        
        left_widget.setMinimumWidth(330)
        left_widget.setMaximumWidth(400)
        main_splitter.addWidget(left_widget)

        # 2. CENTER COLUMN: Multi-Tab Dashboard (Dual Camera, Connection Config, Trajectory Map, 3D Design)
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)

        self.center_tabs = QTabWidget()
        self.center_tabs.setTabPosition(QTabWidget.North)
        
        # Disable tab switching via mouse wheel
        self.center_tabs.wheelEvent = lambda event: event.ignore()
        if hasattr(self.center_tabs, "tabBar"):
            self.center_tabs.tabBar().wheelEvent = lambda event: event.ignore()

        # TAB 1: Dual Display Camera + HUD Instruments + Mini Trajectory Canvas
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
        hud_layout.setContentsMargins(6, 16, 6, 6)
        hud_layout.setSpacing(10)

        self.attitude_indicator = AttitudeIndicator()
        self.attitude_indicator.setMaximumSize(160, 160)

        self.compass_indicator = CompassIndicator()
        self.compass_indicator.setMaximumSize(160, 160)

        hud_layout.addStretch()
        hud_layout.addWidget(self.attitude_indicator)
        hud_layout.addWidget(self.compass_indicator)
        hud_layout.addStretch()

        # QR Panel ringkas ditaruh di bottom dashboard
        self.qr_panel = QRPanel()

        # Bottom dashboard as a widget with fixed max height
        bottom_dashboard_widget = QWidget()
        bottom_dashboard_widget.setMaximumHeight(240)
        bottom_dashboard_layout = QHBoxLayout(bottom_dashboard_widget)
        bottom_dashboard_layout.setContentsMargins(0, 0, 0, 0)
        bottom_dashboard_layout.setSpacing(8)

        bottom_dashboard_layout.addWidget(hud_group, stretch=2)
        bottom_dashboard_layout.addWidget(self.telemetry_panel, stretch=3)
        bottom_dashboard_layout.addWidget(self.qr_panel, stretch=3)

        tab_cam_layout.addWidget(bottom_dashboard_widget)
        self.center_tabs.addTab(tab_cam_widget, "Dashboard")

        # TAB 2: Connection & Autonomous Config Panel
        self.conn_config_panel = ConnectionConfigPanel()
        self.center_tabs.addTab(self.conn_config_panel, "CONFIG KONEKSI & AUTONOMOUS")

        # TAB 3: Motor Diagnostics
        self.motor_panel = MotorPanel()
        self.center_tabs.addTab(self.motor_panel, "MOTOR DIAGNOSTICS")

        # TAB 4: SERVO CONTROL
        self.servo_panel = ServoPanel()
        self.center_tabs.addTab(self.servo_panel, "SERVO CONTROL")

        # TAB 5: JOYSTICK MAPPER
        self.joystick_mapper = JoystickMapperPanel()
        self.center_tabs.addTab(self.joystick_mapper, "JOYSTICK MAPPER")

        # TAB 6: Gambar Design ROV (Placeholder)
        self.design_panel = DesignROVPanel()
        self.center_tabs.addTab(self.design_panel, "GAMBAR DESIGN ROV")

        center_layout.addWidget(self.center_tabs)
        main_splitter.addWidget(center_widget)

        # 3. RIGHT COLUMN: Live Trajectory Tracker & Log Console (Log Console dibuat ringkas)
        right_splitter = QSplitter(Qt.Vertical)
        
        self.trajectory_panel = TrajectoryPanel()
        self.log_panel = LogPanel()
        self.log_panel.setMaximumHeight(200)  # Memperkecil log telemetry console
        
        right_splitter.addWidget(self.trajectory_panel)
        right_splitter.addWidget(self.log_panel)
        right_splitter.setSizes([480, 200])
        
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(right_splitter)
        right_widget.setMinimumWidth(320)
        right_widget.setMaximumWidth(420)
        main_splitter.addWidget(right_widget)


        # Proporsi awal splitter kanan-kiri
        main_splitter.setSizes([340, 680, 320])
        main_layout.addWidget(main_splitter, 1)

    def _init_worker(self):
        self.worker = ROVWorker(self)

        # Connect UI signals ke Worker methods
        self.control_panel.sig_connect_requested.connect(self.worker.connect_rov)
        self.control_panel.sig_disconnect_requested.connect(self.worker.disconnect_rov)
        self.conn_config_panel.sig_connect_requested.connect(self.worker.connect_rov)
        self.conn_config_panel.sig_disconnect_requested.connect(self.worker.disconnect_rov)

        self.control_panel.sig_arm_requested.connect(self.worker.set_armed)
        self.control_panel.sig_mode_requested.connect(self.worker.set_mode)

        self.control_panel.sig_auto_mode_toggled.connect(self._on_auto_mode_toggled)
        self.conn_config_panel.sig_auto_mode_toggled.connect(self._on_auto_mode_toggled)

        # Connect Worker signals ke UI updates
        self.worker.sig_log.connect(self.log_panel.append_log)
        self.worker.sig_connected.connect(self._on_connection_changed)
        self.worker.sig_state_updated.connect(self._on_state_updated)

        # Connect MotorPanel signals
        self.motor_panel.sig_motor_test.connect(self.worker.send_motor_test)

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
        self.joystick_worker.sig_set_servo.connect(self.worker.send_set_servo)
        self.joystick_worker.sig_auto_toggled.connect(self._on_joystick_auto_toggled)
        self.servo_panel.sig_config_saved.connect(self.joystick_worker.reload_servo_config)
        self.joystick_mapper.sig_config_saved.connect(self.joystick_worker.reload_joystick_config)
        self.joystick_worker.sig_mode_changed.connect(self.worker.set_mode)
        self.control_panel.sig_joystick_enable_toggled.connect(self.joystick_worker.set_enabled)
        self.worker.sig_state_updated.connect(self.joystick_worker.on_state_updated)
        self.joystick_worker.start()

        self.log_panel.append_log("Cockpit GUI v2.0 siap. Dual Camera, Trajectory, QR Decoder, & USB Joystick siap.", "INFO")


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
        self.conn_config_panel.set_connected_state(connected)
        self.video_panel.set_streaming_state(connected)

    def _on_auto_mode_toggled(self, is_auto: bool):
        self.control_panel.set_auto_mode_state(is_auto)
        self.conn_config_panel.set_auto_mode_state(is_auto)
        self.worker.set_auto_mode(is_auto)

    def _on_joystick_auto_toggled(self):
        current_state = self.control_panel._auto_mode
        new_state = not current_state
        self._on_auto_mode_toggled(new_state)

    def _on_state_updated(self, state):
        # Debug logging ke console
        print(f"[MainWindow DEBUG] _on_state_updated dipanggil! Roll={state.roll:.1f} Pitch={state.pitch:.1f} Yaw={state.yaw:.1f}")
        
        # Update Telemetri & Altimeter Dasar Kolam
        self.telemetry_panel.update_telemetry(state)
        self.control_panel.update_status(state.mode, state.armed)

        # Update HUD Instruments (Roll, Pitch, Yaw)
        self.attitude_indicator.set_attitude(state.roll, state.pitch)
        self.compass_indicator.set_yaw(state.yaw)

        # Update Trajectory Path Tracker di Sidebar Kanan
        self.trajectory_panel.update_trajectory(state)



        # Update Motor PWM
        if hasattr(state, 'pwm_outputs'):
            self.motor_panel.update_pwm_data(state.pwm_outputs)

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
        if hasattr(self, 'joystick_mapper'):
            self.joystick_mapper.stop()
        self.video_receivers.stop_all()
        self.worker.disconnect_rov()
        event.accept()
