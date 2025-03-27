from apscheduler.executors.pool import ThreadPoolExecutor
from flask_apscheduler import APScheduler
from sqlalchemy import or_

from modbus.client import modbus_client
from models import Station, Solder, SolderModel, SolderFlowRecord, User, Alarm
from util.db_connection import db_instance
from util.logger import logger
from datetime import datetime
# 设置 APScheduler 日志级别为 WARNING

def lc_mode():
    session = db_instance.get_session()
    solders = session.query(Solder).all()
    stations = session.query(Station).all()
    StaType_station_dict = {station.StaType: station.StationID for station in stations}

    # 检查初始化冷藏区，有锡膏的点位状态为0
    lc_solders_stationID_list = session.query(Station.StationID).join(Solder, Solder.StationID == Station.StationID).filter(Solder.StationID.between(201,539)).all()
    for solders_stationID in lc_solders_stationID_list:
        modbus_client.modbus_write("jcq", 0 , solders_stationID, 1)

    warm_solders_list = session.query(Solder).filter(Solder.StationID.between(601,650)).all()
    daiqu_solder_list = session.query(Solder).filter(Solder.StationID.between(801,820)).all()

    for solder in warm_solders_list:
        # 回温区的锡膏状态设成5（异常）
        modbus_client.modbus_write("jcq", 5, int(solder.StationID), 1)
        # 冷藏区找出第一个没锡膏的点位，状态设成1（可放)
        solder_fang_stationID = session.query(Station.StationID).filter(Station.StationID.between(201, 539), Station.StationID.not_in(lc_solders_stationID_list)).first().StationID
        modbus_client.modbus_write("jcq", 1 , solder_fang_stationID, 1)
        lc_solders_stationID_list.append(solder_fang_stationID)

    for solder in daiqu_solder_list:
        # 回温区的锡膏状态设成5（异常）
        modbus_client.modbus_write("jcq", 5, int(solder.StationID), 1)
        # 冷藏区找出第一个没锡膏的点位，状态设成1（可放)
        solder_fang_stationID = session.query(Station.StationID).filter(Station.StationID.between(201, 539), Station.StationID.not_in(lc_solders_stationID_list)).first().StationID
        modbus_client.modbus_write("jcq", 1 , solder_fang_stationID, 1)
        lc_solders_stationID_list.append(solder_fang_stationID)

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
                                    existing_record.BackLCTimes = 1 + int(existing_record.BackLCTimes)
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
                                InTimes=int(inTimes)+1,
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