import asyncio
from flask import Flask, request, jsonify
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer

app = Flask(__name__)
pc = None  # 全局的 WebRTC PeerConnection 实例
RTSP_URL = "rtsp://admin:jonsion1@192.168.1.64/h264/ch1/main/av_stream"

@app.route("/offer", methods=["POST"])
def offer():
    global pc

    # 获取客户端的 SDP offer
    offer_sdp = request.json["sdp"]
    offer_type = request.json["type"]

    # 创建 PeerConnection 实例
    pc = RTCPeerConnection()

    # 添加 RTSP 视频流轨道
    player = MediaPlayer(RTSP_URL)
    pc.addTrack(player.video)

    async def handle_offer():
        # 设置远端描述
        offer = RTCSessionDescription(sdp=offer_sdp, type=offer_type)
        await pc.setRemoteDescription(offer)

        # 创建 SDP answer
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        return pc.localDescription

    # 运行异步任务
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    answer = loop.run_until_complete(handle_offer())

    # 返回 SDP answer
    return jsonify({"sdp": answer.sdp, "type": answer.type})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080)
