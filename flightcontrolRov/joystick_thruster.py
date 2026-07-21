import pygame
import time
from pymavlink import mavutil

# --- KONFIGURASI MAVLINK ---
# Ganti dengan connection string yang sesuai dengan setup Anda.
# Contoh untuk koneksi langsung via serial: 'COM3' (Windows) atau '/dev/ttyACM0' (Linux)
# Contoh untuk koneksi Companion Computer (Raspberry Pi/BlueOS): 'udpin:0.0.0.0:14550'
CONNECTION_STRING = 'COM13' 

# --- KONFIGURASI PIN PIXHAWK ---
# Pastikan di parameter QGroundControl:
# - SERVO7_FUNCTION diset ke 0 (Disabled)
# - SERVO8_FUNCTION diset ke 0 (Disabled)
# Hal ini penting agar ArduSub tidak melakukan override pada perintah manual ini.
PIN_THRUSTER = 7
PIN_REVERSE = 8

# --- KONFIGURASI JOYSTICK ---
# Mapping tombol ini mungkin perlu disesuaikan tergantung OS dan jenis stick (PS3/PS4/PS5)
AXIS_LEFT_STICK_Y = 1  # Biasanya Axis 1 untuk Analog Kiri Atas/Bawah (Negatif = Atas)
BUTTON_R2 = 5          # Biasanya Button 5 untuk R2 di pygame

def set_servo_pwm(master, servo_n, pwm):
    """
    Mengirim perintah PWM MAV_CMD_DO_SET_SERVO ke pin servo tertentu.
    """
    master.mav.command_long_send(
        master.target_system, 
        master.target_component,
        mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
        0,            # confirmation
        servo_n,      # param 1: servo number
        pwm,          # param 2: pwm value (biasanya 1100 - 1900, 1500 = stop)
        0, 0, 0, 0, 0 # param 3-7: not used
    )

def main():
    # 1. Inisialisasi koneksi MAVLink
    print(f"Menghubungkan ke Pixhawk di {CONNECTION_STRING}...")
    try:
        master = mavutil.mavlink_connection(CONNECTION_STRING)
        master.wait_heartbeat(timeout=10)
        print("Berhasil terhubung ke Pixhawk!")
        
        # --- ARMING ---
        print("Meng-arm kendaraan (Arming)...")
        # Ingatkan user soal safety switch jika ada
        print("CATATAN: Jika Pixhawk memiliki tombol Safety Switch (lampu merah kedap-kedip), pastikan sudah ditekan hingga menyala solid!")
        
        master.arducopter_arm()
        master.motors_armed_wait()
        print("Kendaraan berhasil ARMED!")
    except Exception as e:
        print(f"Gagal terhubung atau arming Pixhawk: {e}")
        return

    # 2. Inisialisasi Pygame & Joystick
    pygame.init()
    pygame.joystick.init()
    
    if pygame.joystick.get_count() == 0:
        print("Joystick tidak terdeteksi! Pastikan joystick PS sudah terhubung ke komputer.")
        return
        
    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    print(f"Joystick terdeteksi: {joystick.get_name()}")
    
    # Deteksi apakah R2 dibaca sebagai axis alih-alih button (umum di PS4/PS5 controller Windows)
    # R2 biasanya axis 5 jika ada lebih dari 4 axis.
    r2_is_axis = joystick.get_numaxes() > 5 
    if r2_is_axis:
        print("Catatan: Trigger R2 kemungkinan terbaca sebagai Axis (Analog) di sistem ini.")
        AXIS_R2 = 5

    print("\nMemulai loop kontrol... Tekan Ctrl+C di terminal untuk berhenti.")
    
    try:
        while True:
            # Refresh event input dari pygame
            pygame.event.pump()
            
            # --- BACA INPUT JOYSTICK ---
            
            # Throttle (Analog Kiri - Axis Y)
            # Ditarik ke atas = nilai negatif (0.0 sampai -1.0)
            left_stick_y = joystick.get_axis(AXIS_LEFT_STICK_Y)
            
            # Mundur (R2)
            if r2_is_axis:
                # Jika R2 adalah axis, nilainya dari -1.0 (lepas) hingga 1.0 (ditekan penuh)
                r2_val = joystick.get_axis(AXIS_R2)
                r2_pressed = r2_val > 0.5 # Dianggap ditekan jika ditarik lebih dari setengah
            else:
                r2_pressed = joystick.get_button(BUTTON_R2)
            
            # --- HITUNG PWM ---
            # Nilai awal diset ke 800 sesuai permintaan.
            # Berdasarkan instruksi, asumsikan motor dikontrol satu arah secara terpisah pada pin 7 & 8:
            pwm_thruster = 800
            pwm_reverse = 800
            
            # Logika Analog Kiri (Maju & Mundur)
            # Deadzone kecil (-0.1 hingga 0.1) agar tidak bergerak saat analog sedikit kendor
            if left_stick_y < -0.1: 
                # Ditarik ke ATAS -> Maju
                speed_ratio = abs(left_stick_y)
                pwm_thruster = int(800 + (speed_ratio * 1100))
                # pwm_reverse tetap 800 (Mati)
            elif left_stick_y > 0.1:
                # Ditarik ke BAWAH -> Mundur
                speed_ratio = abs(left_stick_y)
                # Pin 7 (Motor Utama) dinaikkan juga agar motor punya tenaga
                pwm_thruster = int(800 + (speed_ratio * 1100))
                # Pin 8 (Switch Reverse) diaktifkan maksimal
                pwm_reverse = 1900
                
            # --- KIRIM PERINTAH KE PIXHAWK ---
            set_servo_pwm(master, PIN_THRUSTER, pwm_thruster)
            set_servo_pwm(master, PIN_REVERSE, pwm_reverse)
            
            # Tampilkan nilai untuk debugging di terminal
            print(f"Analog Y: {left_stick_y:+0.2f} | R2 Ditekan: {r2_pressed} | PWM Pin 7: {pwm_thruster} | PWM Pin 8: {pwm_reverse}   ", end='\r')
            
            # Delay loop 20Hz (0.05 detik) agar tidak membanjiri koneksi MAVLink
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        print("\n\nProgram dihentikan oleh user.")
    finally:
        # --- SAFETY: MATIKAN MOTOR ---
        print("Mematikan motor...")
        try:
            set_servo_pwm(master, PIN_THRUSTER, 800)
            set_servo_pwm(master, PIN_REVERSE, 800)
            print("Melepas arming (Disarming)...")
            master.arducopter_disarm()
            master.motors_disarmed_wait()
            print("Kendaraan berhasil DISARMED.")
        except:
            pass
        pygame.quit()

if __name__ == '__main__':
    main()
