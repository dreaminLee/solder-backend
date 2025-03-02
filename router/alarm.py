from flask import Blueprint, request, jsonify
from sqlalchemy import and_
from util.db_connection import db_instance
from models import Alarm
from util.Response import Response
from datetime import datetime

alarm_bp = Blueprint('alarm', __name__)

# 获取数据库会话
session = db_instance.get_session()

# 增加一个报警信息
@alarm_bp.route('/add_alarm', methods=['POST'])
def add_alarm():
    data = request.get_json()
    alarm_text = data.get('alarm_text')
    datetime_str = data.get('datetime')

    if not alarm_text or not datetime_str:
        return jsonify(Response.FAIL("报警信息或时间不能为空"))

    # 解析日期时间
    try:
        alarm_datetime = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return jsonify(Response.FAIL("无效的日期时间格式"))

    # 创建 Alarm 实例
    new_alarm = Alarm(AlarmText=alarm_text, DateTime=alarm_datetime)

    # 向数据库添加报警信息
    session.add(new_alarm)
    session.commit()

    return jsonify(Response.SUCCESS({"message": "报警信息添加成功"}))

# 获取所有报警信息
@alarm_bp.route('/get_alarms', methods=['POST'])
def get_alarms():
    # 获取请求数据
    data = request.get_json()
    start_date_str = data.get('start_date')
    end_date_str = data.get('end_date')

    # 校验是否传递了日期
    if not start_date_str or not end_date_str:
        return Response.FAIL(jsonify({"error": "Missing start_date or end_date"}))

    try:
        # 将字符串日期转换为datetime对象
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    except ValueError:
        return Response.FAIL("Invalid date format. Please use YYYY-MM-DD.")

    # 初始化数据库会话
    try:

        # 查询指定日期范围内的报警记录
        alarms = session.query(Alarm).filter(
            and_(
                Alarm.DateTime >= start_date,
                Alarm.DateTime <= end_date
            )
        ).order_by(Alarm.ID.desc()).all()

        # 如果没有找到报警记录
        if not alarms:
            return Response.FAIL("No alarms found for the specified date range.")

        # 将结果转换为字典列表
        alarms_data = [
            {"ID": alarm.ID, "AlarmText": alarm.AlarmText, "DateTime": alarm.DateTime.strftime("%Y-%m-%d %H:%M:%S")}
            for alarm in alarms
        ]

        # 返回成功的响应
        return Response.SUCCESS(data=alarms_data)

    except Exception as e:
        # 捕获异常并回滚事务
        session.rollback()  # 出错时回滚事务
        return Response.FAIL(str(e))

    finally:
        # 关闭 session，确保资源得到释放
        session.close()

# 删除报警信息
@alarm_bp.route('/delete_alarm', methods=['DELETE'])
def delete_alarm():
    data = request.get_json()
    alarm_id = data.get('id')

    if not alarm_id:
        return jsonify(Response.FAIL("报警ID不能为空").to_dict())

    alarm = session.query(Alarm).filter_by(ID=alarm_id).first()

    if not alarm:
        return jsonify(Response.FAIL("未找到该报警信息"))

    session.delete(alarm)
    session.commit()

    return jsonify(Response.SUCCESS({"message": "报警信息删除成功"}))
