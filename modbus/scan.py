import serial
import time

from util.logger import logger
from config.modbus_config import serial_port, serial_baudrate, serial_bytesize, serial_parity, serial_stopbits, serial_timeout

#
# def scan():
#     # 配置串口参数
#     port = 'COM1'  # 根据实际情况修改串口号
#     baudrate = 115200  # 根据扫描枪的波特率进行修改
#     bytesize = serial.EIGHTBITS
#     parity = serial.PARITY_NONE
#     stopbits = serial.STOPBITS_ONE
#     timeout = 1  # 超时时间，单位：秒
#
#     received_data = ""
#     try:
#         # 打开串口
#         ser = serial.Serial(port, baudrate, bytesize, parity, stopbits, timeout=timeout)
#         logger.info(f"成功打开串口: {port}")
#
#         # 要发送的 16 进制报文
#         hex_data = '16540D'
#         # 将 16 进制字符串转换为字节类型
#         byte_data = bytes.fromhex(hex_data)
#
#         # 发送报文
#         ser.write(byte_data)
#         logger.info(f"已发送报文: {hex_data}")
#         spin_timeout = 2 # 电机转一圈7秒
#         time.sleep(spin_timeout) # 等电机转一圈的时间
#         received_bytes = ser.read(ser.in_waiting)
#         logger.info(f"接收到的原始字节数据: {received_bytes}")
#         received_data += received_bytes.decode('utf-8', errors='ignore').strip()
#         logger.info(f"接收到有效的条码数据: {received_data}")
#
#     except serial.SerialException as e:
#         logger.info(f"串口打开失败: {e}")
#     except ValueError as e:
#         logger.info(f"数据转换错误: {e}")
#     finally:
#         # 关闭串口
#         if 'ser' in locals() and ser.is_open:
#             ser.close()
#             logger.info("串口已关闭。")
#     return received_data
#
#
# if __name__ == "__main__":
#     scan()


import serial
import time

from util.logger import logger


def scan():
    # 配置串口参数
    port = serial_port  # 根据实际情况修改串口号
    baudrate = serial_baudrate  # 根据扫描枪的波特率进行修改
    bytesize = serial_bytesize
    parity = serial_parity
    stopbits = serial_stopbits
    timeout = serial_timeout  # 超时时间，单位：秒

    try:
        # 打开串口
        ser = serial.Serial(port, baudrate, bytesize, parity, stopbits, timeout=timeout)
        print(f"成功打开串口: {port}")

        # 要发送的 16 进制报文
        hex_data = '16540D'
        # 将 16 进制字符串转换为字节类型
        byte_data = bytes.fromhex(hex_data)

        # 发送报文
        ser.write(byte_data)
        print(f"已发送报文: {hex_data}")
        # 延时 50 毫秒
        milliseconds = 500
        time.sleep(milliseconds / 1000)
        # 等待扫描枪返回数据
        wait_time = 10  # 最大等待时间，单位：秒
        start_time = time.time()
        while (time.time() - start_time) < wait_time:
            if ser.in_waiting > 0:
                time.sleep(3)
                print(f"检测到有 {ser.in_waiting} 字节的数据可用")
                logger.info(f"检测到有 {ser.in_waiting} 字节的数据可用")
                # 读取扫描枪返回的原始字节数据
                received_bytes = ser.read(ser.in_waiting)
                print(f"接收到的原始字节数据: {received_bytes}")
                logger.info(f"接收到的原始字节数据: {received_bytes}")
                try:
                    received_data = received_bytes.decode('utf-8', errors='ignore').strip()
                    print(f"接收到有效的条码数据: {received_data}")
                    logger.info(f"接收到有效的条码数据: {received_data}")
                    return received_data

                except UnicodeDecodeError as e:
                    print(f"解码错误: {e}")
                break
        else:
            print("未接收到扫描枪返回的数据。")
            logger.info("未接收到扫描枪返回的数据。")

    except serial.SerialException as e:
        print(f"串口打开失败: {e}")
        logger.info(f"串口打开失败: {e}")
    except ValueError as e:
        print(f"数据转换错误: {e}")
        logger.info(f"数据转换错误: {e}")
    finally:
        # 关闭串口
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("串口已关闭。")
            logger.info("串口已关闭。")

if __name__ == "__main__":
    scan()
