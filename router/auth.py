

import os
import json
from datetime import datetime
import base64
import hashlib

import requests
from flask import Blueprint, request

from util.AES_util import validate_certificate, CERTIFICATE_FILE
from util.Response import Response
# from util.activate_code import initialize_trial, verify_extension_code, generate_extension_code

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/check_trial', methods=['GET'])
def check_trial():
    """检查试用期"""
    if not os.path.exists(CERTIFICATE_FILE):
        return Response.FAIL("未激活")

    # secret_ID = request.args.get("secret_ID", "default_device")  # 从请求中获取设备ID
    with open(CERTIFICATE_FILE, "r") as file:
        extension_code = file.read()

    # extension_code = data.get("extension_code")
    if not extension_code:
        return Response.FAIL("试用期信息无效")

    is_valid, remaining_time = validate_certificate(extension_code)
    if not is_valid:
        return Response.FAIL("试用期已结束")

    return Response.SUCCESS(f"试用期剩余 {remaining_time} 秒")


@auth_bp.route('/extend_trial', methods=['POST'])
def extend_trial():
    """延长试用期"""
    # secret_ID = request.json.get("secret_ID")  # 从请求中获取设备ID
    data = request.get_json()
    new_extension_code = data.get('new_extension_code')
    # if not os.path.exists(TRIAL_FILE):
    #     initialize_trial()
    # flag , remain_time=verify_extension_code(new_extension_code)
    flag,remainingtime = validate_certificate(new_extension_code)
    if flag:
        # 清空文件内容
        with open(CERTIFICATE_FILE, "w") as file:
            file.truncate(0)
        # 保存到文件
        with open(CERTIFICATE_FILE, "wb") as file:
            file.write(new_extension_code.encode("utf-8"))
        # with open(TRIAL_FILE, "r+") as file:
        #     data = json.load(file)
        #     # new_extension_code = generate_extension_code(secret_ID)  # 生成新的延期码
        #     data["extension_code"] = new_extension_code

        return Response.SUCCESS("试用期已延长")
    else:
        return Response.FAIL("激活码错误")