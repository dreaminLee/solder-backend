from modbus.client import modbus_client
from models import SolderModel, Solder
from test import session
from datetime import datetime, timedelta, timezone

def condition_in_area_to_cold_area():
    """
    入柜区有点位状态是2
    :return:
    bool:
    int: cold_area_empty_stationID
    """
    in_area_available_staionID_list = []
    for in_area_stationID in range(901,929):
        if modbus_client.modbus_read("jcq", in_area_stationID, 1) == 2:
            in_area_available_staionID_list.append(in_area_stationID)
    # 冷藏区中第一个空的点位
    cold_area_empty_stationID = 0
    for cold_area_stationID in range(201, 540):
        if session.query(Solder).filter(Solder.StationID == cold_area_stationID).all() == None :
            cold_area_empty_stationID = cold_area_stationID
            break

    if len(in_area_available_staionID_list) != 0 and cold_area_empty_stationID != 0:
        return True, cold_area_empty_stationID
    else:
        return False,cold_area_empty_stationID


'''
    冷藏时间满足 and (回温数量不足 or 预约时间 <= 现在时间 + 回温时间 + 搅拌时间)
    :return:
    Solder: 要从冷藏区送往回温区的solder
    staionID: 要放到回温区的那个点位(如果是0，就说明回温区没有可放的点位了）
    
'''
def condition_cold_area_to_rewarm_area():
    model_solders = session.query(SolderModel,Solder).join(Solder.Model == SolderModel.Model).filter(Solder.StationID.between(201,539)).all()
    current_time = datetime.now()
    for model,solder in model_solders:
        model_rewarm_count = session.query(Solder).filter(Solder.Model == model.Model
                                                          ,Solder.StationID.between(601,650)).count()
        if (solder.StorageDateTime <= current_time - timedelta(hours=getattr(model, "MinLcTim"))
                and model_rewarm_count < model.RewarmNum):
            # 获取回温区第一个空的点位
            rewarm_area_empty_station = 0
            for rewarm_area_stationID in range(603,650):
                if session.query(Solder).filter(Solder.StationID == rewarm_area_stationID).all() == None:
                    rewarm_area_empty_station = rewarm_area_stationID
                    break

            return solder,rewarm_area_empty_station

        elif ( solder.StorageDateTime <= current_time - timedelta(hours=getattr(model, "MinLcTim"))
               and solder.OrderDateTime != None
               and solder.OrderDateTime <= current_time + model.RewarmTime + model.StirTime
        ):
            # 获取回温区预约专用区第一个空的点位
            rewarm_area_empty_station = 0
            for rewarm_area_stationID in range(601, 603):
                if session.query(Solder).filter(Solder.StationID == rewarm_area_stationID).all() == None:
                    rewarm_area_empty_station = rewarm_area_stationID
                    break

            return solder, rewarm_area_empty_station






'''
    超出最大出冷藏时间
'''
def condition_go_back_cold_area():
    return True


'''
    回温时间到 and 锡膏是自动搅拌 and (待取数量不足 or 预约时间 <= 现在时间 + 搅拌时间)
'''
def condition_rewarm_area_to_ready_area():
    return True


'''
    出库搅拌 and 用户点击出库
'''
def condition_to_be_stirred_out():
    return True


'''
    自动搅拌 and 用户点击出库
'''
def condition_already_stirred_out():
    return True


'''
    有锡膏在回温区或待取区
'''
def condition_cold_mode():
    return True
