import cv2
import numpy as np
from PIL import Image

from config.face_config import recognizer_path, samples_path

recognizer = cv2.face.LBPHFaceRecognizer.create()


def data_translate(path):
    face_data = []
    id_data = []
    file_list = [p for p in path.iterdir()]
    for file in file_list:
        file_name = file.stem
        pil_image = Image.open(file).convert("L")
        np_image = np.array(pil_image, "uint8")
        uid = int(file_name.split(".")[0])
        face_data.append(np_image)
        id_data.append(uid)
    return face_data, id_data


def train():
    print("开始训练模型")
    faces, uids = data_translate(samples_path)
    recognizer.train(faces, np.array((uids)))
    recognizer.save(recognizer_path)
    print("模型保存成功")


if __name__ == "__main__":
    train()
