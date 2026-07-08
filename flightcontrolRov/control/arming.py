"""
Kontrol Arming / Disarming untuk ROV.
"""
from pymavlink import mavutil
from connection.mav_client import MAVClient

class ROVArmingControl:
    def __init__(self, client: MAVClient):
        self.client = client

    def arm(self, force: bool = False) -> bool:
        """
        Mengirimkan perintah ARM (menyala/aktifkan motor thruster).
        :param force: Jika True, memaksa arming meskipun ada pre-arm safety check (gunakan hati-hati).
        """
        print("[ROVArmingControl] Mengirim perintah ARM...")
        param2 = 21196.0 if force else 0.0  # Magic number 21196 untuk force arming pada ArduPilot
        return self.client.send_command_long(
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            param1=1.0,  # 1 = ARM
            param2=param2
        )

    def disarm(self) -> bool:
        """
        Mengirimkan perintah DISARM (mematikan motor thruster secara langsung).
        """
        print("[ROVArmingControl] Mengirim perintah DISARM...")
        return self.client.send_command_long(
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            param1=0.0  # 0 = DISARM
        )
