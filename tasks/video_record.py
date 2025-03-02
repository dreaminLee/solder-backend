# import cv2
#
# # RTSP URL (替换为实际的 URL)
# RTSP_URL = "rtsp://admin:jonsion1@192.168.1.64/h264/ch1/main/av_stream"
#
# # 创建视频捕获对象
# cap = cv2.VideoCapture(RTSP_URL)
#
# # 检查是否成功打开视频流
# if not cap.isOpened():
#     print("无法打开 RTSP 流")
#     exit()
#
# # 获取视频的帧宽度和高度
# frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
# frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
#
# # 定义保存视频的文件名
# output_filename = "output_video.avi"
#
# # 创建 VideoWriter 对象，指定编码方式、帧率、帧大小等
# fourcc = cv2.VideoWriter_fourcc(*'XVID')  # 使用 XVID 编码
# out = cv2.VideoWriter(output_filename, fourcc, 25.0, (frame_width, frame_height))
#
# # 关闭显示窗口
# cv2.namedWindow("RTSP Stream", cv2.WINDOW_NORMAL)
# cv2.destroyAllWindows()
#
# while True:
#     ret, frame = cap.read()
#     if not ret:
#         print("无法读取视频帧")
#         break
#
#     # 将读取到的每一帧写入视频文件
#     out.write(frame)
#
#     # 按 'Esc' 键退出
#     key = cv2.waitKey(1) & 0xFF
#     if key == 27:
#         break
#
# # 释放资源并关闭视频文件
# cap.release()
# out.release()
# cv2.destroyAllWindows()
#
# print(f"视频保存成功，保存路径：{output_filename}")
