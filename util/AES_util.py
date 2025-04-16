import os
import socket
from datetime import datetime, timedelta
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes

# 文件路径
CERTIFICATE_FILE = "certificate"
app_key = "4595e0fa9db68649465c3b84346d5e80"
EXTENSION_TIME = 6000000


def generate_certificate(*args):
    """生成证书文件，包含主机标识符和时间戳。"""
    import socket
    from datetime import datetime
    from Crypto.Cipher import AES
    from Crypto.Random import get_random_bytes
    from Crypto.Util.Padding import pad

    # 假设以下全局变量已经定义
    global app_key, CERTIFICATE_FILE, EXTENSION_TIME

    # 获取主机名和当前时间
    hostname = socket.gethostname()
    timestamp = int(datetime.now().timestamp()) + EXTENSION_TIME  # 未来的时间戳

    # 使用固定的 16 字节密钥
    random_key = bytes.fromhex(app_key)

    # 包含主机名和时间的标识符
    identifier = f"{hostname}|{timestamp}"

    # 加密标识符和密钥
    iv = get_random_bytes(16)
    cipher = AES.new(random_key, AES.MODE_CBC, iv)
    data_to_encrypt = f"{identifier}|{app_key}"
    encrypted_data = cipher.encrypt(pad(data_to_encrypt.encode(), AES.block_size))

    # 将 IV 和加密数据转换为十六进制字符串存储
    certificate_data = (iv + encrypted_data).hex()

    # 如果可变参数包含 "save_to_file"，则保存到文件
    if "not_save_to_file" in args:
        return certificate_data
    with open(CERTIFICATE_FILE, "w") as file:
        file.write(certificate_data)
    print(f"Certificate generated and saved to {CERTIFICATE_FILE}")

    return certificate_data


def validate_certificate(hex_data):
    """验证证书文件中的数据，检查时间戳和主机标识符。"""
    try:
        # 将十六进制字符串转换为字节
        content = bytes.fromhex(hex_data)

        # 分割 IV 和加密数据
        iv, encrypted_data = content[:16], content[16:]

        # 使用相同的密钥
        random_key = bytes.fromhex(app_key)

        # 解密数据
        cipher = AES.new(random_key, AES.MODE_CBC, iv)
        decrypted_data = unpad(cipher.decrypt(encrypted_data), AES.block_size).decode()

        # 分割标识符和密钥
        identifier, stored_key = decrypted_data.rsplit("|", 1)
        hostname, timestamp = identifier.split("|")

        # 检查主机名是否匹配
        current_hostname = socket.gethostname()
        if hostname != current_hostname:
            print(f"Host mismatch! Expected: {hostname}, Found: {current_hostname}")
            return False, 0

        # 检查时间是否过期
        current_time = int(datetime.now().timestamp())
        if current_time > int(timestamp):
            print("Certificate expired! Time difference exceeds 1 minute.")
            return False, 0

        print("Certificate is valid.")
        return True, int(timestamp) - current_time

    except Exception as e:
        print(f"Validation failed: {e}")
        return False, 0


# 测试生成和验证
# certificate_hex = generate_certificate("not_save_to_file")
# print("Generated Certificate (Hex):", certificate_hex)

# # 模拟读取并验证
# with open(CERTIFICATE_FILE, "r") as file:
#     loaded_hex_data = file.read()
#
# is_valid, time_diff = validate_certificate(loaded_hex_data)
# print(f"Validation Result: {is_valid}, Time Difference: {time_diff}s")
if __name__ == "__main__":
    generate_certificate()
