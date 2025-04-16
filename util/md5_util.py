import hashlib

# MD5盐
SECRET = "salt"


def md5_hex(input_string: str) -> str:
    """
    将输入字符串加密为 MD5 哈希值（16进制）。
    :param input_string: 待加密的字符串
    :return: MD5 哈希值
    """
    md5 = hashlib.md5()
    md5.update(input_string.encode("utf-8"))
    return md5.hexdigest()
