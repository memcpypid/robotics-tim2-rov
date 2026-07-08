import socket
import struct
import threading
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
        
        # Buffer untuk menyusun chunk berdasarkan packet_id
        self._buffer: Dict[int, Dict[int, bytes]] = {}
        self._expected_chunks: Dict[int, int] = {}

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
                packet, _ = self.sock.recvfrom(65535)
                if len(packet) < 6:
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


class DualVideoReceiverManager(QObject):
    """
    Manajer untuk menangani penerimaan stream dari kamera & QR ROV:
    - CAM 1 (Port 9002)
    - CAM 2 (Port 9003)
    - QR Crop Image (Port 9004)
    """
    sig_frame_cam1 = Signal(QPixmap)
    sig_frame_cam2 = Signal(QPixmap)
    sig_frame_qr = Signal(QPixmap)
    sig_log = Signal(str, str)

    def __init__(self, port_cam1: int = 9002, port_cam2: int = 9003, port_qr: int = 9004, parent=None):
        super().__init__(parent)
        self.receiver_cam1 = UDPFrameReceiver(port=port_cam1, cam_name="CAM 1 FRONT")
        self.receiver_cam2 = UDPFrameReceiver(port=port_cam2, cam_name="CAM 2 BOTTOM")
        self.receiver_qr = UDPFrameReceiver(port=port_qr, cam_name="QR CROP FRAME")

        self.receiver_cam1.sig_frame_received.connect(self.sig_frame_cam1)
        self.receiver_cam2.sig_frame_received.connect(self.sig_frame_cam2)
        self.receiver_qr.sig_frame_received.connect(self.sig_frame_qr)
        self.receiver_cam1.sig_log.connect(self.sig_log)
        self.receiver_cam2.sig_log.connect(self.sig_log)
        self.receiver_qr.sig_log.connect(self.sig_log)

    def start_all(self):
        self.receiver_cam1.start_receiver()
        self.receiver_cam2.start_receiver()
        self.receiver_qr.start_receiver()

    def stop_all(self):
        self.receiver_cam1.stop_receiver()
        self.receiver_cam2.stop_receiver()
        self.receiver_qr.stop_receiver()
