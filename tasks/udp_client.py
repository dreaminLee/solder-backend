import cv2
import socket
import struct
import numpy as np

UDP_IP = "127.0.0.1"
UDP_PORT = 5005
PACKET_SIZE = 60000  # 每个数据包的最大大小
WINDOW_WIDTH, WINDOW_HEIGHT = 320, 240

def start_client():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    sock.settimeout(0.1)  # 设置超时时间为 100 毫秒

    cv2.namedWindow("Client Video")
    cv2.resizeWindow("Client Video", WINDOW_WIDTH, WINDOW_HEIGHT)

    buffer_dict = {}
    current_frame_id = -1

    while True:
        try:
            packet, _ = sock.recvfrom(PACKET_SIZE + 12)  # 12 字节的头部 + 数据
            frame_id, chunk_id, total_chunks = struct.unpack("III", packet[:12])
            chunk_data = packet[12:]

            if frame_id not in buffer_dict:
                buffer_dict[frame_id] = [None] * total_chunks

            buffer_dict[frame_id][chunk_id] = chunk_data

            # 如果所有分块已接收完，显示完整帧
            if None not in buffer_dict[frame_id] and frame_id > current_frame_id:
                frame_data = b''.join(buffer_dict[frame_id])
                frame = cv2.imdecode(np.frombuffer(frame_data, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is not None:
                    cv2.imshow("Client Video", frame)
                    current_frame_id = frame_id

                del buffer_dict[frame_id]  # 删除已处理的帧

            if cv2.waitKey(1) == ord('q'):
                break

        except socket.timeout:
            continue  # 超时则跳过，继续接收下一个包

    cv2.destroyAllWindows()
    sock.close()

if __name__ == "__main__":
    start_client()
