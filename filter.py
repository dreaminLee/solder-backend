import logging

from flask_jwt_extended import JWTManager, get_jwt_identity, verify_jwt_in_request, get_jwt
from flask import Flask, g, request

from login.login import admin_blueprint
from util.Response import Response
import datetime

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# jwt 配置
app.config['JWT_SECRET_KEY'] = 'test'  # 更改为你的密钥
jwt = JWTManager(app)

# 用户登录路由
app.register_blueprint(admin_blueprint)

"""
拦截器，所有请求先经过这里，可以获取请求头token进行拦截
"""
# 免过滤接口，这里写的是不需要经过jwt token验证的接口，如登录接口或者其他免登接口
exclude_path_patterns_list = [
    "/ssss"
]


@app.before_request
def my_before_request():
    # 获取路径
    url = request.path
    now_time = datetime.datetime.now()
    logging.info(f"{now_time}:访问接口：{url}")
    if url in exclude_path_patterns_list:
        return
    try:
        # JWT 验证成功，解析 JWT 中的内容
        verify_jwt_in_request()
        # 在这里你可以根据 claims 做一些额外的处理
        user_identity = get_jwt_identity()
        msg = get_jwt()
        # 获取保存在token里的东西
        adminId = msg.get('adminid')
        # 将获取到的信息保存到全局上下文中
        setattr(g, "adminId", adminId)
        setattr(g, "adminPhone", user_identity)
    except Exception as e:
        # 如果JWT验证失败，返回错误信息
        return Response.LOGIN_OUT(e.__str__()).to_dict()


"""
上下文对象，可以保存全局变量
"""


@app.context_processor
def my_context_processor():
    return {"adminId": g.adminId, "adminPhone": g.adminPhone}
