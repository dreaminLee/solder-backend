from config.barcode_parse_config import seperator
from config.barcode_parse_config import model_row, model_start_pos, model_length
from config.barcode_parse_config import prod_date_row, prod_date_start_pos, prod_date_length
from config.barcode_parse_config import expire_date_row, expire_date_start_pos, expire_date_length
from config.barcode_parse_config import shelf_life_row, shelf_life_start_pos, shelf_life_length

def parse_barcode(barcode):
    """
    根据条码规则解析条码
    :param barcode: 输入的产品条码
    :return: 解析后的字典，包含各部分信息
    """
    parsed_result = {
        "model": "",
        "product_date": "",
        "expire_date": "",
        "shelf_life": ""
    }
    try:
        if seperator:
            parts = barcode.split(seperator)
            if model_row >= 0:
                parsed_result["model"] = parts[model_row]
            if prod_date_row >= 0:
                parsed_result["product_date"] = parts[prod_date_row]
            if expire_date_row >= 0:
                parsed_result["expire_date"] = parts[expire_date_row]
            if shelf_life_row >= 0:
                parsed_result["shelf_life"] = parts[shelf_life_row]
        else:
            if model_start_pos >= 0:
                parsed_result["model"] = barcode[model_start_pos-1 : model_start_pos-1 + model_length]
            if prod_date_start_pos >= 0:
                parsed_result["product_date"] = barcode[prod_date_start_pos-1 : prod_date_start_pos-1 + prod_date_length]
            if expire_date_start_pos >= 0:
                parsed_result["expire_date"] = barcode[expire_date_start_pos-1 : expire_date_start_pos-1 + expire_date_length]
            if shelf_life_start_pos >= 0:
                parsed_result["shelf_life"] = barcode[shelf_life_start_pos-1 : shelf_life_start_pos-1 + shelf_life_length]
        return parsed_result
    except Exception as exp:
        return None


if __name__ == '__main__':
    barcode = "RLT25032400051&RLT.NRK0307&1&"

    # 调用函数解析条码
    try:
        result = parse_barcode(barcode)
        print("解析结果:", result)
    except ValueError as e:
        print("错误:", e)
