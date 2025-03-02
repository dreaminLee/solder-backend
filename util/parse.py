def parse_barcode(barcode):
    """
    根据条码规则解析条码
    :param barcode: 输入的产品条码
    :return: 解析后的字典，包含各部分信息
    """
    config = {
        "Length": 15,
        "CodeStartLength": 8,
        "CodeLength": 7,
        "ModelStartLength": 0,
        "ModelLength": 2,
        "ProductionDateStartLength": 2,
        "ProductionDateLength": 6,
        "ExpireDateStartLength": -1,
        "ExpireDateLength": -1,
        "Common1StartLength": -1,
        "Common1Length": -1,
        "Common2StartLength": -1,
        "Common2Length": -1,
        "Common3StartLength": -1,
        "Common3Length": -1,
    }

    parsed_result = {}

    # 校验条码总长度是否正确
    if len(barcode) != config["Length"]:
        raise ValueError(f"条码长度不匹配，期望长度为 {config['Length']}，实际长度为 {len(barcode)}")

    # 遍历配置规则并解析条码
    for key, start_key, length_key in [
        ("唯一码", "CodeStartLength", "CodeLength"),
        ("型号", "ModelStartLength", "ModelLength"),
        ("生产日期", "ProductionDateStartLength", "ProductionDateLength"),
        ("到期日期", "ExpireDateStartLength", "ExpireDateLength"),
        ("通用1", "Common1StartLength", "Common1Length"),
        ("通用2", "Common2StartLength", "Common2Length"),
        ("通用3", "Common3StartLength", "Common3Length"),
    ]:
        start = config[start_key]
        length = config[length_key]
        if start != -1 and length != -1:
            parsed_result[key] = barcode[start : start + length]

    return parsed_result


# 示例条码
# barcode = "AB20230101001234"
#
# # 调用函数解析条码
# try:
#     result = parse_barcode(barcode)
#     print("解析结果:", result)
# except ValueError as e:
#     print("错误:", e)
