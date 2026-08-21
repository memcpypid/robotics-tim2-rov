from ursina import *
import math
from udp_link import UDPLink
from kinematics import ROVKinematics

def update():
    """Fungsi utama yang dipanggil oleh Ursina setiap frame (60 FPS)."""
    # 1. Update paket UDP
    udp.update()
    
    # 2. Map input joystick ke 6 thruster
    kinematics.map_to_thrusters(udp.cmd_x, udp.cmd_y, udp.cmd_z, udp.cmd_r)
    
    # 3. Hitung kecepatan pergerakan
    v_surge, v_sway, v_heave, v_yaw = kinematics.calculate_velocity(time.dt)
    
    # 4. Gerakkan model ROV (Ursina menggunakan koordinat y sebagai atas-bawah)
    # Putar ROV di sumbu Y (Yaw)
    rov.rotation_y += v_yaw
    
    # Translasi maju/mundur searah dengan rotasi ROV (local coordinate)
    rov.position += rov.forward * v_surge
    rov.position += rov.right * v_sway
    rov.y -= v_heave  # Asumsi z positif (depth/heave) berarti turun ke bawah

    # Batasi pergerakan agar tidak menembus kolam (5x5x2m)
    # Kolam: x dari -2.5 s/d 2.5, z dari -2.5 s/d 2.5, kedalaman (y) dari 0 s/d -2.0
    rov.x = clamp(rov.x, -2.5, 2.5)
    rov.z = clamp(rov.z, -2.5, 2.5)
    rov.y = clamp(rov.y, -2.0, 0.0)

    # 5. Visualisasikan Thruster (ubah warna hijau/merah berdasarkan arah dorong)
    for i, t_val in enumerate(kinematics.thrusters):
        intensity = abs(t_val)
        if t_val > 0.1:
            thruster_entities[i].color = color.rgba(0, 255, 0, int(255 * intensity))
        elif t_val < -0.1:
            thruster_entities[i].color = color.rgba(255, 0, 0, int(255 * intensity))
        else:
            thruster_entities[i].color = color.gray
            
    # 6. Kirim Telemetri balik ke Base Station (setiap ~0.05 detik / 20Hz)
    if hasattr(udp, 'last_telemetry_time'):
        if time.time() - udp.last_telemetry_time > 0.05:
            # Kirim (pos_x, pos_y, pos_z, pitch, roll, yaw)
            # Karena Ursina pakai sistem koordinat Y-up, kita convert ke Z-down standard robotika
            # pos_x (North) = Ursina z
            # pos_y (East) = Ursina x
            # pos_z (Depth) = -Ursina y
            udp.send_telemetry(
                pos_x=rov.z, 
                pos_y=rov.x, 
                pos_z=-rov.y, 
                pitch=0.0, 
                roll=0.0, 
                yaw=rov.rotation_y
            )
            udp.last_telemetry_time = time.time()
    else:
        udp.last_telemetry_time = time.time()

# ==========================================================
# Inisialisasi Environment 3D
# ==========================================================
if __name__ == '__main__':
    app = Ursina(title="ROV 3D Kinematic Simulator", size=(1024, 768))

    # Inisialisasi Jaringan & Logika Gerak
    udp = UDPLink(command_port=9001, telemetry_port=9000)
    kinematics = ROVKinematics()

    print("[SIMULATOR] Berjalan di port UDP 9001. Menunggu koneksi Base Station...")

    # Kamera
    cam = EditorCamera() # Memungkinkan pengguna memutar kamera dengan mouse kanan
    # Mencegah EditorCamera ikut berputar saat analog kanan (gamepad) digerakkan
    orig_cam_update = cam.update
    def custom_cam_update():
        held_keys['gamepad right stick x'] = 0
        held_keys['gamepad right stick y'] = 0
        orig_cam_update()
    cam.update = custom_cam_update

    # Lingkungan Kolam (5m x 5m x 2m)
    # Dibuat transparan hanya garis tepi (wireframe) sesuai permintaan
    pool_bounds = Entity(model='wireframe_cube', scale=(5, 2, 5), color=color.rgba(0, 150, 255, 255), position=(0, -1, 0))

    # Objek ROV (Skala 0.35 x 0.25 x 0.35 meter)
    rov = Entity(model='cube', scale=(0.35, 0.25, 0.35), color=color.orange, position=(0, 0, 0))
    
    # Tanda depan (Front) berupa balok merah agar jelas arah majunya
    nose = Entity(parent=rov, model='cube', scale=(0.6, 0.1, 0.1), color=color.red, position=(0, 0, 0.5))
    
    # Tanda Axis X, Y, Z pada bodi ROV (Standar: X=Merah, Y=Hijau, Z=Biru)
    axis_x = Entity(parent=rov, model='cube', scale=(1.2, 0.02, 0.02), color=color.red, position=(0, 0, 0))
    axis_y = Entity(parent=rov, model='cube', scale=(0.02, 1.2, 0.02), color=color.green, position=(0, 0, 0))
    axis_z = Entity(parent=rov, model='cube', scale=(0.02, 0.02, 1.2), color=color.blue, position=(0, 0, 0))

    # 6 Thruster Vectored pada ROV (T1 s/d T6)
    # Format: [X, Y, Z] relatif terhadap ROV
    thruster_positions = [
        (0.6, 0.0, 0.6),   # T1: Depan Kanan
        (-0.6, 0.0, 0.6),  # T2: Depan Kiri
        (0.6, 0.0, -0.6),  # T3: Belakang Kanan
        (-0.6, 0.0, -0.6), # T4: Belakang Kiri
        (0.4, 0.6, 0.0),   # T5: Vertikal Kanan
        (-0.4, 0.6, 0.0)   # T6: Vertikal Kiri
    ]

    thruster_entities = []
    for i, pos in enumerate(thruster_positions):
        # Kalau Vertikal (T5, T6), silindernya tegak (rotasi X 0)
        # Kalau Horizontal (T1-T4), silindernya mendatar (rotasi X 90)
        rot_x = 0 if i >= 4 else 90
        
        # Rotasi vectored 45 derajat untuk T1-T4
        rot_y = 0
        if i == 0 or i == 3: rot_y = 45   # Depan Kanan & Belakang Kiri
        elif i == 1 or i == 2: rot_y = -45 # Depan Kiri & Belakang Kanan

        # Menggunakan 'cube' memanjang karena beberapa versi ursina tidak memiliki 'cylinder'
        t = Entity(parent=rov, model='cube', scale=(0.15, 0.3, 0.15), 
                   position=pos, rotation_x=rot_x, rotation_y=rot_y, color=color.gray)
        thruster_entities.append(t)

    # UI Teks Bantuan
    Text(text="ROV 3D Kinematic Simulator\nKoneksikan Base Station ke 127.0.0.1\nTahan Klik Kanan untuk putar kamera", 
         origin=(-0.5, 0.5), position=(-0.85, 0.45), scale=1.2, color=color.black)

    # Jalankan App
    app.run()
