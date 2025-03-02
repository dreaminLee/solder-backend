from flask import Blueprint, request
from datetime import datetime

from util.db_connection import db_instance
from util.Response import Response
from models import SolderFlowRecord

solderflow_bp = Blueprint('solderflow', __name__)

# 获取锡膏记录
@solderflow_bp.route('/get_solder_flow_records', methods=['POST'])
def get_solder_flow_records():
    # 获取查询参数
    data = request.get_json()
    solder_code = data.get('solder_code')
    user_id = data.get('user_id')
    record_type = data.get('record_type')
    start_date  = data.get('start_date')
    end_date = data.get('end_date')
    # solder_code = request.args.get('solder_code')  # 锡膏码
    # user_id = request.args.get('user_id')  # 工号
    # record_type = request.args.get('type')  # 类型
    # start_date = request.args.get('start_date')  # 起始日期
    # end_date = request.args.get('end_date')  # 结束日期

    # 获取数据库会话
    session = db_instance.get_session()

    try:
        # 初始化查询
        query = session.query(SolderFlowRecord)

        # 如果有锡膏码，添加筛选条件
        if solder_code:
            query = query.filter(SolderFlowRecord.SolderCode == solder_code)

        # 如果有工号，添加筛选条件
        if user_id:
            query = query.filter(SolderFlowRecord.UserID == user_id)

        # 如果有类型，添加筛选条件
        if record_type:
            query = query.filter(SolderFlowRecord.Type == record_type)

        # 如果有日期区间，过滤记录
        if start_date and end_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d')
                end_date = datetime.strptime(end_date, '%Y-%m-%d')
                query = query.filter(SolderFlowRecord.DateTime.between(start_date, end_date))
            except ValueError:
                return (Response.FAIL("日期格式错误，正确格式为 YYYY-MM-DD"))

        # 获取记录
        records = query.all()

        # 如果没有记录
        if not records:
            return (Response.FAIL("没有符合条件的锡膏记录"))

        # 将查询结果转化为字典
        record_list = [
            {
                "id": record.id,
                "SolderCode": record.SolderCode,
                "UserID": record.UserID,
                "UserName": record.UserName,
                "Type": record.Type,
                "DateTime": record.DateTime.strftime("%Y-%m-%d %H:%M:%S")
            }
            for record in records
        ]

        # 返回成功的响应
        return (Response.SUCCESS(record_list))

    except Exception as e:
        # 出现异常时回滚并返回错误
        session.rollback()
        return (Response.FAIL(f"数据库查询错误: {str(e)}"))

    finally:
        # 关闭会话
        session.close()
