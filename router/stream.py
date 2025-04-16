import os
import subprocess
from threading import Thread, Lock

from click import DateTime
from flask import Blueprint, Response
from random import randint
import json
import time
from datetime import datetime

from dicts import alarm_dict
from modbus.client import modbus_client
from models import Alarm
from tasks.scheduler import file_path
from util.AES_util import validate_certificate, CERTIFICATE_FILE

# from util.activate_code import TRIAL_FILE, verify_extension_code
from util.db_connection import db_instance
from models import Station, Solder
import util.global_args

stream_bp = Blueprint("stream", __name__)

# @stream_bp.route('/timeStream')
# def time_stream():
#     def generate_data():
#         while True:
#             yield f"data: 当前时间是 {datetime.now()}\n\n"
#             time.sleep(1)
#     return Response(generate_data(), mimetype='text/event-stream')


@stream_bp.route("/capaStream")
def capa_stream():
    def generate_capa_data():
        while True:
            capacity_data = {
                "leng": {"total": randint(500, 600), "cur": randint(0, 500)},
                "hui": {"total": randint(200, 300), "cur": randint(0, 200)},
                "dai": {"total": randint(100, 150), "cur": randint(0, 100)},
                "hui_dai": {"total": randint(50, 100), "cur": randint(0, 50)},
                "yi": {"total": randint(10, 20), "cur": randint(0, 10)},
            }
            yield f"data: {json.dumps(capacity_data)}\n\n"
            time.sleep(1)

    return Response(generate_capa_data(), mimetype="text/event-stream")


@stream_bp.route("/tempStream")
def temp_stream():
    def generate_temp_data():
        while True:
            data = {
                "bg_shang": modbus_client.read_float(700),
                "bg_zhong": modbus_client.read_float(702),
                "bg_xia": modbus_client.read_float(704),
                "hui_wen": modbus_client.read_float(706),
            }
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(util.global_args.TEMP_COLLECTION_INTERVAL)

    return Response(generate_temp_data(), mimetype="text/event-stream")


# 用于存储上次的数据
last_cold_storage_count = None
last_warm_storage_count = None
last_waiting_pickup_count = None


@stream_bp.route("/get_storage_station", methods=["GET"])
def get_storage_station():
    def generate_sse_data():
        global last_cold_storage_count, last_warm_storage_count, last_waiting_pickup_count

        while True:
            try:
                session = db_instance.get_session()  # 获取数据库会话
                # 查询冷藏区数量
                cold_storage_count = (
                    session.query(Solder)
                    .filter(Solder.StationID.between(201, 539))
                    .count()
                )

                # 冷藏容量是固定值
                cold_storage_capacity = 539 - 201 + 1  # 339

                # 查询回温区数量
                warm_storage_count = (
                    session.query(Solder)
                    .filter(Solder.StationID.between(601, 660))
                    .count()
                )

                # 回温容量是固定值
                warm_storage_capacity = 660 - 601 + 1  # 60

                # 查询待取区数量
                waiting_pickup_count = (
                    session.query(Solder)
                    .filter(Solder.StationID.between(801, 870))
                    .count()
                )

                # 待取容量是固定值
                waiting_pickup_capacity = 870 - 801 + 1  # 70
                session.close()
                # 判断数据是否变化
                if (
                    cold_storage_count != last_cold_storage_count
                    or warm_storage_count != last_warm_storage_count
                    or waiting_pickup_count != last_waiting_pickup_count
                ):
                    # 组装 SSE 数据
                    data = {
                        "cold_storage_count": cold_storage_count,
                        "cold_storage_capacity": cold_storage_capacity,
                        "warm_storage_count": warm_storage_count,
                        "warm_storage_capacity": warm_storage_capacity,
                        "waiting_pickup_count": waiting_pickup_count,
                        "waiting_pickup_capacity": waiting_pickup_capacity,
                    }

                    # 将数据转换为 JSON 格式并通过 SSE 发送
                    yield f"data: {json.dumps(data)}\n\n"

                    # 更新上次数据
                    last_cold_storage_count = cold_storage_count
                    last_warm_storage_count = warm_storage_count
                    last_waiting_pickup_count = waiting_pickup_count

                # 如果没有变化，等一秒再查询
                time.sleep(1)

            except Exception as e:
                # 处理异常，避免 SSE 流被中断
                print(f"Error in SSE stream: {e}")
                break

    return Response(generate_sse_data(), mimetype="text/event-stream")


# 用于存储上次的数据
last_data = None


@stream_bp.route("/get_ruku_data", methods=["GET"])
def get_ruku_data():
    def generate_sse_data():
        global last_data
        while True:
            try:
                current_data = {}

                # 判断文件是否为空并读取内容
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    with open(file_path, "r") as file:
                        code = file.read()

                # 遍历 901 到 928 之间的数字
                for station_id in range(901, 929):
                    modbus_result = modbus_client.modbus_read("jcq", station_id, 1)

                    # 组装每个入库区的状态
                    for i, value in enumerate(modbus_result):
                        current_data[f"入库区{station_id + i}"] = (
                            value  # 假设你想通过 station_id 加上索引来构造入库区名称
                        )

                # 检查数据是否有变化
                if current_data != last_data:
                    # 组装 SSE 数据
                    data = {"ruku_data": current_data, "code": code}
                    # 将数据转换为 JSON 格式并通过 SSE 发送
                    yield f"data: {json.dumps(data)}\n\n"

                    # 更新上次的数据
                    last_data = current_data

                # 等待一秒再查询
                time.sleep(1)

            except Exception as e:
                # 处理异常，避免 SSE 流被中断
                print(f"Error in SSE stream: {e}")
                break

    return Response(generate_sse_data(), mimetype="text/event-stream")


# 定义后台任务函数
def background_db_task(alarm_data, alarm_type):
    """后台任务执行数据库操作，将报警信息存入数据库"""
    try:
        with db_instance.get_session() as session:
            for key, value in alarm_data.items():
                # 新建一个报警记录
                new_alarm = Alarm(
                    AlarmText=key,  # 报警文本为 key 值
                    StartTime=datetime.now() if alarm_type == "start" else None,
                    EndTime=datetime.now() if alarm_type == "end" else None,
                    Kind="警告" if alarm_dict.get(key) == 729 else "报警",
                )
                session.add(new_alarm)
            session.commit()  # 提交事务
            # print(f"成功将报警信息保存到数据库：{alarm_data}，Type: {alarm_type}")
    except Exception as e:
        print(f"数据库操作失败: {e}")


# SSE 流的生成函数
@stream_bp.route("/get_warn_states", methods=["GET"])
def get_warn_states():
    def generate_sse_data():
        previous_alarm_data = {"安全门报警屏蔽请注意安全": True}  # 保存上次的报警数据

        while True:
            try:
                alarm_data = {}
                for key, value in alarm_dict.items():
                    # 读取当前报警信息
                    current_value = modbus_client.modbus_read("xq", int(value), 1)[0]
                    alarm_data[key] = current_value

                # 找出从 False 到 True 的变化（启动报警）
                changed_to_true = {
                    k: v
                    for k, v in alarm_data.items()
                    if previous_alarm_data.get(k) == 0 and v == 1
                }

                # 找出从 True 到 False 的变化（结束报警）
                changed_to_false = {
                    k: v
                    for k, v in alarm_data.items()
                    if previous_alarm_data.get(k) == 1 and v == 0
                }

                # 如果有从 False 到 True 的变化，处理为 Type="start"
                if changed_to_true:
                    thread = Thread(
                        target=background_db_task, args=(changed_to_true, "start")
                    )
                    thread.start()

                # 如果有从 True 到 False 的变化，处理为 Type="end"
                if changed_to_false:
                    thread = Thread(
                        target=background_db_task, args=(changed_to_false, "end")
                    )
                    thread.start()

                # 更新之前的数据
                previous_alarm_data = alarm_data.copy()

                # 将数据转换为 JSON 格式并通过 SSE 发送
                yield f"data: {json.dumps(previous_alarm_data)}\n\n"

            except Exception as e:
                print(f"Error in SSE stream: {e}")
                break

    return Response(generate_sse_data(), mimetype="text/event-stream")


# @stream_bp.route('/get_location', methods=['GET'])
# def get_location():
#     # data = request.get_json()
#     # 读取当前 coil 状态
#     location = modbus_client.modbus_read("PCB", 708, 8)
#
#     return Response(f"{json.dumps(location)}", mimetype='text/event-stream')

# 假设 modbus_client 是你已经连接的 Modbus 客户端对象
# 通过锁来确保读取和数据比较的线程安全
lock = Lock()

# 初始化上次的值
last_location_data = {}
last_speed_data = {}


def read_location_data():
    return {
        "x_location": round(modbus_client.read_float(708), 2),
        "y_location": round(modbus_client.read_float(712), 2),
        "z_location": round(modbus_client.read_float(716), 2),
        "r_location": round(modbus_client.read_float(720), 2),
    }


def read_speed_data():
    return {
        "x_speed": round(modbus_client.read_float(710), 2),
        "y_speed": round(modbus_client.read_float(714), 2),
        "z_speed": round(modbus_client.read_float(718), 2),
        "r_speed": round(modbus_client.read_float(722), 2),
    }


def generate_sse_data(data_type):
    global last_location_data, last_speed_data

    while True:
        try:
            with lock:  # 保证线程安全
                if data_type == "location":
                    new_data = read_location_data()
                    # 检查数据是否有变化
                    if new_data != last_location_data:
                        last_location_data = new_data
                        yield f"data: {json.dumps(new_data)}\n\n"
                elif data_type == "speed":
                    new_data = read_speed_data()
                    # 检查数据是否有变化
                    if new_data != last_speed_data:
                        last_speed_data = new_data
                        yield f"data: {json.dumps(new_data)}\n\n"
            time.sleep(1)

        except Exception as e:
            # 处理异常，避免 SSE 流被中断
            print(f"Error in SSE stream: {e}")
            break


@stream_bp.route("/get_location", methods=["GET"])
def get_location():
    return Response(generate_sse_data("location"), mimetype="text/event-stream")


@stream_bp.route("/get_speed", methods=["GET"])
def get_speed():
    return Response(generate_sse_data("speed"), mimetype="text/event-stream")


@stream_bp.route("/trial_clock", methods=["GET"])
def trial_clock():
    def generate_sse_data():
        while True:
            try:
                with open(CERTIFICATE_FILE, "r") as file:
                    extension_code = json.load(file)

                if not extension_code:
                    return

                is_valid, remaining_time = validate_certificate(extension_code)
                if is_valid:
                    data = {"remain": remaining_time}
                else:
                    data = {"remain": -99999999}
                yield f"data: {json.dumps(data)}\n\n"
                time.sleep(1)

            except Exception as e:
                # 处理异常，避免 SSE 流被中断
                print(f"Error in SSE stream: {e}")
                break

    return Response(generate_sse_data(), mimetype="text/event-stream")


@stream_bp.route("/monitor_video", methods=["GET"])
def monitor_video():
    # RTSP 视频流的 URL
    rtsp_url = "rtsp://admin:jonsion1@192.168.1.64/h264/ch1/main/av_stream"

    # 使用 FFmpeg 将 RTSP 流转码为 MP4 格式并通过管道传输数据
    def generate():
        try:
            process = subprocess.Popen(
                [
                    r"D:\ffmpeg-7.0.2-essentials_build\bin\ffmpeg.exe",  # FFmpeg 可执行文件路径
                    "-i",
                    rtsp_url,  # RTSP 输入地址
                    "-c:v",
                    "libx264",  # 使用 H.264 编解码器
                    "-preset",
                    "ultrafast",  # 编码速度设置为最快
                    "-f",
                    "mp4",  # 输出格式为 MP4
                    "-tune",
                    "zerolatency",  # 优化为低延迟模式
                    "-b:v",
                    "1M",  # 设置视频比特率
                    "-an",  # 禁用音频
                    "pipe:1",  # 输出到管道，传输数据到标准输出
                ],
                stdout=subprocess.PIPE,  # 获取标准输出流（视频流）
                stderr=subprocess.PIPE,  # 获取错误流
            )
            # 逐行读取 stderr 和 stdout
            while True:
                stdout_line = process.stdout.readline()
                stderr_line = process.stderr.readline()

                if stdout_line:
                    yield stdout_line  # 逐帧输出数据
                if stderr_line:
                    print("FFmpeg Error Output:", stderr_line.decode(), file=sys.stderr)
                #
                # # 进程结束并且没有更多输出时退出
                # if not stdout_line and not stderr_line and process.poll() is not None:
                #     break

            # while True:
            #     # 从 FFmpeg 标准输出流读取数据
            #     data = process.stdout.read(1024)
            #     if not data:
            #         break
            #     yield data  # 将读取到的数据发送给客户端

        except Exception as e:
            print(f"Error occurred while processing video stream: {e}")

    # 返回生成的视频流，设置 MIME 类型为 video/mp4
    return Response(generate(), mimetype="video/mp4")
