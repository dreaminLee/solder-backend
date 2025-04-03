from models import SolderModel
from util.db_connection import db_instance
session = db_instance.get_session()
def parse_barcode(barcode):
    """
    根据条码规则解析条码
    :param barcode: 输入的产品条码
    :return: 解析后的字典，包含各部分信息
    """
    # config = {
    #     "Length": 15,
    #     "CodeStartLength": 8,
    #     "CodeLength": 7,
    #     "ModelStartLength": 0,
    #     "ModelLength": 2,
    #     "ProductionDateStartLength": 2,
    #     "ProductionDateLength": 6,
    #     "ExpireDateStartLength": -1,
    #     "ExpireDateLength": -1,
    #     "Common1StartLength": -1,
    #     "Common1Length": -1,
    #     "Common2StartLength": -1,
    #     "Common2Length": -1,
    #     "Common3StartLength": -1,
    #     "Common3Length": -1,
    # }

    parsed_result = {}
    # 校验条码总长度是否正确
    if len(barcode) == 0:
        raise ValueError(f"条码长度不匹配，实际长度为 {len(barcode)}")

    # # 遍历配置规则并解析条码
    # for key, start_key, length_key in [
    #     ("唯一码", "CodeStartLength", "CodeLength"),
    #     ("型号", "ModelStartLength", "ModelLength"),
    #     ("生产日期", "ProductionDateStartLength", "ProductionDateLength"),
    #     ("到期日期", "ExpireDateStartLength", "ExpireDateLength"),
    #     ("通用1", "Common1StartLength", "Common1Length"),
    #     ("通用2", "Common2StartLength", "Common2Length"),
    #     ("通用3", "Common3StartLength", "Common3Length"),
    # ]:
    #     start = config[start_key]
    #     length = config[length_key]
    #     if start != -1 and length != -1:
    #         parsed_result[key] = barcode[start : start + length]
    solder_model = session.query(SolderModel).first()
    # 有分隔符
    if solder_model.Separator:
        separator = solder_model.Separator
        # 型号按分隔符位置获取
        if solder_model.ModelSeparatorStart and solder_model.ModelLength:
            # 型号在第n个分隔符后
            n = solder_model.ModelSeparatorStart
            length = solder_model.ModelLength
            # 型号所在的index = 前面分割符index + 1
            model_start_index = find_n_substring_index(barcode, separator, n) + 1
            # 根据型号的起始位置和长度从barcode中获取到型号
            model = get_substring(barcode, model_start_index, length)
            # 直接添加元素
            parsed_result['model'] = model
        # 生产日期按分隔符位置获取
        if solder_model.ProductionDateSeparatorStart and solder_model.ProductionDateLength:
            # 生产日期在第n个分隔符后
            n = solder_model.ProductionDateSeparatorStart
            length = solder_model.ProductionDateLength
            # 生产日期所在的index = 前面分割符index + 1
            product_date_start_index = find_n_substring_index(barcode,separator,n) + 1
            # 根据生产日期的起始位置和长度从barcode中获取到生产日期
            product_date = get_substring(barcode,product_date_start_index,length)
            # 直接添加元素
            parsed_result['product_date'] = product_date
        # 过期日期按分隔符位置获取
        elif solder_model.ExpirationDateSeparatorStart and solder_model.ExpirationDateLength:
            # 过期日期在第n个分隔符后
            n = solder_model.ExpirationDateSeparatorStart
            length = solder_model.ExpirationDateLength
            # 过期日期所在的index = 前面分隔符index + 1
            expire_date_start_index = find_n_substring_index(barcode,separator,n) + 1
            # 根据过期日期的起始位置和长度从barcode中获取到过期日期
            expire_date = get_substring(barcode,expire_date_start_index,length)
            # 直接添加元素
            parsed_result['expire_date'] = expire_date
        # 保质期按分隔符位置获取
        elif solder_model.ShelfLifeSeparatorStart and solder_model.ShelfLifeLength:
            # 保质期在第n个分隔符后
            n = solder_model.ShelfLifeSeparatorStart
            length = solder_model.ShelfLifeLength
            # 保质期所在的index= 保质期前的分隔符所在的index+1
            shelf_life_start_index = find_n_substring_index(barcode,separator,n) + 1
            # 根据过期日期的起始位置和长度从barcode中获取到过期日期
            shelf_life = get_substring(barcode,shelf_life_start_index,length)
            # 直接添加元素
            parsed_result['shelf_life'] = shelf_life
    # 型号按位置获取
    if solder_model.ModelStart and solder_model.ModelLength:
        model_start_index = solder_model.ModelStart
        length = solder_model.ModelLength
        # 根据型号的起始位置和长度从barcode中获取到型号
        model = get_substring(barcode, model_start_index, length)
        # 直接添加元素
        parsed_result['model'] = model
    # 生产日期按位置获取
    if solder_model.ProductionDateStart and solder_model.ProductionDateLength:
        product_date_start_index = solder_model.ProductionDateStart
        length = solder_model.ProductionDateLength
        # 根据生产日期的起始位置和长度从barcode中获取到生产日期
        product_date = get_substring(barcode, product_date_start_index, length)
        # 直接添加元素
        parsed_result['product_date'] = product_date
    if solder_model.ExpirationDateStart and solder_model.ExpirationDateLength:
        expire_date_start_index = solder_model.ExpirationDateStart
        length = solder_model.ExpirationDateLength
        # 根据过期日期的起始位置和长度从barcode中获取到过期日期
        expire_date = get_substring(barcode, expire_date_start_index, length)
        # 直接添加元素
        parsed_result['expire_date'] = expire_date
    if solder_model.ShelfLifeStart and solder_model.ShelfLifeLength:
        shelf_life_start_index = solder_model.ShelfLifeStart
        length = solder_model.ShelfLifeLength
        # 根据过期日期的起始位置和长度从barcode中获取到过期日期
        shelf_life = get_substring(barcode, shelf_life_start_index, length)
        # 直接添加元素
        parsed_result['shelf_life'] = shelf_life
    return parsed_result

def find_n_substring_index(string, substring, n):
    """
    查找字符串中第 n 个子串的索引

    :param string: 要搜索的主字符串
    :param substring: 要查找的子字符串
    :param n: 要查找的子字符串的序号（从 1 开始）
    :return: 第 n 个子串的起始索引，如果未找到则返回 -1
    """
    start = 0
    for _ in range(n):
        start = string.find(substring, start)
        if start == -1:
            return -1
        start += len(substring)
    return start - len(substring)
def get_substring(string, start_index, length):
    """
    此函数用于根据给定的起始索引和长度从字符串中获取子串。
    参数:
    string: 原始字符串。
    start_index (int): 子串的起始索引。
    length (int): 子串的长度。
    返回:
    str: 获取到的子串。如果索引超出范围，返回空字符串。
    """
    end_index = start_index + length
    return string[start_index:end_index]

# 示例条码
barcode = "10107.00000014.00A+2503+501139+Q00550+S3X58-M406-3++0.5+00038"

# 调用函数解析条码
try:
    result = parse_barcode(barcode)
    print("解析结果:", result)
except ValueError as e:
    print("错误:", e)
