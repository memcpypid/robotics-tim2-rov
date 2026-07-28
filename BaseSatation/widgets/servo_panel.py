import json
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QGroupBox, QLineEdit, QComboBox, QGridLayout, QMessageBox,
    QTabWidget, QFrame
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False


# ============================================================
# Nama tombol joystick berdasarkan pola umum (Xbox/Generic USB)
# ============================================================
XBOX_BUTTON_NAMES = {
    0: "A",
    1: "B",
    2: "X",
    3: "Y",
    4: "LB (L1)",
    5: "RB (R1)",
    6: "BACK / SELECT",
    7: "START",
    8: "LS (Stick Kiri Tekan)",
    9: "RS (Stick Kanan Tekan)",
    10: "Xbox / Guide",
}

class JoystickTesterWidget(QWidget):
    """Widget untuk mengidentifikasi nomor tombol joystick secara live."""

    # Signal agar ServoPanel bisa menerima nomor tombol yang ditekan
    sig_button_pressed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._poll)
        self._joystick = None
        self._prev_buttons = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        title = QLabel("JOYSTICK BUTTON FINDER")
        title.setStyleSheet("font-weight: bold; font-size: 13px; color: #ffd54f;")
        layout.addWidget(title)

        desc = QLabel(
            "Hubungkan joystick Anda, lalu tekan sembarang tombol untuk\n"
            "melihat nomor dan nama tombolnya secara langsung."
        )
        desc.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(desc)

        # Status bar joystick
        self.lbl_joystick_name = QLabel("Status: Tidak ada joystick terdeteksi")
        self.lbl_joystick_name.setStyleSheet(
            "background: #1a2535; border: 1px solid #33445a; border-radius: 4px; "
            "padding: 5px 10px; color: #ff7043;"
        )
        layout.addWidget(self.lbl_joystick_name)

        # Area tampilan tombol yang ditekan (BESAR & JELAS)
        self.lbl_button_display = QLabel("Belum Ada Tombol Ditekan")
        self.lbl_button_display.setAlignment(Qt.AlignCenter)
        self.lbl_button_display.setStyleSheet(
            "background: #0d1b2a; border: 2px solid #00e5ff; border-radius: 8px; "
            "padding: 20px; color: #00e5ff; font-size: 22px; font-weight: bold;"
        )
        self.lbl_button_display.setMinimumHeight(90)
        layout.addWidget(self.lbl_button_display)

        # Tabel semua tombol yang ditekan sekarang
        self.lbl_all_pressed = QLabel("Tombol aktif: -")
        self.lbl_all_pressed.setStyleSheet("color: #80cbc4; font-size: 11px;")
        layout.addWidget(self.lbl_all_pressed)

        # Referensi pemetaan tombol Xbox
        ref_group = QGroupBox("Referensi Pemetaan Tombol (Xbox 360 / Generic)")
        ref_group.setStyleSheet("QGroupBox { font-weight: bold; color: #aaa; border: 1px solid #33445a; margin-top: 1ex; }")
        ref_layout = QGridLayout(ref_group)
        ref_layout.setSpacing(4)

        sorted_items = sorted(XBOX_BUTTON_NAMES.items())
        for i, (btn_idx, btn_name) in enumerate(sorted_items):
            row, col = divmod(i, 2)
            badge = QLabel(f"  #{btn_idx}")
            badge.setStyleSheet(
                "background: #1e3a5f; color: #81d4fa; border-radius: 3px; "
                "font-weight: bold; padding: 2px 6px;"
            )
            ref_layout.addWidget(badge, row, col * 2)
            ref_layout.addWidget(QLabel(f"= {btn_name}"), row, col * 2 + 1)

        layout.addWidget(ref_group)

        # Tombol start/stop
        self.btn_toggle = QPushButton("Mulai Deteksi Tombol")
        self.btn_toggle.setStyleSheet(
            "background-color: #00695c; color: white; font-weight: bold; padding: 6px;"
        )
        self.btn_toggle.clicked.connect(self.toggle_detection)
        layout.addWidget(self.btn_toggle)

        if not PYGAME_AVAILABLE:
            self.btn_toggle.setEnabled(False)
            self.btn_toggle.setText("pygame tidak tersedia - Tidak bisa mendeteksi")

    def toggle_detection(self):
        if self._timer.isActive():
            self._timer.stop()
            if self._joystick:
                try:
                    self._joystick.quit()
                except Exception:
                    pass
                self._joystick = None
            self.btn_toggle.setText("Mulai Deteksi Tombol")
            self.btn_toggle.setStyleSheet(
                "background-color: #00695c; color: white; font-weight: bold; padding: 6px;"
            )
            self.lbl_joystick_name.setText("Status: Deteksi dihentikan.")
            self.lbl_joystick_name.setStyleSheet(
                "background: #1a2535; border: 1px solid #33445a; border-radius: 4px; "
                "padding: 5px 10px; color: #ff7043;"
            )
        else:
            if not PYGAME_AVAILABLE:
                return
            try:
                pygame.init()
                pygame.joystick.init()
            except Exception as e:
                self.lbl_joystick_name.setText(f"Error init pygame: {e}")
                return

            self._timer.start()
            self.btn_toggle.setText("Hentikan Deteksi")
            self.btn_toggle.setStyleSheet(
                "background-color: #b71c1c; color: white; font-weight: bold; padding: 6px;"
            )

    def _poll(self):
        if not PYGAME_AVAILABLE:
            return
        try:
            pygame.event.pump()
            count = pygame.joystick.get_count()
            if count == 0:
                self.lbl_joystick_name.setText("Status: Tidak ada joystick terdeteksi — Colokkan controller Anda.")
                self.lbl_joystick_name.setStyleSheet(
                    "background: #1a2535; border: 1px solid #33445a; border-radius: 4px; "
                    "padding: 5px 10px; color: #ff7043;"
                )
                self._joystick = None
                self._prev_buttons = []
                return

            if self._joystick is None:
                self._joystick = pygame.joystick.Joystick(0)
                self._joystick.init()
                name = self._joystick.get_name()
                n_btn = self._joystick.get_numbuttons()
                self.lbl_joystick_name.setText(f"✔  {name}  |  {n_btn} tombol terdeteksi")
                self.lbl_joystick_name.setStyleSheet(
                    "background: #0a3d1f; border: 1px solid #2e7d32; border-radius: 4px; "
                    "padding: 5px 10px; color: #69f0ae;"
                )
                self._prev_buttons = [0] * n_btn

            num_buttons = self._joystick.get_numbuttons()
            current = [self._joystick.get_button(i) for i in range(num_buttons)]

            # Tombol yang baru SAJA ditekan (single press detection)
            newly_pressed = []
            for idx in range(num_buttons):
                if len(self._prev_buttons) > idx and current[idx] and not self._prev_buttons[idx]:
                    newly_pressed.append(idx)

            if newly_pressed:
                last = newly_pressed[-1]
                btn_name = XBOX_BUTTON_NAMES.get(last, f"Tombol Tidak Dikenal")
                self.lbl_button_display.setText(f"Tombol #{last}\n{btn_name}")
                self.sig_button_pressed.emit(last)

            # Tampilkan SEMUA tombol yang sedang ditahan
            held = [str(i) for i, s in enumerate(current) if s]
            if held:
                self.lbl_all_pressed.setText(f"Tombol aktif saat ini: [{', '.join(held)}]")
            else:
                self.lbl_all_pressed.setText("Tombol aktif: -")

            self._prev_buttons = current

        except Exception:
            pass

    def stop(self):
        self._timer.stop()


class ServoPanel(QWidget):
    sig_config_saved = Signal()  # Emit saat config disimpan agar JoystickWorker bisa reload

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'servo_config.json'))
        self.servos_data = []
        self._init_ui()
        self.load_config()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)

        # Tab internal: Servo Config & Button Finder
        self.inner_tabs = QTabWidget()

        # === TAB 1: KONFIGURASI SERVO ===
        servo_tab = QWidget()
        servo_layout = QVBoxLayout(servo_tab)

        header = QLabel("PENGATURAN SERVO (Gripper, Arm, Shoulder)")
        header.setStyleSheet("font-weight: bold; font-size: 14px; color: #00e5ff;")
        servo_layout.addWidget(header)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.addStretch()
        self.scroll_area.setWidget(self.scroll_widget)
        servo_layout.addWidget(self.scroll_area)

        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("+ Tambah Servo")
        self.btn_save = QPushButton("💾 Simpan Konfigurasi")
        self.btn_save.setStyleSheet(
            "background-color: #1565c0; color: white; font-weight: bold; padding: 6px;"
        )
        self.btn_add.clicked.connect(self.add_servo_ui)
        self.btn_save.clicked.connect(self.save_config)
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_save)
        servo_layout.addLayout(btn_layout)

        self.inner_tabs.addTab(servo_tab, "⚙️ Konfigurasi Servo")

        # === TAB 2: JOYSTICK BUTTON FINDER ===
        self.btn_finder = JoystickTesterWidget()
        self.inner_tabs.addTab(self.btn_finder, "🕹️ Cari Nomor Tombol Joystick")

        main_layout.addWidget(self.inner_tabs)
        self.servo_widgets = []

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    self.servos_data = data.get("servos", [])
            except Exception as e:
                print(f"Error loading servo config: {e}")
        self.refresh_ui()

    def refresh_ui(self):
        for w in self.servo_widgets:
            w["group"].setParent(None)
            w["group"].deleteLater()
        self.servo_widgets.clear()
        for servo in self.servos_data:
            self.add_servo_ui(servo)

    def add_servo_ui(self, data=None):
        if data is False or data is None:
            data = {
                "name": "Servo Baru", "pin": 9,
                "min_pwm": 1000, "max_pwm": 2000, "trim_pwm": 1500,
                "mode": "toggle", "btn_1": -1, "btn_2": -1, "step": 20
            }

        group = QGroupBox(data.get("name", "Servo"))
        group.setStyleSheet(
            "QGroupBox { font-weight: bold; border: 1px solid #444; border-radius: 5px; "
            "margin-top: 1ex; padding: 10px; }"
        )
        layout = QGridLayout(group)

        # Row 0: Nama & Pin
        layout.addWidget(QLabel("Nama:"), 0, 0)
        le_name = QLineEdit(str(data.get("name", "")))
        layout.addWidget(le_name, 0, 1)
        layout.addWidget(QLabel("Pin (9-14):"), 0, 2)
        le_pin = QLineEdit(str(data.get("pin", 9)))
        layout.addWidget(le_pin, 0, 3)

        # Row 1: Min & Max PWM
        layout.addWidget(QLabel("Min PWM:"), 1, 0)
        le_min = QLineEdit(str(data.get("min_pwm", 1000)))
        layout.addWidget(le_min, 1, 1)
        layout.addWidget(QLabel("Max PWM:"), 1, 2)
        le_max = QLineEdit(str(data.get("max_pwm", 2000)))
        layout.addWidget(le_max, 1, 3)

        # Row 2: Trim & Step
        layout.addWidget(QLabel("Trim PWM:"), 2, 0)
        le_trim = QLineEdit(str(data.get("trim_pwm", 1500)))
        layout.addWidget(le_trim, 2, 1)
        layout.addWidget(QLabel("Step (Speed):"), 2, 2)
        le_step = QLineEdit(str(data.get("step", 20)))
        layout.addWidget(le_step, 2, 3)

        # Row 3: Mode
        layout.addWidget(QLabel("Mode:"), 3, 0)
        cb_mode = QComboBox()
        cb_mode.addItems(["toggle", "3-state", "incremental", "follow_roll", "follow_pitch", "follow_yaw"])
        cb_mode.setCurrentText(data.get("mode", "toggle"))
        layout.addWidget(cb_mode, 3, 1)

        # Row 4: Tombol
        layout.addWidget(QLabel("Btn 1 (Toggle/Naik):"), 4, 0)
        le_btn1 = QLineEdit(str(data.get("btn_1", -1)))
        layout.addWidget(le_btn1, 4, 1)

        # Tombol helper: klik untuk isi otomatis dari Button Finder
        btn_pick1 = QPushButton("Ambil dari Finder →")
        btn_pick1.setStyleSheet("font-size: 10px; padding: 2px 6px; color: #ffd54f;")
        btn_pick1.clicked.connect(
            lambda: self._switch_to_finder_and_pick(le_btn1, btn_pick1)
        )
        layout.addWidget(btn_pick1, 4, 2)

        layout.addWidget(QLabel("Btn 2 (Turun):"), 5, 0)
        le_btn2 = QLineEdit(str(data.get("btn_2", -1)))
        layout.addWidget(le_btn2, 5, 1)

        btn_pick2 = QPushButton("Ambil dari Finder →")
        btn_pick2.setStyleSheet("font-size: 10px; padding: 2px 6px; color: #ffd54f;")
        btn_pick2.clicked.connect(
            lambda: self._switch_to_finder_and_pick(le_btn2, btn_pick2)
        )
        layout.addWidget(btn_pick2, 5, 2)

        btn_delete = QPushButton("Hapus")
        btn_delete.setStyleSheet("background-color: #aa0000; color: white;")
        layout.addWidget(btn_delete, 5, 3)

        widget_refs = {
            "group": group, "name": le_name, "pin": le_pin,
            "min": le_min, "max": le_max, "trim": le_trim, "step": le_step,
            "mode": cb_mode, "btn1": le_btn1, "btn2": le_btn2
        }

        btn_delete.clicked.connect(lambda: self.remove_servo_ui(widget_refs))
        self.servo_widgets.append(widget_refs)
        # Insert sebelum stretch (item terakhir)
        self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, group)

    def _switch_to_finder_and_pick(self, target_lineedit: QLineEdit, pick_btn: QPushButton):
        """Pindah ke tab Finder dan saat tombol ditekan, isi ke field yang dituju."""
        self.inner_tabs.setCurrentIndex(1)
        # Sambungkan signal sekali saja
        self._pending_field = target_lineedit
        try:
            self.btn_finder.sig_button_pressed.disconnect(self._on_button_picked)
        except Exception:
            pass
        self.btn_finder.sig_button_pressed.connect(self._on_button_picked)

    def _on_button_picked(self, btn_idx: int):
        if hasattr(self, '_pending_field') and self._pending_field:
            self._pending_field.setText(str(btn_idx))
            self._pending_field = None
            try:
                self.btn_finder.sig_button_pressed.disconnect(self._on_button_picked)
            except Exception:
                pass
            # Kembali ke tab config
            self.inner_tabs.setCurrentIndex(0)

    def remove_servo_ui(self, widget_refs):
        group = widget_refs["group"]
        self.scroll_layout.removeWidget(group)
        group.setParent(None)
        group.deleteLater()
        if widget_refs in self.servo_widgets:
            self.servo_widgets.remove(widget_refs)

    def save_config(self):
        new_data = []
        for w in self.servo_widgets:
            try:
                servo = {
                    "name": w["name"].text(),
                    "pin": int(w["pin"].text()),
                    "min_pwm": int(w["min"].text()),
                    "max_pwm": int(w["max"].text()),
                    "trim_pwm": int(w["trim"].text()),
                    "step": int(w["step"].text()),
                    "mode": w["mode"].currentText(),
                    "btn_1": int(w["btn1"].text()),
                    "btn_2": int(w["btn2"].text())
                }
                new_data.append(servo)
            except ValueError:
                QMessageBox.warning(self, "Input Error", "Pastikan semua nilai angka diisi dengan benar (Pin, PWM, Tombol).")
                return

        self.servos_data = new_data
        try:
            with open(self.config_path, 'w') as f:
                json.dump({"servos": self.servos_data}, f, indent=4)
            QMessageBox.information(self, "Tersimpan", "Konfigurasi servo berhasil disimpan!")
            self.sig_config_saved.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Gagal menyimpan file: {e}")

    def closeEvent(self, event):
        self.btn_finder.stop()
        super().closeEvent(event)
