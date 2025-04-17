import requests
import json
import os
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# 缓存已发送的日志信息
sent_logs_cache = {}


# 发送日志的基础函数
def send_log(opt_code, rid, user_login):
    # 检查缓存中是否已经发送过相同的日志
    cache_key = f"{rid}_{opt_code}"
    if cache_key in sent_logs_cache:
        logger.info(f"Log with RID {rid} and OPT_CODE {opt_code} has already been sent recently.")
        return {"message": "Log already sent"}

    # 从文件加载 token
    token, _ = load_token()

    if not token:
        logger.error("Token not found! Please obtain token first.")
        return

    # 设置请求头，携带 Bearer Token
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Authorization": f"Bearer {token}"  # Bearer Token
    }

    url = "http://192.168.1.8:8090/emes/api/SolderManageAuth/AddSolderOptLog"

    data = {
        "RID": rid,  # 锡膏条码
        "OPT_CODE": opt_code,  # 操作码
        "USERLOGIN": user_login  # 人工工号
    }

    try:
        # 使用 POST 方法发送请求
        response = requests.post(url, headers=headers, json=data)

        # 输出返回信息
        if response.status_code == 200:
            # 缓存成功发送的日志
            sent_logs_cache[cache_key] = {
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "response": response.json()
            }
            logger.info(f"Log with RID {rid} and OPT_CODE {opt_code} sent successfully.")
        else:
            logger.error(f"Failed to send log with RID {rid} and OPT_CODE {opt_code}: {response.status_code}")

        return response.json()  # 直接返回响应的 JSON 内容
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        return {"error": str(e)}
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON response: {e}")
        return {"error": "Failed to decode JSON response"}


# 1. 冷冻操作
def send_freeze_log(rid, user_login):
    return send_log("018001", rid, 'LZ01')


# 2. 回温操作
def send_reheat_log(rid, user_login):
    return send_log("018002", rid, 'LZ01')


# 3. 领用操作
def send_take_log(rid, user_login):
    return send_log("018003", rid, 'LZ01')


# 4. 搅拌操作
def send_mix_log(rid, user_login):
    return send_log("018006", rid, 'LZ01')


# 配置目标 URL 和请求头
url = "http://192.168.1.8:8090/emes/api/Auth/login"
headers = {
    "Content-Type": "application/json;charset=UTF-8"
}

# 保存 token 到文件的路径
TOKEN_FILE_PATH = "token.json"


# 获取 token 的函数
def get_token():
    data = {
        "UserLogin": "LZ01",
        "Password": "123456"
    }

    try:
        # 使用 POST 方法发送请求
        response = requests.post(url, headers=headers, json=data)

        # 输出返回信息
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get("retCode") == "1":
                token = response_data["Data"].get("token")
                expiration = response_data["Data"].get("expiration")
                # 保存 token 和过期时间到文件
                save_token(token, expiration)
                logger.info("Token fetched successfully!")
                return token
            else:
                logger.error(f"Login failed: {response_data.get('Message')}")
        else:
            logger.error(f"Failed to login, status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON response: {e}")

    return None


# 保存 token 到文件
def save_token(token, expiration):
    with open(TOKEN_FILE_PATH, "w") as file:
        json.dump({"token": token, "expiration": expiration}, file)
    logger.info("Token saved to file.")


# 从文件加载 token
def load_token():
    if os.path.exists(TOKEN_FILE_PATH):
        with open(TOKEN_FILE_PATH, "r") as file:
            data = json.load(file)
            return data.get("token"), data.get("expiration")
    return None, None


# 定时任务：每天零点请求一次获取 token
def schedule_get_token():
    logger.info("Fetching token...")
    token = get_token()
    if token:
        logger.info("Token fetched and saved.")
    else:
        logger.error("Failed to fetch token.")


# 在程序启动时获取 token
def startup_get_token():
    logger.info("Fetching token on startup...")
    token = get_token()
    if token:
        logger.info("Token fetched and saved.")
    else:
        logger.error("Failed to fetch token.")
