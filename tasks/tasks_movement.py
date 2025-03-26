'''
    入库：从入柜区到冷藏区
'''
def task_move_in_area_to_cold_area():
    pass


'''
    从冷藏区到回温区
'''
def task_move_cold_area_to_rewarm_area():
    pass


'''
    从回温区到冷藏区
'''
def task_move_rewarm_area_to_cold_area():
    pass


'''
    从回温区到待取区（自动搅拌，流程中需要搅拌）
'''
def task_move_rewarm_area_to_ready_area():
    pass


'''
    从待取区到冷藏区
'''
def task_move_ready_area_to_cold_area():
    pass


'''
    从回温区出库（出库搅拌）
'''
def task_move_out_from_rewarm_area():
    pass


'''
    从待取区出库（自动搅拌，此时已搅拌过）
'''
def task_move_out_from_ready_area():
    pass
