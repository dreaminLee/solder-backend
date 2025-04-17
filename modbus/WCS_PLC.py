from pymodbus.client.sync import ModbusTcpClient
import random
import time

# 设置目标IP地址和端口
host = '127.0.0.1'
port = 502  # 默认的 Modbus TCP 端口

# 创建 Modbus TCP 客户端连接
client = ModbusTcpClient(host, port=port)

def PCB():
    # 连接到设备
    if client.connect():
        print("成功连接到设备 192.168.1.88")

        try:
            # 向201-215 (601, 661) (801, 841) (861, 871) (891, 893)的寄存器发送随机数字0, 1或2
            for register_address in range(891, 893):
                # 随机选择 0, 1 或 2
                value_to_send = random.choice([0, 1, 2])

                # 向寄存器写入数据
                result = client.write_register(register_address, value_to_send)

                # 检查是否写入成功
                if result.isError():
                    print(f"写入寄存器 {register_address} 失败: {result}")
                else:
                    print(f"成功写入寄存器 {register_address} 数据: {value_to_send}")

                # 稍作延时，避免过快地写入
                time.sleep(0.1)

        except KeyboardInterrupt:
            print("手动停止操作")

        finally:
            # 断开连接
            client.close()
            print("断开与设备的连接")

    else:
        print("无法连接到设备")

def xianquan():
    try:
        # 向201-215 (601, 661) (801, 841) (861, 871) (891, 893)的线圈批量写入
        # for register_address in range(500, 508):
            # 随机生成一个包含多个线圈的状态列表
            coils_to_send = [random.choice([True]) for _ in range(15)]  # 1个线圈状态

            # 向多个线圈写入数据
            result = client.write_coils(500, coils_to_send)

            # 检查是否写入成功
            if result.isError():
                print(f"写入线圈 {500} 失败: {result}")
            else:
                print(f"成功写入线圈 {500} 的状态: {coils_to_send}")

            # 稍作延时，避免过快地写入
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("手动停止操作")

    finally:
        # 断开连接
        client.close()
        print("断开与设备的连接")

xianquan()