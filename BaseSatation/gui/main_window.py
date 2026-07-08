from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QGroupBox
)
from PySide6.QtCore import Qt, QThread, QTimer, QDateTime
from PySide6.QtGui import QIcon

from widgets import (
    AttitudeIndicator, CompassIndicator, TelemetryPanel,
    ControlPanel, VideoPanel, LogPanel
)
from worker import ROVWorker
from styles import DARK_HUD_THEME


class MainWindow(QMainWindow):
    """
    Jendela Utama (Cockpit Dashboard) GUI Base Station ROV.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BASE STATION ROV - COMMAND COCKPIT v1.0")
        self.setMinimumSize(1200, 750)
        self.setStyleSheet(DARK_HUD_THEME)

        self._init_ui()
        self._init_worker()
        self._init_clock()

    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # === TOP HEADER BAR ===
        header_layout = QHBoxLayout()
        self.lbl_title = QLabel("🛸 BASE STATION ROV // COMMAND & CONTROL HUD")
        self.lbl_title.setObjectName("header_label")
        
        self.lbl_clock = QLabel("CLOCK: 00:00:00 UTC")
        self.lbl_clock.setStyleSheet("font-size: 14px; font-weight: bold; color: #00e5ff; background-color: #171f2e; padding: 4px 12px; border: 1px solid #28354d; border-radius: 4px;")

        header_layout.addWidget(self.lbl_title)
        header_layout.addStretch()
        header_layout.addWidget(self.lbl_clock)
        main_layout.addLayout(header_layout)

        # === MAIN SPLITTER (LEFT / CENTER / RIGHT) ===
        main_splitter = QSplitter(Qt.Horizontal)

        # 1. LEFT COLUMN: Kontrol & Telemetri
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.control_panel = ControlPanel()
        self.telemetry_panel = TelemetryPanel()
        
        left_layout.addWidget(self.control_panel)
        left_layout.addWidget(self.telemetry_panel)
        left_layout.addStretch()
        left_widget.setMinimumWidth(320)
        left_widget.setMaximumWidth(400)
        main_splitter.addWidget(left_widget)

        # 2. CENTER COLUMN: Video Feed & Artificial Horizon / Compass HUD
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)

        # Video Canvas
        self.video_panel = VideoPanel()
        center_layout.addWidget(self.video_panel, stretch=3)

        # HUD Row (Attitude + Compass)
        hud_group = QGroupBox("NAVIGATION INSTRUMENTS (6-DOF ATTITUDE & HEADING)")
        hud_layout = QHBoxLayout(hud_group)

        self.attitude_indicator = AttitudeIndicator()
        self.compass_indicator = CompassIndicator()

        hud_layout.addStretch()
        hud_layout.addWidget(self.attitude_indicator)
        hud_layout.addSpacing(30)
        hud_layout.addWidget(self.compass_indicator)
        hud_layout.addStretch()

        center_layout.addWidget(hud_group, stretch=2)
        main_splitter.addWidget(center_widget)

        # 3. RIGHT / BOTTOM COLUMN: System Log Console
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        self.log_panel = LogPanel()
        right_layout.addWidget(self.log_panel)
        right_widget.setMinimumWidth(300)
        main_splitter.addWidget(right_widget)

        # Set proporsi awal splitter
        main_splitter.setSizes([340, 560, 300])
        main_layout.addWidget(main_splitter)

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

        self.log_panel.append_log("GUI Base Station siap. Silakan pilih target koneksi dan tekan 'CONNECT ROV'.", "INFO")

    def _init_clock(self):
        self.clock_timer = QTimer(self)
        self.clock_timer.setInterval(1000)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start()
        self._update_clock()

    def _update_clock(self):
        now_str = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
        self.lbl_clock.setText(f"CLOCK: {now_str}")

    def _on_connection_changed(self, connected: bool):
        self.control_panel.set_connected_state(connected)
        self.video_panel.set_streaming_state(connected)

    def _on_state_updated(self, state):
        # Update Telemetry Digital
        self.telemetry_panel.update_telemetry(state)
        self.control_panel.set_armed_state(state.armed)

        # Update Instruments HUD (Roll, Pitch, Yaw)
        self.attitude_indicator.set_attitude(state.roll, state.pitch)
        self.compass_indicator.set_yaw(state.yaw)

    def closeEvent(self, event):
        """Clean up threads & MAVLink connection pada saat aplikasi ditutup."""
        self.worker.disconnect_rov()
        if self.worker_thread.isRunning():
            self.worker_thread.quit()
            self.worker_thread.wait(1000)
        event.accept()
