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
    event = data.get('event')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    page = data.get('page', 1)  # 默认第1页
    page_size = data.get('page_size', 10)  # 默认每页10条
    sort_order = data.get('sort_order', 'desc')  # 默认降序排序

    # 获取数据库会话
    with db_instance.get_session() as session:

        query = session.query(SolderFlowRecord)

        if solder_code:
            query = query.filter(SolderFlowRecord.SolderCode == solder_code)
        if user_id and user_id != '':
            query = query.filter(SolderFlowRecord.UserID == user_id)
        if event:
            query = query.filter(SolderFlowRecord.Event == event)
        if start_date and end_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
            end_date = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
            query = query.filter(SolderFlowRecord.DateTime.between(start_date, end_date))
        if sort_order == 'asc':
            query = query.order_by(SolderFlowRecord.DateTime.asc())
        else:
            query = query.order_by(SolderFlowRecord.DateTime.desc())

        total = query.count()
        records = query.offset((page - 1) * page_size).limit(page_size).all()

        record_list = [
            {
                "id": record.id,
                "SolderCode": record.SolderCode,
                "UserID": record.UserID,
                "UserName": record.UserName,
                "Event": record.Event,
                "DateTime": record.DateTime.strftime("%Y-%m-%d %H:%M:%S")
            }
            for record in records
        ]

        return (Response.SUCCESS({
            "list": record_list,
            "total": total
        }))
