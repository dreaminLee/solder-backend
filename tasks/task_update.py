import collections
from datetime import datetime, timedelta

from models import Solder, SolderModel
from util.db_connection import db_instance
from util.logger import logger
from modbus.client import modbus_client
from modbus.modbus_addresses import ADDR_REGION_COLD_START, ADDR_REGION_COLD_END
from modbus.modbus_addresses import ADDR_REGION_REWARM_START, ADDR_REGION_REWARM_END
from modbus.modbus_addresses import ADDR_REGION_WAIT_START, ADDR_REGION_WAIT_END
from modbus.modbus_addresses import in_region_cold, in_region_rewarm, in_region_wait


def task_update():
    """
        回温区——冷藏区：超出最大回温时间
        待取区——冷藏区：超出最大回温时间
        冷藏区——回温区：保持回温数量不足
        回温区——待取区：保持待取数量不足
    """
    with db_instance.get_session() as db_session:

        logger.info("开始更新点位状态")

        solders: list[Solder] = db_session.query(Solder).all()
        solder_models: list[SolderModel] = db_session.query(SolderModel).all()
        solders: dict[str, Solder] = {solder.SolderCode: solder for solder in solders}
        solder_models: dict[str, SolderModel] = {model.Model: model for model in solder_models}

        region_cold   = {k: 1 for k in range(ADDR_REGION_COLD_START,   ADDR_REGION_COLD_END+1)}
        region_rewarm = {k: -1 for k in range(ADDR_REGION_REWARM_START, ADDR_REGION_REWARM_END+1)}
        region_wait   = {k: -1 for k in range(ADDR_REGION_WAIT_START,   ADDR_REGION_WAIT_END+1)}

        # region_rewarm_now = modbus_client.read_region(ADDR_REGION_REWARM_START, ADDR_REGION_REWARM_END - ADDR_REGION_REWARM_START + 1)
        # region_wait_now   = modbus_client.read_region(ADDR_REGION_WAIT_START,   ADDR_REGION_WAIT_END   - ADDR_REGION_WAIT_START + 1)
        # region_rewarm_now = {k: v for k, v in zip(range(ADDR_REGION_REWARM_START, ADDR_REGION_REWARM_END + 1), region_rewarm_now)}
        # region_wait_now   = {k: v for k, v in zip(range(ADDR_REGION_WAIT_START,   ADDR_REGION_WAIT_END + 1), region_wait_now)}

        # 过滤正在取出的锡膏
        solders_out_now: dict[str, Solder] = {
            solder_code: solder
            for solder_code, solder in solders.items()
            if (in_region_rewarm(solder.StationID) and
               #region_rewarm_now[solder.StationID] == 22 and
                modbus_client.modbus_read("jcq", solder.StationID, 1)[0] == 22) or

               (in_region_wait(solder.StationID) and
               #region_wait_now[solder.StationID] == 2 and
                modbus_client.modbus_read("jcq", solder.StationID, 1)[0] == 2)
        }
        # 正在取出锡膏的点位设置为对应状态
        for _, solder in solders_out_now.items():
            if in_region_rewarm(solder.StationID):
                region_rewarm[solder.StationID] = 22
            elif in_region_wait(solder.StationID):
                region_wait[solder.StationID] = 2

        solders = {k: v for k, v in solders.items() if k not in solders_out_now}

        # 已有锡膏的点位设置0
        for _, solder in solders.items():
            if     in_region_cold(solder.StationID):
                region_cold  [solder.StationID] = 0
            elif in_region_rewarm(solder.StationID):
                region_rewarm[solder.StationID] = 0
            elif   in_region_wait(solder.StationID):
                region_wait  [solder.StationID] = 0

        # 处理：回温区——冷藏区，待取区——冷藏区
        current_time = datetime.now()
        solders_abnormal = {}
        for solder_code, solder in solders.items():
            is_abnormal = False

            # 回温区超时
            if (in_region_rewarm(solder.StationID) and
                current_time >= solder.ReadyOutDateTime + timedelta(minutes=solder_models[solder.Model].RewarmMaxTime) and
                solder.BackLCTimes < solder_models[solder.Model].OutChaoshiAutoLcTimes):

                region_rewarm[solder.StationID] = 5
                logger.info(f"回温区 {solder.StationID} 锡膏码 {solder.SolderCode} 异常，回冷藏区")
                is_abnormal = True

            # 回温区超时 and 回冷藏区次数超出限制
            elif (in_region_rewarm(solder.StationID) and
                  current_time >= solder.ReadyOutDateTime + timedelta(minutes=solder_models[solder.Model].RewarmMaxTime) and
                  solder.BackLCTimes >= solder_models[solder.Model].OutChaoshiAutoLcTimes):

                region_rewarm[solder.StationID] = 6
                logger.info(f"回温区 {solder.StationID} 锡膏码 {solder.SolderCode} 异常，无法回冷藏区")
                is_abnormal = True

            # 待取区超时
            elif (in_region_wait(solder.StationID) and
                 current_time >= solder.ReadyOutDateTime + timedelta(
                     hours=solder_models[solder.Model].OutChaoshiAutoLc,
                     seconds=solder_models[solder.Model].StirTime) and
                 solder.BackLCTimes < solder_models[solder.Model].OutChaoshiAutoLcTimes and
                 solder_models[solder.Model].IfBackAfterJiaoban):

                region_wait[solder.StationID] = 5
                logger.info(f"待取区 {solder.StationID} 锡膏码 {solder.SolderCode} 异常，回冷藏区")
                is_abnormal = True

            # 待取区超时 and (回冷藏区次数超出限制 or 搅拌后不可回冷藏)
            elif (in_region_wait(solder.StationID) and
                  current_time >= solder.ReadyOutDateTime + timedelta(
                      hours=solder_models[solder.Model].OutChaoshiAutoLc,
                      seconds=solder_models[solder.Model].StirTime) and
                 (solder.BackLCTimes >= solder_models[solder.Model].OutChaoshiAutoLcTimes or
                  not solder_models[solder.Model].IfBackAfterJiaoban)):

                region_wait[solder.StationID] = 6
                logger.info(f"待取区 {solder.StationID} 锡膏码 {solder.SolderCode} 异常，无法回冷藏区")
                is_abnormal = True

            if is_abnormal:
                solders_abnormal[solder_code] = solder


        # 处理预约锡膏
        solders = {k: v for k, v in solders.items() if k not in solders_abnormal}
        solders_ordered = {k: v for k, v in solders.items() if v.OrderUser}
        num_solders_ordered_move_to_rewarm = 0
        num_solders_ordered_move_to_wait = 0

        for solder_code, solder in solders_ordered.items():
            if in_region_cold(solder.StationID) and \
               current_time >= solder.OrderDateTime - timedelta(minutes=solder_models[solder.Model].RewarmTime + 10):

                region_cold[solder.StationID] = 2
                num_solders_ordered_move_to_rewarm += 1
                logger.info(f"冷藏区 {solder.StationID} 预约锡膏码 {solder.SolderCode} 移动到回温区")

            elif in_region_rewarm(solder.StationID) and \
                 current_time >= solder.OrderDateTime - timedelta(minutes=10) and \
                 solder_models[solder.Model].JiaobanRule == "自动搅拌": # 仅自动搅拌规则的锡膏需要移动到待取区

                region_rewarm[solder.StationID] = 2
                num_solders_ordered_move_to_wait += 1
                logger.info(f"回温区 {solder.StationID} 预约锡膏码{solder.SolderCode} 移动到待取区")

        logger.info(f"需要移动到回温区的预约锡膏数量: {num_solders_ordered_move_to_rewarm}")
        logger.info(f"需要移动到待取区的预约锡膏数量: {num_solders_ordered_move_to_wait}")

        
        # 过滤预约锡膏
        solders = {k: v for k, v in solders.items() if k not in solders_ordered}

        # 处理: 回温区——待取区（仅自动搅拌规则的锡膏）
        # 需要移动到待取区的锡膏数量 = 待取区保持数量 - 已经在待取区的锡膏数量
        # 将移动到待取区的锡膏数量 = min(需要移动到待取区的锡膏数量, 回温区已经到回温时间且未被预约的锡膏数量)
        solder_models_auto_stir = {
            model_name: model
            for model_name, model in solder_models.items()
                if model.JiaobanRule == "自动搅拌"
        }

        solders_in_wait_by_model_auto_stir = {
            model_name: [
                solder for _, solder in solders.items()
                if (model_name == solder.Model and
                    in_region_wait(solder.StationID))
            ]
            for model_name, _ in solder_models_auto_stir.items()
        }

        solders_movable_from_rewarm_by_model_auto_stir = {
            model_name: [
                solder for _, solder in solders.items()
                if (model_name == solder.Model and
                    in_region_rewarm(solder.StationID) and
                    current_time >= solder.RewarmEndDateTime)
            ]
            for model_name, _ in solder_models_auto_stir.items()
        }

        num_solders_put_to_wait_by_model_auto_stir = {
            model_name: min(
                model.ReadyOutNum - len(solders_in_wait_by_model_auto_stir[model_name]),
                len(solders_movable_from_rewarm_by_model_auto_stir[model_name]),
            )
            for model_name, model in solder_models_auto_stir.items()
        }

        for model_name, solders_movable in solders_movable_from_rewarm_by_model_auto_stir.items():
            num_solders_move = num_solders_put_to_wait_by_model_auto_stir[model_name]
            logger.info(f"型号 {model_name} 有 {num_solders_move} 个锡膏将从回温区移动到待取区")
            for solder_movable in solders_movable:
                if num_solders_move == 0:
                    break
                else:
                    region_rewarm[solder_movable.StationID] = 2
                    num_solders_move -= 1

        num_make_region_wait_puttable = sum([v for _, v in num_solders_put_to_wait_by_model_auto_stir.items()])
        logger.info(f"需要移动到待取区的非预约锡膏数量：{num_make_region_wait_puttable}")
        num_make_region_wait_puttable += num_solders_ordered_move_to_wait
        logger.info(f"需要移动到待取区的总锡膏数量：{num_make_region_wait_puttable}")
        for addr, status in region_wait.items():
            if status == -1:
                region_wait[addr] = 1 if num_make_region_wait_puttable > 0 else 0
                num_make_region_wait_puttable -= 1


        # 处理: 冷藏区——回温区
        # 需要移动到回温区的锡膏数量 = 回温区保持数量 - (已经在回温区的锡膏数量 - 将移动到待取区的锡膏数量)
        # 将移动到回温区的锡膏数量 = min(需要移动到回温区的锡膏数量, 冷藏区已经到冷藏时间且未被预约的锡膏数量)
        solders_in_rewarm_by_model = {
            model_name: [
                solder for _, solder in solders.items()
                if (model_name == solder.Model and
                    in_region_rewarm(solder.StationID) and
                    region_rewarm[solder.StationID] == 0) # 保留停留在回温区的锡膏
            ]
            for model_name, _ in solder_models.items()
        }

        solders_movable_from_cold_by_model = {
            model_name: [
                solder for _, solder in solders.items()
                if (model_name == solder.Model and
                    in_region_cold(solder.StationID) and
                    current_time >= solder.StorageDateTime + timedelta(hours=solder_models[model_name].MinLcTime))
            ]
            for model_name, _ in solder_models.items()
        }

        num_solders_put_to_rewarm_by_model = {
            model_name: min(
                model.RewarmNum - len(solders_in_rewarm_by_model[model_name]),
                len(solders_movable_from_cold_by_model[model_name]),
            )
            for model_name, model in solder_models.items()
        }

        for model_name, solders_movable in solders_movable_from_cold_by_model.items():
            num_solders_move = num_solders_put_to_rewarm_by_model[model_name]
            logger.info(f"型号 {model_name} 有 {num_solders_move} 个锡膏将从冷藏区移动到回温区")
            for solder_movable in solders_movable:
                if num_solders_move == 0:
                    break
                else:
                    region_cold[solder_movable.StationID] = 2
                    num_solders_move -= 1

        num_make_region_rewarm_puttable = sum([v for _, v in num_solders_put_to_rewarm_by_model.items()])
        logger.info(f"需要移动到回温区的非预约锡膏数量: {num_make_region_rewarm_puttable}")
        num_make_region_rewarm_puttable += num_solders_ordered_move_to_rewarm
        logger.info(f"需要移动到回温区的总锡膏数量: {num_make_region_rewarm_puttable}")
        for addr, status in region_rewarm.items():
            if status == -1:
                region_rewarm[addr] = 1 if num_make_region_rewarm_puttable > 0 else 0
                num_make_region_rewarm_puttable -= 1


        logger.info(f"冷藏区下个状态: {region_cold}")
        region_cold   = [v for _, v in region_cold.items()]
        logger.info(f"冷藏区下个状态: {collections.Counter(region_cold)}")

        logger.info(f"回温区下个状态: {region_rewarm}")
        region_rewarm = [v for _, v in region_rewarm.items()]
        logger.info(f"回温区下个状态: {collections.Counter(region_rewarm)}")

        logger.info(f"待取区下个状态: {region_wait}")
        region_wait   = [v for _, v in region_wait.items()]
        logger.info(f"待取区下个状态: {collections.Counter(region_wait)}")

        modbus_client.write_region(ADDR_REGION_COLD_START,   region_cold)
        modbus_client.write_region(ADDR_REGION_REWARM_START, region_rewarm)
        modbus_client.write_region(ADDR_REGION_WAIT_START,   region_wait)

        logger.info("点位状态更新完毕")
