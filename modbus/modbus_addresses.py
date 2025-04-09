from enum import IntEnum, Enum
import functools

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

ADDR_REGION_ENTER_START  = 901
ADDR_REGION_ENTER_END    = 928
ADDR_REGION_SCAN         = 190 # 仅作识别使用，禁止读写
ADDR_REGION_COLD_START   = 201
ADDR_REGION_COLD_END     = 580
ADDR_REGION_REWARM_START = 601
ADDR_REGION_REWARM_END   = 700
ADDR_REGION_WAIT_START   = 801
ADDR_REGION_WAIT_END     = 840
ADDR_REGION_FETCH_START  = 891
ADDR_REGION_FETCH_END    = 892


def region_addr_to_region_name(addr):
    if ADDR_REGION_ENTER_START  <= addr and addr <= ADDR_REGION_ENTER_END:
        return "入柜区"
    elif ADDR_REGION_SCAN == addr:
        return "扫码区"
    elif ADDR_REGION_COLD_START   <= addr and addr <= ADDR_REGION_COLD_END:
        return "冷藏区"
    elif ADDR_REGION_REWARM_START <= addr and addr <= ADDR_REGION_REWARM_END:
        return "回温区"
    elif ADDR_REGION_WAIT_START   <= addr and addr <= ADDR_REGION_WAIT_END:
        return "待取区"
    elif ADDR_REGION_FETCH_START  <= addr and addr <= ADDR_REGION_FETCH_END:
        return "取料区"
    else:
        return "未知"


def in_region(region_start, region_end, addr):
    return region_start <= addr and addr <= region_end

in_region_cold   = functools.partial(in_region, ADDR_REGION_COLD_START,   ADDR_REGION_COLD_END)
in_region_rewarm = functools.partial(in_region, ADDR_REGION_REWARM_START, ADDR_REGION_REWARM_END)
in_region_wait   = functools.partial(in_region, ADDR_REGION_WAIT_START,   ADDR_REGION_WAIT_END)
