# from flask import request, Blueprint
#
# from db_connection import db_instance
# from model.user import User
# # from model.mysql_db_model import adminDO, session
# from util import md5_util
# from flask_jwt_extended import create_access_token
# from datetime import timedelta
# from util.Response import Response
#
#
# # 引入路由
# admin_blueprint = Blueprint("admin_blueprint", __name__, url_prefix="/admin")
# user_bp = Blueprint('user', __name__)
#
# @admin_blueprint.route("/login", methods=['POST'])
# def login():
#     data = request.get_json()
#     user_id = data.get('user_id')
#     password = data.get('password')
#     user_ic = data.get('user_ic')
#     if user_ic is None:
#         if user_id is None or password is None:
#             return Response.FAIL("账号或密码不能为空").to_dict()
#         input_string = f"{password}{md5_util.SECRET}"
#         password = md5_util.md5_hex(input_string)
#         mysqlAdminDO = db_instance.query(User).filter_by(UserID=user_id).first()
#     else:
#         mysqlAdminDO = db_instance.query(User).filter_by(UserID=user_ic).first()
#
#     print(mysqlAdminDO)
#     if mysqlAdminDO is None:
#         return Response.FAIL("用户不存在").to_dict()
#
#     mysql_password = mysqlAdminDO.admin_password
#     print(mysql_password)
#     if password != mysql_password:
#         return Response.FAIL("密码错误").to_dict()
#
#     if mysqlAdminDO.admin_status == 0:
#         return Response.FAIL("用户已被禁用").to_dict()
#
#     access_token = create_access_token(
#         identity=mysqlAdminDO.admin_phone,
#         expires_delta=timedelta(hours=168),
#         additional_claims={'adminid': mysqlAdminDO.admin_id}
#     )
#     access_token = f"Bearer {access_token}"
#     res_list = {"token": access_token}
#     return Response.SUCCESS(res_list).to_dict()
