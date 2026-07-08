from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QPushButton, QFileDialog, QFrame
)
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPixmap


class DesignROVCanvas(QFrame):
    """
    Kanvas placeholder / penampil gambar sketsa/3D CAD Design ROV tim.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.setStyleSheet("background-color: #080c12; border: 1px solid #1f2c40; border-radius: 6px;")
        self.pixmap = None

    def load_image(self, file_path: str):
        self.pixmap = QPixmap(file_path)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        center_x = width / 2.0
        center_y = height / 2.0

        if self.pixmap and not self.pixmap.isNull():
            # Gambar desain ROV di tengah, diposisikan secara proporsional
            scaled_pix = self.pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            px = (width - scaled_pix.width()) / 2
            py = (height - scaled_pix.height()) / 2
            painter.drawPixmap(int(px), int(py), scaled_pix)
        else:
            # Blueprint grid background
            grid_pen = QPen(QColor("#102238"), 1, Qt.DotLine)
            painter.setPen(grid_pen)
            for x in range(0, width, 30):
                painter.drawLine(x, 0, x, height)
            for y in range(0, height, 30):
                painter.drawLine(0, y, width, y)

            # Center wireframe box / schematic placeholder
            bw = min(width, height) * 0.5
            bh = bw * 0.65
            bx = center_x - bw / 2.0
            by = center_y - bh / 2.0

            painter.setPen(QPen(QColor("#00e5ff"), 2, Qt.DashLine))
            painter.drawRect(QRectF(bx, by, bw, bh))
            painter.drawLine(bx, by, bx + bw, by + bh)
            painter.drawLine(bx + bw, by, bx, by + bh)

            painter.setFont(QFont("Segoe UI", 13, QFont.Bold))
            painter.setPen(QColor("#00e5ff"))
            painter.drawText(QRectF(10, center_y - 80, width - 20, 40), Qt.AlignCenter, "[ GAMBAR DESIGN ROV (PLACEHOLDER) ]")
            
            painter.setFont(QFont("Consolas", 11))
            painter.setPen(QColor("#899cb8"))
            painter.drawText(QRectF(20, center_y + 10, width - 40, 60), Qt.AlignCenter, "Gambar / 3D Model ROV akan ditampilkan di sini (Nanti Saja).\nTekan 'UPLOAD DESIGN ROV' di bawah jika sudah siap menyisipkan gambar.")


class DesignROVPanel(QWidget):
    """
    Panel untuk menampilkan desain fisik atau CAD 3D ROV.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("ROV BLUEPRINT & 3D CAD DESIGN (SCHEMATIC VIEW)")
        group_layout = QVBoxLayout(group)

        self.canvas = DesignROVCanvas()
        group_layout.addWidget(self.canvas, stretch=1)

        # Bottom Bar
        bar_layout = QHBoxLayout()
        lbl_info = QLabel("Status Gambar: Placeholder Default (Menunggu Upload Desain ROV Tim)")
        lbl_info.setStyleSheet("font-size: 12px; color: #a6e3e9;")
        bar_layout.addWidget(lbl_info)
        bar_layout.addStretch()

        btn_load = QPushButton("UPLOAD DESIGN ROV (.PNG/.JPG)")
        btn_load.clicked.connect(self._browse_image)
        bar_layout.addWidget(btn_load)

        group_layout.addLayout(bar_layout)
        layout.addWidget(group)

    def _browse_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Pilih Gambar Design ROV", "", "Images (*.png *.xpm *.jpg *.jpeg *.bmp)")
        if file_path:
            self.canvas.load_image(file_path)
