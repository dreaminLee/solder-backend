from contextlib import contextmanager
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token

from util.db_connection import db_instance
from face.collect import collect
from face.detect import detect
from face.train import train
from models import User
from util import md5_util
from util.Response import Response

user_bp = Blueprint('user', __name__)



@user_bp.route("/login", methods=['POST'])
def login():
    data = request.get_json()
    user_id = data.get('id')
    password = data.get('password')
    user_ic = data.get('user_ic')
    input_string = f"{password}{md5_util.SECRET}"
    password = md5_util.md5_hex(input_string)

    @contextmanager
    def session_scope():
        session = db_instance.get_session()  # 获取会话
        try:
            yield session
        finally:
            session.close()  # 自动释放连接

    # 使用时可以这样做：
    with session_scope() as session:
        if user_ic is None or user_ic == "":
            if user_id is None or password is None:
                return Response.FAIL("账号或密码不能为空")
            mysqlAdminDO = session.query(User).filter_by(UserID=user_id).first()
        else:
            mysqlAdminDO = session.query(User).filter_by(UserIC=user_ic).first()
    # print(user_ic)
    if mysqlAdminDO is None:
        return Response.FAIL("用户不存在")
    if user_ic is None:
        mysql_password = mysqlAdminDO.Password
        print(mysql_password)
        if password != mysql_password:
            return Response.FAIL("密码错误")

    access_token = create_access_token(
        identity=mysqlAdminDO.UserID,
        expires_delta=timedelta(hours=168),
        additional_claims={'user_id': mysqlAdminDO.UserID}
    )
    access_token = f"Bearer {access_token}"
    res_list = {"token": access_token}
    # 将 UserID 写入 user_cache.txt 文件
    user_cache_file = "user_cache.txt"
    # 清空文件内容
    with open(user_cache_file, "w") as file:
        file.truncate(0)
    with open(user_cache_file, 'a') as file:
        file.write(f"{mysqlAdminDO.UserID}\n")
    return Response.SUCCESS(res_list)


@user_bp.route('/user_info', methods=['GET'])
@jwt_required()
def user_info():
    session = db_instance.get_session()
    user_id = get_jwt_identity()
    user = session.query(User).filter_by(UserID=user_id).first()

    if not user:
        return Response.FAIL("用户不存在")

    user_data = {
        'UserID': user.UserID,
        'UserName': user.UserName,
        'UserGrade': user.UserGrade
    }
    return Response.SUCCESS(user_data)


@user_bp.route('/add_user', methods=['POST'])
def add_user():
    data = request.get_json()

    # 获取请求数据
    user_ic = data.get('user_ic')
    user_name = data.get('user_name')
    password = data.get('password')
    user_grade = data.get('user_grade')

    # 检查必填参数
    if not user_name or not password:
        return Response.FAIL("缺少必要的参数")

    # 获取数据库会话
    session = db_instance.get_session()
    try:
        # 添加新用户
        user = User(
            UserIC=user_ic,
            UserName=user_name,
            Password=md5_util.md5_hex(f"{password}{md5_util.SECRET}"),
            UserGrade=user_grade if user_grade else 0,
            updateAt=datetime.now(),
            createAt=datetime.now()
        )

        session.add(user)
        session.commit()

        return Response.SUCCESS("用户添加成功")
    except Exception as e:
        # 捕获异常并回滚
        session.rollback()
        return Response.FAIL("添加用户失败")
    finally:
        # 确保关闭会话
        session.close()


@user_bp.route('/edit_user', methods=['POST'])
def edit_user():
    data = request.get_json()

    # 获取请求数据
    user_id = data.get('user_id')
    user_ic = data.get('user_ic')
    user_name = data.get('user_name')
    password = data.get('password')
    user_grade = data.get('user_grade')
    # fingerprint1 = data.get('fingerprint1')
    # fingerprint2 = data.get('fingerprint2')
    # fingerprint3 = data.get('fingerprint3')

    # 检查必填参数
    if not user_id or not user_name or not password:
        return jsonify(Response.FAIL("缺少必要的参数"))

    session = db_instance.get_session()
    try:
        # 查找用户是否存在
        user = session.query(User).filter_by(UserID=user_id).first()

        if not user:
            return Response.FAIL("用户不存在")

        # 更新用户信息
        user.UserIC = user_ic
        user.UserName = user_name
        user.Password = md5_util.md5_hex(f"{password}{md5_util.SECRET}")
        user.UserGrade = user_grade if user_grade else 0
        user.updateAt = datetime.now()
        # user.Fingerprint1 = fingerprint1
        # user.Fingerprint2 = fingerprint2
        # user.Fingerprint3 = fingerprint3

        session.commit()
        return Response.SUCCESS("用户信息更新成功")
    except Exception as e:
        session.rollback()
        return Response.FAIL(f"更新用户信息失败: {e}")
    finally:
        session.close()


@user_bp.route('/delete_user', methods=['POST'])
def delete_user():
    data = request.get_json()
    user_id = data.get('user_id')

    if not user_id:
        return Response.FAIL("缺少用户ID参数")

    session = db_instance.get_session()
    try:
        user = session.query(User).filter_by(UserID=user_id).first()

        if not user:
            return Response.FAIL("用户不存在")

        session.delete(user)
        session.commit()
        return Response.SUCCESS("用户删除成功")
    except Exception as e:
        session.rollback()
        return Response.FAIL(f"删除用户失败: {e}")
    finally:
        session.close()


# 获取用户列表
@user_bp.route('/get_user_list', methods=['GET'])
def get_user_list():
    # 获取 session
    session = db_instance.get_session()

    try:
        # 查询所有用户
        users = session.query(User).all()

        # 如果没有找到记录
        if not users:
            return Response.FAIL("没有找到用户记录")

        # 返回用户列表
        user_list = [user.to_dict() for user in users]
        return Response.SUCCESS(user_list)
    except Exception as e:
        # 异常处理
        return Response.FAIL(f"查询用户列表时发生错误: {str(e)}")
    finally:
        # 确保关闭 session
        session.close()


@user_bp.route('/face_collect', methods=['POST'])
def face_collect():
    data = request.get_json()

    # 获取请求数据
    user_id = data.get('user_id')

    res = collect(user_id)
    train()
    return jsonify(Response.SUCCESS(res))


@user_bp.route('/face_detect', methods=['GET'])
def face_detect():
    user_id = detect()
    if user_id is not "UNKNOWN":
        mysqlAdminDO = db_instance.get_session().query(User).filter_by(UserID=user_id).first()
        access_token = create_access_token(
            identity=mysqlAdminDO.UserID,
            expires_delta=timedelta(hours=168),
            additional_claims={'user_id': mysqlAdminDO.UserID}
        )
        access_token = f"Bearer {access_token}"
        res_list = {"token": access_token, "user_id":user_id}
        # 将 UserID 写入 user_cache.txt 文件
        user_cache_file = "user_cache.txt"
        with open(user_cache_file, "w") as file:
            file.write(f"{mysqlAdminDO.UserID}\n")
        return Response.SUCCESS(res_list)
    else:
        return jsonify(Response.FAIL({"message": "识别失败"}))
