# import json
# from random import uniform, randint
#
# from flask import Flask, request, jsonify
# from sqlalchemy.orm import sessionmaker
# from sqlalchemy import create_engine
# from flask_jwt_extended import create_access_token, JWTManager, jwt_required, get_jwt_identity
# from datetime import timedelta, datetime
# import time
# from models import User
# from util import md5_util  # 假设 md5_util 和 Response 工具类定义在 utils 模块中
# from util.Response import Response
#
# # 初始化 Flask 应用
# app = Flask(__name__)
#
# # 配置 JWT 密钥
# SECRET_KEY = "your_secret_key"
# app.config['JWT_SECRET_KEY'] = SECRET_KEY
# jwt = JWTManager(app)
# # 配置数据库连接
# HOSTNAME = "127.0.0.1"
# # mysql端口号
# PORT = "3306"
# USERNAME = "root"
# PASSWORD = "123456"
# DATABASE = "solder"
# DATABASE_URL = f'mysql+pymysql://{USERNAME}:{PASSWORD}@{HOSTNAME}:{PORT}/{DATABASE}?charset=utf8mb4'
# engine = create_engine(DATABASE_URL, echo=True)
# Session = sessionmaker(bind=engine)
# session = Session()
#
# # 配置加密密钥
# SECRET = "your_secret_salt"
#
# @app.route('/login', methods=['POST'])
# def login():
#     # 获取请求中的 JSON 数据
#     data = request.get_json()
#     account = data.get('account')
#     password = data.get('password')
#
#     # 检查账户和密码是否为空
#     if not account or not password:
#         return jsonify(Response.FAIL("账号或密码不能为空").to_dict())
#
#     # 计算加密后的密码
#     input_string = f"{account}{password}{SECRET}"
#     encrypted_password = md5_util.md5_hex(input_string)
#
#     # 查询数据库中的用户信息
#     user = session.query(User).filter_by(UserID=account).first()
#
#     # 验证用户是否存在
#     if not user:
#         return jsonify(Response.FAIL("用户不存在").to_dict())
#
#     # 验证密码是否正确
#     if encrypted_password != user.Password:
#         return jsonify(Response.FAIL("密码错误").to_dict())
#
#     # 检查用户状态
#     # if user.admin_status == 0:
#     #     return jsonify(Response.FAIL("用户已被禁用").to_dict())
#
#     # 生成 JWT Token
#     access_token = create_access_token(
#         identity=user.UserID,
#         expires_delta=timedelta(minutes=60),
#         additional_claims={'UserGrade': user.UserGrade}
#     )
#     access_token = f"Bearer {access_token}"
#     res_list = {"token": access_token}
#
#     # 返回成功响应
#     return jsonify(Response.SUCCESS(res_list).to_dict())
#
# # 返回用户信息接口
# @app.route('/user_info', methods=['GET'])
# @jwt_required()  # 装饰器验证 JWT token 是否有效
# def user_info():
#     try:
#         # 获取当前用户的身份（UserID）
#         user_id = get_jwt_identity()
#
#         # 查询数据库中的用户信息
#         user = session.query(User).filter_by(UserID=user_id).first()
#
#         if not user:
#             return jsonify(Response.FAIL("用户不存在").to_dict())
#
#         # 返回用户信息
#         user_data = {
#             'UserID': user.UserID,
#             'UserName': user.UserName,
#             'UserGrade': user.UserGrade
#         }
#
#         return jsonify(Response.SUCCESS(user_data).to_dict())
#
#     except Exception as e:
#         # 如果 JWT 过期或验证失败，返回登录失效信息
#         return jsonify(Response.LOGIN_OUT().to_dict())
#
# # SSE 数据流生成器
# @app.route('/stream')
# def stream():
#     # 数据生成器，向客户端不断发送数据
#     def generate_data():
#         while True:
#             yield f"data: 当前时间是 {datetime.now()}\n\n"
#             time.sleep(1)  # 模拟实时数据推送的间隔
#
#     from flask import Response
#     # 修复后的 Response
#     return Response(generate_data(), mimetype='text/event-stream')  # 使用 mimetype 代替 content_type
#
# # SSE 数据流生成器
# @app.route('/capaStream')
# def stream():
#     def generate_capa_data():
#         while True:
#             capacity_data = {
#                 "冷藏容量": {
#                     "总容量": randint(500, 600),
#                     "当前数量": randint(0, 500)
#                 },
#                 "回温容量": {
#                     "总容量": randint(200, 300),
#                     "当前数量": randint(0, 200)
#                 },
#                 "待取容量": {
#                     "总容量": randint(100, 150),
#                     "当前数量": randint(0, 100)
#                 },
#                 "回温代取容量": {
#                     "总容量": randint(50, 100),
#                     "当前数量": randint(0, 50)
#                 },
#                 "异常容量": {
#                     "总容量": randint(10, 20),
#                     "当前数量": randint(0, 10)
#                 }
#             }
#             # 将数据转换为 JSON 字符串并发送
#             yield f"data: {json.dumps(capacity_data)}\n\n"
#             time.sleep(1)  # 模拟 1 秒的间隔
#
#     from flask import Response
#     # 修复后的 Response
#     return Response(generate_capa_data(), mimetype='text/event-stream')  # 使用 mimetype 代替 content_type
#
# @app.route('/tempStream')
# def stream():
#     # 数据生成器，向客户端不断发送数据
#     def generate_temp_data():
#         while True:
#             # 模拟数据
#             data = {
#                 "冰柜温度": [round(uniform(-20.0, 0.0), 2) for _ in range(5)],  # 生成随机温度列表
#                 "回温区": round(uniform(0.0, 10.0), 2),  # 生成随机回温区值
#                 "气压": round(uniform(980.0, 1050.0), 2)  # 生成随机气压值
#             }
#             # 将数据转换为 JSON 字符串并发送
#             yield f"data: {json.dumps(data)}\n\n"
#             time.sleep(1)  # 模拟 1 秒的延迟
#
#     from flask import Response
#     # 修复后的 Response
#     return Response(generate_temp_data(), mimetype='text/event-stream')  # 使用 mimetype 代替 content_type