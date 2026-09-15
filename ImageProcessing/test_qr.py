import cv2
import numpy as np
from pyzbar import pyzbar

img = cv2.imread(r"G:\Kuliah\ROV\robotics-tim2-rov\ImageProcessing\contoh_QR\image.png")
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

print("Original shape:", gray.shape)

# 1. Normal PyZbar
res1 = pyzbar.decode(gray)
print("1. Normal PyZbar:", [r.data for r in res1])

# 2. CLAHE
clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
gray_clahe = clahe.apply(gray)
print("2. CLAHE PyZbar:", [r.data for r in pyzbar.decode(gray_clahe)])

# 3. Threshold
_, thresh = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY)
print("3. Thresh PyZbar:", [r.data for r in pyzbar.decode(thresh)])

# 4. Adaptive Threshold
athresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 2)
print("4. Adaptive Thresh:", [r.data for r in pyzbar.decode(athresh)])

# 5. Crop and Perspective (Manual test)
H, W = gray.shape
src2 = np.float32([[W*0.3, H*0.2], [W*0.7, H*0.2], [W, H], [0, H]])
dst2 = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
m = cv2.getPerspectiveTransform(src2, dst2)
warped = cv2.warpPerspective(gray, m, (W, H))
print("5. Warped 1:", [r.data for r in pyzbar.decode(warped)])

cv2.imwrite("warped.png", warped)
cv2.imwrite("athresh.png", athresh)
cv2.imwrite("thresh.png", thresh)

# Let's try WeChat QRCode if available
try:
    detector = cv2.wechat_qrcode_WeChatQRCode()
    res, points = detector.detectAndDecode(gray)
    print("6. WeChat:", res)
except Exception as e:
    print("6. WeChat Failed:", e)

# Built-in OpenCV
detector2 = cv2.QRCodeDetector()
res, points, _ = detector2.detectAndDecode(img)
print("7. OpenCV built-in:", res)

