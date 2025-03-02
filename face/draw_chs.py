from PIL import Image, ImageFont, ImageDraw
import cv2
import numpy as np
from pathlib import Path

fontfile_chs = Path(__file__).parent / Path("msyh.ttc")

def draw_chs(frame, text, position, text_color, text_size):
    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img)
    font_style = ImageFont.truetype(fontfile_chs, size=text_size, encoding="utf-8")
    b, g, r = text_color
    text_color = (r, g, b)
    draw.text(xy=position, text=text, font=font_style, fill=text_color)
    cv2.cvtColor(src=np.asarray(img), code=cv2.COLOR_RGB2BGR, dst=frame)
