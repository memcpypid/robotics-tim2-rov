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
                
                # Ambil frame counter (untuk bergantian variasi sudut tiap frame agar FPS tidak turun drastis)
                self.frame_counter = getattr(self, 'frame_counter', 0) + 1
                
                # Selalu cek frame normal grayscale dan CLAHE (meratakan pencahayaan jika silau/gelap)
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
                variations = [
                    (gray, 0),
                    (clahe.apply(gray), 0)
                ]
                
                # Secara bergantian (round-robin) cek sudut miring (Tilted) dan perspektif curam
                cycle = self.frame_counter % 8
                image_center = tuple(np.array(gray.shape[1::-1]) / 2)
                H, W = gray.shape
                
                if cycle == 1:
                    _, thresh = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY)
                    variations.append((thresh, None))
                elif cycle == 2:
                    m = cv2.getRotationMatrix2D(image_center, 25, 1.0)
                    inv_m = cv2.getRotationMatrix2D(image_center, -25, 1.0)
                    variations.append((cv2.warpAffine(gray, m, (W, H)), inv_m))
                elif cycle == 3:
                    m = cv2.getRotationMatrix2D(image_center, -25, 1.0)
                    inv_m = cv2.getRotationMatrix2D(image_center, 25, 1.0)
                    variations.append((cv2.warpAffine(gray, m, (W, H)), inv_m))
                elif cycle == 4:
                    # Perspektif 1: Kemiringan sedang ke lantai (Bird's eye view ringan)
                    src1 = np.float32([[W*0.15, H*0.1], [W*0.85, H*0.1], [W, H], [0, H]])
                    dst1 = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
                    m = cv2.getPerspectiveTransform(src1, dst1)
                    inv_m = cv2.getPerspectiveTransform(dst1, src1)
                    variations.append((cv2.warpPerspective(gray, m, (W, H)), inv_m))
                elif cycle == 5:
                    # Perspektif 2: Sangat curam (Cocok untuk QR di lantai persis di depan ROV)
                    src2 = np.float32([[W*0.3, H*0.2], [W*0.7, H*0.2], [W, H], [0, H]])
                    dst2 = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
                    m = cv2.getPerspectiveTransform(src2, dst2)
                    inv_m = cv2.getPerspectiveTransform(dst2, src2)
                    variations.append((cv2.warpPerspective(gray, m, (W, H)), inv_m))
                elif cycle == 6:
                    # Perspektif 3: Lebih lebar di tengah (Lensa wide/fisheye distorsi kemiringan)
                    src3 = np.float32([[W*0.2, H*0.3], [W*0.8, H*0.3], [W, H], [0, H]])
                    dst3 = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
                    m = cv2.getPerspectiveTransform(src3, dst3)
                    inv_m = cv2.getPerspectiveTransform(dst3, src3)
                    variations.append((cv2.warpPerspective(gray, m, (W, H)), inv_m))
                elif cycle == 7 or cycle == 0:
                    m = cv2.getRotationMatrix2D(image_center, 45, 1.0)
                    inv_m = cv2.getRotationMatrix2D(image_center, -45, 1.0)
                    variations.append((cv2.warpAffine(gray, m, (W, H)), inv_m))

                for var_frame, inv_m in variations:
                    barcodes = pyzbar.decode(var_frame)
                    if barcodes:
                        for barcode in barcodes:
                            decoded = barcode.data.decode("utf-8").strip()
                            if decoded:
                                detected_text = decoded
                                polygon = barcode.polygon
                                if len(polygon) == 4:
                                    pts = np.array([[pt.x, pt.y] for pt in polygon], dtype=float)
                                else:
                                    rect = barcode.rect
                                    pts = np.array([
                                        [rect.left, rect.top],
                                        [rect.left + rect.width, rect.top],
                                        [rect.left + rect.width, rect.top + rect.height],
                                        [rect.left, rect.top + rect.height]
                                    ], dtype=float)
                                
                                # Kembalikan koordinat bounding box ke posisi frame asli
                                if inv_m is not None:
                                    pts = np.array([pts])
                                    if inv_m.shape == (3, 3):
                                        # Transformasi balik dari perspektif (3x3)
                                        transformed_pts = cv2.perspectiveTransform(pts, inv_m)[0]
                                    else:
                                        # Transformasi balik dari affine/rotasi (2x3)
                                        transformed_pts = cv2.transform(pts, inv_m)[0]
                                    points = transformed_pts.astype(int)
                                else:
                                    points = pts.astype(int)
                                break
                        if detected_text:
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
