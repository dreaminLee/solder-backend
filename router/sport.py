import time

from flask import Blueprint, request

from modbus.client import modbus_client
from models import Solder
from util.Response import Response

import threading

from util.db_connection import db_instance

# 创建一个全局的锁对象
lock = threading.Lock()

sport_bp = Blueprint("sport", __name__)


def get_device_status(coil_status):
    # 定义设备状态字典
    status_dict = {
        "输入_出库区域滑台原位（槽型光电）": coil_status[0],
        "输入_出库区域滑台到位（槽型光电）": coil_status[1],
        "输入_冰箱门推拉气缸原位": coil_status[2],
        "输入_冰箱门推拉气缸到位": coil_status[3],
        "输入_冰箱门滑台气缸原位": coil_status[4],
        "输入_冰箱门滑台气缸到位": coil_status[5],
        "输入_移动模组夹爪气缸原位X7.0": coil_status[6],
        "输入_移动模组夹爪气缸到位": coil_status[7],
        "输入_移动模组180°旋转气缸原位": coil_status[8],
        "输入_移动模组180°旋转气缸到位": coil_status[9],
        "输入_移动模组45°旋转气缸原位": coil_status[10],
        "输入_移动模组45°旋转气缸到位": coil_status[11],
    }

    # 返回字典
    return status_dict


def get_device_status1(coil_status):
    # 定义设备状态字典
    status_dict = {
        "输出_三色灯黄": coil_status[0],
        "输出_三色灯绿": coil_status[1],
        "输出_三色灯红": coil_status[2],
        "输出_三色灯蜂鸣": coil_status[3],
        "输出_入库门打开": coil_status[4],
        "输出_出库门打开": coil_status[5],
        "输出_出库滑台动作": coil_status[6],
        "输出_出库滑台复位": coil_status[7],
        "输出_冰箱门推拉动作": coil_status[8],
        "输出_冰箱门推拉复位": coil_status[9],
        "输出_冰箱门滑台动作": coil_status[10],
        "输出_冰箱门滑台复位": coil_status[11],
        "输出_移动模组夹爪气缸动作": coil_status[12],
        "输出_移动模组夹爪气缸复位": coil_status[13],
        "输出_移动模组180°旋转气缸动作": coil_status[14],
        "输出_移动模组180°旋转气缸复位": coil_status[15],
        "输出_移动模组45°旋转气缸动作": coil_status[16],
        "输出_移动模组45°旋转气缸复位": coil_status[17],
    }

    # 返回字典
    return status_dict


@sport_bp.route("/get_sport_states", methods=["GET"])
def get_sport_states():
    # 读取线圈 62 到 75（共 14 个线圈）
    # coil_status = modbus_client.modbus_read("xq", 62, 12)
    # device_status = get_device_status(coil_status)
    coil_status = modbus_client.modbus_read("xq", 310, 18)
    # res={**device_status,**device_status1}
    # 检查读取的结果并返回
    if coil_status is None:
        return Response.FAIL("无法读取线圈状态")
    else:
        # 返回布尔值的列表
        device_status1 = get_device_status1(coil_status)
        return Response.SUCCESS(str(device_status1))


# 输入字符串列表
commands = [
    "三色灯黄",
    "三色灯绿",
    "三色灯红",
    "三色灯蜂鸣",

    "入库门打开",
    "出库门打开",
    "出库滑台动作",
    "出库滑台复位",

    "冰箱门1推拉动作",
    "冰箱门1推拉复位",
    "冰箱门1滑台动作",
    "冰箱门1滑台复位",

    "模组夹爪气缸动作",
    "模组夹爪气缸复位",
    "模组180度旋转气缸动作",
    "模组180度旋转气缸复位",
    "模组45度旋转气缸动作",
    "模组45度旋转气缸复位",

    "扫码旋转电机动作",
    "搅拌电机动作",

    "报警复位按钮",
    "回原位按钮",
    "一键冷藏按钮",

    "冰箱门2推拉动作",
    "冰箱门2推拉复位",
    "冰箱门2滑台动作",
    "冰箱门2滑台复位",
]

# 地址列表
addresses = [
    500,
    501,
    502,
    503,

    504,
    505,
    2506,
    2507,

    2508,
    2509,
    2510,
    2511,

    2512,
    2513,
    2514,
    2515,
    2516,
    2517,

    518,
    519,

    571,
    572,
    573,

    564,
    565,
    566,
    567,
]
c_a_dict = dict(zip(commands, map(int, addresses)))


@sport_bp.route("/get_sport_states2", methods=["GET"])
def get_sport_states2():
    greater_than_2000 = {cmd: addr for cmd, addr in c_a_dict.items() if addr >= 2000}
    res = {}
    for cmd, addr in greater_than_2000.items():
        coil_status = modbus_client.modbus_read("xq", addr, 1)[0]
        res[cmd] = coil_status
    return Response.SUCCESS(res)


# 全局锁和状态记录
# pending_tag2 = False
# last_tag1_time = 0
@sport_bp.route("/set_sport", methods=["POST"])
def set_sport():
    # global pending_tag2, last_tag1_time

    data = request.get_json()
    action = data.get("action")
    tag = data.get("tag")

    if not action or not tag:
        return Response.FAIL("参数缺失")

    if tag not in [1, 2]:
        return Response.FAIL("未知的 tag 类型")

    # if c_a_dict[action] == 573:
    #     from modbus.modbus_addresses import (
    #         ADDR_REGION_START_REWARM,
    #         ADDR_REGION_END_REWARM,
    #         ADDR_REGION_START_WAIT,
    #         ADDR_REGION_END_WAIT,
    #     )
    #     from sqlalchemy import or_

    #     session = db_instance.get_session()
    #     # 查询 Solder 表中 StationID 在 601 到 660 或 801 到 840 之间的数据
    #     solder_records = (
    #         session.query(Solder)
    #         .filter(
    #             or_(
    #                 Solder.StationID.between(ADDR_REGION_START_REWARM, ADDR_REGION_END_REWARM),
    #                 Solder.StationID.between(ADDR_REGION_START_WAIT,   ADDR_REGION_END_WAIT),
    #             )
    #         )
    #         .all()
    #     )
    #     session.close()
    #     # 遍历查询结果并执行操作
    #     for solder in solder_records:
    #         modbus_client.modbus_write("jcq", 5, int(solder.StationID), 1)

    #     return Response.SUCCESS("一键冷藏设置完成")

    write_value = [tag == 1]
    coil_status = modbus_client.modbus_write(
        "xq", write_value, int(c_a_dict[action]), 1
    )

    if not coil_status:
        return Response.FAIL("操作错误")
    return Response.SUCCESS(write_value)


def handle_auto_tag2(action):
    """监控是否在 1 秒内收到 tag=2，如果没有则自动执行 tag=2"""
    global pending_tag2, last_tag1_time

    time.sleep(1)  # 等待 1 秒

    with lock:
        # 如果仍然等待 tag=2，则自动执行 tag=2
        if pending_tag2 and (time.time() - last_tag1_time >= 1):
            pending_tag2 = False
            write_value = [False]
            coil_status = modbus_client.modbus_write(
                "xq", write_value, c_a_dict[action], 1
            )

            # 可根据需要记录日志或采取其他动作
            if not coil_status:
                print(f"自动执行 tag=2 操作失败 for action: {action}")
            else:
                print(f"自动执行 tag=2 操作成功 for action: {action}")


from threading import Event, Lock

# 全局变量与锁
heartbeat_event = Event()
lock = Lock()
is_heartbeat_active = False  # 标志位：心跳是否活跃
heartbeat_thread = None
stop_heartbeat_thread = False  # 标志位：是否停止线程
# from flask_socketio import SocketIO, emit
# 定义 tuned_dict
# 假设这是你定义的 tuned_dict
tuned_dict = {
    "X轴点动向左": 540,
    "X轴绝对定位": 541,
    "Y轴点动向前": 542,
    "Y轴绝对定位": 543,
    "Z轴点动向上": 544,
    "Z轴绝对定位": 545,
    "R1轴点动正转": 546,
    "R1轴绝对定位": 547,
    "搅拌电机转动一组": 548,
    "扫码旋转转动一组": 549,
    "X轴原点位置确认": 550,
    "Y轴原点位置确认": 551,
    "Z轴原点位置确认": 552,
    "R1轴回原点": 553,
    "搅拌电机回原点": 554,
    "X轴点动向右": 555,
    "Y轴点动向后": 556,
    "Z轴点动向下": 557,
    "R1轴点动反转": 558,
    "手动xy45度动作向上": 562,
    "手动xy45度动作向下": 563,
    "R2轴回原点": 568,
    "R2轴点动正转": 569,
    "R2轴绝对定位": 582,
    "R2轴点动反转": 583,
}


@sport_bp.route("/tuned_control", methods=["POST"])
def tuned_control():
    data = request.get_json()
    action = data.get("action")
    tag = data.get("tag")
    # # 使用锁来保证写操作的同步
    # with lock:
    # 根据 coil_status 的值来决定写入的值
    if tag == 1:  # 如果 coil_status 是 [True]，则写入 [False]
        write_value = [True]
    elif tag == 2:  # 如果 coil_status 不是 [True]，则写入 [True]
        write_value = [False]
    else:
        return Response.FAIL("tag不对")

    # 执行写操作
    result = modbus_client.modbus_write("xq", write_value, tuned_dict[action], 1)

    # 检查写操作的结果并返回
    if not result:
        return Response.FAIL("操作错误")
    else:
        return Response.SUCCESS()


@sport_bp.route("/tuned_operate", methods=["POST"])
def tuned_operate():
    tuned_dict = {"执行": 900, "停止": 901, "教导": 902}
    data = request.get_json()
    action = data.get("action")
    tag = data.get("tag")
    id = data.get("id")
    # 使用锁来保证写操作的同步
    with lock:
        # 根据 coil_status 的值来决定写入的值
        if tag == 1:  # 如果 coil_status 是 [True]，则写入 [False]
            write_value = [True]
        elif tag == 2:  # 如果 coil_status 不是 [True]，则写入 [True]
            write_value = [False]

        # 写寄存器
        if tuned_dict[action] == 902:
            result = modbus_client.modbus_write("jcq", id, 6221, 1)  # 施教
        else:
            result = modbus_client.modbus_write("jcq", id, 6220, 1)  # 到点
        # 写线圈
        result2 = modbus_client.modbus_write(
            "xq", write_value, int(tuned_dict[action]), 1
        )

        # 检查写操作的结果并返回
        if not result:
            return Response.FAIL("操作错误")
        else:
            return Response.SUCCESS(write_value)


@sport_bp.route("/tuned_speed", methods=["POST"])
def tuned_speed():
    tuned_dict = {
        "XYZR手动速度百分比": 1512,
        "X轴满载速度": 1514,
        "Y轴满载速度": 1516,
        "Z轴满载速度": 1518,
        "R轴满载速度": 1520,
        "XYZR自动速度百分比": 1538,
    }
    data = request.get_json()
    value = data.get("value")
    type = data.get("type")
    # 使用锁来保证写操作的同步
    with lock:
        if modbus_client.write_float(value, tuned_dict[type]):
            return Response.SUCCESS()
        # 检查写操作的结果并返回
        else:
            return Response.FAIL("操作错误")


@sport_bp.route("/get_speed", methods=["GET"])
def get_speed():
    tuned_dict = {
        "XYZR手动速度百分比": 1512,
        "X轴满载速度": 1514,
        "Y轴满载速度": 1516,
        "Z轴满载速度": 1518,
        "R轴满载速度": 1520,
        "XYZR自动速度百分比": 1538,
    }
    res = {}
    for key, value in tuned_dict.items():
        res[key] = modbus_client.read_float(value)
    return Response.SUCCESS(res)


@sport_bp.route("/switch_auto", methods=["GET"])
def switch_auto():
    # data = request.get_json()
    # tag = data.get("tag")
    with lock:
        # 读取当前 coil 状态
        coil_status = modbus_client.modbus_read("xq", 570, 1)
        if coil_status == [True]:  # 如果 coil_status 是 [True]，则写入 [False]
            write_value = [False]
        else:  # 如果 coil_status 不是 [True]，则写入 [True]
            write_value = [True]
        # 执行写操作
        result = modbus_client.modbus_write("xq", write_value, 570, 1)
        if result:
            return Response.SUCCESS(write_value[0])
        else:
            return Response.FAIL()


@sport_bp.route("/get_auto", methods=["GET"])
def get_auto():
    # 读取当前 coil 状态
    coil_status = modbus_client.modbus_read("xq", 570, 1)
    return Response.SUCCESS(coil_status[0])


@sport_bp.route("/get_is_stiring", methods=["GET"])
def get_is_stiring():
    return Response.SUCCESS(modbus_client.modbus_read("xq", 741, 1, slave=1)[0])


@sport_bp.route("/input_open", methods=["POST"])
def input_open():
    data = request.get_json()
    tag = data.get("tag")

    def delayed_write():
        """延迟 500ms 后写入 [False]"""
        time.sleep(0.5)  # 延迟 500ms
        with lock:
            modbus_client.modbus_write("xq", [False], 575, 1)

    # 使用锁来保证写操作的同步
    with lock:
        # 根据 tag 值决定写入的值
        if tag == 1:
            write_value = [True]
        elif tag == 2:
            write_value = [False]
        else:
            return Response.FAIL()

        result = modbus_client.modbus_write("xq", write_value, 575, 1)
        if result:
            # 如果写入 [True] 成功，启动延迟写入线程
            if write_value == [True]:
                threading.Thread(target=delayed_write, daemon=True).start()
            return Response.SUCCESS(write_value)
        else:
            return Response.FAIL()


@sport_bp.route("/output_open", methods=["POST"])
def output_open():
    data = request.get_json()
    tag = data.get("tag")
    # 使用锁来保证写操作的同步
    with lock:
        # 根据 coil_status 的值来决定写入的值
        if tag == 1:  # 如果 coil_status 是 [True]，则写入 [False]
            write_value = [True]
        elif tag == 2:  # 如果 coil_status 不是 [True]，则写入 [True]
            write_value = [False]
        result = modbus_client.modbus_write("xq", write_value, 576, 1)
        if result:
            return Response.SUCCESS(write_value)
        else:
            return Response.FAIL()
