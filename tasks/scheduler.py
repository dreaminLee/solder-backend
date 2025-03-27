import os
import re
import time
from datetime import datetime, timedelta, timezone
import logging

from collections import defaultdict

import pytz
from apscheduler.executors.pool import ThreadPoolExecutor
from flask_apscheduler import APScheduler
from sqlalchemy import or_

from modbus.client import modbus_client
from modbus.scan import scan
from models import Station, Solder, SolderModel, SolderFlowRecord, User, Alarm
from util.MES_request import schedule_get_token, send_freeze_log, send_reheat_log, send_mix_log
from util.db_connection import db_instance
from util.logger import logger

from .task_heartbeat import task_heartbeat
from .conditions import *
from .tasks_movement import *
from .misc import read_mode

# 设置 APScheduler 日志级别为 WARNING
logging.getLogger('apscheduler').setLevel(logging.WARNING)


# 初始化调度器
scheduler = APScheduler()


def main_loop():
    if read_mode() == 1:
        if condition_in_area_to_cold_area():
            task_move_in_area_to_cold_area()
        elif condition_cold_area_to_rewarm_area():
            task_move_cold_area_to_rewarm_area()
        elif condition_go_back_cold_area():
            # 判断锡膏是在回温区还是在待取区
            task_move_rewarm_area_to_cold_area()
            task_move_ready_area_to_cold_area()
        elif condition_rewarm_area_to_ready_area():
            task_move_rewarm_area_to_ready_area()
        elif condition_to_be_stirred_out():
            task_move_out_from_rewarm_area()
        elif condition_already_stirred_out():
            task_move_out_from_ready_area()
    else:
        if condition_cold_mode():
            # 判断锡膏是在回温区还是在待取区
            task_move_rewarm_area_to_cold_area()
            task_move_ready_area_to_cold_area()


# 初始化调度器
def init_scheduler(app):
    scheduler.init_app(app)
    scheduler.add_job(id='task_heartbeat', func=task_heartbeat, trigger="interval", seconds=1, max_instances=1)
    scheduler.add_job(id='main_loop', func=main_loop, trigger="interval", seconds=1,  max_instances=1)
    if not scheduler.running:
        scheduler.start()
