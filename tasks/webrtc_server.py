import asyncio
import logging
from aiortc import VideoStreamTrack, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.signaling import object_from_string, object_to_string
import cv2
import numpy as np


class VideoStreamTrackCustom(VideoStreamTrack):
    """
    A custom video stream track that streams frames to WebRTC.
    """

    def __init__(self):
        super().__init__()  # Initialize base class
        self.cap = cv2.VideoCapture(
            "rtsp://admin:jonsion1@192.168.1.64/h264/ch1/main/av_stream")  # RTSP video stream URL

    async def recv(self):
        ret, frame = self.cap.read()
        if not ret:
            raise Exception("Failed to read video frame")

        # Resize the frame to desired size
        frame = cv2.resize(frame, (640, 480))

        # Convert to RGB (WebRTC expects RGB frames)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Encode the frame as JPEG
        ret, jpeg = cv2.imencode('.jpg', frame)
        if not ret:
            raise Exception("Failed to encode video frame")

        # Convert JPEG to bytes
        return jpeg.tobytes()


async def create_offer(pc, signaling):
    # Create an offer
    await pc.setLocalDescription(await pc.createOffer())

    # Send offer to signaling server
    offer_sdp = object_to_string(pc.localDescription)
    signaling.send(offer_sdp)


async def answer_offer(pc, signaling, sdp):
    # Set the remote description to the offer from the client
    offer = object_from_string(sdp)
    await pc.setRemoteDescription(offer)

    # Create an answer and send it back to the client
    await pc.setLocalDescription(await pc.createAnswer())
    answer_sdp = object_to_string(pc.localDescription)
    signaling.send(answer_sdp)


async def signaling_handler(pc, signaling):
    # Signaling handler to manage offer/answer exchange
    while True:
        message = signaling.receive()

        if message:
            sdp = message
            await answer_offer(pc, signaling, sdp)


async def webrtc_server():
    signaling = Signaling()  # Your custom signaling handler (could be WebSocket, HTTP, etc.)

    # Create a peer connection
    pc = RTCPeerConnection()

    # Add custom video track
    pc.addTrack(VideoStreamTrackCustom())

    # Start the signaling handler in the background
    asyncio.create_task(signaling_handler(pc, signaling))

    # Create and send an offer
    await create_offer(pc, signaling)

    # Run the event loop
    await asyncio.Event().wait()


def start_webrtc_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(webrtc_server())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    start_webrtc_server()
