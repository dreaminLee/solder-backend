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
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    page = data.get('page', 1)  # 默认第1页
    page_size = data.get('page_size', 10)  # 默认每页10条
    sort_order = data.get('sort_order', 'desc')  # 默认降序排序

    # 获取数据库会话
    session = db_instance.get_session()

    try:
        # 初始化查询
        query = session.query(SolderFlowRecord)

        # 如果有锡膏码，添加筛选条件
        if solder_code:
            query = query.filter(SolderFlowRecord.SolderCode == solder_code)

        # 如果有工号，添加筛选条件（空字符串或None时不添加筛选）
        if user_id and user_id != '':
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

        # 添加时间排序
        if sort_order == 'asc':
            query = query.order_by(SolderFlowRecord.DateTime.asc())
        else:
            query = query.order_by(SolderFlowRecord.DateTime.desc())

        # 获取总记录数
        total = query.count()

        # 使用分页获取记录
        records = query.offset((page - 1) * page_size).limit(page_size).all()

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

        # 返回成功的响应，包含分页信息
        return (Response.SUCCESS({
            "list": record_list,
            "total": total
        }))

    except Exception as e:
        # 出现异常时回滚并返回错误
        session.rollback()
        return (Response.FAIL(f"数据库查询错误: {str(e)}"))

    finally:
        # 关闭会话
        session.close()
