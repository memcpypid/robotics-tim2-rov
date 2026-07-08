"""
Kontrol Perubahan Mode Operasi untuk ROV (ArduSub).
Mode umum ArduSub: MANUAL, STABILIZE, DEPTH_HOLD, POSITION_HOLD, AUTO, ACRO.
"""
from pymavlink import mavutil
from connection.mav_client import MAVClient

class ROVModeControl:
    def __init__(self, client: MAVClient):
        self.client = client

    def set_mode(self, mode_name: str) -> bool:
        """
        Mengubah mode operasi ROV.
        :param mode_name: Nama mode (contoh: 'MANUAL', 'STABILIZE', 'ALT_HOLD' atau 'DEPTH_HOLD', 'POSHOLD')
        """
        if not self.client.is_connected():
            print("[ROVModeControl Error] ROV belum terhubung!")
            return False

        # Pemetaan khusus jika user mengetik DEPTH_HOLD (pada MAVLink ArduSub sering dipetakan sebagai ALT_HOLD)
        if mode_name.upper() == "DEPTH_HOLD":
            mode_name = "ALT_HOLD"

        mode_name = mode_name.upper()

        mode_mapping = self.client.master.mode_mapping()
        if not mode_mapping or mode_name not in mode_mapping:
            print(f"[ROVModeControl Error] Mode '{mode_name}' tidak ditemukan di pemetaan mode Flight Controller.")
            if mode_mapping:
                print(f"Mode yang tersedia: {list(mode_mapping.keys())}")
            return False

        mode_id = mode_mapping[mode_name]
        print(f"[ROVModeControl] Mengubah mode ke: {mode_name} (ID: {mode_id})...")
        
        # MAV_CMD_DO_SET_MODE (176)
        return self.client.send_command_long(
            mavutil.mavlink.MAV_CMD_DO_SET_MODE,
            param1=1.0,      # 1 = MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
            param2=float(mode_id)
        )
