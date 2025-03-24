import random
from datetime import datetime
from time import sleep
from concurrent.futures import ThreadPoolExecutor
from flask import request, Blueprint
from sqlalchemy import and_, DateTime

from modbus.client import modbus_client
from util.db_connection import db_instance
from models import TemperatureRecord
from util.Response import Response
from util.thread_pool import executor

temperature_bp = Blueprint('temperature', __name__)


import threading

insert_lock = threading.Lock()

def insert_temperature_data():
    try:
        # 创建随机温度数据
        ReTemper = round(modbus_client.read_float(706),2)
        ColdTemperS = round(modbus_client.read_float(700), 2)
        ColdTemperM = round(modbus_client.read_float(702), 2)
        ColdTemperD = round(modbus_client.read_float(704), 2)
        DateTime = datetime.now()

        # 将数据插入到数据库
        session = db_instance.get_session()
        new_record = TemperatureRecord(
            ReTemper=ReTemper,
            ColdTemperS=ColdTemperS,
            ColdTemperM=ColdTemperM,
            ColdTemperD=ColdTemperD,
            DateTime=DateTime
        )

        # 确保每次只有一个线程能够插入数据
        with insert_lock:
            session.add(new_record)
            session.commit()
            session.close()
            # print(f"Inserted: {new_record}")
    except Exception as e:
        print(f"Error inserting temperature record: {str(e)}")


# 定义一个函数来定期调用插入数据
def periodic_insertion():
    while True:
        # print(f'==========={datetime.now()}==========')
        # 提交插入数据的任务到线程池
        # executor.submit(insert_temperature_data)
        insert_temperature_data()
        # print(f'==========={datetime.now()}=================')
        sleep(int(modbus_client.read_float(1502)))  # 每x秒执行一次

import threading

periodic_insertion_thread = None


def start_periodic_insertion():
    global periodic_insertion_thread
    # 确保只启动一个线程
    if periodic_insertion_thread is None or not periodic_insertion_thread.is_alive():  # 如果线程未运行
        periodic_insertion_thread = threading.Thread(target=periodic_insertion)
        periodic_insertion_thread.daemon = True  # 设置为守护线程，确保程序退出时自动停止
        periodic_insertion_thread.start()


# 获取温度记录的接口
@temperature_bp.route('/get_temperature_records', methods=['POST'])
def get_temperature_records():
    # 获取请求数据
    data = request.get_json()
    start_date_str = data.get('start_date')
    end_date_str = data.get('end_date')
    page = data.get('page', 1)  # 默认第1页
    page_size = data.get('page_size', 10)  # 默认每页10条

    if not start_date_str or not end_date_str:
        return Response.FAIL("Missing start_date or end_date")

    try:
        # 转换日期字符串为 datetime 对象
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    except ValueError:
        return Response.FAIL("Invalid date format. Please use YYYY-MM-DD.")

    # 创建数据库会话
    session = db_instance.get_session()

    try:
        # 构建基础查询
        query = session.query(TemperatureRecord).filter(
            and_(
                TemperatureRecord.DateTime >= start_date,
                TemperatureRecord.DateTime <= end_date
            )
        )


        # 获取总记录数
        total = query.count()

        # 使用分页获取记录
        records = query.offset((page - 1) * page_size).limit(page_size).all()

        # 如果没有找到记录
        if not records:
            return Response.SUCCESS(data={
                "list": [],
                "total": 0
            })

        # 将记录数据格式化为返回数据
        records_data = [
            {
                "id": record.id,
                "ReTemper": record.ReTemper,
                "ColdTemperS": record.ColdTemperS,
                "ColdTemperM": record.ColdTemperM,
                "ColdTemperD": record.ColdTemperD,
                "DateTime": record.DateTime.strftime("%Y-%m-%d %H:%M:%S")
            }
            for record in records
        ]

        return Response.SUCCESS(data={
            "list": records_data,
            "total": total
        })

    except Exception as e:
        session.rollback()  # 回滚事务
        return Response.FAIL(str(e))

    finally:
        session.close()  # 关闭会话
