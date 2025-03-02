import os
import json
from datetime import datetime
import base64
import hashlib

import requests
from flask import Blueprint, request

from util.Response import Response
#
# # TRIAL_FILE = "trial_info.json"
# # EXTENSION_TIME = 60  # 延期时间（秒）
# # SECRET_KEY = "18401010407"
# # secret_ID = "zhangjiahui"
# #
# # def generate_extension_code(secret_ID):
# #     """
# #     生成延期码
# #     :param secret_ID: 用户设备ID
# #     """
# #     timestamp = get_timestamp_from_network_time() + EXTENSION_TIME  # 生成未来的时间戳
# #     data = f"{secret_ID}|{timestamp}|{SECRET_KEY}"
# #     hash_data = hashlib.sha256(data.encode()).hexdigest()
# #     extension_code = base64.urlsafe_b64encode(f"{hash_data}|{timestamp}".encode()).decode()
# #     return extension_code
#
#
# def verify_extension_code(extension_code):
#     """
#     验证延期码
#     :param extension_code: 延期码
#     :param secret_ID: 用户设备ID
#     :return: 是否有效，及剩余时间（秒）
#     """
#     try:
#         decoded_data = base64.urlsafe_b64decode(extension_code).decode()
#         hash_data, timestamp = decoded_data.split('|')
#         timestamp = int(timestamp)
#
#         # 校验时间戳是否过期
#         current_time = get_timestamp_from_network_time()
#         if current_time > timestamp:
#             return False, 0
#
#         # 校验延期码的哈希值
#         expected_data = f"{secret_ID}|{timestamp}|{SECRET_KEY}"
#         expected_hash = hashlib.sha256(expected_data.encode()).hexdigest()
#         if hash_data == expected_hash:
#             return True, timestamp - current_time
#
#         return False, 0
#     except Exception:
#         return False, 0
#
#
# # @activate_bp.route('/initialize_trial', methods=['GET'])
# def initialize_trial():
#     """初始化试用期"""
#     if not os.path.exists(TRIAL_FILE):
#         secret_ID = request.args.get("secret_ID", "default_device")  # 从请求中获取设备ID
#         extension_code = generate_extension_code(secret_ID)
#         with open(TRIAL_FILE, "w") as file:
#             json.dump({"extension_code": extension_code}, file)
#         return Response.SUCCESS("试用期已初始化")
#
#
def get_network_time():
    """获取网络时间"""
    try:
        response = requests.get("http://worldtimeapi.org/api/ip")
        response.raise_for_status()
        data = response.json()
        return data['datetime']
    except requests.RequestException:
        return None


def get_timestamp_from_network_time():
    """从网络时间获取当前时间戳"""
    network_time = get_network_time()
    if network_time:
        # 解析 datetime 字符串为 datetime 对象
        dt = datetime.strptime(network_time, "%Y-%m-%dT%H:%M:%S.%f%z")
        # 转换为时间戳（单位为秒）
        return int(dt.timestamp())
    return int(datetime.now().timestamp())
#
# print(generate_extension_code('zjh'))