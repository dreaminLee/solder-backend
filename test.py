from modbus.client import modbus_client
from models import SolderModel, Solder
from tasks.scheduler import file_path
from util.db_connection import db_instance
from sqlalchemy import or_
session = db_instance.get_session()
# 查询 Solder 表中 StationID 在 601 到 660 或 801 到 840 之间的数据
# solder_records = session.query(Solder).filter(
#     or_(
#         Solder.StationID.between(601, 660),
#         Solder.StationID.between(801, 840)
#     )
# ).all()
# session.close()
# # 遍历查询结果并执行操作
# for solder in solder_records:
#     # modbus_client.modbus_write('jcq', 5, int(solder.StationID), 1)
#     print(modbus_client.modbus_read("jcq",int(solder.StationID),1))
# coil_status = modbus_client.read_float_test(2000,6079)

# for station_id in range(201, 539):  # 范围 601 到 660
#     modbus_client.modbus_write("jcq", 0, station_id, 1)
coil_status = modbus_client.modbus_read('jcq',601,32)
print(coil_status)
print(f"============{modbus_client.read_float(1540)}=========================")
# for station_id in range(601, 661):
#     modbus_client.modbus_write('jcq',0,station_id,1)
# coil_status = modbus_client.modbus_read('jcq',601,32)
# import re
#
# def check_string(s):
#     # 条件 1: 位置 4-9 为六位数字
#     condition_1 = bool(re.match(r".{3}(\d{6})", s))  # 匹配位置 4-9 为六位数字
#
#     # 条件 2: 位置 10-14 为五位数字
#     condition_2 = bool(re.match(r".{9}(\d{5})", s))  # 匹配位置 10-14 为五位数字
#
#     # 条件 3: 存在 3 个 “&” 符号
#     condition_3 = s.count("&") == 3  # 检查是否存在 3 个 & 符号
#
#     # 条件 4: 第 15 位是符号 "&"
#     condition_4 = len(s) >= 15 and s[14] == "&"  # 检查第 15 位是否为 "&"
#
#     # 返回是否符合所有条件
#     return condition_1 and condition_2 and condition_3 and condition_4
#
# # 示例字符串
# s = "RLT25011700039&RLT.NRK0307&1&"
#
# # 调用函数进行检查
# result = check_string(s)
# print("String meets all conditions:", result)



# res_asc="RLT25011500010&RLT.WTOLF2000T&1&"
# parts = res_asc.split('&')
# model = parts[1] if len(parts) > 1 else None
# session = db_instance.get_session()
# solder_model_dict = {
#         model_data.Model: model_data
#         for model_data in session.query(SolderModel).all()
#     }
#
# print(solder_model_dict)

#
# import requests
# import json
# import os
#
#
# # 配置目标 URL 和请求头
# headers = {
#     "Content-Type": "application/json;charset=UTF-8"
# }
#
# # 存储 token 的文件路径
# TOKEN_FILE_PATH = "token.json"
#
# # 登录函数
# def login(user_login, password):
#     url = "http://192.168.1.8:8090/emes/api/Auth/login"
#     data = {
#         "UserLogin": user_login,
#         "Password": password
#     }
#
#     try:
#         # 使用 POST 方法发送请求
#         response = requests.post(url, headers=headers, json=data)
#
#         # 输出返回信息
#         if response.status_code == 200:
#             print("Login Successful!")
#             # 获取返回的 JSON 响应
#             login_data = response.json()
#             # 获取 token 和过期时间
#             token = login_data.get("Data", {}).get("token")
#             expiration = login_data.get("Data", {}).get("expiration")
#             # 将 token 存储到文件
#             if token:
#                 save_token(token, expiration)
#                 return token
#             else:
#                 print("Token not found in response!")
#                 return None
#         else:
#             print(f"Login Failed with status code {response.status_code}")
#             return None
#     except requests.exceptions.RequestException as e:
#         print("Login Request failed:", e)
#     except json.JSONDecodeError as e:
#         print("Failed to decode JSON response:", e)
#
#
# # 保存 token 到文件
# def save_token(token, expiration):
#     data = {
#         "token": token,
#         "expiration": expiration
#     }
#     with open(TOKEN_FILE_PATH, "w") as file:
#         json.dump(data, file)
#     print("Token saved successfully!")
#
#
# # 从文件加载 token
# def load_token():
#     if os.path.exists(TOKEN_FILE_PATH):
#         with open(TOKEN_FILE_PATH, "r") as file:
#             data = json.load(file)
#             return data.get("token"), data.get("expiration")
#     return None, None
#
#
# # 发送日志的函数
# def send_log(rid, opt_code, user_login):
#     # 从文件加载 token
#     token, _ = load_token()
#
#     if not token:
#         print("Token not found! Please obtain token first.")
#         return
#
#     # 设置请求头，携带 Bearer Token
#     headers = {
#         "Content-Type": "application/json;charset=UTF-8",
#         "Authorization": f"Bearer {token}"  # Bearer Token
#     }
#
#     url = "http://192.168.1.8:8090/emes/api/SolderManageAuth/AddSolderOptLog"
#     data = {
#         "RID": rid,  # 锡膏条码
#         "OPT_CODE": opt_code,  # 操作码
#         "USERLOGIN": user_login  # 人工工号
#     }
#
#     try:
#         # 使用 POST 方法发送请求
#         response = requests.post(url, headers=headers, json=data)
#
#         # 输出返回信息
#         print("Response Status Code:", response.status_code)
#         print("Response Body:", response.json())  # 解析 JSON 响应
#     except requests.exceptions.RequestException as e:
#         print("Log Request failed:", e)
#     except json.JSONDecodeError as e:
#         print("Failed to decode JSON response:", e)
#
#
# # 示例调用
# if __name__ == "__main__":
#     # 执行登录并获取 token
#     token = login("LZ01", "123456")
#
#     if token:
#         # 登录成功后发送日志（可以根据需要调整日志数据）
#         send_log("RLT25011500007&RLT.WTO-LF2000T&1&", "018001", "LZ01")
