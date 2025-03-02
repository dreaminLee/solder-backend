import asyncio
import json
import requests
import cv2  # 导入 OpenCV 库
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.contrib.media import MediaPlayer, VideoFrame

RTSP_URL = "rtsp://admin:jonsion1@192.168.1.64/h264/ch1/main/av_stream"

# 自定义视频流轨道，用于从服务器接收视频流
class RTSPVideoStreamTrack(VideoStreamTrack):
    def __init__(self, rtsp_url):
        super().__init__()
        self.cap = cv2.VideoCapture(rtsp_url)

    async def recv(self):
        # 从RTSP流中读取帧
        ret, frame = self.cap.read()
        if not ret:
            raise Exception("无法读取RTSP流帧")

        # 将OpenCV的帧转换为WebRTC兼容的格式
        frame = VideoFrame.from_ndarray(frame, format="bgr24")
        frame.pts, frame.time_base = await self.next_timestamp()
        return frame

    def __del__(self):
        # 释放资源
        self.cap.release()

# 客户端与服务器建立WebRTC连接并发送/接收SDP
async def connect_to_server():
    pc = RTCPeerConnection()

    # 创建RTSP视频轨道并添加到连接中
    video_track = RTSPVideoStreamTrack(RTSP_URL)
    pc.addTrack(video_track)

    # 创建WebRTC offer
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    # 发送offer到信令服务器
    response = requests.post(
        "http://127.0.0.1:8080/offer",
        json={"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
    )
    data = response.json()

    # 从服务器接收SDP answer
    answer = RTCSessionDescription(sdp=data['sdp'], type=data['type'])
    await pc.setRemoteDescription(answer)

    # 输出WebRTC连接的状态
    print("WebRTC连接已建立")
    print(f"本地描述：{pc.localDescription}")
    print(f"远程描述：{pc.remoteDescription}")

    # 保持连接
    await asyncio.sleep(3600)  # 保持连接1小时

if __name__ == "__main__":
    asyncio.run(connect_to_server())
