import socket
import struct
import cv2
import numpy as np
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Optional, Dict


class UDPVideoStreamer:
    """
    Streamer video berkecepatan tinggi menggunakan UDP dan kompresi JPEG.
    Memecah frame menjadi chunk kecil (<60 KB) agar tidak terpotong oleh batas MTU jaringan.
    - Port default CAM 1: 9002
    - Port default CAM 2: 9003
    """
    MAX_CHUNK_SIZE = 60000

    def __init__(self, target_ip: str = "127.0.0.1", port: int = 9002, jpeg_quality: int = 70):
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
        """Memperbarui frame terkini untuk endpoint stream_name ('cam1' atau 'cam2')."""
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
                pass  # Sembunyikan log request HTTP agar terminal bersih

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
                        threading.Event().wait(0.04)  # ~25 FPS loop
                except Exception:
                    pass

        return MJPEGHandler
