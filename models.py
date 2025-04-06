from extends import db

# 建表视图
class User(db.Model):
    __tablename__ = 'user'

    # 定义字段与表结构一致
    UserID = db.Column(db.Integer, primary_key=True,  autoincrement=True)  # 对应 UserID
    UserIC = db.Column(db.String(100))  # 对应 UserIC
    UserName = db.Column(db.String(100), nullable=False)  # 对应 UserName
    Password = db.Column(db.String(100), nullable=False)  # 对应 Password
    UserGrade = db.Column(db.Integer, nullable=False)  # 对应 UserGrade
    createAt = db.Column(db.DateTime)  # 对应 ModifyDateTime
    updateAt = db.Column(db.DateTime)  # 对应 ModifyDateTime
    Fingerprint1 = db.Column(db.Text)  # 对应 Fingerprint1
    Fingerprint2 = db.Column(db.Text)  # 对应 Fingerprint2
    Fingerprint3 = db.Column(db.Text)  # 对应 Fingerprint3

    def to_dict(self):
        # 定义一个方法将 ORM 对象转换为字典
        return {
            'user_id': self.UserID,
            'user_ic': self.UserIC,
            'user_name': self.UserName,
            'password': self.Password,
            'user_grade': self.UserGrade,
            'createAt': self.createAt,
            'updateAt': self.updateAt,
            'fingerprint1': self.Fingerprint1,
            'fingerprint2': self.Fingerprint2,
            'fingerprint3': self.Fingerprint3,
        }


class Alarm(db.Model):
    __tablename__ = 'alarm'

    ID =  db.Column(db.Integer, primary_key=True, autoincrement=True)
    AlarmText =  db.Column(db.String(100), nullable=False)
    StartTime =  db.Column(db.DateTime, nullable=True)
    EndTime = db.Column(db.DateTime, nullable=True)
    Kind = db.Column(db.String(10), nullable=True)

    def to_dict(self):
        return {
            'id': self.ID,
            'alarm_text': self.AlarmText,
            'start_time': self.StartTime,
            'end_time': self.EndTime,
            'kind':self.Kind
        }
#模式预约表
class Order(db.Model):
    __tablename__ = 'order'
    ID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    OrderUser = db.Column(db.String(100))  # 预约人
    OrderDateTime = db.Column(db.DateTime)  # 预约开工时间
    OrderUserID = db.Column(db.Integer)  # 预约人ID
    DateTime = db.Column(db.DateTime)  # 预约时间

    def to_dict(self):
        return {
            'id': self.ID,
            'order_user': self.OrderUser,
            'order_datetime': self.OrderDateTime.strftime('%Y-%m-%d %H:%M:%S') if self.OrderDateTime else None,
            'order_user_id': self.OrderUserID,
            'datetime': self.DateTime.strftime('%Y-%m-%d %H:%M:%S')
        }

class Solder(db.Model):
    __tablename__ = 'solder'

    SolderCode = db.Column(db.String(100), primary_key=True)  # 锡膏码
    Model = db.Column(db.String(100), nullable=False)  # 型号
    StationID = db.Column(db.Integer, nullable=False)  # 所在工位
    ExpireDate = db.Column(db.DateTime)  # 过期日期
    ProductDate = db.Column(db.DateTime)  # 生产日期
    ShelfLife = db.Column(db.Integer)  # 保质期
    BackLCTimes = db.Column(db.Integer)  # 回冷藏区次数
    Common2 = db.Column(db.String(100))  # 通用2
    Common3 = db.Column(db.String(100))  # 通用3
    StorageUser = db.Column(db.String(100))  # 入柜人
    StorageDateTime = db.Column(db.DateTime)  # 入柜时间
    OrderUser = db.Column(db.String(100))  # 预约人
    OrderDateTime = db.Column(db.DateTime)  # 预约时间
    RewarmStartUser = db.Column(db.String(100))  # 回温开始人
    RewarmStartDateTime = db.Column(db.DateTime)  # 回温开始时间
    RewarmEndDateTime = db.Column(db.DateTime)  # 回温结束时间
    StirStartDateTime = db.Column(db.DateTime)  # 搅拌开始时间
    ReadyOutDateTime = db.Column(db.DateTime)  # 准备出柜时间
    OutUser = db.Column(db.String(100))  # 取出人
    OutDateTime = db.Column(db.DateTime)  # 取出时间
    Decoded = db.Column(db.Boolean, nullable=False, default=False)  # 是否解码
    DecodedUser = db.Column(db.String(100))  # 解码人
    DecodedDateTime = db.Column(db.DateTime)  # 解码时间
    InTimes = db.Column(db.Integer, nullable=False)  # 入柜次数
    CurrentFlow = db.Column(db.Integer, nullable=False)  # 当前流程
    Code = db.Column(db.String(200), nullable=False)  # 二维码
    WorkNum = db.Column(db.String(100))  # 工单号
    MesError = db.Column(db.String(200))  # 其它错误内容
    AgainColdDateTime = db.Column(db.DateTime)  # 再次冷藏时间

    def to_dict(self):
        return {
            'solder_code': self.SolderCode,
            'model': self.Model,
            'station_id': self.StationID,
            'product_date': None if self.ProductDate is None else self.ProductDate.strftime('%Y-%m-%d'),
            'expire_date': None if self.ExpireDate is None else self.ExpireDate.strftime('%Y-%m-%d'),
            'shelf_life': self.ShelfLife,
            'BackLCTimes': self.BackLCTimes,
            'common2': self.Common2,
            'common3': self.Common3,
            'storage_user': self.StorageUser,
            'storage_datetime': self.StorageDateTime.strftime('%Y-%m-%d %H:%M:%S') if self.StorageDateTime else None,
            'order_user': self.OrderUser,
            'order_datetime': self.OrderDateTime.strftime('%Y-%m-%d %H:%M:%S') if self.OrderDateTime else None,
            'rewarm_start_user': self.RewarmStartUser,
            'rewarm_start_datetime': self.RewarmStartDateTime,
            'rewarm_end_datetime': self.RewarmEndDateTime,
            'stir_start_datetime': self.StirStartDateTime,
            'ready_out_datetime': self.ReadyOutDateTime,
            'out_user': self.OutUser,
            'out_datetime': self.OutDateTime,
            'decoded': self.Decoded,
            'decoded_user': self.DecodedUser,
            'decoded_datetime': self.DecodedDateTime,
            'in_times': self.InTimes,
            'current_flow': self.CurrentFlow,
            'code': self.Code,
            'work_num': self.WorkNum,
            'mes_error': self.MesError,
            'again_cold_datetime': self.AgainColdDateTime
        }

class SolderModel(db.Model):
    __tablename__ = 'soldermodel'

    Model = db.Column(db.String(100), primary_key=True)  # 型号
    ModelSysName = db.Column(db.String(100), nullable=False, unique=True)  # 系统名称
    MinColdNum = db.Column(db.Integer, nullable=False)  # 最小冷藏数
    RewarmNum = db.Column(db.Integer, nullable=False)  # 回温次数
    ReadyOutNum = db.Column(db.Integer, nullable=False)  # 准备出柜次数
    StirTime = db.Column(db.Integer, nullable=False)  # 搅拌时间
    StirSpeed = db.Column(db.Integer, nullable=False)  # 搅拌速度
    RewarmTime = db.Column(db.Integer, nullable=False)  # 回温时间
    RewarmMaxTime = db.Column(db.Integer, nullable=False)  # 最大回温时间
    ReadyOutTimeOut = db.Column(db.Integer, nullable=False)  # 准备出柜超时
    ShelfLife = db.Column(db.Integer, nullable=False)  # 保质期
    ZOffSet = db.Column(db.Float, nullable=False)  # Z轴偏移
    ModifyDateTime = db.Column(db.DateTime, nullable=False)  # 修改时间
    IfJiaoban = db.Column(db.String(255), default=None)  # 首次出库是否搅拌
    JiaobanRule = db.Column(db.String(255), default=None)  # 搅拌规则
    MinLcTime = db.Column(db.Integer, default=None)  # 最小冷藏时间
    OutChaoshiAutoLc = db.Column(db.Integer, default=None)  # 出库超时自动冷藏
    OutChaoshiAutoLcTimes = db.Column(db.Integer, default=None)  # 出库超时自动冷藏次数
    IfBackAfterJiaoban = db.Column(db.Integer, default=None)  # 搅拌后是否回冰柜
    TwiceChaoshiJinzhiInBinggui = db.Column(db.Integer, default=None)  # 二次超时禁止入冰柜
    TwiceInKu = db.Column(db.String(255), default=None)  # 再次入库选项
    # 新增字段
    Separator = db.Column(db.String(10), default=None)  # 分隔符
    ModelStart = db.Column(db.Integer, default=None)  # 型号起始位置
    ModelSeparatorStart = db.Column(db.Integer, default=None)  # 型号起始分隔符位置
    ModelLength = db.Column(db.Integer, default=None)  # 型号长度
    ProductionDateStart = db.Column(db.Integer, default=None)  # 生产日期起始位置
    ProductionDateSeparatorStart = db.Column(db.Integer, default=None)  # 生产日期起始分隔符位置
    ProductionDateLength = db.Column(db.Integer, default=None)  # 生产日期长度
    ShelfLifeStart = db.Column(db.Integer, default=None)  # 保质期起始位置
    ShelfLifeSeparatorStart = db.Column(db.Integer, default=None)  # 保质期起始分隔符位置
    ShelfLifeLength = db.Column(db.Integer, default=None)  # 保质期长度
    ExpirationDateStart = db.Column(db.Integer, default=None)  # 过期日期起始位置
    ExpirationDateSeparatorStart = db.Column(db.Integer, default=None)  # 过期日期起始分隔符位置
    ExpirationDateLength = db.Column(db.Integer, default=None)  # 过期日期长度
    def to_dict(self):
        return {
            'model': self.Model,
            'model_sys_name': self.ModelSysName,
            'min_cold_num': self.MinColdNum,
            'rewarm_num': self.RewarmNum,
            'ready_out_num': self.ReadyOutNum,
            'stir_time': self.StirTime,
            'stir_speed': self.StirSpeed,
            'rewarm_time': self.RewarmTime,
            'rewarm_max_time': self.RewarmMaxTime,
            'ready_out_timeout': self.ReadyOutTimeOut,
            'shelf_life': self.ShelfLife,
            'z_offset': self.ZOffSet,
            'modify_datetime': self.ModifyDateTime.strftime('%Y-%m-%d %H:%M:%S') if self.ModifyDateTime else None,
            'if_jiaoban': self.IfJiaoban,
            'jiaoban_rule': self.JiaobanRule,
            'min_lc_time': self.MinLcTime,
            'out_chaoshi_auto_lc': self.OutChaoshiAutoLc,
            'out_chaoshi_auto_lc_times': self.OutChaoshiAutoLcTimes,
            'if_back_after_jiaoban': self.IfBackAfterJiaoban,
            'twice_chaoshi_jinzhi_in_binggui': self.TwiceChaoshiJinzhiInBinggui,
            'twice_in_ku': self.TwiceInKu,
            # 新增字段
            'separator': self.Separator,
            'model_start': self.ModelStart,
            'model_separator_start': self.ModelSeparatorStart,
            'model_length': self.ModelLength,
            'production_date_start': self.ProductionDateStart,
            'production_date_separator_start': self.ProductionDateSeparatorStart,
            'production_date_length': self.ProductionDateLength,
            'shelf_life_start': self.ShelfLifeStart,
            'shelf_life_separator_start': self.ShelfLifeSeparatorStart,
            'shelf_life_length': self.ShelfLifeLength,
            'expiration_date_start': self.ExpirationDateStart,
            'expiration_date_separator_start': self.ExpirationDateSeparatorStart,
            'expiration_date_length': self.ExpirationDateLength
        }


class Barcoderule(db.Model):
    __tablename__ = 'barcoderule'

    ID = db.Column(db.Integer, primary_key=True)
    ModelStartLab = db.Column(db.Integer, default=None)
    ModelEndLab = db.Column(db.Integer, default=None)
    ModelStart = db.Column(db.Integer, default=None)
    ModelLength = db.Column(db.Integer, default=None)
    ShelfLifeStart = db.Column(db.Integer, default=None)
    ShelfLifeLength = db.Column(db.Integer, default=None)
    ShelfLifeStartLab = db.Column(db.Integer, default=None)
    ShelfLifeEndLab = db.Column(db.Integer, default=None)
    ProductTimeStart = db.Column(db.Integer, default=None)
    ProductTimeLength = db.Column(db.Integer, default=None)
    ExpTimeStart = db.Column(db.Integer, default=None)
    ExpTimeLength = db.Column(db.Integer, default=None)
    CodeStart = db.Column(db.Integer, default=None)
    CodeLength = db.Column(db.Integer, default=None)
    CodeStartLab = db.Column(db.Integer, default=None)
    CodeEndLab = db.Column(db.Integer, default=None)
    Length = db.Column(db.Integer, default=None)

    def to_dict(self):
        return {
            'ID': self.ID,
            'ModelStartLab': self.ModelStartLab,
            'ModelEndLab': self.ModelEndLab,
            'ModelStart': self.ModelStart,
            'ModelLength': self.ModelLength,
            'ShelfLifeStart': self.ShelfLifeStart,
            'ShelfLifeLength': self.ShelfLifeLength,
            'ShelfLifeStartLab': self.ShelfLifeStartLab,
            'ShelfLifeEndLab': self.ShelfLifeEndLab,
            'ProductTimeStart': self.ProductTimeStart,
            'ProductTimeLength': self.ProductTimeLength,
            'ExpTimeStart': self.ExpTimeStart,
            'ExpTimeLength': self.ExpTimeLength,
            'CodeStart': self.CodeStart,
            'CodeLength': self.CodeLength,
            'CodeStartLab': self.CodeStartLab,
            'CodeEndLab': self.CodeEndLab,
            "Length" : self.Length,
        }


class TemperatureRecord(db.Model):
    __tablename__ = 'temperaturerecord'
    id = db.Column(db.Integer, primary_key=True)
    ReTemper = db.Column(db.Float(8, 2), nullable=False)  # 回温温度
    ColdTemperS = db.Column(db.Float(8, 2), nullable=False)  # 冷温度（开始）
    ColdTemperM = db.Column(db.Float(8, 2), nullable=False)  # 冷温度（中间）
    ColdTemperD = db.Column(db.Float(8, 2), nullable=False)  # 冷温度（结束）
    DateTime = db.Column(db.DateTime, nullable=False)  # 时间

    def to_dict(self):
        # 将 ORM 对象转换为字典格式，方便返回 JSON
        return {
            're_temper': self.ReTemper,
            'cold_temper_s': self.ColdTemperS,
            'cold_temper_m': self.ColdTemperM,
            'cold_temper_d': self.ColdTemperD,
            'date_time': self.DateTime.strftime('%Y-%m-%d %H:%M:%S'),  # 格式化日期时间
        }

class SolderFlowRecord(db.Model):
    __tablename__ = 'solderflowrecord'
    id = db.Column(db.Integer, primary_key=True,  autoincrement=True)
    SolderCode = db.Column(db.String(100), nullable=False)  # 锡膏码
    UserID = db.Column(db.String(100), nullable=False)  # 工号
    UserName = db.Column(db.String(100), nullable=False)  # 姓名
    Type = db.Column(db.String(100), nullable=False)  # 类型
    DateTime = db.Column(db.DateTime, nullable=False)  # 日期时间

    def to_dict(self):
        # 将 ORM 对象转换为字典，方便返回 JSON 格式
        return {
            'solder_code': self.SolderCode,
            'user_id': self.UserID,
            'user_name': self.UserName,
            'type': self.Type,
            'date_time': self.DateTime.strftime('%Y-%m-%d %H:%M:%S'),  # 格式化为字符串
        }

class Station(db.Model):
    __tablename__ = 'station'

    StationID = db.Column(db.Integer, primary_key=True)  # 工位ID
    StaType = db.Column(db.String(255), default=None)  # 工位类型
    StaArea = db.Column(db.String(255), default=None)  # 工位区域
    StaLayer = db.Column(db.Integer, default=None)  # 工位层数
    StaColumn = db.Column(db.Integer, default=None)  # 工位列数
    XAxis = db.Column(db.Float, default=None)  # X轴
    YAxis = db.Column(db.Float, default=None)  # Y轴
    ZAxis = db.Column(db.Float, default=None)  # Z轴
    RAxis = db.Column(db.Float, default=None)  # R轴
    Disabled = db.Column(db.Integer, default=None)  # 是否禁用
    SolderCode = db.Column(db.String(100), default=None)  # 锡膏码
    ModifyDateTime = db.Column(db.DateTime, default=None)  # 修改时间

    def to_dict(self):
        return {
            'station_id': self.StationID,
            'sta_type': self.StaType,
            'sta_area': self.StaArea,
            'sta_layer': self.StaLayer,
            'sta_column': self.StaColumn,
            'x_axis': self.XAxis,
            'y_axis': self.YAxis,
            'z_axis': self.ZAxis,
            'r_axis': self.RAxis,
            'disabled': self.Disabled,
            'solder_code': self.SolderCode,
            'modify_datetime': self.ModifyDateTime
        }
