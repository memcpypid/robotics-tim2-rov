from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QLineEdit, QPushButton, QFrame, QApplication
)
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QImage, QPixmap


class QRImageCanvas(QFrame):
    """
    Frame visual untuk menampilkan hasil capture QR Code / targeting frame kamera bawah.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(220, 180)
        self.setStyleSheet("background-color: #080c12; border: 1px solid #1f2c40; border-radius: 6px;")
        self._qr_code_text = ""
        self._is_scanning = True
        self._scan_line_y = 10
        self._scan_direction = 1

        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self._animate_scan)
        self.timer.start()

    def set_qr_data(self, text: str):
        self._qr_code_text = text
        self.update()

    def _animate_scan(self):
        if not self._qr_code_text:
            self._scan_line_y += self._scan_direction * 3
            if self._scan_line_y > self.height() - 20:
                self._scan_direction = -1
            elif self._scan_line_y < 20:
                self._scan_direction = 1
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        center_x = width / 2.0
        center_y = height / 2.0

        # Background grid
        grid_pen = QPen(QColor("#131e30"), 1, Qt.DotLine)
        painter.setPen(grid_pen)
        for x in range(0, width, 25):
            painter.drawLine(x, 0, x, height)
        for y in range(0, height, 25):
            painter.drawLine(0, y, width, y)

        # Target QR Box Corner HUD
        box_w = min(width, height) * 0.65
        box_h = box_w
        bx = center_x - box_w / 2.0
        by = center_y - box_h / 2.0

        corner_pen = QPen(QColor("#00e5ff") if not self._qr_code_text else QColor("#40bf6a"), 3)
        painter.setPen(corner_pen)
        c_len = 18

        # Top-left
        painter.drawLine(bx, by, bx + c_len, by)
        painter.drawLine(bx, by, bx, by + c_len)
        # Top-right
        painter.drawLine(bx + box_w, by, bx + box_w - c_len, by)
        painter.drawLine(bx + box_w, by, bx + box_w, by + c_len)
        # Bottom-left
        painter.drawLine(bx, by + box_h, bx + c_len, by + box_h)
        painter.drawLine(bx, by + box_h, bx, by + box_h - c_len)
        # Bottom-right
        painter.drawLine(bx + box_w, by + box_h, bx + box_w - c_len, by + box_h)
        painter.drawLine(bx + box_w, by + box_h, bx + box_w, by + box_h - c_len)

        if self._qr_code_text:
            # Tampilkan simulasi / representasi QR Code Terdeteksi
            painter.setBrush(QBrush(QColor(64, 191, 106, 50)))
            painter.setPen(QPen(QColor("#40bf6a"), 2))
            painter.drawRect(QRectF(bx, by, box_w, box_h))

            painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(QRectF(bx, by, box_w, box_h), Qt.AlignCenter | Qt.TextWordWrap, f"[ QR DETECTED ]\n{self._qr_code_text}")
        else:
            # Laser Scan Line animation
            laser_pen = QPen(QColor(0, 229, 255, 180), 2)
            painter.setPen(laser_pen)
            painter.drawLine(bx + 4, self._scan_line_y, bx + box_w - 4, self._scan_line_y)

            # Glow under scan line
            painter.setBrush(QBrush(QColor(0, 229, 255, 30)))
            painter.setPen(Qt.NoPen)
            painter.drawRect(QRectF(bx + 4, self._scan_line_y - 6, box_w - 8, 12))

            painter.setFont(QFont("Consolas", 9))
            painter.setPen(QColor("#64809f"))
            painter.drawText(QRectF(0, height - 25, width, 20), Qt.AlignCenter, "SCANNING FOR QR CODE...")


class QRPanel(QWidget):
    """
    Panel Frame Capture QR Code & Hasil Pembacaan QR Code.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("QR CODE CAPTURE & DECODER")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        # 1. Canvas / Frame Capture QR
        self.canvas = QRImageCanvas()
        layout.addWidget(self.canvas, stretch=2)

        # 2. Hasil Pembacaan QR Code
        lbl_result_title = QLabel("Hasil Pembacaan QR Code:")
        lbl_result_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #a6e3e9;")
        layout.addWidget(lbl_result_title)

        self.txt_result = QLineEdit()
        self.txt_result.setReadOnly(True)
        self.txt_result.setPlaceholderText("Belum ada QR Code terdeteksi...")
        self.txt_result.setStyleSheet("background-color: #0a0e14; border: 1px solid #00e5ff; font-size: 14px; font-weight: bold; color: #40bf6a; padding: 8px;")
        layout.addWidget(self.txt_result)

        # 3. Waktu Deteksi Info & Tombol
        info_layout = QHBoxLayout()
        self.lbl_time = QLabel("Waktu Scan: -")
        self.lbl_time.setStyleSheet("font-size: 11px; color: #899cb8;")
        info_layout.addWidget(self.lbl_time)
        info_layout.addStretch()

        self.btn_copy = QPushButton("COPY DATA")
        self.btn_copy.setStyleSheet("padding: 4px 10px; font-size: 11px;")
        self.btn_copy.clicked.connect(self._copy_data)
        info_layout.addWidget(self.btn_copy)

        self.btn_clear = QPushButton("CLEAR")
        self.btn_clear.setStyleSheet("padding: 4px 10px; font-size: 11px;")
        self.btn_clear.clicked.connect(self._clear_data)
        info_layout.addWidget(self.btn_clear)

        layout.addLayout(info_layout)
        main_layout.addWidget(group)

    def update_qr_data(self, qr_text: str, timestamp_str: str = ""):
        """Dipanggil dari state atau worker saat QR terdeteksi."""
        if not qr_text:
            return
        self.canvas.set_qr_data(qr_text)
        self.txt_result.setText(qr_text)
        if timestamp_str:
            self.lbl_time.setText(f"Waktu Scan: {timestamp_str}")
        else:
            self.lbl_time.setText("Waktu Scan: Baru saja")

    def _copy_data(self):
        text = self.txt_result.text()
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)

    def _clear_data(self):
        self.canvas.set_qr_data("")
        self.txt_result.clear()
        self.lbl_time.setText("Waktu Scan: -")
