import logging
import random
import struct
import time
from pymodbus.client.sync import ModbusTcpClient
import re
from time import sleep

from util.logger import logger
from config.modbus_config import tcp_host, tcp_port

# 设置日志
logging.basicConfig(level=logging.INFO)

class ModbusClientSingleton:
    _instance = None
    _client: ModbusTcpClient = None

    def __new__(cls, host=tcp_host, port=tcp_port):
        """创建单例客户端，并在创建时自动连接设备"""
        if cls._instance is None:
            cls._instance = super(ModbusClientSingleton, cls).__new__(cls)
            cls._instance._client = ModbusTcpClient(host, port)
            if cls._instance._client.connect():
                logging.info(f"成功连接到设备 {tcp_host}:{tcp_port}")
            else:
                logging.error("无法连接到设备")
        return cls._instance

    def disconnect(self):
        """断开连接"""
        if self._client.is_socket_open():
            self._client.close()
            logging.info("断开与设备的连接")
        else:
            logging.warning("连接已经关闭，无需再次断开")

    def is_connected(self):
        """检查是否已连接"""
        return self._client.is_socket_open()

    def modbus_read(self, type: str, address:int, count: int, unit=0):
        """读取寄存器或线圈"""
        try:
            # address=int(address)
            if type == "jcq":
                # 调整寄存器地址，尝试读取 40900 开始的寄存器（确保地址是正确的）
                result = self._client.read_holding_registers(address=address, count=count, unit=unit)  # 读取指定数量的寄存器

                if result.isError():
                    logging.error(f"读取寄存器失败: {result}")
                else:
                    # logging.info(f"读取到的寄存器数据: {result.registers}")
                    return result.registers
            else:
                # 读取线圈的状态
                result = self._client.read_coils(address=address, count=count, unit=unit)  # 读取一个线圈

                if result.isError():
                    logging.error(f"读取线圈失败: {result}")
                else:
                    coil_status = result.bits  # 获取线圈的状态
                    # logging.info(f"线圈的状态: {coil_status}")
                    return coil_status[:count]

        except Exception as e:
            logging.error(f"读取失败: {e}")
        # finally:
            # return None
            # print("读取操作结束")

    def modbus_write(self, type: str, content, address:int, count: int, unit=0):
        """向寄存器或线圈写入数据"""
        try:
            # address=int(address)
            if type == "jcq":
                # 向201-215 (601, 661) (801, 841) (861, 871) (891, 893)的寄存器发送随机数字0, 1或2
                for register_address in range(address, address + count):
                    value_to_send = content  # random.choice([0, 1, 2])  # 随机选择 0, 1 或 2

                    # 向寄存器写入数据
                    result = self._client.write_register(register_address, value_to_send, unit=unit)

                    # time.sleep(0.1)
                    # 检查是否写入成功
                    if result.isError():
                        logging.error(f"写入寄存器 {register_address} 失败: {result}")
                    # else:
                        # logging.info(f"成功写入寄存器 {register_address} 数据: {value_to_send}")
                return True

            else:
                # 向多个线圈写入数据
                coils_to_send = content
                result = self._client.write_coils(address=address, values=coils_to_send, unit=unit)

                # time.sleep(0.1)
                if result.isError():
                    logging.error(f"写入线圈 {address} 失败: {result}")
                    return False
                else:
                    # logging.info(f"成功写入线圈 {address} 的状态: {coils_to_send}")
                    return True

        except Exception as e:
            logging.error(f"写入失败: {e}")
            return False
        finally:
            # logging.info("写入操作结束")
            return True

    def write_ascii_string(self, register_address:int, input_string:str):
        """
        将 ASCII 字符串写入 Modbus 寄存器
        :param register_address: 起始寄存器地址
        :param input_string: 需要写入的 ASCII 字符串
        :return: 是否成功写入
        """
        # 计算每个字符需要的寄存器数量
        num_registers = (len(input_string) + 1) // 2  # 每两个字符占一个寄存器，计算寄存器数量
        # register_address=int(register_address)
        # 准备写入的寄存器值
        registers = []
        for i in range(0, len(input_string), 2):
            # 取每两个字符作为一个寄存器值，确保每个寄存器存储两个字符
            high_byte = ord(input_string[i])  # 高字节
            low_byte = ord(input_string[i + 1]) if i + 1 < len(input_string) else 0  # 低字节

            # 将两个字节组合成一个寄存器值
            register_value = (high_byte << 8) | low_byte
            registers.append(register_value)

        # 使用 Modbus 客户端写入寄存器
        try:
            result = self._client.write_registers(register_address, registers, unit=1)
            if result.isError():
                logging.error("写入寄存器数据时出错")
                return False
            return True
        except Exception as e:
            logging.error("写入寄存器时发生异常: %s", e)
            return False

    def read_float(self,address):
        address=int(address)
        # 读取 708 和 709 寄存器的值（假设每个寄存器存储 16 位数据）
        result = self._client.read_holding_registers(address, 2, unit=1)  # 读取 2 个寄存器（708 和 709）

        if result.isError():
            logging.error("读取寄存器失败！")
        else:
            # 将寄存器值转换为字节（每个寄存器是 2 字节，16 位）
            # `struct.pack` 将整数转换为二进制字节
            # 以大端序方式将两个寄存器的数据转换为字节
            byte_data = struct.pack('>HH', result.registers[1], result.registers[0])
            float_v = struct.unpack('>f', byte_data)[0]
            return float_v

    import struct
    import logging

    def read_float_test(self, start_address, end_address):
        start_address = int(start_address)
        end_address = int(end_address)

        if end_address < start_address:
            logging.error("结束地址必须大于或等于起始地址！")
            return []

        # 计算需要读取的寄存器数量
        num_registers = (end_address - start_address + 1)

        # 每次读取的最大寄存器数量（设为 124）
        max_registers_per_request = 124

        float_values = []
        for i in range(start_address, end_address + 1, max_registers_per_request):
            # 计算当前批次的寄存器数量
            current_batch_end = min(i + max_registers_per_request - 1, end_address)
            num_registers_batch = current_batch_end - i + 1

            # 打印当前读取的寄存器范围
            print(f"正在读取寄存器：起始地址 {i}，结束地址 {current_batch_end}，数量 {num_registers_batch}")

            # 读取寄存器的值
            result = self._client.read_holding_registers(i, num_registers_batch, unit=1)

            if result.isError():
                logging.error(f"读取寄存器失败！起始地址: {i}，结束地址: {current_batch_end}")
                continue  # 跳过当前批次，继续读取后续寄存器

            # 打印读取的寄存器值
            print(f"读取的寄存器值：{result.registers}")

            # 将寄存器值转换为字节，每2个寄存器为一个 float
            for j in range(0, num_registers_batch, 2):
                byte_data = struct.pack('>HH', result.registers[j + 1], result.registers[j])  # 大端字节序
                float_v = struct.unpack('>f', byte_data)[0]  # 转换成 float
                float_values.append(float_v)

                # 打印转换后的浮动值
                print(f"转换后的浮动值：{float_v}")

        return float_values

    def read_float_ASCII(self, address_from: int, address_to: int):
        """
        读取指定地址范围内的 Modbus 寄存器，并将其解析为 ASCII 格式的浮动值
        :param address_from: 起始地址
        :param address_to: 结束地址
        :return: 解析后的浮动值
        """
        length = address_to - address_from + 1  # 计算要读取的寄存器数量
        result = self._client.read_holding_registers(address_from, length, unit=1)

        if result.isError():
            logger.error("读取寄存器数据时出错")
            return None
        else:
            registers = result.registers  # 获取寄存器数据

            # 交换寄存器中的高字节和低字节（每个寄存器有两个字节）
            swapped_registers = []
            for reg in registers:
                # 对每个寄存器中的两个字节进行交换
                swapped_reg = ((reg >> 8) & 0xFF) | ((reg & 0xFF) << 8)
                swapped_registers.append(swapped_reg)

            # 将寄存器值转换为字节数据（每个寄存器 2 字节）
            byte_data = struct.pack(f'>{length}H', *swapped_registers)

            # 打印原始字节数据
            logger.info("原始字节数据: %s", byte_data)

            # 解析字节数据为 ASCII 字符
            try:
                ascii_str = byte_data.decode('ascii')  # 假设 Modbus 返回的是 ASCII 编码字符串
                return ascii_str
            except UnicodeDecodeError as e:
                logger.error("字节数据无法解码为 ASCII 字符串: %s", e)
                return None

            # try:
            #     extracted = re.sub(r'[^a-zA-Z0-9]', '', ascii_str)
            #     return extracted
            # except ValueError:
            #     logging.error("无法将 ASCII 字符串转换为浮动值: %s", ascii_str)
            #     return None

    def write_ASCII_string_to_registers(self, address_from, address_to, ascii_string):
        """
        将 ASCII 字符串写入 Modbus 寄存器，并交换每两个字节的顺序
        :param address_from: 起始地址
        :param address_to: 结束地址
        :param ascii_string: 需要写入的 ASCII 字符串
        :return: 是否成功写入
        """
        address_from=int(address_from)
        address_to=int(address_to)
        # 计算需要的寄存器数量（每个寄存器包含 2 个字节）
        required_length = address_to - address_from + 1
        byte_data = ascii_string.encode('ascii')  # 将字符串转换为字节数据

        # 如果字节长度不符合要求，返回错误
        if len(byte_data) != required_length * 2:
            logging.error("字节数据长度与寄存器范围不匹配")
            return False

        # 交换每两个字节的位置
        swapped_bytes = []
        for i in range(0, len(byte_data), 2):
            # 交换高字节和低字节
            swapped_bytes.append(byte_data[i + 1])  # 低字节
            swapped_bytes.append(byte_data[i])  # 高字节

        # 将字节数据转换为寄存器数据
        registers = []
        for i in range(0, len(swapped_bytes), 2):
            register = (swapped_bytes[i] << 8) + swapped_bytes[i + 1]  # 组合成寄存器值
            registers.append(register)

        # 检查寄存器数量是否符合要求
        if len(registers) != required_length:
            logging.error("寄存器数量与目标地址范围不匹配")
            return False

        # 写入寄存器
        try:
            result = self._client.write_holding_registers(address_from, registers, unit=1)
            if result.isError():
                logging.error("写入寄存器数据时出错")
                return False
            return True
        except Exception as e:
            logging.error("写入寄存器时发生异常: %s", e)
            return False

    def write_float(self,float_v:float,add:int):
        byte_data = struct.pack('>f', float_v)
        register1, register0 = struct.unpack('>HH', byte_data)
        modbus_client.modbus_write('jcq', register0, int(add), 1)
        modbus_client.modbus_write('jcq',register1,int(add+1),1)
        return True

    """
        读一片连续的保持寄存器
    """
    def read_region(self, region_start, region_len, unit=0):
        bulk_len = 100
        read_addr = region_start
        res = []

        while region_len:
            # print(f"{read_addr}: {bulk_len if bulk_len <= region_len else region_len}")
            bulk = self._client.read_holding_registers(read_addr, bulk_len if bulk_len <= region_len else region_len, unit=unit).registers
            res += bulk
            # print(len(res))
            region_len -= len(bulk)
            read_addr += len(bulk)

        return res

    """
        写一片连续的保持寄存器
    """
    def write_region(self, region_start, content, unit=0):
        bulk_len = 100
        write_addr = region_start
        nums_written = 0

        while nums_written < len(content):
            resp = self._client.write_registers(write_addr, content[nums_written:nums_written+bulk_len], unit=unit)
            sleep(0.01)
            nums_written += bulk_len
            write_addr += bulk_len

# 使用示例
# if __name__ == "__main__":
#     # 获取 Modbus 客户端单例（会自动连接设备）
modbus_client = ModbusClientSingleton()
# res=modbus_client.read_float(2001)
# print(res)
# modbus_client.modbus_write("jcq",1,710,2)
# res=modbus_client.modbus_read("jcq",710,2)
# print(res)
# res=modbus_client.modbus_read("xq",500,9)
# print(res)
#
#     # 使用 Modbus 客户端进行读取操作
#     modbus_client.modbus_read("PCB", 40901, 50)
#
#     # 使用 Modbus 客户端进行写入操作
#     modbus_client.modbus_write("PCB", [random.choice([0, 1, 2]) for _ in range(5)], 40901, 5)
#
#     # 断开连接
#     modbus_client.disconnect()
