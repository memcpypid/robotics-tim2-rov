import math
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPolygonF


class CompassIndicator(QWidget):
    """
    Widget Kompas Navigasi (Yaw / Heading HUD) untuk ROV.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._yaw = 0.0  # Derajat (0 s/d 360)
        self.setMinimumSize(140, 140)

    def set_yaw(self, yaw: float):
        # Normalisasi ke 0 - 360
        self._yaw = yaw % 360.0
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
        radius = min(width, height) / 2.0 - 18

        painter.save()
        painter.translate(center_x, center_y)

        # 1. Background Kompas Gelap
        painter.setBrush(QBrush(QColor("#121824")))
        painter.setPen(QPen(QColor("#2d3e5c"), 2))
        painter.drawEllipse(QPointF(0, 0), radius, radius)

        # 2. Outer Ring Digital Tick Marks
        painter.save()
        painter.rotate(-self._yaw)

        for deg in range(0, 360, 15):
            painter.save()
            painter.rotate(deg)
            if deg % 90 == 0:
                pen = QPen(QColor("#00e5ff"), 3)
                length = 12
            elif deg % 45 == 0:
                pen = QPen(QColor("#ffffff"), 2)
                length = 8
            else:
                pen = QPen(QColor("#52637a"), 1)
                length = 5
            painter.setPen(pen)
            painter.drawLine(QPointF(0, -radius), QPointF(0, -radius + length))

            # Teks Mata Angin Utama
            if deg % 90 == 0:
                painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
                text = {0: "N", 90: "E", 180: "S", 270: "W"}.get(deg, "")
                color = QColor("#ff3333") if text == "N" else QColor("#00e5ff")
                painter.setPen(color)
                painter.drawText(QRectF(-15, -radius + 14, 30, 20), Qt.AlignCenter, text)
            painter.restore()

        painter.restore()

        # 3. Jarum Penunjuk Fixed Top Triangle (Heading Pointer)
        painter.setBrush(QBrush(QColor("#ff3333")))
        painter.setPen(Qt.NoPen)
        pointer_polygon = QPolygonF([
            QPointF(0, -radius - 4),
            QPointF(-6, -radius - 14),
            QPointF(6, -radius - 14)
        ])
        painter.drawPolygon(pointer_polygon)

        # 4. Center Mini ROV Icon
        painter.setPen(QPen(QColor("#00e5ff"), 2))
        painter.setBrush(QBrush(QColor("#171f2e")))
        painter.drawEllipse(QPointF(0, 0), 22, 22)

        painter.restore()

        # Label Teks Derajat Heading
        painter.setPen(QColor("#00e5ff"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.drawText(QRectF(0, height - 16, width, 15), Qt.AlignCenter, f"HEADING: {self._yaw:.1f}°")
