import os
import re
import time
from datetime import datetime, timedelta, timezone
import logging
import traceback

from collections import defaultdict

import pytz
from apscheduler.executors.pool import ThreadPoolExecutor
from flask_apscheduler import APScheduler
from sqlalchemy import or_
from time import sleep

from modbus.client import modbus_client
from modbus.scan import scan
from modbus.modbus_addresses import ADDR_ROBOT_STATUS, ADDR_ROBOT_CONFIRM
from modbus.modbus_addresses import ADDR_REGION_COLD_START, ADDR_REGION_COLD_END
from modbus.modbus_addresses import ADDR_REGION_REWARM_START, ADDR_REGION_REWARM_END
from modbus.modbus_addresses import region_addr_to_region_name
from models import Station, Solder, SolderModel, SolderFlowRecord, User, Alarm
from util.MES_request import schedule_get_token, send_freeze_log, send_reheat_log, send_mix_log
from util.db_connection import db_instance
from util.logger import logger
from util.parse import parse_barcode

from .task_heartbeat import task_heartbeat
from .task_freeze import task_freeze
from .task_scan import task_scan
from .task_robot import task_robot

# 设置 APScheduler 日志级别为 WARNING
logging.getLogger('apscheduler').setLevel(logging.WARNING)


# 初始化调度器
scheduler =  APScheduler()
# 本地文件路径
file_path = "res_asc.txt"

from datetime import datetime, timedelta

# 初始化601、602、801、802点位为11
process_stations = [601,602,801,802]
for station in process_stations:
    modbus_client.modbus_write("jcq", 11, station, 1)
    status= modbus_client.modbus_read('jcq',station,1)[0]


def process_solders():
    start_time = time.time()
    session = db_instance.get_session()

    for station in process_stations:
        # 如果该点位没有solder，则写11
        if not session.query(Solder.StationID).filter(Solder.StationID == station).all():
            modbus_client.modbus_write("jcq", 11, station, 1)
            status = modbus_client.modbus_read('jcq', station, 1)[0]
            logger.info(f"点位：{station}的状态为：{status}")

    # 查询所有预约的 Solder 数据
    solders = session.query(Solder).filter(Solder.OrderDateTime!=None).all()
    timeout_cache = set()
    solder_fang_station_cache=0
    for item in solders:
        if modbus_client.modbus_read('jcq',item.StationID,1)[0] == 6:
            timeout_cache.add(item.StationID)
            alarm = Alarm(
                AlarmText=f"点位异常：{item.StationID}",
                StartTime=datetime.now(),
                Kind="报警"
            )
            with db_instance.get_instance() as alarm_session:
                alarm_session.add(alarm)
                alarm_session.commit()

    # 查询所有 预约solder可用点位的Station 数据
    stations = session.query(Station).filter(
        or_(
            Station.StationID.between(201, 539),
            Station.StationID.in_([601, 602, 801, 802])
        )
    ).all()

    # 根据 StaType 和 StationID 创建字典
    StaType_station_dict = {station.StaType: station.StationID for station in stations}

    # 冷藏区 回温区 待取区 异常区 取料区 状态变换
    try:
        # 一次性查询所有 Solder 和 SolderModel 关联数据
        solder_data_all = (
            session.query(Solder, SolderModel)
            .join(SolderModel, Solder.Model == SolderModel.Model)
            .filter(( (Solder.StationID.between(201, 870)) |(Solder.StationID.in_(process_stations))), Solder.OrderDateTime != None)
            .all()
        )

        # 定义 ranges
        ranges = [
            (201, 539),
            (601, 602),
            (801, 802)
        ]

        for start, end in ranges:
            solder_data = [
                (solder, model_data) for solder, model_data in solder_data_all
                if start <= solder.StationID <= end
            ]
            solder_station_ids = {int(solder.StationID) for solder, _ in solder_data}
            # 获取当前时间并转换为本地时间（Asia/Shanghai）UTC格式
            local_time = datetime.now()  # 假设这是本地时间，没有时区信息
            local_time = pytz.UTC.localize(local_time)
            # 检查出库是否超时
            if start == 601 or start == 801:
                for solder, model_data in solder_data:
                    if int(solder.StationID) in timeout_cache:
                        continue
                    if model_data and solder.ReadyOutDateTime:
                        # 出库时间超时检查（自动超时冷藏）
                        out_timeout_minutes = getattr(model_data, "OutChaoshiAutoLc", None)
                        ready_out_time = solder.ReadyOutDateTime
                        ready_out_time = pytz.UTC.localize(ready_out_time)
                        if ready_out_time.tzinfo is None:
                            logger.warning("ready_out_time为空")
                        if ready_out_time is not None and out_timeout_minutes is not None:
                            # 计算超时阈值
                            out_timeout_threshold = ready_out_time + timedelta(hours=out_timeout_minutes)
                            # 检查是否超时
                            if local_time > out_timeout_threshold:
                                logger.info(
                                    f"触发自动超时冷藏--出库超时：库位号{int(solder.StationID)} || 出库时间{ready_out_time} || 超时阈值{out_timeout_threshold.strftime('%Y-%m-%d %H:%M:%S %z')} || 设定超时时间{model_data.OutChaoshiAutoLc}小时"
                                )
                                out_chaoshi_auto_lc_times = getattr(model_data, "OutChaoshiAutoLcTimes", None)
                                flag = modbus_client.modbus_read("jcq", int(solder.StationID), 1)[0]
                                # 5是回冷藏，6是异常
                                if flag != 5 and flag != 6:
                                    if solder.BackLCTimes >= out_chaoshi_auto_lc_times:
                                        modbus_client.modbus_write("jcq", 6, int(solder.StationID), 1)
                                        if solder.MesError is None:
                                            error_message = ""
                                        else:
                                            error_message = solder.MesError
                                        # 使用 update 直接修改 Solder 表中的记录
                                        session.query(Solder).filter(Solder.SolderCode == solder.SolderCode).update({
                                            Solder.MesError: error_message + "|出库超时，回冷藏区次数超限制|"
                                        }, synchronize_session=False)
                                        session.commit()
                                    else:
                                        if start == 601:  # 回温区给状态 5
                                            modbus_client.modbus_write("jcq", 5, int(solder.StationID), 1)
                                        else:  # 待取区，若搅拌后回冰柜，给 5，否则 6
                                            if_back_after_jiaoban = getattr(model_data, "IfBackAfterJiaoban", None)
                                            if int(if_back_after_jiaoban) == 1:
                                                modbus_client.modbus_write("jcq", 5, int(solder.StationID), 1)
                                            else:
                                                if solder.MesError is None:
                                                    error_message = ""
                                                else:
                                                    error_message = solder.MesError
                                                modbus_client.modbus_write("jcq", 6, int(solder.StationID), 1)
                                                # 使用 update 直接修改 Solder 表中的记录
                                                session.query(Solder).filter(
                                                    Solder.SolderCode == solder.SolderCode).update({
                                                    Solder.MesError: error_message + "|出库超时，应回冷藏区，但是设置搅拌后不回冰柜|"
                                                }, synchronize_session=False)
                                                session.commit()
                                session.commit()  # 提交数据库更新
                                timeout_cache.add(int(solder.StationID))
                                continue  # 超时后跳过后续操作
                        else:
                            logger.error(
                                f"ready_out_time is {ready_out_time} and out_timeout_minutes is {out_timeout_minutes}")
            if start == 201:
                for solder, model_data in solder_data:
                    if int(solder.StationID) in timeout_cache:
                        continue
                    if model_data:
                        order_time = solder.OrderDateTime
                        sitr_time = timedelta(seconds=model_data.StirTime)
                        rewarm_time = timedelta(minutes=model_data.RewarmTime)
                        offset_time = timedelta(minutes=1)

                        # 计算目标时间：OrderDateTime - SitrTime - RewarmTime - 1 分钟
                        target_time = order_time - sitr_time - rewarm_time - offset_time
                        current_time = datetime.now()

                        # if target_time <= current_time:
                        #     # 执行 modbus_write 操作
                        #     modbus_client.modbus_write("jcq", 12, item.StationID, 1)

                        solder_storage_time = solder.StorageDateTime
                        if solder_storage_time.tzinfo is None:
                            solder_storage_time = pytz.UTC.localize(solder_storage_time)
                        # 动态选择时间字段和区域名称
                        check_field = "MinLcTime"
                        region_name = "冷藏区"

                        # 状态变换判断
                        time_delta = timedelta(
                            hours=getattr(model_data, check_field) if check_field == "MinLcTime" else 0,
                            minutes=getattr(model_data, check_field) if check_field == "RewarmTime" else 0
                        )
                        check_threshold = local_time - time_delta
                        modbus_value = 12 if solder_storage_time <= check_threshold else 10

                        if target_time <= current_time:
                            modbus_client.modbus_write("jcq", modbus_value, int(solder.StationID), 1)
                            logger.info(
                                f"状态变换：{region_name} || 存储时间{solder_storage_time} || 预约的冷藏结束时间{check_threshold} 出库使劲{target_time} || 点位{int(solder.StationID)} || 写入值{modbus_value}"
                            )

            if start == 601:
                for solder, model_data in solder_data:
                    if int(solder.StationID) in timeout_cache:
                        continue
                    if model_data:
                        solder_storage_time = solder.StorageDateTime
                        if solder_storage_time.tzinfo is None:
                            solder_storage_time = pytz.UTC.localize(solder_storage_time)
                        # 动态选择时间字段和区域名称
                        timeout_field = "RewarmMaxTime"
                        check_field = "RewarmTime"
                        region_name = "回温区"
                        # RewarmMaxTime 超时判断
                        timeout_threshold = local_time - timedelta(minutes=getattr(model_data, timeout_field))

                        if solder_storage_time <= timeout_threshold:
                            logger.info(
                                f"超时：{region_name}{timeout_threshold.strftime('%Y-%m-%d %H:%M:%S %z')} || {int(solder.StationID)} || 设定超时时间{getattr(model_data, timeout_field)}"
                            )
                            modbus_client.modbus_write("jcq", 5, int(solder.StationID), 1)
                            continue  # 超时后跳过后续操作
                        # 状态变换判断
                        time_delta = timedelta(
                            hours=getattr(model_data, check_field) if check_field == "MinLcTime" else 0,
                            minutes=getattr(model_data, check_field) if check_field == "RewarmTime" else 0
                        )
                        check_threshold = local_time - time_delta
                        # 回温结束时间算出来之后，那就要填到solder表中对应的记录中去
                        session.query(Solder).filter(Solder.SolderCode == solder.SolderCode).update({
                            Solder.RewarmEndDateTime: check_threshold
                        }, synchronize_session=False)
                        rule = session.query().with_entities(SolderModel.JiaobanRule).filter(SolderModel.Model == solder.Model).first().JiaobanRule
                        if solder_storage_time <= check_threshold:
                            if rule == "自动搅拌":
                                modbus_value = 12
                            else:
                                modbus_value = 21
                        else:
                            modbus_value = 10
                        # modbus_value = 12 if solder_storage_time <= check_threshold else 10
                        session.commit()
                        logger.info(
                            f"状态变换：{region_name} || 存储时间{solder_storage_time} || 预约的回温结束时间{check_threshold} || 点位{int(solder.StationID)} || 写入值{modbus_value}"
                        )
                        modbus_client.modbus_write("jcq", modbus_value, int(solder.StationID), 1)

            if start == 801:
                for solder, model_data in solder_data:
                    if model_data:
                        # ReadyOutTimeOut 超时判断
                        timeout_field = "ReadyOutTimeOut"
                        region_name = "待取区"
                        timeout_threshold = local_time - timedelta(minutes=getattr(model_data, timeout_field))
                        solder_storage_time = solder.StorageDateTime
                        if solder_storage_time.tzinfo is None:
                            solder_storage_time = pytz.UTC.localize(solder_storage_time)

                        if solder_storage_time <= timeout_threshold:
                            logger.info(
                                f"超时：预约的锡膏在{region_name}{timeout_threshold.strftime('%Y-%m-%d %H:%M:%S %z')} || {int(solder.StationID)} || 设定超时时间{getattr(model_data, timeout_field)}"
                            )
                            modbus_client.modbus_write("jcq", 5, int(solder.StationID), 1)
                            timeout_cache.add(int(solder.StationID))
                            continue  # 超时后跳过后续操作

                    # 判断是否需要写入 0，只有待取区等于2的时候，要一直为2，直到有人来取
                    flag = modbus_client.modbus_read("jcq", int(solder.StationID), 1)[0]
                    if flag == 11:
                        modbus_client.modbus_write("jcq", 10, int(solder.StationID), 1)

            for item in timeout_cache:
                logger.info(f"超时点位缓存{item}")

            if 601 == start:
                # 点位没锡膏的，且不是正在被放锡膏的点位，让这些点位全都能放
                for station_id in range(601, 603):  # 范围 601 到 602
                    if station_id not in solder_station_ids:
                        modbus_client.modbus_write("jcq", 11, station_id, 1)

            if 801 == start:
                # 点位没锡膏的，且不是正在被放锡膏的点位，让这些点位全都能放
                for station_id in range(801, 803):
                    if station_id not in solder_station_ids:
                        modbus_client.modbus_write("jcq", 11, station_id, 1)
            # if 201 == start:
            #     for station_id in range(201, 539):
            #         if station_id not in solder_station_ids:
            #             modbus_client.modbus_write("jcq", 11, station_id, 1)
    except Exception as e:
        session.close()
        logger.error(f"Error in query_solder_and_station task: {e}")
    except TimeoutError:
        logger.warning("任务执行超时，跳过当前任务")
    finally:
        end_time = time.time()
        # 计算任务执行时间
        execution_time = end_time - start_time
        logger.info(f"预约区的任务执行时间：{execution_time} 秒")
        session.close()

def move_update():
    start_time = time.time()
    huiwen_daiqu = True     # 待取区保持数量不够，需要从回温区取
    lengcang_huiwen = True  # 回温区保持数量不够，需要从冷藏区取
    with db_instance.get_session() as session:
        # 查询所有非预约的 Solder 数据
        solders = session.query(Solder).filter(Solder.OrderDateTime==None).all()
        # 假设 solder 是字典列表，每个字典有一个 'StationID' 键
        timeout_cache = set()
        # solder_fang_station_cache=0
        # solder_qu_station_cache = 0
        # #用于取完成之后缓存取出来的锡膏信息
        # solder_cache=[]

        for item in solders:
            if modbus_client.modbus_read('jcq',item.StationID,1)[0] == 6:
                timeout_cache.add(item.StationID)
                alarm = Alarm(
                    AlarmText=f"点位异常：{item.StationID}",
                    StartTime=datetime.now(),
                    Kind="报警"
                )
                with db_instance.get_instance() as alarm_session:
                    alarm_session.add(alarm)
                    alarm_session.commit()
        # 查询非预约专用点位的 Station 数据
        stations = session.query(Station).filter(Station.StationID.notin_([601,602,801,802]) ).all()
        # 根据 StaType 和 StationID 创建字典
        StaType_station_dict = {station.StaType: station.StationID for station in stations}

        # 提取所需字段（Model 和 StationID），并确保 StationID 转换为整数,用于下面统计回温和待取的锡膏个数
        solder_data = [
            {"Model": solder.Model, "StationID": solder.StationID}  # 转换为整数
            for solder in solders if (603 <= solder.StationID <= 660) or (803<= solder.StationID<=840)  # 在筛选时也确保转换为整数
        ]
        # 查询所有 SolderModel 数据并构建字典 {Model: SolderModel 对象}
        solder_model_dict = {
            model_data.Model: model_data
            for model_data in session.query(SolderModel).all()
        }
        # 统计每个 Model 在不同区间（601-660 和 801-840）内的数量
        count_by_model = defaultdict(lambda: {"count_603_660": 0, "count_803_840": 0})
        for solder in solder_data:  # 遍历列表中的字典
            model = solder['Model']
            station_id = solder['StationID']
            # 判断 StationID 是否在指定区间
            if 603 <= station_id <= 660:
                count_by_model[model]["count_603_660"] += 1
            elif 803 <= station_id <= 840:
                count_by_model[model]["count_803_840"] += 1


        #各个位置取放时交互信息

        #冷藏区 回温区 待取区 异常区 取料区 状态变换
        """
            处理：
                冷藏区——回温区：保持回温数量不足
                回温区——冷藏区：超出最大回温时间
                回温区——待取区：保持待取数量不足
                待取区——冷藏区：超出待取区超时时间
        """

        # 一次性查询所有 Solder 和 SolderModel 关联数据
        # solder_data_all = (
        #     session.query(Solder, SolderModel)
        #     .join(SolderModel, Solder.Model == SolderModel.Model)
        #     .filter(Solder.StationID.between(201, 870))
        #     .all()
        # )
        solder_data_all = (
            session.query(Solder, SolderModel)
            .join(SolderModel, Solder.Model == SolderModel.Model)
            .filter((Solder.StationID.between(201, 870)) & (Solder.StationID.notin_([601,602,801,802])) )
            .all()
        )

        # 定义 ranges
        ranges = [
            (201, 539),
            (603, 660),
            (803, 870)
        ]
        # fang_603_660 = 1 if 603 <= solder_fang_station_cache <= 660 else 0
        # fang_803_840 = 1 if 803 <= solder_fang_station_cache <= 840 else 0
        for start, end in ranges: # 处理冷藏区、回温区、待取区
            solder_data = [
                (solder, model_data) for solder, model_data in solder_data_all
                if start <= solder.StationID <= end
            ]
            # 每个区域的存在锡膏的点位
            solder_station_ids = {int(solder.StationID) for solder, _ in solder_data}
            # 获取当前时间并转换为本地时间（Asia/Shanghai）UTC格式
            local_time = datetime.now()
            #检查出库是否超时
            if start == 603 or start == 803:
                for solder, model_data in solder_data:
                    if int(solder.StationID) in timeout_cache:
                        continue
                    if model_data and solder.ReadyOutDateTime:
                        # 出库时间超时检查（自动超时冷藏）
                        out_timeout_minutes = getattr(model_data, "OutChaoshiAutoLc", None)
                        ready_out_time = solder.ReadyOutDateTime
                        if ready_out_time.tzinfo is None:
                            logger.warning("ready_out_time为空")
                        if ready_out_time is not None and out_timeout_minutes is not None:
                            # 计算超时阈值
                            out_timeout_threshold = ready_out_time + timedelta(hours=out_timeout_minutes)
                            # 检查是否超时
                            if local_time > out_timeout_threshold:
                                logger.info(
                                    f"触发自动超时冷藏--出库超时：该锡膏的型号{solder.Model} || 库位号{int(solder.StationID)} || 出库时间{ready_out_time} || 超时阈值{out_timeout_threshold.strftime('%Y-%m-%d %H:%M:%S %z')} || 设定超时时间{model_data.OutChaoshiAutoLc}小时"
                                )
                                out_chaoshi_auto_lc_times = getattr(model_data, "OutChaoshiAutoLcTimes", None)
                                logger.info(
                                    f"锡膏{solder.SolderCode}的型号：{solder.Model}，该型号的允许冷藏区的最大次数为：{out_chaoshi_auto_lc_times}")

                                flag=modbus_client.modbus_read("jcq",int(solder.StationID), 1)[0]
                                #5是回冷藏，6是异常
                                if flag!=5 and flag!=6:
                                    if solder.BackLCTimes >=out_chaoshi_auto_lc_times:
                                        modbus_client.modbus_write("jcq", 6, int(solder.StationID), 1)
                                        if solder.MesError is None:
                                            error_message = ""
                                        else:
                                            error_message = solder.MesError
                                        # 使用 update 直接修改 Solder 表中的记录
                                        session.query(Solder).filter(Solder.SolderCode == solder.SolderCode).update({
                                            Solder.MesError: error_message + "|出库超时，回冷藏区次数超限制|"
                                        }, synchronize_session=False)
                                        session.commit()
                                    else:
                                        if start == 601:  # 回温区给状态 5
                                            modbus_client.modbus_write("jcq", 5, int(solder.StationID), 1)
                                            logger.info(f"锡膏{solder.SolderCode}在点位{solder.StationID}上达到了自动回冷藏的时间")
                                        else:  # 待取区，若搅拌后回冰柜，给 5，否则 6
                                            if_back_after_jiaoban = getattr(model_data, "IfBackAfterJiaoban", None)
                                            if int(if_back_after_jiaoban) == 1:
                                                modbus_client.modbus_write("jcq", 5, int(solder.StationID), 1)
                                                logger.info(
                                                    f"锡膏{solder.SolderCode}在点位{solder.StationID}上达到了自动回冷藏的时间")
                                            else:
                                                if solder.MesError is None:
                                                    error_message=""
                                                else:
                                                    error_message = solder.MesError
                                                modbus_client.modbus_write("jcq", 6, int(solder.StationID), 1)
                                                # 使用 update 直接修改 Solder 表中的记录
                                                session.query(Solder).filter(Solder.SolderCode == solder.SolderCode).update({
                                                    Solder.MesError: error_message+"|出库超时，应回冷藏区，但是设置搅拌后不回冰柜|"
                                                }, synchronize_session=False)
                                                session.commit()
                                session.commit()  # 提交数据库更新
                                timeout_cache.add(int(solder.StationID))
                                continue  # 超时后跳过后续操作
                        else:
                            logger.error(
                                f"ready_out_time is {ready_out_time} and out_timeout_minutes is {out_timeout_minutes}")
            if start == 201:
                for solder, model_data in solder_data:
                    if int(solder.StationID) in timeout_cache:
                        continue
                    if model_data:
                        amount = model_data.RewarmNum - count_by_model[model_data.Model]["count_603_660"]
                        amount = amount if amount>0 else 0
                        check_field = "MinLcTime"
                        region_name = "冷藏区"
                        ok_solders = (
                            session.query(Solder)
                            .filter(Solder.StationID.between(201,539),
                                    Solder.Model==model_data.Model,
                                    Solder.StorageDateTime <= local_time - timedelta(hours=getattr(model_data, check_field))
                                    )
                            .order_by(Solder.InTimes.desc())
                            .limit(amount)
                        )
                        if solder.OutDateTime == None:
                            modbus_value = 2 if solder in ok_solders else 0
                        else:
                            modbus_value = 12 if solder in ok_solders else 10
                        modbus_client.modbus_write("jcq", modbus_value, int(solder.StationID), 1)
                        logger.info(
                            f"状态变换：{region_name} || 存储时间{solder.StorageDateTime} || 冷藏结束时间{local_time - timedelta(hours=getattr(model_data, check_field))} || 点位{int(solder.StationID)} || 写入值{modbus_value}"
                        )

            if start == 603:
                for solder, model_data in solder_data:
                    if int(solder.StationID) in timeout_cache:
                        continue
                    if model_data :
                        solder_storage_time = solder.StorageDateTime
                        timeout_field = "RewarmMaxTime"
                        check_field = "RewarmTime"
                        region_name = "回温区"

                        # RewarmMaxTime 超时判断
                        timeout_threshold = local_time - timedelta(minutes=getattr(model_data, timeout_field))
                        if solder_storage_time <= timeout_threshold:
                            logger.info(f"超时：{region_name}{timeout_threshold.strftime('%Y-%m-%d %H:%M:%S %z')} || {int(solder.StationID)} || 设定超时时间{getattr(model_data, timeout_field)}")
                            modbus_client.modbus_write("jcq", 5, int(solder.StationID), 1)
                            continue  # 超时后跳过后续操作

                        rule = session.query().with_entities(SolderModel.JiaobanRule).filter(SolderModel.Model == solder.Model).first().JiaobanRule
                        if solder.RewarmEndDateTime <= local_time:
                            if rule == "自动搅拌":
                                modbus_value = 2
                            else:
                                modbus_value = 21
                        else:
                            modbus_value = 0
                        # modbus_value = 12 if solder_storage_time <= check_threshold else 10
                        session.commit()
                        logger.info(
                            f"状态变换：{region_name} || 存储时间{solder_storage_time} || 回温结束时间{solder.RewarmEndDateTime} || 点位{int(solder.StationID)} || 写入值{modbus_value}"
                        )
                        current_modbus_status = modbus_client.modbus_read("jcq", int(solder.StationID), 1)[0]
                        if current_modbus_status != 22 and current_modbus_status != 21:
                            modbus_client.modbus_write("jcq", modbus_value, int(solder.StationID), 1)

            if start == 803:
                for solder, model_data in solder_data:
                    if model_data:
                        # ReadyOutTimeOut 超时判断
                        timeout_field = "ReadyOutTimeOut"
                        region_name = "待取区"
                        timeout_threshold = local_time - timedelta(minutes=getattr(model_data, timeout_field))
                        solder_storage_time = solder.StorageDateTime

                        if solder_storage_time <= timeout_threshold:
                            logger.info(
                                f"超时：{region_name}{timeout_threshold.strftime('%Y-%m-%d %H:%M:%S %z')} || {int(solder.StationID)} || 设定超时时间{getattr(model_data, timeout_field)}"
                            )
                            modbus_client.modbus_write("jcq", 5, int(solder.StationID), 1)
                            timeout_cache.add(int(solder.StationID))
                            continue  # 超时后跳过后续操作

                    # 判断是否需要写入 0，只有待取区等于2的时候，要一直为2，直到有人来取
                    flag = modbus_client.modbus_read("jcq", int(solder.StationID), 1)[0]
                    if flag == 1:
                        modbus_client.modbus_write("jcq", 0, int(solder.StationID), 1)



            # # 将 Station 数据转化为字典（这里直接使用 StationID 作为字典的键）
            station_dict = {station.StationID: station for station in stations}
            # # 筛选出符合条件的 Station 数据
            station_data = [
                station for station in station_dict.values()
                if start <= station.StationID <= end and station.StationID not in solder_station_ids
            ]
            # 遍历每个 Model 并进行逻辑判断
            for model, counts in count_by_model.items():
                solder_model = solder_model_dict.get(model)
                if solder_model:
                    rewarm_num = solder_model.RewarmNum
                    ready_out_num = solder_model.ReadyOutNum

                    logger.info(f"找到 Model='{model}' 的记录: RewarmNum={rewarm_num}, ReadyOutNum={ready_out_num}")
                    logger.info(
                        f"查询结果: count_803_840={counts['count_803_840']}, count_603_660={counts['count_603_660']}")

                    # 根据查询结果设置 huiwen_daiqu 的值
                    huiwen_daiqu = counts["count_803_840"] < ready_out_num
                    logger.info(f"设置 huiwen_daiqu = {huiwen_daiqu} for Model {model}")

                    # 根据查询结果设置 lengcang_huiwen 的值
                    lengcang_huiwen = counts["count_603_660"] < rewarm_num
                    logger.info(f"设置 lengcang_huiwen = {lengcang_huiwen} for Model {model}")

                    logger.info(f"count_by_model:{count_by_model},rewarm_num:{rewarm_num}")
                else:
                    logger.error(f"未找到符合条件的 {model} 模型记录")

            # 输出最终结果日志
            logger.info(f"最终状态: huiwen_daiqu={huiwen_daiqu}, lengcang_huiwen={lengcang_huiwen}")

            for item in timeout_cache:
                logger.info(f"超时点位缓存{item}")

            if 603 == start:

                if lengcang_huiwen == False:
                    for station_id in range(603, 661):  # 范围 601 到 660
                        if station_id not in solder_station_ids:
                            modbus_client.modbus_write("jcq", 0, station_id, 1)
                else:
                    for station_id in range(603, 661):  # 范围 601 到 660
                        if station_id not in solder_station_ids:
                            modbus_client.modbus_write("jcq", 1, station_id, 1)
            if 803 == start:
                if huiwen_daiqu == False:
                    for station_id in range(803, 841):  # 范围 601 到 660
                        if station_id not in solder_station_ids:
                            modbus_client.modbus_write("jcq", 0, station_id, 1)
                else:
                    for station_id in range(803, 841):  # 范围 801 到 840
                        if station_id not in solder_station_ids:
                            modbus_client.modbus_write("jcq", 1, station_id, 1)
            if 201 == start :
                for station_id in range(201, 539):  # 范围 601 到 660
                    if station_id not in solder_station_ids:
                        modbus_client.modbus_write("jcq", 1, station_id, 1)


def read_mode():
    """
    从本地文件 mode.txt 中读取模式
    :return: 返回模式的整数（0 或 1）
    """
    try:
        with open("mode.txt", "r") as file:
            mode = file.read().strip()
            return int(mode) if mode in ['0', '1'] else 0  # 默认返回 0
    except FileNotFoundError:
        return -1  # 如果文件不存在，默认返回 -1


def run_scheduler():
    mode = read_mode()
    if mode == 0:
        task_robot()
        task_freeze()
    elif mode == 1:
        task_scan()
        task_robot()
        if not modbus_client.modbus_read("jcq", ADDR_ROBOT_STATUS.ACT, 1)[0]:
            move_update()
            process_solders()


def infinite_loop(func, interval=1):
    while True:
        sleep(interval)
        try:
            func()
        except Exception as exc:
            logger.error(traceback.format_exc())


def init_scheduler(app):
    scheduler.init_app(app)
    scheduler.add_job(id='task_heartbeat', func=task_heartbeat, trigger='interval', seconds=1)
    scheduler.add_job(id='run_scheduler', func=infinite_loop, args=(run_scheduler,), trigger='date', next_run_time=datetime.now())
    if not scheduler.running:
        # 确保调度器正在运行，如果不是可以重启调度器或处理该情况
        scheduler.start()
