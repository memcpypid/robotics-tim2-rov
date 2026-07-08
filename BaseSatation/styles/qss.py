"""
QSS (Qt Style Sheets) untuk Tema Modern Dark Futuristic HUD Base Station ROV.
"""

DARK_HUD_THEME = """
/* Global Application Style */
QMainWindow {
    background-color: #0f141d;
    color: #e0e6ed;
    font-family: 'Segoe UI', 'Inter', 'Roboto', sans-serif;
}

QWidget {
    color: #e0e6ed;
    font-family: 'Segoe UI', 'Inter', 'Roboto', sans-serif;
    font-size: 13px;
}

/* GroupBox & Panels */
QGroupBox {
    background-color: #171f2e;
    border: 1px solid #28354d;
    border-radius: 8px;
    margin-top: 24px;
    padding-top: 14px;
    font-weight: bold;
    font-size: 14px;
    color: #00e5ff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 10px;
    background-color: #1f2c40;
    border: 1px solid #00e5ff;
    border-radius: 4px;
    color: #00e5ff;
    left: 12px;
}

/* Buttons */
QPushButton {
    background-color: #202d42;
    border: 1px solid #324666;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
    color: #c5d2e8;
}

QPushButton:hover {
    background-color: #2b3d59;
    border-color: #00e5ff;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #152030;
    border-color: #00b2cc;
}

QPushButton:disabled {
    background-color: #121924;
    border-color: #1f2a3d;
    color: #52637a;
}

/* Primary Action Buttons (Connect / ARM) */
QPushButton#btn_connect {
    background-color: #0066cc;
    border: 1px solid #0088ff;
    color: #ffffff;
    font-weight: bold;
}
QPushButton#btn_connect:hover {
    background-color: #0080ff;
    border-color: #66b8ff;
}
QPushButton#btn_connect:checked {
    background-color: #cc2929;
    border-color: #ff4d4d;
}

QPushButton#btn_arm {
    background-color: #1a6634;
    border: 1px solid #26994d;
    color: #ffffff;
    font-weight: bold;
    font-size: 14px;
}
QPushButton#btn_arm:hover {
    background-color: #238a46;
    border-color: #40bf6a;
}
QPushButton#btn_arm:checked {
    background-color: #a61c1c;
    border-color: #e62e2e;
    color: #ffffff;
}

/* Inputs & ComboBox */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #121824;
    border: 1px solid #2d3e5c;
    border-radius: 5px;
    padding: 6px 10px;
    color: #ffffff;
    selection-background-color: #00e5ff;
    selection-color: #000000;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid #00e5ff;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left-width: 1px;
    border-left-color: #2d3e5c;
    border-left-style: solid;
}

QComboBox QAbstractItemView {
    background-color: #171f2e;
    border: 1px solid #00e5ff;
    selection-background-color: #202d42;
    selection-color: #00e5ff;
}

/* Tab Widget & Tab Bars */
QTabWidget::pane {
    border: 1px solid #28354d;
    background-color: #121824;
    border-radius: 6px;
    padding: 6px;
}

QTabBar::tab {
    background-color: #171f2e;
    border: 1px solid #28354d;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 18px;
    margin-right: 4px;
    color: #899cb8;
    font-weight: bold;
}

QTabBar::tab:selected {
    background-color: #1f2c40;
    border: 1px solid #00e5ff;
    border-bottom: 2px solid #1f2c40;
    color: #00e5ff;
}

QTabBar::tab:hover:!selected {
    background-color: #1a2436;
    color: #ffffff;
}

/* Labels */
QLabel {
    color: #c5d2e8;
}
QLabel#header_label {
    font-size: 16px;
    font-weight: 800;
    color: #00e5ff;
}
QLabel#header_team {
    font-size: 14px;
    font-weight: bold;
    color: #ffcc00;
    background-color: #222014;
    padding: 4px 14px;
    border: 1px solid #665200;
    border-radius: 5px;
}
QLabel#value_label {
    font-size: 20px;
    font-weight: bold;
    color: #ffffff;
}

/* Progress Bar (Battery / Depth) */
QProgressBar {
    background-color: #121824;
    border: 1px solid #2d3e5c;
    border-radius: 6px;
    text-align: center;
    color: #ffffff;
    font-weight: bold;
}

QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00b2cc, stop:1 #00e5ff);
    border-radius: 5px;
}

/* TextEdit / Log Console */
QTextEdit, QPlainTextEdit {
    background-color: #0a0e14;
    border: 1px solid #1f2c40;
    border-radius: 6px;
    padding: 8px;
    color: #a6e3e9;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #121824;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #2d3e5c;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #00e5ff;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""
