import cv2
import time
from datetime import datetime

from config.face_config import classifier_path, recognizer_path
from .draw_chs import draw_chs
from .collect import set_window_topmost

classfier = cv2.CascadeClassifier(classifier_path)
detected_threshold = 30
conf_threshold = 70

def detect():
    recognizer = cv2.face.LBPHFaceRecognizer.create()
    if not recognizer_path.exists():
        return "UNKNOWN"
    recognizer.read(recognizer_path)
    id = 'UNKNOWN'

    capture = cv2.VideoCapture(0)

    # 标记是否退出
    exit_flag = False
    timeout_flag = False

    # 鼠标点击事件回调函数
    def mouse_callback(event, x, y, flags, param):
        nonlocal exit_flag
        if event == cv2.EVENT_LBUTTONDOWN:  # 鼠标左键点击
            print("clicked")
            exit_flag = True

    # 先创建窗口
    window_name = "Detecting......"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 800, 600)
    cv2.moveWindow(window_name, (1920-800) >> 1, (1080-600) >> 1)

    # 设置鼠标回调函数
    cv2.setMouseCallback(window_name, mouse_callback)

    start_time = time.time()
    detected = 0
    while capture.isOpened() and not exit_flag:
        if time.time() - start_time >= 30:
            timeout_flag = True
            break
        res, frame = capture.read()

        if not res:
            print("未能读取到有效帧")
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = classfier.detectMultiScale(gray, 1.2, 5, minSize=(100, 100))

        if not len(faces):
            print("未检测到人脸")
        elif len(faces) == 1:
            x, y, w, h = faces[0]
            gray_face = gray[y:y+h, x:x+w]
            label, conf = recognizer.predict(gray_face)
            print(f"{label}: {conf}")
            if conf < conf_threshold:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (76, 177, 34), 2)
                draw_chs(frame, "正在识别", (x, y + h), (76, 177, 34), 30)
                detected += 1
                id = label
            else:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 240, 240), 2)
                draw_chs(frame, "正在识别", (x, y + h), (0, 240, 240), 30)
        else:
            for x, y, w, h in faces:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                draw_chs(frame, "检测到多个目标", (x, y + h), (0, 0, 255), 30)

        draw_chs(frame, "点击退出", (30, 60), (0, 0, 255), 30)
        cv2.imshow(window_name, frame)
        set_window_topmost(window_name)

        # delay, frame will not show if waitKey not called
        cv2.waitKey(4)

        if detected >= detected_threshold or exit_flag or cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
            break

    # 释放摄像头并关闭窗口
    capture.release()
    cv2.destroyAllWindows()
    return "UNKNOWN" if timeout_flag or exit_flag else id

if __name__ == "__main__":
    print(detect())
