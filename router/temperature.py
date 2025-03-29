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
clear_lock = threading.Lock()

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
# 全局变量
expire_days=30
clear_expired_event = threading.Event()

# 添加清除过期温度数据的函数
def clear_expired_temperature_records():
    try:
        # 计算过期日期
        from datetime import datetime, timedelta
        expire_date = datetime.now() - timedelta(days=expire_days)

        # 创建数据库会话
        session = db_instance.get_session()

        # 查询过期的记录
        records = session.query(TemperatureRecord).filter(
            TemperatureRecord.DateTime < expire_date
        ).all()

        # 删除记录
        for record in records:
            session.delete(record)

        # 提交事务
        with clear_lock:
            session.commit()
            session.close()
            print(f"Deleted {len(records)} expired temperature records.")
    except Exception as e:
        session.rollback()  # 回滚事务
        print(f"Error clearing expired temperature records: {str(e)}")



# 定义一个函数来定期调用插入数据
def periodic_insertion():
    while True:
        # print(f'==========={datetime.now()}==========')
        # 提交插入数据的任务到线程池
        # executor.submit(insert_temperature_data)
        insert_temperature_data()
        # print(f'==========={datetime.now()}=================')
        sleep(int(modbus_client.read_float(1502)))  # 每x秒执行一次

# 定义一个函数来定期调用清除数据
def periodic_clear():
    while True:
        if clear_expired_event.is_set():
            print("Stopping thread due to clear_expired_event.")
            break
        clear_expired_temperature_records()
        sleep(9000)  # 每2.5h执行一次

import threading

# 全局变量与锁
periodic_insertion_thread = None
clear_expired_thread = None

def start_periodic_insertion():
    global periodic_insertion_thread
    # 确保只启动一个线程
    if periodic_insertion_thread is None or not periodic_insertion_thread.is_alive():  # 如果线程未运行
        periodic_insertion_thread = threading.Thread(target=periodic_insertion)
        periodic_insertion_thread.daemon = True  # 设置为守护线程，确保程序退出时自动停止
        periodic_insertion_thread.start()

def start_periodic_clear():
    global clear_expired_thread
    # 确保只启动一个线程
    if clear_expired_thread is None or not clear_expired_thread.is_alive():  # 如果线程未运行
        clear_expired_thread = threading.Thread(target=periodic_clear)
        clear_expired_thread.daemon = True  # 设置为守护线程，确保程序退出时自动停止
        clear_expired_thread.start()

# 新增接口供前端调用输入设置数据过期的天数
@temperature_bp.route('/set_expiration_days', methods=['POST'])
def set_expiration_days():
    # 获取请求数据
    data = request.get_json()
    expire_days_str = data.get('expire_days')

    if not expire_days_str:
        return Response.FAIL("Missing expire_days")

    try:
        # 转换过期天数字符串为整数
        global expire_days #使用全局变量
        original_expire_days = expire_days
        expire_days = int(expire_days_str)
    except ValueError:
        return Response.FAIL("Invalid expire_days format. Please use an integer.")

    # 停止之前启动的清除过期数据的线程
    global clear_expired_thread
    if clear_expired_thread is not None and clear_expired_thread.is_alive():
        clear_expired_event.set()  # 设置事件标志以停止线程
        clear_expired_thread.join(timeout=1)  # 尝试停止线程
        clear_expired_event.clear()  # 清除事件标志以允许重新启动线程
        clear_expired_thread = None

    # 启动新的清除过期数据的线程
    start_periodic_clear()
    return Response.SUCCESS(f"Expiration days updated from {original_expire_days} to {expire_days}.")#返回成功响应

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
