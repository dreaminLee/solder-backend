from datetime import datetime

from flask import Blueprint, request, jsonify

from flask_jwt_extended import jwt_required, get_jwt_identity

from modbus.client import modbus_client
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

    # if barcode:
    #     result = parse_barcode(barcode)
    #     model = result['型号']
    #     model_sys_name = data.get('model_sys_name')
    #     min_cold_num = data.get('min_cold_num')
    #     rewarm_num = data.get('rewarm_num')
    #     ready_out_num = data.get('ready_out_num')
    #     stir_time = data.get('stir_time')
    #     stir_speed = data.get('stir_speed')
    #     rewarm_time = data.get('rewarm_time')
    #     rewarm_max_time = data.get('rewarm_max_time')
    #     ready_out_timeout = data.get('ready_out_timeout')
    #     expire_date = result['到期日期']
    #     product_date = result['生产日期']
    #     z_offset = data.get('z_offset')
    #     if_jiaoban = data.get('if_jiaoban')
    #     jiaoban_rule = data.get('jiaoban_rule')
    #     min_lc_time = data.get('min_lc_time')
    #     out_chaoshi_auto_lc = data.get('out_chaoshi_auto_lc')
    #     out_chaoshi_auto_lc_times = data.get('out_chaoshi_auto_lc_times')
    #     if_back_after_jiaoban = data.get('if_back_after_jiaoban')
    #     twice_chaoshi_jinzhi_in_binggui = data.get('twice_chaoshi_jinzhi_in_binggui')
    #     twice_in_ku = data.get('twice_in_ku')
    #     modify_datetime = datetime.now()
    # else:
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
            ModifyDateTime=modify_datetime
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

@solder_bp.route('/unordered_solder', methods=['GET'])
def unordered_solder():
    # 获取 SQLAlchemy 会话
    session = db_instance.get_session()
    try:
        # 查询 OrderUser 为 None 且 StationID 在 201 到 539 之间的记录
        solders = session.query(Solder).filter(
            Solder.OrderUser == None,
            Solder.StationID.between(201, 539)
        ).all()

        # 进一步筛选 modbus_read 值等于 2 的记录
        unordered_solder = []
        for solder in solders:
            result=modbus_client.modbus_read("jcq",solder.StationID,1)[0]
            if result==2:
                unordered_solder.append(solder)

        if not unordered_solder:
            return Response.SUCCESS("没有记录")

    except Exception as e:
        session.rollback()
        return Response.FAIL(f"失败: {str(e)}")

    finally:
        session.close()
    # 假设 unordered_solder 是一个包含多个 SolderModel 实例的列表
    unordered_solder_dict = [solder.to_dict() for solder in unordered_solder]
    # 返回包含字典的响应
    return Response.SUCCESS(unordered_solder_dict)


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

    if order_datetime_str:
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

    session = db_instance.get_session()
    try:
        # 查询 OrderUser 为 None 的记录，限制返回最多 amount 条记录
        solders = session.query(Solder).filter(
            Solder.OrderUser == None,
            Solder.StationID.between(201, 539),
            Solder.Model == model
        ).order_by(desc(Solder.BackLCTimes)).limit(amount).all()

        # 进一步筛选 modbus_read 值等于 2 的记录
        unordered_solder = []
        for solder in solders:
            result = modbus_client.modbus_read("jcq", solder.StationID, 1)[0]
            if result == 2:
                unordered_solder.append(solder)

        if len(unordered_solder) < amount:
            return Response.FAIL(f"不足 {amount} 个，无法预约")

        # 将时间字符串转换为 datetime 对象
        order_datetime = datetime.strptime(order_datetime_str, "%Y-%m-%d %H:%M:%S")

        # 查询 User 表，获取对应的 username
        user = session.query(User).filter(User.UserID == user_id).first()
        if not user:
            return Response.FAIL("用户不存在")

        username = user.UserName

        # 更新符合条件的 Solder 的 OrderDateTime 和 OrderUser 字段
        for solder in unordered_solder:
            solder.OrderDateTime = order_datetime
            solder.OrderUser = username

        session.commit()
        return Response.SUCCESS("型号更新成功")

    except Exception as e:
        session.rollback()
        return Response.FAIL(f"更新型号失败: {str(e)}")

"""
    待取出的锡膏列表：待取区中状态为0的锡膏 + 回温区中状态为21的”出库搅拌“的锡膏
"""
@solder_bp.route('/daiqu_solder', methods=['GET'])
def daiqu_solder():
    data = request.get_json()
    # type = data.get('type')
    # 获取数据库会话
    session = db_instance.get_session()

    # 查询 Solder 数据并同时获取 Station.Disabled 字段
    results = session.query(Solder, Station.StationID).join(
        Station, Solder.StationID == Station.StationID
    ).filter(
        (Station.StaArea == "待取区")
    ).all()
    # 将查询结果转化为字典并根据条件过滤
    records_ready_daiqu = [
        {
            "SolderCode": solder.SolderCode,
            "Model": solder.Model,
            "StorageUser": solder.StorageUser,
            "StorageDateTime": solder.StorageDateTime.strftime("%Y-%m-%d %H:%M:%S") if solder.StorageDateTime else None,
            'Station':solder.StationID
        }
        for solder, station_disabled in results
        if modbus_client.modbus_read('jcq',station_disabled,1)[0] == 0
    ]

    # 查询回温区中的 搅拌规则=“出库搅拌” 的 Solder 数据
    rewarm_area_out_stir_solders = session.query(Solder).join(
        SolderModel, Solder.Model == SolderModel.Model
    ).filter(
        (SolderModel.JiaobanRule == "出库搅拌"),
        (Solder.StationID.between(601, 650)),
    ).all()
    # 将查询结果转化为字典并根据条件过滤
    records_rewarm_daiqu = [
        {
            "SolderCode": solder.SolderCode,
            "Model": solder.Model,
            "StorageUser": solder.StorageUser,
            "StorageDateTime": solder.StorageDateTime.strftime("%Y-%m-%d %H:%M:%S") if solder.StorageDateTime else None,
            'Station': solder.StationID
        }
        for solder in rewarm_area_out_stir_solders
        if modbus_client.modbus_read('jcq', solder.StationID , 1)[0] == 21
    ]

    session.close()
    records_daiqu = records_ready_daiqu + records_rewarm_daiqu
    # 返回查询结果
    return jsonify(Response.SUCCESS(records_daiqu))


"""
    可取出的锡膏列表：待取区中状态为2的锡膏 / 回温区中状态为22的”出库搅拌“的锡膏
"""
@solder_bp.route('/accessible_solder', methods=['GET'])
def accessible_solder():
    data = request.get_json()
    # 获取数据库会话
    session = db_instance.get_session()

    # 查询 Solder 数据并同时获取 Station.Disabled 字段
    results = session.query(Solder, Station.StationID).join(
        Station, Solder.StationID == Station.StationID
    ).filter(
        (Station.StaArea == "待取区")
    ).all()
    # 将查询结果转化为字典并根据条件过滤
    records_ready_accessible = [
        {
            "SolderCode": solder.SolderCode,
            "Model": solder.Model,
            "StorageUser": solder.StorageUser,
            "StorageDateTime": solder.StorageDateTime.strftime("%Y-%m-%d %H:%M:%S") if solder.StorageDateTime else None,
            'Station': solder.StationID
        }
        for solder, station_disabled in results
        if modbus_client.modbus_read('jcq', station_disabled, 1)[0] == 2
    ]

    # 查询回温区中的 搅拌规则=“出库搅拌” 的 Solder 数据
    rewarm_area_out_stir_solders = session.query(Solder).join(
        SolderModel, Solder.Model == SolderModel.Model
    ).filter(
        (SolderModel.JiaobanRule == "出库搅拌"),
        (Solder.StationID.between(601, 650)),
    ).all()
    # 将查询结果转化为字典并根据条件过滤
    records_rewarm_accessible = [
        {
            "SolderCode": solder.SolderCode,
            "Model": solder.Model,
            "StorageUser": solder.StorageUser,
            "StorageDateTime": solder.StorageDateTime.strftime("%Y-%m-%d %H:%M:%S") if solder.StorageDateTime else None,
            'Station': solder.StationID
        }
        for solder in rewarm_area_out_stir_solders
        if modbus_client.modbus_read('jcq', solder.StationID, 1)[0] == 22
    ]

    session.close()
    records_accessible = records_ready_accessible + records_rewarm_accessible
    # 返回查询结果
    return jsonify(Response.SUCCESS(records_accessible))

@solder_bp.route('/out_solder', methods=['POST'])
@jwt_required()
def out_solder():
    data = request.get_json()
    user_id = get_jwt_identity()  # 获取当前登录用户的ID
    model_type = data.get('model_type')
    amount = data.get('amount')  # 新增参数，查询需要处理的数量
    solder_code = data.get("solder_code")
    if solder_code and solder_code != "":
        session = db_instance.get_session()
        # 查询 Station 表中 StaArea 为 "待取区" 的一个记录
        station = session.query(Station).filter(Station.StaArea == "待取区").first()
        if station:
            # 如果查到记录，获取该 Station 的 StationID
            new_station_id = station.StationID
            # 更新 Solder 表中 solder_code 等于给定 id 的记录
            solder = session.query(Solder).filter(Solder.SolderCode == solder_code).first()

            if solder:
                # 更新记录的 StationID
                solder.StationID = new_station_id
                session.commit()  # 提交事务
                session.close()
                return Response.SUCCESS("Solder record updated successfully.")
            else:
                return Response.SUCCESS("Solder record not found for the provided id.")
        else:
            return Response.SUCCESS("No Station found with StaArea == '回温区'.")

    if not amount or amount <= 0:
        return Response.FAIL("请提供有效的数量参数")

    # 获取数据库会话
    session = db_instance.get_session()

    # 获取用户信息，根据 user_id 查询 UserName
    user = session.query(User).filter(User.UserID == user_id).first()
    if not user:
        return jsonify(Response.FAIL("用户不存在"))

    user_name = user.UserName  # 获取用户名

    results = session.query(Solder, Station.StationID).join(
        Station, Solder.StationID == Station.StationID
    ).filter(
        or_(Station.StaArea == "待取区", Station.StaArea == "回温区")
    ).all()

    # 将查询结果转化为字典并根据条件过滤
    solder_records = [
        {
            "SolderCode": solder.SolderCode,
            "StationID": station_id
        }
        for solder, station_id in results
        if (modbus_client.modbus_read('jcq', station_id, 1)[0] == 0 or modbus_client.modbus_read("jcq", station_id, 1)[0] == 21) and solder.Model==model_type
    ]

    # 如果没有找到符合条件的锡膏记录
    if len(solder_records) < amount:
        return Response.FAIL(f"未找到足够的锡膏记录，当前只有 {len(solder_records)} 条")

    # 遍历找到的 solder 记录，逐条插入 SolderFlowRecord
    for solder_record in solder_records[:amount]:  # 只处理前 amount 条记录
        solder_flow_record = SolderFlowRecord(
            UserID=user_id,
            UserName=user_name,
            SolderCode=solder_record['SolderCode'],
            Type="请求出柜",  # 假设类型为 "出柜"，可以根据实际需求调整
            DateTime=datetime.now()
        )

        # 插入到 SolderFlowRecord 表
        session.add(solder_flow_record)
        rule = session.query().with_entities(SolderModel.JiaobanRule).filter(SolderModel.Model == model_type).first().JiaobanRule
        modbus_client.modbus_write('jcq',2 if rule == "自动搅拌" else 22,solder_record["StationID"],1)
        # # 更新记录的 StationID 为 "待取区" 的工位ID
        # solder_record.StationID = station.StationID  # 修改 StationID 为待取区的工位ID

    # 提交事务
    session.commit()
    session.close()
    send_take_log(rid=solder_code,user_login=user_id)
    # 返回成功的响应
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

    if not barcode:
        return Response.FAIL("条码不能为空")

    return Response.SUCCESS(barcode)