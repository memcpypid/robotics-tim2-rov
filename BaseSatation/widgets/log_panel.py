from PySide6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QTextEdit
from PySide6.QtCore import Qt
import datetime


class LogPanel(QWidget):
    """
    Panel Log & Event Console real-time untuk memantau status komunikasi dan pesan error/warning.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("SYSTEM & TELEMETRY LOGS")
        group_layout = QVBoxLayout(group)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        group_layout.addWidget(self.txt_log)

        layout.addWidget(group)

    def append_log(self, message: str, level: str = "INFO"):
        """Menambahkan entri log baru dengan format warna berdasarkan level (INFO, WARN, ERROR)."""
        time_str = datetime.datetime.now().strftime("%H:%M:%S")
        
        color_map = {
            "INFO": "#00e5ff",
            "SUCCESS": "#40bf6a",
            "WARN": "#ffcc00",
            "ERROR": "#ff4d4d",
            "DEBUG": "#899cb8"
        }
        color = color_map.get(level.upper(), "#e0e6ed")

        formatted_msg = f'<span style="color: #6c809a;">[{time_str}]</span> <span style="color: {color}; font-weight: bold;">[{level}]</span> <span style="color: #e0e6ed;">{message}</span>'
        self.txt_log.append(formatted_msg)
