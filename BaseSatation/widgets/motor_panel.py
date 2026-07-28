from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QSlider, QPushButton, QGroupBox, QGridLayout
)
from PySide6.QtCore import Qt, Signal

class MotorPanel(QWidget):
    """
    Panel Diagnostik Motor untuk Base Station.
    Menampilkan nilai PWM real-time dari ROV (Main/Throttle & Aux/Direction)
    dan menyediakan slider untuk melakukan Motor Test individual.
    """
    # Signal saat user menggerakkan slider test: channel (1-6, 0=reset), thrust (-1.0 to +1.0)
    sig_motor_test = Signal(int, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.num_motors = 6
        
        # Referensi UI element per motor
        self.bars_throttle = []
        self.lbls_throttle = []
        self.lbls_direction = []
        self.sliders_test = []
        self.lbls_slider_val = []

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        group_box = QGroupBox("MOTOR DIAGNOSTICS & INDIVIDUAL TEST")
        group_box.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #28354d;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
                color: #00e5ff;
            }
        """)
        
        grid = QGridLayout(group_box)
        grid.setSpacing(10)
        grid.setContentsMargins(15, 15, 15, 15)

        # Header Kolom
        grid.addWidget(QLabel("<b>MOTOR</b>"), 0, 0)
        grid.addWidget(QLabel("<b>THROTTLE (PWM)</b>"), 0, 1)
        grid.addWidget(QLabel("<b>ARAH</b>"), 0, 2)
        grid.addWidget(QLabel("<b>TEST THRUST</b>"), 0, 3, 1, 2)

        # Baris per motor (1 - 6)
        for i in range(self.num_motors):
            ch = i + 1
            row = i + 1

            # 1. Label Nama Motor
            lbl_name = QLabel(f"Thruster {ch}")
            lbl_name.setStyleSheet("font-weight: bold;")
            grid.addWidget(lbl_name, row, 0)

            # 2. Progress Bar Throttle (800 - 2000)
            bar = QProgressBar()
            bar.setRange(800, 2000)
            bar.setValue(800)  # Default idle
            bar.setTextVisible(False)
            bar.setMinimumWidth(150)
            bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #3c4c66;
                    border-radius: 4px;
                    background-color: #171f2e;
                    height: 18px;
                }
                QProgressBar::chunk {
                    background-color: #00e5ff;
                    border-radius: 3px;
                }
            """)
            
            lbl_val = QLabel("800 µs")
            lbl_val.setFixedWidth(55)
            
            hbox_pwm = QHBoxLayout()
            hbox_pwm.addWidget(bar)
            hbox_pwm.addWidget(lbl_val)
            grid.addLayout(hbox_pwm, row, 1)
            
            self.bars_throttle.append(bar)
            self.lbls_throttle.append(lbl_val)

            # 3. Label Arah
            lbl_dir = QLabel("MAJU")
            lbl_dir.setStyleSheet("color: #00ff00; font-weight: bold;") # Hijau = Maju
            lbl_dir.setFixedWidth(60)
            grid.addWidget(lbl_dir, row, 2)
            self.lbls_direction.append(lbl_dir)

            # 4. Slider Test (-100% sampai +100%)
            slider = QSlider(Qt.Horizontal)
            slider.setRange(-100, 100)
            slider.setValue(0)
            slider.setTickPosition(QSlider.TicksBelow)
            slider.setTickInterval(25)
            slider.setMinimumWidth(120)
            # Custom style slider
            slider.setStyleSheet("""
                QSlider::groove:horizontal {
                    border: 1px solid #3c4c66;
                    height: 8px;
                    background: #171f2e;
                    margin: 2px 0;
                    border-radius: 4px;
                }
                QSlider::handle:horizontal {
                    background: #ffaa00;
                    border: 1px solid #ffcc00;
                    width: 14px;
                    margin: -4px 0;
                    border-radius: 7px;
                }
            """)
            
            lbl_slider = QLabel("0%")
            lbl_slider.setFixedWidth(40)
            lbl_slider.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
            hbox_slider = QHBoxLayout()
            hbox_slider.addWidget(slider)
            hbox_slider.addWidget(lbl_slider)
            grid.addLayout(hbox_slider, row, 3)

            self.sliders_test.append(slider)
            self.lbls_slider_val.append(lbl_slider)

            # Binding signal slider (gunakan lambda dengan default arg untuk mencegah late-binding issue di loop Python)
            slider.valueChanged.connect(lambda val, idx=i: self._on_slider_changed(idx, val))
            slider.sliderReleased.connect(lambda idx=i: self._on_slider_released(idx))

        main_layout.addWidget(group_box)
        main_layout.addStretch()

        # Tombol Reset Test
        self.btn_reset = QPushButton("🛑 KEMBALI KE KONTROL NORMAL (STOP TEST)")
        self.btn_reset.setMinimumHeight(40)
        self.btn_reset.setStyleSheet("""
            QPushButton {
                background-color: #d32f2f;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #f44336;
            }
        """)
        self.btn_reset.clicked.connect(self.reset_all_tests)
        main_layout.addWidget(self.btn_reset)

    # ─────────────────────────────────────────────
    # Updates from Telemetry
    # ─────────────────────────────────────────────
    def update_pwm_data(self, pwm_list: list):
        """
        Diperbarui secara real-time dari telemetri ROV.
        pwm_list: [{'main': 1500, 'aux': 1300}, ...]
        """
        if not pwm_list:
            return
            
        for i in range(min(self.num_motors, len(pwm_list))):
            data = pwm_list[i]
            thr = data.get('main', 800)
            aux = data.get('aux', 1300)
            
            self.bars_throttle[i].setValue(thr)
            self.lbls_throttle[i].setText(f"{thr} µs")
            
            if aux < 1500:
                self.lbls_direction[i].setText("MAJU")
                self.lbls_direction[i].setStyleSheet("color: #00ff00; font-weight: bold;")
            else:
                self.lbls_direction[i].setText("MUNDUR")
                self.lbls_direction[i].setStyleSheet("color: #ff3333; font-weight: bold;")

    # ─────────────────────────────────────────────
    # Internal Handlers
    # ─────────────────────────────────────────────
    def _on_slider_changed(self, motor_idx: int, value: int):
        # Update text persentase
        self.lbls_slider_val[motor_idx].setText(f"{value}%")
        
        # Kirim signal test motor
        # thrust range: -1.0 to 1.0
        thrust = value / 100.0
        channel = motor_idx + 1
        self.sig_motor_test.emit(channel, thrust)

    def _on_slider_released(self, motor_idx: int):
        """Otomatis kembali ke 0 saat slider dilepas (opsional untuk safety)"""
        # Uncomment 2 baris di bawah jika ingin slider bersifat seperti joystick (spring back to 0)
        # self.sliders_test[motor_idx].setValue(0)
        # self.sig_motor_test.emit(motor_idx + 1, 0.0)
        pass

    def reset_all_tests(self):
        """Reset semua slider dan kirim signal channel=0 (normal mode)."""
        for slider in self.sliders_test:
            slider.blockSignals(True)
            slider.setValue(0)
            slider.blockSignals(False)
        
        for lbl in self.lbls_slider_val:
            lbl.setText("0%")
            
        # Emit signal 0 untuk menonaktifkan test mode (kirim 3x untuk keamanan UDP)
        import time
        for _ in range(3):
            self.sig_motor_test.emit(0, 0.0)
            time.sleep(0.05)
