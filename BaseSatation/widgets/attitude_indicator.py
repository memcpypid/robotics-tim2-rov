import math
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath


class AttitudeIndicator(QWidget):
    """
    Widget Artificial Horizon (HUD Attitude Indicator) untuk memvisualisasikan Roll dan Pitch ROV.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._roll = 0.0
        self._pitch = 0.0
        self.setMinimumSize(180, 180)

    def set_attitude(self, roll: float, pitch: float):
        self._roll = roll
        self._pitch = pitch
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        try:
            width = self.width()
            height = self.height()
            center_x = width / 2.0
            center_y = height / 2.0
            radius = min(width, height) / 2.0 - 10

            painter.save()
            clip_path = QPainterPath()
            clip_path.addEllipse(QPointF(center_x, center_y), radius, radius)
            painter.setClipPath(clip_path)

            painter.translate(center_x, center_y)
            painter.rotate(-self._roll)

            pitch_offset = self._pitch * (radius / 30.0)
            painter.translate(0, pitch_offset)

            sky_rect = QRectF(-width * 2, -height * 2, width * 4, height * 2)
            painter.fillRect(sky_rect, QColor("#1b4b7a"))

            sea_rect = QRectF(-width * 2, 0, width * 4, height * 2)
            painter.fillRect(sea_rect, QColor("#0d2137"))

            horizon_pen = QPen(QColor("#00e5ff"), 2, Qt.SolidLine)
            painter.setPen(horizon_pen)
            painter.drawLine(-width * 2, 0, width * 2, 0)

            font = QFont("Segoe UI", 8, QFont.Bold)
            painter.setFont(font)
            painter.setPen(QPen(QColor("#ffffff"), 1.5))

            for p in range(-60, 61, 10):
                if p == 0:
                    continue
                y_pos = -p * (radius / 30.0)
                line_len = 30 if p % 20 == 0 else 18
                painter.drawLine(QPointF(-line_len, y_pos), QPointF(line_len, y_pos))
                if p % 20 == 0:
                    painter.drawText(QPointF(-line_len - 22, y_pos + 4), f"{p}°")
                    painter.drawText(QPointF(line_len + 4, y_pos + 4), f"{p}°")

            painter.restore()

            painter.save()
            painter.translate(center_x, center_y)

            ring_pen = QPen(QColor("#00e5ff"), 3)
            painter.setPen(ring_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(0, 0), radius, radius)

            symbol_pen = QPen(QColor("#ffcc00"), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(symbol_pen)
            painter.drawLine(QPointF(-40, 0), QPointF(-15, 0))
            painter.drawLine(QPointF(-15, 0), QPointF(-15, 8))
            painter.drawLine(QPointF(15, 0), QPointF(40, 0))
            painter.drawLine(QPointF(15, 0), QPointF(15, 8))
            painter.setBrush(QBrush(QColor("#ffcc00")))
            painter.drawEllipse(QPointF(0, 0), 3, 3)

            painter.restore()

            painter.setPen(QColor("#00e5ff"))
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.drawText(QRectF(0, height - 26, width, 20), Qt.AlignCenter, f"R: {self._roll:.1f}° | P: {self._pitch:.1f}°")
        finally:
            if painter.isActive():
                painter.end()

        painter.save()
        painter.translate(center_x, center_y)

        ring_pen = QPen(QColor("#00e5ff"), 3)
        painter.setPen(ring_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(0, 0), radius, radius)

        symbol_pen = QPen(QColor("#ffcc00"), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(symbol_pen)
        painter.drawLine(QPointF(-40, 0), QPointF(-15, 0))
        painter.drawLine(QPointF(-15, 0), QPointF(-15, 8))
        painter.drawLine(QPointF(15, 0), QPointF(40, 0))
        painter.drawLine(QPointF(15, 0), QPointF(15, 8))
        painter.setBrush(QBrush(QColor("#ffcc00")))
        painter.drawEllipse(QPointF(0, 0), 3, 3)

        painter.restore()

        painter.setPen(QColor("#00e5ff"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.drawText(QRectF(0, height - 26, width, 20), Qt.AlignCenter, f"R: {self._roll:.1f}° | P: {self._pitch:.1f}°")
