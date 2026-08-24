"""
Modul Manajemen Kamera Ganda (Dual Camera Capture) untuk Linux & Jetson Nano.
Menggunakan OpenCV + backend V4L2 secara eksklusif untuk mendukungan 2 stream USB Webcam
secara simultan dengan konfigurasi independen (resolusi, frame rate, dan FOURCC codec).
"""

import cv2
import threading
import time
from dataclasses import dataclass
from typing import Optional, Tuple, Union
import numpy as np

@dataclass
class CameraConfig:
    """Konfigurasi independen untuk setiap kamera USB V4L2."""
    device: Union[int, str] = "/dev/video0"
    width: int = 640
    height: int = 480
    fps: int = 30
    fourcc: Optional[str] = None
    cam_name: str = "CAM"


def _decode_fourcc(fourcc_int: float) -> str:
    """Menerjemahkan integer 32-bit FOURCC dari OpenCV menjadi string 4 karakter (cth: 'YUYV' atau 'MJPG')."""
    try:
        val = int(fourcc_int)
        chars = [chr((val >> (8 * i)) & 0xFF) for i in range(4)]
        cleaned = "".join(c if c.isprintable() else "?" for c in chars)
        return cleaned.strip() if cleaned.strip() else "UNKNOWN"
    except Exception:
        return "UNKNOWN"


class CameraThread:
    """
    Thread independen untuk menangkap frame video dari kamera USB menggunakan backend V4L2.
    Menjamin proteksi timeout, pemanasan kamera (warmup/discard startup frames),
    verifikasi properti kamera yang diatur, dan pengambilan frame non-blocking yang thread-safe.
    """
    def __init__(
        self,
        config: Union[CameraConfig, int, str],
        cam_name: str = "CAM",
        width: int = 640,
        height: int = 480,
        fps: int = 30,
        fourcc: Optional[str] = None
    ):
        if isinstance(config, CameraConfig):
            self.config = config
        else:
            self.config = CameraConfig(
                device=config,
                width=width,
                height=height,
                fps=fps,
                fourcc=fourcc,
                cam_name=cam_name
            )

        self.cap: Optional[cv2.VideoCapture] = None
        self._frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.is_connected = False
        self.active_source: Optional[Union[int, str]] = None

    @property
    def source(self) -> Union[int, str]:
        return self.config.device

    @property
    def cam_name(self) -> str:
        return self.config.cam_name

    def start(self, *args, **kwargs) -> bool:
        """
        Membuka kamera menggunakan backend V4L2, mengatur properti, memvalidasi konfigurasi,
        dan memulai background thread capture loop.
        """
        if self._running:
            return True

        print(f"[{self.cam_name}] Opening camera device: {self.config.device} ...")
        import sys
        # 1. Buka kamera dengan backend sesuai OS
        
        # Konversi ke integer jika device berupa digit string ('0' -> 0)
        source_val = int(self.config.device) if isinstance(self.config.device, str) and self.config.device.isdigit() else self.config.device

        try:
            if sys.platform.startswith('linux'):
                backend = cv2.CAP_V4L2
                backend_str = "V4L2"
            elif sys.platform.startswith('win'):
                backend = cv2.CAP_DSHOW
                backend_str = "DSHOW"
            else:
                backend = cv2.CAP_ANY
                backend_str = "ANY"
            
            print(f"[{self.cam_name}] Backend: {backend_str}")
            self.cap = cv2.VideoCapture(source_val, backend)
        except Exception as e:
            print(f"[{self.cam_name} ERROR] Exception saat membuka device {self.config.device}: {e}")
            self.is_connected = False
            return False

        if not self.cap or not self.cap.isOpened():
            print(f"[{self.cam_name} ERROR] Failure reason: Failed to open device {self.config.device} with V4L2 backend.")
            self.is_connected = False
            return False

        print(f"[{self.cam_name}] Camera opened successfully.")

        # 2. Atur konfigurasi spesifik untuk kamera ini
        req_format_str = self.config.fourcc if self.config.fourcc else "Default (YUYV/Auto)"
        print(f"[{self.cam_name}] Requested format: {req_format_str} @ {self.config.width}x{self.config.height} ({self.config.fps} FPS)")

        if self.config.fourcc and len(self.config.fourcc) == 4:
            fourcc_code = cv2.VideoWriter_fourcc(*self.config.fourcc.upper())
            self.cap.set(cv2.CAP_PROP_FOURCC, fourcc_code)

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.config.fps)

        # 3. Verifikasi setiap properti setelah cap.set()
        act_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        act_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        act_fps = self.cap.get(cv2.CAP_PROP_FPS)
        act_fourcc_int = self.cap.get(cv2.CAP_PROP_FOURCC)
        act_fourcc_str = _decode_fourcc(act_fourcc_int)

        print(f"[{self.cam_name}] Actual format: {act_fourcc_str} @ {act_width}x{act_height} ({act_fps:.1f} FPS)")

        # 4. Pemanasan kamera & discard startup frames
        print(f"[{self.cam_name}] Warming up camera (waiting 1s and discarding startup frames)...")
        time.sleep(1.0)

        valid_frame_received = False
        start_probe_time = time.time()

        # Discard beberapa frame awal dengan proteksi timeout 3 detik
        for _ in range(10):
            if time.time() - start_probe_time > 3.0:
                break
            ret, frame = self.cap.read()
            if ret and frame is not None and frame.size > 0:
                valid_frame_received = True
                with self._lock:
                    if frame.shape[1] != self.config.width or frame.shape[0] != self.config.height:
                        self._frame = cv2.resize(frame, (self.config.width, self.config.height))
                    else:
                        self._frame = frame
                break
            time.sleep(0.05)

        if not valid_frame_received:
            print(f"[{self.cam_name} ERROR] Failure reason: No valid frame received within 3 seconds during startup check (Timeout).")
            self.cap.release()
            self.cap = None
            self.is_connected = False
            return False

        print(f"[{self.cam_name}] Frame received! Capture loop started.")
        self.is_connected = True
        self.active_source = source_val
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, name=f"Thread-{self.cam_name}", daemon=True)
        self._thread.start()
        return True

    def _capture_loop(self):
        """Loop penangkapan frame secara kontinyu tanpa sleep berlebih, dengan proteksi timeout 3 detik."""
        last_valid_time = time.time()
        while self._running and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret and frame is not None and frame.size > 0:
                last_valid_time = time.time()
                frame = cv2.flip(frame, 1) # Flip horizontal untuk menghilangkan efek mirror
                if frame.shape[1] != self.config.width or frame.shape[0] != self.config.height:
                    frame = cv2.resize(frame, (self.config.width, self.config.height))
                with self._lock:
                    self._frame = frame
            else:
                # Proteksi timeout: Jika tidak ada frame valid masuk selama > 3 detik
                if time.time() - last_valid_time > 3.0:
                    print(f"[{self.cam_name} ERROR] Failure reason: Capture loop timed out (>3s without valid frame).")
                    break
                time.sleep(0.01)

        self._running = False
        self.is_connected = False
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        print(f"[{self.cam_name}] Capture loop terminated.")

    def get_frame(self) -> Optional[np.ndarray]:
        """Mengambil salinan thread-safe dari frame terakhir yang berhasil ditangkap."""
        with self._lock:
            if self._frame is not None:
                return self._frame.copy()
            return None

    def stop(self):
        """Menghentikan thread dan menutup device V4L2 secara bersih."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        self.is_connected = False
        self.active_source = None
        print(f"[{self.cam_name}] Camera closed cleanly.")


class DualCameraCapture:
    """
    Manajer untuk mengoperasikan 2 kamera USB V4L2 secara independen dan bersamaan di Linux/Jetson Nano.
    - Kamera 1 (misal: Logitech C170, /dev/video0, YUYV/Default @ 640x480)
    - Kamera 2 (misal: Android UVC Camera, /dev/video1, MJPG @ 1280x720)
    """
    def __init__(
        self,
        cam1_config: Optional[Union[CameraConfig, int, str]] = None,
        cam2_config: Optional[Union[CameraConfig, int, str]] = None,
        cam1_source: Optional[Union[int, str]] = None,
        cam2_source: Optional[Union[int, str]] = None,
        width: int = 640,
        height: int = 480
    ):
        # Resolve Konfigurasi untuk CAM 1
        if isinstance(cam1_config, CameraConfig):
            cfg1 = cam1_config
        else:
            src1 = cam1_source if cam1_source is not None else (cam1_config if cam1_config is not None else "/dev/video0")
            cfg1 = CameraConfig(
                device=src1,
                width=width,
                height=height,
                fps=15,       # Turunkan ke 15 FPS untuk menghemat USB Bandwidth
                fourcc=None,  # Kembalikan ke format bawaan kamera (YUYV) agar tidak error
                cam_name="CAM1-FRONT"
            )

        # Resolve Konfigurasi untuk CAM 2
        if isinstance(cam2_config, CameraConfig):
            cfg2 = cam2_config
        else:
            src2 = cam2_source if cam2_source is not None else (cam2_config if cam2_config is not None else "/dev/video1")
            # Gunakan MJPG agar kedua kamera eksternal (Dual Webcam) dapat berjalan bersamaan di 1 USB Controller
            cfg2 = CameraConfig(
                device=src2,
                width=width,
                height=height,
                fps=15,       # Turunkan ke 15 FPS untuk menghemat USB Bandwidth
                fourcc=None,  # Kembalikan ke format bawaan kamera (YUYV) agar tidak error
                cam_name="CAM2-BOTTOM"
            )

        self.cam1 = CameraThread(cfg1)
        self.cam2 = CameraThread(cfg2)

    def start_all(self):
        """Memulai kedua kamera sesuai konfigurasi independen masing-masing tanpa fallback otomatis."""
        print("\n[DualCameraCapture] Initializing dual V4L2 cameras with independent settings...")
        success1 = self.cam1.start()
        success2 = self.cam2.start()

        if not success1 and not success2:
            print("[DualCameraCapture WARNING] Both cameras failed to open. Please verify USB connections and permissions.")
        elif not success1:
            print("[DualCameraCapture WARNING] CAM 1 failed to open. Only CAM 2 is active.")
        elif not success2:
            print("[DualCameraCapture WARNING] CAM 2 failed to open. Only CAM 1 is active.")
        else:
            print("[DualCameraCapture SUCCESS] Both V4L2 cameras (CAM 1 & CAM 2) are active and streaming!")

    def get_frames(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Mengembalikan tuple frame dari kedua kamera: (frame_cam1, frame_cam2)."""
        return self.cam1.get_frame(), self.cam2.get_frame()

    def stop_all(self):
        """Menghentikan seluruh layanan kamera dan membebaskan device node V4L2."""
        self.cam1.stop()
        self.cam2.stop()
