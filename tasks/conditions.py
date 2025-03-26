'''
    入柜区有点位状态是2
'''
def condition_in_area_to_cold_area():
    return True


'''
    冷藏时间满足 and (回温数量不足 or 预约时间 <= 现在时间 + 回温时间 + 搅拌时间)
'''
def condition_cold_area_to_rewarm_area():
    return True


'''
    超出最大出冷藏时间
'''
def condition_go_back_cold_area():
    return True


'''
    回温时间到 and 锡膏是自动搅拌 and (待取数量不足 or 预约时间 <= 现在时间 + 搅拌时间)
'''
def condition_rewarm_area_to_ready_area():
    return True


'''
    出库搅拌 and 用户点击出库
'''
def condition_to_be_stirred_out():
    return True


'''
    自动搅拌 and 用户点击出库
'''
def condition_already_stirred_out():
    return True


'''
    有锡膏在回温区或待取区
'''
def condition_cold_mode():
    return True
