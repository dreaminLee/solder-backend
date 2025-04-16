from flask import Blueprint

from modbus.client import modbus_client
from util.Response import Response

sport_bp = Blueprint("warn", __name__)


@sport_bp.route("/get_warn_states", methods=["GET"])
def get_warn_states():
    def get_alarm_status(coil_status):
        # 定义报警状态字典
        alarm_dict = {
            "报警_X轴错误": coil_status[0],
            "报警_Y轴错误": coil_status[1],
            "报警_Z轴错误": coil_status[2],
            "报警_R轴错误": coil_status[3],
            "报警_相机扫描处电机错误": coil_status[4],
            "报警_搅拌电机错误": coil_status[5],
            "报警_出库滑台动作失败": coil_status[6],
            "报警_出库滑台复位失败": coil_status[7],
            "报警_冰箱门推拉动作失败": coil_status[8],
            "报警_冰箱门推拉复位失败": coil_status[9],
            "报警_冰箱门滑台动作失败": coil_status[10],
            "报警_冰箱门滑台复位失败": coil_status[11],
            "报警_模组夹爪气缸动作失败": coil_status[12],
            "报警_模组夹爪气缸复位失败": coil_status[13],
            "报警_模组180度旋转气缸动作失败": coil_status[14],
            "报警_模组180度旋转气缸复位失败": coil_status[15],
            "报警_模组45度旋转气缸动作失败": coil_status[16],
            "报警_模组45度旋转气缸复位失败": coil_status[17],
            "报警_相机扫码失败": coil_status[18],
            "报警_扫码解析失败": coil_status[19],
            "报警_冷藏区温度异常": coil_status[20],
            "报警_回温区温度异常": coil_status[21],
            "报警_气压传感器异常": coil_status[22],
            "报警_水箱液位传感器超限报警": coil_status[23],
            "报警_夹爪未正常抓取产品": coil_status[24],
            "报警_夹爪未正常放置产品": coil_status[25],
            "报警_WCS与PLC通讯异常": coil_status[26],
            "报警_设备急停状态": coil_status[27],
            "警告_安全门打开": coil_status[28],
            "警告_安全门报警屏蔽请注意安全": coil_status[29],
            "报警_备用1": coil_status[30],
            "报警_备用2": coil_status[31],
            "报警_备用3": coil_status[32],
            "报警_备用4": coil_status[33],
            "报警_备用5": coil_status[34],
            "报警_备用6": coil_status[35],
            "报警_备用7": coil_status[36],
            "报警_备用8": coil_status[37],
            "报警_备用9": coil_status[38],
            "报警_备用10": coil_status[39],
        }

        # 过滤出布尔值为 True 的报警项
        true_alarms = {k: v for k, v in alarm_dict.items() if v}

        # 返回布尔值为 True 的报警项
        return true_alarms

    # 读取线圈 62 到 75（共 14 个线圈）
    coil_status = modbus_client.modbus_read("xq", 700, 40)
    alarm_status = get_alarm_status(coil_status)
    # 检查读取的结果并返回
    if coil_status is None:
        return Response.FAIL("无法读取线圈状态")
    else:
        # 返回布尔值的列表
        return Response.SUCCESS(alarm_status)
