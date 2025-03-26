from apscheduler.executors.pool import ThreadPoolExecutor
from flask_apscheduler import APScheduler
from sqlalchemy import or_

from modbus.client import modbus_client
from models import Station, Solder, SolderModel, SolderFlowRecord, User, Alarm
from router.solder import daiqu_solder
from util.db_connection import db_instance
from util.logger import logger
# 设置 APScheduler 日志级别为 WARNING
logger.getLogger('apscheduler').setLevel(logger.WARNING)

def lc_mode():
    session = db_instance.get_session()
    solders = session.query(Solder).all()
    stations = session.query(Station).all()
    StaType_station_dict = {station.StaType: station.StationID for station in stations}

    # 检查初始化冷藏区，有锡膏的点位状态为0
    lc_solders_stationID_list = session.query(Station.StationID).join(Solder.StationID == Station.StationID).filter(Solder.StationID.between(201,539)).all()
    for solders_stationID in lc_solders_stationID_list:
        modbus_client.modbus_write("jcq", 0 , solders_stationID, 1)

    warm_solders_list = session.query(Solder).filter(Solder.StationID.between(601,650)).all()
    daiqu_solder_list = session.query(Solder).filter(Solder.StationID.between(801,820)).all()

    for solder in warm_solders_list:
        # 回温区的锡膏状态设成5（异常）
        modbus_client.modbus_write("jcq", 5, int(solder.StationID), 1)
        # 冷藏区找出第一个没锡膏的点位，状态设成1（可放)
        solder_fang_stationID = session.query(Station.StationID).filter(Station.StationID.not_in(lc_solders_stationID_list)).first()
        modbus_client.modbus_write("jcq", 1 , solder_fang_stationID, 1)
        lc_solders_stationID_list.append(solder_fang_stationID)

    for solder in daiqu_solder_list:
        # 回温区的锡膏状态设成5（异常）
        modbus_client.modbus_write("jcq", 5, int(solder.StationID), 1)
        # 冷藏区找出第一个没锡膏的点位，状态设成1（可放)
        solder_fang_stationID = session.query(Station.StationID).filter(Station.StationID.not_in(lc_solders_stationID_list)).first()
        modbus_client.modbus_write("jcq", 1 , solder_fang_stationID, 1)
        lc_solders_stationID_list.append(solder_fang_stationID)
