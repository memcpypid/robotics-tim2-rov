# Base Station ROV

Base Station GUI untuk robot bawah air (ROV) yang dibuat dengan framework PySide6. Aplikasi ini berfungsi sebagai pusat kendali dan monitoring jarak jauh, menggantikan joystick fisik dengan antarmuka digital yang intuitif.

## 🚀 Fitur Utama

### 📊 Telemetry Dashboard
Menampilkan data real-time dari sensor kapal robot: 
- Kedalaman (Depth) & Ketinggian (Altitude)
- Kecepatan vertikal dan lateral
- Status baterai (Voltase & Persentase)
- Sudut attitude (Roll, Pitch, Yaw) dengan visualisasi HUD

### 🎮 Advanced Joystick Control
Menggantikan joystick fisik dengan kontrol digital:
- **Touch Joystick**: Pad virtual di layar untuk gerakan halus
- **Arrow Button**: Tombol arah presisi untuk manuver terukur
- **Toggle Mode**: Sakelar cepat antara mode manual (joystick) dan mode "Auto-Pilot"

### 📹 Video Feed
Integrasi langsung dengan kamera kapal untuk tampilan bawah air secara real-time.

### 💾 Logging & Records
- Menyimpan log telemetri lengkap ke database SQLite
- Fitur rekam video otomatis saat dalam mode "Auto-Pilot"
- Histori data untuk analisis performa

## 📋 Instalasi & Persiapan

### Prasyarat
- Python 3.8+
- Qt 6 (disarankan melalui PySide6)

### Langkah Instalasi

1.  **Clone Repositori**
    ```bash
    git clone <repository-url>
    cd BaseSatation
    ```

2.  **Buat Virtual Environment**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # Linux/Mac
    # .venv\Scripts\activate  # Windows
    ```

3.  **Instal Dependensi**
    ```bash
    pip install PySide6
    ```

## 🏃 Menjalankan Aplikasi

Setelah instalasi berhasil, jalankan aplikasi melalui file `main.py`:

```bash
python main.py
```

## 📡 Konfigurasi Koneksi

Aplikasi ini menggunakan protokol UDP untuk berkomunikasi dengan kapal.
- **IP Address**: `[IP_ADDRESS]` (default)
- **Port**: `5005` (default)

Pastikan IP Address komputer Anda sudah benar di-set pada konfigurasi kapal (Flight Control).

## 🎨 Desain & Styling

Antarmuka menggunakan tema gelap modern dengan aksen Cyan (`#00E5FF`) dan kuning (`#FFCC00`) untuk hierarki visual yang jelas dan mengurangi ketegangan mata saat penggunaan jangka panjang.
