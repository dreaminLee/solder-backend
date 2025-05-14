from datetime import datetime
import logging
import traceback
import functools

from flask_apscheduler import APScheduler
from time import sleep

from modbus.client import modbus_client
from modbus.modbus_addresses import ADDR_ROBOT_STATUS
from util.logger import logger

from .task_heartbeat import task_heartbeat
from .task_freeze import task_freeze
from .task_scan import task_scan
from .task_robot import task_robot
from .task_update import task_update
from .task_monitor import task_monitor

# 设置 APScheduler 日志级别为 WARNING
logging.getLogger("apscheduler").setLevel(logging.WARNING)


# 初始化调度器
scheduler = APScheduler()
# 本地文件路径
file_path = "res_asc.txt"


def read_mode():
    """
    从本地文件 mode.txt 中读取模式
    :return: 返回模式的整数（0 或 1）
    """
    try:
        with open("mode.txt", "r") as file:
            mode = file.read().strip()
            return int(mode) if mode in ["0", "1"] else 0  # 默认返回 0
    except FileNotFoundError:
        return -1  # 如果文件不存在，默认返回 -1


def task_main():
    mode = read_mode()
    if mode == 0:
        task_robot()
        task_freeze()
    elif mode == 1:
        task_scan()
        task_robot()
        if not modbus_client.modbus_read("jcq", ADDR_ROBOT_STATUS.ACT, 1)[0]:
            task_update()


def infinite_loop(func, interval=1):
    def loop():
        while True:
            sleep(interval)
            try:
                func()
            except Exception as exc:
                logger.error(traceback.format_exc())

    return loop


def init_scheduler(app):
    scheduler.init_app(app)
    scheduler.add_job(
        id="task_heartbeat",
        func=infinite_loop(task_heartbeat),
        trigger="date",
        next_run_time=datetime.now(),
    )
    scheduler.add_job(
        id="task_main",
        func=infinite_loop(task_main),
        trigger="date",
        next_run_time=datetime.now(),
    )
    scheduler.add_job(
        id="task_monitor",
        func=infinite_loop(task_monitor, 0.5),
        trigger="date",
        next_run_time=datetime.now(),
    )
    if not scheduler.running:
        # 确保调度器正在运行，如果不是可以重启调度器或处理该情况
        scheduler.start()
