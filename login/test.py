from flask import g

from util.Response import Response

"""
测试专用
"""


@bi.route('/ssss', methods=['GET'])
def get_test():
    adminId = g.get("adminId")
    adminPhone = g.get("adminPhone")
    res = Response.SUCCESS(f"{adminId},{adminPhone}")
    # 在这里可以拿到在拦截器中保存的用户信息
    print(res.to_dict())
    return res.to_dict()
