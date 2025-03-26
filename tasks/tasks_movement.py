def task_move_in_area_to_cold_area(cold_area_empty: int):
    """
    入库：从入柜区到冷藏区
    :param cold_area_empty: 当前未放置锡膏的冷藏区点位
    """


def task_move_cold_area_to_rewarm_area(solder_to_move: Solder, rewarm_area_empty: int):
    """
    从冷藏区到回温区
    :param solder_to_move: 待移动的锡膏
    :param rewarm_area_empty: 当前未放置锡膏的回温区点位
    """
    pass


def task_move_rewarm_area_to_cold_area(solder_to_move: Solder, cold_area_empty: int):
    """
    从回温区到冷藏区
    :param solder_to_move: 待移动的锡膏
    :param cold_area_empty:
    """
    pass


def task_move_rewarm_area_to_ready_area(solder_to_move: Solder, ready_area_empty: int):
    """
    从回温区到待取区（自动搅拌，流程中需要搅拌）
    :param solder_to_move: 待移动的锡膏
    :param ready_area_empty: 当前未放置锡膏的待取区点位
    """
    pass


def task_move_ready_area_to_cold_area(solder_to_move: Solder, cold_area_empty: int):
    """
    从待取区到冷藏区
    :param solder_to_move: 待移动的锡膏
    :param cold_area_empty: 当前未放置锡膏的冷藏区点位
    """
    pass


def task_move_out_from_rewarm_area(solder_to_move: Solder):
    """
    从回温区出库（出库搅拌）
    :param solder_to_move: 待移动的锡膏
    """
    pass


def task_move_out_from_ready_area(solder_to_move: Solder):
    """
    从待取区出库（自动搅拌，此时已搅拌过）
    :param solder_to_move: 待移动的锡膏
    """
    pass
