import pytz
from sqlalchemy.sql.functions import current_time

from modbus.client import modbus_client
from models import SolderModel, Solder
from router.solder import out_solder
from test import session
from datetime import datetime, timedelta, timezone
import logging
"""
    获取冷藏区中第一个空的点位
    :return:
    int: cold_area_first_empty_station
"""
def find_cold_area_first_empty_station():
    cold_area_empty_station = 0
    for cold_area_stationID in range(201, 540):
        if session.query(Solder).filter(Solder.StationID == cold_area_stationID).all() == None:
            cold_area_empty_station = cold_area_stationID
            return cold_area_empty_station
    return cold_area_empty_station

"""
    获取回温区中第一个空的点位
    :return:
    int: rewarm_area_first_empty_station
"""
def find_rewarm_area_first_empty_station():
    rewarm_area_empty_station = 0
    for rewarm_area_stationID in range(603, 650):
        if session.query(Solder).filter(Solder.StationID == rewarm_area_stationID).all() == None:
            rewarm_area_empty_station = rewarm_area_stationID
            return rewarm_area_empty_station
    return rewarm_area_empty_station

"""
    获取回温区中预约专用区域第一个空的点位
    :return:
    int: rewarm_area_order_first_empty_station
"""
def find_rewarm_area_order_first_empty_station():
    rewarm_area_order_empty_station = 0
    for rewarm_area_order_stationID in range(601, 603):
        if session.query(Solder).filter(Solder.StationID == rewarm_area_order_stationID).all() == None:
            rewarm_area_order_empty_station = rewarm_area_order_stationID
            return rewarm_area_order_empty_station
    return rewarm_area_order_empty_station

"""
    获取待取区中第一个空的点位
    :return:
    int: ready_area_first_empty_station
"""
def find_ready_area_first_empty_station():
    ready_area_empty_station = 0
    for ready_area_stationID in range(603, 650):
        if session.query(Solder).filter(Solder.StationID == ready_area_stationID).all() == None:
            ready_area_empty_station = ready_area_stationID
            return ready_area_empty_station
    return ready_area_empty_station

"""
    获取待取区中预约专用区域第一个空的点位
    :return:
    int: ready_area_order_first_empty_station
"""
def find_ready_area_order_first_empty_station():
    ready_area_order_empty_station = 0
    for ready_area_order_stationID in range(601, 603):
        if session.query(Solder).filter(Solder.StationID == ready_area_order_stationID).all() == None:
            ready_area_order_empty_station = ready_area_order_stationID
            return ready_area_order_empty_station
    return ready_area_order_empty_station


"""
    入柜区有点位状态是2
    :return:
    bool:
    int: cold_area_empty_stationID
"""
def condition_in_area_to_cold_area():
    
    in_area_available_staionID_list = []
    for in_area_stationID in range(901,929):
        if modbus_client.modbus_read("jcq", in_area_stationID, 1) == 2:
            in_area_available_staionID_list.append(in_area_stationID)
    # 冷藏区中第一个空的点位
    cold_area_empty_stationID = find_cold_area_first_empty_station()

    if len(in_area_available_staionID_list) != 0 and cold_area_empty_stationID != 0:
        return True, cold_area_empty_stationID
    else:
        return False,cold_area_empty_stationID


'''
    冷藏时间满足 and (回温数量不足 or 预约时间 <= 现在时间 + 回温时间 + 搅拌时间)
    :return
    Solder: 要从冷藏区送往回温区的solder
    staionID: 要放到回温区的那个点位(如果是0，就说明回温区没有可放的点位了）
    
'''
def condition_cold_area_to_rewarm_area():
    model_solders = session.query(SolderModel,Solder).join(Solder.Model == SolderModel.Model).filter(Solder.StationID.between(201,539)).all()
    current_time = datetime.now()
    for model,solder in model_solders:
        model_rewarm_count = session.query(Solder).filter(Solder.Model == model.Model
                                                          ,Solder.StationID.between(603,650)).count()
        if (solder.StorageDateTime <= current_time - timedelta(hours=getattr(model, "MinLcTim"))
                and model_rewarm_count < model.RewarmNum):
            # 获取回温区第一个空的点位
            rewarm_area_empty_station = find_rewarm_area_first_empty_station()
            return solder,rewarm_area_empty_station

        elif ( solder.StorageDateTime <= current_time - timedelta(hours=getattr(model, "MinLcTim"))
               and solder.OrderDateTime != None
               and solder.OrderDateTime <= current_time + model.RewarmTime + model.StirTime
        ):
            # 获取回温区预约专用区第一个空的点位
            rewarm_area_order_empty_station = find_rewarm_area_order_first_empty_station()
            return solder, rewarm_area_order_empty_station



'''
    超出最大出冷藏时间
    :return
    Solder:回温区或待取区中冷藏时间>=最大出冷藏时间的锡膏
    int: 冷藏区中空的staionID
'''
def condition_go_back_cold_area():
    current_time = datetime.now()
    model_solders = (session.query(SolderModel,Solder).join(SolderModel.Model == Solder.Model)
                     .filter((Solder.StationID.between(601,650))) | (Solder.StationID.between(801,820))).all()
    
    
    for model,solder in model_solders:    
        # 出库时间超时检查（自动超时冷藏）
        out_timeout_minutes = getattr(model, "OutChaoshiAutoLc", None)
        ready_out_time = solder.ReadyOutDateTime
        ready_out_time = pytz.UTC.localize(ready_out_time)
        if ready_out_time.tzinfo is None:
            logging.warning(f"{solder.SolderCode}锡膏的ready_out_time为空")
        if ready_out_time is not None and out_timeout_minutes is not None:
            # 计算超时阈值
            out_timeout_threshold = ready_out_time + timedelta(hours=out_timeout_minutes)
            # 检查如果超时
            if current_time > out_timeout_threshold:
                logging.info(f"触发自动超时冷藏--出库超时：库位号{int(solder.StationID)} || 出库时间{ready_out_time} || 超时阈值{out_timeout_threshold.strftime('%Y-%m-%d %H:%M:%S %z')} || 设定超时时间{model.OutChaoshiAutoLc}小时")
                # 获取冷藏区中第一个空的点位
                cold_area_first_empty_station = find_cold_area_first_empty_station()
                return solder, cold_area_first_empty_station  



'''
    回温时间到 and 锡膏是自动搅拌 and (待取数量不足 or 预约时间 <= 现在时间 + 搅拌时间)
    :return
    Solder:回温区中满足回温时间的锡膏
    int:待取区空的点位stationID
'''
def condition_rewarm_area_to_ready_area():
    rewarm_area_model_solders = (session.query(SolderModel, Solder).join(Solder.Model == SolderModel.Model)
                     .filter(Solder.StationID.between(601, 650)).all())
    current_time = datetime.now()
    for model, solder in rewarm_area_model_solders:

        model_ready_count = session.query(Solder).filter(Solder.Model == model.Model
                                                          , Solder.StationID.between(803, 820)).count()
        if (solder.ReadyOutDateTime <= current_time - timedelta(minutes=getattr(model, "RewarmTime"))
                and model_ready_count < model.ReadyOutNum):
            # 获取待取区第一个空的点位
            ready_area_first_empty_station = find_ready_area_first_empty_station()
            return solder, ready_area_first_empty_station

        elif (solder.ReadyOutDateTime <= current_time - timedelta(minutes=getattr(model, "RewarmTime"))
              and solder.OrderDateTime != None
              and solder.OrderDateTime <= current_time + model.StirTime
        ):
            # 获取待取区预约专用区第一个空的点位
            ready_area_order_first_empty_station = find_ready_area_order_first_empty_station()
            return solder, ready_area_order_first_empty_station


'''
    出库搅拌 and 用户点击出库
    :return
    Solder: 回温区中要直接出库的锡膏  
    stirTime
    striSpeed
'''
def condition_to_be_stirred_out():
    solders = out_solder()
    for solder in solders:
        model = session.query(SolderModel).filter(SolderModel.Model == solder.Model).first()
        if solder.JiaobanRule == "出库搅拌":
            return solder, model.StirTime, model.StirSpeed



'''
    自动搅拌 and 用户点击出库
    :return
    Solder: 回温区中型号参数为自动搅拌的锡膏
    stirTime
    striSpeed
    int: ready_area_first_empty_stationID
'''
def condition_already_stirred_out():
    # rewarm_area_auto_stir_solders = (session.query(SolderModel,Solder).join(SolderModel.Model==Solder.Model)
    #                                  .filter(SolderModel.JiaobanRule == "自动搅拌").all())
    # for rewarm_area_auto_stir_solder in rewarm_area_auto_stir_solders:
    #     # 如果回温时间满足就去搅拌,然后放到到待取区
    #     if rewarm_area_auto_stir_solder
    solders = out_solder()
    for solder in solders:
        model = session.query(SolderModel).filter(SolderModel.Model == solder.Model).first()
        if solder.JiaobanRule == "自动搅拌":
            ready_area_first_empty_station = find_ready_area_first_empty_station()
            return solder,ready_area_first_empty_station,model.StirTime,model.StirSpeed


'''
    有锡膏在回温区或待取区
    
    Solder: 冷藏模式下，还在回温区或待取区中的锡膏
    int: 冷藏区空的点位stationID
'''
def condition_cold_mode():
    rewarm_or_ready_area_solders = session.query(Solder).filter( (Solder.StationID.between(601,650)) | (Solder.StationID.between(801,820))).all()
    for solder in rewarm_or_ready_area_solders:
        cold_area_first_empty_station = find_cold_area_first_empty_station()
        return solder,cold_area_first_empty_station

