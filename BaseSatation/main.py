"""
Main Entry Point untuk GUI Base Station ROV (PySide6).
Jalankan script ini dengan: python3 main.py
"""
import os
import sys

# Pastikan root folder berada dalam sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
except ImportError:
    print("[ERROR] Library PySide6 tidak ditemukan!")
    print("[HINT] Silakan install terlebih dahulu dengan: pip install PySide6")
    sys.exit(1)

from gui.main_window import MainWindow


def main():
    # Dalam PySide6 / Qt6, High-DPI scaling aktif secara default dan atribut AA_* telah deprecated
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
