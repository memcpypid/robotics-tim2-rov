from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSplitter,
    QPushButton, QGroupBox
)
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont


class CameraCanvas(QWidget):
    """
    Kanvas individual untuk 1 channel kamera ROV dengan HUD overlay khusus.
    """
    def __init__(self, cam_title="CAMERA 1: FRONT NAV", cam_type="FRONT", parent=None):
        super().__init__(parent)
        self.cam_title = cam_title
        self.cam_type = cam_type  # "FRONT" atau "BOTTOM"
        self.setMinimumSize(320, 240)
        self._is_streaming = False

    def set_streaming_state(self, is_streaming: bool):
        self._is_streaming = is_streaming
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        center_x = width / 2.0
        center_y = height / 2.0

        # 1. Background (Simulasi Feed Kamera)
        painter.fillRect(self.rect(), QColor("#080c12"))

        # 2. Grid HUD
        grid_pen = QPen(QColor("#132238"), 1, Qt.DotLine)
        painter.setPen(grid_pen)
        for x in range(0, width, 35):
            painter.drawLine(x, 0, x, height)
        for y in range(0, height, 35):
            painter.drawLine(0, y, width, y)

        # 3. Sudut Bingkai Kamera (Corner brackets)
        corner_color = QColor("#00e5ff") if self.cam_type == "FRONT" else QColor("#40bf6a")
        corner_pen = QPen(corner_color, 2.5)
        painter.setPen(corner_pen)
        margin = 15
        c_len = 20

        # Top-Left
        painter.drawLine(margin, margin, margin + c_len, margin)
        painter.drawLine(margin, margin, margin, margin + c_len)
        # Top-Right
        painter.drawLine(width - margin, margin, width - margin - c_len, margin)
        painter.drawLine(width - margin, margin, width - margin, margin + c_len)
        # Bottom-Left
        painter.drawLine(margin, height - margin, margin + c_len, height - margin)
        painter.drawLine(margin, height - margin, margin, height - margin - c_len)
        # Bottom-Right
        painter.drawLine(width - margin, height - margin, width - margin - c_len, height - margin)
        painter.drawLine(width - margin, height - margin, width - margin, height - margin - c_len)

        # 4. Crosshair / Target Overlay
        cross_pen = QPen(corner_color, 1.2, Qt.DashLine)
        painter.setPen(cross_pen)
        if self.cam_type == "FRONT":
            painter.drawEllipse(QPointF(center_x, center_y), 30, 30)
            painter.drawLine(center_x - 45, center_y, center_x + 45, center_y)
            painter.drawLine(center_x, center_y - 45, center_x, center_y + 45)
        else:
            # Bottom Camera has Square QR targeting box
            box_s = 60
            painter.drawRect(QRectF(center_x - box_s/2, center_y - box_s/2, box_s, box_s))
            painter.drawLine(center_x - 50, center_y, center_x + 50, center_y)
            painter.drawLine(center_x, center_y - 50, center_x, center_y + 50)

        # 5. Header Bar Overlay di dalam video
        painter.fillRect(0, 0, width, 26, QColor(15, 20, 29, 210))
        painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
        
        if self._is_streaming:
            painter.setBrush(QBrush(QColor("#ff2a2a")))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(16, 13), 5, 5)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(28, 17, f"{self.cam_title} [LIVE HD @ 60FPS]")
        else:
            painter.setBrush(QBrush(QColor("#52637a")))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(16, 13), 5, 5)
            painter.setPen(QColor("#899cb8"))
            painter.drawText(28, 17, f"{self.cam_title} [STANDBY / NO STREAM]")

        # Footer Bar Overlay
        painter.setFont(QFont("Consolas", 9))
        painter.setPen(corner_color)
        if self.cam_type == "FRONT":
            painter.drawText(12, height - 10, "ZOOM: 1.0x | IR: AUTO | TILT: 0°")
        else:
            painter.drawText(12, height - 10, "ZOOM: 1.0x | SCANNER: ACTIVE | LIGHT: ON")


class VideoPanel(QWidget):
    """
    Panel Tampilan 2 Display Camera ROV (Camera 1: Front Navigation & Camera 2: Bottom QR / Gripper).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Control Bar Atas (Layout Switcher)
        ctrl_layout = QHBoxLayout()
        lbl_title = QLabel("🎥 DUAL ROV CAMERA CHANNELS")
        lbl_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #00e5ff;")
        ctrl_layout.addWidget(lbl_title)
        ctrl_layout.addStretch()

        self.btn_split = QPushButton("DUAL SPLIT (50/50)")
        self.btn_cam1 = QPushButton("CAM 1 ONLY")
        self.btn_cam2 = QPushButton("CAM 2 ONLY")

        for btn in [self.btn_split, self.btn_cam1, self.btn_cam2]:
            btn.setStyleSheet("padding: 4px 12px; font-size: 11px;")
            ctrl_layout.addWidget(btn)

        self.btn_split.clicked.connect(self._show_split)
        self.btn_cam1.clicked.connect(self._show_cam1)
        self.btn_cam2.clicked.connect(self._show_cam2)

        layout.addLayout(ctrl_layout)

        # Splitter untuk 2 kamera
        self.splitter = QSplitter(Qt.Horizontal)
        
        self.cam1_canvas = CameraCanvas("CAM 1: FRONT NAVIGATION", "FRONT")
        self.cam2_canvas = CameraCanvas("CAM 2: BOTTOM QR & GRIPPER", "BOTTOM")

        self.splitter.addWidget(self.cam1_canvas)
        self.splitter.addWidget(self.cam2_canvas)
        self.splitter.setSizes([500, 500])

        layout.addWidget(self.splitter, stretch=1)

    def _show_split(self):
        self.cam1_canvas.setVisible(True)
        self.cam2_canvas.setVisible(True)
        self.splitter.setSizes([500, 500])

    def _show_cam1(self):
        self.cam1_canvas.setVisible(True)
        self.cam2_canvas.setVisible(False)

    def _show_cam2(self):
        self.cam1_canvas.setVisible(False)
        self.cam2_canvas.setVisible(True)

    def set_streaming_state(self, is_streaming: bool):
        self.cam1_canvas.set_streaming_state(is_streaming)
        self.cam2_canvas.set_streaming_state(is_streaming)
