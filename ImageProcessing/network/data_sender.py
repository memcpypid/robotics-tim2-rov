import socket
import json
import time
from typing import Dict, Any, Optional


class QRDataSender:
    """
    Mengirimkan hasil pembacaan QR Code (atau telemetri pemrosesan gambar)
    ke Base Station GUI melalui protokol UDP JSON Port 9000.
    """
    def __init__(self, base_station_ip: str = "127.0.0.1", port: int = 9000):
        self.base_station_ip = base_station_ip
        self.port = port
        self.sock: Optional[socket.socket] = None
        self._last_sent_code = ""
        self._last_sent_time = 0.0
        self._init_socket()

    def _init_socket(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            print(f"[QRDataSender] Siap mengirim data ke Base Station @ {self.base_station_ip}:{self.port}")
        except Exception as e:
            print(f"[QRDataSender ERROR] Gagal membuat socket UDP: {e}")

    def update_target(self, ip: str, port: int = 9000):
        self.base_station_ip = ip
        self.port = port
        print(f"[QRDataSender] Target diubah ke {self.base_station_ip}:{self.port}")

    def send_qr_result(self, qr_code_str: str, timestamp: float, cam_source: str = "", image_crop: Optional[Any] = None, force_send: bool = False) -> bool:
        """
        Mengirimkan hasil pembacaan QR beserta gambar crop hasil capture ke Base Station.
        Secara default mencegah pengiriman duplikat berlebihan (throttle 1 detik untuk teks yang sama).
        """
        if not qr_code_str or not self.sock:
            return False

        now = time.time()
        # Jika teks sama dan baru dikirim kurang dari 1 detik lalu, lewati kecuali force_send=True
        if not force_send and qr_code_str == self._last_sent_code and (now - self._last_sent_time < 1.0):
            return False

        payload = {
            "type": "TELEMETRY",
            "data": {
                "qr_last_code": qr_code_str,
                "qr_last_time": timestamp,
                "qr_last_cam": cam_source
            }
        }

        if image_crop is not None:
            try:
                import cv2
                import base64
                import numpy as np
                if isinstance(image_crop, np.ndarray) and image_crop.size > 0:
                    # Compress ke JPG quality 80 dan ubah ke Base64 string
                    ret, buffer = cv2.imencode('.jpg', image_crop, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if ret:
                        payload["data"]["qr_last_image"] = base64.b64encode(buffer).decode('ascii')
            except Exception as e:
                print(f"[QRDataSender WARNING] Gagal encode gambar QR: {e}")

        try:
            data_bytes = json.dumps(payload).encode("utf-8")
            self.sock.sendto(data_bytes, (self.base_station_ip, self.port))
            self._last_sent_code = qr_code_str
            self._last_sent_time = now
            print(f"[QRDataSender] Terkirim ke BaseStation -> QR: '{qr_code_str}' [{cam_source}] (@ {time.strftime('%H:%M:%S')})")
            return True
        except Exception as e:
            print(f"[QRDataSender ERROR] Gagal mengirim paket UDP: {e}")
            return False

    def send_custom_telemetry(self, data_dict: Dict[str, Any]) -> bool:
        """Mengirimkan dictionary sembarang ke Base Station port 9000."""
        if not self.sock:
            return False
        payload = {
            "type": "TELEMETRY",
            "data": data_dict
        }
        try:
            data_bytes = json.dumps(payload).encode("utf-8")
            self.sock.sendto(data_bytes, (self.base_station_ip, self.port))
            return True
        except Exception as e:
            print(f"[QRDataSender ERROR] Gagal mengirim telemetry kustom: {e}")
            return False

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
