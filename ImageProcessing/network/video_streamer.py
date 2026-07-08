import socket
import struct
import cv2
import numpy as np
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Optional, Dict, Any


class UDPVideoStreamer:
    """
    Metode Lama (Dioptimalkan): Streamer video berbasis UDP dan kompresi JPEG.
    Diperbarui agar menggunakan chunk 1400 byte (di bawah batas MTU Ethernet 1500 byte)
    serta automatic fast downscaling agar ringan saat dikirim lewat LAN/WiFi.
    - Port default CAM 1: 9002
    - Port default CAM 2: 9003
    """
    MAX_CHUNK_SIZE = 1400

    def __init__(self, target_ip: str = "127.0.0.1", port: int = 9002, jpeg_quality: int = 60):
        self.target_ip = target_ip
        self.port = port
        self.jpeg_quality = jpeg_quality
        self.sock: Optional[socket.socket] = None
        self._packet_counter = 0
        self._init_socket()

    def _init_socket(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            print(f"[UDPVideoStreamer] Siap mengirim stream ke {self.target_ip}:{self.port}")
        except Exception as e:
            print(f"[UDPVideoStreamer ERROR] Gagal membuat socket UDP: {e}")

    def update_target(self, ip: str, port: int):
        self.target_ip = ip
        self.port = port
        print(f"[UDPVideoStreamer] Target stream diubah ke {self.target_ip}:{self.port}")

    def send_frame(self, frame: np.ndarray) -> bool:
        if frame is None or not self.sock:
            return False

        try:
            # Downscaling kilat jika frame terlalu besar (> 640px) agar latensi rendah di mode UDP
            h, w = frame.shape[:2]
            if w > 640:
                frame = cv2.resize(frame, (640, int(640 * h / w)), interpolation=cv2.INTER_NEAREST)

            # 1. Kompresi frame ke JPEG
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
            ret, jpeg_data = cv2.imencode('.jpg', frame, encode_param)
            if not ret:
                return False

            raw_bytes = jpeg_data.tobytes()
            total_size = len(raw_bytes)
            
            # Hitung jumlah chunk yang dibutuhkan
            total_chunks = (total_size + self.MAX_CHUNK_SIZE - 1) // self.MAX_CHUNK_SIZE
            if total_chunks > 255:
                return False  # Melebihi kapasitas 1 byte indeks chunk

            self._packet_counter = (self._packet_counter + 1) % 4294967295
            
            # Header format: !I B B (Packet ID 4 bytes uint, Total Chunks 1 byte uint, Chunk Index 1 byte uint) -> 6 bytes
            for i in range(total_chunks):
                start = i * self.MAX_CHUNK_SIZE
                end = min(total_size, (i + 1) * self.MAX_CHUNK_SIZE)
                chunk_data = raw_bytes[start:end]
                
                header = struct.pack("!IBB", self._packet_counter, total_chunks, i)
                self.sock.sendto(header + chunk_data, (self.target_ip, self.port))
                
            return True
        except Exception:
            return False

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None


class GStreamerH264Streamer:
    """
    Metode 1 (Ultra-Light & Zero-Copy Hardware Acceleration):
    Mengirim stream video H.264 melalui UDP RTP menggunakan pipeline GStreamer.
    Memanfaatkan GPU NVENC (nvv4l2h264enc) pada Jetson Nano atau x264enc di Linux PC.
    Sangat ringan (penggunaan CPU <5%, bandwidth hanya ~1.5 Mbps).
    """
    def __init__(self, target_ip: str = "127.0.0.1", port: int = 9002, bitrate: int = 1500000):
        self.target_ip = target_ip
        self.port = port
        self.bitrate = bitrate
        self.writer: Optional[cv2.VideoWriter] = None
        self._lock = threading.Lock()
        self._current_size: Optional[Tuple[int, int]] = None
        print(f"[GStreamerH264Streamer] Siap mengirim stream H.264 RTP ke {self.target_ip}:{self.port}")

    def update_target(self, ip: str, port: int):
        with self._lock:
            if ip != self.target_ip or port != self.port:
                self.target_ip = ip
                self.port = port
                print(f"[GStreamerH264Streamer] Target stream diubah ke {self.target_ip}:{self.port}. Merestart pipeline...")
                if self.writer:
                    try:
                        self.writer.release()
                    except Exception:
                        pass
                    self.writer = None
                self._current_size = None

    def _open_pipeline(self, w: int, h: int) -> bool:
        # 1. Coba pipeline Jetson Hardware Accelerated NVENC terlebih dahulu
        pipeline_jetson = (
            f"appsrc ! video/x-raw, format=BGR ! queue ! videoconvert ! video/x-raw, format=BGRx ! "
            f"nvvidconv ! video/x-raw(memory:NVMM), format=NV12 ! nvv4l2h264enc bitrate={self.bitrate} preset-level=1 insert-sps-pps=true idrinterval=15 ! "
            f"h264parse ! mpegtsmux alignment=7 ! udpsink host={self.target_ip} port={self.port} async=false sync=false"
        )
        writer = cv2.VideoWriter(pipeline_jetson, cv2.CAP_GSTREAMER, 30.0, (w, h), True)
        if writer.isOpened():
            print(f"[GStreamerH264Streamer SUCCESS] Pipeline NVENC GPU aktif -> {w}x{h} @ {self.target_ip}:{self.port}")
            self.writer = writer
            self._current_size = (w, h)
            return True

        # 2. Fallback ke x264enc software encoder jika dijalankan di Desktop Linux biasa
        print("[GStreamerH264Streamer WARNING] NVENC tidak tersedia. Mencoba fallback ke x264enc GStreamer...")
        pipeline_fallback = (
            f"appsrc ! video/x-raw, format=BGR ! queue ! videoconvert ! video/x-raw, format=I420 ! "
            f"x264enc tune=zerolatency bitrate={self.bitrate // 1000} speed-preset=ultrafast key-int-max=15 ! "
            f"h264parse ! mpegtsmux alignment=7 ! udpsink host={self.target_ip} port={self.port} async=false sync=false"
        )
        writer = cv2.VideoWriter(pipeline_fallback, cv2.CAP_GSTREAMER, 30.0, (w, h), True)
        if writer.isOpened():
            print(f"[GStreamerH264Streamer SUCCESS] Pipeline x264enc aktif -> {w}x{h} @ {self.target_ip}:{self.port}")
            self.writer = writer
            self._current_size = (w, h)
            return True

        print(f"[GStreamerH264Streamer ERROR] Gagal membuka pipeline GStreamer ke {self.target_ip}:{self.port}")
        return False

    def send_frame(self, frame: np.ndarray) -> bool:
        if frame is None or frame.size == 0:
            return False

        with self._lock:
            h, w = frame.shape[:2]
            if self.writer is None or self._current_size != (w, h):
                if self.writer:
                    try:
                        self.writer.release()
                    except Exception:
                        pass
                    self.writer = None
                success = self._open_pipeline(w, h)
                if not success:
                    return False

            try:
                self.writer.write(frame)
                return True
            except Exception:
                return False

    def close(self):
        with self._lock:
            if self.writer:
                try:
                    self.writer.release()
                except Exception:
                    pass
                self.writer = None


class UnifiedVideoStreamer:
    """
    Proxy Manager yang memungkinkan pengalihan instan (runtime switchable) antara:
    - Mode 'gstreamer' (Metode 1: H.264 Hardware Acceleration via NVENC / RTP UDP)
    - Mode 'udp'       (Metode Sekarang: Optimized JPEG UDP Chunking)
    """
    def __init__(self, target_ip: str = "127.0.0.1", port: int = 9002, mode: str = "gstreamer"):
        self.target_ip = target_ip
        self.port = port
        self.mode = mode.lower()
        self.streamer: Any = self._create_streamer(self.mode)

    def _create_streamer(self, mode: str):
        if mode == "gstreamer":
            print(f"[UnifiedVideoStreamer] Mengaktifkan Mode 1 (GStreamer H.264) di port {self.port}")
            return GStreamerH264Streamer(self.target_ip, self.port)
        else:
            print(f"[UnifiedVideoStreamer] Mengaktifkan Mode UDP (JPEG Optimized) di port {self.port}")
            return UDPVideoStreamer(self.target_ip, self.port, jpeg_quality=60)

    def set_mode(self, mode: str):
        mode_clean = mode.lower()
        if mode_clean != self.mode:
            print(f"[UnifiedVideoStreamer] Mengubah metode stream dari '{self.mode}' ke '{mode_clean}'...")
            if self.streamer:
                self.streamer.close()
            self.mode = mode_clean
            self.streamer = self._create_streamer(self.mode)

    def update_target(self, ip: str, port: int):
        self.target_ip = ip
        self.port = port
        if self.streamer:
            self.streamer.update_target(ip, port)

    def send_frame(self, frame: np.ndarray) -> bool:
        if self.streamer:
            return self.streamer.send_frame(frame)
        return False

    def close(self):
        if self.streamer:
            self.streamer.close()
            self.streamer = None


class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class MJPEGServer:
    """
    HTTP MJPEG Stream Server opsional agar frame kamera juga dapat diakses
    melalui browser / klien TCP (contoh: http://ip_jetson:8080/cam1).
    """
    def __init__(self, port: int = 8080):
        self.port = port
        self.server: Optional[_ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._frames: Dict[str, bytes] = {}
        self._lock = threading.Lock()
        self._running = False

    def update_frame(self, stream_name: str, frame: np.ndarray):
        if frame is None:
            return
        try:
            ret, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
            if ret:
                with self._lock:
                    self._frames[stream_name] = jpeg.tobytes()
        except Exception:
            pass

    def get_jpeg(self, stream_name: str) -> Optional[bytes]:
        with self._lock:
            return self._frames.get(stream_name, None)

    def start(self):
        if self._running:
            return
        try:
            handler_class = self._make_handler()
            self.server = _ThreadingHTTPServer(("0.0.0.0", self.port), handler_class)
            self._running = True
            self._thread = threading.Thread(target=self.server.serve_forever, name="MJPEGServerThread", daemon=True)
            self._thread.start()
            print(f"[MJPEGServer] HTTP Stream aktif di port {self.port} (Endpoint: /cam1 dan /cam2)")
        except Exception as e:
            print(f"[MJPEGServer ERROR] Gagal memulai server HTTP: {e}")

    def stop(self):
        self._running = False
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass
            self.server = None

    def _make_handler(self):
        parent_server = self

        class MJPEGHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def do_GET(self):
                stream_name = self.path.lstrip("/").lower()
                if stream_name not in ["cam1", "cam2"]:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"Endpoint tidak ditemukan. Gunakan /cam1 atau /cam2")
                    return

                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.end_headers()

                try:
                    while parent_server._running:
                        jpeg_bytes = parent_server.get_jpeg(stream_name)
                        if jpeg_bytes:
                            self.wfile.write(b"--frame\r\n")
                            self.send_header("Content-Type", "image/jpeg")
                            self.send_header("Content-Length", str(len(jpeg_bytes)))
                            self.end_headers()
                            self.wfile.write(jpeg_bytes)
                            self.wfile.write(b"\r\n")
                        threading.Event().wait(0.04)
                except Exception:
                    pass

        return MJPEGHandler
