from datetime import datetime

from modbus.client import modbus_client
from modbus.scan import scan
from models import Solder, SolderFlowRecord, User
from util.db_connection import db_instance
from util.logger import task_scan_logger

def barcode_check(barcode):
    condition_1 = barcode.count("+") >= 5

    return condition_1


def get_current_user() -> int:
    user_cache_file = "user_cache.txt"
    with open(user_cache_file, "r", encoding="utf-8") as f:
        id_str = f.read()
        return int(id_str) if len(id_str) else -1


def task_scan():
    if read_mode() == 0:
        return
    # 获取扫码结果并检查结果是否符合格式
    req_scan = modbus_client.modbus_read("jcq", 111, 1)[0]
    location = modbus_client.modbus_read("jcq", 110, 1)[0]
    if not req_scan:
        modbus_client.modbus_write("jcq", 0, 140, 1)
        modbus_client.modbus_write("jcq", 0, 141, 1)
        return

    barcode = scan()
    task_scan_logger.info(f"扫描到条码：{barcode}")
    if not barcode_check(barcode):
        modbus_client.modbus_write("jcq",        2, 141, 1)
        modbus_client.modbus_write("jcq", location, 140, 1)
        return

    with open("res_asc.txt", "w") as barcode_file:
        barcode_file.write(barcode)
    parts = barcode.split('+')
    model = parts[4]
    product_date = parts[2]
    year, month, day = 2020 + int(product_date[0]), int(product_date[1:3]), int(product_date[3:5])
    product_date = datetime(year, month, day)

    current_user_id = get_current_user()
    current_time = datetime.now()
    new_solder = Solder(
        SolderCode = barcode,
        Model = model,
        ProductDate = product_date,
        Intimes = in_times + 1,
        BackLCTimes = 0,
        StationID = 190,
        StorageUser = "",
        StorageDateTime = current_time
    )
    new_solder_flow_record = SolderFlowRecord(
        SolderCode = barcode,
        UserID = str(current_user_id),
        UserName = "",
        DateTime = current_time,
        Type = "请求入柜"
    )
    with db_instance.get_session() as session:
        in_times = session.query (SolderFlowRecord
                         ).join  (Solder, Solder.SolderCode == SolderFlowRecord.SolderCode
                         ).filter(SolderFlowRecord.Type == "请求入柜"
                         ).count ()
        current_user_name = session.query(User).filter_by(UserID=current_user_id).first()
        current_user_name = current_user_name if current_user_name else "未知用户"
        new_solder.StorageUser = current_user_name
        new_solder_flow_record.UserName = current_user_name
        session.add(new_solder)
        session.add(new_solder_flow_record)
        modbus_client.modbus_write("jcq", 1, 141, 1)
        modbus_client.modbus_write("jcq", location, 140, 1)
        session.commit()
