from flask import Blueprint, request, jsonify
from sqlalchemy import and_
from util.db_connection import db_instance
from models import Alarm
from util.Response import Response
from datetime import datetime
from flask import Blueprint, request, jsonify
from sqlalchemy import and_
from datetime import datetime
from dicts import alarm_dict  # 导入 alarm_dict 字典


alarm_bp = Blueprint('alarm', __name__)


# 增加一个报警信息
@alarm_bp.route('/add_alarm', methods=['POST'])
def add_alarm():
    with db_instance.get_session() as session:
        data = request.get_json()
        alarm_text = data.get('alarm_text')
        start_time_str = data.get('start_time')
        kind= "警告" if alarm_dict.get(alarm_text) == 729 else "报警"
        if not alarm_text or not start_time_str:
            return jsonify(Response.FAIL("报警信息或时间不能为空"))

        # 解析日期时间
        alarm_datetime = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")

        # 创建 Alarm 实例
        new_alarm = Alarm(AlarmText=alarm_text, StartTime=alarm_datetime,EndTime=None,Kind=kind)

        # 向数据库添加报警信息
        session.add(new_alarm)
        session.commit()

        return jsonify(Response.SUCCESS({"message": "报警信息添加成功"}))


# 获取所有报警信息，实现分页查询
@alarm_bp.route('/get_alarms', methods=['POST'])
def get_alarms():
    # 获取请求数据
    data = request.get_json()
    start_date_str = data.get('start_date')
    end_date_str = data.get('end_date') if data.get('end_date') else datetime.today()
    page = data.get('page')
    page_size = data.get('page_size')

    # 校验是否传递了日期
    if not start_date_str:
        return Response.FAIL(jsonify({"error": "Missing start_date or end_date"}))

    # 将字符串日期转换为datetime对象
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

    with db_instance.get_session() as session:
        # 计算偏移量
        offset = (page - 1) * page_size

        # 查询指定日期范围内的报警记录，并进行分页
        alarms_query = session.query(Alarm).filter(
            and_(
                Alarm.StartTime >= start_date,
                Alarm.StartTime <= end_date
            )
        ).order_by(Alarm.ID.desc())
        print("接收到的数据Received data:", alarms_query)
        # 获取总记录数
        total = alarms_query.count()

        # 获取当前页的数据
        alarms = alarms_query.offset(offset).limit(page_size).all()

        # 将结果转换为字典列表
        alarms_data = [
            {
                "ID": alarm.ID,
                "AlarmText": alarm.AlarmText,
                "StartTime": alarm.StartTime.strftime("%Y-%m-%d %H:%M:%S"),
                "EndTime": alarm.EndTime.strftime("%Y-%m-%d %H:%M:%S") if alarm.EndTime else None,
                "Kind": "警告" if alarm_dict.get(alarm.AlarmText) == 729 else "报警"
            }
            for alarm in alarms
        ]

        # 返回成功的响应
        return Response.SUCCESS(data={"alarms": alarms_data, "total": total})


# 删除报警信息
@alarm_bp.route('/delete_alarm', methods=['DELETE'])
def delete_alarm():
    with db_instance.get_session() as session:
        data = request.get_json()
        alarm_id = data.get('id')

        alarm = session.query(Alarm).filter_by(ID=alarm_id).first()

        session.delete(alarm)
        session.commit()

        return jsonify(Response.SUCCESS({"message": "报警信息删除成功"}))


# 清除所有报警信息
@alarm_bp.route('/clear_alarms', method=["POST"])
def clear_alarms():
    with db_instance.get_session() as session:
        num_of_rows_deleted = session.query(Alarm).delete()
        session.commit()
        return jsonify(Response.SUCCESS({"message": f"{num_of_rows_deleted}条报警信息已清空"}))
