#!/usr/bin/env python3
"""
Main Controller untuk modul Image Processing & Camera Streaming Base Station ROV.
Menangani 2 sumber kamera sekaligus (Laptop Camera & Action Camera via Kabel USB),
melakukan pembacaan QR Code secara real-time, dan mengirimkan data telemetri + stream video
ke Base Station GUI melalui protokol UDP dan MJPEG.
"""

import argparse
import time
import signal
import sys
import cv2

from camera import DualCameraCapture
from processing import QRCodeProcessor
from network import QRDataSender, UDPVideoStreamer, UnifiedVideoStreamer, MJPEGServer


def main():
    parser = argparse.ArgumentParser(description="Image Processing & 2-CH Camera Streaming ROV")
    parser.add_argument("--cam1", default="0", help="Device index / path untuk CAM 1 (Laptop Camera / Front Nav), default: 0")
    parser.add_argument("--cam2", default="1", help="Device index / path untuk CAM 2 (Action Cam USB / Bottom QR), default: 1")
    parser.add_argument("--bs-ip", default="127.0.0.1", help="Alamat IP Base Station GUI tujuan, default: 127.0.0.1")
    parser.add_argument("--telemetry-port", type=int, default=9000, help="Port UDP tujuan telemetri QR Code, default: 9000")
    parser.add_argument("--cam1-port", type=int, default=9002, help="Port UDP tujuan stream CAM 1, default: 9002")
    parser.add_argument("--cam2-port", type=int, default=9003, help="Port UDP tujuan stream CAM 2, default: 9003")
    parser.add_argument("--qr-img-port", type=int, default=9004, help="Port UDP tujuan stream gambar crop QR Code, default: 9004")
    parser.add_argument("--mjpeg-port", type=int, default=8080, help="Port HTTP lokal untuk MJPEG stream (/cam1 dan /cam2), default: 8080")
    parser.add_argument("--stream-mode", default="gstreamer", choices=["gstreamer", "udp"], help="Metode stream video ('gstreamer' untuk Mode 1 H.264 Hardware, 'udp' untuk Optimized JPEG chunking), default: gstreamer")
    parser.add_argument("--show", action="store_true", help="Tampilkan jendela preview lokal OpenCV di layar saat berjalan")
    parser.add_argument("--fps", type=int, default=30, help="Target frame rate pemrosesan loop, default: 30")
    args = parser.parse_args()

    print("==========================================================")
    print("🛸 ROV DUAL CAMERA & QR CODE PROCESSING SYSTEM")
    print("==========================================================")
    print(f"-> CAM 1 (Laptop / Front) : {args.cam1}")
    print(f"-> CAM 2 (Action Cam USB) : {args.cam2}")
    print(f"-> Target Base Station  : {args.bs_ip if hasattr(args, 'bs_ip') else getattr(args, 'bs-ip', '127.0.0.1')} (Telemetry Port: {args.telemetry_port})")
    print(f"-> Stream UDP Ports     : CAM 1 @ {args.cam1_port} | CAM 2 @ {args.cam2_port} | QR Crop @ {args.qr_img_port}")
    print(f"-> Stream Method Mode   : {args.stream_mode.upper()}")
    print(f"-> Local MJPEG Server   : http://0.0.0.0:{args.mjpeg_port}/cam1 dan /cam2")
    print("==========================================================\n")

    bs_ip = getattr(args, 'bs_ip', getattr(args, 'bs-ip', '127.0.0.1'))

    # 1. Inisialisasi Kamera
    dual_capture = DualCameraCapture(cam1_source=args.cam1, cam2_source=args.cam2, width=640, height=480)
    dual_capture.start_all()

    # 2. Inisialisasi QR Decoder Engine
    qr_processor = QRCodeProcessor()

    # 3. Inisialisasi Network Data & Streamer
    qr_sender = QRDataSender(base_station_ip=bs_ip, port=args.telemetry_port)
    streamer_cam1 = UnifiedVideoStreamer(target_ip=bs_ip, port=args.cam1_port, mode=args.stream_mode)
    streamer_cam2 = UnifiedVideoStreamer(target_ip=bs_ip, port=args.cam2_port, mode=args.stream_mode)
    streamer_qr = UDPVideoStreamer(target_ip=bs_ip, port=args.qr_img_port, jpeg_quality=80)
    
    def start_auto_discovery():
        import socket, threading
        def _loop():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("0.0.0.0", 9005))
                print("[AutoDiscovery] Mendengarkan paket PING_STREAM dari Base Station di port 9005...")
                current_ip = qr_sender.base_station_ip
                while True:
                    data, addr = sock.recvfrom(1024)
                    client_ip = addr[0]
                    if client_ip != current_ip:
                        current_ip = client_ip
                        print(f"\n[AutoDiscovery] Target Base Station terdeteksi di {client_ip}! Mengubah tujuan stream & telemetri...")
                        qr_sender.update_target(client_ip, qr_sender.port)
                        streamer_cam1.update_target(client_ip, streamer_cam1.port)
                        streamer_cam2.update_target(client_ip, streamer_cam2.port)
                        streamer_qr.update_target(client_ip, streamer_qr.port)
            except Exception as e:
                print(f"[AutoDiscovery ERROR] {e}")
        t = threading.Thread(target=_loop, name="StreamAutoDiscovery", daemon=True)
        t.start()
    
    start_auto_discovery()
    
    mjpeg_server = MJPEGServer(port=args.mjpeg_port)
    mjpeg_server.start()

    # Flag penghentian bersih
    running = True

    def signal_handler(sig, frame):
        nonlocal running
        print("\n[System] Menerima sinyal penghentian. Menutup kamera & stream...")
        running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("\n[System] Loop pemrosesan gambar aktif! Tekan Ctrl+C untuk berhenti.")
    loop_delay = 1.0 / max(1, args.fps)

    try:
        while running:
            start_time = time.time()

            # Ambil frame terbaru dari kedua kamera
            frame1, frame2 = dual_capture.get_frames()

            # Pemrosesan CAM 1 (Front Navigation + QR Scan)
            if frame1 is not None:
                processed_frame1, qr_text1, timestamp1, qr_crop1 = qr_processor.process_frame(frame1)
                
                if qr_text1:
                    qr_sender.send_qr_result(qr_text1, timestamp1, cam_source="CAM 1: FRONT NAV", image_crop=qr_crop1)
                    if qr_crop1 is not None:
                        streamer_qr.send_frame(qr_crop1)

                streamer_cam1.send_frame(processed_frame1)
                mjpeg_server.update_frame("cam1", processed_frame1)
                if args.show:
                    cv2.imshow("Preview CAM 1 - Front Navigation", processed_frame1)

            # Pemrosesan CAM 2 (Bottom / Action Cam + QR Scan)
            if frame2 is not None:
                processed_frame2, qr_text2, timestamp2, qr_crop2 = qr_processor.process_frame(frame2)
                
                if qr_text2:
                    qr_sender.send_qr_result(qr_text2, timestamp2, cam_source="CAM 2: BOTTOM QR", image_crop=qr_crop2)
                    if qr_crop2 is not None:
                        streamer_qr.send_frame(qr_crop2)

                streamer_cam2.send_frame(processed_frame2)
                mjpeg_server.update_frame("cam2", processed_frame2)
                if args.show:
                    cv2.imshow("Preview CAM 2 - Bottom QR & Action Cam", processed_frame2)

            if args.show:
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            # Pertahankan target FPS
            elapsed = time.time() - start_time
            if elapsed < loop_delay:
                time.sleep(loop_delay - elapsed)

    finally:
        running = False
        dual_capture.stop_all()
        qr_sender.close()
        streamer_cam1.close()
        streamer_cam2.close()
        streamer_qr.close()
        mjpeg_server.stop()
        if args.show:
            cv2.destroyAllWindows()
        print("[System] Semua layanan ImageProcessing ditutup dengan bersih.")


if __name__ == "__main__":
    main()
