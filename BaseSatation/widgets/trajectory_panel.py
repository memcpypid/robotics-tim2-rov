import math
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QPushButton, QFrame
)
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath


class TrajectoryCanvas(QFrame):
    """
    Kanvas 2D untuk menggambar lintasan (trajectory) ROV dari titik awal (0,0) hingga posisi terkini.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(360, 300)
        self.setStyleSheet("background-color: #080c12; border: 1px solid #1f2c40; border-radius: 6px;")
        
        self.path_points = [(0.0, 0.0)]  # Daftar koordinat (pos_x, pos_y)
        self.current_x = 0.0
        self.current_y = 0.0
        self.current_z = 0.0
        self.current_yaw = 0.0
        self.total_distance = 0.0
        
        self.scale = 25.0  # piksel per meter
        self.offset_x = 0.0
        self.offset_y = 0.0

    def update_position(self, x: float, y: float, z: float, yaw: float):
        """Memperbarui posisi terkini dan menambahkan ke jejak lintasan bila berpindah > 0.05 m."""
        dx = x - self.current_x
        dy = y - self.current_y
        dist = math.sqrt(dx*dx + dy*dy)
        
        if dist > 0.05 or len(self.path_points) == 1:
            if len(self.path_points) > 0:
                last_x, last_y = self.path_points[-1]
                step_dist = math.sqrt((x - last_x)**2 + (y - last_y)**2)
                self.total_distance += step_dist
            self.path_points.append((x, y))
            
        self.current_x = x
        self.current_y = y
        self.current_z = z
        self.current_yaw = yaw
        self.update()

    def reset_trajectory(self):
        self.path_points = [(0.0, 0.0)]
        self.current_x = 0.0
        self.current_y = 0.0
        self.current_z = 0.0
        self.total_distance = 0.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.update()

    def zoom_in(self):
        self.scale = min(200.0, self.scale * 1.25)
        self.update()

    def zoom_out(self):
        self.scale = max(5.0, self.scale * 0.8)
        self.update()

    def center_on_rov(self):
        self.offset_x = -self.current_y * self.scale
        self.offset_y = -self.current_x * self.scale
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        cx = width / 2.0 + self.offset_x
        cy = height / 2.0 + self.offset_y

        # 1. Background & Grid
        grid_pen = QPen(QColor("#131e30"), 1, Qt.DotLine)
        painter.setPen(grid_pen)
        grid_spacing = int(self.scale) if self.scale >= 15 else int(self.scale * 5)
        if grid_spacing > 5:
            for x in range(int(cx) % grid_spacing, width, grid_spacing):
                painter.drawLine(x, 0, x, height)
            for y in range(int(cy) % grid_spacing, height, grid_spacing):
                painter.drawLine(0, y, width, y)

        # 2. Sumbu X (North) & Y (East) pusat (0,0)
        axis_pen = QPen(QColor("#283e5e"), 1.5)
        painter.setPen(axis_pen)
        painter.drawLine(int(cx), 0, int(cx), height)
        painter.drawLine(0, int(cy), width, int(cy))

        # Label Arah Mata Angin pada grid (N/S/E/W)
        painter.setFont(QFont("Consolas", 9, QFont.Bold))
        painter.setPen(QColor("#4b6c96"))
        painter.drawText(int(cx) + 5, 18, "N (Forward X+)")
        painter.drawText(width - 85, int(cy) - 5, "E (Right Y+)")

        # 3. Gambar Jejak Lintasan (Trajectory Path)
        if len(self.path_points) > 1:
            path_pen = QPen(QColor("#00e5ff"), 2.5, Qt.SolidLine)
            path_pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(path_pen)
            
            for i in range(len(self.path_points) - 1):
                x1, y1 = self.path_points[i]
                x2, y2 = self.path_points[i+1]
                # Konversi NED ke koordinat layar (X North -> -Y screen, Y East -> +X screen)
                px1 = cx + (y1 * self.scale)
                py1 = cy - (x1 * self.scale)
                px2 = cx + (y2 * self.scale)
                py2 = cy - (x2 * self.scale)
                painter.drawLine(QPointF(px1, py1), QPointF(px2, py2))

            # Draw waypoint dots
            painter.setBrush(QBrush(QColor("#00e5ff")))
            painter.setPen(Qt.NoPen)
            for pt in self.path_points[1:-1:2]:
                px = cx + (pt[1] * self.scale)
                py = cy - (pt[0] * self.scale)
                painter.drawEllipse(QPointF(px, py), 2.5, 2.5)

        # 4. Titik Awal [START (0,0)]
        start_x = cx
        start_y = cy
        painter.setBrush(QBrush(QColor("#40bf6a")))
        painter.setPen(QPen(QColor("#ffffff"), 1.5))
        painter.drawEllipse(QPointF(start_x, start_y), 6, 6)
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.setPen(QColor("#40bf6a"))
        painter.drawText(int(start_x) + 8, int(start_y) + 4, "[START 0,0]")

        # 5. Posisi Terkini ROV [CURRENT]
        cur_px = cx + (self.current_y * self.scale)
        cur_py = cy - (self.current_x * self.scale)

        # Gambar icon arah segitiga/ROV berdasarkan Yaw
        painter.save()
        painter.translate(cur_px, cur_py)
        painter.rotate(self.current_yaw)
        
        rov_path = QPainterPath()
        rov_path.moveTo(0, -10)   # Hidung ROV
        rov_path.lineTo(-7, 8)    # Sayap Kiri
        rov_path.lineTo(0, 4)     # Ekor
        rov_path.lineTo(7, 8)     # Sayap Kanan
        rov_path.closeSubpath()

        painter.setBrush(QBrush(QColor("#ff3b30")))
        painter.setPen(QPen(QColor("#ffffff"), 1.5))
        painter.drawPath(rov_path)
        painter.restore()

        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.setPen(QColor("#ff3b30"))
        painter.drawText(int(cur_px) + 12, int(cur_py) + 4, f"[ROV ({self.current_x:.1f}, {self.current_y:.1f})]")

        # 6. Overlay Info Scale & Metrics di Pojok Kiri Bawah
        painter.setFont(QFont("Consolas", 10, QFont.Bold))
        painter.setPen(QColor("#00e5ff"))
        painter.drawText(12, height - 12, f"SCALE: {self.scale:.1f} px/m | TOTAL JARAK: {self.total_distance:.2f} m")


class TrajectoryPanel(QWidget):
    """
    Panel yang menampung TrajectoryCanvas beserta kontrol zoom & reset.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("ROV TRAJECTORY & PATH TRACKER (2D LOCAL MAP)")
        group_layout = QVBoxLayout(group)

        self.canvas = TrajectoryCanvas()
        group_layout.addWidget(self.canvas, stretch=1)

        # Status & Controls bar
        ctrl_layout = QHBoxLayout()
        self.lbl_pos = QLabel("Posisi Terkini: X: 0.00m | Y: 0.00m | Z: 0.00m | Yaw: 0.0°")
        self.lbl_pos.setStyleSheet("font-size: 12px; font-weight: bold; color: #a6e3e9;")
        ctrl_layout.addWidget(self.lbl_pos)
        ctrl_layout.addStretch()

        self.btn_center = QPushButton("CENTER ROV")
        self.btn_center.clicked.connect(self.canvas.center_on_rov)
        ctrl_layout.addWidget(self.btn_center)

        self.btn_zoom_in = QPushButton("ZOOM +")
        self.btn_zoom_in.clicked.connect(self.canvas.zoom_in)
        ctrl_layout.addWidget(self.btn_zoom_in)

        self.btn_zoom_out = QPushButton("ZOOM -")
        self.btn_zoom_out.clicked.connect(self.canvas.zoom_out)
        ctrl_layout.addWidget(self.btn_zoom_out)

        self.btn_reset = QPushButton("RESET PATH")
        self.btn_reset.setStyleSheet("background-color: #591b1b; border: 1px solid #ff4d4d; color: #ffffff; font-weight: bold;")
        self.btn_reset.clicked.connect(self._reset_path)
        ctrl_layout.addWidget(self.btn_reset)

        group_layout.addLayout(ctrl_layout)
        layout.addWidget(group)

    def _reset_path(self):
        self.canvas.reset_trajectory()
        self.lbl_pos.setText("Posisi Terkini: X: 0.00m | Y: 0.00m | Z: 0.00m | Yaw: 0.0°")

    def update_trajectory(self, state):
        self.canvas.update_position(state.pos_x, state.pos_y, state.pos_z, state.yaw)
        self.lbl_pos.setText(f"Posisi Terkini: X: {state.pos_x:.2f}m | Y: {state.pos_y:.2f}m | Z: {state.pos_z:.2f}m | Yaw: {state.yaw:.1f}°")
