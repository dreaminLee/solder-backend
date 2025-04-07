from modbus.client import modbus_client
from models import Solder
from util.db_connection import db_instance
from util.logger import logger
from modbus.modbus_addresses import ADDR_REGION_COLD_START, ADDR_REGION_COLD_END
from modbus.modbus_addresses import ADDR_REGION_REWARM_START, ADDR_REGION_REWARM_END
from modbus.modbus_addresses import ADDR_REGION_WAIT_START, ADDR_REGION_WAIT_END


def task_freeze():
    session = db_instance.get_session()

    solder_stationID_list_cold   = [r.StationID for r in session.query(Solder.StationID).filter(Solder.StationID.between(  ADDR_REGION_COLD_START,   ADDR_REGION_COLD_END)).all()]
    solder_stationID_list_rewarm = [r.StationID for r in session.query(Solder.StationID).filter(Solder.StationID.between(ADDR_REGION_REWARM_START, ADDR_REGION_REWARM_END)).all()]
    solder_stationID_list_wait   = [r.StationID for r in session.query(Solder.StationID).filter(Solder.StationID.between(  ADDR_REGION_WAIT_START,   ADDR_REGION_WAIT_END)).all()]
    logger.info(f"冷藏区已有锡膏的点位：{solder_stationID_list_cold}")
    logger.info(f"回温区已有锡膏的点位：{solder_stationID_list_rewarm}")
    logger.info(f"待取区已有锡膏的点位：{solder_stationID_list_wait}")

    session.close()

    for stationID in range(ADDR_REGION_COLD_START, ADDR_REGION_COLD_END+1):
        # 冷藏区的锡膏状态设成0（不可取不可放）
        modbus_client.modbus_write("jcq", 0 if stationID in solder_stationID_list_cold else 1, stationID, 1)

    for stationID in range(ADDR_REGION_REWARM_START, ADDR_REGION_REWARM_END+1):
        # 回温区的锡膏状态设成5（异常）
        modbus_client.modbus_write("jcq", 5 if stationID in solder_stationID_list_rewarm else 0, stationID, 1)

    for stationID in range(ADDR_REGION_WAIT_START, ADDR_REGION_WAIT_END+1):
        # 待取区的锡膏状态设成5（异常）
        modbus_client.modbus_write("jcq", 5 if stationID in solder_stationID_list_wait else 0, stationID, 1)
