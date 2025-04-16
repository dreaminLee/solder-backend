from datetime import datetime

from util.db_connection import db_instance
from util.logger import logger
from models import Solder, SolderFlowRecord, SolderFlowRecordEvent, SolderStatus
from modbus.modbus_addresses import (
    in_region_cold,
    in_region_rewarm,
    in_region_wait,
    in_region_scan,
    in_region_fetch,
)


class solder_stat:
    def __init__(self, station_id, status):
        self.station_id = station_id
        self.status = status

    def __eq__(self, other):
        if isinstance(other, solder_stat):
            return self.station_id == other.station_id and self.status == other.status
        return False

    def update(self, other):
        if isinstance(other, solder_stat):
            self.station_id = other.station_id
            self.status = other.status


solder_status_dict = {}
with db_instance.get_session() as db_session:
    for code, station_id, status in db_session.query(
        Solder.SolderCode, Solder.StationID, Solder.Status
    ).all():
        solder_status_dict[code] = solder_stat(station_id, SolderStatus(status))


def task_monitor():
    """
    监视solder表变化并记录
    """
    with db_instance.get_session() as db_session:
        for code, station_id_now, sstatus_now in db_session.query(
            Solder.SolderCode, Solder.StationID, Solder.Status
        ).all():
            stat_now = solder_stat(station_id_now, sstatus_now)
            stat_last: solder_stat = solder_status_dict[code]
            if stat_now != stat_last:
                logger.info(
                    f"锡膏号 {code} 状态更新 station_id: {stat_last.station_id} -> {stat_now.station_id}, status: {stat_last.status} -> {stat_now.status}"
                )

                if (stat_last.status == SolderStatus.STATION and
                    stat_now.status  == SolderStatus.MOVING):
                    move_record = SolderFlowRecord(
                        Event=SolderFlowRecordEvent.FROM_REGION_COLD.value   if in_region_cold  (stat_last.station_id) else
                              SolderFlowRecordEvent.FROM_REGION_REWARM.value if in_region_rewarm(stat_last.station_id) else
                              SolderFlowRecordEvent.FROM_REGION_WAIT.value   if in_region_wait  (stat_last.station_id) else
                              SolderFlowRecordEvent.REQUEST_IN_GOOD.value    if in_region_scan  (stat_last.station_id) else "未知",
                        DateTime=datetime.now(),
                        SolderCode=code
                    )
                    db_session.add(move_record)

                    if move_record.Event == SolderFlowRecordEvent.FROM_REGION_REWARM.value:
                        stir_record = SolderFlowRecord(
                            Event=SolderFlowRecordEvent.START_STIR.value,
                            DateTime=datetime.now(),
                            SolderCode=code
                        )
                        db_session.add(stir_record)

                elif (stat_last.status == SolderStatus.MOVING and
                      stat_now.status  == SolderStatus.STATION):
                    move_record = SolderFlowRecord(
                        Event=SolderFlowRecordEvent.TO_REGION_COLD.value     if in_region_cold  (station_id_now) else
                              SolderFlowRecordEvent.TO_REGION_REWARM.value   if in_region_rewarm(station_id_now) else
                              SolderFlowRecordEvent.TO_REGION_WAIT.value     if in_region_wait  (station_id_now) else
                              SolderFlowRecordEvent.REQUEST_OUT_FINISH.value if in_region_fetch (station_id_now) else "未知",
                        DateTime=datetime.now(),
                        SolderCode=code
                    )

                    if (move_record.Event == SolderFlowRecordEvent.TO_REGION_WAIT.value or
                        move_record.Event == SolderFlowRecordEvent.REQUEST_OUT_FINISH.value):
                        stir_record = SolderFlowRecord(
                            Event=SolderFlowRecordEvent.FINISH_STIR.value,
                            DateTime=datetime.now(),
                            SolderCode=code
                        )
                        db_session.add(stir_record)

                    db_session.add(move_record)

                db_session.commit()
                stat_last.update(stat_now)
                return
