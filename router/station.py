import os

from flask import Blueprint, jsonify, request
from sqlalchemy import cast, func, Integer, or_

from modbus.client import modbus_client
from tasks.scheduler import file_path
from util.db_connection import db_instance
from models import Station, Solder
from util.Response import Response

station_bp = Blueprint('station', __name__)


@station_bp.route('/get_storage_station', methods=['GET'])
def get_storage_station():
    try:
        session = db_instance.get_session()  # 获取数据库会话

        # 查询冷藏区数量
        cold_storage_count = session.query(Solder).filter(Solder.StationID.between(201, 539)).count()
        cold_storage_capacity = 539 - 201 + 1  # 339

        # 查询回温区数量
        warm_storage_count = session.query(Solder).filter(Solder.StationID.between(601, 660)).count()
        warm_storage_capacity = 660 - 601 + 1  # 60

        # 查询待取区数量
        waiting_pickup_count = session.query(Solder).filter(Solder.StationID.between(801, 870)).count()
        waiting_pickup_capacity = 870 - 801 + 1  # 70

        session.close()

        # 组装返回的数据
        data = {
            "cold_storage_count": cold_storage_count,
            "cold_storage_capacity": cold_storage_capacity,
            "warm_storage_count": warm_storage_count,
            "warm_storage_capacity": warm_storage_capacity,
            "waiting_pickup_count": waiting_pickup_count,
            "waiting_pickup_capacity": waiting_pickup_capacity
        }

        return Response.SUCCESS(data)

    except Exception as e:
        # 处理异常并返回错误信息
        return Response.FAIL(str(e))

@station_bp.route('/get_all_stations', methods=['GET'])
def get_all_stations():
    session = db_instance.get_session()
    try:
        # 查询并根据 SolderCode 升序排序，并且只查询 SolderCode >= 0 的记录
        stations = session.query(Station).filter(Station.SolderCode >= 0).order_by(Station.SolderCode).all()

        # 查询所有浮动数值
        float_values = modbus_client.read_float_test(2000, 6079)

        from concurrent.futures import ThreadPoolExecutor

        # 提前处理浮动值
        def round_or_none(value):
            return round(value, 2) if value is not None else None

        def modbus_read_disabled_bulk(station_disabled_list):
            """
            批量读取所有站点的 Disabled 状态。
            你可以根据你的需求，批量读取这些数据。
            """
            # 假设通过一个查询获取所有站点的 Disabled 状态
            disabled_data = {}
            for station_disabled in station_disabled_list:
                disabled_data[station_disabled] = modbus_client.modbus_read('jcq', station_disabled, 1)
            return disabled_data

        def process_station_batch(stations, float_values, index, disabled_data):
            station_list = []
            # 处理所有的站点数据
            for station in stations:
                if index + 3 < len(float_values):  # 确保浮动值足够
                    station.XAxis = round_or_none(float_values[index])
                    station.YAxis = round_or_none(float_values[index + 1])
                    station.ZAxis = round_or_none(float_values[index + 2])
                    station.RAxis = round_or_none(float_values[index + 3])
                    index += 4  # 每次处理 4 个浮动值
                else:
                    # 如果浮动值不足，其他的轴赋为 None
                    station.XAxis = None
                    station.YAxis = None
                    station.ZAxis = None
                    station.RAxis = None

                # 获取 Disabled 状态
                disabled = disabled_data.get(station.Disabled, None)

                # 构造字典
                station_list.append({
                    'StationID': station.StationID,
                    'StaType': station.StaType,
                    'StaArea': station.StaArea,
                    'StaLayer': station.StaLayer,
                    'StaColumn': station.StaColumn,
                    'XAxis': station.XAxis,
                    'YAxis': station.YAxis,
                    'ZAxis': station.ZAxis,
                    'RAxis': station.RAxis,
                    'Disabled': disabled,
                    'SolderCode': station.SolderCode,
                    'ModifyDateTime': station.ModifyDateTime.strftime(
                        '%Y-%m-%d %H:%M:%S') if station.ModifyDateTime else None
                })

            return station_list, index

        # 批量处理站点
        def process_stations_parallel(stations, float_values):
            station_list = []
            index = 0  # 初始化 index

            # 批量处理 Disabled 状态
            station_disabled_list = [station.Disabled for station in stations if station.Disabled]
            disabled_data = modbus_read_disabled_bulk(station_disabled_list)

            # 使用线程池批量处理站点数据
            with ThreadPoolExecutor() as executor:
                results = executor.submit(process_station_batch, stations, float_values, index, disabled_data)
                station_list, _ = results.result()

            return station_list

        # 处理站点
        station_list = process_stations_parallel(stations, float_values)

        # 现在 station_list 已经包含了所有符合条件的站点信息

        return Response.SUCCESS(data=station_list)
    except Exception as e:
        session.close()
        return Response.FAIL(f"查询站点列表失败: {e}")

@station_bp.route('/update_station_location', methods=['POST'])
def update_station_location():
    session = db_instance.get_session()
    try:
        data = request.get_json()
        x = data.get('x')
        y = data.get('y')
        z = data.get('z')
        r = data.get('r')
        StaType = data.get('StaType')
        stations=session.query(Station).filter(Station.StaType==StaType).first()
        x_ = stations.XAxis
        y_ = stations.YAxis
        z_ = stations.ZAxis
        r_ = stations.RAxis
        # def fun(float_v:float,add:int):
        #     byte_data = struct.pack('>f', float_v)
        #     register1, register0 = struct.unpack('>HH', byte_data)
        #     modbus_client.modbus_write('jcq', register0, int(add), 1)
        #     modbus_client.modbus_write('jcq',register1,int(add+1),1)
        modbus_client.write_float(x, x_)
        modbus_client.write_float(y, y_)
        modbus_client.write_float(z, z_)
        modbus_client.write_float(r, r_)

        return jsonify(Response.SUCCESS())
    except Exception as e:
        session.rollback()
        return jsonify(Response.FAIL(f"查询站点列表失败: {e}"))
    finally:
        session.close()
    # 检查是否为 SSE 请求
    # if request.headers.get('Accept') == 'text/event-stream':
    #     return Response(generate_sse_data(), mimetype='text/event-stream')
    #
    # # 非 SSE 请求返回默认 JSON 数据
    # cold_storage_stations = Station.query.filter_by(StaArea="\u51b7\u85cf\u533a", Disabled=False).all()
    # if not cold_storage_stations:
    #     return jsonify(Response.FAIL("\u6ca1\u6709\u627e\u5230\u51b7\u85cf\u533a\u5de5\u4f4d\u8bb0\u5f55").to_dict())
    #
    # total_capacity = sum(station.StaLayer * station.StaColumn for station in cold_storage_stations)
    # total_remaining_capacity = sum(station.StaLayer * station.StaColumn for station in cold_storage_stations)
    # storage_stations = Station.query.filter_by(StaArea="\u5165\u5e93\u533a", Disabled=False).all()
    # storage_records = [
    #     {
    #         "id": station.id,
    #         "StaArea": station.StaArea,
    #         "StaLayer": station.StaLayer,
    #         "StaColumn": station.StaColumn,
    #     } for station in storage_stations
    # ]
    # solder_code = f"SC-{randint(1000, 9999)}"
    #
    # return jsonify(Response.SUCCESS({
    #     'cold_storage': {
    #         'total_capacity': total_capacity,
    #         'total_remaining_capacity': total_remaining_capacity
    #     },
    #     'storage_records': storage_records,
    #     'solder_code': solder_code
    # }).to_dict())

@station_bp.route('/get_ruku_data', methods=['GET'])
def get_ruku_data():
    try:
        current_data = {}

        # 判断文件是否为空并读取内容
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            with open(file_path, "r") as file:
                code = file.read()

        # 遍历 901 到 928 之间的数字
        for station_id in range(901, 929):
            modbus_result = modbus_client.modbus_read('jcq', station_id, 1)

            # 组装每个入库区的状态
            for i, value in enumerate(modbus_result):
                current_data[f"入库区{station_id + i}"] = value  # 假设你想通过 station_id 加上索引来构造入库区名称

        # 组装响应数据
        data = {
            "ruku_data": current_data,
            "code": code
        }

        # 返回 JSON 格式响应
        return Response.SUCCESS(data)

    except Exception as e:
        # 处理异常
        return Response.FAIL({"error": "Failed to fetch ruku data"})


@station_bp.route('/get_stations', methods=['GET'])
def get_stations():
    return Response.FAIL("Not implemented")


@station_bp.route('/get_all_stations_byArea', methods=['POST'])
def get_all_stations_by_area():
    data = request.get_json()
    area = data.get('area')
    with db_instance.get_session() as session:
        stations_query = session.query(Station)
        if area:
            stations_query = stations_query.filter(Station.StaArea == area)
        stations = stations_query.all()
        stations_data = [
            {
                "StaType": station.StaType,
                "XAxis": station.XAxis,
                "YAxis": station.YAxis,
                "ZAxis": station.ZAxis,
                "RAxis": station.RAxis,
                "StaArea": station.StaArea,
                "StationID": station.StationID
            }
            for station in stations
        ]
        return Response.SUCCESS(data=stations_data)
