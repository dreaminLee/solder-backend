from datetime import datetime

from modbus.client import modbus_client
from modbus.modbus_addresses import ADDR_ROBOT_STATUS, ADDR_ROBOT_CONFIRM
from modbus.modbus_addresses import region_addr_to_region_name
from modbus.modbus_addresses import ADDR_REGION_COLD_START, ADDR_REGION_COLD_END
from modbus.modbus_addresses import ADDR_REGION_REWARM_START, ADDR_REGION_REWARM_END
from util.logger import logger
from models import SolderModel, SolderFlowRecord, Station, Solder
from util.db_connection import db_instance


def task_robot():
    robot_get = modbus_client.modbus_read("jcq", ADDR_ROBOT_STATUS.GET, 1)[0]
    robot_put = modbus_client.modbus_read("jcq", ADDR_ROBOT_STATUS.PUT, 1)[0]
    robot_act = modbus_client.modbus_read("jcq", ADDR_ROBOT_STATUS.ACT, 1)[0]

    db_session = db_instance.get_session()

    stations = db_session.query(Station).filter(Station.StationID.notin_([601, 602, 801, 802])).all()
    StaType_station_dict = {station.StaType: station.StationID for station in stations} # 移动模组[id]: 点位地址
    solders = db_session.query(Solder).all()

    station_get = StaType_station_dict.get(f"移动模组[{robot_get}]")
    station_put = StaType_station_dict.get(f"移动模组[{robot_put}]")
    station_get_status = modbus_client.modbus_read("jcq", station_get, 1)[0]
    station_put_status = modbus_client.modbus_read("jcq", station_put, 1)[0]
    logger.info(f"机械臂状态: {robot_act}")
    logger.info(f"取库位号: {region_addr_to_region_name(station_get)}{station_get} 状态{station_get_status}")
    logger.info(f"放库位号: {region_addr_to_region_name(station_put)}{station_put} 状态{station_put_status}")
    solder_getting = next((solder for solder in solders if solder.StationID == station_get))


    if robot_act == 2 and station_get: # 取完成
        if ADDR_REGION_COLD_END <= station_get and station_get <= ADDR_REGION_COLD_END: #从冷藏区取出，准备出库
            #更新出库时间，用来回冷藏
            solder_getting.ReadyOutDateTime = datetime.now()

        elif ADDR_REGION_REWARM_START <= station_get and station_get <= ADDR_REGION_REWARM_END:
            solder_model_getting = db_session.query(SolderModel
                                        ).filter(SolderModel.Model == solder_getting.Model
                                        ).scalar()
            if solder_model_getting:
                modbus_client.write_float(solder_model_getting.StirSpeed, 1522)
                modbus_client.write_float(solder_model_getting.StirTime,  1526)
                logger.info(f"{solder_getting.SolderCode}在搅拌区设置搅拌参数成功 时间{solder_model_getting.StirSpeed}速度{solder_model_getting.StirTime}")
            else:
                logger.error(f"{solder_getting.SolderCode}在搅拌区设置搅拌参数出错 未找到solder_model_record")


    elif robot_act == 4 and station_get and station_put: # 放完成
        modbus_client.modbus_write("jcq", 0, station_put, 1)
        modbus_client.modbus_write("jcq", 1, station_get, 1)
        solder_getting.StationID = station_put

        if ADDR_REGION_COLD_START <= station_put and station_put <= ADDR_REGION_COLD_END:
            new_solderflowrecord = SolderFlowRecord(
                SolderCode=solder_getting.SolderCode,
                DateTime=datetime.now(),
                Type="进冷藏区"
            )
            db_session.add(new_solderflowrecord)

        elif ADDR_REGION_REWARM_START <= station_put and station_put <= ADDR_REGION_REWARM_END:
            solder_getting.RewarmStartDateTime = datetime.now()
            new_solderflowrecord = SolderFlowRecord(
                SolderCode=solder_getting.SolderCode,
                DateTime=datetime.now(),
                Type="进回温区"
            )
            db_session.add(new_solderflowrecord)


    elif robot_act == 5:  # 锡膏被人取走完成
        new_solderflowrecord = SolderFlowRecord(
            SolderCode=solder_getting.SolderCode,
            DateTime=datetime.now(),
            Type="出柜"
        )
        db_session.delete(solder_getting)
        db_session.add(new_solderflowrecord)


    db_session.commit()
    db_session.close()

    modbus_client.modbus_write("jcq", robot_get, ADDR_ROBOT_CONFIRM.GET, 1)
    modbus_client.modbus_write("jcq", robot_put, ADDR_ROBOT_CONFIRM.PUT, 1)
    modbus_client.modbus_write("jcq", robot_act, ADDR_ROBOT_CONFIRM.ACT, 1)
