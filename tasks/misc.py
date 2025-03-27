def read_mode():
    """
    从本地文件 mode.txt 中读取模式
    :return: 返回模式的整数（0 或 1）
    """
    try:
        with open("mode.txt", "r") as file:
            mode = file.read().strip()
            return int(mode) if mode in ['0', '1'] else 0  # 默认返回 0
    except FileNotFoundError:
        return 1  # 如果文件不存在，默认返回 1

barcode_file_path = "res_asc.txt"

def get_current_user() -> int:
        user_cache_file = "user_cache.txt"
        with open(user_cache_file, "r", encoding="utf-8") as f:
            id_str = f.read()
            return int(id_str) if len(id_str) else 0
