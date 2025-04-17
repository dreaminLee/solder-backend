from modbus.client import modbus_client
from models import Solder
from util.db_connection import db_instance
from util.logger import logger
from modbus.modbus_addresses import ADDR_REGION_START_COLD,   ADDR_REGION_END_COLD
from modbus.modbus_addresses import ADDR_REGION_START_REWARM, ADDR_REGION_END_REWARM
from modbus.modbus_addresses import ADDR_REGION_START_WAIT,   ADDR_REGION_END_WAIT


def task_freeze():
    with db_instance.get_session() as db_session:

        solder_stationID_list_cold   = [r.StationID for r in db_session.query(Solder.StationID).filter(Solder.StationID.between(ADDR_REGION_START_COLD,   ADDR_REGION_END_COLD)).all()]
        solder_stationID_list_rewarm = [r.StationID for r in db_session.query(Solder.StationID).filter(Solder.StationID.between(ADDR_REGION_START_REWARM, ADDR_REGION_END_REWARM)).all()]
        solder_stationID_list_wait   = [r.StationID for r in db_session.query(Solder.StationID).filter(Solder.StationID.between(ADDR_REGION_START_WAIT,   ADDR_REGION_END_WAIT)).all()]
        logger.info(f"冷藏区已有锡膏的点位：{solder_stationID_list_cold}")
        logger.info(f"回温区已有锡膏的点位：{solder_stationID_list_rewarm}")
        logger.info(f"待取区已有锡膏的点位：{solder_stationID_list_wait}")

        """
            冷藏区的锡膏状态设成0（不可取不可放）
            回温区的锡膏状态设成5（异常）
            待取区的锡膏状态设成5（异常）
        """
        station_status_cold   = [0 if stationID in   solder_stationID_list_cold else 1 for stationID in range(ADDR_REGION_START_COLD,   ADDR_REGION_END_COLD + 1)]
        station_status_rewarm = [5 if stationID in solder_stationID_list_rewarm else 0 for stationID in range(ADDR_REGION_START_REWARM, ADDR_REGION_END_REWARM + 1)]
        station_status_wait   = [5 if stationID in   solder_stationID_list_wait else 0 for stationID in range(ADDR_REGION_START_WAIT,   ADDR_REGION_END_WAIT + 1)]

        bulk_len = 100
        for bulk_start in range(0, len(station_status_cold), bulk_len):
            modbus_client._client.write_registers(bulk_start + ADDR_REGION_START_COLD, station_status_cold[bulk_start: bulk_start + bulk_len if bulk_start + bulk_len < len(station_status_cold) else None], unit=0)

        for bulk_start in range(0, len(station_status_rewarm), bulk_len):
            modbus_client._client.write_registers(bulk_start + ADDR_REGION_START_REWARM, station_status_rewarm[bulk_start: bulk_start + bulk_len if bulk_start + bulk_len < len(station_status_rewarm) else None], unit=0)

        for bulk_start in range(0, len(station_status_wait), bulk_len):
            modbus_client._client.write_registers(bulk_start + ADDR_REGION_START_WAIT, station_status_wait[bulk_start: bulk_start + bulk_len if bulk_start + bulk_len < len(station_status_wait) else None], unit=0)
