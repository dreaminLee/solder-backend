from pymodbus.client.sync import ModbusTcpClient
import time

# 设置目标IP地址和端口
host = '192.168.1.88'
port = 502  # 默认的 Modbus TCP 端口

# 创建 Modbus TCP 客户端连接
client = ModbusTcpClient(host, port=port)

def PCB():
    # 连接到设备
    if client.connect():
        print("成功连接到设备 192.168.1.88")

        try:
            while True:
                # 调整寄存器地址，尝试读取 40900 开始的寄存器（确保地址是正确的）
                result = client.read_holding_registers(901, 50)  # 读取 50 个寄存器
                # result = client.read_holding_registers(990, 2)  # 读取 50 个寄存器

                if result.isError():
                    print(f"读取寄存器失败: {result}")
                else:
                    # 输出读取到的寄存器数据
                    print(f"读取到的寄存器数据: {result.registers}")

                # 每隔 1 秒钟读取一次数据
                time.sleep(1)

        except KeyboardInterrupt:
            print("手动停止监听")

        finally:
            # 断开连接
            client.close()
            print("断开与设备的连接")

    else:
        print("无法连接到设备")
def xianquan():
    # 连接到设备
    if client.connect():
        print("成功连接到设备 192.168.1.88")

        try:
            # 读取线圈的状态
            result = client.read_coils(500, 8)  # 读取一个线圈

            if result.isError():
                print(f"读取线圈失败: {result}")
            else:
                coil_status = result.bits  # 获取线圈的状态
                print(f"线圈的状态: {coil_status}")

            # 稍作延时，避免过快地读取
            time.sleep(0.1)

        except KeyboardInterrupt:
            print("手动停止操作")

        finally:
            # 断开连接
            client.close()
            print("断开与设备的连接")

    else:
        print("无法连接到设备")

xianquan()