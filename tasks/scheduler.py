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

# 设置 APScheduler 日志级别为 WARNING
logging.getLogger('apscheduler').setLevel(logging.WARNING)


# 初始化调度器
scheduler =  APScheduler()
# 本地文件路径
file_path = "res_asc.txt"
def check_string(s):
    # 条件 1: 位置 4-9 为六位数字
    condition_1 = bool(re.match(r".{3}(\d{6})", s))  # 匹配位置 4-9 为六位数字

    # 条件 2: 位置 10-14 为五位数字
    condition_2 = bool(re.match(r".{9}(\d{5})", s))  # 匹配位置 10-14 为五位数字

    # 条件 3: 存在 3 个 “&” 符号
    condition_3 = s.count("&") == 3  # 检查是否存在 3 个 & 符号

    # 条件 4: 第 15 位是符号 "&"
    condition_4 = len(s) >= 15 and s[14] == "&"  # 检查第 15 位是否为 "&"

    # 返回是否符合所有条件
    return condition_1 and condition_2 and condition_3 and condition_4

def check_string2(s):
    condition_1 = s.count("+") >= 5

    return condition_1
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

    # 各个位置取放时交互信息
    try:
        # 查询 Station 表并插入 Solder 数据逻辑
        qu = modbus_client.modbus_read("jcq", 100, 1)
        fang = modbus_client.modbus_read("jcq", 101, 1)
        result = modbus_client.modbus_read("jcq", 102, 1)
        sta_types = [f"移动模组[{qu[0]}]", f"移动模组[{fang[0]}]"]
        # 获取对应的 Station 对象
        station_qu = StaType_station_dict.get(sta_types[0])
        station_fang = StaType_station_dict.get(sta_types[1])
        if result[0] == 2:  # 取完成
            if station_qu:
                if station_qu >= 201 and station_qu <= 539:  # 从冷藏区取出，准备出库
                    session.query(Solder).filter(Solder.StationID == station_qu).update({
                        Solder.ReadyOutDateTime: datetime.now()  # 准备出库时间，用来回冷藏
                    }, synchronize_session=False)
                    session.commit()

                if station_qu >= 601 and station_qu <= 602:
                    solder_record = session.query(Solder).filter(Solder.StationID == station_qu).first()
                    if solder_record:
                        solder_model_record = session.query(SolderModel).filter(
                            SolderModel.Model == solder_record.Model).first()
                        if solder_model_record:
                            modbus_client.write_float(solder_model_record.StirSpeed, 1522)
                            modbus_client.write_float(solder_model_record.StirTime, 1526)
                            logger.info(
                                f"{solder_record.SolderCode}在搅拌区设置搅拌参数成功 时间{solder_model_record.StirSpeed}速度{solder_model_record.StirTime}")
                            # 从回温区取完成并给设置了搅拌参数之后，立刻会转移到搅拌区，那就把这个时刻作为搅拌开始时间StirStartDateTime
                            session.query(Solder).filter(Solder.SolderCode == solder_record.SolderCode).update({
                                Solder.StirStartDateTime: datetime.now()
                            }, synchronize_session=False)
                            session.commit()
                        else:
                            logger.error(
                                f"{solder_record.SolderCode}在搅拌区设置搅拌参数出错 未找到solder_model_record")

                modbus_client.modbus_write("jcq", qu[0], 105, 1)
                modbus_client.modbus_write("jcq", fang[0], 106, 1)
                modbus_client.modbus_write("jcq", result[0], 107, 1)
                logger.info(f"预约:状态{result[0]} :从{qu[0]}移动到{fang[0]}")
            else:
                logger.error(f"没有找到符合 StaType '{station_qu}' 的 StationID")

        if result[0] == 4:  # 放完成
            if station_qu and station_fang:
                modbus_client.modbus_write('jcq', 10, station_fang, 1)
                modbus_client.modbus_write("jcq", 11, station_qu, 1)
                solder_fang_station_cache = station_fang
                # 从 Solder 表中查询 StationID 等于当前 station 的记录
                # logger.info(f"0--------{station_fang}--------{station_qu}")
                solder_record = next((solder for solder in solders if solder.StationID == station_qu), None)
                # logger.info(f"1----------------{solder_record}")
                if solder_record:
                    code = solder_record.SolderCode  # 使用查询到的 SolderCode
                    # logger.info(f"2----------------{code}")
                    from sqlalchemy.orm.exc import NoResultFound
                    from sqlalchemy.exc import IntegrityError

                    try:
                        # 查询是否已经存在相同的 SolderCode 或 StationID
                        existing_record = session.query(Solder).filter(
                            (Solder.SolderCode == code) | (Solder.StationID == station_fang)
                        ).first()

                        if existing_record:
                            # 如果存在相同的 SolderCode 或 StationID
                            if existing_record.SolderCode == code and existing_record.StationID == station_fang:
                                # 如果 SolderCode 和 StationID 都一致，更新数据
                                # logger.info(f"SolderCode {code} 和 StationID {station_fang} 已存在，正在更新数据。")
                                existing_record.StorageDateTime = datetime.now()
                                session.commit()
                                # modbus_client.modbus_write("jcq", qu[0], 105, 1)
                                # modbus_client.modbus_write("jcq", fang[0], 106, 1)
                                # modbus_client.modbus_write("jcq", result[0], 107, 1)
                                # logger.info(f"预约:状态{result[0]} :从{qu[0]}移动到{fang[0]}")
                                # logger.info(f"Solder 数据已更新：SolderCode={code}, StationID={station_fang}")
                            elif existing_record.SolderCode == code:
                                # 如果只有 SolderCode 存在，更新 StationID 和 StorageDateTimedianwei
                                # logger.info(f"SolderCode {code} 已存在，正在更新 StationID 和数据。")
                                existing_record.StationID = station_fang
                                existing_record.StorageDateTime = datetime.now()
                                session.commit()
                                # modbus_client.modbus_write("jcq", qu[0], 105, 1)
                                # modbus_client.modbus_write("jcq", fang[0], 106, 1)
                                # modbus_client.modbus_write("jcq", result[0], 107, 1)
                                # logger.info(f"预约:状态{result[0]} :从{qu[0]}移动到{fang[0]}")
                                # logger.info(f"Solder 数据已更新：SolderCode={code}, StationID={station_fang}")
                            elif existing_record.StationID == station_fang:
                                # 如果只有 StationID 存在，更新 SolderCode 和数据
                                # logger.info(f"StationID {station_fang} 已存在，正在更新 SolderCode 和数据。")
                                existing_record.SolderCode = code
                                existing_record.StorageDateTime = datetime.now()
                                session.commit()
                                # modbus_client.modbus_write("jcq", qu[0], 105, 1)
                                # modbus_client.modbus_write("jcq", fang[0], 106, 1)
                                # modbus_client.modbus_write("jcq", result[0], 107, 1)
                                # logger.info(f"预约:状态{result[0]} :从{qu[0]}移动到{fang[0]}")
                                # # logger.info(f"Solder 数据已更新：SolderCode={code}, StationID={station_fang}")
                        else:
                            # 如果不存在相同的 SolderCode 和 StationID，插入新数据
                            sql_data = Solder(
                                SolderCode=code,
                                Model=solder_record.Model,
                                BackLCTimes=0,
                                StationID=station_fang,
                                StorageDateTime=datetime.now()
                            )
                            session.add(sql_data)
                            session.commit()  # 提交新记录
                            # logger.info(f"新Solder数据添加成功：SolderCode={code}, StationID={station_fang}")
                            # modbus_client.modbus_write("jcq", qu[0], 105, 1)
                            # modbus_client.modbus_write("jcq", fang[0], 106, 1)
                            # modbus_client.modbus_write("jcq", result[0], 107, 1)
                            # logger.info(f"预约:状态{result[0]} :从{qu[0]}移动到{fang[0]}")
                        session.commit()
                        modbus_client.modbus_write("jcq", qu[0], 105, 1)
                        modbus_client.modbus_write("jcq", fang[0], 106, 1)
                        modbus_client.modbus_write("jcq", result[0], 107, 1)
                        logger.info(f"放完成:状态{result[0]} :从{qu[0]}移动到{fang[0]}")
                    except IntegrityError as e:
                        # 捕获 IntegrityError 错误，处理唯一键冲突
                        session.rollback()  # 回滚事务
                        logger.error(f"数据库操作失败，发生唯一键冲突：{e}")
                    except Exception as e:
                        # 捕获其他异常
                        session.rollback()
                        logger.error(f"发生错误：{e}")

                    # 放冷藏区
                    if 201 <= station_fang <= 539:
                        solder = session.query(Solder).filter(
                            Solder.SolderCode == solder_record.SolderCode).first()
                        if solder:
                            solder.BackLCTimes += 1
                            session.commit()  # 提交更改
                            # logger.info(f"BackLCTimes 自增后: {solder_record.BackLCTimes}")
                        else:
                            logger.error(f"BackLCTimes 自增出错，未找到条码{solder_record.SolderCode}")
                        # 更新 SolderFlowRecord 表中的 Type 字段为 '入柜'
                        # 查询到最新的 SolderFlowRecord 记录
                        # logger.info(f"4----------------入柜")
                        solder_flow_record = session.query(SolderFlowRecord).filter(
                            SolderFlowRecord.SolderCode == code).order_by(
                            SolderFlowRecord.DateTime.desc()).first()
                        # logger.info(f"5----------------{solder_flow_record}")
                        if solder_flow_record:  # 确保找到了记录
                            # 更新实例的字段
                            solder_flow_record.Type = '入柜'  # 你可以在这里使用你需要的中文或字段
                            solder_flow_record.DateTime = datetime.now()
                            logger.info("发送冷冻日志s")
                            # send_freeze_log(rid=code,user_login=None)
                            logger.info("发送冷冻日志e")
                        else:
                            logger.warning("===============入柜状态4：未找到solderflowrecord===============")
                    if 601 <= station_fang <= 602:
                        # 放到回温区，那回温开始时间就从此刻算起了
                        # 更新Solder表中这个solder_record的RewarmStartDateTime
                        session.query(Solder).filter(Solder.SolderCode == code).update({
                            Solder.RewarmStartDateTime: datetime.now()
                        }, synchronize_session=False)
                        session.commit()
                        logger.info("发送回温日志")
                        # send_reheat_log(rid=code, user_login=None)
                        logger.info("发送回温日志")
                    # session.commit()
                    # modbus_client.modbus_write("jcq", qu[0], 105, 1)
                    # modbus_client.modbus_write("jcq", fang[0], 106, 1)
                    # modbus_client.modbus_write("jcq", result[0], 107, 1)
                    # logger.info(f"预约:状态{result[0]} :从{qu[0]}移动到{fang[0]}")
                    # logger.info(f"条码 '{solder_record.SolderCode}' 从{station_qu}移动到{station_fang} 完成")
                else:
                    logger.error(f"没有找到 StationID 等于 '{station_qu}' 的 Solder 记录")
            else:
                logger.error(f"没有找到符合 StaType '{station_qu}' 的 StationID")

        if result[0] == 5:  # 锡膏被人取走完成
            if station_fang:
                # 根据查询到的 StationID，查询 Solder 表中的记录
                solder_record = session.query(Solder).filter(Solder.StationID == station_fang).first()
                if solder_record:
                    solder_code = solder_record.SolderCode  # 获取 SolderCode

                    # 删除 Solder 表中对应 SolderCode 的记录
                    session.query(Solder).filter(Solder.SolderCode == solder_code).delete()

                    # 更新 SolderFlowRecord 表中的 Type 字段为 '出柜'
                    # 查询到最新的 SolderFlowRecord 记录
                    solder_flow_record = session.query(SolderFlowRecord).filter(
                        SolderFlowRecord.SolderCode == solder_code).order_by(
                        SolderFlowRecord.DateTime.desc()).first()

                    if solder_flow_record:  # 确保找到了记录
                        # 更新实例的字段
                        solder_flow_record.Type = '出柜'
                        solder_flow_record.DateTime = datetime.now()
                    else:
                        logger.warning("===============出柜状态5：未找到solderflowrecord===============")
                    # 提交事务
                    session.commit()
                    modbus_client.modbus_write("jcq", qu[0], 105, 1)
                    modbus_client.modbus_write("jcq", fang[0], 106, 1)
                    modbus_client.modbus_write("jcq", result[0], 107, 1)
                    logger.info(f"预约:状态{result[0]} :从{qu[0]}移动到{fang[0]}")
                    logger.info(f"条码` '{solder_code}' 已删除并标记为出柜")
                else:
                    logger.error(f"{station_fang}点位没有找到 Solder 记录")
            else:
                logger.error(f"没有找到符合 StaType '{station_fang}' 的 Station 记录")

    except Exception as e:
        session.close()
        logger.error(f"Error in periodic task (Station/Solder logic): {e}")
        return
    except TimeoutError:
        logger.warning("任务执行超时，跳过当前任务")

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
                        session.commit()
                        modbus_value = 12 if solder_storage_time <= check_threshold else 10
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
                    if station_id not in solder_station_ids and station_id != solder_fang_station_cache:
                        modbus_client.modbus_write("jcq", 11, station_id, 1)

            if 801 == start:
                # 点位没锡膏的，且不是正在被放锡膏的点位，让这些点位全都能放
                for station_id in range(801, 803):
                    if station_id not in solder_station_ids and station_id != solder_fang_station_cache:
                        modbus_client.modbus_write("jcq", 11, station_id, 1)
            # if 201 == start:
            #     for station_id in range(201, 539):
            #         if station_id not in solder_station_ids and station_id != solder_fang_station_cache:
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

def move_update(mode):
    start_time = time.time()
    huiwen_daiqu = True  # 给变量一个初始值，避免未赋值的情况
    lengcang_huiwen = True  # 同样处理另一个变量
    session = db_instance.get_session()
    # 查询所有非预约的 Solder 数据
    solders = session.query(Solder).filter(Solder.OrderDateTime==None).all()
    # 假设 solder 是字典列表，每个字典有一个 'StationID' 键
    timeout_cache = set()
    solder_fang_station_cache=0
    solder_qu_station_cache = 0
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

    # 扫码位置成功扫码
    try:
        # 读取 Modbus 数据逻辑
        result = modbus_client.modbus_read("jcq", 111, 1)
        if result[0] == 1:
            location = modbus_client.modbus_read("jcq", 110, 1)[0]
            # res_asc = modbus_client.read_float_ASCII(115, 134)
            res_asc = scan()
            # 清空文件内容
            with open(file_path, "w") as file:
                file.truncate(0)
            # 将 res_asc 写入本地文件
            with open(file_path, "w") as file:
                file.write(res_asc)
            logger.info(f"读到条码{res_asc}")
            if check_string2(res_asc):
                # 提取型号、生产日期
                code=res_asc
                parts = code.split('+')
                model = parts[4] if len(parts) > 4 else None
                productDate = parts[2] if len(parts) > 4 else None
                # 尝试将其转换为正确的日期时间格式
                try:
                    # 假设前两位是年份，中间两位是月份，后两位是日期
                    year = 2000 + int(productDate[:2])
                    month = int(productDate[2:4])
                    day = int(productDate[4:])
                    # 检查日期是否合法
                    if 1 <= month <= 12 and 1 <= day <= 31:
                        productDate = datetime.datetime(year, month, day)
                    else:
                        # 处理不合法的日期，例如设置为默认值
                        productDate = None
                except ValueError:
                    # 处理转换失败的情况，例如设置为默认值
                    productDate = None
                logger.info(f"根据扫描到的条码解析到了型号：{model}")
                logger.info(f"根据扫描到的条码解析到了生产日期：{productDate}")
                modbus_client.modbus_write("jcq", 1, 141, 1)
                modbus_client.modbus_write("jcq", location, 140, 1)
                # modbus_client.write_ascii_string(145, res_asc)

                # 读取 user_cache.txt 中的 UserID
                user_cache_file = "user_cache.txt"
                with open(user_cache_file, "r") as file:
                    user_id = file.read()
                user_name=""
                if user_id:
                    # 查询 User 表中的 UserName
                    user = session.query(User).filter_by(UserID=user_id).first()
                    if user:
                        user_name = user.UserName
                    else:
                        user_name = "未知用户"  # 如果没有找到对应用户，可以设置为默认值

                # 查询是否已经存在相同的 SolderCode 数据
                existing_solder = session.query(Solder).filter(Solder.SolderCode == code).first()
                if existing_solder and (existing_solder.StationID==190 or existing_solder.Station.StationID==191):
                    # 更新现有记录
                    existing_solder.SolderCode = code
                    existing_solder.Model = model
                    existing_solder.ProductDate = productDate
                    existing_solder.InTimes += 1
                    existing_solder.StorageUser = user_name
                    existing_solder.StorageDateTime = datetime.now()
                    if user_name:
                        # 创建 SolderFlowRecord 记录
                        solder_flow_record = SolderFlowRecord(
                            SolderCode=code,
                            UserID=user_id,
                            UserName=user_name,
                            DateTime=datetime.now(),
                            Type="请求入柜"  # 设置操作类型为“更新入柜”
                        )
                        session.add(solder_flow_record)
                        session.commit()
                    # 提交更新的 Solder 数据
                    session.commit()
                    solder_data.append(existing_solder)
                    logger.info(f"当前Station存在锡膏，已更新 Solder 扫码入库：{code}")
                else:
                    #查询此前该锡膏的入柜次数
                    inTimes=session.query(SolderFlowRecord).join(Solder,Solder.SolderCode==SolderFlowRecord.SolderCode).filter(SolderFlowRecord.Type=="请求入柜").count()
                    # 插入新的 Solder 数据
                    sql_data = Solder(
                        SolderCode=code,
                        Model=model,
                        ProductDate=productDate,
                        InTimes=inTimes+1,
                        BackLCTimes=0,
                        StationID=190,
                        StorageUser=user_name,
                        StorageDateTime=datetime.now()
                    )
                    if user_name:
                        # 创建 SolderFlowRecord 记录
                        solder_flow_record = SolderFlowRecord(
                            SolderCode=code,
                            UserID=user_id,
                            UserName=user_name,
                            DateTime=datetime.now(),
                            Type="请求入柜"  # 设置操作类型为“请求入柜”
                        )
                        session.add(solder_flow_record)
                        session.commit()
                    session.add(sql_data)
                    session.commit()
                    solder_data.append(sql_data)
                    logger.info(f"新 Solder 数据添加成功：{code}")
                # 提交事务
                session.commit()
                logger.info(f"{code}已经从 '扫码区' 取出，放入冷藏区")

            else:
                logger.info(f"异常条码{res_asc}")
                modbus_client.modbus_write("jcq", 2, 141, 1)
                modbus_client.modbus_write("jcq", location, 140, 1)
        else:
            modbus_client.modbus_write("jcq", 0, 140, 1)
            modbus_client.modbus_write("jcq", 0, 141, 1)
            modbus_client.modbus_write("jcq", 0, 145, 25)
    except Exception as e:
        session.close()
        logger.error(f"Error in periodic task (Modbus read/write): {e}")
        return
    except TimeoutError:
        logger.warning("任务执行超时，跳过当前任务")

    #各个位置取放时交互信息
    try:
        # 查询 Station 表并插入 Solder 数据逻辑
        qu = modbus_client.modbus_read("jcq", 100, 1)
        fang = modbus_client.modbus_read("jcq", 101, 1)
        result = modbus_client.modbus_read("jcq", 102, 1)
        sta_types = [f"移动模组[{qu[0]}]", f"移动模组[{fang[0]}]"]
        # 获取对应的 Station 对象
        station_qu = StaType_station_dict.get(sta_types[0])
        logger.info(f"打算从点位{station_qu}中取出")
        station_fang = StaType_station_dict.get(sta_types[1])
        logger.info(f"打算放到点位{station_fang}中")
        if result[0] == 2:  # 取完成
            if station_qu:
                # solder_record = session.query(Solder).filter(Solder.StationID == station_qu).first()
                # #先把取出来的锡膏缓存
                # solder_record.StationID=None
                # session.query(Solder).filter(Solder.StationID == station_qu).update({Solder.StaionID:None})
                # session.commit()
                # solder_cache.append(solder_record)
                # solder_flag=session.query(Solder).filter(Solder.StationID == station_qu).all()
                # flag=True if solder_flag else False
                # logger.info(f"成功从{station_qu}取出锡膏，现在{station_qu}中是否还有锡膏：{flag}")
                if station_qu>=201 and station_qu<=539: #从冷藏区取出，准备出库
                    session.query(Solder).filter(Solder.StationID == station_qu).update({
                        Solder.ReadyOutDateTime: datetime.now() #准备出库时间，用来回冷藏
                    }, synchronize_session=False)
                    session.commit()

                if station_qu >= 603 and station_qu <= 660:
                    solder_record = session.query(Solder).filter(Solder.StationID == station_qu).first()
                    if solder_record:
                        solder_model_record = session.query(SolderModel).filter(
                            SolderModel.Model == solder_record.Model).first()
                        if solder_model_record:
                            modbus_client.write_float(solder_model_record.StirSpeed,1522)
                            modbus_client.write_float(solder_model_record.StirTime,1526)
                            logger.info(f"{solder_record.SolderCode}在搅拌区设置搅拌参数成功 时间{solder_model_record.StirSpeed}速度{solder_model_record.StirTime}")
                        else:
                            logger.error(f"{solder_record.SolderCode}在搅拌区设置搅拌参数出错 未找到solder_model_record")
                modbus_client.modbus_write("jcq", qu[0], 105, 1)
                modbus_client.modbus_write("jcq", fang[0], 106, 1)
                modbus_client.modbus_write("jcq", result[0], 107, 1)
                logger.info(f"状态{result[0]} :从{qu[0]}移动到{fang[0]}")

            else:
                logger.error(f"没有找到符合 StaType '{station_qu}' 的 StationID")

        if result[0] == 4:  # 放完成
            if station_qu and station_fang:
                modbus_client.modbus_write('jcq', 0, station_fang,1)
                modbus_client.modbus_write("jcq", 1, station_qu, 1)
                station_qu_status=modbus_client.modbus_read("jcq", station_qu,1)[0]
                station_fang_status = modbus_client.modbus_read("jcq", station_fang, 1)[0]
                logger.info(f"{station_qu}点位的状态：{station_qu_status}")
                logger.info(f"{station_fang}点位的状态：{station_fang_status}")
                solder_fang_station_cache=station_fang
                solder_qu_station_cache = station_qu
                logger.info(f"正在从{station_qu}往{station_fang}放，把这2个点位缓存起来{solder_qu_station_cache}、{solder_fang_station_cache}")
                solder_record = next((solder for solder in solders if solder.StationID == station_qu), None)
                # solder_record=solder_cache[0]
                # solder_cache.pop(0)
                # logger.info(f"1----------------{solder_record}")
                if solder_record:
                    code = solder_record.SolderCode  # 使用查询到的 SolderCode
                    # logger.info(f"2----------------{code}")
                    from sqlalchemy.orm.exc import NoResultFound
                    from sqlalchemy.exc import IntegrityError

                    try:
                        # 查询是否已经存在相同的 SolderCode 或 StationID
                        existing_record = session.query(Solder).filter(
                            (Solder.SolderCode == code) | (Solder.StationID == station_fang)
                        ).first()

                        if existing_record:
                            # 如果存在相同的 SolderCode 或 StationID
                            if existing_record.SolderCode == code and existing_record.StationID == station_fang:
                                # 如果 SolderCode 和 StationID 都一致，更新数据
                                # logger.info(f"SolderCode {code} 和 StationID {station_fang} 已存在，正在更新数据。")
                                existing_record.StorageDateTime = datetime.now()
                                session.commit()
                            elif existing_record.SolderCode == code:
                                # 如果只有 SolderCode 存在，更新 StationID 和 StorageDateTimedianwei
                                # logger.info(f"SolderCode {code} 已存在，正在更新 StationID 和数据。")
                                existing_record.StationID = station_fang
                                existing_record.StorageDateTime = datetime.now()
                                if station_fang in range(201,540):
                                    existing_record.BackLCTimes += 1
                                session.commit()
                            elif existing_record.StationID == station_fang:
                                # 如果只有 StationID 存在，更新 SolderCode 和数据
                                # logger.info(f"StationID {station_fang} 已存在，正在更新 SolderCode 和数据。")
                                existing_record.SolderCode = code
                                existing_record.StorageDateTime = datetime.now()
                                session.commit()
                        else:
                            # 如果不存在相同的 SolderCode 和 StationID，插入新数据
                            inTimes=session.query(SolderFlowRecord).join(Solder,Solder.SolderCode==SolderFlowRecord.SolderCode).filter(SolderFlowRecord.Type=="请求入柜").count()
                            # 读取 user_cache.txt 中的 UserID
                            user_cache_file = "user_cache.txt"
                            with open(user_cache_file, "r") as file:
                                user_id = file.read()
                            user_name = ""
                            if user_id:
                                # 查询 User 表中的 UserName
                                user = session.query(User).filter_by(UserID=user_id).first()
                                if user:
                                    user_name = user.UserName
                                else:
                                    user_name = "未知用户"  # 如果没有找到对应用户，可以设置为默认值
                            sql_data = Solder(
                                SolderCode=code,
                                Model=solder_record.Model,
                                InTimes=inTimes+1,
                                BackLCTimes=0,
                                StationID=station_fang,
                                StorageUser=user_name,
                                StorageDateTime=datetime.now()
                            )
                            session.add(sql_data)
                            session.commit()  # 提交新记录

                        # 放冷藏区,写入库记录
                        if 201 <= station_fang <= 539:
                            solder = session.query(Solder).filter(
                                Solder.SolderCode == solder_record.SolderCode).first()
                            # 更新 SolderFlowRecord 表中的 Type 字段为 '入柜'
                            # 查询到最新的 SolderFlowRecord 记录
                            # logger.info(f"4----------------入柜")
                            solder_flow_record = session.query(SolderFlowRecord).filter(
                                SolderFlowRecord.SolderCode == code).order_by(
                                SolderFlowRecord.DateTime.desc()).first()
                            # logger.info(f"5----------------{solder_flow_record}")
                            if solder_flow_record:  # 确保找到了记录
                                # 更新实例的字段
                                solder_flow_record.Type = '入柜'  # 你可以在这里使用你需要的中文或字段
                                solder_flow_record.DateTime = datetime.now()
                                logger.info("发送冷冻日志s")
                                # send_freeze_log(rid=code,user_login=None)
                                logger.info("发送冷冻日志e")

                            else:
                                logger.warning("===============入柜状态4：未找到solderflowrecord,即该锡膏之前未入库过===============")

                        # 放回温区
                        if 603 <= station_fang <= 660:
                            # 放到回温区，那回温开始时间就从此刻算起了
                            # 更新Solder表中这个solder_record的RewarmStartDateTime
                            session.query(Solder).filter(Solder.SolderCode == code).update({
                                Solder.RewarmStartDateTime: datetime.now()
                            }, synchronize_session=False)
                            session.commit()
                            logger.info("发送回温日志")
                            logger.info("发送回温日志")
                        session.commit()
                        modbus_client.modbus_write("jcq", qu[0], 105, 1)
                        modbus_client.modbus_write("jcq", fang[0], 106, 1)
                        modbus_client.modbus_write("jcq", result[0], 107, 1)
                        logger.info(f"放完成:状态{result[0]} :从{qu[0]}移动到{fang[0]}")
                    except IntegrityError as e:
                        # 捕获 IntegrityError 错误，处理唯一键冲突
                        session.rollback()  # 回滚事务
                        logger.error(f"数据库操作失败，发生唯一键冲突：{e}")
                    except Exception as e:
                        # 捕获其他异常
                        session.rollback()
                        logger.error(f"发生错误：{e}")
                else:
                    logger.error(f"没有找到 StationID 等于 '{station_qu}' 的 Solder 记录")
            else:
                logger.error(f"没有找到符合 StaType '{station_qu}' 的 StationID")

        if result[0] == 5:  # 锡膏被人取走完成
            if station_fang:
                # 根据查询到的 StationID，查询 Solder 表中的记录
                solder_record = session.query(Solder).filter(Solder.StationID == station_fang).first()
                if solder_record:
                    solder_code = solder_record.SolderCode  # 获取 SolderCode
                    # 删除 Solder 表中对应 SolderCode 的记录
                    session.query(Solder).filter(Solder.SolderCode == solder_code).delete()

                    # 更新 SolderFlowRecord 表中的 Type 字段为 '出柜'
                    # 查询到最新的 SolderFlowRecord 记录
                    solder_flow_record = session.query(SolderFlowRecord).filter(
                        SolderFlowRecord.SolderCode == solder_code).order_by(
                        SolderFlowRecord.DateTime.desc()).first()

                    if solder_flow_record:  # 确保找到了记录
                        # 更新实例的字段
                        solder_flow_record.Type = '出柜'
                        solder_flow_record.DateTime = datetime.now()
                    else:
                        logger.warning("===============出柜状态5：未找到solderflowrecord===============")
                    # 提交事务
                    session.commit()
                    logger.info(f"条码` '{solder_code}' 已出柜，并且已删除")
                    modbus_client.modbus_write("jcq", qu[0], 105, 1)
                    modbus_client.modbus_write("jcq", fang[0], 106, 1)
                    modbus_client.modbus_write("jcq", result[0], 107, 1)
                    logger.info(f"人工取走:状态{result[0]} :从{qu[0]}移动到{fang[0]}")
                else:
                    logger.error(f"{station_fang}点位没有找到 Solder 记录")
            else:
                logger.error(f"没有找到符合 StaType '{station_fang}' 的 Station 记录")


    except Exception as e:
        session.close()
        logger.error(f"Error in periodic task (Station/Solder logic): {e}")
        return
    except TimeoutError:
        logger.warning("任务执行超时，跳过当前任务")

    #冷藏区 回温区 待取区 异常区 取料区 状态变换
    try:
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
        fang_603_660 = 1 if 603 <= solder_fang_station_cache <= 660 else 0
        fang_803_840 = 1 if 803 <= solder_fang_station_cache <= 840 else 0
        for start, end in ranges:
            solder_data = [
                (solder, model_data) for solder, model_data in solder_data_all
                if start <= solder.StationID <= end
            ]
            # 每个区域的存在锡膏的点位
            solder_station_ids = {int(solder.StationID) for solder, _ in solder_data}
            # 获取当前时间并转换为本地时间（Asia/Shanghai）UTC格式
            local_time = datetime.now()  # 假设这是本地时间，没有时区信息
            local_time = pytz.UTC.localize(local_time)
            #检查出库是否超时
            if start == 603 or start == 803:
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
                        amount = model_data.RewarmNum - count_by_model[model_data.Model]["count_603_660"] - fang_603_660
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
                        if solder_storage_time.tzinfo is None:
                            solder_storage_time = pytz.UTC.localize(solder_storage_time)
                        timeout_field = "RewarmMaxTime"
                        check_field = "RewarmTime"
                        region_name = "回温区"

                        # RewarmMaxTime 超时判断
                        timeout_threshold = local_time - timedelta(minutes=getattr(model_data, timeout_field))
                        if solder_storage_time <= timeout_threshold:
                            logger.info(f"超时：{region_name}{timeout_threshold.strftime('%Y-%m-%d %H:%M:%S %z')} || {int(solder.StationID)} || 设定超时时间{getattr(model_data, timeout_field)}")
                            modbus_client.modbus_write("jcq", 5, int(solder.StationID), 1)
                            continue  # 超时后跳过后续操作

                        # 状态变换判断
                        time_delta = timedelta(
                            minutes=getattr(model_data, check_field) if check_field == "RewarmTime" else 0
                        )
                        check_threshold = local_time - time_delta
                        # 回温结束时间算出来之后，那就要填到solder表中对应的记录中去
                        session.query(Solder).filter(Solder.SolderCode == solder.SolderCode).update({
                            Solder.RewarmEndDateTime: check_threshold
                        }, synchronize_session=False)
                        session.commit()
                        modbus_value = 2 if solder_storage_time <= check_threshold else 0
                        logger.info(
                            f"状态变换：{region_name} || 存储时间{solder_storage_time} || 回温结束时间{check_threshold} || 点位{int(solder.StationID)} || 写入值{modbus_value}"
                        )
                        modbus_client.modbus_write("jcq", modbus_value, int(solder.StationID), 1)

            if start == 803:
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
                    huiwen_daiqu = counts["count_803_840"]+fang_803_840 < ready_out_num
                    logger.info(f"设置 huiwen_daiqu = {huiwen_daiqu} for Model {model}")

                    # 根据查询结果设置 lengcang_huiwen 的值
                    lengcang_huiwen = counts["count_603_660"]+fang_603_660 < rewarm_num
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
                        if station_id not in solder_station_ids and station_id != solder_fang_station_cache:
                            modbus_client.modbus_write("jcq", 0, station_id, 1)
                else:
                    for station_id in range(603, 661):  # 范围 601 到 660
                        if station_id not in solder_station_ids and station_id != solder_fang_station_cache:
                            modbus_client.modbus_write("jcq", 1, station_id, 1)
            if 803 == start:
                if huiwen_daiqu == False:
                    for station_id in range(803, 841):  # 范围 601 到 660
                        if station_id not in solder_station_ids and station_id != solder_fang_station_cache:
                            modbus_client.modbus_write("jcq", 0, station_id, 1)
                else:
                    for station_id in range(803, 841):  # 范围 801 到 840
                        if station_id not in solder_station_ids and station_id != solder_fang_station_cache:
                            modbus_client.modbus_write("jcq", 1, station_id, 1)
            if 201 == start :
                for station_id in range(201, 539):  # 范围 601 到 660
                    if station_id not in solder_station_ids and station_id != solder_fang_station_cache:
                        modbus_client.modbus_write("jcq", 1, station_id, 1)
    except Exception as e:
        session.close()
        logger.error(f"Error in query_solder_and_station task: {e}")
    except TimeoutError:
        logger.warning("任务执行超时，跳过当前任务")
    finally:
        end_time = time.time()
        # 计算任务执行时间
        execution_time = end_time - start_time
        logger.info(f"任务执行时间：{execution_time} 秒")
        session.close()

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

def lc_mode():
    session = db_instance.get_session()
    # solders = process_solders(100, session)
    solders = session.query(Solder).filter(Solder.OrderDateTime==None).all()
    # 扫码位置成功扫码
    try:
        # 读取 Modbus 数据逻辑
        result = modbus_client.modbus_read("jcq", 111, 1)
        if result[0] == 1:
            location = modbus_client.modbus_read("jcq", 110, 1)[0]
            # res_asc = modbus_client.read_float_ASCII(115, 139)
            # 提取字母和数字部分
            # res_asc = re.sub(r'[^a-zA-Z0-9&.-]', '', res_asc)
            res_asc = scan()
            # 清空文件内容
            with open(file_path, "w") as file:
                file.truncate(0)
            # 将 res_asc 写入本地文件
            with open(file_path, "w") as file:
                file.write(res_asc)
            logger.info(f"读到条码{res_asc}")
            if check_string2(res_asc):
                modbus_client.modbus_write("jcq", 1, 141, 1)
                modbus_client.modbus_write("jcq", location, 140, 1)
                modbus_client.write_ascii_string(145, res_asc)
                # elif station_qu == 190 or station_qu == 191:
                #     with open(file_path, "r") as file:
                #         code = file.read()
                # 提取型号：在第一个 '&' 和第二个 '&' 之间
                code = res_asc
                parts = code.split('+')
                model = parts[4] if len(parts) > 4 else None

                # 查询是否已经存在相同的 SolderCode 数据
                existing_solder = session.query(Solder).filter(Solder.SolderCode == code).first()
                if existing_solder and (existing_solder.StationID == 190 or existing_solder.Station.StationID == 191):
                    # 更新现有记录
                    existing_solder.SolderCode = code
                    existing_solder.Model = model
                    existing_solder.BackLCTimes = 0
                    existing_solder.StorageDateTime = datetime.now()

                    # 读取 user_cache.txt 中的 UserID
                    user_cache_file = "user_cache.txt"
                    with open(user_cache_file, "r") as file:
                        user_id = file.read()

                    if user_id:
                        # 查询 User 表中的 UserName
                        user = session.query(User).filter_by(UserID=user_id).first()
                        if user:
                            user_name = user.UserName
                        else:
                            user_name = "未知用户"  # 如果没有找到对应用户，可以设置为默认值

                        # 创建 SolderFlowRecord 记录
                        solder_flow_record = SolderFlowRecord(
                            SolderCode=code,
                            UserID=user_id,
                            UserName=user_name,
                            DateTime=datetime.now(),
                            Type="请求入柜"  # 设置操作类型为“更新入柜”
                        )
                        session.add(solder_flow_record)
                        session.commit()

                    # 提交更新的 Solder 数据
                    session.commit()
                    logger.info(f"当前Station存在锡膏，已更新 Solder 扫码入库：{code}")
                else:
                    # 插入新的 Solder 数据
                    sql_data = Solder(
                        SolderCode=code,
                        Model=model,
                        BackLCTimes=0,
                        StationID=190,
                        StorageDateTime=datetime.now()
                    )
                    # 读取 user_cache.txt 中的 UserID
                    user_cache_file = "user_cache.txt"
                    with open(user_cache_file, "r") as file:
                        user_id = file.read()

                    if user_id:
                        # 查询 User 表中的 UserName
                        user = session.query(User).filter_by(UserID=user_id).first()
                        if user:
                            user_name = user.UserName
                        else:
                            user_name = "未知用户"  # 如果没有找到对应用户，可以设置为默认值

                        # 创建 SolderFlowRecord 记录
                        solder_flow_record = SolderFlowRecord(
                            SolderCode=code,
                            UserID=user_id,
                            UserName=user_name,
                            DateTime=datetime.now(),
                            Type="请求入柜"  # 设置操作类型为“请求入柜”
                        )
                        session.add(solder_flow_record)
                        session.commit()

                    session.add(sql_data)
                    session.commit()
                    logger.info(f"新 Solder 数据添加成功：{code}")
                # 提交事务
                session.commit()
                logger.info(f"{code}已经从 '扫码区' 取出，放入冷藏区")

            else:
                logger.info(f"异常条码{res_asc}")
                modbus_client.modbus_write("jcq", 2, 141, 1)
                modbus_client.modbus_write("jcq", location, 140, 1)
        else:
            modbus_client.modbus_write("jcq", 0, 140, 1)
            modbus_client.modbus_write("jcq", 0, 141, 1)
            modbus_client.modbus_write("jcq", 0, 145, 25)
    except Exception as e:
        session.close()
        logger.error(f"Error in periodic task (Modbus read/write): {e}")
        return
    except TimeoutError:
        logger.warning("任务执行超时，跳过当前任务")
    stations = session.query(Station).all()
    StaType_station_dict = {station.StaType: station.StationID for station in stations}

    # 各个位置取放时交互信息
    try:
        # 查询 Station 表并插入 Solder 数据逻辑
        qu = modbus_client.modbus_read("jcq", 100, 1)
        fang = modbus_client.modbus_read("jcq", 101, 1)
        result = modbus_client.modbus_read("jcq", 102, 1)
        sta_types = [f"移动模组[{qu[0]}]", f"移动模组[{fang[0]}]"]
        # 获取对应的 Station 对象
        station_qu = StaType_station_dict.get(sta_types[0])
        station_fang = StaType_station_dict.get(sta_types[1])
        if result[0] == 2:  # 取完成
            if station_qu:
                logger.warning(f"solders type: {type(solders)}")
                solder_record = next((solder for solder in solders if solder.StationID == station_qu), None)
                if station_qu >= 201 and station_qu <= 539:  # 从冷藏区取出，准备出库
                    session.query(Solder).filter(Solder.StationID == station_qu).update({
                        Solder.ReadyOutDateTime: datetime.now()  # 准备出库时间，用来回冷藏
                    }, synchronize_session=False)
                    session.commit()

                if station_qu >= 601 and station_qu <= 660:
                    # solder_record = session.query(Solder).filter(Solder.StationID == station_qu).first()
                    if solder_record:
                        solder_model_record = session.query(SolderModel).filter(
                            SolderModel.Model == solder_record.Model).first()
                        if solder_model_record:
                            modbus_client.write_float(solder_model_record.StirSpeed, 1522)
                            modbus_client.write_float(solder_model_record.StirTime, 1526)
                            logger.info(
                                f"{solder_record.SolderCode}1在搅拌区设置搅拌参数成功 时间{solder_model_record.StirSpeed}速度{solder_model_record.StirTime}")
                        else:
                            logger.error(
                                f"{solder_record.SolderCode}在搅拌区设置搅拌参数出错 未找到solder_model_record")
                    # send_mix_log(rid=None, user_login=None)
            else:
                logger.error(f"没有找到符合 StaType '{station_qu}' 的 StationID")
        logger.warning(f"0--------{station_fang}--------{station_qu}------------{result}------------{result[0]}")
        if result[0] == 4:  # 放完成
            if station_qu and station_fang:
                logger.info("++++++++++++++++++++++++++++++++")
                modbus_client.modbus_write('jcq', 0, station_fang, 1)
                modbus_client.modbus_write("jcq", 1, station_qu, 1)
                # 从 Solder 表中查询 StationID 等于当前 station 的记录
                # logger.info(f"0--------{station_fang}--------{station_qu}")
                solder_record = next((solder for solder in solders if solder.StationID == station_qu), None)
                # logger.info(f"1----------------{solder_record}")
                if solder_record:
                    code = solder_record.SolderCode  # 使用查询到的 SolderCode
                    # logger.info(f"2----------------{code}")
                    from sqlalchemy.orm.exc import NoResultFound
                    from sqlalchemy.exc import IntegrityError

                    try:
                        # 查询是否已经存在相同的 SolderCode 或 StationID
                        existing_record = session.query(Solder).filter(
                            (Solder.SolderCode == code) | (Solder.StationID == station_fang)
                        ).first()

                        if existing_record:
                            # 如果存在相同的 SolderCode 或 StationID
                            if existing_record.SolderCode == code and existing_record.StationID == station_fang:
                                # 如果 SolderCode 和 StationID 都一致，更新数据
                                # logger.info(f"SolderCode {code} 和 StationID {station_fang} 已存在，正在更新数据。")
                                existing_record.StorageDateTime = datetime.now()
                                session.commit()
                                # logger.info(f"Solder 数据已更新：SolderCode={code}, StationID={station_fang}")
                            elif existing_record.SolderCode == code:
                                # 如果只有 SolderCode 存在，更新 StationID 和 StorageDateTimedianwei
                                # logger.info(f"SolderCode {code} 已存在，正在更新 StationID 和数据。")
                                existing_record.StationID = station_fang
                                existing_record.StorageDateTime = datetime.now()
                                session.commit()
                                # logger.info(f"Solder 数据已更新：SolderCode={code}, StationID={station_fang}")
                            elif existing_record.StationID == station_fang:
                                # 如果只有 StationID 存在，更新 SolderCode 和数据
                                # logger.info(f"StationID {station_fang} 已存在，正在更新 SolderCode 和数据。")
                                existing_record.SolderCode = code
                                existing_record.StorageDateTime = datetime.now()
                                session.commit()
                                # logger.info(f"Solder 数据已更新：SolderCode={code}, StationID={station_fang}")
                        else:
                            # 如果不存在相同的 SolderCode 和 StationID，插入新数据
                            sql_data = Solder(
                                SolderCode=code,
                                Model=solder_record.Model,
                                BackLCTimes=0,
                                StationID=station_fang,
                                StorageDateTime=datetime.now()
                            )
                            session.add(sql_data)
                            session.commit()  # 提交新记录
                            # logger.info(f"新Solder数据添加成功：SolderCode={code}, StationID={station_fang}")

                    except IntegrityError as e:
                        # 捕获 IntegrityError 错误，处理唯一键冲突
                        session.rollback()  # 回滚事务
                        logger.error(f"数据库操作失败，发生唯一键冲突：{e}")
                    except Exception as e:
                        # 捕获其他异常
                        session.rollback()
                        logger.error(f"发生错误：{e}")
                    # logger.info(f"3----------------{station_fang}")
                    # 放冷藏区
                    if 201 <= station_fang <= 539:
                        solder = session.query(Solder).filter(
                            Solder.SolderCode == solder_record.SolderCode).first()
                        if solder:
                            solder.BackLCTimes += 1
                            session.commit()  # 提交更改
                            # logger.info(f"BackLCTimes 自增后: {solder_record.BackLCTimes}")
                        else:
                            logger.error(f"BackLCTimes 自增出错，未找到条码{solder_record.SolderCode}")
                        # 更新 SolderFlowRecord 表中的 Type 字段为 '入柜'
                        # 查询到最新的 SolderFlowRecord 记录
                        # logger.info(f"4----------------入柜")
                        solder_flow_record = session.query(SolderFlowRecord).filter(
                            SolderFlowRecord.SolderCode == code).order_by(
                            SolderFlowRecord.DateTime.desc()).first()
                        # logger.info(f"5----------------{solder_flow_record}")
                        if solder_flow_record:  # 确保找到了记录
                            # 更新实例的字段
                            solder_flow_record.Type = '入柜'  # 你可以在这里使用你需要的中文或字段
                            solder_flow_record.DateTime = datetime.now()
                            # logger.info("发送冷冻日志s")
                            # send_freeze_log(rid=code, user_login=None)
                            # logger.info("发送冷冻日志e")
                        else:
                            logger.warning("===============入柜状态4：未找到solderflowrecord===============")
                    if 601 <= station_fang <= 660:
                        logger.info("发送回温日志")
                        # send_reheat_log(rid=code, user_login=None)
                        # logger.info("发送回温日志")
                    session.commit()
                    logger.info(f"条码 '{solder_record.SolderCode}' 从{qu}移动到{fang} 完成")
                else:
                    logger.error(f"没有找到 StationID 等于 '{station_qu}' 的 Solder 记录")
            else:
                logger.error(f"没有找到符合 StaType '{station_qu}' 的 StationID")

        if result[0] == 5:  # 锡膏被人取走完成
            logger.info(f"状态5-----------{station_qu}--------------{station_fang}--------------取走锡膏")
            if station_fang:
                # 根据查询到的 StationID，查询 Solder 表中的记录
                solder_record = session.query(Solder).filter(Solder.StationID == station_fang).first()
                if solder_record:
                    solder_code = solder_record.SolderCode  # 获取 SolderCode

                    # 删除 Solder 表中对应 SolderCode 的记录
                    session.query(Solder).filter(Solder.SolderCode == solder_code).delete()

                    # 更新 SolderFlowRecord 表中的 Type 字段为 '出柜'
                    # 查询到最新的 SolderFlowRecord 记录
                    solder_flow_record = session.query(SolderFlowRecord).filter(
                        SolderFlowRecord.SolderCode == solder_code).order_by(
                        SolderFlowRecord.DateTime.desc()).first()

                    if solder_flow_record:  # 确保找到了记录
                        # 更新实例的字段
                        solder_flow_record.Type = '出柜'
                        solder_flow_record.DateTime = datetime.now()
                    else:
                        logger.warning("===============出柜状态5：未找到solderflowrecord===============")
                    # 提交事务
                    session.commit()
                    logger.info(f"条码` '{solder_code}' 已删除并标记为出柜")
                else:
                    logger.error(f"{station_fang}点位没有找到 Solder 记录")
            else:
                logger.error(f"没有找到符合 StaType '{station_fang}' 的 Station 记录")
        modbus_client.modbus_write("jcq", qu[0], 105, 1)
        modbus_client.modbus_write("jcq", fang[0], 106, 1)
        modbus_client.modbus_write("jcq", result[0], 107, 1)
        logger.info(f"状态{result[0]} :从{qu[0]}移动到{fang[0]}")
    except Exception as e:
        session.close()
        logger.error(f"Error in periodic task (Station/Solder logic): {e}")
        return
    except TimeoutError:
        logger.warning("任务执行超时，跳过当前任务")
    finally:
        # 假设 solders 是你的对象列表
        filtered_solders = [solder for solder in solders if 201 <= solder.StationID <= 539]
        # 遍历过滤后的列表
        for solder in filtered_solders:
            # 执行需要的操作，例如打印或其他操作
            modbus_client.modbus_write("jcq", 0, solder.StationID, 1)

        session.close()
    return

def run_scheduler():
    mode = read_mode()
    if mode == 0:
        lc_mode()
        #scheduler.add_job(id='lc_mode', func=lc_mode, trigger='interval', seconds=2, max_instances=100)
    elif mode == 1:
        move_update(mode=mode)
        process_solders()
        # scheduler.add_job(id='move_update', func=move_update, trigger='interval', seconds=2, max_instances=100,kwargs={'mode': mode})
        # scheduler.add_job(id='move_update', func=move_update, trigger='interval', seconds=2, max_instances=100,kwargs={'mode': mode})

# 初始化调度器
def init_scheduler(app):
    scheduler.init_app(app)
    # if mode == 0:
    #     scheduler.add_job(id='lc_mode', func=lc_mode, trigger='interval', seconds=2, max_instances=100)
    # elif mode == 1:
    #     scheduler.add_job(id='move_update', func=move_update, trigger='interval', seconds=2, max_instances=100,kwargs={'mode': mode})
    # else:
    #     scheduler.add_job(id='move_update', func=move_update, trigger='interval', seconds=2, max_instances=100,kwargs={'mode': mode})
    scheduler.add_job(id='task_heartbeat', func=task_heartbeat, trigger='interval', seconds=1, max_instances=1)
    scheduler.add_job(id='run_scheduler', func=run_scheduler, trigger='interval', seconds=2, max_instances=1)
    if not scheduler.running:
        # 确保调度器正在运行，如果不是可以重启调度器或处理该情况
        scheduler.start()