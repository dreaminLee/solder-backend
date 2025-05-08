import threading
import time

from flask import Blueprint, request

from modbus.client import modbus_client
from models import Solder, Station
from router.sport import lock
from util.Response import Response
from util.db_connection import db_instance
from util.logger import logger

system_bp = Blueprint("system", __name__)


# @system_bp.route('/settings', methods=['GET'])
# def settings():
@system_bp.route("/on", methods=["GET"])
def on():
    modbus_client.modbus_write("xq", [True], 577, 1)
    return Response.SUCCESS()


@system_bp.route("/off", methods=["GET"])
def off():
    modbus_client.modbus_write("xq", [False], 578, 1)
    return Response.SUCCESS()


set_dict = {
    "冰柜温度设置": 1500,
    "温度采集周期": 1502,
    "回温区低温报警设置温度": 1504,
    "回温区高温报警设置温度": 1506,
    "冰柜内低温报警设置温度": 1508,
    "冰柜内高温报警设置温度": 1510,
}

config_dict = {
    "强制清除信息的库位号": 1540,
    "强制取出锡膏库位号": 1534,
    "系统配置_禁用门锁按钮": 1511,
    "系统配置_禁用蜂鸣按钮": 1512,
    "系统配置_禁用温度传感器报警": 1513,
    "系统配置_禁用气压传感器报警": 1514,
    "系统配置_禁用液位传感器报警": 1515,
    "Z轴取放上位置间距": 1536,
}
xq_dict = {"强制取出锡膏库位号": 1500, "强制清除信息的库位号": 579}
import util.global_args
import re


@system_bp.route("/settings", methods=["POST"])
def settings():
    data = request.get_json()
    value = data.get("value")
    type = data.get("type")

    # 根据不同的 type 进行处理
    if type == "Z轴取放上位置间距":
        return handle_z_axis_distance(value, type)

    if type == "强制清除信息的库位号" or type == "强制取出锡膏库位号":
        return handle_forced_clear_or_withdraw(value, type)

    if type in set_dict:
        return handle_set_dict(value, type)

    if type in config_dict:
        return handle_config_dict(value, type)

    return Response.FAIL("无效类型")


# 处理 Z轴取放上位置间距
def handle_z_axis_distance(value, type):
    if modbus_client.write_float(value, config_dict[type]):
        return Response.SUCCESS()
    else:
        return Response.FAIL()


# 处理强制清除或取出锡膏库位号
def handle_forced_clear_or_withdraw(value, type):
    session = db_instance.get_session()
    try:
        # 通过 merge 确保对象在 session 中
        station = session.query(Station).filter(Station.StationID == value).first()
        if station is not None:
            # 确保对象已经与 Session 绑定
            station = session.merge(station)

        if type == "强制清除信息的库位号":
            # 获取所有符合条件的 Solder 记录
            solders = session.query(Solder).filter_by(StationID=value).all()

            if not solders:
                return Response.FAIL("锡膏记录不存在")

            # 删除所有符合条件的 Solder 记录
            for solder in solders:
                session.delete(solder)
            modbus_client.modbus_write("jcq", 1, int(value), 1)

            session.commit()
            return Response.SUCCESS()

        if station and station.StaType:
            match = re.search(r"\[(\d+)\]", station.StaType)
            if match:
                result = int(match.group(1))
                if modbus_client.write_float(result, config_dict[type]):
                    modbus_client.modbus_write("xq", [True], xq_dict[type], 1)
                    return Response.SUCCESS()
            else:
                return Response.FAIL("未找到 [] 中的数字")
        else:
            return Response.FAIL("未找到该点位")

    except Exception as e:
        return Response.FAIL(f"数据库操作失败: {str(e)}")
    finally:
        session.close()


# 处理 set_dict 类型
def handle_set_dict(value, type):
    if modbus_client.write_float(value, set_dict[type]):
        if type == "温度采集周期":
            try:
                util.global_args.TEMP_COLLECTION_INTERVAL = value
            except Exception as e:
                return Response.FAIL(f"写入本地配置失败: {str(e)}")
        return Response.SUCCESS()
    else:
        return Response.FAIL("Modbus 操作失败")


# 处理 config_dict 类型
def handle_config_dict(value, type):
    if modbus_client.modbus_write("xq", [value], config_dict[type], 1):
        return Response.SUCCESS()
    else:
        return Response.FAIL("Modbus 写入失败")


@system_bp.route("/get_settings", methods=["GET"])
def get_settings():
    res = {}
    for key, value in set_dict.items():
        res[key] = modbus_client.read_float(value)
    for key, value in config_dict.items():
        res[key] = modbus_client.modbus_read("xq", value, 1)[0]
    return Response.SUCCESS(res)


@system_bp.route("/button", methods=["POST"])
def button():
    global pending_tag2, last_tag1_time

    data = request.get_json()
    action = data.get("action")
    tag = data.get("tag")
    c_a_dict = {
        "报警复位按钮": 571,
        "回原位按钮": 572,
        "一键冷藏按钮": 573,
        "系统配置_锡膏全部人工拿走后清除库位锡膏信息": 1516,
        "强制清除工位信息": 579,
        "强制关闭冰箱": 1517,
        "一键清步序ID": 580,
        "系统配置_强制取出库位锡膏": 1500,
    }

    if not action or not tag:
        return Response.FAIL("参数缺失")

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

    with lock:
        if c_a_dict[action] == 1516:
            # 当 action 为 1516 时，删除数据库表 Solder 中的所有数据
            session = db_instance.get_session()  # 创建一个数据库会话
            try:
                # 删除所有记录
                session.query(Solder).delete()
                session.commit()  # 提交事务
                print("已删除 Solder 表中的所有数据")
                return Response.SUCCESS("Solder 表中的数据已删除")
            except Exception as e:
                session.rollback()  # 如果有错误，回滚事务
                print(f"删除 Solder 表数据失败: {e}")
                return Response.FAIL("删除 Solder 表数据失败")
            finally:
                session.close()  # 关闭会话

        if 2000 < c_a_dict.get(action, 0):
            # 读取当前 coil 状态
            coil_status = modbus_client.modbus_read("xq", c_a_dict[action], 1)
            if coil_status == [True]:  # 如果 coil_status 是 [True]，则写入 [False]
                write_value = [False]
            else:  # 如果 coil_status 不是 [True]，则写入 [True]
                write_value = [True]
            # 执行写操作
            result = modbus_client.modbus_write("xq", write_value, c_a_dict[action], 1)
            if result:
                return Response.SUCCESS(write_value[0])
            else:
                return Response.FAIL()
        else:
            # 检查是否是 tag=1 的请求
            if tag == 1:
                # 更新最后的 tag=1 请求时间并设置 pending 状态
                last_tag1_time = time.time()
                pending_tag2 = True

                # 启动一个线程监控是否收到 tag=2
                threading.Thread(target=handle_auto_tag2, args=(action,)).start()

                # 立即执行 tag=1 的操作
                write_value = [True]
                coil_status = modbus_client.modbus_write(
                    "xq", write_value, c_a_dict[action], 1
                )

                if not coil_status:
                    return Response.FAIL("操作错误")
                return Response.SUCCESS(write_value)

            # 检查是否是 tag=2 的请求
            elif tag == 2:
                if not pending_tag2:
                    return Response.FAIL("未等待 tag=2 的状态")

                # 收到 tag=2，清除 pending 状态并执行操作
                pending_tag2 = False
                write_value = [False]
                coil_status = modbus_client.modbus_write(
                    "xq", write_value, c_a_dict[action], 1
                )

                if not coil_status:
                    return Response.FAIL("操作错误")
                return Response.SUCCESS(write_value)

    return Response.FAIL("未知的 tag 类型")


@system_bp.route("/write_mode", methods=["POST"])
def write_mode():
    """
    将模式写入 mode.txt 文件
    :param mode: 模式值（0 或 1）
    """
    is_moving = modbus_client.modbus_read("jcq", 102, 1)[0] != 0
    is_stiring = modbus_client.modbus_read("xq", 741, 1, slave=1)[0]
    is_req_scan = modbus_client.modbus_read("jcq", 111, 1)[0] != 0
    if is_moving or is_stiring or is_req_scan:
        return Response.FAIL("设备动作中，无法更改模式")
    data = request.get_json()
    mode = data.get("mode")
    if mode not in [0, 1, 2]:
        return Response.FAIL("模式必须是 0 冷藏模式 或 1 日常模式 或 2 预约模式")

    with open("mode.txt", "w") as file:
        file.write(str(mode))
    return Response.SUCCESS(f"模式已更改为 {mode} 并保存到 mode.txt")


@system_bp.route("/read_mode", methods=["GET"])
def read_mode():
    """
    从本地文件 mode.txt 中读取模式
    :return: 返回模式的整数（0 或 1）
    """
    try:
        with open("mode.txt", "r") as file:
            mode = file.read().strip()
            return Response.SUCCESS(int(mode))
    except FileNotFoundError:
        return Response.FAIL(-1)  # 如果文件不存在，默认返回 -1


@system_bp.route("/device_model", methods=["GET", "POST"])
def device_model():

    if request.method == "GET":
        with lock:
            res = modbus_client.modbus_read("jcq", 108, 1)
            if not res:
                return Response.FAIL("读寄存器失败")
            return Response.SUCCESS({"model": res[0]})

    elif request.method == "POST":
        data = request.get_json()
        model = data.get("model")

        if model is None:
            return Response.FAIL(f"参数缺失 model: {model}")

        res = modbus_client.modbus_write("jcq", model, 108, 1)
        if not res:
            return Response.FAIL(f"写寄存器失败 model: {model}")

        return Response.SUCCESS({"model": model})
