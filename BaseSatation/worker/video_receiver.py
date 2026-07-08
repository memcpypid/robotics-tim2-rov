import socket
import struct
import threading
import time
import cv2
from typing import Optional, Dict
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage, QPixmap


class UDPFrameReceiver(QObject):
    """
    Background worker untuk menerima stream chunk video UDP (dari ImageProcessing/UDPVideoStreamer)
    dan merakit kembali frame JPEG menjadi QPixmap untuk ditampilkan pada GUI Base Station.
    """
    sig_frame_received = Signal(QPixmap)
    sig_log = Signal(str, str)

    def __init__(self, port: int = 9002, cam_name: str = "CAM 1", parent=None):
        super().__init__(parent)
        self.port = port
        self.cam_name = cam_name
        self.sock: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        self._buffer: Dict[int, Dict[int, bytes]] = {}
        self._expected_chunks: Dict[int, int] = {}
        self.target_ip: str = "AUTO"

    def set_target_ip(self, ip: str):
        self.target_ip = ip
        self.sig_log.emit(f"[{self.cam_name} Receiver] Target IP Jetson diset ke: {ip}", "INFO")

    def start_receiver(self):
        if self._running:
            return
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(("0.0.0.0", self.port))
            self.sock.settimeout(1.0)
            
            self._running = True
            self._thread = threading.Thread(target=self._listen_loop, name=f"Receiver-{self.cam_name}", daemon=True)
            self._thread.start()
            self.sig_log.emit(f"[{self.cam_name} Receiver] Mendengarkan video stream UDP di port {self.port}", "INFO")
        except Exception as e:
            self.sig_log.emit(f"[{self.cam_name} Receiver ERROR] Gagal membuka port {self.port}: {e}", "ERROR")

    def stop_receiver(self):
        self._running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        self.sig_log.emit(f"[{self.cam_name} Receiver] Layanan stream video ditutup.", "INFO")

    def _listen_loop(self):
        while self._running and self.sock:
            try:
                packet, addr = self.sock.recvfrom(65535)
                if len(packet) < 6:
                    continue
                
                # Filter stream agar hanya menerima paket dari IP Jetson yang ditargetkan
                if self.target_ip and self.target_ip not in ["0.0.0.0", "AUTO"]:
                    sender_ip = addr[0]
                    if self.target_ip == "127.0.0.1" and sender_ip not in ["127.0.0.1", "localhost"]:
                        continue
                    elif self.target_ip != "127.0.0.1" and sender_ip != self.target_ip:
                        continue
                
                # Unpack header: !I B B -> 6 bytes
                packet_id, total_chunks, chunk_idx = struct.unpack("!IBB", packet[:6])
                payload = packet[6:]
                
                if packet_id not in self._buffer:
                    self._buffer[packet_id] = {}
                    self._expected_chunks[packet_id] = total_chunks
                    
                self._buffer[packet_id][chunk_idx] = payload
                
                # Jika semua chunk paket sudah lengkap tersusun
                if len(self._buffer[packet_id]) == total_chunks:
                    jpeg_data = b"".join(self._buffer[packet_id][i] for i in range(total_chunks))
                    
                    # Bersihkan buffer dari paket lama untuk mencegah kebocoran memori
                    keys_to_clean = [k for k in self._buffer.keys() if k < packet_id - 5]
                    for k in keys_to_clean:
                        self._buffer.pop(k, None)
                        self._expected_chunks.pop(k, None)
                    self._buffer.pop(packet_id, None)
                    self._expected_chunks.pop(packet_id, None)

                    # Decode dari bytes JPEG ke QPixmap
                    qimg = QImage.fromData(jpeg_data, "JPG")
                    if not qimg.isNull():
                        pix = QPixmap.fromImage(qimg)
                        self.sig_frame_received.emit(pix)

            except socket.timeout:
                pass
            except Exception:
                pass


class GStreamerFrameReceiver(QObject):
    """
    Metode 1 Receiver (Ultra-Light): Menerima stream H.264 over UDP RTP menggunakan GStreamer
    atau FFMPEG backend OpenCV pada Base Station, lalu mendekodenya langsung ke QPixmap untuk GUI.
    """
    sig_frame_received = Signal(QPixmap)
    sig_log = Signal(str, str)

    def __init__(self, port: int = 9002, cam_name: str = "CAM 1", parent=None):
        super().__init__(parent)
        self.port = port
        self.cam_name = cam_name
        self.cap: Optional[cv2.VideoCapture] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.target_ip: str = "AUTO"

    def set_target_ip(self, ip: str):
        self.target_ip = ip
        self.sig_log.emit(f"[{self.cam_name} GStreamer Receiver] Target IP Jetson diset ke: {ip}", "INFO")

    def start_receiver(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, name=f"GstReceiver-{self.cam_name}", daemon=True)
        self._thread.start()
        self.sig_log.emit(f"[{self.cam_name} GStreamer Receiver] Membuka penerima H.264 RTP di port {self.port}...", "INFO")

    def stop_receiver(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        self.sig_log.emit(f"[{self.cam_name} GStreamer Receiver] Layanan H.264 ditutup.", "INFO")

    def _listen_loop(self):
        # 1. Coba pipeline GStreamer RTP H.264 depayloader terlebih dahulu
        gst_pipeline = (
            f"udpsrc port={self.port} caps=\"application/x-rtp, media=video, encoding-name=H264, payload=96\" ! "
            f"rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! video/x-raw, format=BGR ! appsink drop=true max-buffers=1 sync=false"
        )
        self.cap = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)
        
        # 2. Jika GStreamer depayloader gagal di PC lokal, coba langsung via FFMPEG UDP
        if not self.cap.isOpened():
            self.sig_log.emit(f"[{self.cam_name}] GStreamer depay tidak tersedia, mencoba FFMPEG udp://@0.0.0.0:{self.port}...", "WARNING")
            self.cap = cv2.VideoCapture(f"udp://@0.0.0.0:{self.port}", cv2.CAP_FFMPEG)

        if not self.cap.isOpened():
            self.sig_log.emit(f"[{self.cam_name} ERROR] Gagal membuka stream H.264 di port {self.port}", "ERROR")
            self._running = False
            return

        self.sig_log.emit(f"[{self.cam_name} SUCCESS] H.264 Stream terhubung @ port {self.port}!", "SUCCESS")

        while self._running and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret and frame is not None and frame.size > 0:
                try:
                    # Konversi BGR ke RGB untuk Qt
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb_frame.shape
                    qimg = QImage(rgb_frame.data, w, h, ch * w, QImage.Format_RGB888)
                    pix = QPixmap.fromImage(qimg)
                    self.sig_frame_received.emit(pix)
                except Exception:
                    pass
            else:
                time.sleep(0.02)


class DualVideoReceiverManager(QObject):
    """
    Manajer untuk menangani penerimaan stream dari kamera & QR ROV dengan kemampuan
    pengalihan instan (switchable) antara Metode 1 (GStreamer H.264) dan Metode UDP (Optimized JPEG).
    - CAM 1 (Port 9002)
    - CAM 2 (Port 9003)
    - QR Crop Image (Port 9004) -> Selalu menggunakan UDP Frame karena berupa gambar snapshot statis
    """
    sig_frame_cam1 = Signal(QPixmap)
    sig_frame_cam2 = Signal(QPixmap)
    sig_frame_qr = Signal(QPixmap)
    sig_log = Signal(str, str)

    def __init__(self, port_cam1: int = 9002, port_cam2: int = 9003, port_qr: int = 9004, mode: str = "gstreamer", parent=None):
        super().__init__(parent)
        self.port_cam1 = port_cam1
        self.port_cam2 = port_cam2
        self.port_qr = port_qr
        self.mode = mode.lower()
        self._running = False

        self.receiver_cam1 = self._create_receiver(self.port_cam1, "CAM 1 FRONT", self.mode)
        self.receiver_cam2 = self._create_receiver(self.port_cam2, "CAM 2 BOTTOM", self.mode)
        self.receiver_qr = UDPFrameReceiver(port=self.port_qr, cam_name="QR CROP FRAME")

        self._connect_signals()

    def _create_receiver(self, port: int, name: str, mode: str):
        if mode == "gstreamer":
            return GStreamerFrameReceiver(port=port, cam_name=name)
        else:
            return UDPFrameReceiver(port=port, cam_name=name)

    def _connect_signals(self):
        self.receiver_cam1.sig_frame_received.connect(self.sig_frame_cam1)
        self.receiver_cam2.sig_frame_received.connect(self.sig_frame_cam2)
        self.receiver_qr.sig_frame_received.connect(self.sig_frame_qr)
        self.receiver_cam1.sig_log.connect(self.sig_log)
        self.receiver_cam2.sig_log.connect(self.sig_log)
        self.receiver_qr.sig_log.connect(self.sig_log)

    def _disconnect_signals(self):
        try:
            self.receiver_cam1.sig_frame_received.disconnect()
            self.receiver_cam2.sig_frame_received.disconnect()
            self.receiver_cam1.sig_log.disconnect()
            self.receiver_cam2.sig_log.disconnect()
        except Exception:
            pass

    def set_stream_mode(self, mode: str):
        mode_clean = mode.lower()
        if mode_clean != self.mode:
            self.sig_log.emit(f"[DualVideoReceiver] Mengalihkan mode penerimaan ke '{mode_clean.upper()}'...", "INFO")
            was_running = self._running
            if was_running:
                self.receiver_cam1.stop_receiver()
                self.receiver_cam2.stop_receiver()

            self._disconnect_signals()
            self.mode = mode_clean
            self.receiver_cam1 = self._create_receiver(self.port_cam1, "CAM 1 FRONT", self.mode)
            self.receiver_cam2 = self._create_receiver(self.port_cam2, "CAM 2 BOTTOM", self.mode)
            self._connect_signals()

            if was_running:
                self.receiver_cam1.start_receiver()
                self.receiver_cam2.start_receiver()

    def set_target_ip(self, ip: str):
        self.receiver_cam1.set_target_ip(ip)
        self.receiver_cam2.set_target_ip(ip)
        self.receiver_qr.set_target_ip(ip)

    def start_all(self):
        self._running = True
        self.receiver_cam1.start_receiver()
        self.receiver_cam2.start_receiver()
        self.receiver_qr.start_receiver()

    def stop_all(self):
        self._running = False
        self.receiver_cam1.stop_receiver()
        self.receiver_cam2.stop_receiver()
        self.receiver_qr.stop_receiver()
