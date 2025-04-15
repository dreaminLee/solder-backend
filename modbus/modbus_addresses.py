from enum import IntEnum, Enum
import functools
from config.modbus_config import region_setting

class ADDR_ROBOT_STATUS(IntEnum):
    GET = 100
    PUT = 101
    ACT = 102


class ADDR_ROBOT_CONFIRM(IntEnum):
    GET = 105
    PUT = 106
    ACT = 107


class ADDR_SCANNER_STATUS(IntEnum):
    POS = 110
    REQ = 111


class ADDR_SCANNER_CONFIRM(IntEnum):
    POS = 140
    RET = 141


class REGION_TYPE(Enum):
    ENTER  = 0
    SCAN   = 1
    COLD   = 2
    REWARM = 3
    WAIT   = 4
    FETCH  = 5


ADDR_STIRING_STATUS = 741

ADDR_REGION_START_ENTER  = region_setting["addr_region_start_enter"]
ADDR_REGION_END_ENTER    = region_setting["addr_region_end_enter"]
ADDR_REGION_START_SCAN   = region_setting["addr_region_start_scan"]
ADDR_REGION_END_SCAN     = region_setting["addr_region_end_scan"]
ADDR_REGION_START_COLD   = region_setting["addr_region_start_cold"]
ADDR_REGION_END_COLD     = region_setting["addr_region_end_cold"]
ADDR_REGION_START_REWARM = region_setting["addr_region_start_rewarm"]
ADDR_REGION_END_REWARM   = region_setting["addr_region_end_rewarm"]
ADDR_REGION_START_WAIT   = region_setting["addr_region_start_wait"]
ADDR_REGION_END_WAIT     = region_setting["addr_region_end_wait"]
ADDR_REGION_START_FETCH  = region_setting["addr_region_start_fetch"]
ADDR_REGION_END_FETCH    = region_setting["addr_region_end_fetch"]


def in_region(region_start, region_end, addr):
    return region_start <= addr and addr <= region_end


in_region_enter  = functools.partial(in_region, ADDR_REGION_START_ENTER, ADDR_REGION_END_ENTER)
in_region_scan   = functools.partial(in_region, ADDR_REGION_START_SCAN, ADDR_REGION_END_SCAN)
in_region_cold   = functools.partial(in_region, ADDR_REGION_START_COLD, ADDR_REGION_END_COLD)
in_region_rewarm = functools.partial(in_region, ADDR_REGION_START_REWARM, ADDR_REGION_END_REWARM)
in_region_wait   = functools.partial(in_region, ADDR_REGION_START_WAIT, ADDR_REGION_END_WAIT)
in_region_fetch  = functools.partial(in_region, ADDR_REGION_START_FETCH, ADDR_REGION_END_FETCH)


def region_addr_to_region_name(addr):
    if in_region_enter(addr):
        return "入柜区"
    elif in_region_scan(addr):
        return "扫码区"
    elif in_region_cold(addr):
        return "冷藏区"
    elif in_region_rewarm(addr):
        return "回温区"
    elif in_region_wait(addr):
        return "待取区"
    elif in_region_fetch(addr):
        return "取料区"
    else:
        return "未知"
