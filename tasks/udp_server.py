import cv2
import socket
import struct
import time

UDP_IP = "127.0.0.1"
UDP_PORT = 5005
PACKET_SIZE = 60000  # 每个数据包的最大大小
FRAME_WIDTH, FRAME_HEIGHT = 320, 240
FRAME_QUALITY = 50

def start_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    cap = cv2.VideoCapture("rtsp://admin:jonsion1@192.168.1.64/h264/ch1/main/av_stream")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, 30)

    frame_id = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, FRAME_QUALITY])
        data = buffer.tobytes()

        total_packets = (len(data) // PACKET_SIZE) + 1
        for i in range(total_packets):
            chunk = data[i * PACKET_SIZE:(i + 1) * PACKET_SIZE]
            header = struct.pack("III", frame_id, i, total_packets)  # 帧 ID、分块序号、总分块数
            sock.sendto(header + chunk, (UDP_IP, UDP_PORT))

        frame_id += 1
        time.sleep(1 / 30)

    cap.release()
    sock.close()

if __name__ == "__main__":
    start_server()
