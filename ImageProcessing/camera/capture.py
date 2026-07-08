import cv2
import threading
import time
from typing import Optional, Tuple, Union
import numpy as np


class CameraThread:
    """
    Thread independen untuk membaca frame video dari 1 kamera secara kontinyu (non-blocking).
    Mendukung input device index (0, 1, 2) atau device path/URL ('/dev/video0', 'rtsp://...').
    """
    def __init__(self, source: Union[int, str], cam_name: str = "CAM", width: int = 640, height: int = 480, fps: int = 30):
        self.source = source
        self.cam_name = cam_name
        self.target_width = width
        self.target_height = height
        self.target_fps = fps

        self.cap: Optional[cv2.VideoCapture] = None
        self._frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._running = False
        self.active_source: Optional[Union[int, str]] = None
        self.is_connected = False

    def start(self, exclude_sources: Optional[set] = None) -> bool:
        if self._running:
            return True

        if exclude_sources is None:
            exclude_sources = set()

        print(f"[{self.cam_name}] Membuka sumber video: {self.source} ...")
        
        # Coba konversi ke integer jika source berupa digit string ('0' -> 0)
        source_val = int(self.source) if isinstance(self.source, str) and self.source.isdigit() else self.source
        
        def _try_open(src):
            if src in exclude_sources:
                return None
            cap = cv2.VideoCapture(src, cv2.CAP_V4L2 if isinstance(src, int) else cv2.CAP_ANY)
            if not cap.isOpened():
                cap = cv2.VideoCapture(src)
            if cap.isOpened():
                # Penting di Linux/USB Webcam: Set FOURCC ke MJPG untuk mencegah error ENOSPC (USB Bandwidth penuh saat 2 kamera nyala)
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.target_width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.target_height)
                cap.set(cv2.CAP_PROP_FPS, self.target_fps)
                # Tes baca 1 frame untuk memastikan node video valid (bukan node metadata / subdevice)
                ret, frame = cap.read()
                if ret and frame is not None:
                    return cap
                cap.release()
            return None

        self.cap = _try_open(source_val)

        # Jika indeks utama gagal (misal index 1 ternyata metadata node dari /dev/video0), lakukan smart probing di indeks lain
        if self.cap is None and isinstance(source_val, int):
            print(f"[{self.cam_name} WARNING] Device {source_val} gagal / bukan stream video aktif. Melakukan scanning otomatis kamera lain...")
            # Coba indeks genap (biasanya stream video di Linux: 2, 4, 6) lalu indeks ganjil
            probe_list = [i for i in [2, 4, 6, 8, 0, 1, 3] if i != source_val and i not in exclude_sources]
            for candidate in probe_list:
                print(f"[{self.cam_name}] Probing fallback device {candidate}...")
                cap_test = _try_open(candidate)
                if cap_test is not None:
                    self.cap = cap_test
                    self.active_source = candidate
                    print(f"[{self.cam_name} SUCCESS] Berhasil menemukan dan membuka kamera di device {candidate}!")
                    break
        else:
            if self.cap is not None:
                self.active_source = source_val

        if self.cap is None or not self.cap.isOpened():
            print(f"[{self.cam_name} ERROR] Gagal membuka kamera {self.source} maupun fallback devices!")
            self.is_connected = False
            return False

        self.is_connected = True
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, name=f"Thread-{self.cam_name}", daemon=True)
        self._thread.start()
        print(f"[{self.cam_name}] Berhasil terhubung! Capture loop berjalan @ {self.target_fps} FPS (Source: {self.active_source}).")
        return True

    def _capture_loop(self):
        delay = 1.0 / max(1, self.target_fps)
        while self._running and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret and frame is not None:
                # Resize jika resolusi kamera asli berbeda dr target width/height (opsional)
                if frame.shape[1] != self.target_width or frame.shape[0] != self.target_height:
                    frame = cv2.resize(frame, (self.target_width, self.target_height))
                with self._lock:
                    self._frame = frame
            else:
                time.sleep(0.05)
            time.sleep(delay * 0.5)

    def get_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            if self._frame is not None:
                return self._frame.copy()
            return None

    def stop(self):
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
        print(f"[{self.cam_name}] Kamera ditutup.")


class DualCameraCapture:
    """
    Manajer untuk menangani 2 kamera ROV sekaligus:
    - CAM 1 (Laptop / Front Camera): contoh device 0
    - CAM 2 (Action Cam via Kabel USB / Bottom Camera): contoh device 1
    """
    def __init__(self, cam1_source: Union[int, str] = 0, cam2_source: Union[int, str] = 1, width: int = 640, height: int = 480):
        self.cam1 = CameraThread(cam1_source, cam_name="CAM1-FRONT", width=width, height=height)
        self.cam2 = CameraThread(cam2_source, cam_name="CAM2-BOTTOM", width=width, height=height)

    def start_all(self):
        print("\n[DualCameraCapture] Memulai inisialisasi 2 kamera ROV...")
        success1 = self.cam1.start()
        exclude_set = {self.cam1.active_source} if success1 and self.cam1.active_source is not None else set()
        success2 = self.cam2.start(exclude_sources=exclude_set)
        if not success1 and not success2:
            print("[DualCameraCapture WARNING] Kedua kamera gagal dibuka. Periksa kabel USB dan permission kamera.")
        elif not success1:
            print("[DualCameraCapture WARNING] CAM 1 (Front/Laptop) gagal. Hanya CAM 2 yang aktif.")
        elif not success2:
            print("[DualCameraCapture WARNING] CAM 2 (Bottom/Action Cam) gagal. Hanya CAM 1 yang aktif.")
        else:
            print("[DualCameraCapture SUCCESS] Kedua kamera (CAM 1 & CAM 2) aktif dan siap!")

    def get_frames(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Mengembalikan tuple (frame_cam1, frame_cam2)."""
        return self.cam1.get_frame(), self.cam2.get_frame()

    def stop_all(self):
        self.cam1.stop()
        self.cam2.stop()
