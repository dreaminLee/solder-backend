from datetime import datetime
from modbus.client import modbus_client
from modbus.modbus_addresses import ADDR_SCANNER_STATUS, ADDR_SCANNER_CONFIRM
from modbus.scan import scan
from util.parse import parse_barcode
from util.db_connection import db_instance
from util.logger import logger
from models import User, Solder, SolderFlowRecord, SolderFlowRecordEvent, Station2


def task_scan_impl(scanner_req, scanner_pos):
    with db_instance.get_session() as db_session:

        if not scanner_req:
            return 0

        barcode_scanned = scan()
        if not barcode_scanned:
            return 2

        logger.info(f"扫到条码: {barcode_scanned}")
        open("res_asc.txt", "w", encoding="utf8").write(barcode_scanned)
        parse_result = parse_barcode(barcode_scanned)
        if not parse_result:
            return 2

        model = parse_result["model"]
        # productDate = parse_result['product_date']
        # expireDate = parse_result['expire_date']
        # shelfLife = parse_result['shelf_life']
        scan_station_id = db_session.query(Station2.StationID).filter(Station2.Region == "扫码区").scalar()

        user_cache_file = "user_cache.txt"
        user_id = int(open(user_cache_file, "r").read())
        user_name = (
            db_session.query(User.UserName).where(User.UserID == user_id).scalar()
        )
        user_name = user_name if user_name else "未知用户"

        # 删除已扫码但未进入冷藏柜的锡膏
        old_solder = db_session.query(Solder).filter(Solder.StationID == scan_station_id).scalar()
        if old_solder:
            db_session.delete(old_solder)

        # 查询此前该锡膏的入柜次数
        in_times = (
            db_session.query(SolderFlowRecord)
            .filter(
                SolderFlowRecord.Event == SolderFlowRecordEvent.REQUEST_IN.value,
                SolderFlowRecord.SolderCode == barcode_scanned,
            )
            .count()
        )
        new_solder = Solder(
            SolderCode=barcode_scanned,
            Model=model,
            # ProductDate=productDate,
            # ExpireDate=expireDate,
            # ShelfLife = shelfLife,
            InTimes=in_times + 1,
            BackLCTimes=0,
            StationID=scan_station_id,
            StorageUser=user_name,
            StorageDateTime=datetime.now(),
        )
        new_solderflowrecord = SolderFlowRecord(
            SolderCode=barcode_scanned,
            UserID=user_id,
            UserName=user_name,
            DateTime=datetime.now(),
            Event=SolderFlowRecordEvent.REQUEST_IN.value,
        )
        db_session.add(new_solder)
        db_session.add(new_solderflowrecord)
        db_session.commit()

        return 1


def task_scan():
    scanner_req = modbus_client.modbus_read("jcq", ADDR_SCANNER_STATUS.REQ, 1)[0]
    scanner_pos = modbus_client.modbus_read("jcq", ADDR_SCANNER_STATUS.POS, 1)[0]
    logger.info(f"扫码状态：请求 {scanner_req}, 库位号 {scanner_pos}")
    scan_res = task_scan_impl(scanner_req, scanner_pos)
    modbus_client.modbus_write("jcq", scan_res, ADDR_SCANNER_CONFIRM.RET, 1)
    modbus_client.modbus_write("jcq", scanner_pos, ADDR_SCANNER_CONFIRM.POS, 1)
