from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSplitter,
    QPushButton, QGroupBox, QFrame
)
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPixmap


class CameraCanvas(QWidget):
    """
    Kanvas individual untuk 1 channel kamera ROV dengan HUD overlay khusus.
    Mendukung tampilan live video QPixmap sekaligus simulasi HUD standby.
    """
    def __init__(self, cam_title="CAMERA 1: FRONT NAV", cam_type="FRONT", parent=None):
        super().__init__(parent)
        self.cam_title = cam_title
        self.cam_type = cam_type  # "FRONT" atau "BOTTOM"
        self.setMinimumSize(320, 240)
        self._is_streaming = False
        self._current_pixmap: Optional[QPixmap] = None

    def set_streaming_state(self, is_streaming: bool):
        self._is_streaming = is_streaming
        if not is_streaming:
            self._current_pixmap = None
        self.update()

    def set_frame(self, pixmap: QPixmap):
        """Menerima frame video live dari VideoReceiverWorker dan langsung menggambarnya."""
        self._current_pixmap = pixmap
        self._is_streaming = True
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        if not painter.isActive():
            return
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        center_x = width / 2.0
        center_y = height / 2.0

        # 1. Background / Frame Video Live
        if self._current_pixmap and not self._current_pixmap.isNull():
            painter.fillRect(self.rect(), QColor("#000000"))
            scaled_pix = self._current_pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            px = (width - scaled_pix.width()) / 2
            py = (height - scaled_pix.height()) / 2
            painter.drawPixmap(int(px), int(py), scaled_pix)
        else:
            painter.fillRect(self.rect(), QColor("#080c12"))
            # Grid HUD Latar Belakang jika standby
            grid_pen = QPen(QColor("#132238"), 1, Qt.DotLine)
            painter.setPen(grid_pen)
            for x in range(0, width, 35):
                painter.drawLine(x, 0, x, height)
            for y in range(0, height, 35):
                painter.drawLine(0, y, width, y)

        # 2. Sudut Bingkai Kamera (Corner brackets)
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

        # 3. Crosshair / Target Overlay
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

        # 4. Header Bar Overlay di atas video
        painter.setFont(QFont("Consolas", 7))
        painter.setPen(corner_color)
        
        header_rect = QRectF(0, 15, width, 30)
        
        if self._is_streaming:
            text = f"{self.cam_title}\n[LIVE STREAM ACTIVE]"
        else:
            text = f"{self.cam_title}\n[STANDBY / AWAITING UDP STREAM]"
            
        painter.drawText(header_rect, Qt.AlignHCenter | Qt.AlignTop, text)

        # 5. Footer Bar Overlay
        painter.setFont(QFont("Consolas", 7))
        painter.setPen(corner_color)
        
        footer_rect = QRectF(0, height - 40, width, 30)
        
        if self.cam_type == "FRONT":
            text = "ZOOM: 1.0x | IR: AUTO | TILT: 0°\nSTREAM: UDP PORT 9002"
        else:
            text = "ZOOM: 1.0x | SCANNER: ACTIVE | LIGHT: ON\nSTREAM: UDP PORT 9003"
            
        painter.drawText(footer_rect, Qt.AlignHCenter | Qt.AlignBottom, text)


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

        # Control Bar Atas (Layout Switcher) dibungkus dalam QFrame agar rapi
        ctrl_frame = QFrame()
        ctrl_frame.setStyleSheet("QFrame { background-color: #1a2332; border: 1px solid #28354d; border-radius: 6px; }")
        ctrl_layout = QHBoxLayout(ctrl_frame)
        ctrl_layout.setContentsMargins(10, 8, 10, 8)
        ctrl_layout.setSpacing(10)

        lbl_title = QLabel(" DUAL ROV CAMERA CHANNELS")
        lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #00e5ff; border: none; background: transparent;")
        ctrl_layout.addWidget(lbl_title)
        ctrl_layout.addStretch()

        self.btn_split = QPushButton("DUAL SPLIT (50/50)")
        self.btn_cam1 = QPushButton("CAM 1 ONLY")
        self.btn_cam2 = QPushButton("CAM 2 ONLY")

        for btn in [self.btn_split, self.btn_cam1, self.btn_cam2]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #202d42;
                    color: white;
                    border: 1px solid #3d5070;
                    border-radius: 4px;
                    padding: 6px 16px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #2b3b55;
                    border: 1px solid #00e5ff;
                }
            """)
            ctrl_layout.addWidget(btn)

        self.btn_split.clicked.connect(self._show_split)
        self.btn_cam1.clicked.connect(self._show_cam1)
        self.btn_cam2.clicked.connect(self._show_cam2)

        layout.addWidget(ctrl_frame)

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

    def update_cam1_frame(self, pixmap: QPixmap):
        self.cam1_canvas.set_frame(pixmap)

    def update_cam2_frame(self, pixmap: QPixmap):
        self.cam2_canvas.set_frame(pixmap)
