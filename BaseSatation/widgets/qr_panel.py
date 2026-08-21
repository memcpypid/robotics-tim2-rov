from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QLineEdit, QPushButton, QFrame, QApplication
)
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPixmap


class QRImageCanvas(QFrame):
    """
    Frame visual untuk menampilkan hasil capture gambar/crop QR Code live dari kamera,
    ataupun animasi targeting standby saat mencari QR Code.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(220, 180)
        self.setStyleSheet("background-color: #080c12; border: 1px solid #1f2c40; border-radius: 6px;")
        self._qr_code_text = ""
        self._current_pixmap: Optional[QPixmap] = None
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

    def set_qr_image(self, pixmap: Optional[QPixmap]):
        self._current_pixmap = pixmap
        self.update()

    def _animate_scan(self):
        if not self._qr_code_text and not self._current_pixmap:
            self._scan_line_y += self._scan_direction * 3
            if self._scan_line_y > self.height() - 20:
                self._scan_direction = -1
            elif self._scan_line_y < 20:
                self._scan_direction = 1
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        if not painter.isActive():
            return
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
        box_w = min(width, height) * 0.75
        box_h = box_w
        bx = center_x - box_w / 2.0
        by = center_y - box_h / 2.0

        # 1. Gambar Hasil Capture Frame QR Code (QPixmap) jika ada
        has_image = self._current_pixmap and not self._current_pixmap.isNull()
        if has_image:
            scaled_pix = self._current_pixmap.scaled(int(box_w - 4), int(box_h - 4), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            px = center_x - scaled_pix.width() / 2.0
            py = center_y - scaled_pix.height() / 2.0
            painter.drawPixmap(int(px), int(py), scaled_pix)
        elif self._qr_code_text:
            painter.setBrush(QBrush(QColor(64, 191, 106, 50)))
            painter.setPen(QPen(QColor("#40bf6a"), 2))
            painter.drawRect(QRectF(bx, by, box_w, box_h))

        # 2. Bingkai Pojok (Corner HUD)
        corner_pen = QPen(QColor("#00e5ff") if not (self._qr_code_text or has_image) else QColor("#40bf6a"), 3)
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

        # 3. Label status / animasi
        if self._qr_code_text or has_image:
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.fillRect(int(bx), int(by), int(box_w), 24, QColor(0, 150, 0, 200))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(QRectF(bx, by, box_w, 24), Qt.AlignCenter, "[ QR CODE CAPTURED ]")
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
    Panel Frame Capture QR Code & Hasil Pembacaan QR Code (Mode Ringkas / Compact).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("QR CODE DECODER")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(6, 14, 6, 6)
        layout.setSpacing(4)

        # 1. Canvas / Frame Capture QR
        self.canvas = QRImageCanvas()
        layout.addWidget(self.canvas, stretch=1)

        # 2. Hasil Pembacaan QR Code
        self.txt_result = QLineEdit()
        self.txt_result.setReadOnly(True)
        self.txt_result.setPlaceholderText("Menunggu QR Code...")
        self.txt_result.setStyleSheet("background-color: #0a0e14; border: 1px solid #00e5ff; font-size: 12px; font-weight: bold; color: #40bf6a; padding: 4px;")
        layout.addWidget(self.txt_result)

        # 3. Waktu Deteksi Info & Tombol
        info_layout = QHBoxLayout()
        self.lbl_time = QLabel("Waktu: -")
        self.lbl_time.setStyleSheet("font-size: 10px; color: #899cb8;")
        info_layout.addWidget(self.lbl_time)
        info_layout.addStretch()

        self.btn_copy = QPushButton("COPY")
        self.btn_copy.setStyleSheet("padding: 2px 6px; font-size: 10px;")
        self.btn_copy.clicked.connect(self._copy_data)
        info_layout.addWidget(self.btn_copy)

        self.btn_clear = QPushButton("CLEAR")
        self.btn_clear.setStyleSheet("padding: 2px 6px; font-size: 10px;")
        self.btn_clear.clicked.connect(self._clear_data)
        info_layout.addWidget(self.btn_clear)

        layout.addLayout(info_layout)
        main_layout.addWidget(group)

    def set_qr_image(self, pixmap: QPixmap):
        """Menerima langsung stream UDP frame gambar QR dari port 9004."""
        if pixmap and not pixmap.isNull():
            self.canvas.set_qr_image(pixmap)

    def update_qr_data(self, qr_text: str, timestamp_str: str = "", cam_name: str = "", pixmap: Optional[QPixmap] = None):
        """Dipanggil dari state atau worker saat QR terdeteksi."""
        if not qr_text:
            return
        self.canvas.set_qr_data(qr_text)
        self.txt_result.setText(qr_text)
        if pixmap and not pixmap.isNull():
            self.canvas.set_qr_image(pixmap)
            
        src_str = cam_name if cam_name else "QR CAM"
        if timestamp_str:
            self.lbl_time.setText(f"Waktu Scan: {timestamp_str} | Sumber: {src_str}")
        else:
            self.lbl_time.setText(f"Waktu Scan: Baru saja | Sumber: {src_str}")

    def _copy_data(self):
        text = self.txt_result.text()
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)

    def _clear_data(self):
        self.canvas.set_qr_image(None)
        self.canvas.set_qr_data("")
        self.txt_result.clear()
        self.lbl_time.setText("Waktu Scan: - | Sumber: -")
