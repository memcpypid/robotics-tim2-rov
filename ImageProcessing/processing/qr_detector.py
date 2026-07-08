import cv2
import time
from typing import Tuple, Optional
import numpy as np

try:
    from pyzbar import pyzbar
    PYZBAR_AVAILABLE = True
except ImportError:
    PYZBAR_AVAILABLE = False


class QRCodeProcessor:
    """
    Modul Image Processing untuk mendeteksi dan mendekode QR Code secara real-time.
    Menggunakan kombinasi cv2.QRCodeDetector dan PyZbar (jika tersedia) untuk akurasi maksimal.
    """
    def __init__(self):
        self.detector = cv2.QRCodeDetector()
        self.last_code = ""
        self.last_detection_time = 0.0
        self.total_detections = 0

    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, str, float]:
        """
        Mendeteksi QR Code pada frame input.
        Mengembalikan tuple: (frame_dengan_bounding_box, qr_text, timestamp)
        """
        if frame is None:
            return frame, "", 0.0

        output_frame = frame.copy()
        detected_text = ""
        points = None

        # 1. Coba deteksi memakai OpenCV QRCodeDetector
        try:
            data, bbox, _ = self.detector.detectAndDecode(frame)
            if bbox is not None and len(bbox) > 0 and data:
                detected_text = data.strip()
                points = bbox[0].astype(int)
        except Exception:
            pass

        # 2. Jika OpenCV tidak menemukan teks, coba gunakan PyZbar (sangat tangguh untuk QR miring/buram)
        if not detected_text and PYZBAR_AVAILABLE:
            try:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                barcodes = pyzbar.decode(gray)
                for barcode in barcodes:
                    decoded = barcode.data.decode("utf-8").strip()
                    if decoded:
                        detected_text = decoded
                        polygon = barcode.polygon
                        if len(polygon) == 4:
                            points = np.array([[pt.x, pt.y] for pt in polygon], dtype=int)
                        else:
                            rect = barcode.rect
                            points = np.array([
                                [rect.left, rect.top],
                                [rect.left + rect.width, rect.top],
                                [rect.left + rect.width, rect.top + rect.height],
                                [rect.left, rect.top + rect.height]
                            ], dtype=int)
                        break
            except Exception:
                pass

        # 3. Jika QR Code terdeteksi, gambar overlay di frame video
        qr_crop = None
        if detected_text:
            now = time.time()
            self.last_code = detected_text
            self.last_detection_time = now
            self.total_detections += 1

            if points is not None and len(points) == 4:
                # Crop area gambar QR Code (dari frame asli sebelum diberi garis overlay)
                min_x = max(0, int(np.min(points[:, 0])) - 35)
                max_x = min(frame.shape[1], int(np.max(points[:, 0])) + 35)
                min_y = max(0, int(np.min(points[:, 1])) - 35)
                max_y = min(frame.shape[0], int(np.max(points[:, 1])) + 35)
                if max_x > min_x and max_y > min_y:
                    qr_crop = frame[min_y:max_y, min_x:max_x].copy()

                # Gambar garis bounding box warna hijau terang (#40bf6a / RGB 106, 191, 64 -> BGR 64, 191, 106)
                for i in range(4):
                    pt1 = tuple(points[i])
                    pt2 = tuple(points[(i + 1) % 4])
                    cv2.line(output_frame, pt1, pt2, (64, 255, 64), 3)

                # Gambar kotak latar belakang label di atas QR
                x_coords = points[:, 0]
                y_coords = points[:, 1]
                top_left = (int(min(x_coords)), max(10, int(min(y_coords)) - 35))
                bottom_right = (int(max(x_coords)), int(min(y_coords)))
                
                cv2.rectangle(output_frame, top_left, bottom_right, (0, 150, 0), cv2.FILLED)
                cv2.putText(
                    output_frame,
                    f"QR: {detected_text[:25]}",
                    (top_left[0] + 5, top_left[1] + 24),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    2
                )
            else:
                qr_crop = frame.copy()
                # Jika koordinat polygon tidak lengkap, tampilkan banner di pojok kiri atas
                cv2.rectangle(output_frame, (10, 10), (380, 50), (0, 150, 0), cv2.FILLED)
                cv2.putText(
                    output_frame,
                    f"[QR DETECTED] {detected_text[:25]}",
                    (20, 38),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    2
                )

            if qr_crop is None:
                qr_crop = frame.copy()

        return output_frame, detected_text, self.last_detection_time, qr_crop
