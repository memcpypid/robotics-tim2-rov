import time
import threading

try:
    import smbus2 as smbus
    SMBUS_AVAILABLE = True
except ImportError:
    try:
        import smbus
        SMBUS_AVAILABLE = True
    except ImportError:
        SMBUS_AVAILABLE = False

from models.state import StateManager


class MS5803Sensor(threading.Thread):
    """
    Reader untuk sensor pressure & temperature GY-MS5803-01BA via I2C.
    Berjalan di thread terpisah agar tidak memblokir main thread.
    """
    def __init__(self, bus_number=1, i2c_address=0x76, fluid_density=997.0):
        super().__init__(name="MS5803_Thread", daemon=True)
        self.bus_number = bus_number
        self.address = i2c_address
        self.fluid_density = fluid_density # 997 untuk air tawar, 1029 untuk air laut
        self.state_mgr = StateManager.get_instance()
        self.running = False
        
        # Calibration Coefficients
        self.C = []
        
        self.bus = None
        if SMBUS_AVAILABLE:
            try:
                self.bus = smbus.SMBus(self.bus_number)
                self._reset_sensor()
                self._read_prom()
                print(f"[MS5803] Inisialisasi berhasil di bus {self.bus_number}, address {hex(self.address)}")
            except Exception as e:
                print(f"[MS5803] Gagal inisialisasi I2C: {e}")
                self.bus = None
        else:
            print("[MS5803] Library smbus/smbus2 tidak tersedia. Mode simulasi MS5803 aktif.")

    def _reset_sensor(self):
        """Reset sensor sebelum baca kalibrasi."""
        if not self.bus: return
        self.bus.write_byte(self.address, 0x1E)
        time.sleep(0.01)

    def _read_prom(self):
        """Membaca 8 koefisien dari PROM MS5803."""
        if not self.bus: return
        self.C = []
        for i in range(8):
            # Command untuk baca PROM: 0xA0 to 0xAE
            data = self.bus.read_i2c_block_data(self.address, 0xA0 + (i * 2), 2)
            c_val = (data[0] << 8) | data[1]
            self.C.append(c_val)
        # C[0] = reserved
        # C[1] = Pressure sensitivity
        # C[2] = Pressure offset
        # C[3] = Temp coeff of pressure sensitivity
        # C[4] = Temp coeff of pressure offset
        # C[5] = Reference temperature
        # C[6] = Temp coeff of the temperature
        # C[7] = Serial code / CRC

    def run(self):
        self.running = True
        
        # Base atmospheric pressure for depth calc
        # Usually we capture this on startup in air
        self.base_pressure = 1013.25 
        
        while self.running:
            try:
                if self.bus and len(self.C) >= 7:
                    # 1. Read D1 (Pressure)
                    self.bus.write_byte(self.address, 0x48) # OSR = 4096
                    time.sleep(0.01)
                    d1_data = self.bus.read_i2c_block_data(self.address, 0x00, 3)
                    D1 = (d1_data[0] << 16) | (d1_data[1] << 8) | d1_data[2]
                    
                    # 2. Read D2 (Temperature)
                    self.bus.write_byte(self.address, 0x58) # OSR = 4096
                    time.sleep(0.01)
                    d2_data = self.bus.read_i2c_block_data(self.address, 0x00, 3)
                    D2 = (d2_data[0] << 16) | (d2_data[1] << 8) | d2_data[2]
                    
                    # 3. Calculate Temp
                    dT = D2 - (self.C[5] * 256)
                    TEMP = 2000 + ((dT * self.C[6]) / 8388608)
                    
                    # 4. Calculate Pressure
                    OFF = (self.C[2] * 65536) + ((self.C[4] * dT) / 128)
                    SENS = (self.C[1] * 32768) + ((self.C[3] * dT) / 256)
                    
                    # Second order temperature compensation
                    T2 = 0
                    OFF2 = 0
                    SENS2 = 0
                    
                    if TEMP < 2000:
                        T2 = 3 * (dT ** 2) / 8589934592
                        OFF2 = 3 * ((TEMP - 2000) ** 2) / 2
                        SENS2 = 5 * ((TEMP - 2000) ** 2) / 8
                        if TEMP < -1500:
                            OFF2 = OFF2 + 7 * ((TEMP + 1500) ** 2)
                            SENS2 = SENS2 + 4 * ((TEMP + 1500) ** 2)
                            
                    TEMP = TEMP - T2
                    OFF = OFF - OFF2
                    SENS = SENS - SENS2
                    
                    P = ((D1 * SENS / 2097152) - OFF) / 32768
                    
                    temp_c = TEMP / 100.0
                    pressure_mbar = P / 10.0
                    
                    # Initialize base pressure at first valid reading if not set
                    if getattr(self, '_init_pressure', False) == False:
                        self.base_pressure = pressure_mbar
                        self._init_pressure = True
                        print(f"[MS5803] Base atmospheric pressure set to {self.base_pressure:.2f} mbar")
                    
                    # Calculate Depth
                    # 1 mbar = 100 Pa
                    pressure_diff_pa = (pressure_mbar - self.base_pressure) * 100.0
                    gravity = 9.80665
                    depth_m = pressure_diff_pa / (self.fluid_density * gravity)
                    
                    self.state_mgr.update(
                        ms5803_pressure=pressure_mbar,
                        ms5803_temp=temp_c,
                        ms5803_depth=max(0.0, depth_m)
                    )
                else:
                    # Simulation mode if no I2C
                    time.sleep(1)
            except Exception as e:
                print(f"[MS5803] Error reading sensor: {e}")
                time.sleep(1)
            
            time.sleep(0.05) # 20Hz update rate
            
    def calibrate(self):
        """Force the sensor to reset its base pressure (calibrate to current depth)."""
        self._init_pressure = False
        print("[MS5803] Kalibrasi dipicu. Base pressure akan di-reset pada pembacaan berikutnya.")

    def stop(self):
        self.running = False
        if self.bus:
            try:
                self.bus.close()
            except:
                pass
