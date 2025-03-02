import cv2

# RTSP URL (替换为实际的 URL)
RTSP_URL = "rtsp://admin:jonsion1@192.168.1.64/h264/ch1/main/av_stream"

# 创建视频捕获对象
cap = cv2.VideoCapture(RTSP_URL)

# 检查是否成功打开视频流
if not cap.isOpened():
    print("无法打开 RTSP 流")
    exit()

# 显示视频流
cv2.namedWindow("RTSP Stream", cv2.WINDOW_NORMAL)

while True:
    ret, frame = cap.read()
    if not ret:
        print("无法读取视频帧")
        break

    cv2.imshow("RTSP Stream", frame)

    # 按 'Esc' 键退出
    key = cv2.waitKey(1) & 0xFF

    # 如果按下 'Esc' 键，或者窗口关闭，退出循环
    if key == 27 or cv2.getWindowProperty("RTSP Stream", cv2.WND_PROP_VISIBLE) < 1:
        break
if __name__ == '__main__':
    # 释放资源并关闭窗口
    cap.release()
    cv2.destroyAllWindows()
