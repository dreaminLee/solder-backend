from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify

from flask_jwt_extended import jwt_required, get_jwt_identity

from modbus.client import modbus_client
from modbus.modbus_addresses import ADDR_REGION_COLD_START, ADDR_REGION_COLD_END
from modbus.modbus_addresses import ADDR_REGION_REWARM_START, ADDR_REGION_REWARM_END
from modbus.modbus_addresses import ADDR_REGION_WAIT_START, ADDR_REGION_WAIT_END
from modbus.modbus_addresses import in_region_rewarm, in_region_wait
from tasks.scheduler import file_path
from util.MES_request import send_take_log
from util.db_connection import db_instance
from util.Response import Response
from models import Solder, SolderModel, Station, SolderFlowRecord, User
from util.parse import parse_barcode
from sqlalchemy import desc, or_

solder_bp = Blueprint('solder', __name__)

def extract_info(input_str):
    try:
        # 提取日期：位置 4-9（索引 3 到 9，不包括 9）
        date = input_str[3:9]

        # 提取唯一标识：位置 10-14（索引 9 到 14，不包括 14）
        unique_id = input_str[9:14]

        # 提取型号：在第一个 '&' 和第二个 '&' 之间
        parts = input_str.split('&')
        model = parts[1] if len(parts) > 1 else None

        return date,unique_id,model
    except Exception as e:
        print(f"Error extracting info: {e}")
        return None

@solder_bp.route("/get_solder_models_type", methods=['GET'])
def get_solder_models_type():
    session = db_instance.get_session()
    try:
        # 查询 solder 表中不同的型号
        models = session.query(Solder.Model).distinct().all()

        if not models:
            return Response.FAIL("没有找到任何型号")

        # 提取型号列表
        model_list = [model[0] for model in models if model[0] is not None]

        return Response.SUCCESS(model_list)
    except Exception as e:
        return Response.FAIL(f"查询失败: {str(e)}")
    finally:
        session.close()


@solder_bp.route("/get_solders", methods=['POST'])
def get_solders():
    session = db_instance.get_session()
    data = request.get_json()
    try:
        model = data.get('model')
        StaArea = data.get('StaArea')
        # 根据条件查询
        if model != "" and StaArea != "":
            # 两者都不为空，进行连表查询并过滤 model
            solders = session.query(Solder, Station.StaArea).filter(Station.StaArea == StaArea, Solder.Model == model).join(Station, Solder.StationID == Station.StationID).all()
        elif model != "":
            # 仅 model 不为空，根据 model 查询
            solders = session.query(Solder, Station.StaArea).filter(Solder.Model == model).join(Station, Solder.StationID == Station.StationID).all()
        elif StaArea != "":
            # 仅 StaArea 不为空，进行连表查询
            solders = session.query(Solder, Station.StaArea).filter(Station.StaArea == StaArea).join(Station, Solder.StationID == Station.StationID).all()
        else:
            # 两者都为空，查询全部
            solders = session.query(Solder, Station.StaArea).join(Station, Solder.StationID == Station.StationID).all()
        if not solders:
            return Response.SUCCESS()

        # 构建返回结果
        solder_list = []
        for solder, area in solders:
            solder_data = {
                "SolderCode": solder.SolderCode,
                "Model": solder.Model,
                "StationID": solder.StationID,
                "ExpireDate": solder.ExpireDate,
                "StorageUser": solder.StorageUser,
                "StorageDateTime": solder.StorageDateTime,
                "OrderUser": solder.OrderUser,
                "OrderDateTime": solder.OrderDateTime,
                "RewarmStartUser": solder.RewarmStartUser,
                "RewarmStartDateTime": solder.RewarmStartDateTime,
                "RewarmEndDateTime": solder.RewarmEndDateTime,
                "StirStartDateTime": solder.StirStartDateTime,
                "ReadyOutDateTime": solder.ReadyOutDateTime,
                "OutUser": solder.OutUser,
                "OutDateTime": solder.OutDateTime,
                "Decoded": solder.Decoded,
                "DecodedUser": solder.DecodedUser,
                "DecodedDateTime": solder.DecodedDateTime,
                "InTimes": solder.InTimes,
                "CurrentFlow": solder.CurrentFlow,
                "Code": solder.Code,
                "WorkNum": solder.WorkNum,
                "MesError": solder.MesError,
                "AgainColdDateTime": solder.AgainColdDateTime,
                "StaArea": area
            }
            solder_list.append(solder_data)

        return Response.SUCCESS(solder_list)
    except Exception as e:
        return Response.FAIL(f"查询失败: {str(e)}")
    finally:
        session.close()

@solder_bp.route("/get_code", methods=['GET'])
def get_code():
    with open(file_path, "r") as file:
        code = file.read()
    if code:
        return Response.SUCCESS(code)
    else:
        return Response.FAIL()

@solder_bp.route("/delete_solder", methods=['POST'])
def delete_solder():
    data = request.get_json()
    solder_code = data.get('solder_code')
    if not solder_code:
        return Response.FAIL("锡膏码不能为空")

    session = db_instance.get_session()
    try:
        solder = session.query(Solder).filter_by(SolderCode=solder_code).first()

        if not solder:
            return Response.FAIL("锡膏记录不存在")

        session.delete(solder)
        session.commit()

        return Response.SUCCESS("锡膏记录删除成功")
    except Exception as e:
        session.rollback()
        return Response.FAIL(f"删除失败: {str(e)}")
    finally:
        session.close()


@solder_bp.route("/add_solder", methods=['POST'])
def add_solder():
    data = request.get_json()

    solder_code = data.get('SolderCode')
    model = data.get('Model')
    station_id = data.get('StationID')
    expire_date = data.get('ExpireDate')
    storage_user = data.get('StorageUser')
    storage_date_time = data.get('StorageDateTime')
    order_user = data.get('OrderUser')
    order_date_time = data.get('OrderDateTime')
    rewarm_start_user = data.get('RewarmStartUser')
    rewarm_start_date_time = data.get('RewarmStartDateTime')
    rewarm_end_date_time = data.get('RewarmEndDateTime')
    stir_start_date_time = data.get('StirStartDateTime')
    ready_out_date_time = data.get('ReadyOutDateTime')
    out_user = data.get('OutUser')
    out_date_time = data.get('OutDateTime')
    decoded = data.get('Decoded', False)  # 默认为 False
    decoded_user = data.get('DecodedUser')
    decoded_date_time = data.get('DecodedDateTime')
    in_times = data.get('InTimes', 0)  # 默认为 0
    current_flow = data.get('CurrentFlow', 0)  # 默认为 0
    code = data.get('Code')
    work_num = data.get('WorkNum')
    mes_error = data.get('MesError')
    again_cold_date_time = data.get('AgainColdDateTime')

    # 校验必填字段
    if not solder_code:
        return Response.FAIL("锡膏码不能为空")

    session = db_instance.get_session()
    try:
        solder = Solder(
            SolderCode=solder_code,
            Model=model,
            StationID=station_id,
            ExpireDate=expire_date,
            StorageUser=storage_user,
            StorageDateTime=storage_date_time,
            OrderUser=order_user,
            OrderDateTime=order_date_time,
            RewarmStartUser=rewarm_start_user,
            RewarmStartDateTime=rewarm_start_date_time,
            RewarmEndDateTime=rewarm_end_date_time,
            StirStartDateTime=stir_start_date_time,
            ReadyOutDateTime=ready_out_date_time,
            OutUser=out_user,
            OutDateTime=out_date_time,
            Decoded=decoded,
            DecodedUser=decoded_user,
            DecodedDateTime=decoded_date_time,
            InTimes=in_times,
            CurrentFlow=current_flow,
            Code=code,
            WorkNum=work_num,
            MesError=mes_error,
            AgainColdDateTime=again_cold_date_time
        )

        session.add(solder)
        session.commit()

        return Response.SUCCESS("锡膏记录添加成功")
    except Exception as e:
        session.rollback()
        return Response.FAIL(f"添加失败: {str(e)}")
    finally:
        session.close()


# 获取型号列表
@solder_bp.route('/get_models', methods=['GET'])
def get_models():
    # 获取所有型号信息
    session = db_instance.get_session()
    models = session.query(SolderModel).all()
    session.close()
    # 如果没有找到记录
    if not models:
        return Response.FAIL("没有找到锡膏型号记录")

    # 返回型号列表
    model_list = [model.to_dict() for model in models]
    return Response.SUCCESS(model_list)


@solder_bp.route('/add_model', methods=['POST'])
def add_model():
    data = request.get_json()
    barcode = data.get("barcode")
    # 获取请求数据
    model = data.get('model')
    model_sys_name = data.get('model_sys_name')
    min_cold_num = data.get('min_cold_num')
    rewarm_num = data.get('rewarm_num')
    ready_out_num = data.get('ready_out_num')
    stir_time = data.get('stir_time')
    stir_speed = data.get('stir_speed')
    rewarm_time = data.get('rewarm_time')
    rewarm_max_time = data.get('rewarm_max_time')
    ready_out_timeout = data.get('ready_out_timeout')
    shelf_life = data.get('shelf_life')
    z_offset = data.get('z_offset')
    if_jiaoban = data.get('if_jiaoban')
    jiaoban_rule = data.get('jiaoban_rule')
    min_lc_time = data.get('min_lc_time')
    out_chaoshi_auto_lc = data.get('out_chaoshi_auto_lc')
    out_chaoshi_auto_lc_times = data.get('out_chaoshi_auto_lc_times')
    if_back_after_jiaoban = data.get('if_back_after_jiaoban')
    twice_chaoshi_jinzhi_in_binggui = data.get('twice_chaoshi_jinzhi_in_binggui')
    twice_in_ku = data.get('twice_in_ku')
    # 新增字段获取逻辑
    separator = data.get('separator')
    model_start = data.get('model_start')
    model_separator_start = data.get('model_separator_start')
    model_length = data.get('model_length')
    production_date_start = data.get('production_date_start')
    production_date_separator_start = data.get('production_date_separator_start')
    production_date_length = data.get('production_date_length')
    shelf_life_start = data.get('shelf_life_start')
    shelf_life_separator_start = data.get('shelf_life_separator_start')
    shelf_life_length = data.get('shelf_life_length')
    expiration_date_start = data.get('expiration_date_start')
    expiration_date_separator_start = data.get('expiration_date_separator_start')
    expiration_date_length = data.get('expiration_date_length')
    modify_datetime = datetime.now()

    # 验证必要参数
    if not all([model, model_sys_name]):
        return Response.FAIL("缺少必要的参数")

    session = db_instance.get_session()

    try:
        # 查找是否已存在该型号
        solder_model = session.query(SolderModel).filter_by(Model=model).first()

        if solder_model:
            return Response.FAIL("型号已存在")

        # 添加新型号
        solder_model = SolderModel(
            Model=model,
            ModelSysName=model_sys_name,
            MinColdNum=min_cold_num,
            RewarmNum=rewarm_num,
            ReadyOutNum=ready_out_num,
            StirTime=stir_time,
            StirSpeed=stir_speed,
            RewarmTime=rewarm_time,
            RewarmMaxTime=rewarm_max_time,
            ReadyOutTimeOut=ready_out_timeout,
            ShelfLife=shelf_life,
            ZOffSet=z_offset,
            IfJiaoban=if_jiaoban,
            JiaobanRule=jiaoban_rule,
            MinLcTime=min_lc_time,
            OutChaoshiAutoLc=out_chaoshi_auto_lc,
            OutChaoshiAutoLcTimes=out_chaoshi_auto_lc_times,
            IfBackAfterJiaoban=if_back_after_jiaoban,
            TwiceChaoshiJinzhiInBinggui=twice_chaoshi_jinzhi_in_binggui,
            TwiceInKu=twice_in_ku,
            ModifyDateTime=modify_datetime,
            # 新增字段添加到实例中
            Separator=separator,
            ModelStart =model_start,
            ModelSeparatorStart =model_separator_start,
            ModelLength =model_length,
            ProductionDateStart=production_date_start,
            ProductionDateSeparatorStart=production_date_separator_start,
            ProductionDateLength=production_date_length,
            ShelfLifeStart=shelf_life_start,
            ShelfLifeSeparatorStart=shelf_life_separator_start,
            ShelfLifeLength=shelf_life_length,
            ExpirationDateStart=expiration_date_start,
            ExpirationDateSeparatorStart=expiration_date_separator_start,
            ExpirationDateLength=expiration_date_length,
        )

        session.add(solder_model)
        session.commit()
        return Response.SUCCESS("型号添加成功")

    except Exception as e:
        session.rollback()
        return Response.FAIL(f"添加型号失败: {str(e)}")

    finally:
        session.close()



@solder_bp.route('/edit_model', methods=['POST'])
def edit_model():
    data = request.get_json()

    # 获取请求数据
    model = data.get('model')
    model_sys_name = data.get('model_sys_name')
    min_cold_num = data.get('min_cold_num')
    rewarm_num = data.get('rewarm_num')
    ready_out_num = data.get('ready_out_num')
    stir_time = data.get('stir_time')
    stir_speed = data.get('stir_speed')
    rewarm_time = data.get('rewarm_time')
    rewarm_max_time = data.get('rewarm_max_time')
    ready_out_timeout = data.get('ready_out_timeout')
    shelf_life = data.get('shelf_life')
    z_offset = data.get('z_offset')
    if_jiaoban = data.get('if_jiaoban')
    jiaoban_rule = data.get('jiaoban_rule')
    min_lc_time = data.get('min_lc_time')
    out_chaoshi_auto_lc = data.get('out_chaoshi_auto_lc')
    out_chaoshi_auto_lc_times = data.get('out_chaoshi_auto_lc_times')
    if_back_after_jiaoban = data.get('if_back_after_jiaoban')
    twice_chaoshi_jinzhi_in_binggui = data.get('twice_chaoshi_jinzhi_in_binggui')
    twice_in_ku = data.get('twice_in_ku')
    modify_datetime = datetime.now()
    # 新增字段获取逻辑
    separator = data.get('separator')
    model_start = data.get('model_start')
    model_separator_start = data.get('model_separator_start')
    model_length = data.get('model_length')
    production_date_start = data.get('production_date_start')
    production_date_separator_start = data.get('production_date_separator_start')
    production_date_length = data.get('production_date_length')
    shelf_life_start = data.get('shelf_life_start')
    shelf_life_separator_start = data.get('shelf_life_separator_start')
    shelf_life_length = data.get('shelf_life_length')
    expiration_date_start = data.get('expiration_date_start')
    expiration_date_separator_start = data.get('expiration_date_separator_start')
    expiration_date_length = data.get('expiration_date_length')

    # 验证必要参数
    if not all([model, model_sys_name]):
        return Response.FAIL("缺少必要的参数")

    session = db_instance.get_session()

    try:
        # 查找型号
        solder_model = session.query(SolderModel).filter_by(Model=model).first()

        if not solder_model:
            return Response.FAIL("型号不存在")

        # 更新型号信息
        solder_model.ModelSysName = model_sys_name
        solder_model.MinColdNum = min_cold_num
        solder_model.RewarmNum = rewarm_num
        solder_model.ReadyOutNum = ready_out_num
        solder_model.StirTime = stir_time
        solder_model.StirSpeed = stir_speed
        solder_model.RewarmTime = rewarm_time
        solder_model.RewarmMaxTime = rewarm_max_time
        solder_model.ReadyOutTimeOut = ready_out_timeout
        solder_model.ShelfLife = shelf_life
        solder_model.ZOffSet = z_offset
        solder_model.IfJiaoban = if_jiaoban
        solder_model.JiaobanRule = jiaoban_rule
        solder_model.MinLcTime = min_lc_time
        solder_model.OutChaoshiAutoLc = out_chaoshi_auto_lc
        solder_model.OutChaoshiAutoLcTimes = out_chaoshi_auto_lc_times
        solder_model.IfBackAfterJiaoban = if_back_after_jiaoban
        solder_model.TwiceChaoshiJinzhiInBinggui = twice_chaoshi_jinzhi_in_binggui
        solder_model.TwiceInKu = twice_in_ku
        solder_model.ModifyDateTime = modify_datetime
        # 新增字段添加到实例中
        solder_model.Separator = separator,
        if model_start:
            solder_model.ModelStart = int(model_start),
        if model_separator_start:
            solder_model.ModelSeparatorStart = int(model_separator_start),
        solder_model.ModelLength = model_length,
        solder_model.ProductionDateStart = production_date_start,
        solder_model.ProductionDateSeparatorStart = production_date_separator_start,
        solder_model.ProductionDateLength = production_date_length,
        solder_model.ShelfLifeStart = shelf_life_start,
        solder_model.ShelfLifeSeparatorStart = shelf_life_separator_start,
        solder_model.ShelfLifeLength = shelf_life_length,
        solder_model.ExpirationDateStart = expiration_date_start,
        solder_model.ExpirationDateSeparatorStart = expiration_date_separator_start,
        solder_model.ExpirationDateLength = expiration_date_length,

        session.commit()
        modbus_client.write_float(stir_time, 1526)
        modbus_client.write_float(stir_speed, 1522)
        modbus_client.write_float(z_offset, 1536)
        return Response.SUCCESS("型号更新成功")

    except Exception as e:
        session.rollback()
        return Response.FAIL(f"更新型号失败: {str(e)}")

    finally:
        session.close()



@solder_bp.route('/delete_model', methods=['POST'])
def delete_model():
    data = request.get_json()
    model = data.get('model')
    session = db_instance.get_session()

    if not model:
        return Response.FAIL("缺少型号参数")

    try:
        solder_model = session.query(SolderModel).filter_by(Model=model).first()

        if not solder_model:
            return Response.FAIL("型号不存在")

        session.delete(solder_model)
        session.commit()
        return Response.SUCCESS("型号删除成功")

    except Exception as e:
        session.rollback()
        return Response.FAIL(f"删除型号失败: {str(e)}")

    finally:
        session.close()


"""
    未被预约的锡膏: 在冷藏区中 and OrderUser == None and 冷藏时间超过最小冷藏时间
"""
@solder_bp.route('/unordered_solder', methods=['GET'])
def unordered_solder():
    with db_instance.get_session() as db_session:
        solders_unordered = db_session.query(Solder, SolderModel.MinLcTime
                                     ).join(SolderModel, SolderModel.Model == Solder.Model
                                     ).filter(
            Solder.StationID.between(ADDR_REGION_COLD_START, ADDR_REGION_COLD_END),
            Solder.OrderUser == None,
        ).all()
        return Response.SUCCESS([
            solder.to_dict()
            for solder, min_lc_time in solders_unordered
                if datetime.now() >= solder.StorageDateTime + timedelta(hours=min_lc_time)
        ])


"""
    已被预约的锡膏: OrderUser != None
"""
@solder_bp.route('/ordered_solder', methods=['GET'])
def ordered_solder():
    session = db_instance.get_session()

    try:
        ordered_solder = session.query(Solder).filter(Solder.OrderUser != None).all()
        if not ordered_solder:
            return Response.FAIL("没有")
    except Exception as e:
        session.rollback()
        return Response.FAIL(f"失败: {str(e)}")

    finally:
        session.close()

    # 将修改后的 solder 对象转换为字典
    ordered_solder_dict = [solder.to_dict() for solder in ordered_solder]

    # 返回包含字典的响应
    return Response.SUCCESS(ordered_solder_dict)


"""
    预约锡膏
    可被预约的锡膏: 在冷藏区中 and OrderUser == None and 冷藏时间超过最小冷藏时间
    预约功能无视回温时间限制
"""
@solder_bp.route('/order_solder', methods=['POST'])
@jwt_required()
def order_solder():
    data = request.get_json()
    user_id = get_jwt_identity()  # 获取当前登录用户的ID
    model = data.get('model')
    amount = data.get('amount')  # 获取amount参数
    # 假设 OrderDateTime 字符串的格式是 'YYYY-MM-DDTHH:MM:SS'
    order_datetime_str = data.get('OrderDateTime')

    if not user_id or not model or not amount or not order_datetime_str:
        return Response.FAIL("缺少用户ID、型号、数量或日期时间参数")

    amount = int(amount)

    try:
        # 使用 strptime 将字符串转换为 datetime 对象
        order_datetime = datetime.strptime(order_datetime_str, '%Y-%m-%d %H:%M:%S')

        # 检查日期是否早于当前时间
        if order_datetime < datetime.now():
            return Response.FAIL("日期时间早于当前时间，无法预约")

        # 然后使用 strftime 格式化为所需格式
        order_datetime_str = order_datetime.strftime('%Y-%m-%d %H:%M:%S')
    except ValueError as e:
        # 如果字符串格式不匹配，捕获异常
        print(f"Invalid date format: {e}")
        return Response.FAIL("日期时间格式无效")

    with db_instance.get_session() as session:

        # 查询 User 表，获取对应的 username
        user = session.query(User).filter(User.UserID == user_id).first()
        if not user:
            return Response.FAIL("用户不存在")

        # 查询 OrderUser 为 None 的记录，限制返回最多 amount 条记录
        solders_unordered = session.query(Solder, SolderModel.MinLcTime
                                  ).join(SolderModel, SolderModel.Model == Solder.Model
                                  ).filter(
            Solder.StationID.between(ADDR_REGION_COLD_START, ADDR_REGION_COLD_END),
            Solder.OrderUser == None,
            Solder.Model == model,
        ).order_by(desc(Solder.BackLCTimes)).all()

        solders_unordered = [
            solder for solder, min_lc_time in solders_unordered
                if datetime.now() >= solder.StorageDateTime + timedelta(hours=min_lc_time)
        ]

        if len(solders_unordered) < amount:
            return Response.FAIL(f"不足 {amount} 个，无法预约")

        # 将时间字符串转换为 datetime 对象
        order_datetime = datetime.strptime(order_datetime_str, "%Y-%m-%d %H:%M:%S")

        username = user.UserName

        # 更新符合条件的 Solder 的 OrderDateTime 和 OrderUser 字段
        for solder in solders_unordered[:amount]:
            solder.OrderDateTime = order_datetime
            solder.OrderUser = username

        session.commit()
        return Response.SUCCESS("型号更新成功")


"""
    待取出的锡膏列表
    - 自动搅拌规则, 待取区中状态为0的锡膏
    - 出库搅拌规则, 回温区中到达回温时间状态为0的锡膏或被预约的锡膏
"""
@solder_bp.route('/daiqu_solder', methods=['GET'])
def daiqu_solder():
    with db_instance.get_session() as db_session:
        solders_in_rewarm_wait_model = db_session.query(Solder, SolderModel
            ).join(SolderModel, SolderModel.Model == Solder.Model
            ).filter(
            or_(
                Solder.StationID.between(ADDR_REGION_REWARM_START, ADDR_REGION_REWARM_END),
                Solder.StationID.between(ADDR_REGION_WAIT_START, ADDR_REGION_WAIT_END),
            )
        ).all()
        solders_outable = [
            solder for solder, solder_model in solders_in_rewarm_wait_model
            if (solder_model.JiaobanRule == "自动搅拌" and
                in_region_wait(solder.StationID) and
                modbus_client.modbus_read("jcq", solder.StationID, 1)[0] == 0)
                or
               (solder_model.JiaobanRule == "出库搅拌" and
                in_region_rewarm(solder.StationID) and
                modbus_client.modbus_read("jcq", solder.StationID, 1)[0] == 0 and
                (datetime.now() >= solder.RewarmEndDateTime or solder.OrderUser != None))
        ]
        return Response.SUCCESS([
            {
                "SolderCode": solder.SolderCode,
                "Model": solder.Model,
                "StorageUser": solder.StorageUser,
                "StorageDateTime": solder.StorageDateTime.strftime("%Y-%m-%d %H:%M:%S")
                                if solder.StorageDateTime else None,
                'Station': solder.StationID
            }
            for solder in solders_outable
        ])


"""
    可取出的锡膏列表：待取区中状态为2的锡膏 / 回温区中状态为22的”出库搅拌“的锡膏
"""
@solder_bp.route('/accessible_solder', methods=['GET'])
def accessible_solder():
    with db_instance.get_session() as db_session:
        solders_in_rewarm_wait = db_session.query(Solder).filter(
            or_(
                Solder.StationID.between(ADDR_REGION_REWARM_START, ADDR_REGION_REWARM_END),
                Solder.StationID.between(ADDR_REGION_WAIT_START, ADDR_REGION_WAIT_END),
            )
        ).all()
        return Response.SUCCESS([
            res 
            for res in ({
                    "SolderCode": solder.SolderCode,
                    "Model": solder.Model,
                    "StorageUser": solder.StorageUser,
                    "StorageDateTime": solder.StorageDateTime.strftime("%Y-%m-%d %H:%M:%S") if solder.StorageDateTime else None,
                    "Station": solder.StationID,
                    "Station_status": modbus_client.modbus_read("jcq", solder.StationID, 1)[0],
                }
                for solder in solders_in_rewarm_wait)
            if (in_region_wait(res["Station"]) and
                res["Station_status"] == 2)
                or
               (in_region_rewarm(res["Station"]) and
                res["Station_status"] == 22)
        ])


"""
    锡膏出库接口
        - 自动搅拌规则, 待取区中的锡膏
        - 出库搅拌规则, 回温区中到达回温时间的锡膏或被预约的锡膏
"""
@solder_bp.route('/out_solder', methods=['POST'])
@jwt_required()
def out_solder():
    data = request.get_json()
    user_id = get_jwt_identity()  # 获取当前登录用户的ID
    model_type = data.get('model_type')
    amount = data.get('amount')  # 新增参数，查询需要处理的数量
    solder_code = data.get("solder_code")

    if not amount or amount <= 0:
        return Response.FAIL("请提供有效的数量参数")
    
    if not model_type:
        return Response.FAIL("请提供锡膏型号")

    with db_instance.get_session() as db_session:

        user = db_session.query(User).filter(User.UserID == user_id).first()
        if not user:
            return jsonify(Response.FAIL("用户不存在"))

        user_name = user.UserName

        solders_model = db_session.query(Solder, SolderModel
            ).join(SolderModel, SolderModel.Model == Solder.Model
            ).filter(Solder.Model == model_type).all()

        solders_outable = [
            (solder, solder_model.JiaobanRule)
            for solder, solder_model in solders_model
            if (solder_model.JiaobanRule == "自动搅拌" and
                in_region_wait(solder.StationID) and
                modbus_client.modbus_read("jcq", solder.StationID, 1)[0] == 0)
                or
               (solder_model.JiaobanRule == "出库搅拌" and
                in_region_rewarm(solder.StationID) and
                modbus_client.modbus_read("jcq", solder.StationID, 1)[0] == 0 and
                datetime.now() >= solder.RewarmEndDateTime or solder.OrderUser != None)
        ]

        if len(solders_outable) < amount:
            return Response.FAIL(f"未找到足够的锡膏记录，当前只有 {len(solders_outable)} 条")
        
        for solder, rule in solders_outable:
            solder_flow_record = SolderFlowRecord(
                UserID=user_id,
                UserName=user_name,
                SolderCode=solder.SolderCode,
                Type="请求出柜",  # 假设类型为 "出柜"，可以根据实际需求调整
                DateTime=datetime.now()
            )

            db_session.add(solder_flow_record)
            modbus_client.modbus_write("jcq", 2 if rule == "自动搅拌" else 22, solder.StationID, 1)
        
        db_session.commit()
        return Response.SUCCESS({"message": f"{amount} 条锡膏记录已出柜，操作成功"})


@solder_bp.route('/lengcang_solder', methods=['GET'])
def lengcang_solder():
    # 获取数据库会话
    session = db_instance.get_session()

    # 使用 JOIN 查询 StaArea 为 '待取区' 的 solder 数据
    results = session.query(Solder).join(Station, Solder.StationID == Station.StationID).filter(
        Station.StaArea == "冷藏区")
    session.close()
    # 如果没有找到结果
    if not results:
        return jsonify(Response.FAIL("没有符合条件的锡膏记录"))

    # 将查询结果转化为字典
    records = [
        {
            "SolderCode": record.SolderCode,
            "Model": record.Model,
            "Station": record.StationID,
            "StorageUser": record.StorageUser,
            "StorageDateTime": record.StorageDateTime.strftime("%Y-%m-%d %H:%M:%S") if record.StorageDateTime else None
        }
        for record in results
    ]

    # 返回查询结果
    return jsonify(Response.SUCCESS(records))

@solder_bp.route('/get_model_by_barcode', methods=['POST'])
def get_model_by_barcode():
    data = request.get_json()
    barcode = data.get("barcode")
    result = parse_barcode(barcode)

    if not barcode:
        return Response.FAIL("条码不能为空")

    return Response.SUCCESS(result)