from flask import jsonify
from datetime import timedelta


class Response:
    def __init__(self, code, msg, data=None):
        self.code = code
        self.msg = msg
        self.data = data  # 添加data属性

    def __str__(self):
        # 修改__str__方法来包含data（如果存在）
        return f"{self.__class__.__name__}({self.code}, \"{self.msg}\", data={self.data})"

    @staticmethod
    def SUCCESS(data=None):
        """返回一个成功的响应实例，可以包含额外的数据"""
        return Response(0, "成功", data=data).to_dict()

    @staticmethod
    def FAIL(data=None):
        """返回一个失败的响应实例，允许自定义失败消息和包含额外的数据"""
        return Response(401, "失败", data=data).to_dict()

    @staticmethod
    def LOGIN_OUT(data=None):
        """返回一个失败的响应实例，允许自定义失败消息和包含额外的数据"""
        return Response(-1, "登录状态已失效", data=data)

    def to_dict(response):
        return {"code": response.code, "msg": response.msg, "data": response.data}