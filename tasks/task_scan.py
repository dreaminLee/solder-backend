from datetime import datetime
from modbus.client import modbus_client
from modbus.modbus_addresses import ADDR_SCANNER_STATUS, ADDR_SCANNER_CONFIRM
from modbus.scan import scan
from util.parse import parse_barcode
from util.db_connection import db_instance
from models import User, Solder, SolderFlowRecord


def task_scan():
    with db_instance.get_session() as db_session:

        scanner_req = modbus_client.modbus_read("jcq", ADDR_SCANNER_STATUS.REQ, 1)[0]
        scanner_pos = modbus_client.modbus_read("jcq", ADDR_SCANNER_STATUS.POS, 1)[0]

        if not scanner_req:
            modbus_client.modbus_write("jcq", 0, ADDR_SCANNER_CONFIRM.RET, 1)
            modbus_client.modbus_write("jcq", 0, ADDR_SCANNER_CONFIRM.POS, 1)
            return

        barcode_scanned = scan()
        open("res_asc.txt", "w", encoding="utf8").write(barcode_scanned)
        parse_result = parse_barcode(barcode_scanned)
        if not parse_result:
            modbus_client.modbus_write("jcq", 2,           ADDR_SCANNER_CONFIRM.RET, 1)
            modbus_client.modbus_write("jcq", scanner_pos, ADDR_SCANNER_CONFIRM.POS, 1)
            return

        model = parse_result['model']
        # productDate = parse_result['product_date']
        # expireDate = parse_result['expire_date']
        # shelfLife = parse_result['shelf_life']


        user_cache_file = "user_cache.txt"
        user_id = int(open(user_cache_file, "r").read())
        user_name = db_session.query(User.UserName).where(User.UserID == user_id).scalar()
        user_name = user_name if user_name else "未知用户"

        #查询此前该锡膏的入柜次数
        in_times=db_session.query(SolderFlowRecord
                        ).join(Solder, Solder.SolderCode==SolderFlowRecord.SolderCode
                        ).filter(SolderFlowRecord.Type=="请求入柜"
                        ).count()
        new_solder = Solder(
            SolderCode=barcode_scanned,
            Model=model,
            # ProductDate=productDate,
            # ExpireDate=expireDate,
            # ShelfLife = shelfLife,
            InTimes=in_times+1,
            BackLCTimes=0,
            StationID=190,
            StorageUser=user_name,
            StorageDateTime=datetime.now()
        )
        new_solderflowrecord = SolderFlowRecord(
            SolderCode=barcode_scanned,
            UserID=user_id,
            UserName=user_name,
            DateTime=datetime.now(),
            Type="请求入柜"
        )
        db_session.add(new_solder)
        db_session.add(new_solderflowrecord)
        db_session.commit()

        modbus_client.modbus_write("jcq", 1,           ADDR_SCANNER_CONFIRM.RET, 1)
        modbus_client.modbus_write("jcq", scanner_pos, ADDR_SCANNER_CONFIRM.POS, 1)
