"""
Joystick Mapper Panel (Modern UI)
==================================
Panel untuk memetakan semua fungsi joystick secara visual dan dinamis.
Fitur:
- Live visualisasi semua axis (bar animasi berwarna)
- Live visualisasi semua tombol (grid real-time)
- Pemetaan axis ke fungsi ROV (Forward, Strafe, Depth, Yaw)
- Pemetaan tombol ke aksi (ARM, DISARM, Mode, dll)
- Invert axis, pengaturan deadzone
- Simpan/Load dari joystick_config.json
"""
import json
import os
from typing import Optional, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QComboBox, QCheckBox, QDoubleSpinBox, QScrollArea,
    QGridLayout, QFrame, QSizePolicy, QSpacerItem, QMessageBox,
    QSlider
)
from PySide6.QtCore import Qt, Signal, QTimer, QPropertyAnimation, QRect
from PySide6.QtGui import QFont, QPainter, QColor, QPen, QBrush, QLinearGradient

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

# ──────────────────────────────────────────────
# Konstanta
# ──────────────────────────────────────────────
AXIS_FUNCTIONS = [
    ("none",      "— Tidak Dipakai —"),
    ("forward_x", "⬆ Maju / Mundur (Pitch/Surge)"),
    ("strafe_y",  "⬅ Geser Kiri / Kanan (Roll/Sway)"),
    ("depth_z",   "🔽 Naik / Turun (Heave/Depth)"),
    ("yaw_r",     "↻ Putar Kiri / Kanan (Yaw)"),
]

BUTTON_FUNCTIONS = [
    ("none",           "— Tidak Dipakai —"),
    ("arm",            "🔑 ARM ROV"),
    ("disarm",         "🛑 DISARM ROV"),
    ("depth_up",       "⬆ Naik Cepat"),
    ("depth_down",     "⬇ Turun Cepat"),
    ("mode_manual",    "🕹️ Mode: MANUAL"),
    ("mode_stabilize", "📐 Mode: STABILIZE"),
    ("mode_depth_hold","📏 Mode: DEPTH HOLD"),
    ("enable_depth_hold","⚓ Enable Depth Hold (MS5803)"),
    ("auto_toggle",    "🤖 Mode: AUTONOMOUS TOGGLE"),
    ("lights_toggle",  "💡 Lampu Toggle"),
]


XBOX_NAMES = {
    0:"A", 1:"B", 2:"X", 3:"Y",
    4:"LB", 5:"RB", 6:"BACK", 7:"START",
    8:"LS", 9:"RS", 10:"GUIDE"
}

CONFIG_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'joystick_config.json')
)

# ──────────────────────────────────────────────
# Widget: Satu Bar Axis (Animasi Live)
# ──────────────────────────────────────────────
class AxisBar(QWidget):
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.label = label
        self._value = 0.0   # -1.0 s/d 1.0
        self.setMinimumSize(140, 36)
        self.setMaximumHeight(36)

    def set_value(self, v: float):
        self._value = max(-1.0, min(1.0, v))
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        pad = 4

        # Background track
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#1a2535"))
        p.drawRoundedRect(pad, pad, w - 2*pad, h - 2*pad, 4, 4)

        # Center line
        cx = w // 2
        p.setPen(QPen(QColor("#2d3f55"), 1))
        p.drawLine(cx, pad + 2, cx, h - pad - 2)

        # Fill bar
        bar_w = int(abs(self._value) * ((w - 2*pad) / 2))
        if self._value >= 0:
            rx = cx
        else:
            rx = cx - bar_w
        
        # Gradient color: hijau saat kecil, kuning tengah, merah penuh
        intensity = abs(self._value)
        r = int(min(255, intensity * 500))
        g = int(max(0, 220 - intensity * 200))
        b = 80
        p.setBrush(QColor(r, g, b, 220))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(rx, pad + 3, bar_w, h - 2*pad - 6, 3, 3)

        # Label & nilai
        p.setPen(QColor("#cdd9e5"))
        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        p.drawText(pad + 4, 0, 50, h, Qt.AlignVCenter, self.label)

        val_str = f"{self._value:+.2f}"
        p.setPen(QColor("#00e5ff"))
        p.drawText(w - 54, 0, 50, h, Qt.AlignVCenter | Qt.AlignRight, val_str)

# ──────────────────────────────────────────────
# Widget: Grid Tombol Live
# ──────────────────────────────────────────────
class ButtonGrid(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._states: list = []
        self._n = 0
        self._labels: list = []
        self.setMinimumHeight(70)

    def set_buttons(self, states: list):
        if len(states) != self._n:
            self._n = len(states)
            self._labels = []
            for i in range(self._n):
                name = XBOX_NAMES.get(i, str(i))
                self._labels.append(f"#{i}\n{name}")
        self._states = states
        self.update()

    def paintEvent(self, e):
        if not self._n:
            p = QPainter(self)
            p.setPen(QColor("#444"))
            p.drawText(self.rect(), Qt.AlignCenter, "Tidak ada tombol terdeteksi")
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cols = min(self._n, 8)
        rows = (self._n + cols - 1) // cols
        bw = max(42, self.width() // cols - 4)
        bh = max(36, (self.height() - 4) // rows - 4)
        pad = 3

        for i in range(self._n):
            col = i % cols
            row = i // cols
            x = col * (bw + pad) + 2
            y = row * (bh + pad) + 2
            pressed = i < len(self._states) and self._states[i]
            
            if pressed:
                p.setBrush(QColor("#00c853"))
                p.setPen(QPen(QColor("#69f0ae"), 1.5))
            else:
                p.setBrush(QColor("#1e2d3d"))
                p.setPen(QPen(QColor("#2d4060"), 1))

            p.drawRoundedRect(x, y, bw, bh, 6, 6)

            p.setPen(QColor("#e8f0fe") if pressed else QColor("#7a8fa6"))
            p.setFont(QFont("Segoe UI", 7, QFont.Bold if pressed else QFont.Normal))
            label = XBOX_NAMES.get(i, str(i))
            p.drawText(x, y, bw, bh, Qt.AlignCenter, f"#{i}\n{label}")


# ──────────────────────────────────────────────
# Panel Utama: Joystick Mapper
# ──────────────────────────────────────────────
class JoystickMapperPanel(QWidget):
    sig_config_saved = Signal(dict)  # Emit config dict saat disimpan

    def __init__(self, parent=None):
        super().__init__(parent)
        self._joystick = None
        self._connected = False
        self._n_axes = 0
        self._n_buttons = 0

        self._timer = QTimer(self)
        self._timer.setInterval(50)  # 20 Hz
        self._timer.timeout.connect(self._poll)

        self.config: Dict[str, Any] = {}
        self._load_config()

        self._axis_bars: list = []
        self._axis_row_widgets: list = []  # [{cb_func, chk_inv, spn_dz}]
        self._button_row_widgets: list = []  # [{lbl, cb_func}]

        self._init_ui()
        self._start_polling()

    # ── Config I/O ─────────────────────────────
    def _load_config(self):
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, 'r') as f:
                    self.config = json.load(f)
        except Exception:
            self.config = {}

        # Defaults
        self.config.setdefault("axes", {})
        self.config.setdefault("buttons", {})
        self.config.setdefault("hat_depth", True)

    def _save_config(self):
        try:
            with open(CONFIG_PATH, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as ex:
            QMessageBox.critical(self, "Error", f"Gagal menyimpan: {ex}")

    # ── UI Init ────────────────────────────────
    def _init_ui(self):
        root = QHBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(8, 8, 8, 8)

        # ── LEFT: Live Visualizer ──
        vis_frame = QFrame()
        vis_frame.setStyleSheet("QFrame { background: #0d1520; border-radius: 10px; border: 1px solid #1e3050; }")
        vis_frame.setFixedWidth(340)
        vis_layout = QVBoxLayout(vis_frame)
        vis_layout.setContentsMargins(12, 12, 12, 12)
        vis_layout.setSpacing(8)

        lbl_vis = QLabel("🕹️  LIVE JOYSTICK MONITOR")
        lbl_vis.setStyleSheet("color:#00e5ff; font-weight:bold; font-size:12px;")
        vis_layout.addWidget(lbl_vis)

        # Status joystick
        self.lbl_status = QLabel("Mendeteksi joystick...")
        self.lbl_status.setStyleSheet(
            "background:#121e2c; border:1px solid #2d4060; border-radius:5px; "
            "padding:5px 10px; color:#ff7043; font-size:11px;"
        )
        self.lbl_status.setWordWrap(True)
        vis_layout.addWidget(self.lbl_status)

        # Axis Section
        lbl_ax = QLabel("AXIS")
        lbl_ax.setStyleSheet("color:#90caf9; font-size:10px; font-weight:bold; margin-top:4px;")
        vis_layout.addWidget(lbl_ax)

        self.axis_container = QWidget()
        self.axis_container_layout = QVBoxLayout(self.axis_container)
        self.axis_container_layout.setSpacing(3)
        self.axis_container_layout.setContentsMargins(0, 0, 0, 0)
        vis_layout.addWidget(self.axis_container)

        # Buttons Section
        lbl_btn = QLabel("TOMBOL")
        lbl_btn.setStyleSheet("color:#90caf9; font-size:10px; font-weight:bold; margin-top:4px;")
        vis_layout.addWidget(lbl_btn)

        self.btn_grid = ButtonGrid()
        self.btn_grid.setMinimumHeight(90)
        vis_layout.addWidget(self.btn_grid)

        vis_layout.addStretch()
        root.addWidget(vis_frame)

        # ── RIGHT: Mapping Editor ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        editor = QWidget()
        self.editor_layout = QVBoxLayout(editor)
        self.editor_layout.setSpacing(12)
        self.editor_layout.setContentsMargins(4, 0, 4, 4)
        scroll.setWidget(editor)
        root.addWidget(scroll, 1)

        # Axis Mapping Group
        self.grp_axes = QGroupBox("⚙️  PEMETAAN AXIS")
        self.grp_axes.setStyleSheet(self._group_style("#1e3050"))
        self.axes_grid = QGridLayout(self.grp_axes)
        self.axes_grid.setSpacing(6)
        headers = ["Axis #", "Nilai Live", "Fungsi", "Invert", "Deadzone", "Scale/Speed"]
        for c, h in enumerate(headers):
            lbl = QLabel(h)
            lbl.setStyleSheet("color:#7a8fa6; font-size:10px; font-weight:bold;")
            self.axes_grid.addWidget(lbl, 0, c)
        self.editor_layout.addWidget(self.grp_axes)

        # Button Mapping Group
        self.grp_buttons = QGroupBox("🎮  PEMETAAN TOMBOL")
        self.grp_buttons.setStyleSheet(self._group_style("#1e3050"))
        self.buttons_grid = QGridLayout(self.grp_buttons)
        self.buttons_grid.setSpacing(6)
        btn_headers = ["Tombol #", "Nama", "Fungsi"]
        for c, h in enumerate(btn_headers):
            lbl = QLabel(h)
            lbl.setStyleSheet("color:#7a8fa6; font-size:10px; font-weight:bold;")
            self.buttons_grid.addWidget(lbl, 0, c)
        self.editor_layout.addWidget(self.grp_buttons)

        # Hat Mapping
        hat_grp = QGroupBox("⬆️  D-PAD (HAT) sebagai Depth Up/Down")
        hat_grp.setStyleSheet(self._group_style("#1e3050"))
        hat_lay = QHBoxLayout(hat_grp)
        self.chk_hat = QCheckBox("Aktifkan D-Pad atas/bawah untuk kontrol kedalaman")
        self.chk_hat.setChecked(self.config.get("hat_depth", True))
        self.chk_hat.setStyleSheet("color:#cdd9e5;")
        hat_lay.addWidget(self.chk_hat)
        self.editor_layout.addWidget(hat_grp)

        # Save Button
        self.btn_save = QPushButton("💾  Simpan Pemetaan Joystick")
        self.btn_save.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #1565c0, stop:1 #0097a7); color:white; font-weight:bold; "
            "padding:10px; border-radius:7px; font-size:13px;"
        )
        self.btn_save.clicked.connect(self._on_save)
        self.editor_layout.addWidget(self.btn_save)
        self.editor_layout.addStretch()

    def _group_style(self, border_color: str) -> str:
        return (
            f"QGroupBox {{ font-weight:bold; color:#cdd9e5; "
            f"border:1px solid {border_color}; border-radius:8px; "
            f"margin-top:10px; padding:10px; background:#0d1828; }}"
            f"QGroupBox::title {{ subcontrol-origin:margin; left:10px; "
            f"padding:0 6px; color:#81d4fa; font-size:12px; }}"
        )

    # ── Polling ────────────────────────────────
    def _start_polling(self):
        if PYGAME_AVAILABLE:
            try:
                if not pygame.get_init():
                    pygame.init()
                if not pygame.joystick.get_init():
                    pygame.joystick.init()
            except Exception:
                pass
        self._timer.start()

    def _poll(self):
        if not PYGAME_AVAILABLE:
            return
        try:
            pygame.event.pump()
            count = pygame.joystick.get_count()

            if count == 0:
                if self._connected:
                    self._connected = False
                    self._joystick = None
                    self.lbl_status.setText("⚠️  Joystick terputus — colokkan controller Anda.")
                    self.lbl_status.setStyleSheet(
                        "background:#1a1a2e; border:1px solid #c62828; border-radius:5px; "
                        "padding:5px 10px; color:#ef9a9a; font-size:11px;"
                    )
                    self._clear_live_rows()
                return

            if not self._connected:
                self._joystick = pygame.joystick.Joystick(0)
                self._joystick.init()
                self._connected = True
                name = self._joystick.get_name()
                na = self._joystick.get_numaxes()
                nb = self._joystick.get_numbuttons()
                self.lbl_status.setText(f"✔  {name}\n{na} axis  |  {nb} tombol")
                self.lbl_status.setStyleSheet(
                    "background:#0a2e1a; border:1px solid #2e7d32; border-radius:5px; "
                    "padding:5px 10px; color:#69f0ae; font-size:11px;"
                )
                self._build_live_rows(na, nb)
                self._build_mapping_rows(na, nb)

            if not self._joystick:
                return

            na = self._joystick.get_numaxes()
            nb = self._joystick.get_numbuttons()
            axes = [self._joystick.get_axis(i) for i in range(na)]
            buttons = [self._joystick.get_button(i) for i in range(nb)]

            # Update axis bars
            for i, bar in enumerate(self._axis_bars):
                if i < len(axes):
                    bar.set_value(axes[i])

            # Update button grid
            self.btn_grid.set_buttons(buttons)

            # Update inline live labels in mapping grid
            for row_data in self._axis_row_widgets:
                idx = row_data.get("axis_idx", -1)
                lbl_live = row_data.get("lbl_live")
                if lbl_live and 0 <= idx < len(axes):
                    v = axes[idx]
                    color = "#69f0ae" if abs(v) > 0.1 else "#445566"
                    lbl_live.setText(f"{v:+.2f}")
                    lbl_live.setStyleSheet(f"color:{color}; font-weight:bold; font-size:11px;")

            for row_data in self._button_row_widgets:
                idx = row_data.get("btn_idx", -1)
                lbl_state = row_data.get("lbl_state")
                if lbl_state and 0 <= idx < len(buttons):
                    if buttons[idx]:
                        lbl_state.setText("● DITEKAN")
                        lbl_state.setStyleSheet("color:#69f0ae; font-weight:bold;")
                    else:
                        lbl_state.setText("○ Lepas")
                        lbl_state.setStyleSheet("color:#445566;")

        except Exception:
            pass

    # ── Build Live Axis Bars ───────────────────
    def _build_live_rows(self, n_axes: int, n_buttons: int):
        # Clear
        for bar in self._axis_bars:
            bar.setParent(None)
            bar.deleteLater()
        self._axis_bars.clear()

        for i in range(n_axes):
            bar = AxisBar(f"Axis {i}")
            self.axis_container_layout.addWidget(bar)
            self._axis_bars.append(bar)

    def _clear_live_rows(self):
        for bar in self._axis_bars:
            bar.set_value(0.0)
        self.btn_grid.set_buttons([])

    # ── Build Mapping Rows ─────────────────────
    def _build_mapping_rows(self, n_axes: int, n_buttons: int):
        if self._n_axes == n_axes and self._n_buttons == n_buttons:
            return  # Sudah dibangun

        self._n_axes = n_axes
        self._n_buttons = n_buttons

        # Clear old rows
        for row_data in self._axis_row_widgets:
            for w in row_data.values():
                if isinstance(w, QWidget):
                    w.setParent(None)
                    w.deleteLater()
        self._axis_row_widgets.clear()

        for row_data in self._button_row_widgets:
            for w in row_data.values():
                if isinstance(w, QWidget):
                    w.setParent(None)
                    w.deleteLater()
        self._button_row_widgets.clear()

        # --- Build axis rows ---
        axes_cfg = self.config.get("axes", {})
        # Buat reverse map: axis_idx -> func_key
        idx_to_func = {}
        idx_to_inv = {}
        idx_to_dz = {}
        idx_to_scale = {}
        for func_key, av in axes_cfg.items():
            if isinstance(av, dict):
                ai = av.get("axis", -1)
                idx_to_func[ai] = func_key
                idx_to_inv[ai] = av.get("invert", False)
                idx_to_dz[ai] = av.get("deadzone", 0.08)
                idx_to_scale[ai] = av.get("scale", 1.0)

        for i in range(n_axes):
            row = i + 1  # Header is row 0

            lbl_idx = QLabel(f"Axis {i}")
            lbl_idx.setStyleSheet("color:#cdd9e5; font-size:11px;")
            self.axes_grid.addWidget(lbl_idx, row, 0)

            lbl_live = QLabel("—")
            lbl_live.setStyleSheet("color:#445566; font-size:11px;")
            self.axes_grid.addWidget(lbl_live, row, 1)

            cb_func = QComboBox()
            cb_func.wheelEvent = lambda event: event.ignore()
            cb_func.setStyleSheet(self._combo_style())
            for val, label in AXIS_FUNCTIONS:
                cb_func.addItem(label, val)
            # Set current
            current_func = idx_to_func.get(i, "none")
            for j in range(cb_func.count()):
                if cb_func.itemData(j) == current_func:
                    cb_func.setCurrentIndex(j)
                    break
            self.axes_grid.addWidget(cb_func, row, 2)

            chk_inv = QCheckBox("Invert")
            chk_inv.setChecked(idx_to_inv.get(i, False))
            chk_inv.setStyleSheet("color:#9ab; font-size:10px;")
            self.axes_grid.addWidget(chk_inv, row, 3)

            spn_dz = QDoubleSpinBox()
            spn_dz.setRange(0.0, 0.5)
            spn_dz.setSingleStep(0.01)
            spn_dz.setDecimals(2)
            spn_dz.setValue(idx_to_dz.get(i, 0.08))
            spn_dz.setFixedWidth(70)
            spn_dz.setStyleSheet("background:#1a2535; color:#cdd9e5; border:1px solid #2d4060;")
            self.axes_grid.addWidget(spn_dz, row, 4)

            spn_scale = QDoubleSpinBox()
            spn_scale.setRange(0.1, 2.0)
            spn_scale.setSingleStep(0.1)
            spn_scale.setDecimals(2)
            spn_scale.setValue(idx_to_scale.get(i, 1.0))
            spn_scale.setFixedWidth(70)
            spn_scale.setStyleSheet("background:#1a2535; color:#cdd9e5; border:1px solid #2d4060;")
            self.axes_grid.addWidget(spn_scale, row, 5)

            self._axis_row_widgets.append({
                "axis_idx": i, "lbl_live": lbl_live,
                "cb_func": cb_func, "chk_inv": chk_inv, "spn_dz": spn_dz, "spn_scale": spn_scale
            })

        # --- Build button rows ---
        btn_cfg = self.config.get("buttons", {})
        func_to_btn = {v: k for k, v in btn_cfg.items() if isinstance(v, int) and v >= 0}

        for i in range(n_buttons):
            row = i + 1
            lbl_idx = QLabel(f"Btn #{i}")
            lbl_idx.setStyleSheet("color:#cdd9e5; font-size:11px;")
            self.buttons_grid.addWidget(lbl_idx, row, 0)

            lbl_state = QLabel("○ Lepas")
            lbl_state.setStyleSheet("color:#445566; font-size:10px;")
            self.buttons_grid.addWidget(lbl_state, row, 1)

            cb_func = QComboBox()
            cb_func.wheelEvent = lambda event: event.ignore()
            cb_func.setStyleSheet(self._combo_style())
            for val, label in BUTTON_FUNCTIONS:
                cb_func.addItem(label, val)
            current_func = func_to_btn.get(i, "none")
            for j in range(cb_func.count()):
                if cb_func.itemData(j) == current_func:
                    cb_func.setCurrentIndex(j)
                    break
            self.buttons_grid.addWidget(cb_func, row, 2)

            self._button_row_widgets.append({
                "btn_idx": i, "lbl_state": lbl_state, "cb_func": cb_func
            })

    def _combo_style(self) -> str:
        return (
            "QComboBox { background:#1a2535; color:#cdd9e5; border:1px solid #2d4060; "
            "border-radius:4px; padding:3px 6px; font-size:11px; min-width:170px; }"
            "QComboBox::drop-down { border:none; }"
            "QComboBox QAbstractItemView { background:#1a2535; color:#cdd9e5; selection-background-color:#1e3a5f; }"
        )

    # ── Save ───────────────────────────────────
    def _on_save(self):
        new_axes: Dict[str, Any] = {}
        # Kumpulkan pemetaan axis
        for row_data in self._axis_row_widgets:
            i = row_data["axis_idx"]
            func = row_data["cb_func"].currentData()
            if func == "none":
                continue
            invert = row_data["chk_inv"].isChecked()
            dz = row_data["spn_dz"].value()
            scale = row_data["spn_scale"].value() if "spn_scale" in row_data else 1.0
            new_axes[func] = {"axis": i, "invert": invert, "deadzone": dz, "scale": scale}

        new_buttons: Dict[str, int] = {}
        # Init semua fungsi ke -1
        for val, _ in BUTTON_FUNCTIONS:
            if val != "none":
                new_buttons[val] = -1
        # Override dengan pilihan user
        for row_data in self._button_row_widgets:
            i = row_data["btn_idx"]
            func = row_data["cb_func"].currentData()
            if func != "none":
                new_buttons[func] = i

        self.config["axes"] = new_axes
        self.config["buttons"] = new_buttons
        self.config["hat_depth"] = self.chk_hat.isChecked()

        self._save_config()
        self.sig_config_saved.emit(self.config)
        QMessageBox.information(self, "Tersimpan",
            "✅ Pemetaan joystick berhasil disimpan!\n"
            "Konfigurasi baru akan aktif otomatis.")

    def stop(self):
        self._timer.stop()
