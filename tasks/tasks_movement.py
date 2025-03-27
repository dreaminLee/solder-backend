from time import sleep
from datetime import datetime
from functools import partial

from util.db_connection import db_instance
from models import Solder, SolderFlowRecord, User
from modbus.client import modbus_client
from modbus.scan import scan
from util.logger import task_movement_logger
from .misc import barcode_file_path
from consts import *


def confirm_robot_action(from_area, to_area, confirm_action):
    """
    确认机械臂动作
    :param from_num: 取点位
    :param to_num: 放点位
    """
    action_complete = modbus_client.modbus_read("jcq", MADDR_ROBOT_STATUS_ACT, 1) == confirm_action
    while not action_complete:
        sleep(ROBOT_ACTING_WAIT_TIME)
        action_complete = modbus_client.modbus_read("jcq", MADDR_ROBOT_STATUS_ACT, 1) == confirm_action
    modbus_client.modbus_write("jcq",      from_area, MADDR_ROBOT_STATUS_GET_COMFIRM, 1)
    modbus_client.modbus_write("jcq",        to_area, MADDR_ROBOT_STATUS_PUT_COMFIRM, 1)
    modbus_client.modbus_write("jcq", confirm_action, MADDR_ROBOT_STATUS_ACT_COMFIRM, 1)


confirm_robot_get_complete = partial(confirm_robot_action, confirm_action=2)
confirm_robot_put_complete = partial(confirm_robot_action, confirm_action=4)
confirm_user_get_complete  = partial(confirm_robot_action, confirm_action=5)


def task_move_in_area_to_cold_area(cold_area_empty: int):
    """
    入库：从入柜区到冷藏区
    :param cold_area_empty: 当前未放置锡膏的冷藏区点位
    """

    def barcode_check(barcode):
        condition_1 = barcode.count("+") >= 5

        return condition_1

    def get_current_user() -> int:
        user_cache_file = "user_cache.txt"
        with open(user_cache_file, "r", encoding="utf-8") as f:
            id_str = f.read()
            return int(id_str) if len(id_str) else 0

    modbus_client.modbus_write("jcq", 1, cold_area_empty, 1) # 机械臂开始移动锡膏
    retry = 0
    max_reties = 3
    barcode = ""
    # 开始扫码流程，重试3次
    while True:
        if retry == max_reties:
            return

        req_scan = modbus_client.modbus_read("jcq", MADDR_BARCODE_SCAN_REQ, 1)[0]
        location = modbus_client.modbus_read("jcq", MADDR_BARCODE_SCAN_GET, 1)[0]
        if not req_scan:
            sleep(ROBOT_ACTING_WAIT_TIME)
            continue

        barcode = scan()
        with open(barcode_file_path, "w") as barcode_file:
            barcode_file.write(barcode)
        task_movement_logger.info(f"scanned: {barcode}")
        if not barcode_check(barcode):
            modbus_client.modbus_write("jcq", location, MADDR_BARCODE_SCAN_GET_COMFIRM, 1)
            modbus_client.modbus_write("jcq",        2, MADDR_BARCODE_SCAN_RET, 1)
            retry += 1
            continue
        else:
            modbus_client.modbus_write("jcq", location, MADDR_BARCODE_SCAN_GET_COMFIRM, 1)
            modbus_client.modbus_write("jcq",        1, MADDR_BARCODE_SCAN_RET, 1)
            break

    # 等待确认机械臂放完成并修改点位状态
    confirm_robot_put_complete(190, cold_area_empty)
    modbus_client.modbus_write("jcq", 0, cold_area_empty, 1)

def task_move_cold_area_to_rewarm_area(solder_to_move: Solder, rewarm_area_empty: int):
    """
    从冷藏区到回温区
    :param solder_to_move: 待移动的锡膏
    :param rewarm_area_empty: 当前未放置锡膏的回温区点位
    """
    cold_area_from = solder_to_move.StationID
    # 修改点位状态、等待机械臂取放完成、再次修改点位状态
    modbus_client.modbus_write("jcq", 2,    cold_area_from, 1)
    modbus_client.modbus_write("jcq", 1, rewarm_area_empty, 1)
    confirm_robot_get_complete(cold_area_from, rewarm_area_empty)
    confirm_robot_put_complete(cold_area_from, rewarm_area_empty)
    modbus_client.modbus_write("jcq", 0,    cold_area_from, 1)
    modbus_client.modbus_write("jcq", 0, rewarm_area_empty, 1)
    
    # 修改锡膏记录
    # TODO


def task_move_rewarm_area_to_cold_area(solder_to_move: Solder, cold_area_empty: int):
    """
    从回温区到冷藏区
    :param solder_to_move: 待移动的锡膏
    :param cold_area_empty: 当前未放置锡膏的冷藏区点位
    """
    rewarm_area_from = solder_to_move.StationID
    # 修改点位状态并等待机械臂取放完成
    modbus_client.modbus_write("jcq", 5, rewarm_area_from, 1)
    modbus_client.modbus_write("jcq", 1,  cold_area_empty, 1)
    confirm_robot_get_complete(rewarm_area_from, cold_area_empty)
    confirm_robot_put_complete(rewarm_area_from, cold_area_empty)
    modbus_client.modbus_write("jcq", 0, rewarm_area_from, 1)
    modbus_client.modbus_write("jcq", 0,  cold_area_empty, 1)

    # 修改锡膏记录
    # TODO


def task_move_rewarm_area_to_ready_area(solder_to_move: Solder, ready_area_empty: int):
    """
    从回温区到待取区（自动搅拌，流程中需要搅拌）
    :param solder_to_move: 待移动的锡膏
    :param ready_area_empty: 当前未放置锡膏的待取区点位
    """
    rewarm_area_from = solder_to_move.StationID
    # 修改点位状态并等待机械臂取放完成
    modbus_client.modbus_write("jcq", 2, rewarm_area_from, 1)
    modbus_client.modbus_write("jcq", 1, ready_area_empty, 1)
    confirm_robot_get_complete(rewarm_area_from, ready_area_empty)
    confirm_robot_put_complete(rewarm_area_from, ready_area_empty)
    modbus_client.modbus_write("jcq", 0, rewarm_area_from, 1)
    modbus_client.modbus_write("jcq", 0, ready_area_empty, 1)

    # 修改锡膏记录
    # TODO


def task_move_ready_area_to_cold_area(solder_to_move: Solder, cold_area_empty: int):
    """
    从待取区到冷藏区
    :param solder_to_move: 待移动的锡膏
    :param cold_area_empty: 当前未放置锡膏的冷藏区点位
    """
    ready_area_from = solder_to_move.StationID
    # 修改点位状态并等待机械臂取放完成
    modbus_client.modbus_write("jcq", 5, ready_area_from, 1)
    modbus_client.modbus_write("jcq", 1, cold_area_empty, 1)
    confirm_robot_get_complete(ready_area_from, cold_area_empty)
    confirm_robot_put_complete(ready_area_from, cold_area_empty)
    modbus_client.modbus_write("jcq", 0, ready_area_from, 1)
    modbus_client.modbus_write("jcq", 0, cold_area_empty, 1)

    # 修改锡膏记录
    # TODO


def task_move_out_from_rewarm_area(solder_to_move: Solder):
    """
    从回温区出库（出库搅拌）
    :param solder_to_move: 待移动的锡膏
    """
    rewarm_area_from = solder_to_move.StationID
    modbus_client.modbus_write("jcq", 22, rewarm_area_from, 1)
    confirm_robot_get_complete(rewarm_area_from, 0)
    confirm_user_get_complete(rewarm_area_from, 0)
    modbus_client.modbus_write("jcq", 0, rewarm_area_from, 1)

    # 修改锡膏记录
    # TODO


def task_move_out_from_ready_area(solder_to_move: Solder):
    """
    从待取区出库（自动搅拌，此时已搅拌过）
    :param solder_to_move: 待移动的锡膏
    """
    ready_area_from = solder_to_move.StationID
    modbus_client.modbus_write("jcq", 2, ready_area_from, 1)
    confirm_robot_get_complete(ready_area_from, 0)
    confirm_user_get_complete(ready_area_from, 0)
    modbus_client.modbus_write("jcq", 0, ready_area_from, 1)

    # 修改锡膏记录
    # TODO
