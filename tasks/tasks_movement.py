from time import sleep
from datetime import datetime
from functools import partial
from sqlalchemy import update, delete, insert

from util.db_connection import db_instance
from models import Solder, SolderFlowRecord, User, SolderModel
from modbus.client import modbus_client
from modbus.scan import scan
from util.logger import task_movement_logger
from .misc import barcode_file_path, get_current_user, area_id_to_move_id
from consts import *


def confirm_robot_action(from_area, to_area, confirm_action):
    """
    确认机械臂动作
    :param from_num: 取点位
    :param to_num: 放点位
    """
    move_id_from, move_id_to = area_id_to_move_id[from_area], area_id_to_move_id[to_area]
    action_complete = modbus_client.modbus_read("jcq", MADDR_ROBOT_STATUS_ACT, 1) == confirm_action
    while not action_complete:
        sleep(ROBOT_ACTING_WAIT_TIME)
        action_complete = modbus_client.modbus_read("jcq", MADDR_ROBOT_STATUS_ACT, 1) == confirm_action
    modbus_client.modbus_write("jcq",   move_id_from, MADDR_ROBOT_STATUS_GET_COMFIRM, 1)
    modbus_client.modbus_write("jcq",     move_id_to, MADDR_ROBOT_STATUS_PUT_COMFIRM, 1)
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

    modbus_client.modbus_write("jcq", 1, cold_area_empty, 1) # 机械臂开始移动锡膏
    retry = 0
    max_reties = 3
    barcode = ""
    # 开始扫码流程，重试3次
    while True:
        if retry == max_reties:
            modbus_client.modbus_write("jcq", 0, cold_area_empty, 1)
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
    confirm_robot_get_complete(190, cold_area_empty)
    confirm_robot_put_complete(190, cold_area_empty)
    modbus_client.modbus_write("jcq", 0, cold_area_empty, 1)

    parts = barcode.split('+')
    model = parts[4]
    product_date = parts[2]
    year, month, day = 2020 + int(product_date[0]), int(product_date[1:3]), int(product_date[3:5])
    product_date = datetime(year, month, day)

    current_user_id = get_current_user()
    current_time = datetime.now()
    with db_instance.get_session() as session:
        in_times = session.query (SolderFlowRecord
                         ).join  (Solder, Solder.SolderCode == SolderFlowRecord.SolderCode
                         ).filter(SolderFlowRecord.Type == "请求入柜"
                         ).count ()
        current_user_name = session.query(User).filter_by(UserID=current_user_id).first()
        current_user_name = current_user_name if current_user_name else "未知用户"
        session.execute(insert(Solder),
            [
                {
                    "SolderCode": barcode,
                    "Model": model,
                    "ProductDate": product_date,
                    "Intimes": in_times + 1,
                    "StationID": cold_area_empty,
                    "StorageUser": current_user_name,
                    "StorageDateTime": current_time
                }
            ]
        )
        session.execute(insert(SolderFlowRecord),
            [
                {
                    "SolderCode": barcode,
                    "UserID": str(current_user_id),
                    "UserName": current_user_name,
                    "DateTime": current_time,
                    "Type": "请求入柜"
                }
            ]
        )
        session.commit()


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
    with db_instance.get_session() as session:
        session.execute(update(Solder),
            [
                {
                    "SolderCode": solder_to_move.SolderCode,
                    "StationID": rewarm_area_empty,
                    "RewarmStartDateTime": datetime.now(),
                }
            ]
        )
        session.commit()


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
    with db_instance.get_session() as session:
        session.execute(update(Solder),
            [
                {
                    "SolderCode": solder_to_move.SolderCode,
                    "StationID": cold_area_empty,
                    "BackLCTimes": solder_to_move.BackLCTimes + 1,
                    "RewarmEndDateTime": datetime.now()
                }
            ]
        )
        session.commit()


def task_move_rewarm_area_to_ready_area(solder_to_move: Solder, ready_area_empty: int):
    """
    从回温区到待取区（自动搅拌，流程中需要搅拌）
    :param solder_to_move: 待移动的锡膏
    :param ready_area_empty: 当前未放置锡膏的待取区点位
    """
    rewarm_area_from = solder_to_move.StationID
    rewarm_end_datetime = datetime.now()
    # 修改点位状态并等待机械臂取放完成
    modbus_client.modbus_write("jcq", 2, rewarm_area_from, 1)
    modbus_client.modbus_write("jcq", 1, ready_area_empty, 1)
    stir_time = 300
    stir_speed = 500
    with db_instance.get_session() as session:
        stir_params = session.query().with_entities(SolderModel.StirTime, SolderModel.StirSpeed).filter(SolderModel.Model == solder_to_move.Model).first()
        stir_time, stir_speed = stir_params.StirTime, stir_params.StirSpeed
    modbus_client.write_float(stir_speed, 1522)
    modbus_client.write_float(stir_time, 1526)
    confirm_robot_get_complete(rewarm_area_from, ready_area_empty)
    confirm_robot_put_complete(rewarm_area_from, ready_area_empty)
    modbus_client.modbus_write("jcq", 0, rewarm_area_from, 1)
    modbus_client.modbus_write("jcq", 0, ready_area_empty, 1)

    # 修改锡膏记录
    with db_instance.get_session() as session:
        session.execute(update(Solder),
            [
                {
                    "SolderCode": solder_to_move.SolderCode,
                    "StationID": ready_area_empty,
                    "RewarmEndDateTime": rewarm_end_datetime,
                    "StirStartDateTime": rewarm_end_datetime,
                    "ReadyOutDateTime": datetime.now()
                }
            ]
        )
        session.commit()


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
    with db_instance.get_session() as session:
        session.execute(update(Solder),
            [
                {
                    "SolderCode": solder_to_move.SolderCode,
                    "StationID": cold_area_empty,
                    "BackLCTimes": solder_to_move.BackLCTimes + 1,
                }
            ]
        )
        session.commit()


def task_move_out_from_rewarm_area(solder_to_move: Solder):
    """
    从回温区出库（出库搅拌）
    :param solder_to_move: 待移动的锡膏
    """
    rewarm_area_from = solder_to_move.StationID
    stir_time = 300
    stir_speed = 500
    with db_instance.get_session() as session:
        stir_params = session.query().with_entities(SolderModel.StirTime, SolderModel.StirSpeed).filter(SolderModel.Model == solder_to_move.Model).first()
        stir_time, stir_speed = stir_params.StirTime, stir_params.StirSpeed
    modbus_client.write_float(stir_speed, 1522)
    modbus_client.write_float(stir_time, 1526)
    modbus_client.modbus_write("jcq", 22, rewarm_area_from, 1)
    confirm_robot_get_complete(rewarm_area_from, 0)
    confirm_user_get_complete(rewarm_area_from, 0)
    modbus_client.modbus_write("jcq", 0, rewarm_area_from, 1)

    # 修改锡膏记录
    current_user_id = get_current_user()
    with db_instance.get_session() as session:
        current_user_name = session.query().with_entities(User.UserName).filter(User.UserID == current_user_id).first()
        current_user_name = current_user_name if current_user_name else "未知用户"
        session.execute(delete(Solder).where(Solder.SolderCode == solder_to_move.SolderCode))
        session.execute(insert(SolderFlowRecord),
            [
                {
                    "SolderCode": solder_to_move.SolderCode,
                    "UserID": current_user_id,
                    "UserName": current_user_name,
                    "Type": "出柜",
                    "DateTime": datetime.now()
                }
            ]
        )
        session.commit()


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
    current_user_id = get_current_user()
    with db_instance.get_session() as session:
        current_user_name = session.query().with_entities(User.UserName).filter(User.UserID == current_user_id).first()
        current_user_name = current_user_name if current_user_name else "未知用户"
        session.execute(delete(Solder).where(Solder.SolderCode == solder_to_move.SolderCode))
        session.execute(insert(SolderFlowRecord),
            [
                {
                    "SolderCode": solder_to_move.SolderCode,
                    "UserID": current_user_id,
                    "UserName": current_user_name,
                    "Type": "出柜",
                    "DateTime": datetime.now()
                }
            ]
        )
        session.commit()
