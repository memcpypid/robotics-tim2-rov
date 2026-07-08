import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

# Add paths
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

from gui.main_window import MainWindow

app = None
window = None

def capture():
    global window, app
    try:
        # Capture the window
        pixmap = window.grab()
        screenshot_path = os.path.join(current_dir, "gui_screenshot.png")
        pixmap.save(screenshot_path)
        print(f"Screenshot successfully saved to {screenshot_path}")
    except Exception as e:
        print("Failed to capture screenshot:", e)
    finally:
        app.quit()

def main():
    global app, window
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    
    QTimer.singleShot(1500, capture)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
