import logging
from datetime import datetime

# 创建日志记录器
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # 设置日志级别

# 创建文件处理器，日志将保存到 log 文件中
log_filename = datetime.now().strftime("log_%Y%m%d_%H.log")
file_handler = logging.FileHandler(log_filename, encoding="utf8")
file_handler.setLevel(logging.DEBUG)

# 创建格式化器，设置日志格式
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)

# 将处理器添加到记录器中
logger.addHandler(file_handler)

# 添加控制台处理器（可选）
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
