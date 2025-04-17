import cv2
import os
import ctypes

from PIL import ImageFont, ImageDraw, Image
import numpy as np
from pathlib import Path

from config.face_config import samples_path, classifier_path, train_size
from .draw_chs import draw_chs

def set_window_topmost(window_name):
    """使用 Windows API 将窗口置顶"""
    hwnd = ctypes.windll.user32.FindWindowW(None, window_name)
    if hwnd != 0:  # 如果找到窗口
        ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 1 | 2)

classifier = cv2.CascadeClassifier(classifier_path)

def collect(user_id):
    sample_num = 0

    # 打开摄像头
    capture = cv2.VideoCapture(0)

    collect_flag = False
    def mouse_callback(event, x, y, flags, param):
        nonlocal collect_flag
        if event == cv2.EVENT_LBUTTONDOWN:  # 鼠标左键点击
            print("clicked")
            collect_flag = True

    # 创建窗口
    window_name = 'Collecting......'
    cv2.namedWindow(window_name, cv2.WINDOW_KEEPRATIO)
    cv2.resizeWindow(window_name, 800, 600)
    cv2.moveWindow(window_name, (1920-800) >> 1, (1080-600) >> 1)
    cv2.setMouseCallback(window_name, mouse_callback)

    # 退出标志
    should_exit = False

    while capture.isOpened() and not should_exit:
        res, frame = capture.read()

        if not res:
            print("未能读取到有效帧")
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = classifier.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(100, 100))

        if collect_flag:
            if len(faces) == 1:
                x, y, w, h = faces[0]
                # print(f"{w}x{h}")
                cv2.rectangle(frame, (x, y), (x + w, y + h), (200, 0, 250), 2)
                draw_chs(frame, "正在录入", (x, y + h), (200, 0, 255), 40)
                sample_num += 1
                gray_face = gray[y:y+h, x:x+w]
                cv2.imwrite(samples_path / Path(f"{user_id}.{sample_num}.jpg"), gray_face)
            else:
                for x, y, w, h in faces:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (200, 0, 250), 2)
                    draw_chs(frame, "检测到多个目标", (x, y + h), (200, 0, 255), 30)
        else:
            draw_chs(frame, "点击开始录入", (100, 100), (0, 0, 255), 30)

        # cv2.putText(frame, 'Close the window to quit', (30, 60), font, 1, (200, 0, 250), 2)
        cv2.imshow(window_name, frame)

        # 设置窗口置顶
        set_window_topmost(window_name)

        # 按 'Esc' 键退出或者窗口关闭时退出
        key = cv2.waitKey(4) & 0xFF
        if key == 27 or cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1 or sample_num == train_size:
            should_exit = True

    # 释放摄像头并销毁窗口
    capture.release()
    cv2.destroyAllWindows()
    return f'共采集了ID为{user_id}的同学的{sample_num}张图片'

if __name__ == '__main__':
    print(collect(1))
