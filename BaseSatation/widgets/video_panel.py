from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont


class VideoPanel(QWidget):
    """
    Panel Tampilan Video Feed Kamera ROV + HUD Crosshairs Overlay.
    Saat ini berfungsi sebagai placeholder / simulasi stream high-tech sebelum kamera fisik tersambung.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(480, 360)
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

        # 1. Background (Simulasi Feed Kamera Gelap laut / static)
        painter.fillRect(self.rect(), QColor("#080c12"))

        # 2. Grid HUD latar belakang
        grid_pen = QPen(QColor("#17263b"), 1, Qt.DotLine)
        painter.setPen(grid_pen)
        for x in range(0, width, 40):
            painter.drawLine(x, 0, x, height)
        for y in range(0, height, 40):
            painter.drawLine(0, y, width, y)

        # 3. Sudut-sudut HUD Bingkai Kamera (Targeting Frame Corners)
        corner_pen = QPen(QColor("#00e5ff"), 3)
        painter.setPen(corner_pen)
        margin = 30
        c_len = 25

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

        # 4. Center Crosshair
        cross_pen = QPen(QColor("#00e5ff"), 1.5, Qt.DashLine)
        painter.setPen(cross_pen)
        painter.drawEllipse(QPointF(center_x, center_y), 40, 40)
        painter.drawLine(center_x - 55, center_y, center_x + 55, center_y)
        painter.drawLine(center_x, center_y - 55, center_x, center_y + 55)

        # 5. Teks Status Stream & REC Indicator
        painter.setFont(QFont("Segoe UI", 11, QFont.Bold))
        if self._is_streaming:
            painter.setBrush(QBrush(QColor("#ff2a2a")))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(45, 48), 6, 6)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(60, 53, "LIVE ROV CAMERA STREAM [HD 1080p @ 60FPS]")
        else:
            painter.setBrush(QBrush(QColor("#52637a")))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(45, 48), 6, 6)
            painter.setPen(QColor("#899cb8"))
            painter.drawText(60, 53, "CAMERA FEED STANDBY / AWAITING RTSP STREAM")

        # Teks Info Bawah
        painter.setFont(QFont("Consolas", 10))
        painter.setPen(QColor("#00e5ff"))
        painter.drawText(40, height - 38, "OPTICAL ZOOM: 1.0x | IR LIGHTS: OFF | CAM TILT: 0°")
