from datetime import datetime, timedelta
from sqlalchemy import or_

from modbus.client import modbus_client
from modbus.modbus_addresses import ADDR_ROBOT_STATUS, ADDR_ROBOT_CONFIRM
from modbus.modbus_addresses import region_addr_to_region_name
from modbus.modbus_addresses import in_region_cold, in_region_rewarm, in_region_wait
from util.logger import logger
from models import SolderModel, SolderFlowRecord, Station, Solder
from util.db_connection import db_instance


def task_robot_impl(robot_get, robot_put, robot_act):
    with db_instance.get_session() as db_session:

        stations = db_session.query(Station).all()
        StaType_station_dict = {station.StaType: station.StationID for station in stations} # 移动模组[id]: 点位地址

        station_get = StaType_station_dict.get(f"移动模组[{robot_get}]")
        station_put = StaType_station_dict.get(f"移动模组[{robot_put}]")
        station_get_status = modbus_client.modbus_read("jcq", station_get, 1)[0] if station_get else -1
        station_put_status = modbus_client.modbus_read("jcq", station_put, 1)[0] if station_put else -1
        logger.info(f"机械臂状态 move_id_get:{robot_get} move_id_put:{robot_put} action:{robot_act}")
        logger.info(f"取库位号: {region_addr_to_region_name(station_get)}{station_get} 状态{station_get_status}")
        logger.info(f"放库位号: {region_addr_to_region_name(station_put)}{station_put} 状态{station_put_status}")
        solder_moving = db_session.query(Solder
                                 ).filter(or_(Solder.StationID == station_get, Solder.StationID == station_put)
                                 ).scalar()
        solder_moving_model = db_session.query (SolderModel
                                        ).filter(SolderModel.Model == (solder_moving.Model)
                                        ).scalar() if solder_moving else None
        if not solder_moving:
            return


        if robot_act == 2 and station_get: # 取完成
            if in_region_cold(station_get): #从冷藏区取出，准备出库
                #更新出库时间，用来回冷藏
                solder_moving.ReadyOutDateTime = datetime.now()
                logger.info(f"冷藏区 {station_get} 锡膏号 {solder_moving.SolderCode} 更新出冷藏区时间 {datetime.now()}")

            elif in_region_rewarm(station_get) and not in_region_cold(station_put):
                if solder_moving_model:
                    modbus_client.write_float(solder_moving_model.StirSpeed, 1522)
                    modbus_client.write_float(solder_moving_model.StirTime,  1526)
                    logger.info(f"{solder_moving.SolderCode}在搅拌区设置搅拌参数成功 时间{solder_moving_model.StirTime}速度{solder_moving_model.StirSpeed}")
                else:
                    logger.error(f"{solder_moving.SolderCode}在搅拌区设置搅拌参数出错 未找到solder_model_record")


        elif robot_act == 4 and station_get and station_put: # 放完成
            modbus_client.modbus_write("jcq", 0, station_put, 1)
            modbus_client.modbus_write("jcq", 0, station_get, 1)
            solder_moving.StationID = station_put

            if in_region_cold(station_put):
                solder_moving.StorageDateTime = datetime.now()
                solder_moving.OrderUser = None
                solder_moving.OrderDateTime = None
                solder_moving.BackLCTimes += 1
                new_solderflowrecord = SolderFlowRecord(
                    SolderCode=solder_moving.SolderCode,
                    DateTime=datetime.now(),
                    Type="进冷藏区"
                )
                db_session.add(new_solderflowrecord)

            elif in_region_rewarm(station_put):
                now_date_time = datetime.now()
                solder_moving.RewarmStartDateTime = now_date_time
                solder_moving.RewarmEndDateTime = now_date_time + timedelta(minutes=solder_moving_model.RewarmTime)
                new_solderflowrecord = SolderFlowRecord(
                    SolderCode=solder_moving.SolderCode,
                    DateTime=datetime.now(),
                    Type="进回温区"
                )
                db_session.add(new_solderflowrecord)

            elif in_region_wait(station_put):
                new_solderflowrecord = SolderFlowRecord(
                    SolderCode=solder_moving.SolderCode,
                    DateTime=datetime.now(),
                    Type="进待取区"
                )
                db_session.add(new_solderflowrecord)


        elif robot_act == 5:  # 锡膏被人取走完成
            new_solderflowrecord = SolderFlowRecord(
                SolderCode=solder_moving.SolderCode,
                DateTime=datetime.now(),
                Type="出柜"
            )
            db_session.delete(solder_moving)
            db_session.add(new_solderflowrecord)


        db_session.commit()

        modbus_client.modbus_write("jcq", robot_get, ADDR_ROBOT_CONFIRM.GET, 1)
        modbus_client.modbus_write("jcq", robot_put, ADDR_ROBOT_CONFIRM.PUT, 1)
        modbus_client.modbus_write("jcq", robot_act, ADDR_ROBOT_CONFIRM.ACT, 1)


def task_robot():
    """
        读取机械臂状态，执行任务，然后确认
    """
    robot_get = modbus_client.modbus_read("jcq", ADDR_ROBOT_STATUS.GET, 1)[0]
    robot_put = modbus_client.modbus_read("jcq", ADDR_ROBOT_STATUS.PUT, 1)[0]
    robot_act = modbus_client.modbus_read("jcq", ADDR_ROBOT_STATUS.ACT, 1)[0]
    task_robot_impl(robot_get, robot_put, robot_act)
    modbus_client.modbus_write("jcq", robot_get, ADDR_ROBOT_CONFIRM.GET, 1)
    modbus_client.modbus_write("jcq", robot_put, ADDR_ROBOT_CONFIRM.PUT, 1)
    modbus_client.modbus_write("jcq", robot_act, ADDR_ROBOT_CONFIRM.ACT, 1)
