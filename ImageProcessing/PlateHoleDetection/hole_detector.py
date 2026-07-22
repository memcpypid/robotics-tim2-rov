import cv2
import numpy as np

def empty(a):
    pass

def detect_holes():
    cap = cv2.VideoCapture(2) # USB Cam
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)

    # 1. Parameter Warna
    cv2.namedWindow("Filter Warna Kardus")
    cv2.resizeWindow("Filter Warna Kardus", 400, 250)
    cv2.createTrackbar("Hue Min", "Filter Warna Kardus", 15, 179, empty)
    cv2.createTrackbar("Hue Max", "Filter Warna Kardus", 27, 179, empty)
    cv2.createTrackbar("Sat Min", "Filter Warna Kardus", 41, 255, empty)
    cv2.createTrackbar("Sat Max", "Filter Warna Kardus", 200, 255, empty)
    cv2.createTrackbar("Val Min", "Filter Warna Kardus", 60, 255, empty)
    cv2.createTrackbar("Val Max", "Filter Warna Kardus", 145, 255, empty)

    # 2. Parameter Ukuran Bentuk
    cv2.namedWindow("Parameter Ukuran")
    cv2.resizeWindow("Parameter Ukuran", 400, 150)
    cv2.createTrackbar("Min Area Plat", "Parameter Ukuran", 5000, 300000, empty)
    cv2.createTrackbar("Min Area Lubang", "Parameter Ukuran", 500, 20000, empty)
    cv2.createTrackbar("Min Circularity", "Parameter Ukuran", 15, 100, empty) # Diturunkan default ke 15 agar bentuk elips (dari samping) bisa terdeteksi

    # 3. Konstanta Kalibrasi Jarak Kamera
    REAL_DIAMETER_CM = 4
    FOCAL_LENGTH = 634

    # 4. Variabel untuk Smoothing (Anti-Glitch)
    smoothed_center = None
    smoothed_axes = None
    smoothed_angle = None
    alpha = 0.5  # Diubah ke 0.5 agar pergerakan lebih cepat dan responsif

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        h_min = cv2.getTrackbarPos("Hue Min", "Filter Warna Kardus")
        h_max = cv2.getTrackbarPos("Hue Max", "Filter Warna Kardus")
        s_min = cv2.getTrackbarPos("Sat Min", "Filter Warna Kardus")
        s_max = cv2.getTrackbarPos("Sat Max", "Filter Warna Kardus")
        v_min = cv2.getTrackbarPos("Val Min", "Filter Warna Kardus")
        v_max = cv2.getTrackbarPos("Val Max", "Filter Warna Kardus")

        min_area_plate = cv2.getTrackbarPos("Min Area Plat", "Parameter Ukuran")
        min_area_hole = cv2.getTrackbarPos("Min Area Lubang", "Parameter Ukuran")
        min_circularity = cv2.getTrackbarPos("Min Circularity", "Parameter Ukuran") / 100.0

        real_diameter = REAL_DIAMETER_CM
        focal_length = FOCAL_LENGTH

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        hsv = cv2.GaussianBlur(hsv, (7, 7), 0)

        lower_bound = np.array([h_min, s_min, v_min])
        upper_bound = np.array([h_max, s_max, v_max])
        mask = cv2.inRange(hsv, lower_bound, upper_bound)

        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, hierarchy = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        if hierarchy is not None:
            plate_idx = -1
            max_plate_area = 0

            for i, cnt in enumerate(contours):
                area = cv2.contourArea(cnt)
                if area > min_area_plate:
                    if area > max_plate_area:
                        max_plate_area = area
                        plate_idx = i

            if plate_idx != -1:
                plate_cnt = contours[plate_idx]
                
                # Mencari aproksimasi poligon dengan tepat 4 titik (bentuk segiempat/trapesium)
                peri = cv2.arcLength(plate_cnt, True)
                approx_polygon = None
                
                # Coba beberapa nilai epsilon untuk memaksa menemukan 4 sudut
                for eps in np.linspace(0.01, 0.1, 10):
                    approx = cv2.approxPolyDP(plate_cnt, eps * peri, True)
                    if len(approx) == 4:
                        approx_polygon = approx
                        break
                
                # Jika tidak bisa dipaksa jadi 4 titik (misal terlalu melengkung), fallback ke kotak persegi (minAreaRect)
                if approx_polygon is None:
                    rect = cv2.minAreaRect(plate_cnt)
                    approx_polygon = np.int32(cv2.boxPoints(rect))
                
                # Menggambar poligon plat kardus dengan garis tipis (1)
                cv2.drawContours(frame, [approx_polygon], 0, (255, 0, 0), 1)

                hole_candidates = []
                for i, cnt in enumerate(contours):
                    parent_idx = hierarchy[0][i][3]
                    
                    if parent_idx == plate_idx:
                        area = cv2.contourArea(cnt)
                        if area > min_area_hole:
                            perimeter = cv2.arcLength(cnt, True)
                            if perimeter > 0 and len(cnt) >= 5: # cv2.fitEllipse butuh minimal 5 titik
                                circularity = 4 * np.pi * (area / (perimeter * perimeter))
                                if circularity >= min_circularity:
                                    temp_ellipse = cv2.fitEllipse(cnt)
                                    (tcx, tcy), (t_minor, t_major), tangle = temp_ellipse
                                    # Filter rasio aspek (menghindari noise garis/objek sangat lonjong)
                                    if t_minor > 0 and (t_major / t_minor) < 4.0:
                                        hole_candidates.append({
                                            "contour": cnt,
                                            "area": area,
                                            "circularity": circularity,
                                            "ellipse": temp_ellipse
                                        })

                if len(hole_candidates) > 0:
                    hole_candidates.sort(key=lambda x: x["area"], reverse=True)
                    best_hole = hole_candidates[0]
                    
                    # Ambil data elips
                    ellipse = best_hole["ellipse"]
                    (cx, cy), (minor_axis, major_axis), angle = ellipse
                    
                    # Terapkan Exponential Moving Average (EMA) untuk mengurangi glitch/flicker
                    if smoothed_center is None:
                        smoothed_center = (cx, cy)
                        smoothed_axes = (minor_axis, major_axis)
                        smoothed_angle = angle
                    else:
                        scx, scy = smoothed_center
                        smoothed_center = (scx + alpha * (cx - scx), scy + alpha * (cy - scy))
                        
                        s_minor, s_major = smoothed_axes
                        smoothed_axes = (s_minor + alpha * (minor_axis - s_minor), s_major + alpha * (major_axis - s_major))
                        smoothed_angle = smoothed_angle + alpha * (angle - smoothed_angle)
                    
                    draw_center = (int(smoothed_center[0]), int(smoothed_center[1]))
                    draw_axes = (int(smoothed_axes[0]/2), int(smoothed_axes[1]/2))
                    draw_angle = smoothed_angle
                    
                    # Gambar elips untuk lubang yang sudah di-smooth dengan garis lebih tipis (1)
                    cv2.ellipse(frame, draw_center, draw_axes, draw_angle, 0, 360, (0, 255, 0), 2)
                    cv2.circle(frame, draw_center, 4, (0, 0, 255), -1)
                    
                    # ---------------------------------------------------------
                    # PENGUKURAN JARAK
                    # ---------------------------------------------------------
                    pixel_diameter = smoothed_axes[1]
                    if pixel_diameter > 0:
                        distance_cm = (real_diameter * focal_length) / pixel_diameter
                        
                        r_approx = int(smoothed_axes[1] / 2)
                        teks_jarak = f"Jarak Kamera: {distance_cm:.1f} cm"
                        cv2.putText(frame, teks_jarak, (draw_center[0]-70, draw_center[1]-r_approx-25), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                    
                    teks_info = f"Lubang (C:{best_hole['circularity']:.2f})"
                    cv2.putText(frame, teks_info, (draw_center[0]-50, draw_center[1]-r_approx-5), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                else:
                    # Reset smoothing jika tidak ada lubang agar tidak nyangkut
                    smoothed_center = None
                    smoothed_axes = None
                    smoothed_angle = None

        cv2.imshow("Masking Warna (HSV)", mask)
        cv2.imshow("Kamera Asli", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    detect_holes()
