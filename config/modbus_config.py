from .read_config import config_dict

tcp_host = ""
tcp_port = 502
serial_port = ""
serial_baudrate = 115200
serial_bytesize = 8 # 5, 6, 7, 8
serial_parity = 'N' # PARITY_NONE, PARITY_EVEN, PARITY_ODD, PARITY_MARK, PARITY_SPACE = 'N', 'E', 'O', 'M', 'S'
serial_stopbits = 1 # STOPBITS_ONE, STOPBITS_ONE_POINT_FIVE, STOPBITS_TWO = (1, 1.5, 2)
serial_timeout = 1
region_settings = {
    "addr_region_enter_start": 901,
    "addr_region_enter_end": 928,
    "addr_region_cold_start": 201,
    "addr_region_cold_end": 580,
    "addr_region_rewarm_start": 603,
    "addr_region_rewarm_end": 700,
    "addr_region_wait_start": 803,
    "addr_region_wait_end": 840
}

locals().update(config_dict["modbus_config"])
